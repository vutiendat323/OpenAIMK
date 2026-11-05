"""Separate VAE reconstruction loss from mouth synthesis and precision effects.

Offline only: compare identical source frames, prepared latents, masks and audio.
The reconstruction control does NOT perform lipsync and must never be deployed.
"""

import argparse
import json
import os
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = (0, 15, 25, 40, 60, 85, 120, 180)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--crop-check", action="store_true")
    args = parser.parse_args()
    info = json.loads(args.prepared.read_text())
    baseline = args.baseline.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    dataset = Path(info["dataset"])
    checkout = ROOT / ".runtime/LiveTalking"
    os.chdir(checkout)
    sys.path[:0] = [str(ROOT), str(checkout)]
    from render_musetalk_review import wait_for_idle

    wait_for_idle()
    import cv2
    import numpy as np
    import torch
    from avatars.audio_features.whisper import WhisperASR
    from avatars.musetalk.models.unet import PositionalEncoding, UNet
    from avatars.musetalk.models.vae import VAE
    from avatars.musetalk.utils.blending import get_image_blending, get_image_prepare_material
    from avatars.musetalk.whisper.audio2feature import Audio2Feature
    from avatars.wav2lip import audio
    from PIL import Image, ImageDraw

    torch.set_num_threads(4)
    torch.set_grad_enabled(False)
    torch.manual_seed(7)
    # Keep Whisper identical to the baseline. Only UNet/VAE/PE precision changes.
    processor = Audio2Feature(model_path="models/whisper")
    speech = audio.load_wav(str(Path(info["staging"]) / "source.wav"), 16000)
    features = processor.audio2feat(speech)
    del processor
    torch.cuda.empty_cache()
    asr = WhisperASR.__new__(WhisperASR)
    chunks = asr._feature2chunks(
        features, batch_size=info["frames"], audio_feat_win=[2, 3], feature_idx_multiplier=2
    )
    vae = VAE(model_path="models/sd-vae", use_float16=False)
    unet = UNet(
        unet_config="models/musetalkV15/musetalk.json",
        model_path="models/musetalkV15/unet.pth",
        device="cpu",
    )
    unet.model = unet.model.eval().float().cuda()
    pe = PositionalEncoding(d_model=384).float().cuda()
    coords = pickle.loads((dataset / "coords.pkl").read_bytes())
    boxes = pickle.loads((dataset / "mask_coords.pkl").read_bytes())
    latents = torch.load(dataset / "latents.pt", map_location="cpu", weights_only=True)
    face_parser = None
    if args.crop_check:
        from avatars.musetalk.utils.face_parsing import FaceParsing

        face_parser = FaceParsing(left_cheek_width=90, right_cheek_width=90)
    rows = []
    for i in SAMPLES:
        wait_for_idle()
        source = cv2.imread(str(dataset / "full_imgs" / f"{i:08d}.png"))
        previous = cv2.imread(str(baseline / "source" / f"{i:08d}.png"))
        if source is None or previous is None or source.shape != previous.shape:
            raise ValueError(f"Missing or mismatched baseline frame {i}")
        latent = latents[i].float().cuda()
        whisper = torch.as_tensor(np.asarray([chunks[i]]), device="cuda", dtype=torch.float32)
        prediction = unet.model(
            latent, torch.tensor([0], device="cuda"), encoder_hidden_states=pe(whisper)
        ).sample
        synthesized = vae.decode_latents(prediction)[0]
        reconstruction = vae.decode_latents(latent[:, 4:])[0]
        mask = cv2.imread(str(dataset / "mask" / f"{i:08d}.png"))
        x1, y1, x2, y2 = map(int, coords[i])

        composited = []
        for face in (reconstruction, synthesized):
            resized = cv2.resize(face, (x2 - x1, y2 - y1))
            composited.append(get_image_blending(source, resized, coords[i], mask, boxes[i]))
        reconstructed, generated = composited
        bounds = (x1 - 40, max(0, y1 - 60), x2 + 40, y2 + 30)
        sheet = Image.new("RGB", (1200, 420), "white")
        draw = ImageDraw.Draw(sheet)
        for col, (title, frame) in enumerate(
            [
                ("Source", source),
                ("VAE control (NOT lipsync)", reconstructed),
                ("MuseTalk FP16 (previous)", previous),
                ("MuseTalk FP32", generated),
            ]
        ):
            tile = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).crop(bounds)
            tile.thumbnail((300, 375))
            sheet.paste(tile, (col * 300 + (300 - tile.width) // 2, 35))
            draw.text((col * 300 + 4, 6), title, fill="black")
            draw.text((col * 300 + 4, 20), f"{i / 25:.2f}s", fill="black")
        sheet.save(out / f"diagnostic-{i:03d}.png")
        cv2.imwrite(str(out / f"fp32-{i:03d}.png"), generated)
        if face_parser is not None:
            crop_sheet = Image.new("RGB", (1200, 420), "white")
            crop_draw = ImageDraw.Draw(crop_sheet)
            comparisons = [("Source", source)]
            for margin in (0, 10, 20):
                wait_for_idle()
                # Native v15 baseline includes extra_margin=10 in stored coordinates.
                bottom = min(source.shape[0], y2 - info["extra_margin"] + margin)
                face_box = (x1, y1, x2, bottom)
                crop = cv2.resize(
                    source[y1:bottom, x1:x2], (256, 256), interpolation=cv2.INTER_LANCZOS4
                )
                # Pair the same VAE sampling noise across these crop experiments.
                torch.manual_seed(7 + i)
                trial_latent = vae.get_latents_for_unet(crop)
                trial_prediction = unet.model(
                    trial_latent,
                    torch.tensor([0], device="cuda"),
                    encoder_hidden_states=pe(whisper),
                ).sample
                face = cv2.resize(vae.decode_latents(trial_prediction)[0], (x2 - x1, bottom - y1))
                trial_mask, trial_box = get_image_prepare_material(
                    source, face_box, fp=face_parser, mode="jaw"
                )
                frame = get_image_blending(source, face, face_box, trial_mask, trial_box)
                comparisons.append((f"Chin margin {margin}px (FP32)", frame))
            for col, (title, frame) in enumerate(comparisons):
                tile = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).crop(bounds)
                tile.thumbnail((300, 375))
                crop_sheet.paste(tile, (col * 300 + (300 - tile.width) // 2, 35))
                crop_draw.text((col * 300 + 4, 6), title, fill="black")
                crop_draw.text((col * 300 + 4, 20), f"{i / 25:.2f}s", fill="black")
            crop_sheet.save(out / f"crop-check-{i:03d}.png")
        # Lower-face crop: this pixel difference measures numerical change only,
        # not naturalness, sync accuracy or perceptual quality.
        region = (slice((y1 + y2) // 2, y2), slice(x1, x2))
        difference = np.abs(generated[region].astype(float) - previous[region].astype(float))
        rows.append(
            dict(frame=i, seconds=i / 25, fp16_fp32_lower_face_mae=float(difference.mean()))
        )
        print(json.dumps(rows[-1]), flush=True)
    (out / "diagnosis.json").write_text(
        json.dumps(
            dict(
                source_sha256=info["source_sha256"],
                samples=rows,
                precision="float32 UNet, VAE and PE; same float16-prepared latents/Whisper",
                metric="Mean absolute RGB difference, 0..255; NOT a quality score",
                reconstruction_control="Reference VAE decode only; NOT audio-driven lipsync",
                crop_check_margins=[0, 10, 20] if args.crop_check else [],
                crop_check_seed="7 + frame index, same seed for each margin",
                activated=False,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
