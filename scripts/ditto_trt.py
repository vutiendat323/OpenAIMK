"""Prepared TensorRT CNNs with Ditto's original Torch sampling boundaries.

No engines are built or accepted implicitly. A matching, explicitly validated
manifest is required. TensorRT is imported only when a GPU runner is selected.
"""

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

CACHE_SCHEMA = 1
MOUTH_ROI = (128, 272, 384, 464)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decoder_roi(roi):
    if roi is None:
        return None
    if len(roi) != 4 or any(not isinstance(value, int) or value % 2 for value in roi):
        raise ValueError("Decoder ROI must contain four even pixel coordinates")
    x0, y0, x1, y1 = roi
    if not 0 <= x0 < x1 <= 512 or not 0 <= y0 < y1 <= 512:
        raise ValueError("Decoder ROI must lie inside the 512px face")
    return tuple(roi)


def roi_covers_regions(roi, regions, *, padding=2.0):
    """Cover all source/wave mouth ellipses, including interpolation support."""
    roi = _decoder_roi(roi)
    if roi is None:
        return True
    x0, y0, x1, y1 = roi
    seen = False
    for region in regions:
        if len(region) != 4 or not np.isfinite(region).all():
            return False
        cx, cy, rx, ry = region
        if rx <= 0 or ry <= 0:
            return False
        if not (
            x0 <= max(0, cx - rx - padding)
            and y0 <= max(0, cy - ry - padding)
            and x1 >= min(512, cx + rx + padding)
            and y1 >= min(512, cy + ry + padding)
        ):
            return False
        seen = True
    return seen


def cache_fingerprint(weight_paths, *, tensorrt_version, compute_capability, decoder_roi=None):
    return {
        "schema": CACHE_SCHEMA,
        "weights_sha256": {name: sha256_file(path) for name, path in sorted(weight_paths.items())},
        "tensorrt_version": tensorrt_version,
        "compute_capability": list(compute_capability),
        "decoder_roi": list(_decoder_roi(decoder_roi)) if decoder_roi is not None else None,
    }


def validate_manifest(
    manifest_path,
    *,
    weight_paths,
    engine_paths,
    tensorrt_version,
    compute_capability,
    decoder_roi=None,
):
    """Reject stale/unvalidated caches; never synthesize validation metadata."""
    try:
        manifest = json.loads(Path(manifest_path).read_text())
    except (OSError, ValueError) as error:
        raise ValueError(
            "Prepared Ditto manifest is missing or invalid; prepare the cache"
        ) from error
    if not isinstance(manifest, dict) or manifest.get("validation", {}).get("passed") is not True:
        raise ValueError("Ditto engines have no passing equivalence validation")
    expected = cache_fingerprint(
        weight_paths,
        tensorrt_version=tensorrt_version,
        compute_capability=compute_capability,
        decoder_roi=decoder_roi,
    )
    if manifest.get("fingerprint") != expected:
        raise ValueError("Ditto cache fingerprint changed; rebuild and validate the engines")
    hashes = {name: sha256_file(path) for name, path in sorted(engine_paths.items())}
    if manifest.get("engines_sha256") != hashes:
        raise ValueError("Ditto engine bytes changed after validation; prepare the cache")
    return manifest


class DenseMotionPrep(nn.Module):
    def __init__(self, original):
        super().__init__()
        from core.models.modules.util import kp2gaussian, make_coordinate_grid

        self.compress, self.norm = original.compress, original.norm
        self.num_kp = original.num_kp
        self._kp2gaussian, self._coordinate_grid = kp2gaussian, make_coordinate_grid

    def forward(self, feature, source, driving):
        feature = F.relu(self.norm(self.compress(feature)))
        batch, _, depth, height, width = feature.shape
        identity = self._coordinate_grid((depth, height, width), ref=source)
        identity = identity.view(1, 1, depth, height, width, 3)
        coordinates = identity - driving.view(batch, self.num_kp, 1, 1, 1, 3)
        moved = coordinates + source.view(batch, self.num_kp, 1, 1, 1, 3)
        sparse = torch.cat([identity.repeat(batch, 1, 1, 1, 1, 1), moved], dim=1)
        repeated = feature.unsqueeze(1).unsqueeze(1).repeat(1, self.num_kp + 1, 1, 1, 1, 1, 1)
        repeated = repeated.view(batch * (self.num_kp + 1), -1, depth, height, width)
        grids = sparse.view(batch * (self.num_kp + 1), depth, height, width, -1)
        deformed = F.grid_sample(repeated, grids, align_corners=False)
        deformed = deformed.view(batch, self.num_kp + 1, -1, depth, height, width)
        gaussian_driving = self._kp2gaussian(driving, (depth, height, width), 0.01)
        gaussian_source = self._kp2gaussian(source, (depth, height, width), 0.01)
        heatmap = gaussian_driving - gaussian_source
        zeros = torch.zeros(
            batch, 1, depth, height, width, dtype=heatmap.dtype, device=heatmap.device
        )
        heatmap = torch.cat([zeros, heatmap], dim=1).unsqueeze(2)
        head_input = torch.cat([heatmap, deformed], dim=2).view(batch, -1, depth, height, width)
        return head_input, sparse


