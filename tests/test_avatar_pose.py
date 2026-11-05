"""Motion timing tests use numeric poses so no model or GPU is required."""

import numpy as np
import pytest

from trendcoffee.avatar_pose import PoseTimeline


def poses(values):
    return [{"exp": np.array([[value]], dtype=np.float32)} for value in values]


def test_model_window_retains_intermediate_poses_at_audio_timestamps():
    timeline = PoseTimeline()
    timeline.append(poses(range(80)), end_sample=51200)
    assert len(timeline) == 80
    # Last model frame follows the 80ms Hubert right context; 40ms separates poses.
    assert timeline.at(49280).drive["exp"].item() == 78
    assert timeline.at(49920).drive["exp"].item() == 79
    assert timeline.at(49600).drive["exp"].item() == pytest.approx(78.5)


def test_pose_selection_does_not_extrapolate_past_received_motion():
    timeline = PoseTimeline()
    timeline.append(poses([10, 20, 30, 40, 50]), end_sample=4480)
    assert timeline.at(50000).sample == 3200
    assert timeline.at(50000).drive["exp"].item() == 50


def test_overlapping_predictions_fuse_without_rewriting_older_history():
    timeline = PoseTimeline()
    timeline.append(poses([0] * 80), end_sample=51200)
    timeline.append(poses([10] * 80), end_sample=54400)
    assert len(timeline) == 85
    assert timeline.at(46720).drive["exp"].item() == 0
    assert timeline.at(48000).drive["exp"].item() == pytest.approx(2.5)
    assert timeline.at(49920).drive["exp"].item() == 10
    assert timeline.at(50560).drive["exp"].item() == 10


def test_pose_retention_and_reset_are_bounded():
    timeline = PoseTimeline(capacity=80)
    for endpoint in range(51200, 115201, 3200):
        timeline.append(poses(range(80)), end_sample=endpoint)
    assert len(timeline) == 80
    assert timeline.dropped > 0
    timeline.clear()
    assert len(timeline) == 0
    assert timeline.at(115200) is None


def test_pose_buffer_owns_arrays_instead_of_mutable_prediction_storage():
    timeline = PoseTimeline()
    predicted = poses([1, 2])
    timeline.append(predicted, end_sample=2560)
    predicted[-1]["exp"][:] = 99
    assert timeline.at(1280).drive["exp"].item() == 2
