#!/usr/bin/env python3
"""Offline Light-ASD exporter: upstream checkpoint -> one ONNX artifact + manifest.

    python3 tools/export_light_asd.py --source-repo REPO --checkpoint FILE --output FILE.onnx

Loads only ``model.Model.ASD_Model`` and the checkpoint's ``lossAV.FC``
classifier from the pinned upstream checkout at ``--source-repo`` -- never
the training ``ASD`` class (it builds CUDA modules and an optimizer) and
never ``lossV`` (training-only visual head).  torch and the upstream source
tree are needed only here, at export time; the deployed runtime provider
(vision/infrastructure/active_speaker/light_asd.py) never imports either.

Run from the vision repo with the system Python (torch, onnx and
onnxruntime are already installed there); no extra install needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import onnxruntime as ort
import torch
from torch import nn

PINNED_REVISION = "ed38c232de5efe0261dbd68627c0ade7cdfe14eb"
MAX_PARITY_ERROR = 1e-4


def export_probabilities(logits: torch.Tensor) -> torch.Tensor:
    """The exported model's output: softmax(logits, dim=-1)[:, 1]."""
    return torch.softmax(logits, dim=-1)[:, 1]


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_checkpoint_state(checkpoint_path: str, expected_sha256: str | None = None) -> dict:
    """The checkpoint's raw state dict, refusing a byte-altered file."""
    actual = _sha256(checkpoint_path)
    if expected_sha256 is not None and actual != expected_sha256:
        raise ValueError(
            f"checkpoint sha256 mismatch for {checkpoint_path}: "
            f"expected {expected_sha256}, got {actual}")
    state = torch.load(checkpoint_path, map_location="cpu")
    if not isinstance(state, dict):
        raise ValueError(f"unexpected checkpoint format in {checkpoint_path}: not a state dict")
    return state


def split_checkpoint(state: dict) -> tuple[dict, dict]:
    """(asd_model_state, classifier_state), keys de-prefixed and validated.

    Normalizes one leading ``module.`` (DataParallel), then requires every
    key to fall under ``model.`` (ASD_Model) or ``lossAV.`` (the AV
    classifier); ``lossV.*`` (training-only visual head) is dropped.  Any
    other prefix, or a missing classifier weight, is a hard failure.
    """
    if any(k.startswith("module.") for k in state):
        state = {k[len("module."):] if k.startswith("module.") else k: v
                  for k, v in state.items()}

    asd_state: dict = {}
    classifier_state: dict = {}
    for key, value in state.items():
        prefix, _, rest = key.partition(".")
        if prefix == "model":
            asd_state[rest] = value
        elif prefix == "lossAV":
            classifier_state[rest] = value
        elif prefix == "lossV":
            continue
        else:
            raise ValueError(f"unexpected checkpoint key: {key}")

    if "FC.weight" not in classifier_state or "FC.bias" not in classifier_state:
        raise ValueError("missing classifier weight: expected lossAV.FC.weight and lossAV.FC.bias")
    return asd_state, classifier_state


def load_state_dict_strict(module: nn.Module, state: dict, label: str) -> None:
    """Strict ``load_state_dict``, wrapped so a missing/mismatched weight is a ValueError."""
    try:
        module.load_state_dict(state, strict=True)
    except RuntimeError as e:
        raise ValueError(f"{label} checkpoint does not match: {e}") from e


class _Classifier(nn.Module):
    """Upstream ``lossAV``'s inference path: one Linear(128, 2), named ``FC``
    to match the checkpoint's ``lossAV.FC.{weight,bias}`` keys."""

    def __init__(self):
        super().__init__()
        self.FC = nn.Linear(128, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.FC(x)


class _ExportWrapper(nn.Module):
    """Audio + video in, 25 per-frame speaking probabilities out."""

    def __init__(self, asd_model: nn.Module, classifier: nn.Module):
        super().__init__()
        self.asd_model = asd_model
        self.classifier = classifier

    def forward(self, audio: torch.Tensor, visual: torch.Tensor) -> torch.Tensor:
        audio_embed = self.asd_model.forward_audio_frontend(audio)
        visual_embed = self.asd_model.forward_visual_frontend(visual)
        backend = self.asd_model.forward_audio_visual_backend(audio_embed, visual_embed)
        logits = self.classifier(backend)
        return export_probabilities(logits)


def _make_maxpool3d_export_safe(audio_encoder: nn.Module) -> None:
    """Give every ``nn.MaxPool3d`` in the audio encoder an unambiguous 5-D input.

    ``audio_encoder`` calls ``MaxPool3d`` on a 4-D (B, C, H, W) tensor;
    PyTorch's implicit "unbatched" rule then reads it as (C, D, H, W), which
    happens to give the right numbers only because B is always 1 here, but
    it makes the TorchScript ONNX exporter emit a MaxPool node whose
    dilations/strides attributes don't match the traced rank (fails to load
    in onnxruntime).  In-place, insert-then-drop a dummy depth axis makes the
    call unambiguously 5-D; verified bit-identical to the original 4-D call
    for the actual runtime shapes (see task-1-report.md).  ``visualEncoder``'s
    MaxPool3d already gets a genuine 5-D (B, C, T, H, W) tensor and must not
    be touched.  This only patches our own instantiated ``ASD_Model`` object,
    never the upstream checkout.
    """
    for module in audio_encoder.modules():
        if isinstance(module, nn.MaxPool3d):
            orig_forward = module.forward  # bound method, captured before overwrite

            def patched_forward(x, _orig=orig_forward):
                return _orig(x.unsqueeze(2)).squeeze(2)

            module.forward = patched_forward


def _git_head(source_repo: str) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source_repo, text=True).strip()


