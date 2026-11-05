"""CPU tests for bounded streaming scheduling and interruption safety."""

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.ditto_realtime import DittoEngine
from trendcoffee.avatar_rest import CrossFade


def engine():
    instance = DittoEngine(Path("source.mp4"), Path("."))
    instance._idle_frames = [np.zeros((4, 4, 3), dtype=np.uint8)]
    instance._ready = True
    instance.reset(1)
    return instance


def test_audio_is_bounded_and_newest_samples_survive():
    instance = engine()
    for index in range(400):
        instance.push(1, np.full(320, index, dtype=np.float32))
    audio, end = instance._audio_snapshot()
    assert len(audio) == instance.AUDIO_CAPACITY
    assert audio[-1] == 399
    assert end == 400 * 320
    assert instance.status()["audio_buffer_samples"] <= instance.AUDIO_CAPACITY


def test_reset_rejects_old_audio_and_inflight_gpu_frame():
    instance = engine()
    old = np.ones((4, 4, 3), dtype=np.uint8)
    instance.push(1, np.ones(320, dtype=np.float32))
    instance.reset(2)
    instance.push(1, np.ones(320, dtype=np.float32))
    assert not instance._publish(1, old)
    epoch, frame, _sequence = instance.latest_frame()
    assert epoch == 2
    assert not frame.any()
    assert instance.status()["audio_buffer_samples"] == 0


def test_frame_slot_replaces_instead_of_queuing():
    instance = engine()
    for index in range(100):
        instance._publish(1, np.full((4, 4, 3), index, dtype=np.uint8))
    assert instance.latest_frame()[1][0, 0, 0] == 99
    assert instance.status()["frame_backlog"] == 1


def test_body_keeps_advancing_while_mouth_inference_or_pcm_is_paused(monkeypatch):
    instance = engine()
    instance._idle_frames = [np.full((4, 4, 3), value, np.uint8) for value in range(24)]
    instance._origin = 10.0
    instance._source_fps = 24
    instance._audio_end, instance._last_push = 16000, 8.0
    seen = []
    for tick in range(24):
        now = 10.001 + tick / 24
        assert instance._present_at(now)
        seen.append(int(instance.latest_frame()[1][0, 0, 0]))
    assert len(set(seen)) == 24


def test_presentation_rejects_retired_guest_mouth_and_preserves_source():
    instance = engine()
    source = np.full((512, 512, 3), (120, 150, 170), np.uint8)
    instance._idle_frames = [source]
    instance._info = {
        "img_rgb_lst": [source],
        "M_c2o_lst": [np.eye(3)],
        "mouth_regions": [(256, 330, 90, 65)],
    }
    face = np.full((512, 512, 3), 220, np.float32)
    assert instance._store_mouth(1, face, "idle", (256, 330, 90, 65))
    instance._present_at(time.monotonic())
    result = instance.latest_frame()[1]
    np.testing.assert_array_equal(result[:250], source[:250])
    assert (result[315:345, 240:272] == 220).all()
    instance.reset(2)
    assert not instance._store_mouth(1, face, "idle", (256, 330, 90, 65))
    instance._present_at(time.monotonic())
    np.testing.assert_array_equal(instance.latest_frame()[1], source)


def test_speech_end_restores_relaxed_source_smile_even_with_silent_pcm(monkeypatch):
    instance = engine()
    source = np.full((512, 512, 3), (120, 150, 170), np.uint8)
    instance._idle_frames = [source]
    instance._info = {"M_c2o_lst": [np.eye(3)], "mouth_regions": [(256, 330, 90, 65)]}
    now = [10.0]
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: now[0])
    instance.push(1, np.full(320, 0.1, np.float32))
    instance._store_mouth(1, np.full((512, 512, 3), 220, np.float32), "idle", (256, 330, 90, 65))
    instance._present_at(10.0)
    assert (instance.latest_frame()[1][315:345, 240:272] == 220).all()
    now[0] = 10.4
    instance.push(1, np.zeros(320, np.float32))
    # Continually arriving silent RTC packets must not preserve pursed model lips.
    instance._present_at(now[0])
    np.testing.assert_array_equal(instance.latest_frame()[1], source)
    now[0] = 10.5
    instance.push(1, np.full(320, 0.1, np.float32))
    # A resumed utterance must wait for its fresh texture instead of flashing
    # the previous utterance's final clamped mouth.
    instance._present_at(now[0])
    np.testing.assert_array_equal(instance.latest_frame()[1], source)
    instance._store_mouth(1, np.full((512, 512, 3), 230, np.float32), "idle", (256, 330, 90, 65))
    instance._present_at(now[0])
    assert (instance.latest_frame()[1][315:345, 240:272] == 230).all()


def full_face_engine():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face")
    pasted = []

    def putback(frame, face, matrix):
        assert face.dtype == np.float32 and frame.dtype == np.uint8
        pasted.append((int(frame[0, 0, 0]), int(face[0, 0, 0]), matrix.copy()))
        return np.full_like(frame, int(face[0, 0, 0]))

    instance._sdk = SimpleNamespace(putback=putback)
    instance._idle_frames = [np.full((512, 512, 3), value, np.uint8) for value in range(48)]
    instance._info = {
        "M_c2o_lst": [np.eye(3) * (1 + value) for value in range(48)],
        "mouth_regions": [(256, 330, 90, 65)] * 48,
    }
    instance._origin = 0.0
    instance._source_fps = 24
    return instance, pasted


def test_full_face_is_pasted_on_the_exact_source_frame_it_was_generated_for():
    instance, pasted = full_face_engine()
    instance.reset(1)
    instance._origin = time.monotonic() - 1.0
    instance.push(1, np.full(320, 0.1, np.float32))
    face = np.full((512, 512, 3), 220, np.float32)
    instance._store_mouth(1, face, "idle", (256, 330, 90, 65), index=7)
    instance._present_at(time.monotonic())  # The clock says about frame 24; this face is 7.
    assert pasted[-1][:2] == (7, 220)
    np.testing.assert_array_equal(pasted[-1][2], instance._info["M_c2o_lst"][7])
    assert (instance.latest_frame()[1] == 220).all()


