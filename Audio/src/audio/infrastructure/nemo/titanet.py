"""NeMo TitaNet speaker embeddings behind the SpeakerEmbedder port."""

from __future__ import annotations

import logging
import time

import numpy as np

from audio.domain.signal import SAMPLE_RATE

logger = logging.getLogger(__name__)


class TitaNetEmbedder:
    """NeMo TitaNet (192-d). Not thread-safe; EMBEDDING_EXECUTOR serialises it."""

    def __init__(
        self, model_name: str = "titanet_small", *, device: str = "cuda"
    ) -> None:
        import torch
        from nemo.collections.asr.models import EncDecSpeakerLabelModel

        self._torch = torch
        self._model = EncDecSpeakerLabelModel.from_pretrained(
            model_name, map_location=device
        ).eval()
        started = time.monotonic()
        self.embed(np.zeros(SAMPLE_RATE, np.int16))
        logger.info(
            f"speaker embedder {model_name} loaded "
            f"(warm-up {time.monotonic() - started:.2f} s)"
        )

    def embed(self, pcm: np.ndarray) -> np.ndarray:
        torch = self._torch
        device = self._model.device
        signal = torch.from_numpy(pcm.astype(np.float32) / 32768.0)[None].to(device)
        with torch.inference_mode():
            _, embedding = self._model.forward(
                input_signal=signal,
                input_signal_length=torch.tensor([signal.shape[1]], device=device),
            )
        return embedding[0].float().cpu().numpy()
