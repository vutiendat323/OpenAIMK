"""Local MuseTalk 1.5 rendering with the shared PCM/motion session boundary."""

from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from avatars.musetalk.models.unet import PositionalEncoding, UNet
from avatars.musetalk.models.vae import VAE
from avatars.musetalk.whisper.audio2feature import Audio2Feature
from avatars.musetalk_avatar import MuseReal, load_avatar
from livetalking_motion import RealtimeMotion

ROOT = Path(__file__).resolve().parent.parent


def bgr_pixels(image):
    image = (image / 2 + 0.5).clamp(0, 1).permute(0, 2, 3, 1).float().cpu().numpy()
    return np.rint(image * 255).astype(np.uint8)[..., ::-1]


class TorchDecoder:
    def __init__(self):
        vae = VAE(model_path="models/sd-vae")
        self.model = vae.vae.eval().half().to(memory_format=torch.channels_last)
        self.scaling_factor = vae.scaling_factor
        self.decode = torch.compile(self.model.decode, mode="max-autotune", fullgraph=True)

    def decode_latents(self, latents):
        return bgr_pixels(self.decode(latents / self.scaling_factor, return_dict=False)[0])


class TensorRTDecoder:
    def __init__(self, path):
        import tensorrt as trt

        self.logger = trt.Logger(trt.Logger.WARNING)
        self.runtime = trt.Runtime(self.logger)
        self.engine = self.runtime.deserialize_cuda_engine(Path(path).read_bytes())
        if self.engine is None:
            raise RuntimeError("musetalk_decoder_engine_unavailable")
        self.context = self.engine.create_execution_context()
        self.shape = tuple(self.engine.get_tensor_shape("latents"))
        self.output = torch.empty(
            tuple(self.engine.get_tensor_shape("image")), device="cuda", dtype=torch.float16
        )

    def decode_latents(self, latents):
        # The engine is the original SD VAE decoder, with its original latent
        # scale and 256px output. No spatial resizing or extra restoration model.
        inputs = (latents / 0.18215).contiguous()
        if tuple(inputs.shape) != self.shape:
            raise ValueError("musetalk_decoder_batch_mismatch")
        self.context.set_tensor_address("latents", inputs.data_ptr())
        self.context.set_tensor_address("image", self.output.data_ptr())
        if not self.context.execute_async_v3(torch.cuda.current_stream().cuda_stream):
            raise RuntimeError("musetalk_decoder_failed")
        return bgr_pixels(self.output)


def load_model(manifest):
    accelerated = manifest.get("decoder") == "tensorrt"
    decoder = (
        TensorRTDecoder(ROOT / ".runtime/tensorrt/musetalk-vae-b4.plan")
        if accelerated
        else TorchDecoder()
    )
    unet = UNet(
        unet_config="models/musetalkV15/musetalk.json",
        model_path="models/musetalkV15/unet.pth",
        device="cpu",
    )
    unet.device = torch.device("cuda")
    unet.model = unet.model.eval().half().cuda().to(memory_format=torch.channels_last)
    unet.model = torch.compile(
        unet.model, mode="reduce-overhead" if accelerated else "max-autotune", fullgraph=True
    )
    pe = PositionalEncoding(d_model=384).half().cuda()
    timesteps = torch.tensor([0], device="cuda")
    audio_processor = Audio2Feature(model_path="models/whisper")
    return decoder, unet, pe, timesteps, audio_processor


@torch.no_grad()
def warm_up(batch_size, model):
    decoder, unet, pe, timesteps, _ = model
    latents = torch.zeros((batch_size, 8, 32, 32), device="cuda", dtype=torch.float16)
    latents = latents.contiguous(memory_format=torch.channels_last)
    features = pe(torch.zeros((batch_size, 50, 384), device="cuda", dtype=torch.float16))
    for _ in range(5):
        torch.compiler.cudagraph_mark_step_begin()
        prediction = unet.model(
            latents, timesteps, encoder_hidden_states=features, return_dict=False
        )[0]
        decoder.decode_latents(prediction)


@lru_cache(maxsize=2)
def gesture_avatar(avatar_id):
    return load_avatar(avatar_id)


class MuseTalkMotionAvatar(RealtimeMotion, MuseReal):
    def append_wave(self, avatar_id):
        wave = gesture_avatar(avatar_id)
        names = (
            "frame_list_cycle",
            "mask_list_cycle",
            "coord_list_cycle",
            "mask_coords_list_cycle",
            "input_latent_list_cycle",
        )
        for name, data in zip(names, wave, strict=True):
            setattr(self, name, list(getattr(self, name)) + list(data))
        return len(wave[0])

    @torch.no_grad()
    def _infer_indices(self, indices, features):
        torch.compiler.cudagraph_mark_step_begin()
        latents = torch.cat([self.input_latent_list_cycle[index] for index in indices])
        latents = latents.to(device="cuda", dtype=torch.float16, memory_format=torch.channels_last)
        features = torch.as_tensor(np.asarray(features), device="cuda", dtype=torch.float16)
        prediction = self.unet.model(
            latents, self.timesteps, encoder_hidden_states=self.pe(features), return_dict=False
        )[0]
        return self.vae.decode_latents(prediction)
