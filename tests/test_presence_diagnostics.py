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


def test_a_held_back_guest_is_reported_as_blocked():
    """With a positive block time the same track waits; the status says how long."""
    policy = PresencePolicy(block_seconds=10.0)
    assert policy.observe(near(1, 100.0), 10.0, 100.1) is None
    assert policy.observe(near(2, 101.0), 11.0, 101.1) is None
    assert policy.observe(near(3, 102.0), 12.0, 102.1) == "enter"
    policy.reset(block=True)
    assert policy.observe(near(4, 105.0), 15.0, 105.1) is None
    info = policy.diagnostics()
    assert info["last"] == {"reason": "blocked_same_guest", "track": 7, "wait_s": 10.0}
    assert info["blocked_track"] == 7 and info["reasons"]["enter"] == 1
    far = {**near(5, 106.0), "event": "person_far", "nearest_m": 1.2}
    assert policy.observe(far, 16.0, 106.1) is None
    assert policy.diagnostics()["last"]["reason"] == "far"
    assert policy.blocked_track is None, "stepping away clears it"


def test_a_guest_who_stays_after_the_session_ended_is_a_new_customer():
    """User decision 2026-11-05: no pause; the usual two seconds near, then a new session."""
    policy = PresencePolicy()
    for seq, at in enumerate((100.0, 101.0, 102.0), start=1):
        result = policy.observe(near(seq, at), at, at + 0.1)
    assert result == "enter"
    policy.reset(block=True)  # the session ended for idleness; the guest is still there
    assert policy.observe(near(4, 103.0), 103.0, 103.1) is None
    assert policy.observe(near(5, 104.0), 104.0, 104.1) is None
    assert policy.observe(near(6, 105.0), 105.0, 105.1) == "enter"
    assert policy.blocked_track is None
