"""Exact interior decoder ROI; retain the full-frame instance statistics."""

import torch
import torch.nn.functional as F


class MouthDecoder(torch.nn.Module):
    def __init__(self, decoder, roi):
        super().__init__()
        if len(roi) != 4 or any(value % 2 for value in roi):
            raise ValueError("Decoder ROI must align to the two-pixel shuffle")
        x0, y0, x1, y1 = roi
        if not 0 <= x0 < x1 or not 0 <= y0 < y1:
            raise ValueError("Invalid decoder ROI")
        self.decoder, self.roi = decoder, tuple(roi)

    @staticmethod
    def _conditioning(norm, seg, box):
        x0, y0, x1, y1 = box
        # Both conditioning convolutions have a one-pixel radius. Trim the two
        # artificial patch boundaries so every retained value is full-frame exact.
        patch = seg[:, :, y0 - 2 : y1 + 2, x0 - 2 : x1 + 2]
        activation = norm.mlp_shared(patch)
        gamma = norm.mlp_gamma(activation)[:, :, 2:-2, 2:-2]
        beta = norm.mlp_beta(activation)[:, :, 2:-2, 2:-2]
        return gamma, beta

    def forward(self, feature):
        model = self.decoder
        x = model.fc(feature)
        x = model.G_middle_0(x, feature)
        x = model.G_middle_1(x, feature)
        x = model.G_middle_2(x, feature)
        x = model.G_middle_3(x, feature)
        x = model.G_middle_4(x, feature)
        x = model.G_middle_5(x, feature)
        x = model.up_0(model.up(x), feature)
        x = model.up(x)
        block = model.up_1
        x0, y0, x1, y1 = self.roi
        height, width = x.shape[-2:]
        a, b, c, d = x0 // 2, y0 // 2, x1 // 2, y1 // 2
        if a < 4 or b < 4 or c + 4 > width or d + 4 > height:
            # Boundary ROIs retain the original full decoder behavior.
            return torch.sigmoid(model.conv_img(F.leaky_relu(block(x, feature), 0.2)))

        # conv0 is full-frame: norm1 statistics depend on all its pixels. Cropping
        # this prefix would change skin/lip appearance even with unchanged weights.
        dense = block.conv_0(block.actvn(block.norm_0(x, feature)))
        normalized = block.norm_1.param_free_norm(dense)
        seg = F.interpolate(feature, size=(height, width), mode="nearest")

        # One halo for conv1 and one for the final RGB convolution.
        gamma, beta = self._conditioning(block.norm_1, seg, (a - 2, b - 2, c + 2, d + 2))
        patch = normalized[:, :, b - 2 : d + 2, a - 2 : c + 2] * (1 + gamma) + beta
        dx = F.conv2d(F.leaky_relu(patch, 0.2), block.conv_1.weight, block.conv_1.bias)

        gamma, beta = self._conditioning(block.norm_s, seg, (a - 1, b - 1, c + 1, d + 1))
        normalized = block.norm_s.param_free_norm(x)[:, :, b - 1 : d + 1, a - 1 : c + 1]
        shortcut = block.conv_s(normalized * (1 + gamma) + beta)
        image_conv = model.conv_img[0]
        pixels = F.conv2d(F.leaky_relu(shortcut + dx, 0.2), image_conv.weight, image_conv.bias)
        pixels = torch.sigmoid(F.pixel_shuffle(pixels, 2))
        result = torch.zeros(
            (feature.shape[0], 3, height * 2, width * 2), dtype=pixels.dtype, device=pixels.device
        )
        result[:, :, y0:y1, x0:x1] = pixels
        return result