def test_full_face_never_blends_two_generated_faces():
    instance, pasted = full_face_engine()
    instance.reset(1)
    instance.push(1, np.full(320, 0.1, np.float32))
    first = np.full((512, 512, 3), 100, np.float32)
    second = np.full((512, 512, 3), 200, np.float32)
    instance._store_mouth(1, first, "idle", (256, 330, 90, 65), index=3)
    instance._present_at(time.monotonic())
    instance._store_mouth(1, second, "idle", (256, 330, 90, 65), index=4)
    instance._present_at(time.monotonic())
    assert pasted[-1][:2] == (4, 200)
    assert instance.status()["interpolated_mouth_frames"] == 0


def test_full_face_silence_uses_the_prepared_closed_face_for_the_current_frame():
    instance, pasted = full_face_engine()
    instance._rest_faces = [np.full((512, 512, 3), 150 + i, np.uint8) for i in range(48)]
    instance.reset(1)
    instance._clip_position = 12.0
    instance._present_at(0.5)
    assert pasted[-1][:2] == (12, 162)


def test_full_face_clip_runs_at_one_steady_rate_in_speech_and_silence():
    instance, _ = full_face_engine()
    instance._source_frame(100.0)
    assert instance._source_frame(102.0)[0] == int(2 * 24 * instance.STEADY_CLIP_RATE)
    before = instance._clip_position
    instance._last_voiced_at = 102.0
    instance._source_frame(103.0)
    assert instance._clip_position - before == pytest.approx(24 * instance.STEADY_CLIP_RATE)


def test_blinks_of_the_clip_are_played_faster_so_closed_eyes_do_not_linger():
    instance, _ = full_face_engine()
    instance._blink_frames = [10 <= index <= 15 for index in range(48)]
    instance._source_frame(100.0)

    def seconds_through(start, end):
        instance._clip_position, instance._clip_at = float(start), 100.0
        elapsed = 0.0
        while instance._clip_position < end and elapsed < 5:
            elapsed += 0.01
            instance._source_frame(100.0 + elapsed)
        return elapsed

    open_time = seconds_through(0, 6)
    blink_time = seconds_through(10, 16)
    assert blink_time < open_time * 0.6


def test_silence_after_speech_never_jumps_the_clip():
    instance, _ = full_face_engine()
    instance._last_voiced_at = 100.0
    instance._source_frame(100.0)
    speaking = instance._source_frame(100.25)[0]
    resting = instance._source_frame(100.32)[0]  # Past the rest delay.
    assert 0 <= resting - speaking <= 2


def test_resting_continues_from_the_frame_shown_during_speech():
    instance, pasted = full_face_engine()
    instance._rest_faces = [np.full((512, 512, 3), 150 + i, np.uint8) for i in range(48)]
    instance.reset(1)
    instance.push(1, np.full(320, 0.1, np.float32))
    instance._clip_position, instance._clip_at = 10.0, time.monotonic()
    face = np.full((512, 512, 3), 220, np.float32)
    instance._store_mouth(1, face, "idle", (256, 330, 90, 65), index=7)
    instance._present_at(time.monotonic())
    instance._last_voiced_at = time.monotonic() - 5
    instance._present_at(time.monotonic())
    assert pasted[-1][0] == 7, "The clock was ahead; the body must not jump forward"
    assert 7 <= instance._clip_position < 8


def test_closed_source_mouth_composite_uses_steady_motion():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="mouth", closed_source=True)
    source_pose = np.zeros((1, 5), np.float32)
    instance._sdk = SimpleNamespace(audio2motion=SimpleNamespace(s_kp_cond=source_pose))
    instance._latest_prediction = np.ones((1, 8, 5), np.float32)
    instance._chain_motion(4)
    assert instance._motion_start() is not source_pose
    instance._source_fps, instance._idle_frames = 24, [None] * 480
    instance._source_frame(100.0)
    assert instance._source_frame(102.0)[0] == int(2 * 24 * instance.STEADY_CLIP_RATE)


def test_presentation_lead_can_be_set_from_the_profile():
    instance = DittoEngine(Path("source.mp4"), Path("."), presentation_lead_ms=360)
    assert instance.status()["presentation_lead_ms"] == 360


def test_mouth_composite_keeps_the_original_clip_clock():
    instance = engine()
    instance._idle_frames = [None] * 480
    instance._origin, instance._source_fps = 0.0, 24
    assert instance._source_frame(2.0)[0] == 48


def test_full_face_rejects_the_partial_mouth_decoder():
    with pytest.raises(ValueError):
        DittoEngine(
            Path("source.mp4"),
            Path("."),
            composite="full-face",
            renderer_backend="tensorrt-mouth",
        )


def chained_engine():
    instance, _ = full_face_engine()
    source_pose = np.zeros((1, 5), np.float32)
    instance._sdk.audio2motion = SimpleNamespace(s_kp_cond=source_pose)
    return instance, source_pose


def test_full_face_motion_continues_from_the_pose_before_the_next_window():
    instance, source_pose = chained_engine()
    assert instance._motion_start() is source_pose
    instance._latest_prediction = np.arange(40, dtype=np.float16).reshape(1, 8, 5)
    instance._chain_motion(4)
    start = instance._motion_start()
    np.testing.assert_array_equal(start, [[15, 16, 17, 18, 19]])
    # Compiled sampling is keyed on dtype; a changed one recompiles during speech.
    assert start.dtype == source_pose.dtype


def test_guest_change_and_silence_restart_motion_from_the_source_pose():
    instance, source_pose = chained_engine()
    instance._latest_prediction = np.ones((1, 8, 5), np.float32)
    instance._chain_motion(4)
    instance.reset(2)
    assert instance._motion_start() is source_pose
    instance._chain_motion(4)
    instance._clear_motion_chain()
    assert instance._motion_start() is source_pose


def test_mouth_composite_keeps_motion_on_the_fixed_source_pose():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="mouth")
    source_pose = np.zeros((1, 5), np.float32)
    instance._sdk = SimpleNamespace(audio2motion=SimpleNamespace(s_kp_cond=source_pose))
    instance._latest_prediction = np.ones((1, 8, 5), np.float32)
    instance._chain_motion(4)
    assert instance._motion_start() is source_pose


