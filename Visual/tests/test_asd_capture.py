import json

import numpy as np
import pytest

from tools.asd_capture import PHASES, RecordingAVBuffer, build, run_guide
from tools.asd_replay import load_fixture


def _record(tmp_path, t0=1790000000.0, packets=30, gap_after=None, loud=None,
            stream="s1"):
    buf = RecordingAVBuffer(str(tmp_path))
    buf.start_stream(stream)
    buf.select_track(7)
    seq, t = 0, t0
    for i in range(packets):
        if gap_after is not None and i == gap_after:
            t += 0.5  # a transport gap: the capture must not paper over it
        level = 8000 if loud is None or i in loud else 10  # speech vs room
        buf.push_audio(stream, seq, t, np.full(1280, level, np.int16))
        seq, t = seq + 1, t + 0.08
    for k in range(int(packets * 0.08 * 15)):
        buf.push_crop(7, t0 + k / 15, np.full((112, 112), k % 256, np.uint8))
    buf.stop_stream(stream)
    return buf


def test_recorder_saves_exactly_what_the_runtime_buffer_received(tmp_path):
    _record(tmp_path)
    raw = np.load(next(tmp_path.glob("raw-*.npz")), allow_pickle=False)
    assert raw["audio_t0s"].shape == (30,) and raw["pcm"].shape == (30, 1280)
    assert raw["crop_ts"].shape[0] == raw["crops"].shape[0] == 36
    assert set(raw["crop_tracks"].tolist()) == {7}


def test_build_writes_a_fixture_the_replay_tool_loads(tmp_path):
    t0 = 1790000000.0
    _record(tmp_path, t0=t0)
    (tmp_path / "labels.json").write_text(json.dumps([
        {"start": t0 + 0.2, "end": t0 + 1.2, "speaking": True, "scenario": "speaking"},
        {"start": t0 + 1.2, "end": t0 + 2.2, "speaking": False, "scenario": "silence"},
    ]))
    manifest_path = build(str(tmp_path), split="calibration")
    manifest, audio, ts, ids, crops = load_fixture(manifest_path)
    assert manifest["audio_t0"] == pytest.approx(t0)
    assert len(audio) == 30 * 1280
    assert [l["track_id"] for l in manifest["labels"]] == [7, 7]
    assert manifest["split"] == "calibration" and manifest["enhancer"] == "none"


def test_build_keeps_only_the_longest_contiguous_audio_run(tmp_path):
    t0 = 1790000000.0
    _record(tmp_path, t0=t0, packets=30, gap_after=10)
    (tmp_path / "labels.json").write_text(json.dumps([
        {"start": t0, "end": t0 + 2.0, "speaking": True, "scenario": "speaking"}]))
    manifest, audio, *_ = load_fixture(build(str(tmp_path), split="held_out"))
    assert len(audio) == 20 * 1280  # never zero-filled across the gap
    assert manifest["audio_t0"] == pytest.approx(t0 + 10 * 0.08 + 0.5)


def test_speaking_phases_are_labeled_only_where_speech_is_heard(tmp_path):
    # Held-out 2026-09-29: the operator spoke 19-33% of each 15 s speaking
    # phase and waited for the bot the rest, yet the whole phase was labeled
    # speaking, so ASD recall read 24% while it caught 99% of real speech.
    t0 = 1790000000.0
    _record(tmp_path, t0=t0, loud=range(5, 10))  # speech 0.40-0.80 s only
    (tmp_path / "labels.json").write_text(json.dumps([
        {"start": t0 + 0.2, "end": t0 + 1.8, "speaking": True, "scenario": "speaking"},
        {"start": t0 + 1.8, "end": t0 + 2.3, "speaking": False, "scenario": "silence"},
    ]))
    manifest, *_ = load_fixture(build(str(tmp_path), split="held_out"))
    speaking, silence = manifest["labels"]
    assert speaking["scenario"] == "speaking" and speaking["speaking"] is True
    assert t0 + 0.28 <= speaking["start"] <= t0 + 0.44
    assert t0 + 0.76 <= speaking["end"] <= t0 + 0.92
    assert (silence["start"], silence["end"]) == (t0 + 1.8, t0 + 2.3)  # unchanged


def test_build_uses_the_capture_the_labels_were_recorded_in(tmp_path):
    # 2026-09-29: capture stayed on, a later voice session saved a newer raw
    # file, and build picked it: 0 labels matched.
    import os

    t0 = 1790000000.0
    _record(tmp_path, t0=t0)
    labeled = next(tmp_path.glob("raw-*.npz"))
    _record(tmp_path, t0=t0 + 600, stream="s2")
    newer = next(p for p in tmp_path.glob("raw-*.npz") if p != labeled)
    os.utime(labeled, (1, 1))  # the labeled capture is the older file
    assert newer.stat().st_mtime > labeled.stat().st_mtime
    (tmp_path / "labels.json").write_text(json.dumps([
        {"start": t0 + 0.2, "end": t0 + 1.2, "speaking": True, "scenario": "speaking"}]))
    manifest, *_ = load_fixture(build(str(tmp_path), split="held_out"))
    assert manifest["audio_t0"] == pytest.approx(t0) and len(manifest["labels"]) == 1


def test_guide_labels_each_phase_on_the_host_clock(tmp_path):
    clock = [1790000000.0]

    def sleep(secs):
        clock[0] += secs

    run_guide(str(tmp_path), now=lambda: clock[0], sleep=sleep, say=lambda _: None)
    labels = json.loads((tmp_path / "labels.json").read_text())
    assert [l["scenario"] for l in labels] == [p[0] for p in PHASES]
    assert all(l["end"] - l["start"] == pytest.approx(p[2]) for l, p in zip(labels, PHASES))
    assert all(b["start"] > a["end"] for a, b in zip(labels, labels[1:]))  # gaps unlabeled
