"""Presentation continues independently of neural inference and audio gaps."""

import cv2
import numpy as np

from trendcoffee.avatar_presentation import MouthFrame, MouthTransition


def sample(epoch=1, kind="idle", at=1.0, shift=0):
    face = np.zeros((512, 512, 3), np.float32)
    cv2.circle(face, (240 + shift, 330), 12, (240, 240, 240), -1)
    return MouthFrame(epoch, kind, face, (256, 330, 90, 65), at)


def test_first_mouth_is_immediate_and_does_not_add_a_playback_queue():
    transition = MouthTransition()
    first = sample()
    face, blended = transition.at(first, 1.001)
    np.testing.assert_array_equal(face, first.rgb)
    assert not blended


def test_transition_is_bounded_to_one_display_interval():
    transition = MouthTransition()
    previous, current = sample(), sample(at=1.1, shift=12)
    transition.at(previous, 1.0)
    middle, blended = transition.at(current, 1.1 + 1 / 48)
    assert blended
    gray = cv2.cvtColor(middle, cv2.COLOR_RGB2GRAY)
    yy, xx = np.nonzero(gray > 150)
    assert 244 < xx.mean() < 248
    assert 327 < yy.mean() < 333
    # Aligned motion has one bright mouth feature, rather than two faded copies.
    assert gray.max() > 220
    assert cv2.connectedComponents((gray > 150).astype(np.uint8))[0] == 2
    final, blended = transition.at(current, 1.1 + 1 / 24 + 0.001)
    np.testing.assert_array_equal(final, current.rgb)
    assert not blended


def test_guest_and_action_change_never_blend_previous_mouth():
    transition = MouthTransition()
    transition.at(sample(), 1.0)
    for current in (sample(epoch=2, at=1.1, shift=12), sample(epoch=2, kind="wave", at=1.2)):
        result, blended = transition.at(current, current.at + 0.001)
        np.testing.assert_array_equal(result, current.rgb)
        assert not blended
    transition.clear()
    current = sample(at=1.3, shift=12)
    result, blended = transition.at(current, current.at + 0.001)
    np.testing.assert_array_equal(result, current.rgb)
    assert not blended


def test_interpolation_never_mixes_previous_tooth_texture():
    previous, current = sample(), sample(at=1.1, shift=12)
    previous.rgb[:] = 0
    current.rgb[:] = 0
    # Nearly identical luminance allows motion tracking, while different colors
    # expose texture crossfading (the source of floating/doubled tooth fragments).
    cv2.circle(previous.rgb, (240, 330), 12, (0, 128, 0), -1)
    cv2.circle(current.rgb, (252, 330), 12, (255, 0, 0), -1)
    transition = MouthTransition()
    transition.at(previous, 1.0)
    result, interpolated = transition.at(current, 1.1 + 1 / 48)
    assert interpolated
    assert result[..., 0].max() > 240
    assert result[..., 1].max() == 0
