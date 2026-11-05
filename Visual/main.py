#!/usr/bin/env python3
"""
Real-Time Face Detection & Distance Estimation with Spoof Detection.

Architecture (3 background threads + camera loop):
  Thread 1 (Fast Track):  SCRFD → ByteTrack                    ~5-8ms, capped 15 fps
  Thread 2 (Spoof):        MiniFASNet ensemble, every N s       ~60ms/face
  Thread 3 (Depth):       Metric3D on dedicated CUDA stream    ~50ms, every N s

Headless by design: the operator GUI is the web console the WS server serves
(http://localhost:9876/).  Nothing opens a window on the kiosk machine.
"""

import logging
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import time
import threading
from typing import Dict, List, Tuple

import numpy as np
import torch

_log = logging.getLogger(__name__)

from Visual.config import Config
from Visual.infrastructure.faces.scrfd import SCRFDFaceDetector
from Visual.infrastructure.camera import init_undistort_maps, open_camera, undistort_frame
from Visual.application.state import SharedState
from Visual.application.camera_router import CameraRouter
from Visual.application.track_faces import _track_loop
from Visual.application.check_liveness import _spoof_loop
from Visual.application.measure_presence import _presence_loop
from Visual.application.active_speaker import _asd_loop


# ======================================================================
# Models — built here and handed to the loops, so tests can hand in fakes
# ======================================================================

def _optional(name: str, path: str, build):
    """Build an optional model; a missing file or a failure degrades, never crashes."""
    if not os.path.isfile(path):
        _log.warning("[main] %s model not found at %s, running without it", name, path)
        return None
    try:
        model = build()
        print(f"[main] {name} ready — {path}")
        return model
    except Exception as e:
        _log.warning("[main] %s init failed (%s), running without it", name, e)
        return None


def _build_active_speaker(cfg: Config):
    """The configured active-speaker model, or None (disabled or failed to load)."""
    if cfg.asd_provider == "none":
        return None
    path = os.path.expanduser(cfg.asd_model_path)

    def _light_asd():
        from Visual.infrastructure.active_speaker.light_asd import LightASD
        return LightASD(path, device=cfg.device)

    return _optional("active speaker", path, _light_asd)


def _build_depth(cfg: Config):
    """Metric3D, or None: a load failure turns presence off, never Vision.

    It needs ../Metric3D, its downloaded weights and VRAM; any of those missing
    used to raise out of build_models and stop face tracking and ASD too.
    """
    h, w = cfg.metric3d_input_size
    precision = "fp16" if cfg.metric3d_half and "cuda" in cfg.device else "fp32"
    try:
        from Visual.infrastructure.depth.metric3d import DepthEstimator
        model = DepthEstimator(
            cfg.metric3d_variant, cfg.device, use_half=cfg.metric3d_half,
            input_size=cfg.metric3d_input_size,
        )
    except Exception as e:
        _log.warning("[main] depth estimator init failed (%s), running without presence", e)
        return None
    print(f"[main] depth estimator ready — {cfg.metric3d_variant} {h}x{w} {precision}")
    return model


def build_models(cfg: Config) -> dict:
    """Every model the worker loops run, built once from *cfg*."""
    from Visual.infrastructure.faces.bytetrack import ByteTrack

    face_detector = SCRFDFaceDetector(
        model_path=cfg.scrfd_model,
        conf_thresh=cfg.scrfd_conf,
        nms_thresh=cfg.scrfd_nms,
        input_size=cfg.scrfd_input_size,
        device=cfg.device,
    )
    face_detector.warmup()

    def _embedder():
        from Visual.infrastructure.faces.embedder import FaceEmbedder
        e = FaceEmbedder(model_path=cfg.embedder_model_path, device=cfg.embedder_device)
        e.warmup()
        return e

    def _lip_reader():
        from Visual.infrastructure.faces.lips import LipReader
        return LipReader(cfg.lip_model_path)

    models = {
        "face_detector": face_detector,
        "tracker": ByteTrack(
            cfg.track_buffer, cfg.track_thresh, cfg.match_thresh,
            cfg.match_thresh_second, cfg.track_init_thresh,
            reid_weight=cfg.reid_weight, gallery_size=cfg.gallery_size,
        ),
        "embedder": _optional("embedder", cfg.embedder_model_path, _embedder),
        "lip_reader": _optional("lip reader", cfg.lip_model_path, _lip_reader),
        "spoof_detector": None,
        "depth_estimator": None,
        "person_detector": None,
        "active_speaker": _build_active_speaker(cfg),
    }
    if cfg.spoof_enabled:
        from Visual.infrastructure.spoof.minifasnet import SpoofDetector
        spoof = SpoofDetector(pad_live_threshold=cfg.spoof_live_threshold, device=cfg.device)
        spoof.prepare()
        models["spoof_detector"] = spoof
    if cfg.async_depth:
        from Visual.infrastructure.person.yolo import PersonDetector
        models["depth_estimator"] = _build_depth(cfg)
        models["person_detector"] = _optional(
            "person detector", cfg.person_model,
            lambda: PersonDetector(cfg.person_model, cfg.person_conf, cfg.device))
    return models


def start_workers(state: SharedState, cfg: Config, models: dict) -> list:
    """Start one daemon thread per worker loop the models allow."""
    plan = [("track", _track_loop,
             (models["face_detector"], models["tracker"], models["embedder"],
              models.get("lip_reader")))]
    if models["spoof_detector"] is not None:
        plan.append(("spoof", _spoof_loop, (models["spoof_detector"],)))
    if models["depth_estimator"] is not None:
        plan.append(("presence", _presence_loop,
                     (models["depth_estimator"], models["person_detector"])))
    if models.get("active_speaker") is not None:
        state.asd_status = "ready"
        plan.append(("asd", _asd_loop, (models["active_speaker"],)))
    elif cfg.asd_provider != "none":
        state.asd_status = "unavailable"
    threads = []
    for name, loop, args in plan:
        t = threading.Thread(target=loop, args=(state, cfg, *args), daemon=True, name=name)
        t.start()
        threads.append(t)
    return threads


