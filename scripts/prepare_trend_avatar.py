"""Prepare both user clips using upstream Wav2Lip's own avatar builder.

Runs in the prepared livetalking-venv. Originals are never modified.
"""

import argparse
import hashlib
import json
import os
import pickle
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def prepare(source, kind, width, checkout):
    digest = hashlib.sha256(source.read_bytes() + str(width).encode()).hexdigest()[:12]
    avatar_id = f"trend_{kind}_{digest}"
    destination = checkout / "data/avatars" / avatar_id
    metadata = destination / "source.json"
    if not metadata.exists():
        staging = ROOT / ".runtime/trend-avatar"
        staging.mkdir(parents=True, exist_ok=True)
        video = staging / f"{avatar_id}.mkv"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(source),
                "-an",
                "-vf",
                f"fps=25,scale={width}:-2",
                "-c:v",
                "ffv1",
                str(video),
            ],
            check=True,
        )
        # Keep the supplied audio as a local QA fixture; conversation still uses native voice.
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(source),
                "-vn",
                "-ar",
                "48000",
                "-ac",
                "1",
                str(staging / f"{kind}-source.wav"),
            ],
            check=True,
        )
        env = {
            **os.environ,
            "PYTHONPATH": str(checkout),
            "TORCH_HOME": str(ROOT / ".runtime/torch"),
        }
        subprocess.run(
            [
                sys.executable,
                "-m",
                "avatars.wav2lip.genavatar",
                "--video_path",
                str(video),
                "--avatar_id",
                avatar_id,
                "--img_size",
                "256",
                "--face_det_batch_size",
                "2",
            ],
            cwd=checkout,
            env=env,
            check=True,
        )
        with (destination / "coords.pkl").open("rb") as handle:
            coords = pickle.load(handle)  # trusted output of the local upstream builder
        if not coords or any(x1 == 0 and x2 >= width for y1, y2, x1, x2 in coords):
            raise RuntimeError(f"Face detection failed for {kind}; avatar was not activated")
        metadata.write_text(
            json.dumps({"source": source.name, "hash": digest, "frames": len(coords)})
        )
    info = json.loads(metadata.read_text())
    return avatar_id, info["frames"]


def build_manifest(
    talking, talk_count, wave, wave_count, *, width, idle_source, engine="wav2lip", decoder="torch"
):
    if idle_source not in ("talking", "wave") or min(talk_count, wave_count) < 1:
        raise ValueError("invalid_avatar_sources")
    if engine not in ("wav2lip", "musetalk") or decoder not in ("torch", "tensorrt"):
        raise ValueError("invalid_avatar_engine")
    return {
        "engine": engine,
        "decoder": decoder,
        "batch_size": 8 if engine == "musetalk" and decoder == "torch" else 4,
        "avatar_id": talking,
        "wave_avatar_id": wave,
        "fps": 25,
        "width": width,
        "talking_frames": talk_count,
        "wave_frames": wave_count,
        "idle_source": idle_source,
        "idle_range": [0, talk_count if idle_source == "talking" else min(18, wave_count)],
        "smile_range": [max(0, wave_count - 35), wave_count],
        "poster": "/avatars/trend-live.png",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--talking", type=Path, required=True)
    parser.add_argument("--wave", type=Path, required=True)
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--engine", choices=("wav2lip", "musetalk"), default="wav2lip")
    parser.add_argument("--decoder", choices=("torch", "tensorrt"), default="torch")
    parser.add_argument("--manifest", type=Path, default=ROOT / ".runtime/trend-avatar.json")
    parser.add_argument(
        "--idle-source",
        choices=("talking", "wave"),
        default="wave",
        help="Use talking for a neutral closed-mouth source shared by idle and speech.",
    )
    args = parser.parse_args()
    checkout = ROOT / ".runtime/LiveTalking"
    talking, talk_count = prepare(args.talking.resolve(), "talking", args.width, checkout)
    wave, wave_count = prepare(args.wave.resolve(), "wave", args.width, checkout)
    if args.engine == "musetalk":
        sys.path[:0] = [str(ROOT), str(checkout)]
        from scripts.prepare_musetalk import convert_avatar

        talking = convert_avatar(talking, checkout)
        wave = convert_avatar(wave, checkout)
    manifest = build_manifest(
        talking,
        talk_count,
        wave,
        wave_count,
        width=args.width,
        idle_source=args.idle_source,
        engine=args.engine,
        decoder=args.decoder,
    )
    poster = ROOT / "frontend/public/avatars/trend-live.png"
    poster_source = talking if args.idle_source == "talking" else wave
    shutil.copyfile(checkout / "data/avatars" / poster_source / "full_imgs/00000000.png", poster)
    path = args.manifest
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2))
    temporary.replace(path)
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
