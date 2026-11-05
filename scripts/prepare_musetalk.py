"""Prepare MuseTalk latents from the validated local face crops."""

import json
import os
import pickle
from functools import lru_cache

MODEL_FILES = (
    (
        "TMElyralab/MuseTalk",
        "2bcb936e2fddb4d86db4c62fd45b387d0c061571",
        "musetalkV15",
        ("musetalk.json", "unet.pth"),
    ),
    (
        "stabilityai/sd-vae-ft-mse",
        "31f26fdeee1355a5c34592e401dd41e45d25a493",
        "sd-vae",
        ("config.json", "diffusion_pytorch_model.safetensors"),
    ),
    (
        "openai/whisper-tiny",
        "169d4a4341b33bc18d8881c4b69c2e104e1cc0af",
        "whisper",
        ("config.json", "model.safetensors", "preprocessor_config.json"),
    ),
)


def ensure_models(checkout):
    from huggingface_hub import hf_hub_download

    for repo, revision, folder, names in MODEL_FILES:
        for name in names:
            destination = checkout / "models" / folder / name
            if destination.is_file():
                continue
            upstream_name = f"{folder}/{name}" if folder == "musetalkV15" else name
            local_dir = checkout / "models" if folder == "musetalkV15" else destination.parent
            hf_hub_download(repo, upstream_name, revision=revision, local_dir=local_dir)


@lru_cache(maxsize=1)
def preparation_vae(checkout):
    from avatars.musetalk.models.vae import VAE

    vae = VAE(model_path=str(checkout / "models/sd-vae"))
    vae.vae = vae.vae.half().eval()
    return vae


def convert_avatar(avatar_id, checkout):
    import cv2
    import numpy as np
    import torch

    from trendcoffee.avatar_composite import _mouth_mask

    source = checkout / "data/avatars" / avatar_id
    destination = source.with_name(avatar_id + "_muse15")
    metadata = destination / "source.json"
    if metadata.exists():
        return destination.name
    ensure_models(checkout)
    vae = preparation_vae(checkout)
    for folder in ("full_imgs", "mask"):
        (destination / folder).mkdir(parents=True, exist_ok=True)
    coords = pickle.loads((source / "coords.pkl").read_bytes())
    latents, boxes = [], []
    torch.manual_seed(7)
    with torch.inference_mode():
        for index, (y1, y2, x1, x2) in enumerate(coords):
            filename = f"{index:08d}.png"
            full = destination / "full_imgs" / filename
            if not full.exists():
                os.link(source / "full_imgs" / filename, full)
            crop = cv2.imread(str(source / "face_imgs" / filename))
            latents.append(vae.get_latents_for_unet(crop).cpu())
            mask = np.rint(_mouth_mask(y2 - y1, x2 - x1) * 255).astype(np.uint8)
            cv2.imwrite(str(destination / "mask" / filename), np.repeat(mask, 3, axis=2))
            boxes.append((x1, y1, x2, y2))
    torch.save(latents, destination / "latents.pt")
    for name in ("coords.pkl", "mask_coords.pkl"):
        (destination / name).write_bytes(pickle.dumps(boxes))
    metadata.write_text(
        json.dumps({"source_avatar": avatar_id, "engine": "musetalk", "frames": len(boxes)})
    )
    print(f"Prepared {destination.name}: {len(boxes)} frames", flush=True)
    return destination.name
