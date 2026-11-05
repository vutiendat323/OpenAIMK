import json
import wave

import numpy as np
import pytest

from tools.asd_replay import replay


def fixture(tmp_path, split="calibration", audio_t0=0.0):
    with wave.open(str(tmp_path / "audio.wav"), "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", ""))
        out.writeframes(np.zeros(48000, dtype="<i2").tobytes())
    ts = audio_t0 + np.arange(0.02, 3.42, 0.04)
    # Video speech is delayed by 200 ms against audio labels.
    speaking = (ts - audio_t0 >= 1.2) & (ts - audio_t0 < 2.2)
    crops = np.broadcast_to(
        (speaking * 255).astype("uint8")[:, None, None], (len(ts), 112, 112)
    ).copy()
    np.savez(
        tmp_path / "crops.npz",
        timestamps=ts,
        track_ids=np.ones(len(ts), dtype=int),
        crops=crops,
    )
    manifest = dict(
        version=1,
        audio_wav="audio.wav",
        audio_t0=audio_t0,
        crops_npz="crops.npz",
        enhancer="none",
        split=split,
        labels=[
            dict(track_id=1, start=audio_t0 + a, end=audio_t0 + b, speaking=s,
                 scenario="synthetic")
            for a, b, s in [(0, 1, False), (1, 2, True), (2, 3, False)]
        ],
    )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


class Detector:
    manifest = {"artifact_sha256": "fake"}

    def predict(self, audio, crops):
        return crops[:, 0, 0] / 255


def test_calibration_selects_positive_offset(tmp_path):
    report = replay(fixture(tmp_path), Detector(), offset_sweep=True)
    assert report["selected_offset_secs"] == 0.2
    assert [r["offset_secs"] for r in report["runs"]] == [
        round(-0.4 + i * 0.04, 2) for i in range(21)
    ]
    assert report["runs"][15]["tracks"]["1"]["fp"] == 0
    assert report["runs"][15]["tracks"]["1"]["fn"] == 0


def test_calibration_holds_at_epoch_scale_timestamps(tmp_path):
    # The documented timeline is Unix seconds; bins must still line up there.
    report = replay(fixture(tmp_path, audio_t0=1790000000.0), Detector(), offset_sweep=True)
    assert report["selected_offset_secs"] == 0.2
    run = report["runs"][15]["tracks"]["1"]
    assert run["unknown"] <= 2 and run["tp"] == 25 and run["fp"] == 0 and run["fn"] == 0


def test_sweep_without_any_true_positive_selects_no_offset(tmp_path):
    class Silent(Detector):
        def predict(self, audio, crops):
            return np.zeros(25, dtype=np.float32)

    report = replay(fixture(tmp_path), Silent(), offset_sweep=True)
    assert report["selected_offset_secs"] is None
    assert "true positive" in report["selection_reason"]


def test_held_out_requires_frozen_offset_and_video(tmp_path):
    path = fixture(tmp_path, "held_out")
    with pytest.raises(ValueError, match="held_out"):
        replay(path, Detector(), offset_sweep=True)
    with pytest.raises(ValueError, match="explicit"):
        replay(path, Detector())
    (tmp_path / "crops.npz").unlink()
    with pytest.raises(ValueError, match="video"):
        replay(path, Detector(), offset_secs=0.2)


def test_unknown_track_is_not_silence(tmp_path):
    path = fixture(tmp_path)
    data = json.loads(path.read_text())
    data["labels"].append(
        dict(track_id=2, start=0, end=3, speaking=False, scenario="missing_face")
    )
    path.write_text(json.dumps(data))
    report = replay(path, Detector(), offset_secs=0.2)["runs"][0]
    assert report["tracks"]["2"]["unknown"] == 75
    assert report["tracks"]["2"]["tn"] == 0
    assert report["windows_skipped"]["missing_crop_coverage"] > 0


@pytest.mark.parametrize("bad", ["length", "nan", "pickle"])
def test_invalid_crop_arrays_rejected(tmp_path, bad):
    path = fixture(tmp_path)
    with np.load(tmp_path / "crops.npz") as z:
        arrays = {k: z[k] for k in z.files}
    if bad == "length":
        arrays["track_ids"] = arrays["track_ids"][:-1]
    elif bad == "nan":
        arrays["timestamps"][0] = np.nan
    else:
        arrays["crops"] = np.array([object()], dtype=object)
    np.savez(tmp_path / "crops.npz", **arrays)
    with pytest.raises(ValueError):
        replay(path, Detector(), offset_secs=0.2)
