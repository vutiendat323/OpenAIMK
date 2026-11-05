"""Whole-face regression: a changed chin must not overwrite the neck or hair."""

import numpy as np
import pytest

from trendcoffee import avatar_whole_face as face


def landmarks():
    result = np.full((478, 2), [256, 250], np.float32)
    angles = np.linspace(-np.pi / 2, 3 * np.pi / 2, len(face.OVAL), endpoint=False)
    result[face.OVAL] = np.column_stack((256 + 130 * np.cos(angles), 250 + 170 * np.sin(angles)))
    result[face.BROWS] = [190, 190]  # Top of the brows, above the eyes
    result[[33, 133, 263, 362, 168, 6, 197, 1]] = [
        [190, 215],
        [215, 215],
        [320, 215],
        [295, 215],
        [256, 225],
        [256, 245],
        [256, 260],
        [256, 280],
    ]
    return result


def test_whole_face_replaces_eyes_cheeks_and_mouth_but_preserves_neck_and_hair():
    original = np.full((512, 512, 3), 80, np.uint8)
    generated = np.full((512, 512, 3), 90, np.float32)
    generated[200:230, 180:330] = 150  # Eyes
    generated[280:300, 195:215] = 150  # Cheek
    generated[320:350, 230:280] = 150  # Mouth
    untouched = original.copy()
    result = face.composite_whole_face(original, generated, np.eye(3), landmarks())
    np.testing.assert_array_equal(result[430:], original[430:])
    np.testing.assert_array_equal(result[:65], original[:65])
    np.testing.assert_array_equal(result[:, :120], original[:, :120])
    assert (result[215, 200] > 100).all()
    assert (result[290, 205] > 100).all()
    assert (result[335, 250] > 100).all()
    np.testing.assert_array_equal(original, untouched)


def test_forehead_above_the_brows_stays_the_clips_so_a_turned_head_cannot_add_hair_wedges():
    original = np.full((512, 512, 3), 80, np.uint8)
    generated = np.full((512, 512, 3), 90, np.float32)
    generated[130:170, 200:300] = 20  # Dark hair wedge the decoder drew on the forehead
    generated[200:230, 180:330] = 150  # Eyes
    result = face.composite_whole_face(original, generated, np.eye(3), landmarks())
    np.testing.assert_array_equal(result[130:170, 200:300], original[130:170, 200:300])
    assert (result[215, 200] > 100).all()


def test_face_mask_follows_the_actual_output_affine_without_spilling_onto_the_body():
    original = np.full((400, 400, 3), 80, np.uint8)
    generated = np.full((512, 512, 3), 90, np.float32)
    generated[320:350, 230:280] = 150
    affine = np.array([[0.5, 0, 30], [0, 0.5, 20], [0, 0, 1]], np.float32)
    result = face.composite_whole_face(original, generated, affine, landmarks())
    assert (result[187, 155] > 100).all()
    np.testing.assert_array_equal(result[240:], original[240:])
    np.testing.assert_array_equal(result[:, :85], original[:, :85])


def bins(degrees):
    """Ditto's 66-bin angle code with this expectation, as the audio model emits it."""
    position = (degrees + 97.5) / 3
    low = int(np.floor(position))
    weight = position - low
    probability = np.full(66, 1e-9, np.float32)
    probability[low], probability[low + 1] = 1 - weight, weight
    return np.log(np.maximum(probability, 1e-9))[None]


def pose(pitch=0.0, yaw=0.0, roll=0.0, t=(0.0, 0.0, 0.0), scale=1.0):
    return {
        "pitch": bins(pitch),
        "yaw": bins(yaw),
        "roll": bins(roll),
        "t": np.array([t], np.float32),
        "scale": np.array([[scale]], np.float32),
    }


def test_pose_degrees_read_the_expectation_of_the_bins():
    assert face.pose_degrees(bins(7.5))[0] == pytest.approx(7.5, abs=0.01)


