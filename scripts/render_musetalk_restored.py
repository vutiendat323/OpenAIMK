"""Render and measure the local mouth-detail fix on recorded audio/video fixtures."""

import argparse
import json
import os
import pickle
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def encode(directory, audio, output, count):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-framerate",
            "25",
            "-i",
            str(directory / "%08d.png"),
            "-i",
            str(audio),
            "-t",
            str(count / 25),
            "-c:v",
            "libopenh264",
            "-b:v",
            "6000000",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    info = json.loads(args.prepared.read_text())
    os.environ.setdefault("TORCHINDUCTOR_CACHE_DIR", str(ROOT / ".runtime/torchinductor"))
    from render_musetalk_review import wait_for_idle

    wait_for_idle()
    import cv2
    import numpy as np
    import torch
    from livetalking_restore import MouthDetailRestorer
    from PIL import Image, ImageDraw

    torch.set_num_threads(4)
    torch.set_grad_enabled(False)
    restorer = MouthDetailRestorer()
    points = np.load(args.landmarks)
    dataset = Path(info["dataset"])
    coords = pickle.loads((dataset / "coords.pkl").read_bytes())
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for label, wav in [
        ("source", Path(info["staging"]) / "source.wav"),
        ("greeting", ROOT / "frontend/public/voice/default/greeting.wav"),
    ]:
        files = sorted((args.input / label).glob("*.png"))
        if not files or len(files) > len(points):
            raise ValueError("missing_or_mismatched_render_frames")
        frames_out = output / label
        compare_out = output / f"{label}-comparison"
        frames_out.mkdir(exist_ok=True)
        compare_out.mkdir(exist_ok=True)
        durations = []
        for i, path in enumerate(files):
            wait_for_idle()
            frame = cv2.imread(str(path))
            source = cv2.imread(str(dataset / "full_imgs" / f"{i:08d}.png"))
            baseline = cv2.imread(str(args.baseline / label / f"{i:08d}.png"))
            if frame is None or source is None or baseline is None:
                raise ValueError(f"incomplete_review_frame_{i}")
            started = time.monotonic()
            result = restorer.restore(frame, points[i])
            elapsed = time.monotonic() - started
            if i == 0:
                repeated = restorer.restore(frame, points[i])
                if not np.array_equal(result, repeated):
                    raise RuntimeError("nondeterministic_restoration")
            else:
                durations.append(elapsed * 1000)
            cv2.imwrite(str(frames_out / f"{i:08d}.png"), result)
            x1, y1, x2, y2 = map(int, coords[i])
            bounds = (x1 - 40, max(0, y1 - 60), x2 + 40, y2 + 30)
            sheet = Image.new("RGB", (900, 410), "white")
            draw = ImageDraw.Draw(sheet)
            for col, (title, image) in enumerate(
                [("Source", source), ("Previous MuseTalk", baseline), ("Mouth detail fix", result)]
            ):
                tile = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).crop(bounds)
                tile.thumbnail((300, 375))
                sheet.paste(tile, (col * 300 + (300 - tile.width) // 2, 30))
                draw.text((col * 300 + 5, 8), f"{title} / {i / 25:.2f}s", fill="black")
            sheet.save(compare_out / f"{i:08d}.png")
            if i % 25 == 0:
                print(label, i, "/", len(files), "restore_ms", round(elapsed * 1000, 2), flush=True)
        encode(frames_out, wav, output / f"{label}-restored.mp4", len(files))
        encode(compare_out, wav, output / f"{label}-comparison.mp4", len(files))
        reports.append(
            dict(
                label=label,
                frames=len(files),
                restoration_ms_median=float(np.median(durations)),
                restoration_ms_p95=float(np.percentile(durations, 95)),
                deterministic_repeat=True,
            )
        )
    (output / "render.json").write_text(
        json.dumps(
            dict(
                preparation=info,
                reports=reports,
                strength=0.75,
                noise="fixed",
                color="low frequencies retained from MuseTalk output",
                timing_scope="restoration/alignment/compositing only; excludes MuseTalk inference",
                activated=False,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