def rest_engine():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face")
    seen = {}

    class Stitch:
        use_d_keys = ("exp",)

        def __call__(self, source_info, drive):
            seen["source"] = source_info["name"]
            seen["keys"] = self.use_d_keys
            seen["pose"] = drive["yaw"].copy()
            return "source-kp", "driving-kp"

    def renderer(features, source, driving):
        seen["features"] = features
        value = {"features-zero": 7.0, "features-one": 9.0}[features]
        return np.full((512, 512, 3), value, np.float32)

    renderer.frame_ms = []
    instance._renderer = renderer
    instance._sdk = SimpleNamespace(motion_stitch=Stitch())
    keys = ("pitch", "yaw", "roll", "t", "scale")
    instance._neutral_drive = {
        **{key: np.zeros((1, 3), np.float32) for key in keys},
        "exp": np.zeros((1, 63), np.float32),
    }
    infos = [
        {
            "name": name,
            **{key: np.full((1, 3), value, np.float32) for key in keys},
            "exp": np.full((1, 63), value, np.float32),
        }
        for name, value in (("zero", 0.0), ("one", 1.0))
    ]
    instance._info = {
        "x_s_info_lst": infos,
        "f_s_lst": ["features-zero", "features-one"],
        "mouth_expression_anchors": np.zeros((2, 1, 63), np.float32),
        "mouth_regions": [(256.0, 330.0, 90.0, 65.0)] * 2,
    }
    return instance, seen


def test_rest_face_takes_appearance_from_the_calm_frame_and_pose_from_the_current_one():
    instance, seen = rest_engine()
    face = instance._rest_face(1, 0)
    assert seen["source"] == "zero" and seen["features"] == "features-zero"
    np.testing.assert_array_equal(seen["pose"], np.ones((1, 3), np.float32))
    assert {"pitch", "yaw", "roll", "t", "scale"} <= set(seen["keys"])
    assert instance._sdk.motion_stitch.use_d_keys == ("exp",), "The stitcher setting is restored"
    assert face.dtype == np.float32
    assert (face[335, 256] == 7).all(), "The mouth comes from the calm frame"
    assert (face[500, 256] == 9).all(), "Neck and collar stay those of the current frame"
    assert (face[100, 256] == 9).all(), "Eyes and hair stay those of the current frame"


def test_calm_frame_rest_face_is_just_its_own_render():
    instance, seen = rest_engine()
    face = instance._rest_face(0, 0)
    assert (face == 7).all()


def test_rest_face_restores_the_stitcher_even_when_rendering_fails():
    instance, _ = rest_engine()
    instance._renderer = lambda *args: (_ for _ in ()).throw(RuntimeError("gpu"))
    with pytest.raises(RuntimeError):
        instance._rest_face(0, 0)
    assert instance._sdk.motion_stitch.use_d_keys == ("exp",)


def test_reset_during_cpu_composition_rejects_the_finished_old_image(monkeypatch):
    from scripts import ditto_realtime

    instance = engine()
    source = np.zeros((512, 512, 3), np.uint8)
    instance._idle_frames = [source]
    instance._info = {"M_c2o_lst": [np.eye(3)], "mouth_regions": [(256, 330, 90, 65)]}
    instance._store_mouth(1, np.full_like(source, 220), "idle", (256, 330, 90, 65))

    def retired(*args, **kwargs):
        instance.reset(2)
        return np.full_like(source, 220)

    monkeypatch.setattr(ditto_realtime, "composite_mouth", retired)
    assert not instance._present_at(time.monotonic())
    assert instance.latest_frame()[0] == 2
    assert not instance.latest_frame()[1].any()


def test_wave_never_reuses_the_previous_idle_mouth():
    instance = engine()
    instance._wave_frames = [np.full((4, 4, 3), 40, np.uint8)] * 24
    instance._store_mouth(1, np.full((512, 512, 3), 220, np.float32), "idle", (256, 330, 90, 65))
    instance.action("wave")
    instance._present_at(time.monotonic())
    assert (instance.latest_frame()[1] == 40).all()


def test_wave_is_one_shot_and_reset_cancels_it():
    instance = engine()
    instance._wave_frames = [np.full((4, 4, 3), 40, dtype=np.uint8)] * 3
    assert not instance.action("unknown")
    assert instance.action("wave")
    assert instance._source_frame(time.monotonic())[1] == "wave"
    assert instance._source_frame(time.monotonic() + 1)[1] == "idle"
    instance.action("wave")
    instance.reset(2)
    assert instance._source_frame(time.monotonic())[1] == "idle"


def test_render_clock_skips_missed_deadlines():
    instance = engine()
    # After slow GPU work schedule in the future, never replay overdue frames.
    instance._next_render = 1.0
    assert instance._advance_render_clock(2.0) >= 2.0
    assert instance._next_render <= 2.0 + 1 / instance.TARGET_FPS


def test_render_time_counts_towards_frame_period():
    instance = engine()
    instance._next_render = 1.0
    # A 70ms inference must leave about 13ms, rather than another full 83ms.
    deadline = instance._advance_render_clock(1.07)
    assert 0 <= deadline - 1.07 < 0.02


def motion(values):
    return [{"exp": np.array([[value]], dtype=np.float32)} for value in values]


def test_speech_pose_uses_audio_time_instead_of_holding_last_window_pose():
    instance = engine()
    instance._audio_started_at = 10.0
    assert instance._accept_motion(1, motion(range(80)), 51200)
    # At3.20s with160ms presentation lead, target audio time is3.04s.
    selected = instance._pose_at(1, 13.20)
    assert selected.sample == pytest.approx(48640)
    assert selected.drive["exp"].item() == pytest.approx(77)


def test_reset_discards_inflight_motion_and_previous_guest_pose():
    instance = engine()
    instance._audio_started_at = 10.0
    instance._accept_motion(1, motion([42] * 80), 51200)
    instance._drive = motion([42])[0]
    instance.reset(2)
    assert not instance._accept_motion(1, motion([99] * 80), 54400)
    assert instance._pose_at(2, 13.2) is None
    assert instance._drive is None
    assert instance.status()["pose_buffer_frames"] == 0
    assert instance.status()["dropped_stale_motion"] == 1


def test_short_pcm_gap_preserves_speech_source_but_eventually_goes_neutral(monkeypatch):
    instance = engine()
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: 10.0)
    instance.push(1, np.ones(320, dtype=np.float32))
    assert instance._speech_active(10.4)
    assert not instance._speech_active(10.8)


def test_resuming_after_long_packet_gap_reanchors_bounded_audio_clock(monkeypatch):
    instance = engine()
    now = [10.0]
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: now[0])
    for _ in range(10):
        instance.push(1, np.ones(320, dtype=np.float32))
        now[0] += 0.02
    now[0] = 12.0
    instance.push(1, np.ones(320, dtype=np.float32))
    assert instance._audio_started_at == pytest.approx(11.78)
    assert instance.status()["audio_clock_reanchors"] == 1


