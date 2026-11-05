"""Why the camera did or did not open a session, as numbers on /api/kiosk/status."""

from trendcoffee.kiosk import PresencePolicy


def near(seq, wall, track=7, distance=0.4):
    return {
        "event": "person_near",
        "frame_seq": seq,
        "captured_at": wall,
        "nearest_m": distance,
        "track_id": track,
    }


def test_a_late_camera_event_is_reported_as_stale_with_its_age():
    policy = PresencePolicy()
    assert policy.observe(near(1, 100.0), 10.0, 103.0) is None
    assert policy.diagnostics()["last"] == {"reason": "stale", "age_s": 3.0}


def test_the_guest_whose_session_just_ended_is_reported_as_blocked():
    policy = PresencePolicy()
    assert policy.observe(near(1, 100.0), 10.0, 100.1) is None
    assert policy.observe(near(2, 101.0), 11.0, 101.1) is None
    assert policy.observe(near(3, 102.0), 12.0, 102.1) == "enter"
    policy.reset(block=True)  # the session ended for idleness while the guest stayed
    assert policy.observe(near(4, 105.0), 15.0, 105.1) is None
    info = policy.diagnostics()
    assert info["last"] == {"reason": "blocked_same_guest", "track": 7, "wait_s": 10.0}
    assert info["blocked_track"] == 7 and info["reasons"]["enter"] == 1
    # Stepping out of range clears the block; coming back opens a new session.
    far = {**near(5, 106.0), "event": "person_far", "nearest_m": 1.2}
    assert policy.observe(far, 16.0, 106.1) is None
    assert policy.diagnostics()["last"]["reason"] == "far"
    assert policy.observe(near(6, 107.0), 17.0, 107.1) is None
    assert policy.observe(near(7, 108.0), 18.0, 108.1) is None
    assert policy.observe(near(8, 109.0), 19.0, 109.1) == "enter"


def test_a_guest_who_stays_after_the_session_ended_is_welcomed_again():
    """User decision 2026-11-05: no need to leave the camera; a short pause, then a session."""
    policy = PresencePolicy()
    for seq, at in enumerate((100.0, 101.0, 102.0), start=1):
        result = policy.observe(near(seq, at), at, at + 0.1)
    assert result == "enter"
    policy.reset(block=True)
    results = [
        policy.observe(near(seq, at), at, at + 0.1)
        for seq, at in ((4, 103.0), (5, 108.0), (6, 112.0))
    ]
    assert results == [None, None, None], "not greeted again during the pause"
    assert policy.diagnostics()["last"]["reason"] == "blocked_same_guest"
    at = 113.0
    assert policy.observe(near(7, at), at, at + 0.1) is None  # pause over: counts as arriving
    assert policy.observe(near(8, 114.0), 114.0, 114.1) is None
    assert policy.observe(near(9, 115.0), 115.0, 115.1) == "enter"
    assert policy.blocked_track is None
