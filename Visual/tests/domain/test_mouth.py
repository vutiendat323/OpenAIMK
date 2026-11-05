"""Mouth activity: how much a face's lip opening varies over the last half second."""

import math

from Visual.domain.mouth import MouthActivity


def _feed(m, tid, openings, t0=0.0, dt=1 / 15):
    for i, value in enumerate(openings):
        m.update(tid, value, t0 + i * dt)
    return t0 + (len(openings) - 1) * dt


def test_a_still_mouth_is_inactive():
    m = MouthActivity()
    _feed(m, 1, [0.005] * 10)
    assert m.activity(1) < 0.1


def test_a_talking_mouth_is_active_and_capped_at_one():
    m = MouthActivity()
    _feed(m, 1, [0.0, 0.3] * 5)
    assert m.activity(1) == 1.0


def test_only_the_last_window_counts():
    m = MouthActivity(window_s=0.5)
    t = _feed(m, 1, [0.0, 0.3] * 5)
    _feed(m, 1, [0.01] * 10, t0=t + 1 / 15)
    assert m.activity(1) < 0.1


def test_unknown_or_single_sample_track_has_no_activity():
    m = MouthActivity()
    assert m.activity(7) is None
    m.update(7, 0.2, 0.0)
    assert m.activity(7) is None


def test_retain_drops_tracks_that_left():
    m = MouthActivity()
    _feed(m, 1, [0.0, 0.3] * 5)
    m.retain({2})
    assert m.activity(1) is None


def test_scale_maps_std_to_activity():
    m = MouthActivity(scale=0.06)
    _feed(m, 1, [0.0, 0.06] * 5)  # std 0.03 -> 0.5
    assert math.isclose(m.activity(1), 0.5, abs_tol=0.02)