def test_gpu_budget_leaves_measured_work_time_for_other_workers():
    instance = DittoEngine(Path("source.mp4"), Path("."), gpu_budget=0.5)
    instance._next_render = 1.0
    # 80ms of GPU-path wall time requires another80ms free at a50% budget.
    assert instance._advance_render_clock(1.08, work_seconds=0.08) == pytest.approx(1.16)
    assert instance.status()["gpu_budget"] == 0.5


@pytest.mark.parametrize("budget", [0, -0.1, 1.1, float("nan")])
def test_invalid_gpu_budget_is_rejected(budget):
    with pytest.raises(ValueError):
        DittoEngine(Path("source.mp4"), Path("."), gpu_budget=budget)


def test_motion_decoder_preserves_every_predicted_pose(monkeypatch):
    instance = engine()
    predicted = np.arange(80, dtype=np.float32).reshape(1, 80, 1)

    class Converter:
        @staticmethod
        def cvt_fmt(sequence):
            return motion(sequence[0, :, 0])

    class SDK:
        audio2motion = Converter()

    instance._sdk = SDK()
    monkeypatch.setattr(instance, "_predict_motion", lambda features: predicted, raising=False)
    trajectory = instance._motion(np.zeros((80, 1), np.float32))
    assert len(trajectory) == 80
    assert trajectory[0]["exp"].item() == 0
    assert trajectory[-1]["exp"].item() == 79


def test_upstream_stitch_cannot_mutate_buffered_pose():
    instance = engine()
    drive = motion([0.25])[0]

    def stitch(source, driving):
        # The real upstream stitch inserts source keys into the supplied dict.
        driving["kp"] = np.zeros((1, 63), np.float32)
        driving["exp"][:] = 99
        return None, None

    instance._sdk = SimpleNamespace(motion_stitch=stitch, putback=lambda *args: args[1])
    instance._info = {
        key: [None] for key in ("x_s_info_lst", "f_s_lst", "img_rgb_lst", "M_c2o_lst")
    }
    instance._info.update(
        img_rgb_lst=[np.zeros((4, 4, 3), np.uint8)],
        M_c2o_lst=[np.eye(3)],
        mouth_regions=[(256, 330, 90, 65)],
    )
    instance._renderer = lambda *args: np.zeros((4, 4, 3), np.uint8)
    instance._renderer.frame_ms = []
    instance._render(0, drive)
    assert set(drive) == {"exp"}
    assert drive["exp"].item() == 0.25


def test_render_does_not_regenerate_source_eyes_and_skin():
    instance = engine()
    source = np.full((512, 512, 3), (120, 150, 170), np.uint8)
    instance._info = {
        "x_s_info_lst": [None],
        "f_s_lst": [None],
        "img_rgb_lst": [source],
        "M_c2o_lst": [np.eye(3)],
        "mouth_regions": [(256, 330, 90, 65)],
    }
    instance._sdk = SimpleNamespace(
        motion_stitch=lambda *args: (None, None),
        putback=lambda *args: np.full_like(source, 220),
    )
    instance._renderer = lambda *args: np.full((512, 512, 3), 220, np.float32)
    instance._renderer.frame_ms = []
    instance._idle_frames = [source]
    face = instance._render(0, motion([0.25])[0])
    instance._store_mouth(1, face, "idle", (256, 330, 90, 65))
    instance._present_at(time.monotonic())
    result = instance.latest_frame()[1]
    np.testing.assert_array_equal(result[:250], source[:250])
    assert (result[315:345, 240:272] == 220).all()


def test_render_fps_can_be_measured_at_eight_without_changing_default(monkeypatch):
    monkeypatch.setenv("DITTO_RENDER_FPS", "8")
    instance = engine()
    instance._next_render = 1.0
    assert instance._advance_render_clock(1.08) == pytest.approx(1.125)
    assert instance.status()["target_fps"] == 8


def test_neural_render_target_is_independent_of_source_presentation_rate():
    instance = DittoEngine(Path("source.mp4"), Path("."), render_fps=20)
    assert instance.status()["target_fps"] == 20
    assert instance.status()["presentation_fps"] == 24


def test_render_removes_predicted_rest_bias_before_driving_source_lips():
    instance = engine()
    source_exp = np.full((1, 63), 0.02, np.float32)
    silent_exp = np.full((1, 63), 0.10, np.float32)
    speech_exp = silent_exp.copy()
    speech_exp[0, 18:21] += [0.01, 0.04, -0.01]
    instance._neutral_drive = {"exp": silent_exp}
    instance._info = {"x_s_info_lst": [{"exp": source_exp}], "f_s_lst": [None]}
    received = []

    def stitch(source, drive):
        received.append(drive["exp"].copy())
        return None, None

    instance._sdk = SimpleNamespace(motion_stitch=stitch)
    instance._renderer = lambda *args: np.zeros((512, 512, 3), np.float32)
    instance._renderer.frame_ms = []
    original = speech_exp.copy()
    instance._render(0, {"exp": speech_exp})
    np.testing.assert_allclose(received[0], source_exp + (speech_exp - silent_exp), atol=1e-8)
    np.testing.assert_array_equal(speech_exp, original)


def test_render_limits_excessive_opening_before_the_neural_warp():
    instance = DittoEngine(Path("source.mp4"), Path("."), lip_opening_limit=0.035)
    source = np.full((1, 63), 0.02, np.float32)
    rest = np.full((1, 63), 0.10, np.float32)
    speech = rest.copy()
    lips = [6, 12, 14, 17, 19, 20]
    speech.reshape(21, 3)[lips, 1] += [-0.06, -0.03, -0.02, 0.02, 0.03, 0.06]
    instance._neutral_drive = {"exp": rest}
    instance._info = {"x_s_info_lst": [{"exp": source}], "f_s_lst": [None]}
    received = []

    def stitch(source_info, drive):
        received.append(drive["exp"].copy())
        return None, None

    instance._sdk = SimpleNamespace(motion_stitch=stitch)
    instance._renderer = lambda *args: np.zeros((512, 512, 3), np.float32)
    instance._renderer.frame_ms = []
    instance._render(0, {"exp": speech})
    vertical = (received[0] - source).reshape(21, 3)[lips, 1]
    assert np.linalg.norm(vertical - vertical.mean()) < 0.035
    assert instance.status()["lip_opening_limit"] == 0.035