def test_head_follows_the_audio_displacement_in_degrees_on_top_of_the_clips_own_pose():
    own = pose(pitch=-4.0, yaw=10.0, roll=1.0)
    rest = pose(pitch=1.0, yaw=-1.0, roll=0.0)
    voice = pose(pitch=3.0, yaw=-2.5, roll=0.5)
    result = face.head_drive(own, voice, rest, 1.0, 1.0)
    assert result["pitch"][0] == pytest.approx(-2.0, abs=0.02)
    assert result["yaw"][0] == pytest.approx(8.5, abs=0.02)
    assert result["roll"][0] == pytest.approx(1.5, abs=0.02)


def test_turning_the_face_is_tamed_separately_so_the_eyes_keep_looking_at_the_camera():
    own = pose(pitch=0.0, yaw=0.0, roll=0.0)
    rest = pose(pitch=0.0, yaw=0.0, roll=0.0)
    voice = pose(pitch=4.0, yaw=-5.0, roll=2.0)
    result = face.head_drive(own, voice, rest, 1.0, 1.0, turn_gain=0.25)
    assert result["yaw"][0] == pytest.approx(-1.25, abs=0.02)
    assert result["pitch"][0] == pytest.approx(1.0, abs=0.02)
    assert result["roll"][0] == pytest.approx(2.0, abs=0.02)


def test_zero_turn_gain_keeps_the_face_exactly_as_the_clip_faces_the_camera():
    own = pose(pitch=5.0, yaw=2.0, roll=0.1)
    rest = pose(pitch=0.0, yaw=0.0, roll=0.0)
    voice = pose(pitch=4.0, yaw=-6.0, roll=1.0)
    result = face.head_drive(own, voice, rest, 1.0, 1.0, turn_gain=0.0)
    assert result["yaw"][0] == pytest.approx(2.0, abs=0.01)
    assert result["pitch"][0] == pytest.approx(5.0, abs=0.01)
    assert result["roll"][0] == pytest.approx(1.1, abs=0.02)


def test_silence_leaves_the_clips_own_head_pose_unchanged():
    own = pose(pitch=-4.0, yaw=10.0, roll=1.0)
    rest = pose(pitch=1.0, yaw=-1.0, roll=0.0)
    result = face.head_drive(own, rest, rest, 1.0, 1.0)
    assert result["pitch"][0] == pytest.approx(-4.0, abs=0.02)
    assert result["yaw"][0] == pytest.approx(10.0, abs=0.02)


def test_head_displacement_is_scaled_by_the_voice_level_and_gain():
    own, rest, voice = pose(pitch=0.0), pose(pitch=0.0), pose(pitch=4.0)
    assert face.head_drive(own, voice, rest, 0.5, 1.0)["pitch"][0] == pytest.approx(2.0, abs=0.02)
    assert face.head_drive(own, voice, rest, 1.0, 0.25)["pitch"][0] == pytest.approx(1.0, abs=0.02)
    assert face.head_drive(own, voice, rest, 0.0, 1.0)["pitch"][0] == pytest.approx(0.0, abs=0.02)


def test_head_position_and_scale_move_by_the_audio_displacement():
    own = pose(t=(0.1, -0.2, 0.0), scale=1.5)
    rest = pose(t=(0.0, 0.0, 0.0), scale=1.0)
    voice = pose(t=(0.02, 0.03, 0.0), scale=1.04)
    result = face.head_drive(own, voice, rest, 1.0, 1.0)
    np.testing.assert_allclose(result["t"], [[0.12, -0.17, 0.0]], atol=1e-6)
    np.testing.assert_allclose(result["scale"], [[1.54]], atol=1e-6)


def test_head_pose_is_returned_as_degrees_for_ditto_to_use_directly():
    result = face.head_drive(pose(), pose(), pose(), 1.0, 1.0)
    for key in ("pitch", "yaw", "roll"):
        assert result[key].shape == (1,) and result[key].dtype == np.float32
