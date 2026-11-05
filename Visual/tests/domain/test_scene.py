"""Scene: who is in front of the kiosk, measured once, read everywhere.

These tests describe behaviour through the Scene interface only -- the
observations the worker threads push in, and the snapshot / kiosk event that
the server and console read out.  They replace the old DepthProcessor tests
and the SharedState track-distance tests.
"""

import math

import pytest

from Visual.domain.scene import Scene

KPS = [[1.0, 1.0]] * 5


def _track(tid, x=0.0):
    return (x, 0.0, x + 50.0, 60.0, tid, 0.9)


class TestEmptyScene:
    def test_nobody_there(self):
        snap = Scene().snapshot()
        assert snap.people == () and snap.nearest is None
        assert snap.body_m == -1.0 and snap.facing is False
        assert snap.event(ts=1.0) == {"event": "no_person", "ts": 1.0,
                                      "body_m": -1.0, "facing": False, "tracks": []}


class TestNearestFace:
    def test_first_measurement_is_reported_as_is(self):
        scene = Scene()
        scene.observe_faces([_track(1)], raw={1: 2.5}, landmarks={1: KPS}, t=0.0)
        snap = scene.snapshot()
        assert snap.nearest.id == 1 and snap.nearest.dist == 2.5
        assert snap.event(ts=1.0)["event"] == "person_near"
        assert snap.event(ts=1.0)["nearest_m"] == 2.5

    def test_nearest_distance_and_track_id_belong_to_the_same_person(self):
        """They used to come from different faces: min() over all distances,
        but the id of whichever track happened to be listed first."""
        scene = Scene()
        scene.observe_faces([_track(1), _track(2, x=100)], raw={1: 2.5, 2: 0.7},
                            landmarks={1: KPS, 2: KPS}, t=0.0)
        event = scene.snapshot().event(ts=1.0)
        assert event["nearest_m"] == 0.7 and event["track_id"] == 2

    def test_presence_reports_each_id_even_when_another_person_is_nearer(self):
        scene = Scene()
        scene.observe_faces([_track(1), _track(2, x=200)], raw={1: 1.4, 2: 0.5},
                            landmarks={1: KPS, 2: KPS}, t=0.0)
        scene.observe_bodies([{"box": (0, 0, 100, 400), "dist": 1.5},
                              {"box": (200, 0, 300, 400), "dist": 0.6}])
        event = scene.snapshot().event(ts=1.0)
        assert event["track_id"] == 2
        assert event["tracks"] == [
            {"track_id": 1, "distance_m": 1.4, "body_m": 1.5},
            {"track_id": 2, "distance_m": 0.5, "body_m": 0.6},
        ]

    def test_a_face_not_measured_yet_is_person_unknown(self):
        scene = Scene()
        scene.observe_faces([_track(7)], raw={}, landmarks={}, t=0.0)
        event = scene.snapshot().event(ts=1.0)
        assert event["event"] == "person_unknown" and event["track_id"] == 7

    def test_a_face_that_left_is_forgotten(self):
        scene = Scene()
        scene.observe_faces([_track(1)], raw={1: 2.0}, landmarks={1: KPS}, t=0.0)
        scene.observe_faces([], raw={}, landmarks={}, t=0.1)
        assert scene.snapshot().people == ()


class TestLandmarkGate:
    def test_gate_says_which_faces_were_measured(self):
        scene = Scene()
        scene.observe_faces([_track(1), _track(2, 60), _track(3, 120)],
                            raw={1: 1.0}, landmarks={1: KPS, 2: KPS}, t=0.0)
        gates = {p.id: p.gate for p in scene.snapshot().people}
        assert gates == {1: True,        # landmarks and a PnP reading
                         2: False,       # landmarks, but PnP rejected them
                         3: None}        # coasting: no detection this update

    def test_a_rejected_frame_holds_the_last_reading(self):
        scene = Scene()
        scene.observe_faces([_track(1)], raw={1: 1.2}, landmarks={1: KPS}, t=0.0)
        scene.observe_faces([_track(1)], raw={}, landmarks={1: KPS}, t=0.1)
        person = scene.snapshot().nearest
        assert person.gate is False and person.dist == pytest.approx(1.2)
        assert person.raw is None

    def test_a_nan_reading_holds_the_last_reading(self):
        scene = Scene()
        scene.observe_faces([_track(1)], raw={1: 2.0}, landmarks={1: KPS}, t=0.0)
        scene.observe_faces([_track(1)], raw={1: math.nan}, landmarks={1: KPS}, t=0.1)
        assert scene.snapshot().nearest.dist == pytest.approx(2.0)