def test_shorter_motion_stride_keeps_the_model_window_at_80_frames(monkeypatch):
    instance = engine()
    instance.MOTION_SAMPLES = 1920
    clock = [10.0]
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: clock[0])
    for _ in range(6):
        instance.push(1, np.full(320, 0.1, np.float32))
    cpu_worker(instance, monkeypatch, clock, iterations=1)
    instance._initialized = threading.Event()
    observed = []

    def motion_window(features):
        observed.append(features.shape)
        return motion([0] * 80)

    monkeypatch.setattr(instance, "_motion", motion_window)
    instance._worker()
    assert observed == [(80, 1)]
    assert instance.status()["motion_stride_ms"] == 120


def test_render_metrics_distinguish_repeated_pose_from_new_neural_frame(monkeypatch):
    instance = engine()
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: 11.0)
    instance._metrics_started = 10.0
    instance._record_render(1, motion([1])[0], 10.1, 10.18)
    instance._record_render(1, motion([1])[0], 10.2, 10.28)
    instance._record_render(1, motion([2])[0], 10.3, 10.38)
    instance._work.append((10.38, 0.24))
    status = instance.status()
    assert status["rendered_fps"] == 3
    assert status["unique_pose_fps"] == 2
    assert status["gpu_work_wall_fraction"] == pytest.approx(0.24)


def cpu_worker(instance, monkeypatch, clock, *, iterations):
    """Replace model initialization/inference; keep the actual worker state machine."""
    closed_detector = SimpleNamespace(close=lambda: None)

    def load():
        instance._silence_feature = np.zeros((5, 1), np.float32)
        instance._neutral_drive = motion([0])[0]
        if not hasattr(instance, "_info"):
            instance._info = {}
        instance._info.setdefault("img_rgb_lst", instance._idle_frames)
        instance._info.setdefault("M_c2o_lst", [np.eye(3)] * len(instance._idle_frames))
        instance._info.setdefault(
            "mouth_regions", [(256, 330, 90, 65)] * len(instance._idle_frames)
        )
        instance._sdk = SimpleNamespace(
            wav2feat=lambda chunk: np.zeros((5, 1), np.float32),
            avatar_registrar=SimpleNamespace(
                source2info=SimpleNamespace(
                    landmark478=SimpleNamespace(model=SimpleNamespace(detector=closed_detector))
                )
            ),
        )

    calls = []

    def render(index, drive, info=None):
        calls.append((index, drive["exp"].item()))
        return np.full((4, 4, 3), 7, dtype=np.uint8)

    ticks = 0

    def advance(now, **kwargs):
        nonlocal ticks
        instance._present_at(now)
        ticks += 1
        clock[0] += 0.1
        if ticks == iterations:
            instance._stop.set()
        return clock[0]

    monkeypatch.setattr(instance, "_load", load)
    monkeypatch.setattr(instance, "_render", render)
    monkeypatch.setattr(instance, "_advance_render_clock", advance)
    return calls


def test_worker_uses_original_smile_through_gap_without_neutral_inference(monkeypatch):
    instance = engine()
    clock = [10.0]
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: clock[0])
    instance.push(1, np.ones(320, dtype=np.float32))
    clock[0] = 10.4
    calls = cpu_worker(instance, monkeypatch, clock, iterations=7)
    instance._initialized = threading.Event()
    instance._worker()
    assert calls == []
    assert instance._mouth is None
    assert instance.status()["generated_frames"] == 0


def test_continuous_silent_packets_do_not_spend_gpu_on_a_clamped_mouth(monkeypatch):
    instance = engine()
    clock = [10.0]
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: clock[0])
    instance.push(1, np.ones(320, np.float32))
    clock[0] = 10.4
    instance.push(1, np.zeros(320, np.float32))
    calls = cpu_worker(instance, monkeypatch, clock, iterations=3)
    instance._initialized = threading.Event()
    instance._worker()
    assert calls == []


def test_idle_uses_the_same_frame_index_as_speech_after_a_source_loop(monkeypatch):
    instance = engine()
    instance._idle_frames = [np.full((4, 4, 3), value, np.uint8) for value in (10, 20)]
    instance._origin = 10.0
    clock = [10.0]
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: clock[0])
    # The mirrored speech-source clock selects frame 1. Idle must not use its
    # old independent modulo clock, which selects frame 0 and jumps on speech.
    monkeypatch.setattr(instance, "_source_frame", lambda now: (1, "idle"))
    cpu_worker(instance, monkeypatch, clock, iterations=1)
    instance._initialized = threading.Event()
    instance._worker()
    assert instance.latest_frame()[1][0, 0, 0] == 20


def test_worker_reset_during_motion_cannot_render_retired_guest_pose(monkeypatch):
    instance = engine()
    clock = [10.0]
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: clock[0])
    for _ in range(10):
        instance.push(1, np.ones(320, dtype=np.float32))
    calls = cpu_worker(instance, monkeypatch, clock, iterations=1)

    def retired_motion(features):
        instance.reset(2)
        return motion([42] * 80)

    monkeypatch.setattr(instance, "_motion", retired_motion)
    instance._initialized = threading.Event()
    instance._worker()
    assert calls == []
    assert instance.latest_frame()[0] == 2
    assert not instance.latest_frame()[1].any()
    assert instance.status()["dropped_stale_motion"] == 1


def test_smile_action_retains_original_source_expression_without_speech(monkeypatch):
    instance = engine()
    clock = [10.0]
    monkeypatch.setattr("scripts.ditto_realtime.time.monotonic", lambda: clock[0])
    instance._info = {"x_s_info_lst": motion([6])}
    instance.action("smile")
    calls = cpu_worker(instance, monkeypatch, clock, iterations=1)
    instance._initialized = threading.Event()
    instance._worker()
    assert calls == []
    np.testing.assert_array_equal(instance.latest_frame()[1], instance._idle_frames[0])


def test_plain_ditto_drops_the_kiosk_expression_layers():
    instance = DittoEngine(
        Path("source.mp4"),
        Path("."),
        composite="full-face",
        lip_opening_limit=0.06,
        plain_ditto=True,
    )
    assert instance._plain_ditto is True
    assert instance._expression_mode == "absolute"
    assert instance._lip_opening_limit == 0
    assert instance.status()["plain_ditto"] is True


def test_plain_ditto_is_only_defined_for_the_whole_face():
    with pytest.raises(ValueError, match="whole face"):
        DittoEngine(Path("source.mp4"), Path("."), composite="mouth", plain_ditto=True)


