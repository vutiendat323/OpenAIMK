"""Optional two-branch motion guidance batch; no sampling or weight changes."""

from types import MethodType

import torch

from scripts.ditto_motion import PreparedMotionDecoder, install_motion_optimization


class BatchedGuidanceMotionDecoder(PreparedMotionDecoder):
    """Run both deterministic guidance branches through the decoder together."""

    def guided_forward(self, x, cond_frame, cond_embed, times, guidance_weight):
        if self.training:
            return self.original.guided_forward(x, cond_frame, cond_embed, times, guidance_weight)
        tokens, hidden = self.prepare_conditioning(cond_embed)
        projected = self._input(x, cond_frame)
        time, time_tokens = self._time(times)
        batch = x.shape[0]
        null_tokens = self.original.null_cond_embed.to(tokens.dtype).expand(batch, -1, -1)
        null_hidden = self.original.null_cond_hidden.to(time.dtype).expand(batch, -1)
        output = self._decode(
            torch.cat((projected, projected), dim=0),
            torch.cat((null_tokens, tokens), dim=0),
            torch.cat((null_hidden, hidden), dim=0),
            torch.cat((time, time), dim=0),
            torch.cat((time_tokens, time_tokens), dim=0),
        )
        unconditioned, conditioned = output.chunk(2, dim=0)
        return unconditioned + (conditioned - unconditioned) * guidance_weight


def install_batched_guidance(diffusion):
    """Opt in before guided_forward compilation; retain per-call audio reuse.

    Bind onto the existing wrapper so the sampler's captured conditioning
    provider remains the same object, including its training/dropout state.
    """
    diffusion = install_motion_optimization(diffusion)
    motion = diffusion.model
    motion.guided_forward = MethodType(BatchedGuidanceMotionDecoder.guided_forward, motion)
    return diffusion
