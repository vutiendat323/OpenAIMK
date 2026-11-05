from scripts.prepare_trend_avatar import build_manifest
from trendcoffee.avatar_motion import MotionController


def test_neutral_asset_import_selects_full_idle_clip_without_changing_gestures():
    manifest = build_manifest("neutral", 250, "wave", 149, width=720, idle_source="talking")
    motion = MotionController.from_manifest(manifest, talking_count=250, wave_count=149)
    assert manifest["avatar_id"] == "neutral"
    assert motion.frames(25, speaking=False) == list(range(25))
    assert motion.frames(3, speaking=True) == [25, 26, 27]
    motion.action("wave")
    assert motion.frames(2, speaking=True) == [250, 251]
    motion.action("smile")
    assert motion.frames(2, speaking=False) == [364, 365]


def test_short_wave_clip_produces_valid_idle_and_smile_ranges():
    manifest = build_manifest("speech", 10, "wave", 4, width=720, idle_source="wave")
    motion = MotionController.from_manifest(manifest, talking_count=10, wave_count=4)
    assert motion.frames(6, speaking=False) == [10, 11, 12, 13, 13, 12]
    motion.action("smile")
    assert motion.frames(4, speaking=False) == [10, 11, 12, 13]
