"""Exact inference reuse of Ditto audio conditioning within one DDIM call.

Install after loading weights and before compiling guided_forward. The upstream
sampler, schedules, random draws, and learned modules remain in use. Prepared
audio tensors are arguments local to the invocation, never a cross-call cache.
"""

import torch
from torch import nn


class PreparedMotionDecoder(nn.Module):
    """Reuse deterministic conditioning and skip the unused null-audio encoder."""

    def __init__(self, original):
        super().__init__()
        self.original = original
        self.train(original.training)

    def prepare_conditioning(self, audio):
        if isinstance(audio, tuple):
            return audio
        model = self.original
        tokens = model.cond_encoder(model.abs_pos_encoding(model.cond_projection(audio)))
        hidden = model.non_attn_cond_projection(tokens.mean(dim=-2))
        return tokens, hidden

    def _input(self, x, cond_frame):
        model = self.original
        if not model.multi_cond_frame:
            cond_frame = cond_frame.unsqueeze(1).repeat(1, x.shape[1], 1)
        return model.abs_pos_encoding(model.input_projection(torch.cat((x, cond_frame), dim=-1)))

    def _time(self, times):
        model = self.original
        hidden = model.time_mlp(times)
        return model.to_time_cond(hidden), model.to_time_tokens(hidden)

    def _decode(self, x, tokens, hidden, time, time_tokens):
        model = self.original
        if hidden is None:
            hidden = model.null_cond_hidden.to(time.dtype)
        # Upstream uses +=. Preserve its dtype and rounding while allowing both
        # guidance branches to consume the same unmodified time projection.
        time = time.clone()
        time += hidden
        memory = model.norm_cond(torch.cat((tokens, time_tokens), dim=-2))
        return model.final_layer(model.seqTransDecoder(x, memory, time))

    def forward(self, x, cond_frame, cond_embed, times, cond_drop_prob=0.0):
        if self.training or cond_drop_prob not in (0, 1):
            return self.original(x, cond_frame, cond_embed, times, cond_drop_prob)
        projected = self._input(x, cond_frame)
        if cond_drop_prob == 0:
            tokens, hidden = self.prepare_conditioning(cond_embed)
        else:
            # Position encoding can promote the autocast dtype. Probe only the
            # inexpensive projection; skip both discarded audio-encoder layers.
            model = self.original
            dtype = model.abs_pos_encoding(model.cond_projection(cond_embed)).dtype
            tokens = model.null_cond_embed.to(dtype).expand(x.shape[0], -1, -1)
            hidden = None
        time, time_tokens = self._time(times)
        return self._decode(projected, tokens, hidden, time, time_tokens)

    def guided_forward(self, x, cond_frame, cond_embed, times, guidance_weight):
        if self.training:
            return self.original.guided_forward(x, cond_frame, cond_embed, times, guidance_weight)
        tokens, hidden = self.prepare_conditioning(cond_embed)
        projected = self._input(x, cond_frame)
        time, time_tokens = self._time(times)
        null_tokens = self.original.null_cond_embed.to(tokens.dtype).expand(x.shape[0], -1, -1)
        unconditioned = self._decode(projected, null_tokens, None, time, time_tokens)
        conditioned = self._decode(projected, tokens, hidden, time, time_tokens)
        return unconditioned + (conditioned - unconditioned) * guidance_weight


def install_motion_optimization(diffusion):
    """Adapt an upstream PyTorch LMDM instance in place and return it.

    For the SDK, pass sdk.audio2motion.lmdm.model. Compile the resulting
    diffusion.model.guided_forward afterward. Load checkpoints before installing
    because the wrapper adds an original. prefix to decoder parameter paths.
    Training and fractional conditioning dropout retain the upstream paths.
    """
    if isinstance(diffusion.model, PreparedMotionDecoder):
        return diffusion
    motion = PreparedMotionDecoder(diffusion.model)
    diffusion.model = motion
    original_sample = diffusion.ddim_sample

    @torch.no_grad()
    def ddim_sample(kp_cond, aud_cond, sampling_timesteps):
        conditioning = aud_cond if motion.training else motion.prepare_conditioning(aud_cond)
        return original_sample(kp_cond, conditioning, sampling_timesteps)

    diffusion.ddim_sample = ddim_sample
    return diffusion
