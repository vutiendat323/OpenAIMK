import pytest

from trendcoffee.avatar_motion import MotionController


def controller():
    return MotionController(talking=(0, 10), wave=(10, 16), idle=(10, 12), smile=(14, 16))


def test_wave_is_one_shot_and_can_lipsync_while_speaking():
    motion = controller()
    assert motion.action("wave")
    assert motion.frames(4, speaking=True) == [10, 11, 12, 13]
    assert motion.frames(4, speaking=True) == [14, 15, 0, 1]
    assert motion.frames(2, speaking=False) == [10, 11]


def test_interrupt_cancels_action_and_returns_to_idle():
    motion = controller()
    motion.action("wave")
    motion.frames(3, speaking=True)
    motion.reset(2)
    assert motion.epoch == 2
    assert motion.frames(4, speaking=False) == [10, 11, 11, 10]
    assert motion.frames(2, speaking=True) == [0, 1]


def test_smile_is_independently_controlled_and_unknown_action_is_ignored():
    motion = controller()
    assert not motion.action("dance")
    assert motion.action("smile")
    assert motion.frames(3, speaking=False) == [14, 15, 10]
    assert motion.action("idle")
    assert motion.frames(2, speaking=False) == [10, 11]


def test_repeated_actions_do_not_leak_into_the_next_guest():
    motion = controller()
    for epoch in range(1, 100):
        motion.action("wave")
        motion.frames(2, speaking=True)
        motion.reset(epoch)
        assert motion.frames(2, speaking=False) == [10, 11]
        assert motion.frames(3, speaking=True) == [0, 1, 2]


def test_neutral_clip_continues_without_head_jump_when_speech_starts_or_stops():
    motion = MotionController(talking=(0, 10), wave=(10, 16), idle=(0, 10), smile=(14, 16))
    assert motion.frames(3, speaking=False) == [0, 1, 2]
    assert motion.frames(4, speaking=True) == [3, 4, 5, 6]
    assert motion.frames(3, speaking=False) == [7, 8, 9]
    assert motion.frames(3, speaking=True) == [9, 8, 7]


def test_manifest_uses_neutral_source_for_idle_and_keeps_separate_gestures():
    motion = MotionController.from_manifest(
        {"idle_source": "talking", "idle_range": [0, 10], "smile_range": [4, 6]},
        talking_count=10,
        wave_count=6,
    )
    assert motion.frames(3, speaking=False) == [0, 1, 2]
    assert motion.action("wave")
    assert motion.frames(7, speaking=True) == [10, 11, 12, 13, 14, 15, 0]
    assert motion.action("smile")
    assert motion.frames(3, speaking=False) == [14, 15, 0]


def test_legacy_manifest_still_uses_wave_source_for_idle():
    motion = MotionController.from_manifest(
        {"idle_range": [0, 2], "smile_range": [4, 6]}, talking_count=10, wave_count=6
    )
    assert motion.frames(3, speaking=False) == [10, 11, 11]


@pytest.mark.parametrize(
    "changes", [{"idle_source": "missing"}, {"idle_range": [0, 11]}, {"smile_range": [4, 7]}]
)
def test_invalid_source_ranges_are_rejected_before_rendering(changes):
    with pytest.raises(ValueError):
        MotionController.from_manifest(
            {"idle_source": "talking", "idle_range": [0, 10], "smile_range": [4, 6], **changes},
            talking_count=10,
            wave_count=6,
        )