# ======================================================================
# Main: camera loop
# ======================================================================

def main():
    # --- configure logging ---
    # Use INFO for normal operation; switch to DEBUG for diagnostics
    _LOG_LEVEL = os.environ.get("JARVIS_LOG_LEVEL", "WARNING")
    logging.basicConfig(
        level=getattr(logging, _LOG_LEVEL, logging.WARNING),
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Always show warnings from our modules
    logging.getLogger("Visual").setLevel(logging.WARNING)
    logging.getLogger("__main__").setLevel(logging.WARNING)
    # Quiet down noisy non-AI loggers
    for noisy in ("PIL", "matplotlib", "urllib3", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    cfg = Config.from_yaml()
    print(f"Device: {cfg.device}")
    print(f"SCRFD: ONNX 2.5G {cfg.scrfd_input_size[0]}x{cfg.scrfd_input_size[1]} | "
          f"Depth every {cfg.depth_interval_sec:g}s")
    print(f"Spoof: {'ON' if cfg.spoof_enabled else 'OFF'} "
          f"(MiniFASNetV2 PAD, every {cfg.spoof_interval_sec}s)")
    print(f"[main] Calibration: use_calibration={cfg.use_calibration}")
    print(f"[main] Intrinsics: fx={cfg.camera_fx:.2f} fy={cfg.camera_fy:.2f} "
          f"cx={cfg.camera_cx:.2f} cy={cfg.camera_cy:.2f}")
    print(f"[main] canonical_to_real_scale = {cfg.canonical_to_real_scale:.6f} "
          f"(= fx / {cfg.metric3d_canonical_focal})")
    print(f"[main] Distortion: {cfg.distortion}")
    print()

    state = SharedState(cfg.mouth_scale)
    capture_dir = os.environ.get("VISION_ASD_CAPTURE_DIR")
    if capture_dir:
        # Operator opt-in: record what ASD sees for tools/asd_capture.py.
        from Visual.tools.asd_capture import RecordingAVBuffer
        state.asd = RecordingAVBuffer(capture_dir)
        print(f"[main] ASD capture on -> {capture_dir}")
    start_workers(state, cfg, build_models(cfg))
    # A page may select its remote camera before voice starts. Keep Vision
    # available even when the local C920 is missing or disconnected.
    router = CameraRouter(state, width=cfg.camera_width, height=cfg.camera_height,
                          remote_hfov_deg=cfg.remote_camera_hfov_deg,
                          stale_after_secs=cfg.remote_camera_stale_secs,
                          steady_frames=cfg.remote_camera_steady_frames)

    # --- Launch WebSocket server (always-on, primary output in headless mode) ---
    from Visual.presentation.ws_server import VisionWSServer
    from Visual.config import _resolve_yaml_path

    ws_server = VisionWSServer(state, port=cfg.ws_port, cfg=cfg,
                               config_path=_resolve_yaml_path(), router=router)
    ws_server.start()
    print(f"[ws] vision events on ws://0.0.0.0:{cfg.ws_port}")
    print(f"[ws] console on http://localhost:{cfg.ws_port}/")

    # --- Set up undistortion maps if calibration is available ---
    if cfg.use_undistort and cfg.distortion != (0.0, 0.0, 0.0, 0.0, 0.0):
        mtx_np = np.array([
            [cfg.camera_fx, 0, cfg.camera_cx],
            [0, cfg.camera_fy, cfg.camera_cy],
            [0, 0, 1],
        ], dtype=np.float32)
        dist_np = np.array(cfg.distortion, dtype=np.float32)
        map_x, map_y = init_undistort_maps(
            mtx_np, dist_np, (cfg.camera_width, cfg.camera_height),
        )
        print(f"[main] Undistortion enabled (remap maps cached)\n")
    else:
        map_x, map_y = None, None
        print(f"[main] Undistortion disabled\n")

    frame_count = 0
    start_time = time.perf_counter()
    cap = None
    next_camera_attempt = 0.0

    print("Running … (Ctrl+C to quit)\n")

    try:
        while state.running:
            if cap is None and time.monotonic() >= next_camera_attempt:
                try:
                    cap = open_camera(cfg.camera_id, cfg.camera_width, cfg.camera_height)
                except RuntimeError as exc:
                    _log.warning("[camera] local camera unavailable; remote input remains ready: %s", exc)
                    next_camera_attempt = time.monotonic() + 2.0
            if cap is None:
                # Remote frames arrive on the WS thread; avoid busy-waiting
                # while periodically checking for a reconnected local camera.
                time.sleep(0.05)
                continue
            ret, frame_bgr = cap.read()
            if not ret:
                _log.warning("[camera] local camera stopped; waiting for local or remote input")
                cap.release()
                cap = None
                next_camera_attempt = time.monotonic() + 2.0
                time.sleep(0.05)
                continue
            capture_ts = time.time()
            frame_count += 1

            # Undistort before any processing
            if map_x is not None:
                frame_bgr = undistort_frame(frame_bgr, map_x, map_y)

            # Workers read it; distances are smoothed inside Scene.  The router
            # publishes it unless a selected remote camera is live.
            router.local_frame(frame_bgr, capture_ts)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        state.running = False
        elapsed = time.perf_counter() - start_time
        print(f"Frames: {frame_count} | {elapsed:.1f}s | "
              f"Avg FPS: {frame_count / elapsed:.1f}")
        if cap is not None:
            cap.release()


if __name__ == "__main__":
    main()
