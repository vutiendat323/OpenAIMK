"""Body observations are evidence with a shelf life and a camera of origin.

OpenJarvis keeps a kiosk session alive while ``body_m`` is inside the zone.  A
body measured once and never refreshed (the presence worker failing every
tick) or measured on a camera the Scene has since forgotten must not do that.
"""

from Visual.domain.scene import Scene

BODY = [{"box": (0, 0, 100, 400), "dist": 1.2}]
FACE = [(20, 20, 60, 80, 1, 0.9)]


def test_a_body_older_than_its_max_age_is_no_longer_reported():
    scene = Scene(body_max_age_sec=3.0)
    scene.observe_faces(FACE, raw={1: 1.2}, landmarks={1: [[1.0, 1.0]] * 5}, t=100.0)
    scene.observe_bodies(BODY, t=100.0)

    fresh = scene.snapshot(t=102.9)
    assert fresh.body_m == 1.2 and fresh.people[0].body_m == 1.2

    stale = scene.snapshot(t=103.1)
    assert stale.body_m == -1.0
    assert stale.bodies == ()
    assert stale.people[0].body_m is None


def test_bodies_measured_before_a_reset_are_dropped():
    scene = Scene()
    generation = scene.generation
    scene.reset()  # the camera switched while the presence tick was running

    scene.observe_bodies(BODY, generation=generation)

    assert scene.snapshot().body_m == -1.0


def test_bodies_measured_after_the_reset_are_kept():
    scene = Scene()
    scene.reset()

    scene.observe_bodies(BODY, generation=scene.generation)

    assert scene.snapshot().body_m == 1.2
