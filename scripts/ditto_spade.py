"""Inference-only packing of Ditto SPADE conditioning convolutions.

Install after loading checkpoint weights and before channels-last conversion and
torch.compile. No conditioning values are cached between input frames. Packing
changes parameter names, so load checkpoints before applying this adapter.
"""

import torch
from torch import nn
from torch.nn import functional as F


def _joined_conv(convs, groups=1):
    first = convs[0]
    joined = nn.Conv2d(
        first.in_channels * groups,
        sum(conv.out_channels for conv in convs),
        first.kernel_size,
        stride=first.stride,
        padding=first.padding,
        dilation=first.dilation,
        groups=groups,
        bias=True,
        padding_mode=first.padding_mode,
        device=first.weight.device,
        dtype=first.weight.dtype,
    )
    with torch.no_grad():
        joined.weight.copy_(torch.cat([conv.weight for conv in convs]))
        joined.bias.copy_(torch.cat([conv.bias for conv in convs]))
    if first.weight.is_contiguous(memory_format=torch.channels_last):
        joined.to(memory_format=torch.channels_last)
    return joined


def _normalize(norm, x, affine):
    gamma, beta = affine.chunk(2, dim=1)
    return norm(x) * (1 + gamma) + beta


class FusedSPADE(nn.Module):
    """One gamma/beta convolution with the original independent filters."""

    def __init__(self, original):
        super().__init__()
        self.param_free_norm = original.param_free_norm
        self.mlp_shared = original.mlp_shared
        self.mlp_affine = _joined_conv((original.mlp_gamma, original.mlp_beta))
        self.train(original.training)

    def forward(self, x, segmap):
        segmap = F.interpolate(segmap, size=x.shape[2:], mode="nearest")
        return _normalize(self.param_free_norm, x, self.mlp_affine(self.mlp_shared(segmap)))


class FusedSPADEResnetBlock(nn.Module):
    """Evaluate all distinct conditioning stems together once per residual block.

    Equal-width affine heads use one grouped convolution. Unequal heads keep
    separate gamma/beta convolutions, avoiding padding and extra multiply-adds.
    """

    def __init__(self, original):
        super().__init__()
        self.learned_shortcut = original.learned_shortcut
        self.conv_0, self.conv_1 = original.conv_0, original.conv_1
        self.norm_0 = original.norm_0.param_free_norm
        self.norm_1 = original.norm_1.param_free_norm
        norms = [original.norm_0, original.norm_1]
        if self.learned_shortcut:
            self.conv_s = original.conv_s
            self.norm_s = original.norm_s.param_free_norm
            norms.append(original.norm_s)
        self.hidden_channels = norms[0].mlp_shared[0].out_channels
        self.affine_sizes = tuple(2 * norm.mlp_gamma.out_channels for norm in norms)
        self.mlp_shared = _joined_conv([norm.mlp_shared[0] for norm in norms])
        affine_heads = [_joined_conv((norm.mlp_gamma, norm.mlp_beta)) for norm in norms]
        self.grouped_affine = len(set(self.affine_sizes)) == 1
        if self.grouped_affine:
            affine_heads = [_joined_conv(affine_heads, groups=len(norms))]
        self.mlp_affine = nn.ModuleList(affine_heads)
        self.train(original.training)

    def forward(self, x, segmap):
        segmap = F.interpolate(segmap, size=x.shape[2:], mode="nearest")
        activation = F.relu(self.mlp_shared(segmap))
        if self.grouped_affine:
            affine = self.mlp_affine[0](activation).split(self.affine_sizes, dim=1)
        else:
            activations = activation.split(self.hidden_channels, dim=1)
            affine = tuple(
                head(value) for head, value in zip(self.mlp_affine, activations, strict=True)
            )
        if self.learned_shortcut:
            shortcut = self.conv_s(_normalize(self.norm_s, x, affine[2]))
        else:
            shortcut = x
        dx = self.conv_0(F.leaky_relu(_normalize(self.norm_0, x, affine[0]), 2e-1))
        dx = self.conv_1(F.leaky_relu(_normalize(self.norm_1, dx, affine[1]), 2e-1))
        return shortcut + dx


def install_spade_optimization(decoder, *, batch_conditioning=False, exclude_modules=()):
    """Return the adapted decoder; replace its SPADE children in place.

    Set batch_conditioning=True to pack each SPADEResnetBlock's conditioning.
    Exclusions are module paths relative to decoder, for example ("up_1",).
    A standalone SPADE/block is supported; use the returned replacement module.
    Reinstallation with the same options is harmless.
    """

    def replace(module, path):
        if path in exclude_modules:
            return module
        name = type(module).__name__
        if name == "SPADEResnetBlock" and batch_conditioning:
            return FusedSPADEResnetBlock(module)
        if name == "SPADE":
            return FusedSPADE(module)
        for child_name, child in tuple(module.named_children()):
            child_path = f"{path}.{child_name}" if path else child_name
            setattr(module, child_name, replace(child, child_path))
        return module

    return replace(decoder, "")
