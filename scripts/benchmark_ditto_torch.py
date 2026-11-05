"""Compare actual Ditto renderer paths on captured source/audio inputs, locally."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, help="Directory containing input-*.npz")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=50)
    args = parser.parse_args()
    if args.iterations < 10:
        parser.error("--iterations must be at least 10")
    sys.path.insert(0, str(ROOT / ".runtime/Ditto"))
    import numpy as np
    import torch
    from core.models.decoder import Decoder
    from core.models.warp_network import WarpNetwork
    from ditto_torch import FusedTorchRenderer
    from review_ditto_source import wait_for_idle

    wait_for_idle()
    torch.set_num_threads(4)
    models = ROOT / ".runtime/Ditto/checkpoints/ditto_pytorch/models"
    warp = WarpNetwork(str(models / "warp_network.pth"))
    decode = Decoder(str(models / "decoder.pth"))
    inputs = []
    for path in sorted(args.inputs.glob("input-*.npz")):
        with np.load(path) as data:
            inputs.append(tuple(data[k] for k in ("feature", "source", "driving")))
    if not inputs:
        parser.error("No captured input frames found")

    def baseline(feature, source, driving):
        return decode(warp(feature, source, driving))

    def measure(render):
        started = time.perf_counter()
        for i in range(10):
            render(*inputs[i % len(inputs)])
        warmup = time.perf_counter() - started
        elapsed = []
        for i in range(args.iterations):
            started = time.perf_counter()
            # Both paths return completed CPU RGB arrays, including transfers.
            render(*inputs[i % len(inputs)])
            elapsed.append((time.perf_counter() - started) * 1000)
        return {
            "warmup_seconds": warmup,
            "frames": len(elapsed),
            "mean_ms": float(np.mean(elapsed)),
            "p95_ms": float(np.percentile(elapsed, 95)),
            "fps": 1000 / float(np.mean(elapsed)),
        }

    reference = np.asarray([baseline(*sample) for sample in inputs])
    before = measure(baseline)
    optimized = FusedTorchRenderer(warp.model, decode.model)
    after = measure(optimized)
    output = np.asarray([optimized(*sample) for sample in inputs])
    difference = np.abs(output - reference)
    equivalent = bool(
        np.isfinite(output).all()
        and difference.mean() < 0.1
        and np.percentile(difference, 99.9) < 1
        and difference.max() < 2
    )
    report = {
        "gpu": torch.cuda.get_device_name(),
        "torch": torch.__version__,
        "baseline": before,
        "optimized": after,
        "speedup": after["fps"] / before["fps"],
        "mae_rgb_255": float(difference.mean()),
        "p999_rgb_255": float(np.percentile(difference, 99.9)),
        "max_rgb_255": float(difference.max()),
        "pixel_equivalence_passed": equivalent,
        "scope": "renderer plus transfers; excludes audio, preparation, WebRTC and browser",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not equivalent:
        raise SystemExit("Optimized renderer failed pixel-equivalence limits")


if __name__ == "__main__":
    main()
