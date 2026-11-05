"""Track faces: SCRFD -> ByteTrack -> PnP distance, reported to the Scene.

Handed the models it runs -- it never builds them -- so the loop runs in a
test with stand-ins.  main.py builds the real models and starts the thread.
"""

import time

import numpy as np

from Visual.application.active_speaker import prepare_face_crop
from Visual.application.ports import Embedder, FaceDetector, LipReader, Tracker
from Visual.application.state import SharedState
from Visual.config import Config
from Visual.domain.geometry import face_distance, iou


def _track_loop(state: SharedState, cfg: Config, face_detector: FaceDetector,
                tracker: Tracker, embedder: Embedder | None = None,
                lip_reader: LipReader | None = None) -> None:
    """Detect, track and measure faces, and report each update to the Scene.

    *face_detector* has ``detect(frame) -> [FaceDetection]``; *tracker* has
    ``update(dets, embeddings=...)`` and ``active_tracks``; *embedder*, when
    given, has ``extract(frame, boxes)`` for appearance ReID.
    """
    min_period = 1.0 / cfg.track_max_fps if cfg.track_max_fps > 0 else 0.0
    configured = (cfg.camera_fx, cfg.camera_fy, cfg.camera_cx, cfg.camera_cy)
    matrix_for = None
    source = None

    last_asd_seq = None

    while state.running:
        snapshot = state.get_frame_snapshot()
        if snapshot is None:
            time.sleep(0.002)
            continue
        frame, frame_seq, frame_ts = snapshot
        # Tracks, distances and mouths belong to one camera: start clean when
        # the router switches between the C920 and a remote camera.
        frame_source = state.frame_source()
        if frame_source != source:
            if source is not None:
                tracker.clear()
                state.scene.reset()
                last_asd_seq = None
            source = frame_source
        # A remote camera publishes its own intrinsics; the C920 publishes none.
        intrinsics = state.frame_intrinsics() or configured
        if intrinsics != matrix_for:
            fx, fy, cx, cy = intrinsics
            camera_matrix = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]])
            matrix_for = intrinsics

        t0 = time.perf_counter()
        try:
            face_dets = face_detector.detect(frame)
        except Exception as e:
            print(f"[track] SCRFD error: {e}")
            face_dets = []

        dets = [d.to_tracker_tuple() for d in face_dets]

        track_embs = None
        if embedder is not None and dets:
            try:
                track_embs = embedder.extract(frame, [(d[0], d[1], d[2], d[3]) for d in dets])
            except Exception as e:
                print(f"[track] embedder error: {e}")

        tracked = tracker.update(dets, embeddings=track_embs)

        # Distance from face geometry, at tracker rate, only for tracks a
        # detection confirmed this frame: a coasting box has no landmarks.
        face_distances = {}
        face_landmarks = {}
        confirmed = []  # (box area, track id, detection box)
        for t in tracker.active_tracks:
            if t.time_since_update or not face_dets:
                continue
            det = max(face_dets, key=lambda d: iou(d.bbox, t.bbox))
            if iou(det.bbox, t.bbox) < 0.5:
                continue
            if det.landmarks is not None:
                face_landmarks[t.id] = [[float(x), float(y)] for x, y in det.landmarks]
            x1, y1, x2, y2 = det.bbox[:4]
            confirmed.append(((x2 - x1) * (y2 - y1), t.id, det.bbox))
            z = face_distance(det.landmarks, camera_matrix, cfg.face_ipd_m)
            if z is not None:
                face_distances[t.id] = z

        if state.asd.active and frame_seq != last_asd_seq:
            last_asd_seq = frame_seq
            pinned = state.asd.pinned_track
            if pinned is not None:
                # The backend locked this customer: stay on them whether or
                # not they are nearest or visible, and without a PnP distance
                # (a turned head still has a mouth to read).
                chosen_id = pinned
                chosen_box = next((box for _, tid, box in confirmed if tid == pinned), None)
            else:
                # Nearest confirmed track with a PnP distance this pass; None
                # clears the selection (and its crop/result history).
                chosen_id, chosen_z, chosen_box = None, None, None
                for _, tid, box in confirmed:
                    z = face_distances.get(tid)
                    if z is not None and (chosen_z is None or z < chosen_z):
                        chosen_id, chosen_z, chosen_box = tid, z, box
            state.asd.select_track(chosen_id)
            if chosen_box is not None:
                try:
                    crop = prepare_face_crop(frame, chosen_box)
                except Exception as e:
                    print(f"[track] ASD crop error: {e}")
                    crop = None
                if crop is not None:
                    state.asd.push_crop(chosen_id, frame_ts, crop)

        elapsed = time.perf_counter() - t0
        state.scene.observe_faces(tracked, face_distances, face_landmarks,
                                  frame_seq=frame_seq, captured_at=frame_ts)
        if lip_reader is not None and confirmed:
            # The three largest faces: the customer is near, and each read
            # costs ~11 ms on the CPU.
            openings = {}
            for _, tid, box in sorted(confirmed, reverse=True)[:3]:
                try:
                    opening = lip_reader.opening(frame, box)
                except Exception as e:
                    print(f"[track] lip reader error: {e}")
                    opening = None
                if opening is not None:
                    openings[tid] = opening
            state.scene.observe_mouths(openings)
        state.set_timing("track", elapsed * 1000.0)

        # Sleep only for the time the cap has left, so a slow inference
        # never has idle time added on top of it.
        if min_period:
            time.sleep(max(0.0, min_period - elapsed))
