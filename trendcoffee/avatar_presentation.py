"""Bounded CPU mouth transitions; source video presentation needs no GPU wait."""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True, eq=False)
class MouthFrame:
    epoch: int
    kind: str
    rgb: np.ndarray
    region: tuple
    at: float
    index: int | None = None


class MouthTransition:
    def __init__(self, seconds=1 / 24):
        self.seconds = seconds
        self.clear()

    def clear(self):
        self.current = None
        self._flow = None

    @staticmethod
    def _prepare(previous, current):
        cx, cy, rx, ry = current.region
        px, py, prx, pry = previous.region
        height, width = current.rgb.shape[:2]
        left, top = max(0, int(cx - rx - 2)), max(0, int(cy - ry - 2))
        right, bottom = min(width, int(cx + rx + 3)), min(height, int(cy + ry + 3))
        if right <= left or bottom <= top:
            return None
        matrix = np.array(
            [[rx / prx, 0, cx - px * rx / prx - left], [0, ry / pry, cy - py * ry / pry - top]],
            dtype=np.float32,
        )
        size = (right - left, bottom - top)
        before = cv2.warpAffine(previous.rgb, matrix, size, flags=cv2.INTER_LINEAR)
        after = current.rgb[top:bottom, left:right]
        scale = min(1.0, 96 / max(size))
        small_size = (max(8, round(size[0] * scale)), max(8, round(size[1] * scale)))

        def gray(image):
            image = cv2.cvtColor(np.clip(image, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
            return cv2.resize(image, small_size, interpolation=cv2.INTER_AREA)

        p, c = gray(before), gray(after)

        def flow(a, b):
            result = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 21, 3, 5, 1.1, 0)
            result = cv2.resize(result, size, interpolation=cv2.INTER_LINEAR)
            result *= (size[0] / small_size[0], size[1] / small_size[1])
            return result

        forward, backward = flow(p, c), flow(c, p)
        x, y = np.meshgrid(
            np.arange(size[0], dtype=np.float32), np.arange(size[1], dtype=np.float32)
        )
        reverse = cv2.remap(forward, x + backward[..., 0], y + backward[..., 1], cv2.INTER_LINEAR)
        valid = np.linalg.norm(backward + reverse, axis=2) < 1.5
        valid &= np.linalg.norm(backward, axis=2) < min(size) * 0.25
        gray_after = cv2.cvtColor(after.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        gradient = np.hypot(
            cv2.Sobel(gray_after, cv2.CV_32F, 1, 0), cv2.Sobel(gray_after, cv2.CV_32F, 0, 1)
        )
        valid &= gradient > 15
        points = np.ascontiguousarray(np.stack((x[valid], y[valid]), axis=1)[::3])
        if len(points) < 12:
            return None
        destination = points + backward[valid][::3]
        affine, inliers = cv2.estimateAffine2D(
            points, destination, method=cv2.RANSAC, ransacReprojThreshold=1.5
        )
        if affine is None or inliers.mean() < 0.65:
            return None
        scales = np.linalg.svd(affine[:, :2], compute_uv=False)
        if scales.min() < 0.5 or scales.max() > 2 or np.linalg.det(affine[:, :2]) <= 0:
            return None
        # One affine map of one texture cannot fold or overlay two tooth rows.
        return left, top, after, affine.astype(np.float32)

    def at(self, frame, now):
        if frame is not self.current:
            previous = self.current
            self.current, self._flow = frame, None
            if (
                previous is not None
                and previous.epoch == frame.epoch
                and previous.kind == frame.kind
                and 0 < frame.at - previous.at < 0.5
                and now - frame.at < self.seconds
            ):
                self._flow = self._prepare(previous, frame)
        alpha = np.float32(np.clip((now - frame.at) / self.seconds, 0, 1))
        if self._flow is None or alpha >= 1:
            self._flow = None
            return frame.rgb, False
        left, top, after, affine = self._flow
        transform = affine * (1 - alpha) + np.eye(2, 3, dtype=np.float32) * alpha
        patch = cv2.warpAffine(
            after,
            transform,
            (after.shape[1], after.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        result = frame.rgb.copy()
        result[top : top + patch.shape[0], left : left + patch.shape[1]] = patch
        return result, True