class DenseMotionCNN(nn.Module):
    def __init__(self, original):
        super().__init__()
        self.hourglass, self.mask, self.occlusion = (
            original.hourglass,
            original.mask,
            original.occlusion,
        )

    def forward(self, head_input):
        prediction = self.hourglass(head_input).contiguous()
        batch, _, _, height, width = prediction.shape
        logits = self.mask(prediction)
        occlusion = torch.sigmoid(self.occlusion(prediction.view(batch, -1, height, width)))
        return logits, occlusion


class DenseMotionPost(nn.Module):
    def __init__(self, original, *, half_boundaries=True):
        super().__init__()
        self.third, self.fourth = original.third, original.fourth
        self.use_occlusion = original.flag_use_occlusion_map
        self.half_boundaries = half_boundaries

    def forward(self, feature, sparse, logits, occlusion):
        if self.half_boundaries:
            logits, occlusion = logits.half(), occlusion.half()
        mask = F.softmax(logits, dim=1).unsqueeze(2)
        deformation = (sparse.permute(0, 1, 5, 2, 3, 4) * mask).sum(dim=1)
        deformation = deformation.permute(0, 2, 3, 4, 1)
        output = F.grid_sample(feature, deformation, align_corners=False)
        batch, channels, depth, height, width = output.shape
        output = self.fourth(self.third(output.view(batch, channels * depth, height, width)))
        if self.use_occlusion:
            output = output * occlusion
        return output


class StaticTensorRTRunner:
    """Single-worker static named I/O; returned buffers are reused next call."""

    def __init__(self, engine_path, *, input_specs, output_specs, device="cuda"):
        import tensorrt as trt

        self.device = torch.device(device)
        if self.device.type != "cuda":
            raise ValueError("TensorRT requires a CUDA device")
        if self.device.index is None:
            self.device = torch.device("cuda", torch.cuda.current_device())
        self.input_specs, self.output_specs = input_specs, output_specs
        self.logger = trt.Logger(trt.Logger.WARNING)
        with torch.cuda.device(self.device):
            self.runtime = trt.Runtime(self.logger)
            self.engine = self.runtime.deserialize_cuda_engine(Path(engine_path).read_bytes())
            if self.engine is None:
                raise RuntimeError("TensorRT engine deserialization failed")
            self.context = self.engine.create_execution_context()
            if self.context is None:
                raise RuntimeError("TensorRT execution context creation failed")
            names = {
                self.engine.get_tensor_name(index) for index in range(self.engine.num_io_tensors)
            }
            if names != set(input_specs) | set(output_specs) or set(input_specs) & set(
                output_specs
            ):
                raise ValueError(f"Unexpected TensorRT I/O names: {sorted(names)}")
            self.buffers = {}
            for name in names:
                shape, dtype = (input_specs | output_specs)[name]
                actual_shape = tuple(self.engine.get_tensor_shape(name))
                actual_dtype = torch.from_numpy(
                    np.empty((), dtype=trt.nptype(self.engine.get_tensor_dtype(name)))
                ).dtype
                mode = trt.TensorIOMode.INPUT if name in input_specs else trt.TensorIOMode.OUTPUT
                if (
                    any(dimension <= 0 for dimension in actual_shape)
                    or actual_shape != tuple(shape)
                    or actual_dtype != dtype
                    or self.engine.get_tensor_mode(name) != mode
                    or self.engine.get_tensor_format(name) != trt.TensorFormat.LINEAR
                ):
                    raise ValueError(f"Unexpected TensorRT shape/dtype/mode/format for {name}")
                self.buffers[name] = torch.empty(shape, dtype=dtype, device=self.device)
                if not self.context.set_tensor_address(name, self.buffers[name].data_ptr()):
                    raise RuntimeError(f"TensorRT failed to bind {name}")

    def __call__(self, **inputs):
        if set(inputs) != set(self.input_specs):
            raise ValueError("TensorRT input names do not match the prepared engine")
        for name, value in inputs.items():
            shape, dtype = self.input_specs[name]
            if (
                tuple(value.shape) != tuple(shape)
                or value.dtype != dtype
                or value.device != self.device
            ):
                raise ValueError(f"TensorRT input shape/dtype/device mismatch for {name}")
            self.buffers[name].copy_(value)
        if not self.context.execute_async_v3(torch.cuda.current_stream(self.device).cuda_stream):
            raise RuntimeError("TensorRT execute_async_v3 failed")
        return {name: self.buffers[name] for name in self.output_specs}


