"""
SCRFD face detector via ONNX Runtime.

Wraps SCRFD ONNX models for real-time face detection.
Supports GPU (CUDA) and CPU inference via onnxruntime.

Auto-detects model format:
  - 3-stride (P3): 9 outputs, strides [8, 16, 32], raw scores (needs sigmoid)
  - 5-stride (P5): 15 outputs, strides [8, 16, 32, 64, 128], post-sigmoid scores

Each bbox is predicted as distances (dl, dt, dr, db) from an anchor center
and must be decoded to (x1, y1, x2, y2).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort

from Visual.domain.faces import FaceDetection


class SCRFDFaceDetector:
    """SCRFD ONNX face detector.

    Usage:
        det = SCRFDFaceDetector("models/scrfd_2.5g_face.onnx", device="cuda")
        det.warmup()
        faces = det.detect(frame_bgr)  # List[FaceDetection]
    """

    def __init__(
        self,
        model_path: str,
        conf_thresh: float = 0.5,
        nms_thresh: float = 0.4,
        input_size: Tuple[int, int] = (640, 640),
        device: str = "cpu",
    ):
        """
        Args:
            model_path: Path to the SCRFD ONNX model file.
            conf_thresh: Minimum confidence for a face detection.
            nms_thresh: IoU threshold for NMS.
            input_size: Model input resolution (width, height).
            device: "cpu" or "cuda".
        """
        self._model_path = model_path
        self._conf_thresh = conf_thresh
        self._nms_thresh = nms_thresh
        self._input_size = input_size  # (W, H)

        # Select execution provider
        if device == "cuda":
            self._providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        else:
            self._providers = ["CPUExecutionProvider"]

        self._session: Optional[ort.InferenceSession] = None
        self._input_name: str = ""
        self._output_names: List[str] = []

        # Detected at load time
        self._strides: List[int] = []
        self._needs_sigmoid: bool = True
        self._anchors: List[np.ndarray] = []  # center coords per stride

        self._load_model()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Create ONNX Runtime session and auto-detect model format."""
        try:
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 2  # limit CPU threads to avoid contention
            self._session = ort.InferenceSession(
                self._model_path,
                sess_options=opts,
                providers=self._providers,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load SCRFD ONNX model from '{self._model_path}'. "
                f"Make sure the model file exists and onnxruntime is installed.\n"
                f"Original error: {e}"
            )

        self._input_name = self._session.get_inputs()[0].name
        self._output_names = [o.name for o in self._session.get_outputs()]

        n_outputs = len(self._output_names)
        if n_outputs % 3 != 0:
            raise RuntimeError(
                f"Expected groups of 3 outputs (score, bbox, kps), "
                f"got {n_outputs}. Unknown model format."
            )

        n_strides = n_outputs // 3

        # Determine strides by running a dummy forward pass to get
        # concrete output shapes (dynamic axes show as None)
        target_w, target_h = self._input_size
        dummy = np.random.randn(1, 3, target_h, target_w).astype(np.float32)
        dummy_outs = self._session.run(
            [o.name for o in self._session.get_outputs()],
            {self._input_name: dummy},
        )
        n_anchors_0 = dummy_outs[0].shape[0]  # e.g. 12800 or 6400
        grid_cells = (target_w // 8) * (target_h // 8)  # 80*80 = 6400
        anchors_per_cell = n_anchors_0 // grid_cells

        # Detect sigmoid need: raw logits on random input are usually
        # small but could be positive; post-sigmoid are never negative.
        # If any score is negative, they're definitely raw logits.
        self._needs_sigmoid = float(dummy_outs[0].min()) < 0

        # Compute strides from actual output sizes (from dummy run)
        self._strides = []
        for i in range(n_strides):
            n_anchors = dummy_outs[i].shape[0]  # concrete value
            for s in [8, 16, 32, 64, 128]:
                cells = (target_w // s) * (target_h // s)
                if cells * anchors_per_cell == n_anchors:
                    self._strides.append(s)
                    break
            else:
                raise RuntimeError(
                    f"Cannot determine stride for output {i} "
                    f"with {n_anchors} anchors at input {target_w}x{target_h}"
                )

        print(f"[face] model: {n_strides} strides {self._strides}, "
              f"{anchors_per_cell} anchor(s)/cell, "
              f"scores={'sigmoid' if self._needs_sigmoid else 'post-sigmoid'}")

        self._build_anchors(anchors_per_cell)

    def _build_anchors(self, anchors_per_cell: int) -> None:
        """Pre-compute anchor center points for each detection stride.

        For models with anchors_per_cell > 1, each center is duplicated.
        """
        target_w, target_h = self._input_size
        self._anchors = []

        for stride in self._strides:
            fmap_h = target_h // stride
            fmap_w = target_w // stride

            # Anchor centres sit on the cell's top-left corner, as SCRFD was
            # trained (insightface scrfd.py: `mgrid * stride`).  Adding half a
            # cell shifted every box and landmark down-right by stride/2 in
            # input space -- 8 to 32 px on the frame, and by a different amount
            # per input size, which fed straight into the PnP pose.
            shift_x = np.arange(0, fmap_w) * stride
            shift_y = np.arange(0, fmap_h) * stride
            xx, yy = np.meshgrid(shift_x, shift_y)

            centers = np.stack((xx.ravel(), yy.ravel()), axis=1).astype(np.float32)

            # Duplicate centers if model has multiple anchors per cell.
            # Model output is interleaved: cell0_a0, cell0_a1, cell1_a0, cell1_a1...
            # so we repeat each center consecutively (not tile which groups by anchor).
            if anchors_per_cell > 1:
                centers = np.repeat(centers, anchors_per_cell, axis=0)

            self._anchors.append(centers)

    def warmup(self) -> None:
        """Run a dummy inference to warm CUDA kernels and allocate memory."""
        dummy = np.zeros(
            (self._input_size[1], self._input_size[0], 3),
            dtype=np.uint8,
        )
        self.detect(dummy)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def detect(self, frame_bgr: np.ndarray) -> List[FaceDetection]:
        """
        Detect faces in a BGR frame.

        Args:
            frame_bgr: BGR image (H, W, 3), uint8.

        Returns:
            List of FaceDetection objects, sorted by confidence descending.
        """
        if self._session is None:
            self._load_model()

        orig_h, orig_w = frame_bgr.shape[:2]

        # 1. Preprocess: letterbox + normalize
        input_tensor, scale, pad_left, pad_top = self._preprocess(frame_bgr)

        # 2. Inference — run all output heads
        outputs = self._session.run(
            self._output_names,
            {self._input_name: input_tensor},
        )

        # 3. Postprocess: decode + filter + NMS + scale back
        detections = self._postprocess(
            outputs, scale, pad_left, pad_top, orig_w, orig_h,
        )

        return detections

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    def _preprocess(
        self, frame_bgr: np.ndarray,
    ) -> Tuple[np.ndarray, float, int, int]:
        """
        Letterbox resize + normalize for SCRFD.

        Returns:
            (input_tensor, scale, pad_left, pad_top)
            input_tensor: (1, 3, H, W) float32, normalized to [-1, 1]
            scale: the resize scale factor applied
            pad_left, pad_top: padding offsets
        """
        target_w, target_h = self._input_size
        h, w = frame_bgr.shape[:2]

        # Keep-ratio resize
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Convert BGR to RGB
        resized_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Pad to target size (centered padding — SCRFD convention)
        pad_w = target_w - new_w
        pad_h = target_h - new_h
        pad_left = pad_w // 2
        pad_top = pad_h // 2
        pad_right = pad_w - pad_left
        pad_bottom = pad_h - pad_top

        padded = cv2.copyMakeBorder(
            resized_rgb,
            pad_top, pad_bottom, pad_left, pad_right,
            cv2.BORDER_CONSTANT,
            value=(0, 0, 0),
        )

        # Normalize: (pixel - 127.5) / 128.0  →  range ~[-1, 1]
        padded_f = padded.astype(np.float32)
        padded_f = (padded_f - 127.5) / 128.0

        # HWC -> CHW -> BCHW
        tensor = np.transpose(padded_f, (2, 0, 1))  # CHW
        tensor = np.expand_dims(tensor, axis=0)      # BCHW

        return tensor, scale, pad_left, pad_top

    # ------------------------------------------------------------------
    # Postprocessing
    # ------------------------------------------------------------------

    def _postprocess(
        self,
        outputs: List[np.ndarray],
        scale: float,
        pad_left: int,
        pad_top: int,
        orig_w: int,
        orig_h: int,
    ) -> List[FaceDetection]:
        """
        Decode multi-scale SCRFD outputs into FaceDetection objects.
        """
        n_strides = len(self._strides)

        # Split outputs into score, bbox, kps groups
        score_outputs = outputs[:n_strides]
        bbox_outputs = outputs[n_strides : 2 * n_strides]
        kps_outputs = outputs[2 * n_strides :]

        all_bboxes = []
        all_scores = []
        all_kps = []

        for i in range(n_strides):
            stride = self._strides[i]
            anchors = self._anchors[i]  # (N_i, 2)

            scores_i = score_outputs[i].flatten().astype(np.float32)  # (N_i,)
            bboxes_i = bbox_outputs[i].astype(np.float32)             # (N_i, 4)
            kps_i = kps_outputs[i].astype(np.float32)                 # (N_i, 10)

            # Apply sigmoid if scores are raw logits
            if self._needs_sigmoid:
                scores_i = 1.0 / (1.0 + np.exp(-scores_i))

            # Decode bbox: distances from anchor center → (x1, y1, x2, y2).
            # Bbox values are in stride-scaled units, so multiply by stride.
            x1 = anchors[:, 0] - bboxes_i[:, 0] * stride
            y1 = anchors[:, 1] - bboxes_i[:, 1] * stride
            x2 = anchors[:, 0] + bboxes_i[:, 2] * stride
            y2 = anchors[:, 1] + bboxes_i[:, 3] * stride
            decoded_bboxes = np.stack([x1, y1, x2, y2], axis=1)

            # Decode keypoints: anchor center + offset * stride
            decoded_kps = np.zeros_like(kps_i)
            for k in range(5):
                decoded_kps[:, 2 * k] = anchors[:, 0] + kps_i[:, 2 * k] * stride
                decoded_kps[:, 2 * k + 1] = anchors[:, 1] + kps_i[:, 2 * k + 1] * stride

            all_bboxes.append(decoded_bboxes)
            all_scores.append(scores_i)
            all_kps.append(decoded_kps)

        # Concatenate all strides
        bboxes = np.concatenate(all_bboxes, axis=0)  # (N_total, 4)
        scores = np.concatenate(all_scores, axis=0)  # (N_total,)
        kps = np.concatenate(all_kps, axis=0)        # (N_total, 10)

        if len(scores) == 0:
            return []

        # Filter by confidence
        mask = scores >= self._conf_thresh
        bboxes = bboxes[mask]
        scores = scores[mask]
        kps = kps[mask]

        if len(bboxes) == 0:
            return []

        # Scale coordinates from model input space back to original frame
        bboxes[:, 0] = (bboxes[:, 0] - pad_left) / scale
        bboxes[:, 1] = (bboxes[:, 1] - pad_top) / scale
        bboxes[:, 2] = (bboxes[:, 2] - pad_left) / scale
        bboxes[:, 3] = (bboxes[:, 3] - pad_top) / scale

        # Clamp to frame bounds
        bboxes[:, 0] = np.clip(bboxes[:, 0], 0, orig_w - 1)
        bboxes[:, 1] = np.clip(bboxes[:, 1], 0, orig_h - 1)
        bboxes[:, 2] = np.clip(bboxes[:, 2], 0, orig_w - 1)
        bboxes[:, 3] = np.clip(bboxes[:, 3], 0, orig_h - 1)

        # Scale landmarks
        kps[:, 0::2] = (kps[:, 0::2] - pad_left) / scale
        kps[:, 1::2] = (kps[:, 1::2] - pad_top) / scale

        # NMS
        keep = self._nms(bboxes, scores, self._nms_thresh)

        # Build results
        detections = []
        for idx in keep:
            bbox = (
                float(bboxes[idx, 0]), float(bboxes[idx, 1]),
                float(bboxes[idx, 2]), float(bboxes[idx, 3]),
            )
            conf = float(scores[idx])

            # Extract 5 landmarks if present (non-zero)
            lm = None
            lm_raw = kps[idx]
            if np.any(lm_raw):
                lm = [
                    (float(lm_raw[0]), float(lm_raw[1])),
                    (float(lm_raw[2]), float(lm_raw[3])),
                    (float(lm_raw[4]), float(lm_raw[5])),
                    (float(lm_raw[6]), float(lm_raw[7])),
                    (float(lm_raw[8]), float(lm_raw[9])),
                ]

            detections.append(FaceDetection(bbox=bbox, confidence=conf, landmarks=lm))

        # Sort by confidence descending
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    @staticmethod
    def _nms(bboxes: np.ndarray, scores: np.ndarray, nms_thresh: float = 0.4) -> List[int]:
        """Greedy NMS. Returns indices to keep in descending score order."""
        order = np.argsort(scores)[::-1]
        keep = []

        while len(order) > 0:
            idx = order[0]
            keep.append(int(idx))

            if len(order) == 1:
                break

            best_box = bboxes[idx]
            rest_boxes = bboxes[order[1:]]

            xx1 = np.maximum(best_box[0], rest_boxes[:, 0])
            yy1 = np.maximum(best_box[1], rest_boxes[:, 1])
            xx2 = np.minimum(best_box[2], rest_boxes[:, 2])
            yy2 = np.minimum(best_box[3], rest_boxes[:, 3])

            iw = np.maximum(0.0, xx2 - xx1)
            ih = np.maximum(0.0, yy2 - yy1)
            inter = iw * ih

            area_best = (best_box[2] - best_box[0]) * (best_box[3] - best_box[1])
            area_rest = (
                (rest_boxes[:, 2] - rest_boxes[:, 0])
                * (rest_boxes[:, 3] - rest_boxes[:, 1])
            )
            union = area_best + area_rest - inter
            iou = inter / (union + 1e-8)

            order = order[1:][iou < nms_thresh]

        return keep
