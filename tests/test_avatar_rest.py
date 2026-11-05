"""The standing clip shown while Trend is not speaking, and the dissolve into and out of it."""

import cv2
import numpy as np
import pytest

from trendcoffee.avatar_rest import CrossFade, load_rest_clip, rest_frame_index


def solid(value):
    return np.full((4, 6, 3), value, np.uint8)


def write_video(path, size, bgr, frames=3, fps=12):
    width, height = size
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for _ in range(frames):
        writer.write(np.full((height, width, 3), bgr, np.uint8))
    writer.release()


def test_rest_clip_plays_forward_then_backward_without_a_jump():
    indexes = [rest_frame_index(step / 10, 10, 4) for step in range(14)]
    assert indexes == [0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 1, 0, 1]


def test_a_single_frame_rest_clip_stays_on_that_frame():
    assert rest_frame_index(5.0, 24, 1) == 0


def test_rest_clip_is_loaded_as_rgb_at_the_engine_frame_size(tmp_path):
    path = tmp_path / "rest.mp4"
    write_video(path, (64, 48), (0, 0, 255))  # Pure red in OpenCV's BGR order.
    frames, fps = load_rest_clip(path, (32, 20))
    assert len(frames) == 3 and fps == pytest.approx(12)
    assert frames[0].shape == (32, 20, 3) and frames[0].dtype == np.uint8
    red, green, blue = frames[0].reshape(-1, 3).mean(0)
    assert red > 200 and green < 60 and blue < 60


def test_a_missing_rest_clip_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="rest"):
        load_rest_clip(tmp_path / "missing.mp4", (32, 20))


def test_first_frame_and_unchanged_mode_pass_through():
    fade = CrossFade(0.5)
    np.testing.assert_array_equal(fade.apply(solid(10), "rest", 1.0), solid(10))
    np.testing.assert_array_equal(fade.apply(solid(20), "rest", 1.1), solid(20))


def test_a_change_of_mode_dissolves_from_the_last_frame_shown():
    fade = CrossFade(0.5)
    fade.apply(solid(0), "rest", 1.0)
    start = fade.apply(solid(200), "face", 2.0)
    middle = fade.apply(solid(200), "face", 2.25)
    end = fade.apply(solid(200), "face", 2.5)
    assert start.mean() == 0
    assert middle.mean() == pytest.approx(100, abs=1)
    np.testing.assert_array_equal(end, solid(200))
    np.testing.assert_array_equal(fade.apply(solid(200), "face", 3.0), solid(200))


def test_cleared_fade_forgets_the_previous_frame():
    fade = CrossFade(0.5)
    fade.apply(solid(0), "rest", 1.0)
    fade.clear()
    np.testing.assert_array_equal(fade.apply(solid(200), "face", 1.1), solid(200))


def test_fade_never_modifies_the_frames_it_is_given():
    fade = CrossFade(0.5)
    first, second = solid(0), solid(200)
    fade.apply(first, "rest", 1.0)
    fade.apply(second, "face", 2.0)
    fade.apply(second, "face", 2.25)
    assert first.mean() == 0 and second.mean() == 200


def test_a_zero_length_fade_is_a_clean_cut_with_no_double_image():
    fade = CrossFade(0.0)
    fade.apply(solid(0), "rest", 1.0)
    np.testing.assert_array_equal(fade.apply(solid(200), "face", 1.0), solid(200))
    np.testing.assert_array_equal(fade.apply(solid(0), "rest", 1.01), solid(0))