def test_plain_ditto_smooths_source_keypoints_as_upstream(monkeypatch):
    calls = []
    module = SimpleNamespace(
        smooth_x_s_info_lst=lambda values, smo_k: calls.append(smo_k) or ["smoothed"]
    )
    monkeypatch.setitem(sys.modules, "core.atomic_components.avatar_registrar", module)
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", plain_ditto=True)
    info = {"x_s_info_lst": ["raw"]}
    instance._smooth_source(info)
    assert info["x_s_info_lst"] == ["smoothed"] and calls == [13]


def test_default_engine_leaves_source_keypoints_unsmoothed():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face")
    info = {"x_s_info_lst": ["raw"]}
    instance._smooth_source(info)
    assert info["x_s_info_lst"] == ["raw"]


def test_plain_rest_takes_calm_expression_without_relative_pose():
    instance, seen = rest_engine()
    instance._plain_ditto, instance._expression_mode = True, "absolute"
    stitch = instance._sdk.motion_stitch
    stitch.d0, stitch.relative_d = "first-drive", True
    during = []
    call = type(stitch).__call__

    def spy(self, source_info, drive):
        during.append((self.d0, self.relative_d, drive["exp"].copy()))
        return call(self, source_info, drive)

    type(stitch).__call__ = spy
    instance._rest_face(1, 0)
    calm = [item for item in during if item[0] is None]
    assert len(calm) == 1 and calm[0][1] is False
    np.testing.assert_array_equal(calm[0][2], np.zeros((1, 63), np.float32))
    assert stitch.d0 == "first-drive" and stitch.relative_d is True


def test_without_the_wave_no_other_person_clip_is_loaded_or_offered(tmp_path):
    clip = tmp_path / "output" / "Café_assistant_waving_hand_a1410f2d_1080p.mp4"
    clip.parent.mkdir()
    clip.touch()
    assert DittoEngine(Path("source.mp4"), tmp_path)._wave_source() == clip
    instance = DittoEngine(Path("source.mp4"), tmp_path, wave=False)
    assert instance._wave_source() is None
    assert instance.action("wave") is False
    assert "wave" not in instance.status()["actions"]


def test_lip_factor_and_head_drive_need_the_plain_path():
    with pytest.raises(ValueError, match="plain"):
        DittoEngine(Path("source.mp4"), Path("."), composite="full-face", lip_factor=0.5)
    with pytest.raises(ValueError, match="plain"):
        DittoEngine(Path("source.mp4"), Path("."), composite="full-face", drive_head=True)


def test_lip_factor_must_compress():
    with pytest.raises(ValueError, match="Lip factor"):
        DittoEngine(
            Path("source.mp4"),
            Path("."),
            composite="full-face",
            plain_ditto=True,
            lip_factor=1.5,
        )


def test_head_drive_adds_pose_keys_to_the_driven_set():
    plain = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", plain_ditto=True)
    head = DittoEngine(
        Path("source.mp4"),
        Path("."),
        composite="full-face",
        plain_ditto=True,
        drive_head=True,
    )
    assert plain._driven_keys() == ("exp",)
    assert head._driven_keys() == ("exp", "pitch", "yaw", "roll", "t")
    assert head.status()["drive_head"] is True


def test_lip_factor_gives_every_source_frame_the_same_closed_lips(monkeypatch):
    def lips(spread):
        points = np.zeros((21, 3), np.float32)
        points[[6, 12, 14], 1] = -spread
        points[[17, 19, 20], 1] = spread
        return points.reshape(1, 63)

    module = SimpleNamespace(smooth_x_s_info_lst=lambda values, smo_k: values)
    monkeypatch.setitem(sys.modules, "core.atomic_components.avatar_registrar", module)
    instance = DittoEngine(
        Path("source.mp4"),
        Path("."),
        composite="full-face",
        plain_ditto=True,
        lip_factor=0.5,
    )
    info = {"x_s_info_lst": [{"exp": lips(s)} for s in (0.5, 0.1, 0.4, 0.3, 0.2, 0.6)]}
    instance._smooth_source(info)
    for item in info["x_s_info_lst"]:
        np.testing.assert_allclose(item["exp"], lips(0.3))
    np.testing.assert_allclose(info["lip_rest_y"], [-0.3, -0.3, -0.3, 0.3, 0.3, 0.3])


def silence_engine():
    return DittoEngine(
        Path("source.mp4"),
        Path("."),
        composite="full-face",
        plain_ditto=True,
        ditto_silence=True,
    )


def test_ditto_silence_needs_the_plain_path():
    with pytest.raises(ValueError, match="plain"):
        DittoEngine(Path("source.mp4"), Path("."), composite="full-face", ditto_silence=True)


def test_silence_padding_fills_the_audio_clock_without_counting_as_voice():
    instance = silence_engine()
    instance._audio_started_at = 100.0
    instance._audio_end = 16000
    instance._last_voiced_at = 101.0
    instance._pad_silence(102.5)
    assert instance._audio_end == 40000
    assert instance._last_voiced_at == 101.0
    assert instance._last_push == 102.5
    assert instance._audio[-1] == 0


def test_silence_padding_waits_for_the_first_audio_of_a_guest():
    instance = silence_engine()
    instance._pad_silence(102.5)
    assert instance._audio_end == 0


def test_silence_padding_never_overtakes_audio_that_arrived_early():
    instance = silence_engine()
    instance._audio_started_at = 100.0
    instance._audio_end = 48000
    instance._pad_silence(101.0)
    assert instance._audio_end == 48000


def test_default_engine_does_not_pad_silence():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face")
    instance._audio_started_at = 100.0
    instance._audio_end = 16000
    instance._pad_silence(102.5)
    assert instance._audio_end == 16000


def test_motion_keeps_running_through_silence_only_when_asked():
    now, last_push, last_voiced = 10.0, 9.9, 2.0
    assert silence_engine()._motion_active(now, 3200, last_push, last_voiced) is True
    plain = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", plain_ditto=True)
    assert plain._motion_active(now, 3200, last_push, last_voiced) is False
    assert silence_engine()._motion_active(now, 0, last_push, last_voiced) is False


def test_voice_level_follows_the_audio_of_the_displayed_pose_not_the_newest():
    instance = silence_engine()
    audio = np.concatenate((np.full(8000, 0.2, np.float32), np.zeros(16000, np.float32)))
    instance._voice_level, instance._voice_at = 0.0, 10.0
    assert instance._voice_alpha(audio, len(audio), 4000, 11.0) == 1.0
    assert instance._voice_alpha(audio, len(audio), 20000, 12.0) == 0.0


