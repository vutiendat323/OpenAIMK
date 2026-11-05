#!/usr/bin/env python3
"""Run the real models on a still image instead of the camera.

Production wiring (main.build_models + main.start_workers + the WS server),
no camera.  Prints the kiosk event once a second and serves the console on a
spare port, so it runs beside a live kiosk.  --cpu keeps it off a GPU the live
stack is holding.

    python tools/smoke_run.py photo.jpg --cpu --port 9877 --seconds 30

Exits 1 when no face distance was ever measured.
"""

import argparse
import json
import os
import sys
import time

_VISION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(_VISION))

import cv2

from Visual.config import Config
from Visual.main import build_models, start_workers
from Visual.application.state import SharedState
from Visual.presentation.ws_server import VisionWSServer


def camera_like(image, width: int, height: int):
    """Centre-crop *image* to the camera's aspect, then resize to its size."""
    h, w = image.shape[:2]
    crop_w = min(w, round(h * width / height))
    crop_h = min(h, round(w * height / width))
    x, y = (w - crop_w) // 2, (h - crop_h) // 2
    return cv2.resize(image[y:y + crop_h, x:x + crop_w], (width, height))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image")
    ap.add_argument("--port", type=int, default=9877)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--cpu", action="store_true", help="run every model on the CPU")
    args = ap.parse_args()

    image = cv2.imread(args.image)
    if image is None:
        sys.exit(f"cannot read {args.image}")

    cfg = Config.from_yaml(os.path.join(_VISION, "config.yml"))
    if args.cpu:
        for key, value in (("device", "cpu"), ("embedder_device", "cpu"), ("metric3d_half", False)):
            object.__setattr__(cfg, key, value)
    print(f"[smoke] intrinsics fx={cfg.camera_fx:.1f} fy={cfg.camera_fy:.1f} "
          f"cx={cfg.camera_cx:.1f} cy={cfg.camera_cy:.1f}")

    frame = camera_like(image, cfg.camera_width, cfg.camera_height)
    state = SharedState()
    state.put_frame(frame)
    threads = start_workers(state, cfg, build_models(cfg))
    VisionWSServer(state, port=args.port, cfg=cfg).start()
    print(f"[smoke] {len(threads)} workers; console on http://localhost:{args.port}/")

    measured = False
    end = time.monotonic() + args.seconds
    next_print = time.monotonic()
    while time.monotonic() < end:
        state.put_frame(frame)
        if time.monotonic() >= next_print:
            event = state.scene.snapshot().event(time.time())
            measured |= event.get("nearest_m", 0) > 0
            print(json.dumps({**event, "timing_ms": state.timings()}))
            next_print += 1.0
        time.sleep(1 / 30)
    state.running = False
    print("[smoke] OK" if measured else "[smoke] FAIL: no face distance measured")
    return 0 if measured else 1


if __name__ == "__main__":
    sys.exit(main())
