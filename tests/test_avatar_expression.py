import numpy as np
import pytest

from trendcoffee.avatar_expression import calibrate_expression, closed_lip_shape, compress_lips


def test_large_vertical_opening_is_bounded_without_narrowing_the_smile():
    source = np.full((1, 63), 0.02, np.float32)
    rest = np.full((1, 63), 0.1, np.float32)
    delta = np.arange(63, dtype=np.float32).reshape(21, 3) * 0.0001
    lips = [6, 12, 14, 17, 19, 20]
    delta[lips, 1] = np.array([-0.06, -0.03, -0.02, 0.02, 0.03, 0.06]) + 0.01
    speech = rest + delta.reshape(1, 63)
    original = speech.copy()
    actual = calibrate_expression(speech, rest, source, opening_limit=0.035)
    displacement = (actual - source).reshape(21, 3)
    vertical = displacement[lips, 1]
    assert np.linalg.norm(vertical - vertical.mean()) < 0.035
    assert vertical.mean() == pytest.approx(delta[lips, 1].mean(), abs=1e-7)
    np.testing.assert_allclose(displacement[:, [0, 2]], delta[:, [0, 2]], atol=1e-8)
    other = [i for i in range(21) if i not in lips]
    np.testing.assert_allclose(displacement[other], delta[other], atol=1e-8)
    np.testing.assert_array_equal(speech, original)


def test_small_speech_and_rest_remain_uncompressed():
    source = np.full((1, 63), 0.02, np.float32)
    rest = np.full((1, 63), 0.1, np.float32)
    speech = rest.copy()
    speech[0, 19] += 0.005
    expected = calibrate_expression(speech, rest, source)
    np.testing.assert_array_equal(
        calibrate_expression(speech, rest, source, opening_limit=0.035), expected
    )
    np.testing.assert_array_equal(
        calibrate_expression(rest, rest, source, opening_limit=0.035), source
    )


@pytest.mark.parametrize("limit", [-1, float("nan"), float("inf")])
def test_invalid_opening_limit_is_rejected(limit):
    pose = np.zeros((1, 63), np.float32)
    with pytest.raises(ValueError, match="opening"):
        calibrate_expression(pose, pose, pose, opening_limit=limit)


def lip_expression(top, bottom):
    points = np.zeros((21, 3), np.float32)
    points[[6, 12, 14], 1] = top
    points[[17, 19, 20], 1] = bottom
    return points.reshape(1, 63)


def test_closed_lip_shape_is_the_most_typical_of_the_closest_source_frames():
    frames = [lip_expression(-spread, spread) for spread in (0.5, 0.1, 0.4, 0.3, 0.2, 0.6)]
    shape = closed_lip_shape(frames)
    np.testing.assert_allclose(shape[:, 1], [-0.3, -0.3, -0.3, 0.3, 0.3, 0.3])


def test_lip_compression_scales_separation_around_the_closed_shape():
    rest = np.array([-0.1, -0.1, -0.1, 0.1, 0.1, 0.1], np.float32)
    result = compress_lips(lip_expression(-0.5, 0.5), rest, 0.5).reshape(21, 3)
    np.testing.assert_allclose(result[[6, 12, 14], 1], -0.3)
    np.testing.assert_allclose(result[[17, 19, 20], 1], 0.3)


def test_lip_compression_keeps_shared_vertical_lip_motion_and_other_points():
    rest = np.array([-0.1, -0.1, -0.1, 0.1, 0.1, 0.1], np.float32)
    source = lip_expression(0.1, 0.3)
    source[0, 0] = 0.7
    result = compress_lips(source, rest, 0.5).reshape(21, 3)
    assert result[[6, 12, 14, 17, 19, 20], 1].mean() == pytest.approx(0.2)
    assert result[0, 0] == pytest.approx(0.7)
