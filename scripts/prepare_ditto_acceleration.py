"""Prepare and validate local TensorRT caches for the unchanged 512px Ditto weights.

Run with the kiosk stopped. A cache manifest is written only after all captured
mouth comparisons pass; rebuilding never changes the source video or weights.
"""

import argparse
import json
import socket
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require_stopped_kiosk():
    for port in (8010, 8011, 9877):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                pass
        except OSError:
            continue
        raise SystemExit(
            f"Stop the kiosk/test avatar before preparing GPU caches (port {port} active)"
        )
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8080/api/kiosk/status", timeout=1
        ) as response:
            active = json.load(response).get("session_active", False)
    except OSError:
        return
    if active:
        raise SystemExit("Voice session active; stop the kiosk before preparing GPU caches")


def build_engine(onnx_path, engine_path, *, decoder):
    import tensorrt as trt

    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    network = builder.create_network(0)
    parser = trt.OnnxParser(network, logger)
    if decoder:
        parser.set_flag(trt.OnnxParserFlag.NATIVE_INSTANCENORM)
    if not parser.parse_from_file(str(onnx_path)):
        raise RuntimeError(
            "ONNX parse failed: "
            + " | ".join(str(parser.get_error(i)) for i in range(parser.num_errors))
        )
    config = builder.create_builder_config()
    config.set_flag(trt.BuilderFlag.FP16)
    config.set_flag(trt.BuilderFlag.OBEY_PRECISION_CONSTRAINTS)
    config.clear_flag(trt.BuilderFlag.TF32)
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 1 << 30)
    for i in range(network.num_layers):
        layer = network.get_layer(i)
        if layer.type == trt.LayerType.CONVOLUTION:
            layer.precision = trt.float16
            for output in range(layer.num_outputs):
                layer.set_output_type(output, trt.float16)
        elif decoder and layer.type in (trt.LayerType.NORMALIZATION, trt.LayerType.REDUCE):
            layer.precision = trt.float32
            if layer.type == trt.LayerType.NORMALIZATION:
                layer.__class__ = trt.INormalizationLayer
                layer.compute_precision = trt.float32
            for output in range(layer.num_outputs):
                if layer.get_output(output).dtype in (trt.float16, trt.float32):
                    layer.set_output_type(output, trt.float32)
        elif (
            not decoder and layer.type == trt.LayerType.SCALE and "BatchNormalization" in layer.name
        ):
            layer.precision = trt.float32
            layer.set_output_type(0, trt.float16)
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError("TensorRT build failed with precision constraints retained")
    temporary = engine_path.with_suffix(".engine.tmp")
    temporary.write_bytes(bytes(serialized))
    temporary.replace(engine_path)


def export_models(models, runtime):
    import torch
    from core.models.decoder import Decoder
    from core.models.warp_network import WarpNetwork

    from scripts.ditto_trt import DenseMotionCNN

    with torch.no_grad():
        warp = WarpNetwork(str(models / "warp_network.pth"), device="cpu").model.eval()
        torch.onnx.export(
            DenseMotionCNN(warp.dense_motion_network).eval(),
            torch.zeros(1, 110, 16, 64, 64),
            str(runtime / "ditto-warp-head.onnx"),
            opset_version=17,
            dynamo=False,
            input_names=["head_input"],
            output_names=["mask_logits", "occlusion"],
            do_constant_folding=False,
        )
        decoder = Decoder(str(models / "decoder.pth"), device="cpu").model.eval()
        for layer in decoder.modules():
            if hasattr(layer, "weight_orig"):
                torch.nn.utils.remove_spectral_norm(layer)
        torch.onnx.export(
            decoder,
            torch.zeros(1, 256, 64, 64),
            str(runtime / "ditto-decoder-512.onnx"),
            opset_version=17,
            dynamo=False,
            input_names=["feature"],
            output_names=["rgb"],
            do_constant_folding=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild", action="store_true", help="Export current weights and build both engines"
    )
    parser.add_argument(
        "--captures", type=Path, default=ROOT / "output/avatar-quality-review/ditto-torch-benchmark"
    )
    args = parser.parse_args()
    require_stopped_kiosk()
    sys.path[:0] = [str(ROOT), str(ROOT / ".runtime/Ditto")]
    import tensorrt as trt
    import torch

    from scripts.ditto_trt import cache_fingerprint, sha256_file

    torch.set_num_threads(4)
    torch.set_grad_enabled(False)
    runtime = ROOT / ".runtime"
    models = runtime / "Ditto/checkpoints/ditto_pytorch/models"
    weights = {"warp_head": models / "warp_network.pth", "decoder": models / "decoder.pth"}
    engines = {
        "warp_head": runtime / "ditto-warp-head.engine",
        "decoder": runtime / "ditto-decoder-512.engine",
    }
    manifest_path = runtime / "ditto-trt.json"
    if args.rebuild or not all(path.exists() for path in engines.values()):
        export_models(models, runtime)
        build_engine(runtime / "ditto-warp-head.onnx", engines["warp_head"], decoder=False)
        build_engine(runtime / "ditto-decoder-512.onnx", engines["decoder"], decoder=True)
    # Validation compares the candidate to current learned weights, not to its
    # own output. Metadata is never used to waive this numerical check.
    validation = validate_candidate(models, engines, args.captures)
    manifest = {
        "fingerprint": cache_fingerprint(
            weights,
            tensorrt_version=trt.__version__,
            compute_capability=torch.cuda.get_device_capability(),
            decoder_roi=None,
        ),
        "engines_sha256": {name: sha256_file(path) for name, path in engines.items()},
        "validation": validation,
    }
    report = ROOT / "output/avatar-quality-review/neural-fps/production-cache-validation.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(manifest, indent=2) + "\n")
    if not validation["passed"]:
        raise SystemExit("Candidate failed pixel accuracy; cache manifest was not updated")
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(manifest_path)
    print(json.dumps({"manifest": str(manifest_path), "validation": validation}), flush=True)


