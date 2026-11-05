"""Render prepared native MuseTalk assets offline; pause GPU batches for active kiosk guests."""

import argparse
import json
import math
import os
import pickle
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wait_for_idle():
    while True:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8080/api/kiosk/status", timeout=2
            ) as response:
                active = json.load(response).get("session_active", False)
        except OSError:
            active = False
        if not active:
            return
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    info = json.loads(args.prepared.read_text())
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    checkout = ROOT / ".runtime/LiveTalking"
    os.chdir(checkout)
    sys.path[:0] = [str(ROOT), str(checkout)]
    wait_for_idle()
    import cv2
    import numpy as np
    import torch
    from avatars.audio_features.whisper import WhisperASR
    from avatars.musetalk.models.unet import PositionalEncoding, UNet
    from avatars.musetalk.models.vae import VAE
    from avatars.musetalk.utils.blending import get_image_blending
    from avatars.musetalk.whisper.audio2feature import Audio2Feature
    from avatars.wav2lip import audio
    from PIL import Image, ImageDraw

    torch.set_num_threads(4)
    torch.set_grad_enabled(False)
    torch.manual_seed(7)
    vae = VAE(model_path="models/sd-vae", use_float16=True)
    unet = UNet(
        unet_config="models/musetalkV15/musetalk.json",
        model_path="models/musetalkV15/unet.pth",
        device="cpu",
    )
    unet.model = unet.model.eval().half().cuda()
    pe = PositionalEncoding(d_model=384).half().cuda()
    processor = Audio2Feature(model_path="models/whisper")
    asr = WhisperASR.__new__(WhisperASR)
    dataset = Path(info["dataset"])
    coords = pickle.loads((dataset / "coords.pkl").read_bytes())
    boxes = pickle.loads((dataset / "mask_coords.pkl").read_bytes())
    latents = torch.load(dataset / "latents.pt", map_location="cpu", weights_only=True)
    reports = []
    for label, wav in [
        ("source", Path(info["staging"]) / "source.wav"),
        ("greeting", ROOT / "frontend/public/voice/default/greeting.wav"),
    ]:
        wait_for_idle()
        speech = audio.load_wav(str(wav), 16000)
        count = min(len(coords), math.ceil(len(speech) / 16000 * 25))
        features = processor.audio2feat(speech)
        chunks = asr._feature2chunks(
            features, batch_size=count, audio_feat_win=[2, 3], feature_idx_multiplier=2
        )
        directory = out / label
        directory.mkdir(exist_ok=True)
        started = time.monotonic()
        for start in range(0, count, 4):
            indices = list(range(start, min(start + 4, count)))
            if all((directory / f"{i:08d}.png").exists() for i in indices):
                continue
            wait_for_idle()
            batch = torch.cat([latents[i] for i in indices]).half().cuda()
            whisper = torch.as_tensor(
                np.asarray([chunks[i] for i in indices]), device="cuda", dtype=torch.float16
            )
            prediction = unet.model(
                batch, torch.tensor([0], device="cuda"), encoder_hidden_states=pe(whisper)
            ).sample
            faces = vae.decode_latents(prediction)
            for i, face in zip(indices, faces, strict=True):
                source = cv2.imread(str(dataset / "full_imgs" / f"{i:08d}.png"))
                x1, y1, x2, y2 = coords[i]
                face = cv2.resize(face, (x2 - x1, y2 - y1))
                mask = cv2.imread(str(dataset / "mask" / f"{i:08d}.png"))
                result = get_image_blending(source, face, coords[i], mask, boxes[i])
                cv2.imwrite(str(directory / f"{i:08d}.png"), result)
                if i in [0, 15, 25, 40, 60, 85, 120, 180]:
                    sheet = Image.new("RGB", (600, 410), "white")
                    draw = ImageDraw.Draw(sheet)
                    bounds = (x1 - 40, max(0, y1 - 60), x2 + 40, y2 + 30)
                    for col, (title, im) in enumerate(
                        [("Source", source), ("MuseTalk native preparation", result)]
                    ):
                        tile = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB)).crop(bounds)
                        tile.thumbnail((300, 375))
                        sheet.paste(tile, (300 * col + (300 - tile.width) // 2, 30))
                        draw.text((col * 300 + 5, 8), f"{title} / {i / 25:.2f}s", fill="black")
                    sheet.save(out / f"{label}-compare-{i:03d}.jpg")
            print(label, start + len(indices), "/", count, flush=True)
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
                str(wav),
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
                str(out / f"{label}-musetalk.mp4"),
            ],
            check=True,
        )
        reports.append(
            dict(
                audio=label,
                frames=count,
                seconds=count / 25,
                render_wall_seconds=round(time.monotonic() - started, 2),
            )
        )
    (out / "render.json").write_text(
        json.dumps(dict(preparation=info, renders=reports, activated=False), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
