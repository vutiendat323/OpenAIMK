"""
ByteTrack-style multi-object tracker.

Implements the core ByteTrack algorithm:
- Kalman-filter-based state estimation per track.
- Two-stage IoU association (high-confidence → low-confidence).
- Track lifecycle management (creation, update, deletion).

Uses filterpy for the Kalman filter and scipy for the Hungarian algorithm.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
from filterpy.kalman import KalmanFilter
from scipy.optimize import linear_sum_assignment

from Visual.domain.geometry import iou_batch, xywh_to_xyxy, xyxy_to_xywh


class STrack:
    """Single-object track with a Kalman filter."""

    _next_id = 1

    def __init__(self, bbox: np.ndarray, score: float):
        """
        Args:
            bbox: [x1, y1, x2, y2] in pixel coordinates.
            score: Detection confidence.
        """
        self.id = STrack._next_id
        STrack._next_id += 1

        self.score = score
        self.hits = 1           # consecutive frames with a match
        self.age = 0            # total frames since creation
        self.time_since_update = 0
        self._state: np.ndarray = xyxy_to_xywh(bbox)  # [cx, cy, w, h]

        # Kalman filter: state = [cx, cy, w, h, vcx, vcy, vw, vh]
        self._kf = KalmanFilter(dim_x=8, dim_z=4)
        self._kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0, 0],
            [0, 1, 0, 0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0, 0, 1, 0],
            [0, 0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 1],
        ])
        self._kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0, 0],
        ])

        # Measurement noise — trust position (cx,cy) more than size (w,h)
        self._kf.R[2:, 2:] *= 10.0
        self._kf.P[4:, 4:] *= 1000.0  # high initial velocity uncertainty
        self._kf.P *= 10.0
        # Process noise — higher for velocity components so the filter can
        # track rapid / non-linear motion (head turns, sudden direction changes).
        # Default filterpy Q is identity; scale position noise moderately and
        # velocity noise aggressively to let the filter trust new measurements
        # over the constant-velocity prediction during fast movement.
        self._kf.Q[4:, 4:] *= 10.0
        self._kf.Q[:4, :4] *= 1.0

        self._kf.x[:4] = self._state.reshape(4, 1)

        # Embedding gallery for appearance-based ReID matching
        self._embeddings: list = []      # list[np.ndarray]
        self._max_gallery: int = 10

    def add_embedding(self, emb: np.ndarray) -> None:
        """Append an embedding to the rolling gallery.

        If the gallery exceeds ``_max_gallery``, the oldest entry is evicted.
        """
        self._embeddings.append(emb)
        if len(self._embeddings) > self._max_gallery:
            self._embeddings.pop(0)

    @property
    def gallery_centroid(self) -> np.ndarray | None:
        """Mean of stored embeddings, L2-normalized.

        Returns ``None`` when the gallery is empty.
        """
        if len(self._embeddings) == 0:
            return None
        centroid = np.mean(np.stack(self._embeddings, axis=0), axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm < 1e-12:
            return None
        return centroid / norm

    def predict(self) -> np.ndarray:
        """Advance the Kalman filter and return the predicted bbox [x1,y1,x2,y2]."""
        self._kf.predict()
        self.age += 1
        self.time_since_update += 1
        return self.tlwh_to_tlbr(self._kf.x[:4].reshape(-1))

    def update(self, bbox: np.ndarray) -> None:
        """Correct the Kalman filter with an observed bbox [x1,y1,x2,y2]."""
        self.time_since_update = 0
        self.hits += 1
        meas = xyxy_to_xywh(bbox)
        self._kf.update(meas.reshape(4, 1))

    @staticmethod
    def tlwh_to_tlbr(tlwh: np.ndarray) -> np.ndarray:
        """Convert [cx, cy, w, h] → [x1, y1, x2, y2]."""
        ret = tlwh.copy()
        ret[0] = tlwh[0] - tlwh[2] / 2
        ret[1] = tlwh[1] - tlwh[3] / 2
        ret[2] = tlwh[0] + tlwh[2] / 2
        ret[3] = tlwh[1] + tlwh[3] / 2
        return ret

    @property
    def bbox(self) -> np.ndarray:
        """Current bounding-box estimate [x1, y1, x2, y2]."""
        return self.tlwh_to_tlbr(self._kf.x[:4].reshape(-1))

    @classmethod
    def reset_id_counter(cls) -> None:
        cls._next_id = 1


class ByteTrack:
    """
    ByteTrack multi-object tracker.

    Implements the two-stage association strategy:
    1. Match high-confidence detections to existing tracks (strict IoU).
    2. Match remaining low-confidence detections to unmatched tracks (lenient IoU).
    """

    def __init__(
        self,
        track_buffer: int = 30,
        track_thresh: float = 0.5,
        match_thresh: float = 0.3,
        match_thresh_second: float = 0.5,
        track_init_thresh: float = 0.7,
        reid_weight: float = 0.6,
        gallery_size: int = 10,
    ):
        """
        Args:
            track_buffer: Frames to keep a lost track before deletion.
            track_thresh: Confidence above which a detection is 'high-confidence'.
            match_thresh: Fused cost threshold for the first association.
            match_thresh_second: Fused cost threshold for the second association.
            track_init_thresh: Minimum confidence to initialise a new track.
            reid_weight: Weight for appearance in fused cost (0=IoU only, 1=appearance only).
            gallery_size: Max embeddings stored per STrack.
        """
        self.track_buffer = track_buffer
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.match_thresh_second = match_thresh_second
        self.track_init_thresh = track_init_thresh
        self.reid_weight = reid_weight
        self.gallery_size = gallery_size

        self._tracks: List[STrack] = []

    @property
    def active_tracks(self) -> List[STrack]:
        """Tracks that have been matched at least once."""
        return [t for t in self._tracks if t.hits > 0]

    def update(
        self,
        detections: List[Tuple[float, float, float, float, float]],
        embeddings: List[np.ndarray] | None = None,
    ) -> List[Tuple[float, float, float, float, int, float]]:
        """
        Run one tracking step.

        Args:
            detections: List of (x1, y1, x2, y2, confidence).
            embeddings: Optional list of L2-normalized embedding vectors,
                one per detection in the same order. When provided, the
                association cost fuses IoU with cosine similarity.

        Returns:
            List of (x1, y1, x2, y2, track_id, confidence) for active tracks.
        """
        # --- predict all existing tracks forward ---
        for track in self._tracks:
            track.predict()

        if len(detections) == 0:
            self._prune_tracks()
            return self._format_output()

        dets = np.array(detections)  # (N, 5)

        # Normalize embeddings: None or empty → list of None per detection
        if embeddings is None or len(embeddings) == 0:
            emb_list: list = [None] * len(dets)
        else:
            emb_list = list(embeddings)

        # split into high- and low-confidence
        high_mask = dets[:, 4] >= self.track_thresh
        low_mask = ~high_mask

        dets_high = dets[high_mask]
        dets_low = dets[low_mask]

        # Build per-confidence-group embedding lists
        high_indices = np.where(high_mask)[0]
        low_indices = np.where(low_mask)[0]
        embs_high = [emb_list[i] for i in high_indices] if len(high_indices) > 0 else []
        embs_low = [emb_list[i] for i in low_indices] if len(low_indices) > 0 else []

        matched_track_ids: set = set()
        matched_det_indices: dict = {}  # track_id → det_idx (in dets_high)

        # --- first association: high-confidence detections ---
        if len(dets_high) > 0 and len(self._tracks) > 0:
            cost_mat = self._build_cost_matrix(
                dets_high[:, :4], self._tracks, embs_high,
            )
            # Zero out costs below threshold
            cost_mat[cost_mat < self.match_thresh] = 0.0

            det_idx, track_idx = linear_sum_assignment(-cost_mat)

            for di, ti in zip(det_idx, track_idx):
                if cost_mat[di, ti] >= self.match_thresh:
                    track = self._tracks[ti]
                    track.update(dets_high[di, :4])
                    track.score = dets_high[di, 4]
                    if embs_high[di] is not None:
                        track.add_embedding(embs_high[di])
                    matched_track_ids.add(track.id)
                    matched_det_indices[track.id] = di

        # --- second association: low-confidence with unmatched tracks ---
        unmatched_tracks = [t for t in self._tracks
                            if t.id not in matched_track_ids and t.time_since_update > 0]

        if len(dets_low) > 0 and len(unmatched_tracks) > 0:
            cost_mat = self._build_cost_matrix(
                dets_low[:, :4], unmatched_tracks, embs_low,
            )
            cost_mat[cost_mat < self.match_thresh_second] = 0.0

            det_idx, track_idx = linear_sum_assignment(-cost_mat)

            for di, ti in zip(det_idx, track_idx):
                if cost_mat[di, ti] >= self.match_thresh_second:
                    track = unmatched_tracks[ti]
                    track.update(dets_low[di, :4])
                    track.score = dets_low[di, 4]
                    if embs_low[di] is not None:
                        track.add_embedding(embs_low[di])
                    matched_track_ids.add(track.id)

        # --- create new tracks from unmatched high-confidence detections ---
        all_matched_det_boxes = set()
        for ti, di in matched_det_indices.items():
            if di < len(dets_high):
                all_matched_det_boxes.add(tuple(dets_high[di, :4]))

        for i, d in enumerate(dets_high):
            if tuple(d[:4]) not in all_matched_det_boxes and d[4] >= self.track_init_thresh:
                track = STrack(d[:4], d[4])
                track._max_gallery = self.gallery_size
                if i < len(embs_high) and embs_high[i] is not None:
                    track.add_embedding(embs_high[i])
                self._tracks.append(track)
                matched_track_ids.add(track.id)

        self._prune_tracks()
        return self._format_output()

    def _build_cost_matrix(
        self,
        det_bboxes: np.ndarray,
        tracks: List[STrack],
        det_embs: list,
    ) -> np.ndarray:
        """Build fused IoU + appearance cost matrix.

        Args:
            det_bboxes: (D, 4) detection bounding boxes.
            tracks: List of T track objects.
            det_embs: List of D embedding arrays (or None entries).

        Returns:
            (D, T) cost matrix where cost = (1-w)*iou + w*cosine_sim.
        """
        track_bboxes = np.array([t.bbox for t in tracks])
        iou_mat = iou_batch(det_bboxes, track_bboxes)  # (D, T)

        # If no embeddings provided or all None, return IoU only
        has_any_embedding = any(e is not None for e in det_embs)
        if not has_any_embedding:
            return iou_mat

        cos_mat = np.zeros_like(iou_mat)
        for di, det_emb in enumerate(det_embs):
            if det_emb is None:
                continue
            for ti, track in enumerate(tracks):
                centroid = track.gallery_centroid
                if centroid is not None:
                    cos_mat[di, ti] = float(np.dot(det_emb, centroid))

        iou_weight = 1.0 - self.reid_weight
        app_weight = self.reid_weight
        fused = iou_weight * iou_mat + app_weight * cos_mat
        return fused

    def _prune_tracks(self) -> None:
        """Remove tracks that have been lost for too long."""
        self._tracks = [
            t for t in self._tracks
            if t.time_since_update <= self.track_buffer
        ]

    def _format_output(self) -> List[Tuple[float, float, float, float, int, float]]:
        """Build output list from active tracks."""
        out: List[Tuple[float, float, float, float, int, float]] = []
        for track in self.active_tracks:
            bbox = track.bbox
            out.append((
                float(bbox[0]), float(bbox[1]),
                float(bbox[2]), float(bbox[3]),
                track.id,
                float(track.score),
            ))
        return out

    def clear(self) -> None:
        """Drop every track but keep counting ids, so none is ever reused."""
        self._tracks.clear()

    def reset(self) -> None:
        """Clear all tracks and reset ID counter."""
        self._tracks.clear()
        STrack.reset_id_counter()