def validate_candidate(models, engines, captures):
    import numpy as np
    import torch
    from core.models.decoder import Decoder
    from core.models.warp_network import WarpNetwork

    from scripts.ditto_torch import _contiguous_volume
    from scripts.ditto_trt import DenseMotionPost, DenseMotionPrep, StaticTensorRTRunner

    warp = WarpNetwork(str(models / "warp_network.pth")).model.eval()
    decoder = Decoder(str(models / "decoder.pth")).model.eval()
    for layer in decoder.modules():
        if hasattr(layer, "weight_orig"):
            torch.nn.utils.remove_spectral_norm(layer)
    torch.nn.utils.convert_conv3d_weight_memory_format(warp, torch.channels_last_3d)
    torch.nn.utils.convert_conv2d_weight_memory_format(warp, torch.channels_last)
    decoder.to(memory_format=torch.channels_last)
    warp.dense_motion_network.hourglass.register_forward_hook(_contiguous_volume)
    options = {"triton.cudagraphs": True, "layout_optimization": False}
    prep = torch.compile(
        DenseMotionPrep(warp.dense_motion_network).eval(), fullgraph=True, options=options
    )
    post = torch.compile(DenseMotionPost(warp).eval(), fullgraph=True, options=options)
    head = StaticTensorRTRunner(
        engines["warp_head"],
        input_specs={"head_input": ((1, 110, 16, 64, 64), torch.float32)},
        output_specs={
            "mask_logits": ((1, 22, 16, 64, 64), torch.float32),
            "occlusion": ((1, 1, 64, 64), torch.float32),
        },
    )
    decode = StaticTensorRTRunner(
        engines["decoder"],
        input_specs={"feature": ((1, 256, 64, 64), torch.float32)},
        output_specs={"rgb": ((1, 3, 512, 512), torch.float32)},
    )
    reference_warp = torch.compile(warp, fullgraph=True, options=options)
    reference_decode = torch.compile(decoder, fullgraph=True, mode="reduce-overhead")
    checks = []
    stream = torch.cuda.Stream()
    with torch.cuda.stream(stream), torch.no_grad():
        for capture in (0, 15, 30, 45, 60):
            with np.load(captures / f"input-{capture}.npz") as data:
                feature = torch.from_numpy(data["feature"].copy()).to(
                    "cuda", memory_format=torch.channels_last_3d
                )
                source, driving = [
                    torch.from_numpy(data[key].copy()).to("cuda") for key in ("source", "driving")
                ]
            with torch.autocast("cuda", dtype=torch.float16):
                expected = (
                    reference_decode(reference_warp(feature, source, driving).float())
                    .float()
                    .cpu()
                    .numpy()
                    .copy()
                )
                packed, sparse = prep(feature, source, driving)
                sparse = sparse.clone()
                outputs = head(head_input=packed)
                warped = post(feature, sparse, outputs["mask_logits"], outputs["occlusion"]).float()
                actual = decode(feature=warped)["rgb"].cpu().numpy().copy()
            error = np.abs(actual[..., 272:464, 128:384] - expected[..., 272:464, 128:384]) * 255
            check = {
                "capture": capture,
                "mae_rgb255": float(error.mean()),
                "p999_rgb255": float(np.percentile(error, 99.9)),
                "max_rgb255": float(error.max()),
                "finite": bool(np.isfinite(actual).all()),
            }
            checks.append(check)
            print(json.dumps(check), flush=True)
        stream.synchronize()
    return {
        "passed": all(
            c["finite"] and c["mae_rgb255"] < 0.1 and c["p999_rgb255"] < 1 and c["max_rgb255"] < 2
            for c in checks
        ),
        "reference": "current PyTorch weights, full 512px, AMP FP16; mouth ROI [128,272,384,464]",
        "checks": checks,
    }


if __name__ == "__main__":
    main()
