"""PCM helpers shared by the gates, the console and the model adapters."""

from __future__ import annotations

import math

import numpy as np

SAMPLE_RATE = 16_000


def resample_to_16k(pcm: np.ndarray, sample_rate: int) -> np.ndarray:
    if sample_rate == SAMPLE_RATE:
        return pcm
    from scipy.signal import resample_poly

    g = math.gcd(SAMPLE_RATE, sample_rate)
    out = resample_poly(pcm.astype(np.float32), SAMPLE_RATE // g, sample_rate // g)
    return np.clip(out, -32768, 32767).astype(np.int16)


def audio_levels(audio: bytes, *, include_waveform: bool = True) -> dict:
    if len(audio) % 2:
        return {"rms_dbfs": None, "peak": None, "waveform": []}
    samples = np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768.0
    if not len(samples):
        return {"rms_dbfs": -96.0, "peak": 0.0, "waveform": []}
    rms = float(np.sqrt(np.mean(samples * samples)))
    # Signed peaks retain short transients without transmitting microphone PCM.
    stride = max(1, math.ceil(len(samples) / 32))
    wave = []
    if include_waveform:
        for start in range(0, len(samples), stride):
            block = samples[start : start + stride]
            wave.extend((round(float(block.min()), 4), round(float(block.max()), 4)))
    return {
        "rms_dbfs": round(max(-96.0, 20 * math.log10(max(rms, 1e-8))), 1),
        "peak": round(float(np.max(np.abs(samples))), 4),
        "waveform": wave,
    }
