"""Visual worker: server camera first, browser camera as a fallback."""

import logging
import signal
import time
from pathlib import Path


def run_local_camera(state, cfg, router, open_source):
    """Keep capturing locally; browser input remains available during retries."""
    logger = logging.getLogger(__name__)
    capture = None
    next_attempt = 0.0
    try:
        while state.running:
            if capture is None and time.monotonic() >= next_attempt:
                try:
                    capture = open_source(cfg.camera_id, cfg.camera_width, cfg.camera_height)
                except (RuntimeError, OSError) as error:
                    logger.warning("Local camera unavailable; browser fallback ready: %s", error)
                    next_attempt = time.monotonic() + 2.0
            if capture is None:
                time.sleep(0.05)
                continue
            success, frame = capture.read()
            if not success:
                logger.warning("Local camera stopped; retrying with browser fallback available")
                capture.release()
                capture = None
                next_attempt = time.monotonic() + 2.0
                continue
            router.local_frame(frame, time.time())
    finally:
        if capture is not None:
            capture.release()


def main():
    from Visual.application.camera_router import CameraRouter
    from Visual.application.state import SharedState
    from Visual.config import Config
    from Visual.infrastructure.camera import open_camera
    from Visual.main import build_models, start_workers
    from Visual.presentation.ws_server import VisionWSServer

    root = Path(__file__).resolve().parent.parent
    logging.basicConfig(level=logging.WARNING)
    cfg = Config(
        ws_port=9877,
        asd_provider="light_asd",
        asd_model_path=str(root / ".runtime/models/light_asd.onnx"),
        metric3d_input_size=(308, 532),
        use_calibration=False,
        use_undistort=False,
    )
    state = SharedState(cfg.mouth_scale)
    models = build_models(cfg)
    missing = [name for name, model in models.items() if model is None]
    if missing:
        raise RuntimeError("required_visual_models_unavailable: " + ", ".join(missing))
    start_workers(state, cfg, models)
    router = CameraRouter(
        state,
        width=cfg.camera_width,
        height=cfg.camera_height,
        remote_hfov_deg=cfg.remote_camera_hfov_deg,
        stale_after_secs=cfg.remote_camera_stale_secs,
        steady_frames=cfg.remote_camera_steady_frames,
        prefer_local=True,
    )
    server = VisionWSServer(state, host="127.0.0.1", port=9877, cfg=cfg, router=router)
    server.start()

    def stop(*_):
        state.running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(
        "Kiosk Visual ready; server camera primary, browser fallback via 127.0.0.1:9877", flush=True
    )
    run_local_camera(state, cfg, router, open_camera)


if __name__ == "__main__":
    main()
