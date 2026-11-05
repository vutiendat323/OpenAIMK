"""A blink of the source clip must stay a blink, not a half-second of closed eyes."""

import numpy as np

from trendcoffee.avatar_blink import blink_flags


def eyes(opening):
    points = np.zeros((478, 2), np.float32)
    points[33], points[133] = [180, 220], [230, 220]
    points[362], points[263] = [280, 220], [330, 220]
    points[159], points[145] = [205, 220 - opening / 2], [205, 220 + opening / 2]
    points[386], points[374] = [305, 220 - opening / 2], [305, 220 + opening / 2]
    return points


def test_only_frames_with_closed_eyes_are_flagged_as_blinks():
    openings = [14, 14, 13, 4, 2, 3, 12, 14, 14]
    flags = blink_flags([eyes(value) for value in openings])
    assert flags == [False, False, False, True, True, True, False, False, False]


def test_a_clip_without_any_blink_has_no_flags():
    assert not any(blink_flags([eyes(14) for _ in range(10)]))