class TestSmoothing:
    """Median-of-3 then a position-only Kalman, with noise per second."""

    def _stream(self, raws, hz):
        scene = Scene()
        out = []
        for i, raw in enumerate(raws):
            scene.observe_faces([_track(1)], raw={1: raw}, landmarks={1: KPS}, t=i / hz)
            out.append(scene.snapshot().nearest.dist)
        return out

    def test_a_change_moves_the_reading_part_way(self):
        out = self._stream([2.0, 3.0], hz=15)
        assert 2.0 < out[1] < 3.0

    def test_a_single_wild_sample_is_dropped(self):
        """A single wall sample in a 0.56 m stream once showed 1.22, 0.97, 0.83,
        0.74 ... for 6 s under an EMA.  Median-of-3 drops it outright."""
        out = self._stream([0.56, 0.56, 0.56, 2.60, 0.56, 0.56], hz=15)
        assert max(out) < 0.65, out

    def test_a_real_change_is_followed_on_the_second_sample(self):
        """A track born on the person behind, then settling on the real face."""
        out = self._stream([1.30, 0.50, 0.50, 0.50], hz=1)
        assert abs(out[2] - 0.50) < 0.05, out

    def test_smoothing_does_not_depend_on_how_often_it_is_read(self):
        """Noise accrues per second of elapsed time, not per call: reading
        the snapshot more often must not change the numbers."""
        a, b = Scene(), Scene()
        for i, raw in enumerate([1.3, 0.5, 0.5]):
            for scene in (a, b):
                scene.observe_faces([_track(1)], raw={1: raw}, landmarks={1: KPS}, t=i / 15)
            for _ in range(20):
                b.snapshot()
        assert a.snapshot().nearest.dist == b.snapshot().nearest.dist


class TestBodies:
    def test_a_body_without_a_face_still_reports_presence(self):
        scene = Scene()
        scene.observe_bodies([{"box": (0, 0, 100, 400), "dist": 1.2}])
        event = scene.snapshot().event(ts=1.0)
        assert event["event"] == "no_person"          # unchanged for old clients
        assert event["body_m"] == 1.2 and event["facing"] is False

    def test_the_nearest_body_wins(self):
        scene = Scene()
        scene.observe_bodies([{"box": (0, 0, 9, 9), "dist": 2.4},
                              {"box": (0, 0, 9, 9), "dist": 0.9}])
        assert scene.snapshot().body_m == 0.9

    def test_a_measured_face_sets_facing(self):
        scene = Scene()
        scene.observe_faces([_track(1)], raw={1: 0.7}, landmarks={1: KPS}, t=0.0)
        scene.observe_bodies([{"box": (0, 0, 100, 400), "dist": 0.8}])
        event = scene.snapshot().event(ts=1.0)
        assert event["event"] == "person_near" and event["facing"] is True
        assert event["body_m"] == 0.8

    def test_a_face_carries_the_body_it_sits_in(self):
        scene = Scene()
        scene.observe_faces([(40, 10, 60, 40, 1, 0.9)], raw={1: 0.7},
                            landmarks={1: KPS}, t=0.0)
        scene.observe_bodies([{"box": (0, 0, 100, 400), "dist": 0.83},
                              {"box": (300, 0, 400, 400), "dist": 2.0}])
        assert scene.snapshot().nearest.body_m == 0.83


class TestSpoof:
    def test_spoof_tags_attach_to_their_face(self):
        scene = Scene()
        scene.observe_faces([_track(1), _track(2, 60)], raw={1: 1.0, 2: 1.5},
                            landmarks={1: KPS, 2: KPS}, t=0.0)
        scene.observe_spoof({2: (True, 0.82)})
        people = {p.id: p for p in scene.snapshot().people}
        assert people[2].spoof == 0.82 and people[2].spoof_flag is True
        assert people[1].spoof is None


def test_mouth_activity_follows_lip_openings_and_leaves_with_the_track():
    scene = Scene()
    track = [(0, 0, 50, 60, 1, 0.9)]
    for i in range(10):
        t = i / 15
        scene.observe_faces(track, raw={}, landmarks={}, t=t)
        scene.observe_mouths({1: 0.3 if i % 2 else 0.0}, t=t)
    assert scene.snapshot().people[0].mouth == 1.0

    scene.observe_faces([], raw={}, landmarks={}, t=1.0)
    scene.observe_faces(track, raw={}, landmarks={}, t=1.1)
    assert scene.snapshot().people[0].mouth is None
