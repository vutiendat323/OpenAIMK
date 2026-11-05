"""Prepare a separate MuseTalk v1.5 avatar using LiveTalking's native generator.

Run with the avatar interpreter and CUDA_VISIBLE_DEVICES='' for CPU preparation.
This command never writes the kiosk manifest or poster.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    avatar = f"trend_muse_native_{digest}"
    checkout = ROOT / ".runtime/LiveTalking"
    staging = ROOT / ".runtime/muse-native" / digest
    frames = staging / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            "fps=25",
            "-start_number",
            "0",
            str(frames / "%08d.png"),
        ],
        check=True,
    )
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
            "16000",
            "-ac",
            "1",
            str(staging / "source.wav"),
        ],
        check=True,
    )
    os.environ.setdefault("TORCH_HOME", str(ROOT / ".runtime/torch"))
    os.chdir(checkout)
    sys.path.insert(0, str(checkout))
    import torch

    torch.set_num_threads(4)
    from render_musetalk_review import wait_for_idle

    wait_for_idle()
    from avatars.musetalk.genavatar import generate_avatar
    from avatars.musetalk.utils import preprocessing

    detect = preprocessing.fa.get_detections_for_batch

    def idle_detection(*args, **kwargs):
        wait_for_idle()
        return detect(*args, **kwargs)

    preprocessing.fa.get_detections_for_batch = idle_detection

    generate_avatar(
        str(frames),
        avatar,
        bbox_shift=0,
        extra_margin=10,
        parsing_mode="jaw",
        version="v15",
        progress_callback=lambda n: print(f"preparation {n}%", flush=True) if n % 10 == 0 else None,
    )
    destination = checkout / "data/avatars" / avatar
    import pickle

    coords = pickle.loads((destination / "coords.pkl").read_bytes())
    expected = len(list(frames.glob("*.png")))
    latents = torch.load(destination / "latents.pt", map_location="cpu", weights_only=True)
    masks = list((destination / "mask").glob("*.png"))
    if len(coords) != expected or len(latents) != expected or len(masks) != expected:
        raise RuntimeError("Incomplete native avatar preparation")
    if any(x2 <= x1 or y2 <= y1 for x1, y1, x2, y2 in coords):
        raise RuntimeError("Invalid native face box")
    report = dict(
        source=source.name,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        avatar_id=avatar,
        frames=expected,
        fps=25,
        pipeline="LiveTalking MuseTalk v15 native",
        bbox_shift=0,
        extra_margin=10,
        parsing_mode="jaw",
        activated=False,
        staging=str(staging),
        dataset=str(destination),
    )
    (staging / "prepared.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
