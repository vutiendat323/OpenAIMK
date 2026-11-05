"""Speaker embeddings off the event loop: a bounded worker and the bot's sink."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor

import numpy as np

from audio.application.ports import SpeakerEmbedder
from audio.domain.identity import BotVoiceprint, EmbeddingJob, unit

logger = logging.getLogger(__name__)


_MAX_TIMINGS = 512


# One GPU model, one thread, apart from the diarizer's so Sortformer never
# waits behind an embedding.
EMBEDDING_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embedder")


class EmbeddingWorker:
    """At most one embedding running and one pending per slot.

    A newer job for a slot replaces its pending one and keeps its place; the
    slot waiting longest goes first, so a TV that never stops talking cannot
    starve the customer's slot. Results reach ``on_result`` on the event loop.
    """

    def __init__(
        self,
        embedder: SpeakerEmbedder,
        on_result: Callable[[EmbeddingJob, np.ndarray, float], None],
        *,
        executor: Executor | None = None,
    ) -> None:
        self._embedder = embedder
        self._on_result = on_result
        self._executor = executor or EMBEDDING_EXECUTOR
        self._pending: dict[int, EmbeddingJob] = {}
        self._order: deque[int] = deque()
        self._task: asyncio.Task | None = None
        self.failed = False
        self.elapsed_ms: deque[float] = deque(maxlen=_MAX_TIMINGS)

    @property
    def pending(self) -> int:
        return len(self._pending)

    def submit(self, job: EmbeddingJob) -> None:
        if self.failed or getattr(self._embedder, "disabled", False):
            return
        if job.slot not in self._pending:
            self._order.append(job.slot)
        self._pending[job.slot] = job
        self._kick()

    def clear(self) -> None:
        self._pending.clear()
        self._order.clear()

    def _kick(self) -> None:
        if self._task is not None or not self._order:
            return
        job = self._pending.pop(self._order.popleft())
        self._task = asyncio.get_running_loop().create_task(self._run(job))

    async def _run(self, job: EmbeddingJob) -> None:
        try:
            started = time.monotonic()
            try:
                embedding = await asyncio.get_running_loop().run_in_executor(
                    self._executor, self._embedder.embed, job.pcm
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - fusion runs on without voiceprints
                self.failed = True
                self._embedder.disabled = True
                self.clear()
                logger.exception(
                    "speaker embedder failed; fusion runs without voiceprints"
                )
                return
            elapsed = (time.monotonic() - started) * 1000.0
            self.elapsed_ms.append(elapsed)
            vector = np.asarray(embedding, dtype=np.float32)
            norm = float(np.linalg.norm(vector))
            if not np.isfinite(vector).all() or norm == 0.0:
                logger.warning(
                    f"speaker embedding for slot {job.slot} is not usable; dropped"
                )
                return
            try:
                self._on_result(job, embedding, elapsed)
            except Exception:  # noqa: BLE001 - a consumer bug is not the embedder's
                logger.exception("speaker embedding consumer failed; result dropped")
        finally:
            self._task = None
            if not self.failed:
                self._kick()

    async def close(self) -> None:
        self.clear()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None


def bot_audio_sink(
    embedder: SpeakerEmbedder, bot: BotVoiceprint, executor: Executor | None = None
) -> Callable[[bytes, int, int], None]:
    """A VieNeu ``on_audio`` hook that embeds the bot's first 3 s, off the loop."""
    pool = executor or EMBEDDING_EXECUTOR

    def embed(pcm: np.ndarray) -> None:
        try:
            bot.embedding = unit(embedder.embed(pcm))
        except Exception:  # noqa: BLE001 - echo falls back to playback overlap
            bot.failed = True
            logger.exception("bot voiceprint unavailable; echo uses playback overlap")

    def sink(audio: bytes, sample_rate: int, num_channels: int) -> None:
        if getattr(embedder, "disabled", False):
            return
        pcm = bot.offer(audio, sample_rate, num_channels)
        if pcm is not None:
            pool.submit(embed, pcm)

    return sink
