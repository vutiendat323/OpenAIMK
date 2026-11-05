"""Prepare a partial decoder for the pixels used by the source-mouth compositor.

Requires the validated full TensorRT cache. Run with the kiosk stopped. This
cache is bound to both source clips and never supplies a complete generated face.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def visible_errors(actual, reference, regions):
    import numpy as np

    y, x = np.ogrid[:512, :512]
    delta = np.abs(actual - reference)
    metrics = []
    for cx, cy, rx, ry in regions:
        distance = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
        edge = np.clip((distance - 0.65) / 0.35, 0, 1)
        alpha = 1 - edge * edge * (3 - 2 * edge)
        # The composited difference is alpha * (actual-reference). Exclude
        # unused pixels, and compare floats before the final uint8 rounding.
        error = (delta * alpha[..., None])[alpha > 0]
        metrics.append((float(error.mean()), float(np.percentile(error, 99.9)), float(error.max())))
    return {
        "worst_mae_rgb255": max(a for a, _, _ in metrics),
        "worst_p999_rgb255": max(b for _, b, _ in metrics),
        "worst_max_rgb255": max(c for _, _, c in metrics),
        "finite": bool(np.isfinite(actual).all()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=ROOT / "Female_staff_member_standing_3128c196.mp4"
    )
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument(
        "--captures", type=Path, default=ROOT / "output/avatar-quality-review/ditto-torch-benchmark"
    )
    args = parser.parse_args()
    sys.path[:0] = [str(ROOT), str(ROOT / ".runtime/Ditto")]
    from scripts.prepare_ditto_acceleration import build_engine, require_stopped_kiosk

    require_stopped_kiosk()
    import numpy as np
    import tensorrt as trt
    import torch
    from core.models.decoder import Decoder
    from core.models.warp_network import WarpNetwork

    from scripts.ditto_realtime import DittoEngine
    from scripts.ditto_roi import MouthDecoder
    from scripts.ditto_torch import FusedTorchRenderer
    from scripts.ditto_trt import (
        MOUTH_ROI,
        StaticTensorRTRunner,
        cache_fingerprint,
        roi_covers_regions,
        sha256_file,
    )

    torch.set_grad_enabled(False)
    torch.set_num_threads(4)
    runtime = ROOT / ".runtime"
    models = runtime / "Ditto/checkpoints/ditto_pytorch/models"
    onnx, engine_path = runtime / "ditto-decoder-roi.onnx", runtime / "ditto-decoder-roi.engine"
    if args.rebuild or not engine_path.exists():
        original = Decoder(str(models / "decoder.pth"), device="cpu").model.eval()
        for layer in original.modules():
            if hasattr(layer, "weight_orig"):
                torch.nn.utils.remove_spectral_norm(layer)
        torch.onnx.export(
            MouthDecoder(original, MOUTH_ROI),
            torch.zeros(1, 256, 64, 64),
            str(onnx),
            opset_version=17,
            dynamo=False,
            do_constant_folding=True,
            input_names=["feature"],
            output_names=["rgb"],
        )
        del original
        build_engine(onnx, engine_path, decoder=True)
    instance = DittoEngine(args.source, ROOT, renderer_backend="tensorrt")
    instance._load()
    try:
        infos = [instance._info, *([instance._wave_info] if instance._wave_info else [])]
        regions = [region for info in infos for region in info["mouth_regions"]]
        if not roi_covers_regions(MOUTH_ROI, regions, padding=4):
            raise ValueError("Partial decoder cannot cover every source/gesture frame")
        reference = FusedTorchRenderer(
            WarpNetwork(str(models / "warp_network.pth")).model,
            Decoder(str(models / "decoder.pth")).model,
        )
        instance._renderer.decoder = StaticTensorRTRunner(
            engine_path,
            input_specs={"feature": ((1, 256, 64, 64), torch.float32)},
            output_specs={"rgb": ((1, 3, 512, 512), torch.float32)},
        )
        checks = []
        for capture in (0, 15, 30, 45, 60):
            with np.load(args.captures / f"input-{capture}.npz") as data:
                sample = tuple(data[key].copy() for key in ("feature", "source", "driving"))
            expected, actual = reference(*sample), instance._renderer(*sample)
            check = {"capture": capture, **visible_errors(actual, expected, regions)}
            checks.append(check)
            print(json.dumps(check), flush=True)
        passed = all(
            c["finite"]
            and c["worst_mae_rgb255"] < 0.1
            and c["worst_p999_rgb255"] < 1
            and c["worst_max_rgb255"] < 2
            for c in checks
        )
        sources = [args.source.resolve()]
        if instance._wave_info:
            sources.append(ROOT / "Café_assistant_waving_hand_a1410f2d_1080p.mp4")
        validation = {
            "passed": passed,
            "scope": "source-composited mouth only, alpha>0, before uint8 rounding; no full-face equivalence claim",
            "reference": "current full 512px PyTorch renderer and weights",
            "all_source_wave_regions_covered": True,
            "regions_tested": len(regions),
            "sources_sha256": {path.name: sha256_file(path) for path in sources},
            "checks": checks,
        }
        manifest = {
            "fingerprint": cache_fingerprint(
                {"warp_head": models / "warp_network.pth", "decoder": models / "decoder.pth"},
                tensorrt_version=trt.__version__,
                compute_capability=torch.cuda.get_device_capability(),
                decoder_roi=MOUTH_ROI,
            ),
            "engines_sha256": {
                "warp_head": sha256_file(runtime / "ditto-warp-head.engine"),
                "decoder": sha256_file(engine_path),
            },
            "validation": validation,
        }
        report = ROOT / "output/avatar-quality-review/neural-fps/presented-mouth-validation.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(manifest, indent=2) + "\n")
        if not passed:
            raise SystemExit("Visible-mouth accuracy failed; prepared manifest was not updated")
        target = runtime / "ditto-trt-roi.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.replace(target)
    finally:
        instance._sdk.avatar_registrar.source2info.landmark478.model.detector.close()


if __name__ == "__main__":
    main()