def build_wrapper(source_repo: str, checkpoint_path: str,
                   expected_checkpoint_sha256: str | None = None) -> nn.Module:
    """The eager model to export: upstream ASD_Model + the checkpoint's AV classifier."""
    state = load_checkpoint_state(checkpoint_path, expected_checkpoint_sha256)
    asd_state, classifier_state = split_checkpoint(state)

    if source_repo not in sys.path:
        sys.path.insert(0, source_repo)
    from model.Model import ASD_Model  # upstream; never the training ASD() class

    asd_model = ASD_Model()
    load_state_dict_strict(asd_model, asd_state, "model")
    _make_maxpool3d_export_safe(asd_model.audioEncoder)
    classifier = _Classifier()
    load_state_dict_strict(classifier, classifier_state, "classifier")

    asd_model.eval()
    classifier.eval()
    return _ExportWrapper(asd_model, classifier)


def export_onnx(wrapper: nn.Module, output_path: str) -> None:
    """Fixed-shape ONNX export: audio (1,100,13) + visual (1,25,112,112) -> (25,)."""
    audio = torch.zeros(1, 100, 13, dtype=torch.float32)
    visual = torch.zeros(1, 25, 112, 112, dtype=torch.float32)
    with torch.no_grad():
        torch.onnx.export(
            wrapper, (audio, visual), output_path,
            input_names=["audio", "visual"], output_names=["probabilities"],
            opset_version=17, dynamo=False)  # avoid the dynamo path's onnxscript dependency
    # The legacy exporter's eval-mode context manager does not reliably restore
    # BatchNorm submodules to eval() afterward -- leaving it as train() would
    # make a later eager call (verify_parity's reference) use batch statistics
    # instead of the checkpoint's running stats, which is not the deployed
    # model's behavior at all.
    wrapper.eval()


def verify_parity(wrapper: nn.Module, onnx_path: str, seed: int = 0) -> dict:
    """Eager vs. ONNX on one seeded nonconstant input pair."""
    torch.manual_seed(seed)
    audio = torch.randn(1, 100, 13, dtype=torch.float32)
    visual = (torch.rand(1, 25, 112, 112) * 255).to(torch.float32)

    with torch.no_grad():
        eager = wrapper(audio, visual).numpy().reshape(-1)

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    onnx_probs = session.run(None, {"audio": audio.numpy(), "visual": visual.numpy()})[0]
    onnx_probs = np.asarray(onnx_probs, dtype=np.float32).reshape(-1)

    return {
        "seed": seed,
        "max_abs_error": float(np.max(np.abs(eager - onnx_probs))),
        "num_probabilities": int(onnx_probs.shape[0]),
        "all_finite": bool(np.isfinite(onnx_probs).all()),
        "in_unit_interval": bool(((onnx_probs >= 0.0) & (onnx_probs <= 1.0)).all()),
    }


def build_manifest(source_revision: str, checkpoint_path: str, checkpoint_sha256: str,
                    artifact_path: str, parity: dict) -> dict:
    return {
        "model": "light_asd",
        "source_revision": source_revision,
        "checkpoint_path": os.path.basename(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256,
        "artifact_sha256": _sha256(artifact_path),
        "preprocessing": {
            "audio": {
                "sample_rate": 16000, "pad_samples": 240, "numcep": 13,
                "winlen": 0.025, "winstep": 0.01,
                "library": "python_speech_features==0.6",
            },
            "video": {
                "frames": 25, "height": 112, "width": 112,
                "dtype": "uint8 raw intensity 0..255 -> float32; normalization inside the graph",
            },
        },
        "output": {
            "shape": [25], "dtype": "float32",
            "meaning": "softmax(logits, dim=-1)[:, 1] per consecutive 40ms bin",
        },
        "export_parity": parity,
        "license": "Light-ASD upstream: MIT (Liao Junhua). Weights kept local, never redistributed.",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-repo", required=True, help="pinned Light-ASD checkout")
    parser.add_argument("--checkpoint", required=True, help="finetuning_TalkSet.model or equivalent")
    parser.add_argument("--output", required=True, help="output .onnx path")
    args = parser.parse_args(argv)

    revision = _git_head(args.source_repo)
    if revision != PINNED_REVISION:
        raise SystemExit(f"{args.source_repo} is at {revision}, expected pinned {PINNED_REVISION}")

    checkpoint_sha256 = _sha256(args.checkpoint)
    wrapper = build_wrapper(args.source_repo, args.checkpoint)

    export_onnx(wrapper, args.output)
    parity = verify_parity(wrapper, args.output)
    if (parity["max_abs_error"] > MAX_PARITY_ERROR
            or not parity["all_finite"] or not parity["in_unit_interval"]):
        raise SystemExit(f"export parity check failed: {parity}")

    manifest = build_manifest(revision, args.checkpoint, checkpoint_sha256, args.output, parity)
    manifest_path = args.output + ".json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
