"""Pixel-level checks for source-preserving Ditto mouth compositing."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from trendcoffee.avatar_appearance import (
    blend_rest_mouth,
    calm_source_frames,
    composite_mouth,
    register_source,
)
from trendcoffee.avatar_expression import source_expression_anchors


def test_installed_poster_matches_the_selected_appearance_source():
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / ".runtime/trend-avatar.json"
    if not manifest_path.exists():
        pytest.skip("No installed avatar manifest")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("engine") != "ditto":
        pytest.skip("This appearance contract targets Ditto")
    poster = cv2.imread(str(root / "frontend/public/avatars/trend-live.png"))
    capture = cv2.VideoCapture(str(root / manifest["source"]))
    try:
        success, first_frame = capture.read()
    finally:
        capture.release()
    assert success and poster is not None
    first_frame = cv2.resize(first_frame, (poster.shape[1], poster.shape[0]))
    assert np.abs(poster.astype(float) - first_frame).mean() < 1, (
        "The mic-off poster and active appearance source differ"
    )


def test_generated_face_cannot_change_original_eyes_hair_or_background():
    rng = np.random.default_rng(7)
    source = rng.integers(0, 255, (512, 512, 3), dtype=np.uint8)
    original = source.copy()
    generated = np.full((512, 512, 3), 220, np.float32)
    region = (256, 330, 90, 65)
    result = composite_mouth(source, generated, np.eye(3), region)
    np.testing.assert_array_equal(result[:260], source[:260])
    np.testing.assert_array_equal(result[:, :160], source[:, :160])
    np.testing.assert_array_equal(result[400:], source[400:])
    np.testing.assert_array_equal(source, original)
    # Replace the complete generated mouth, without ghosting closed source lips.
    np.testing.assert_array_equal(result[315:345, 240:272], 220)


def test_mouth_mask_follows_affine_crop_and_feathers_the_boundary():
    source = np.full((260, 260, 3), 40, np.uint8)
    generated = np.full((512, 512, 3), 220, np.float32)
    affine = np.array([[0.5, 0, 2], [0, 0.5, 3], [0, 0, 1]])
    result = composite_mouth(source, generated, affine, (256, 330, 90, 65))
    assert (result[163:173, 125:135] == 220).all()
    np.testing.assert_array_equal(result[:130], source[:130])
    assert np.abs(np.diff(result.astype(int), axis=0)).max() < 45
    assert np.abs(np.diff(result.astype(int), axis=1)).max() < 45


def test_offscreen_mouth_is_safe_and_returns_independent_frame():
    source = np.zeros((80, 80, 3), np.uint8)
    affine = np.array([[1, 0, 1000], [0, 1, 1000], [0, 0, 1]])
    result = composite_mouth(source, np.ones((512, 512, 3)), affine, (256, 330, 90, 65))
    np.testing.assert_array_equal(result, source)
    assert not np.shares_memory(result, source)


def test_cached_mouth_tracks_current_source_landmarks_without_moving_eyes():
    source = np.full((512, 512, 3), 40, np.uint8)
    generated = np.zeros((512, 512, 3), np.float32)
    generated[315:345, 240:272] = 220
    result = composite_mouth(
        source, generated, np.eye(3), (300, 350, 90, 65), render_region=(256, 330, 90, 65)
    )
    assert (result[340:360, 290:310] == 220).all()
    np.testing.assert_array_equal(result[:250], source[:250])


def test_registration_reuses_existing_landmark_pass_and_restores_detector():
    class Detector:
        calls = 0

        def __call__(self, image):
            self.calls += 1
            landmarks = np.full((1, 478, 3), 0.5, np.float32)
            landmarks[0, 61, :2] = (0.38, 0.65)
            landmarks[0, 291, :2] = (0.62, 0.65)
            landmarks[0, 0, :2] = (0.5, 0.63)
            landmarks[0, 17, :2] = (0.5, 0.69)
            return landmarks

    class Source:
        landmark478 = Detector()

    class Registrar:
        source2info = Source()

        def __call__(self, path, **kwargs):
            self.source2info.landmark478(None)
            self.source2info.landmark478(None)
            return {"img_rgb_lst": [None, None]}

    registrar = Registrar()
    detector = registrar.source2info.landmark478
    info = register_source(registrar, "clip.mp4")
    assert registrar.source2info.landmark478 is detector
    assert detector.calls == 2
    assert len(info["mouth_regions"]) == 2
    cx, cy, rx, ry = info["mouth_regions"][0]
    assert 250 < cx < 262 and 320 < cy < 355
    assert 80 < rx < 120 and 50 < ry < 100


def test_open_source_frame_uses_closed_anchor_instead_of_adding_its_existing_vowel():
    closed, opened = np.full((1, 63), 0.02, np.float32), np.full((1, 63), 0.2, np.float32)

    class Detector:
        count = 0

        def __call__(self, image):
            points = np.full((1, 478, 3), 0.5, np.float32)
            points[0, 61, :2], points[0, 291, :2] = (0.38, 0.65), (0.62, 0.65)
            points[0, 0, :2], points[0, 17, :2] = (0.5, 0.63), (0.5, 0.69)
            points[0, 13, :2] = (0.5, 0.65)
            points[0, 14, :2] = (0.5, 0.65 if self.count == 0 else 0.74)
            self.count += 1
            return points

    class Source:
        landmark478 = Detector()

    class Registrar:
        source2info = Source()

        def __call__(self, *args, **kwargs):
            self.source2info.landmark478(None)
            self.source2info.landmark478(None)
            return {"img_rgb_lst": [None, None], "x_s_info_lst": [{"exp": closed}, {"exp": opened}]}

    info = register_source(Registrar(), "wave.mp4")
    assert info.get("mouth_expression_anchors") is not None
    np.testing.assert_array_equal(info["mouth_expression_anchors"][0], closed)
    np.testing.assert_array_equal(info["mouth_expression_anchors"][1], closed)


def test_shared_anchor_gives_every_frame_one_closed_lip_shape():
    expressions = np.zeros((5, 1, 63), np.float32)
    expressions[:, 0, 0] = [0.0, 0.0, 0.0, 0.9, 0.5]  # A pursed closed frame, then an open one.
    apertures = np.array([0.01, 0.02, 0.01, 0.02, 0.3], np.float32)
    anchors = source_expression_anchors(expressions, apertures, shared=True)
    assert (anchors == anchors[0]).all()
    assert anchors[0, 0, 0] == 0.0


def test_shared_anchor_registration_passes_through_without_reaching_the_registrar():
    class Source:
        landmark478 = staticmethod(
            lambda image: np.tile(np.linspace(0.1, 0.9, 478)[None, :, None], (1, 1, 3))
        )

    class Registrar:
        source2info = Source()

        def __call__(self, path, **kwargs):
            assert "shared_anchor" not in kwargs
            self.source2info.landmark478(None)
            self.source2info.landmark478(None)
            return {
                "img_rgb_lst": [None, None],
                "x_s_info_lst": [
                    {"exp": np.zeros((1, 63), np.float32)},
                    {"exp": np.ones((1, 63), np.float32)},
                ],
            }

    info = register_source(Registrar(), "clip.mp4", shared_anchor=True)
    anchors = info["mouth_expression_anchors"]
    assert (anchors == anchors[0]).all()


def test_calm_source_frames_pick_the_nearest_pose_among_calm_closed_frames_only():
    apertures = np.array([0.01, 0.01, 0.30, 0.01, 0.01, 0.01])
    widths = np.array([100.0, 101, 100, 60, 99, 102])  # Frame 3 is pursed, frame 2 is open.
    poses = np.array([[0.0, 0, 0], [0, 0, 0], [0, 1, 0], [0, 2, 0], [0, 9, 0], [0, 2.5, 0]])
    chosen = calm_source_frames(apertures, widths, poses)
    assert set(chosen) <= {0, 1, 4, 5}
    assert chosen[2] == 1  # An open frame borrows the calm frame with the closest head pose.
    assert chosen[3] == 5 and chosen[4] == 4
    assert chosen[0] == 0 and chosen[1] == 1  # A calm frame keeps its own appearance.


def test_calm_source_frames_fall_back_when_no_frame_is_closed():
    chosen = calm_source_frames(np.array([0.3, 0.2]), np.array([100.0, 100]), np.zeros((2, 3)))
    assert chosen == [1, 1]


def test_rest_mouth_changes_only_the_mouth_and_keeps_neck_collar_and_hair():
    own = np.full((512, 512, 3), 100, np.float32)
    calm = np.full((512, 512, 3), 200, np.float32)
    result = blend_rest_mouth(own, calm, (256.0, 330.0, 90.0, 65.0))
    assert (result[335, 256] == 200).all(), "The mouth comes from the calm frame"
    np.testing.assert_array_equal(result[480:], own[480:])  # Neck and collar.
    np.testing.assert_array_equal(result[:200], own[:200])  # Eyes, hair and forehead.
    np.testing.assert_array_equal(result[:, :120], own[:, :120])  # Cheek edge and hair.
    edge = result[335, 170, 0]
    assert 100 < edge < 200, "The boundary is feathered, not a hard seam"


def test_rest_mouth_leaves_the_inputs_unchanged():
    own = np.full((512, 512, 3), 100, np.float32)
    calm = np.full((512, 512, 3), 200, np.float32)
    blend_rest_mouth(own, calm, (256.0, 330.0, 90.0, 65.0))
    assert (own == 100).all() and (calm == 200).all()
