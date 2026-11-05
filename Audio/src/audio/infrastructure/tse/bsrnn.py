"""REAL-TSE WeSep BSRNN target-speaker extraction behind the Separator port."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from audio.domain.signal import SAMPLE_RATE

logger = logging.getLogger(__name__)


class TseSeparator:
    """REAL-TSE WeSep BSRNN, exported by ``scripts/voice_tse_export.py``.

    Non-causal: it needs the whole overlapped stretch, so the processor holds
    that stretch back from STT and separates it in one call (~0.3 s for 8 s on
    the dev laptop, ~0.7 GB VRAM). Trained on clean Libri2Mix: the 2026-09-26
    spike only partly recovered an order under a loud phone video (spec §11).
    """

    window_samples = 8 * SAMPLE_RATE
    enroll_samples = 3 * SAMPLE_RATE
    _PAD = 128  # one STFT hop, as exported

    def __init__(self, path: str, *, device: str = "cuda") -> None:
        import torch

        # TorchScript's default executor stalls for minutes on this traced
        # LSTM graph or misplaces its constants on the CPU, and its fuser fails
        # to compile kernels. The simple executor with optimisation off (per
        # call, below) runs it as traced. Process-wide, but nothing else in
        # the Voice process runs TorchScript.
        torch._C._jit_set_profiling_executor(False)
        self._torch = torch
        self._device = device
        self._model = torch.jit.load(str(Path(path).expanduser()), map_location=device)
        # The first call costs ~1.2 s, past the STT's drain timeout.
        started = time.monotonic()
        self.separate(
            np.zeros(SAMPLE_RATE, np.float32),
            np.zeros(self.enroll_samples, np.float32),
        )
        logger.info(
            f"TSE separator loaded from {path} "
            f"(warm-up {time.monotonic() - started:.2f} s)"
        )

    def separate(self, mix: np.ndarray, enroll: np.ndarray) -> np.ndarray:
        torch = self._torch
        padded = np.zeros(self.window_samples + self._PAD, np.float32)
        padded[: len(mix)] = mix[: self.window_samples]
        with torch.inference_mode(), torch.jit.optimized_execution(False):
            out = self._model(
                torch.from_numpy(padded)[None].to(self._device),
                torch.from_numpy(enroll[-self.enroll_samples :])[None].to(self._device),
            )
        return out[0, : len(mix)].float().cpu().numpy()
