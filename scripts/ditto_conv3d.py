"""Optional exact Conv3d-to-Conv2d adapter for renderer experiments.

Convert after loading checkpoints and before compiling. The adapter copies all
learned weights, preserves every spatial sample, and changes state-dict keys.
It trades a depth-expanded input allocation for a 2D convolution; speed must be
measured on the target GPU before enabling it in a renderer.
"""

from collections.abc import Iterable

import torch
from torch import nn
from torch.nn import functional as F


class Conv3dAs2d(nn.Module):
    """Apply a numeric-zero-padded Conv3d using one depth-folded Conv2d.

    Inputs and outputs remain N,C,D,H,W. ``channels_last=True`` packs the 2D
    convolution input as NHWC and returns channels_last_3d output, matching the
    existing renderer. False returns standard contiguous output. Like Conv3d,
    different convolution algorithms can produce floating-point rounding drift.
    """

    def __init__(self, conv3d: nn.Conv3d, *, channels_last: bool = True):
        super().__init__()
        if conv3d.padding_mode != "zeros" or isinstance(conv3d.padding, str):
            raise ValueError("Conv3dAs2d requires numeric zero padding")
        self.channels_last = channels_last
        self.depth_kernel = conv3d.kernel_size[0]
        self.depth_stride = conv3d.stride[0]
        self.depth_padding = conv3d.padding[0]
        self.depth_dilation = conv3d.dilation[0]
        self.conv2d = nn.Conv2d(
            conv3d.in_channels * self.depth_kernel,
            conv3d.out_channels,
            conv3d.kernel_size[1:],
            stride=conv3d.stride[1:],
            padding=conv3d.padding[1:],
            dilation=conv3d.dilation[1:],
            groups=conv3d.groups,
            bias=conv3d.bias is not None,
            device=conv3d.weight.device,
            dtype=conv3d.weight.dtype,
        )
        with torch.no_grad():
            # Channel order is (input_channel, depth_kernel_index), within groups.
            self.conv2d.weight.copy_(conv3d.weight.reshape(self.conv2d.weight.shape))
            if conv3d.bias is not None:
                self.conv2d.bias.copy_(conv3d.bias)
        self.conv2d.weight.requires_grad_(conv3d.weight.requires_grad)
        if conv3d.bias is not None:
            self.conv2d.bias.requires_grad_(conv3d.bias.requires_grad)
        if channels_last:
            self.conv2d.to(memory_format=torch.channels_last)
        self.train(conv3d.training)

    def forward(self, volume: torch.Tensor) -> torch.Tensor:
        if self.depth_padding:
            volume = F.pad(volume, (0, 0, 0, 0, self.depth_padding, self.depth_padding))
        depth_span = self.depth_dilation * (self.depth_kernel - 1) + 1
        windows = volume.unfold(2, depth_span, self.depth_stride)[..., :: self.depth_dilation]
        batch, channels, depth, height, width, kernel = windows.shape
        if self.channels_last:
            # This reshape materializes each depth neighborhood once, directly in
            # NHWC order, avoiding an intermediate NCHW copy before conversion.
            folded = windows.permute(0, 2, 3, 4, 1, 5).reshape(
                batch * depth, height, width, channels * kernel
            )
            folded = folded.permute(0, 3, 1, 2)
        else:
            folded = windows.permute(0, 2, 1, 5, 3, 4).reshape(
                batch * depth, channels * kernel, height, width
            )
        result = self.conv2d(folded)
        result = result.reshape(batch, depth, *result.shape[1:]).permute(0, 2, 1, 3, 4)
        memory_format = torch.channels_last_3d if self.channels_last else torch.contiguous_format
        return result.contiguous(memory_format=memory_format)


def replace_conv3d_modules(
    module: nn.Module, names: Iterable[str] | None = None, *, channels_last: bool = True
) -> list[str]:
    """Replace selected named Conv3d children in place and return their paths.

    ``names=None`` selects all Conv3d descendants. Explicit paths are relative to
    ``module`` (for example ``dense_motion_network.mask``). Selection is validated
    before mutation. The root itself is not replaced; wrap a bare Conv3d directly.
    Existing Conv3dAs2d children are left alone when selecting all descendants.
    """
    if names is None:
        selected = {
            name: child
            for name, child in module.named_modules()
            if name and isinstance(child, nn.Conv3d)
        }
    else:
        selected = {}
        for name in names:
            try:
                child = module.get_submodule(name)
            except AttributeError as error:
                raise ValueError(f"{name!r} is not a Conv3d descendant") from error
            if not name or not isinstance(child, nn.Conv3d):
                raise ValueError(f"{name!r} is not a Conv3d descendant")
            selected[name] = child
    replacements = {
        name: Conv3dAs2d(child, channels_last=channels_last) for name, child in selected.items()
    }
    for name, replacement in replacements.items():
        module.set_submodule(name, replacement)
    return list(replacements)
