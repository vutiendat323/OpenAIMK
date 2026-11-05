"""Capture a labeled A/V calibration clip from the live ASD path (operator opt-in).

Three steps, all local and all started by the operator:

1. Run the stack with ``VISION_ASD_CAPTURE_DIR=DIR`` (and ASD on in OpenJarvis).
   Vision then records every audio packet and face crop its runtime AVBuffer
   receives, on the same timeline ASD sees, to ``DIR/raw-<stream>.npz`` when
   the voice session ends.
2. ``python3 tools/asd_capture.py guide DIR`` in a terminal next to the kiosk:
   it prompts each scenario and writes ``DIR/labels.json`` on the host clock.
3. ``python3 tools/asd_capture.py build DIR --split calibration`` writes
   ``manifest.json``, ``audio.wav`` and ``crops.npz`` for tools/asd_replay.py.
   A speaking phase is labeled speaking only where speech is heard (see
   ``speech_runs``); its pauses stay unlabeled, never "silent".

Mute the kiosk speakers while capturing: the bot's replies would be heard as
speech, and waiting for them is what left most of a speaking phase silent.

Record the calibration and the held-out clip into separate directories.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import threading
import time
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Visual.domain.active_speaker import AVBuffer  # noqa: E402

PACKET = 1280
RATE = 16000
CONTIGUOUS_SECS = 0.02  # same continuity rule as AVBuffer.push_audio

# (scenario, operator prompt, seconds, customer speaking?)
PHASES = (
    ("silence", "Nhìn vào camera, IM LẶNG, không cử động miệng.", 15.0, False),
    ("speaking", "Đọc to LIÊN TỤC một đoạn văn (vd. đọc menu), không chờ bot.", 15.0, True),
    ("head_motion", "IM LẶNG, nhưng quay đầu, gật đầu, cử động miệng không thành tiếng.", 15.0, False),
    ("silent_video", "IM LẶNG, phát video có tiếng người nói trên điện thoại gần kiosk.", 15.0, False),
    ("speaking_video", "Đọc to LIÊN TỤC trong khi video vẫn phát.", 15.0, True),
    ("speaking", "Đọc to LIÊN TỤC lần nữa (tắt video).", 15.0, True),
)
GAP_SECS = 3.0  # transitions stay unlabeled
# Speech vs the room: 200 ms RMS over this level. Kiosk C920 via the browser
# measured -44..-53 dBFS room/silence and -18..-30 dBFS speech (2026-09-29).
# Re-measure on another mic; override with build --speech-dbfs.
SPEECH_DBFS = -38.0
BIN_SECS = 0.04  # ASD's output bin; labels land on its grid


class RecordingAVBuffer(AVBuffer):
    """The runtime AVBuffer, also keeping what it was given for offline replay."""

    def __init__(self, out_dir: str):
        super().__init__()
        self._out = Path(out_dir)
        self._out.mkdir(parents=True, exist_ok=True)
        self._rec_lock = threading.Lock()
        self._reset_recording()

    def _reset_recording(self) -> None:
        self._rec_audio_t0s: list[float] = []
        self._rec_pcm: list[np.ndarray] = []
        self._rec_crop_ts: list[float] = []
        self._rec_crop_tracks: list[int] = []
        self._rec_crops: list[np.ndarray] = []

    def push_audio(self, stream_id: str, seq: int, t0: float, pcm16: np.ndarray) -> bool:
        accepted = super().push_audio(stream_id, seq, t0, pcm16)
        # A False return can still be a fresh start after a gap; keep every
        # packet of the current stream that passed validation.
        if (stream_id == self._stream_id and pcm16.shape == (PACKET,)
                and pcm16.dtype == np.int16):
            with self._rec_lock:
                self._rec_audio_t0s.append(float(t0))
                self._rec_pcm.append(pcm16.copy())
        return accepted

    def push_crop(self, track_id: int, ts: float, crop: np.ndarray) -> None:
        super().push_crop(track_id, ts, crop)
        with self._rec_lock:
            self._rec_crop_ts.append(float(ts))
            self._rec_crop_tracks.append(int(track_id))
            self._rec_crops.append(np.asarray(crop, np.uint8).copy())

    def stop_stream(self, stream_id: str) -> None:
        if stream_id == self._stream_id:
            self.save(stream_id)
        super().stop_stream(stream_id)

    def save(self, name: str) -> Path | None:
        with self._rec_lock:
            if not self._rec_pcm:
                return None
            path = self._out / f"raw-{name}.npz"
            np.savez(
                path,
                audio_t0s=np.asarray(self._rec_audio_t0s, np.float64),
                pcm=np.stack(self._rec_pcm),
                crop_ts=np.asarray(self._rec_crop_ts, np.float64),
                crop_tracks=np.asarray(self._rec_crop_tracks, np.int64),
                crops=np.stack(self._rec_crops) if self._rec_crops
                else np.zeros((0, 112, 112), np.uint8),
            )
            self._reset_recording()
        print(f"[asd-capture] saved {path}")
        return path


def _say(text: str) -> None:
    print(text, flush=True)  # the operator reads each prompt as it happens


def _countdown(secs: float, sleep, say) -> None:
    left = int(round(secs))
    while left > 0:
        say(f"    ... còn {left} s")
        sleep(1.0)
        left -= 1


def run_guide(out_dir: str, *, now=time.time, sleep=time.sleep, say=_say) -> Path:
    """Prompt each scenario and label it on the host clock (same as capture)."""
    labels = []
    say("Chuẩn bị: đứng trước kiosk, phiên voice đang chạy.")
    say("Mỗi pha có đếm ngược; tiếng bíp = đổi pha. Bắt đầu sau 5 giây.")
    _countdown(5.0, sleep, say)
    for number, (scenario, prompt, secs, speaking) in enumerate(PHASES, 1):
        say(f"\a\n===== PHA {number}/{len(PHASES)}: {prompt} ({secs:.0f} s) =====")
        start = now()
        _countdown(secs, sleep, say)
        labels.append(dict(start=start, end=now(), speaking=speaking, scenario=scenario))
        say(f"\a----- hết pha {number}; nghỉ {GAP_SECS:.0f} s, chuẩn bị pha sau -----")
        _countdown(GAP_SECS, sleep, say)
    path = Path(out_dir) / "labels.json"
    path.write_text(json.dumps(labels, indent=1))
    say(f"\nĐã ghi nhãn: {path}")
    return path


def _longest_run(t0s: np.ndarray) -> slice:
    """Indices of the longest run of packets that follow each other in time."""
    best, start = (0, 1), 0
    for i in range(1, len(t0s) + 1):
        if i == len(t0s) or abs(t0s[i] - (t0s[i - 1] + PACKET / RATE)) > CONTIGUOUS_SECS:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = i
    return slice(*best)


def speech_runs(audio: np.ndarray, start: float, stop: float,
                speech_dbfs: float = SPEECH_DBFS) -> list[tuple[float, float]]:
    """(start, stop) seconds of the 40 ms bins in [start, stop) with speech.

    Energy cannot tell whose voice it is: in speaking_video the video's own
    speech also counts. It only drops the pauses, which are certainly not
    the customer speaking.
    """
    half = int(0.1 * RATE)
    runs, run_start = [], None
    # Whole bins inside the phase only; 1e-6 absorbs epoch-magnitude float
    # error, which otherwise spills a bin into the next phase's label.
    first = int(np.ceil(start / BIN_SECS - 1e-6))
    last = int(np.floor(stop / BIN_SECS + 1e-6))
    for k in range(first, last + 1):
        loud = False
        if k < last:
            centre = int((k * BIN_SECS + BIN_SECS / 2) * RATE)
            chunk = audio[max(centre - half, 0):centre + half].astype(np.float64)
            rms = np.sqrt(np.mean(chunk ** 2)) if len(chunk) else 0.0
            loud = 20 * np.log10(max(rms, 1e-9) / 32768) > speech_dbfs
        if loud and run_start is None:
            run_start = k
        elif not loud and run_start is not None:
            runs.append((run_start * BIN_SECS, k * BIN_SECS))
            run_start = None
    return runs


def build(out_dir: str, *, split: str, enhancer: str = "none",
          speech_dbfs: float = SPEECH_DBFS) -> Path:
    """Turn the raw capture labels.json was recorded in into an asd_replay fixture."""
    out = Path(out_dir)
    phases = json.loads((out / "labels.json").read_text())
    labeled = (min(p["start"] for p in phases), max(p["end"] for p in phases))

    def overlap(path: Path) -> float:
        # Capture stays on for every later voice session, so the newest raw
        # file is not necessarily the one the operator labeled.
        with np.load(path, allow_pickle=False) as candidate:
            t0s = candidate["audio_t0s"]
            first, last = float(t0s.min()), float(t0s.max()) + PACKET / RATE
        return min(last, labeled[1]) - max(first, labeled[0])

    raw = np.load(max(out.glob("raw-*.npz"), key=overlap), allow_pickle=False)
    order = np.argsort(raw["audio_t0s"])
    t0s, pcm = raw["audio_t0s"][order], raw["pcm"][order]
    run = _longest_run(t0s)
    audio_t0, audio = float(t0s[run][0]), pcm[run].reshape(-1)
    with wave.open(str(out / "audio.wav"), "wb") as w:
        w.setparams((1, 2, RATE, 0, "NONE", ""))
        w.writeframes(audio.astype("<i2").tobytes())
    np.savez(out / "crops.npz", timestamps=raw["crop_ts"],
             track_ids=raw["crop_tracks"], crops=raw["crops"])
    labels = []
    for label in phases:
        inside = (raw["crop_ts"] >= label["start"]) & (raw["crop_ts"] < label["end"])
        if not inside.any():
            continue  # no face seen: unknown, never silence
        tracks, counts = np.unique(raw["crop_tracks"][inside], return_counts=True)
        label = dict(label, track_id=int(tracks[np.argmax(counts)]))
        if not label["speaking"]:
            labels.append(label)
            continue
        for a, b in speech_runs(audio, label["start"] - audio_t0,
                                label["end"] - audio_t0, speech_dbfs):
            labels.append(dict(label, start=audio_t0 + a, end=audio_t0 + b))
    manifest = dict(version=1, audio_wav="audio.wav", audio_t0=audio_t0,
                    crops_npz="crops.npz", enhancer=enhancer, split=split, labels=labels)
    path = out / "manifest.json"
    path.write_text(json.dumps(manifest, indent=1))
    print(f"[asd-capture] {path}: {len(audio) / RATE:.1f} s audio, "
          f"{len(raw['crop_ts'])} crops, {len(labels)} labels")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("guide").add_argument("dir")
    b = sub.add_parser("build")
    b.add_argument("dir")
    b.add_argument("--split", choices=("calibration", "held_out"), required=True)
    b.add_argument("--enhancer", choices=("none", "rnnoise"), default="none")
    b.add_argument("--speech-dbfs", type=float, default=SPEECH_DBFS)
    args = parser.parse_args()
    if args.command == "guide":
        run_guide(args.dir)
    else:
        build(args.dir, split=args.split, enhancer=args.enhancer,
              speech_dbfs=args.speech_dbfs)


if __name__ == "__main__":
    main()