class HybridTensorRTRenderer:
    """Original Torch grid sampling, prepared TRT head/decoder, 512px RGB."""

    def __init__(
        self,
        warper,
        *,
        head_engine_path,
        decoder_engine_path,
        manifest_path,
        weight_paths,
        decoder_roi=None,
        device="cuda",
    ):
        import tensorrt as trt

        self.device = torch.device(device)
        self.decoder_roi = _decoder_roi(decoder_roi)
        self.manifest = validate_manifest(
            manifest_path,
            weight_paths=weight_paths,
            engine_paths={"warp_head": head_engine_path, "decoder": decoder_engine_path},
            tensorrt_version=trt.__version__,
            compute_capability=torch.cuda.get_device_capability(self.device),
            decoder_roi=decoder_roi,
        )
        warper.eval()
        prep = DenseMotionPrep(warper.dense_motion_network).eval().to(self.device)
        post = DenseMotionPost(warper, half_boundaries=True).eval().to(self.device)
        # Retain only the Torch boundary modules; the original CNN can be freed.
        torch.nn.utils.convert_conv3d_weight_memory_format(prep, torch.channels_last_3d)
        torch.nn.utils.convert_conv2d_weight_memory_format(post, torch.channels_last)
        torch.backends.cudnn.benchmark = True
        options = {"triton.cudagraphs": True, "layout_optimization": False}
        self.prep = torch.compile(prep, fullgraph=True, options=options)
        self.post = torch.compile(post, fullgraph=True, options=options)
        self.head = StaticTensorRTRunner(
            head_engine_path,
            input_specs={"head_input": ((1, 110, 16, 64, 64), torch.float32)},
            output_specs={
                "mask_logits": ((1, 22, 16, 64, 64), torch.float32),
                "occlusion": ((1, 1, 64, 64), torch.float32),
            },
            device=self.device,
        )
        self.decoder = StaticTensorRTRunner(
            decoder_engine_path,
            input_specs={"feature": ((1, 256, 64, 64), torch.float32)},
            output_specs={"rgb": ((1, 3, 512, 512), torch.float32)},
            device=self.device,
        )
        self.frame_ms = []

    @torch.no_grad()
    def render_tensors(self, feature, source, driving):
        """Return normalized FP32 GPU RGB; consume before the next invocation."""
        with torch.autocast("cuda", dtype=torch.float16):
            head_input, sparse = self.prep(feature, source, driving)
            # Own storage OUTSIDE compile across the external TensorRT call.
            sparse = sparse.clone()
            output = self.head(head_input=head_input)
            warped = self.post(feature, sparse, output["mask_logits"], output["occlusion"]).float()
        return self.decoder(feature=warped)["rgb"]

    @torch.no_grad()
    def __call__(self, feature, source, driving):
        started = time.perf_counter()
        feature = torch.from_numpy(feature).to(self.device, memory_format=torch.channels_last_3d)
        source, driving = [torch.from_numpy(value).to(self.device) for value in (source, driving)]
        pixels = self.render_tensors(feature, source, driving).float().cpu().numpy()
        if not np.isfinite(pixels).all():
            raise RuntimeError("nonfinite_ditto_frame")
        result = pixels[0].transpose(1, 2, 0).clip(0, 1) * 255
        self.frame_ms.append((time.perf_counter() - started) * 1000)
        return result

    def statistics(self):
        steady = self.frame_ms[10:]
        return {
            "frames": len(self.frame_ms),
            "warmup_frames_excluded": min(10, len(self.frame_ms)),
            "steady_mean_ms": float(np.mean(steady)) if steady else None,
            "steady_p95_ms": float(np.percentile(steady, 95)) if steady else None,
            "steady_render_fps": 1000 / float(np.mean(steady)) if steady else None,
        }


def validate_mouth_sources(manifest, infos, source_paths):
    """A partial decoder can only supply the pixels covered by its validation."""
    validation = manifest.get("validation", {})
    if not validation.get("all_source_wave_regions_covered"):
        raise ValueError("Mouth decoder has no source coverage validation")
    if validation.get("sources_sha256") != {
        name: sha256_file(path) for name, path in source_paths.items()
    }:
        raise ValueError("Mouth decoder sources changed; prepare and validate again")
    regions = [region for info in infos for region in info["mouth_regions"]]
    # Include the transition patch, interpolation halo and rounding of its bounds.
    if not roi_covers_regions(MOUTH_ROI, regions, padding=4):
        raise ValueError("Mouth decoder does not cover every source/gesture frame")


def install_mouth_decoder(renderer, root, infos, source_paths):
    import tensorrt as trt

    root = Path(root)
    models = root / ".runtime/Ditto/checkpoints/ditto_pytorch/models"
    engines = {
        "warp_head": root / ".runtime/ditto-warp-head.engine",
        "decoder": root / ".runtime/ditto-decoder-roi.engine",
    }
    manifest = validate_manifest(
        root / ".runtime/ditto-trt-roi.json",
        weight_paths={"warp_head": models / "warp_network.pth", "decoder": models / "decoder.pth"},
        engine_paths=engines,
        tensorrt_version=trt.__version__,
        compute_capability=torch.cuda.get_device_capability(renderer.device),
        decoder_roi=MOUTH_ROI,
    )
    validate_mouth_sources(manifest, infos, source_paths)
    renderer.decoder = StaticTensorRTRunner(
        engines["decoder"],
        input_specs={"feature": ((1, 256, 64, 64), torch.float32)},
        output_specs={"rgb": ((1, 3, 512, 512), torch.float32)},
        device=renderer.device,
    )
    renderer.decoder_roi, renderer.manifest = MOUTH_ROI, manifest
