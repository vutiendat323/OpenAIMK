"""Read-only saved A/V calibration. Times are on one audio/capture timeline.

Positive offset selects later video. Labels describe audio-time speaker activity.
Overlapping windows contribute each 40 ms labeled bin once (latest window wins).
This retrospective model replay does not measure live scheduling or gate quality.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from Visual.domain.active_speaker import AVBuffer


def metrics(counts):
    tp, fp, fn = (counts.get(k, 0) for k in ("tp", "fp", "fn"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        **{k: counts.get(k, 0) for k in ("tp", "fp", "tn", "fn", "unknown")},
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0,
    }


def load_fixture(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    if (
        manifest.get("version") != 1
        or manifest.get("split") not in ("calibration", "held_out")
        or manifest.get("enhancer") not in ("none", "rnnoise")
    ):
        raise ValueError(
            "expected version 1, calibration/held_out split and none/rnnoise enhancer"
        )
    video = path.parent / manifest.get("crops_npz", "")
    if not video.is_file():
        raise ValueError("missing video crops_npz: a WAV alone cannot be scored as A/V")
    with np.load(video, allow_pickle=False) as data:
        ts, ids, crops = (data[k].copy() for k in ("timestamps", "track_ids", "crops"))
    if (
        ts.ndim != 1
        or ids.shape != ts.shape
        or crops.shape != (len(ts), 112, 112)
        or crops.dtype != np.uint8
        or not np.isfinite(ts).all()
    ):
        raise ValueError("invalid crop arrays or nonfinite timestamps")
    if not np.issubdtype(ids.dtype, np.integer):
        raise ValueError("track_ids must be integers")
    with wave.open(str(path.parent / manifest["audio_wav"]), "rb") as wav:
        if (
            wav.getnchannels(),
            wav.getsampwidth(),
            wav.getframerate(),
            wav.getcomptype(),
        ) != (1, 2, 16000, "NONE"):
            raise ValueError("audio_wav must be PCM16 mono 16 kHz")
        audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").copy()
    if not np.isfinite(manifest["audio_t0"]):
        raise ValueError("nonfinite audio_t0")
    labels = manifest.get("labels", [])
    if not labels:
        raise ValueError("labels required")
    for label in labels:
        if (
            not isinstance(label.get("speaking"), bool)
            or not label.get("scenario")
            or not np.isfinite([label["start"], label["end"]]).all()
            or label["end"] <= label["start"]
        ):
            raise ValueError("invalid label")
    for i, a in enumerate(labels):
        if any(
            a["track_id"] == b["track_id"]
            and max(a["start"], b["start"]) < min(a["end"], b["end"])
            for b in labels[i + 1 :]
        ):
            raise ValueError("overlapping track labels")
    return manifest, audio, ts, ids, crops


def replay(path, detector, *, offset_sweep=False, offset_secs=None):
    manifest, audio, ts, ids, crops = load_fixture(path)
    if offset_sweep and manifest["split"] == "held_out":
        raise ValueError("offset sweep forbidden on held_out")
    if offset_sweep and offset_secs is not None:
        raise ValueError("choose sweep or frozen offset")
    if not offset_sweep and offset_secs is None:
        raise ValueError("explicit frozen offset required")
    offsets = (
        [round(-0.4 + i * 0.04, 2) for i in range(21)]
        if offset_sweep
        else [offset_secs]
    )
    if not all(np.isfinite(x) and -1 <= x <= 1 for x in offsets):
        raise ValueError("offset must be finite in [-1,1]")
    runs = []
    for offset in offsets:
        predictions, latencies, skipped = {}, [], Counter()
        windows = 0
        for track in sorted({l["track_id"] for l in manifest["labels"]}):
            selected = np.flatnonzero(ids == track)
            selected = selected[np.argsort(ts[selected])]
            for end in range(16640, len(audio) + 1, 1280):
                # Exactly thirteen genuine packets; no padding, rolling or wraparound.
                buf = AVBuffer()
                buf.start_stream("replay")
                buf.select_track(track)
                start = end - 16640
                for seq, pos in enumerate(range(start, end, 1280)):
                    buf.push_audio(
                        "replay",
                        seq,
                        manifest["audio_t0"] + pos / 16000,
                        audio[pos : pos + 1280],
                    )
                t0 = manifest["audio_t0"] + end / 16000 - 1
                for index in selected[
                    (ts[selected] >= t0 + offset - 0.08)
                    & (ts[selected] <= t0 + offset + 1.08)
                ]:
                    buf.push_crop(track, float(ts[index]), crops[index])
                window = buf.next_window(offset_secs=offset, now=t0 + 1)
                if window is None:
                    skipped["missing_crop_coverage"] += 1
                    continue
                begin = time.perf_counter()
                probs = np.asarray(detector.predict(window.pcm16, window.crops))
                latencies.append((time.perf_counter() - begin) * 1000)
                if (
                    probs.shape != (25,)
                    or not np.isfinite(probs).all()
                    or not ((probs >= 0) & (probs <= 1)).all()
                ):
                    skipped["invalid_model_output"] += 1
                    continue
                windows += 1
                # Integer 40 ms bin index relative to audio_t0: absolute float
                # keys stop matching at Unix-second magnitudes.
                first_bin = (end - 16000) // 640
                for k, p in enumerate(probs):
                    predictions[(track, first_bin + k)] = float(p)
        counts, scenarios = {}, {}
        for label in manifest["labels"]:
            track = label["track_id"]
            count = counts.setdefault(str(track), Counter())
            scenario = scenarios.setdefault(label["scenario"], Counter())
            start = label["start"] - manifest["audio_t0"]
            stop = label["end"] - manifest["audio_t0"]
            for index in range(len(audio) // 640):
                if not start <= 0.02 + 0.04 * index < stop:
                    continue
                p = predictions.get((track, index))
                key = (
                    "unknown"
                    if p is None
                    else ("tp" if label["speaking"] else "fp")
                    if p >= 0.5
                    else ("fn" if label["speaking"] else "tn")
                )
                count[key] += 1
                scenario[key] += 1
        total = sum(counts.values(), Counter())
        scored = sum(total[k] for k in ("tp", "fp", "tn", "fn"))
        runs.append(
            dict(
                offset_secs=offset,
                tracks={k: metrics(v) for k, v in counts.items()},
                scenarios={k: metrics(v) for k, v in scenarios.items()},
                **metrics(total),
                sample_coverage=scored / (scored + total["unknown"])
                if scored + total["unknown"]
                else 0,
                windows_scored=windows,
                windows_skipped=dict(skipped),
                latency_ms={
                    f"p{q}": float(np.percentile(latencies, q)) if latencies else None
                    for q in (50, 95)
                },
            )
        )
    best = max(
        runs, key=lambda r: (r["f1"], r["sample_coverage"], -abs(r["offset_secs"]))
    )
    # An offset chosen from all-zero F1 is noise; never hand it to held-out.
    selected, reason = (
        (best["offset_secs"], "highest F1, then coverage, then smallest |offset|")
        if best["tp"]
        else (None, "no offset produced a true positive; nothing to freeze")
    )
    return dict(
        version=1,
        split=manifest["split"],
        enhancer=manifest["enhancer"],
        selected_offset_secs=selected,
        selection_reason=reason,
        model_hash=getattr(detector, "manifest", {}).get("artifact_sha256"),
        preprocessing_version="light-asd-mfcc100-crop112-v1",
        gate_comparison="unavailable: requires face/MAR, stream and diarizer receipt/decision evidence",
        runs=runs,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--offset-sweep", action="store_true")
    group.add_argument("--offset-secs", type=float)
    parser.add_argument(
        "--model",
        default=str(Path.home() / ".cache/openjarvis/light_asd/light_asd.onnx"),
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text())
    inputs = [
        manifest_path,
        *(manifest_path.parent / manifest[k] for k in ("audio_wav", "crops_npz")),
    ]
    if Path(args.output).resolve() in [p.resolve() for p in inputs]:
        parser.error("output must not overwrite fixture inputs")
    from Visual.infrastructure.active_speaker.light_asd import LightASD

    report = replay(
        args.manifest,
        LightASD(args.model, device=args.device),
        offset_sweep=args.offset_sweep,
        offset_secs=args.offset_secs,
    )
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
