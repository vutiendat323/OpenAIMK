"""Local PyTorch renderer optimization; preserves Ditto weights and resolution."""

import time

import numpy as np
import torch


def _contiguous_volume(_module, _inputs, output):
    # Upstream flattens channel/depth with view(); NDHWC requires a real repack.
    return output.contiguous()


def _decoded_frame(frame):
    return frame


class FusedTorchRenderer:
    """Keep warper/decoder features on GPU and return the final 512px RGB face."""

    def __init__(self, warper, decoder):
        self.warper = warper.eval()
        self.decoder = decoder.eval()
        torch.backends.cudnn.benchmark = True
        torch.nn.utils.convert_conv3d_weight_memory_format(self.warper, torch.channels_last_3d)
        torch.nn.utils.convert_conv2d_weight_memory_format(self.warper, torch.channels_last)
        # At inference spectral normalization has fixed buffers. Materialize the
        # identical normalized weights once rather than recomputing every frame.
        for module in self.decoder.modules():
            if hasattr(module, "weight_orig"):
                torch.nn.utils.remove_spectral_norm(module)
        self.decoder.to(memory_format=torch.channels_last)
        self._layout_hook = self.warper.dense_motion_network.hourglass.register_forward_hook(
            _contiguous_volume
        )
        # Preserve the measured NDHWC convolution layout in the 3D graph.
        # Compiling both models together with default layout selection was slower.
        self.warper = torch.compile(
            self.warper,
            fullgraph=True,
            options={"triton.cudagraphs": True, "layout_optimization": False},
        )
        self.decoder = torch.compile(self.decoder, mode="reduce-overhead", fullgraph=True)
        self.frame_ms = []

    @torch.no_grad()
    def __call__(self, feature, source, driving):
        started = time.perf_counter()
        feature = torch.from_numpy(feature).to(device="cuda", memory_format=torch.channels_last_3d)
        source = torch.from_numpy(source).to("cuda")
        driving = torch.from_numpy(driving).to("cuda")
        with torch.autocast("cuda", dtype=torch.float16):
            # Match upstream's FP32 feature boundary, without a CPU round trip.
            warped = self.warper(feature, source, driving).float()
            pixels = self.decoder(warped).float().cpu().numpy()
        if not np.isfinite(pixels).all():
            raise RuntimeError("nonfinite_ditto_frame")
        result = pixels[0].transpose(1, 2, 0).clip(0, 1) * 255
        self.frame_ms.append((time.perf_counter() - started) * 1000)
        return result

    def statistics(self):
        # Exclude initial algorithm selection from steady rendering time.
        steady = self.frame_ms[10:]
        return {
            "frames": len(self.frame_ms),
            "warmup_frames_excluded": min(10, len(self.frame_ms)),
            "steady_mean_ms": float(np.mean(steady)) if steady else None,
            "steady_p95_ms": float(np.percentile(steady, 95)) if steady else None,
            "steady_render_fps": 1000 / float(np.mean(steady)) if steady else None,
        }


def install_fused_renderer(sdk):
    warper = sdk.warp_f3d.warp_net
    decoder = sdk.decode_f3d.decoder
    if warper.model_type != "pytorch" or decoder.model_type != "pytorch":
        raise ValueError("Ditto fused renderer requires PyTorch models")
    renderer = FusedTorchRenderer(warper.model, decoder.model)
    sdk.warp_f3d = renderer
    # The warp worker now outputs the final RGB face, so this stage forwards it.
    sdk.decode_f3d = _decoded_frame
    return renderer