def test_voice_level_fades_instead_of_snapping():
    instance = silence_engine()
    audio = np.zeros(16000, np.float32)
    instance._voice_level, instance._voice_at = 1.0, 10.0
    level = instance._voice_alpha(audio, len(audio), 12000, 10.0 + instance.VOICE_FADE_SECONDS / 2)
    assert level == pytest.approx(0.5)


def test_render_passes_the_voice_level_to_upstream_stitching():
    instance, _ = rest_engine()
    instance._plain_ditto, instance._expression_mode = True, "absolute"
    seen = {}
    plain_call = type(instance._sdk.motion_stitch).__call__

    def stitch(self, source_info, drive, **kwargs):
        seen.update(kwargs)
        return plain_call(self, source_info, drive)

    type(instance._sdk.motion_stitch).__call__ = stitch
    instance._render(0, instance._neutral_drive, vad_alpha=0.25)
    assert seen == {"vad_alpha": 0.25}
    seen.clear()
    instance._render(0, instance._neutral_drive)
    assert seen == {}


def test_voice_level_accepts_the_float_sample_position_of_a_pose():
    instance = silence_engine()
    audio = np.full(16000, 0.2, np.float32)
    instance._voice_level, instance._voice_at = 0.0, 10.0
    assert instance._voice_alpha(audio, len(audio), 8000.0, 11.0) == 1.0


def test_reference_face_mode_keeps_source_pose_for_a_connected_neck():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", reference_frame=0)
    assert not instance._ditto_silence
    assert not instance._drive_head
    assert instance.status()["reference_frame"] == 0
    info = {"x_s_info_lst": ["frame-specific"]}
    instance._smooth_source(info)
    assert info["x_s_info_lst"] == ["frame-specific"]


def test_reference_face_mode_rejects_a_mouth_only_composite():
    with pytest.raises(ValueError, match="whole face"):
        DittoEngine(Path("source.mp4"), Path("."), reference_frame=0)


def test_reference_identity_does_not_drift_with_the_previous_windows_prediction():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", reference_frame=0)
    source = np.zeros((1, 265), np.float32)
    instance._sdk = SimpleNamespace(audio2motion=SimpleNamespace(s_kp_cond=source))
    instance._chained_pose = np.ones((1, 265), np.float32)
    np.testing.assert_array_equal(instance._motion_start(), source)


def test_prepared_face_is_blended_without_cross_frame_landmark_warp():
    from test_avatar_whole_face import landmarks

    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", reference_frame=0)
    info = {"M_c2o_lst": [np.eye(3)], "face_landmarks": [landmarks()]}
    original = np.full((512, 512, 3), 80, np.uint8)
    generated = np.full((512, 512, 3), 90, np.float32)
    generated[320:350, 230:280] = 150
    result = instance._paste_face(original, generated, info, 0)
    assert (result[335, 250] > 100).all()
    np.testing.assert_array_equal(result[430:], original[430:])


def test_prepared_source_renders_the_current_frames_features_not_frame_zero():
    prepared, _ = rest_engine()
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", reference_frame=0)
    instance._info, instance._sdk = prepared._info, prepared._sdk
    instance._neutral_drive = prepared._neutral_drive

    def stitch(source, drive):
        return source["name"], drive

    def renderer(features, source, drive):
        # A mismatched source-keypoint/feature pair cannot represent this identity.
        pairs = {"features-zero": ("zero", 7.0), "features-one": ("one", 9.0)}
        name, value = pairs[features]
        return np.full((512, 512, 3), value if source == name else 0.0, np.float32)

    renderer.frame_ms = []
    instance._sdk.motion_stitch = stitch
    instance._renderer = renderer
    result = instance._render(1, instance._neutral_drive)
    np.testing.assert_array_equal(result, 9.0)


def test_reference_face_mode_stops_inference_in_silence():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", reference_frame=0)
    now, last_push, last_voiced = 10.0, 9.9, 9.0
    assert instance._motion_active(now, 3200, last_push, last_voiced) is False
    assert instance._motion_active(now, 3200, last_push, now - 0.1) is True
    instance._audio_started_at, instance._audio_end = 100.0, 16000
    instance._pad_silence(130.0)
    assert instance._audio_end == 16000


def test_reference_face_mode_rests_on_the_prepared_face_after_the_voice_stops():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", reference_frame=0)
    instance._audio_end, instance._last_voiced_at = 16000, 10.0
    instance._rest_faces = [np.full((512, 512, 3), 5, np.uint8)]
    instance._idle_frames = [np.zeros((16, 16, 3), np.uint8)]
    instance._info = {"M_c2o_lst": [np.eye(3)]}
    shown = []
    instance._paste_face = lambda frame, face, info, index: (
        shown.append(int(face[0, 0, 0])) or frame
    )
    instance._publish = lambda epoch, frame: True
    instance._present_at(10.0 + instance.MOUTH_REST_SECONDS + 0.5)
    assert shown == [5]
    assert instance._mouth_mode == "source"


def test_the_silence_option_stays_available_when_asked_with_reference_rendering():
    instance = DittoEngine(
        Path("source.mp4"),
        Path("."),
        composite="full-face",
        reference_frame=0,
        ditto_silence=True,
    )
    assert instance._ditto_silence


def reference_head_engine(drive_head, **options):
    instance = DittoEngine(
        Path("source.mp4"),
        Path("."),
        composite="full-face",
        reference_frame=0,
        drive_head=drive_head,
        **options,
    )
    seen = {}

    class Stitch:
        def __call__(self, source_info, drive):
            seen["pitch"] = drive["pitch"]
            return "source-kp", "driving-kp"

    def renderer(features, source, driving):
        return np.zeros((512, 512, 3), np.float32)

    renderer.frame_ms = []
    instance._renderer = renderer
    instance._sdk = SimpleNamespace(motion_stitch=Stitch())
    return instance, seen


def head_fixture(instance, own_pitch, rest_pitch, voice_pitch):
    from test_avatar_whole_face import pose

    exp = np.zeros((1, 63), np.float32)
    instance._info = {
        "x_s_info_lst": [{**pose(pitch=own_pitch), "exp": exp}],
        "f_s_lst": ["features"],
    }
    instance._neutral_drive = {**pose(pitch=rest_pitch), "exp": exp}
    return {**pose(pitch=voice_pitch), "exp": exp}


