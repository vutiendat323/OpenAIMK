"""Keep source lip shape while applying the model's speech displacement."""

import numpy as np


def calibrate_expression(expression, predicted_rest, source_rest, *, opening_limit=0.0):
    expression, predicted_rest, source_rest = (
        np.asarray(value, dtype=np.float32) for value in (expression, predicted_rest, source_rest)
    )
    if expression.shape != (1, 63) or not (
        predicted_rest.shape == expression.shape == source_rest.shape
    ):
        raise ValueError("Expected matching 21x3 expression coordinates")
    if not all(np.isfinite(value).all() for value in (expression, predicted_rest, source_rest)):
        raise ValueError("Expression coordinates must be finite")
    if not np.isfinite(opening_limit) or opening_limit < 0:
        raise ValueError("Lip opening limit must be finite and nonnegative")
    delta = expression - predicted_rest
    if opening_limit:
        # Bound vertical separation, not the entire expression. Retain sideways
        # smile motion, depth, and the common vertical motion of all lip points.
        # Small articulation is unchanged. The smooth knee avoids a hard plateau
        # and introduces no temporal filtering or extra latency.
        lips = [6, 12, 14, 17, 19, 20]
        points = delta.reshape(21, 3)
        vertical = points[lips, 1]
        center = vertical.mean()
        spread = vertical - center
        magnitude = float(np.linalg.norm(spread))
        knee = opening_limit / 2
        if magnitude > knee:
            bounded = knee + knee * np.tanh((magnitude - knee) / knee)
            points[lips, 1] = center + spread * (bounded / magnitude)
    return source_rest + delta


LIP_POINTS = [6, 12, 14, 17, 19, 20]


def closed_lip_shape(expressions):
    """The most typical of the source's closest lip poses, as 6x3 keypoints."""
    points = np.stack([np.asarray(item, np.float32).reshape(21, 3) for item in expressions])
    separation = np.ptp(points[:, LIP_POINTS, 1], axis=1)
    closed = np.argsort(separation)[: max(5, len(points) // 6)]
    lips = points[closed][:, LIP_POINTS]
    return lips[np.argmin(((lips - lips.mean(0)) ** 2).sum((1, 2)))]


def compress_lips(expression, rest_y, factor):
    """Scale vertical lip separation around the closed shape, keeping shared motion."""
    shape = np.shape(expression)
    points = np.array(expression, np.float32).reshape(21, 3)
    lips = points[LIP_POINTS, 1]
    center = lips.mean()
    points[LIP_POINTS, 1] = center + rest_y + (lips - center - rest_y) * factor
    return points.reshape(shape)


def source_expression_anchors(expressions, apertures, *, closed_threshold=0.06, shared=False):
    """Open source frames borrow a real closed frame, avoiding a second vowel."""
    expressions = np.asarray(expressions, dtype=np.float32)
    apertures = np.asarray(apertures, dtype=np.float32)
    if expressions.shape != (len(apertures), 1, 63) or not len(apertures):
        raise ValueError("Source expressions and apertures must match")
    if not np.isfinite(expressions).all() or not np.isfinite(apertures).all():
        raise ValueError("Source calibration must be finite")
    closed = np.flatnonzero(apertures <= closed_threshold)
    if not len(closed):
        closed = np.array([np.argmin(apertures)])
    candidates = expressions[closed]
    distance = ((candidates - candidates.mean(axis=0)) ** 2).sum(axis=(1, 2))
    # A real source pose, rather than a synthetic average of unrelated shapes.
    neutral = expressions[closed[int(np.argmin(distance))]]
    if shared:
        # A speaking source has pursed frames that also count as closed. One shape for
        # every frame keeps resting lips still and speech free of those vowels.
        return np.broadcast_to(neutral, expressions.shape).copy()
    anchors = expressions.copy()
    anchors[apertures > closed_threshold] = neutral
    return anchors
