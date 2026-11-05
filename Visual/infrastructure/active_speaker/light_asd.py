"""Light-ASD active-speaker detection: ONNX Runtime provider (CPU or CUDA).

The exported ONNX graph already contains the model's own audio/visual
frontends and the softmax classifier (see tools/export_light_asd.py); this
module only prepares its two inputs and validates the artifact + manifest
pair written at export time.  It never imports the upstream Light-ASD
checkout or torch -- that belongs to the exporter, at export time only.
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import onnxruntime as ort

# Fixed preprocessing contract (spec section 5): one 1.0 s / 16 kHz window,
# 240 zero samples appended before framing so the MFCC gives exactly 100 rows.
_SAMPLE_RATE = 16000
_PAD_SAMPLES = 240
_NUM_CEP = 13
_WIN_LEN = 0.025
_WIN_STEP = 0.01


def prepare_audio(pcm16: np.ndarray) -> np.ndarray:
    """MFCC features for one 1.0 s PCM window: float32 (1, 100, 13).

    Computed from raw int16 amplitudes (not amplitude-normalized floats), on
    240 zero samples appended only for this computation -- python_speech_features'
    own frame padding never kicks in, so exactly 100 frames come out.
    """
    from python_speech_features import mfcc  # optional dependency; see requirements-asd.txt

    padded = np.concatenate([pcm16.astype(np.float64), np.zeros(_PAD_SAMPLES, dtype=np.float64)])
    features = mfcc(padded, samplerate=_SAMPLE_RATE, numcep=_NUM_CEP,
                     winlen=_WIN_LEN, winstep=_WIN_STEP)
    return features[None].astype(np.float32)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(model_path: str) -> dict:
    manifest_path = model_path + ".json"
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"no manifest next to {model_path}: expected {manifest_path}")
    with open(manifest_path) as f:
        manifest = json.load(f)
    expected = manifest.get("artifact_sha256")
    if expected != _sha256(model_path):
        raise ValueError(f"{model_path} does not match artifact_sha256 in {manifest_path}")
    return manifest


class LightASD:
    """Active-speaker probabilities from one 1.0 s audio window and 25 face crops."""

    def __init__(self, model_path: str, device: str = "cpu"):
        # Fail the load, not the first inference, when the optional MFCC
        # dependency is missing: main then reports ASD unavailable, not ready.
        import python_speech_features  # noqa: F401  see requirements-asd.txt
        self.manifest = _load_manifest(model_path)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        if device == "cuda":
            # Load CUDA/cuDNN from the pip nvidia packages ourselves: without
            # torch imported first, ORT could not find libcublasLt and fell
            # back to one CPU thread (~150 ms per window).
            ort.preload_dlls()
            # TF32 off: measured max diff vs CPU 3.6e-7 on this model.
            providers = [("CUDAExecutionProvider", {"use_tf32": 0}), "CPUExecutionProvider"]
        else:
            providers = ["CPUExecutionProvider"]
        self._session = ort.InferenceSession(
            model_path, sess_options=options, providers=providers)
        if device == "cuda" and self._session.get_providers()[0] != "CUDAExecutionProvider":
            # Never run a silently slower model: main reports ASD unavailable.
            raise RuntimeError(
                f"Light-ASD asked for CUDA but ONNX Runtime gave "
                f"{self._session.get_providers()[0]}")
        print(f"[asd] Light-ASD on {self._session.get_providers()[0]}")
        self._audio_input, self._visual_input = (i.name for i in self._session.get_inputs())
        self._output = self._session.get_outputs()[0].name

    def predict(self, pcm16: np.ndarray, crops: np.ndarray) -> np.ndarray:
        if pcm16.shape != (16000,) or pcm16.dtype != np.int16:
            raise ValueError(f"pcm16 must be int16 (16000,), got {pcm16.dtype} {pcm16.shape}")
        if crops.shape != (25, 112, 112) or crops.dtype != np.uint8:
            raise ValueError(f"crops must be uint8 (25,112,112), got {crops.dtype} {crops.shape}")

        audio = prepare_audio(pcm16)
        visual = crops[None].astype(np.float32)
        probs = self._session.run([self._output], {
            self._audio_input: audio,
            self._visual_input: visual,
        })[0]
        probs = np.asarray(probs, dtype=np.float32).reshape(-1)

        if probs.shape != (25,):
            raise ValueError(f"model output must have 25 values, got {probs.shape}")
        if not np.isfinite(probs).all():
            raise ValueError("model output has non-finite probabilities")
        if not ((probs >= 0.0) & (probs <= 1.0)).all():
            raise ValueError("model output has probabilities outside [0, 1]")
        return probs