def test_head_drive_is_allowed_in_reference_rendering_and_drives_scale_too():
    instance = DittoEngine(
        Path("source.mp4"),
        Path("."),
        composite="full-face",
        reference_frame=0,
        drive_head=True,
    )
    assert instance._driven_keys() == ("exp", "pitch", "yaw", "roll", "t", "scale")
    assert instance.status()["drive_head"] is True


def test_reference_render_moves_the_head_with_the_voice_when_asked():
    instance, seen = reference_head_engine(drive_head=True)
    voice = head_fixture(instance, own_pitch=-4.0, rest_pitch=1.0, voice_pitch=3.0)
    instance._render(0, voice)
    assert seen["pitch"][0] == pytest.approx(-2.0, abs=0.02)


def test_whole_head_is_pasted_with_upstreams_head_mask_not_inside_the_face_oval():
    calls = []

    def putback(frame, face, matrix):
        calls.append("upstream")
        return frame

    def build(**options):
        instance = DittoEngine(
            Path("source.mp4"),
            Path("."),
            composite="full-face",
            reference_frame=0,
            **options,
        )
        instance._sdk = SimpleNamespace(putback=putback)
        return instance

    info = {"M_c2o_lst": [np.eye(3)], "face_landmarks": [np.zeros((478, 2), np.float32)]}
    frame, face = np.zeros((64, 64, 3), np.uint8), np.zeros((512, 512, 3), np.float32)
    build(whole_head=True)._paste_face(frame, face, info, 0)
    assert calls == ["upstream"]
    build()._paste_face(frame, face, info, 0)  # The face-oval paste does not use putback.
    assert calls == ["upstream"]


def test_reference_render_leaves_the_head_to_the_clip_by_default():
    instance, seen = reference_head_engine(drive_head=False)
    voice = head_fixture(instance, own_pitch=-4.0, rest_pitch=1.0, voice_pitch=3.0)
    instance._render(0, voice)
    np.testing.assert_array_equal(seen["pitch"], voice["pitch"])


def rest_clip_engine():
    instance = DittoEngine(Path("source.mp4"), Path("."), composite="full-face", reference_frame=0)
    instance._idle_frames = [np.full((16, 16, 3), 10, np.uint8)]
    instance._info = {}
    instance._rest_frames = [np.full((16, 16, 3), 60, np.uint8), np.full((16, 16, 3), 70, np.uint8)]
    instance._rest_fps, instance._rest_origin = 24.0, 100.0
    shown = []
    instance._paste_face = lambda frame, face, info, index: np.full_like(frame, 200)
    instance._publish = lambda epoch, frame: shown.append(frame.copy()) or True
    return instance, shown


def test_without_speech_the_rest_clip_is_shown_instead_of_the_source():
    instance, shown = rest_clip_engine()
    instance._present_at(100.0)
    instance._present_at(100.0 + 1 / 24 + 0.001)
    assert [int(frame[0, 0, 0]) for frame in shown] == [60, 70]


def test_a_generated_face_can_dissolve_in_from_the_rest_clip():
    instance, shown = rest_clip_engine()
    instance._fade = CrossFade(0.25)
    instance._present_at(100.0)
    face = np.zeros((16, 16, 3), np.float32)
    assert instance._store_mouth(instance._epoch, face, "idle", (8, 8, 4, 4), 0)
    instance._present_at(100.0)
    instance._present_at(100.0 + 0.26)
    assert int(shown[1][0, 0, 0]) == 60
    assert int(shown[2][0, 0, 0]) == 200


def test_by_default_speech_and_rest_switch_with_a_clean_cut():
    instance, shown = rest_clip_engine()
    instance._present_at(100.0)
    face = np.zeros((16, 16, 3), np.float32)
    assert instance._store_mouth(instance._epoch, face, "idle", (8, 8, 4, 4), 0)
    instance._present_at(100.0)
    instance._mouth = None
    instance._present_at(100.0)
    assert [int(frame[0, 0, 0]) for frame in shown] == [60, 200, 60]


def test_rest_faces_are_not_prepared_when_a_rest_clip_covers_silence():
    instance, _ = rest_clip_engine()
    assert not instance._needs_rest_faces()
    assert DittoEngine(Path("source.mp4"), Path("."), composite="full-face")._needs_rest_faces()
    assert not DittoEngine(Path("source.mp4"), Path("."), composite="mouth")._needs_rest_faces()


def test_reset_starts_a_new_guest_on_the_rest_clip():
    instance, _ = rest_clip_engine()
    instance.reset(1)
    assert int(instance.latest_frame()[1][0, 0, 0]) == 60


def test_rest_clip_is_reported_in_status():
    instance, _ = rest_clip_engine()
    assert instance.status()["rest_clip"] is True
    assert (
        DittoEngine(Path("source.mp4"), Path("."), composite="full-face").status()["rest_clip"]
        is False
    )


def test_head_gain_scales_the_audio_driven_head_motion():
    instance, seen = reference_head_engine(drive_head=True, head_gain=0.5)
    voice = head_fixture(instance, own_pitch=-4.0, rest_pitch=1.0, voice_pitch=3.0)
    instance._render(0, voice)
    assert seen["pitch"][0] == pytest.approx(-3.0, abs=0.02)
    assert instance.status()["head_gain"] == 0.5


def test_head_gain_defaults_to_the_models_own_amplitude():
    instance, _ = reference_head_engine(drive_head=True)
    assert instance.status()["head_gain"] == 1.0


@pytest.mark.parametrize("gain", [0.0, -0.2, float("nan"), float("inf")])
def test_head_gain_must_be_a_positive_finite_number(gain):
    with pytest.raises(ValueError, match="Head gain"):
        reference_head_engine(drive_head=True, head_gain=gain)


def test_head_gain_without_head_drive_is_rejected():
    with pytest.raises(ValueError, match="Head gain"):
        reference_head_engine(drive_head=False, head_gain=0.5)


def test_a_clip_closed_in_advance_is_not_given_the_donor_lips_again():
    prepared = DittoEngine(Path("s.mp4"), Path("."), composite="full-face", reference_frame=0)
    closed = DittoEngine(
        Path("s.mp4"), Path("."), composite="full-face", reference_frame=0, closed_source=True
    )
    assert prepared._prepares_source_mouth() is True
    assert closed._prepares_source_mouth() is False
    assert closed.status()["source_mouth_prepared"] is False
    assert prepared.status()["source_mouth_prepared"] is True


def test_without_reference_rendering_no_source_lips_are_prepared():
    assert not DittoEngine(Path("s.mp4"), Path("."), composite="full-face")._prepares_source_mouth()
