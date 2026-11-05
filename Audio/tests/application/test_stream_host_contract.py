"""What a host relies on: console reads, a wired console, audio outside a session."""

import asyncio
import json
import math
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest

from audio.application.ports import LiveKey
from audio.application.stream import AudioChunk, SpeakerStream
from audio.domain.evidence import FaceTrackBuffer
from audio.domain.fusion import FusionGate
from audio.domain.gate import AudioOnlyGate
from audio.domain.settings import SpeakerSettings
from audio.infrastructure.vision.asd_bridge import VisionAudioBridge

SNAPSHOT_KEYS = [
    "ts",
    "target_audio_monitor",
    "audio",
    "enhancer_requested",
    "enhancer_effective",
    "identity",
    "verdict",
    "verdict_ts",
    "evidence",
    "locked",
    "lock_state",
    "target_track",
    "target_slots",
    "voice_ready",
    "voice_similarity",
    "overlap",
    "bot_speaking",
    "stt_mask",
    "tse_ready",
    "stt_masked_no_verdict_frames",
    "asd_effective_use",
    "asd_late",
    "asd_age_ms",
    "bargein_blocked",
    "echo_rejects",
    "settings",
    "bounds",
]


class Diarizer:
    frame_secs = 0.08
    chunk_samples = 1280

    def reset(self):
        pass

    def push(self, pcm):
        return np.zeros((1, 4))


class Separator:
    window_samples = 1280 * 20
    enroll_samples = 1280 * 2

    def separate(self, mix, enroll):
        return mix


def _chunk(samples=1280):
    return AudioChunk(np.zeros(samples, np.int16).tobytes(), 16_000, 1)


def test_the_stream_exposes_what_the_console_reads():
    gate = AudioOnlyGate(SpeakerSettings(enabled=True))
    stream = SpeakerStream(
        diarizer=Diarizer(),
        gate=gate,
        executor=ThreadPoolExecutor(max_workers=1),
        stt_delay_secs=0.5,
        separator=Separator(),
        tracker=SimpleNamespace(bargein_blocked=4),
    )
    assert stream.gate is gate and stream.fusion is None and stream.bridge is None
    assert stream.bot_audible_until == 0.0 and stream.bargein_blocked == 4
    assert stream.stt_masked_no_verdict == 0 and stream.tse_ready is False
    stream._add_enrollment(np.ones(1280 * 2, np.int16))
    assert stream.tse_ready is True
    stream.bot_started()
    assert stream.bot_audible_until == math.inf


@pytest.mark.anyio
async def test_a_running_stream_with_settings_and_a_bridge_wires_the_console():
    settings = SpeakerSettings(identity="fusion", vision_asd=True)
    faces = FaceTrackBuffer()
    gate = FusionGate(settings, faces, fsm_state=lambda: "active")
    bridge = VisionAudioBridge("ws://vision", "session", faces)
    distance = LiveKey("approach_threshold_m", (0.1, 6.0), lambda: 1.0, lambda v: None)
    stream = SpeakerStream(
        diarizer=Diarizer(),
        gate=gate,
        executor=ThreadPoolExecutor(max_workers=1),
        vision_audio=bridge,
        speaker_settings=settings,
        live_keys=(distance,),
    )
    assert bridge.console is not None
    await stream.start()
    try:
        stream.push_audio(_chunk(320))
        snapshot = bridge.console.snapshot()
    finally:
        await stream.finish()
        await stream.close()
    assert list(snapshot) == SNAPSHOT_KEYS
    assert snapshot["audio"]["ts"] is not None
    assert list(snapshot["settings"])[0] == "approach_threshold_m"
    assert snapshot["identity"] == "fusion" and snapshot["lock_state"] == "NONE"
    json.dumps(snapshot, allow_nan=False)


@pytest.mark.anyio
async def test_audio_outside_a_session_is_bounded_and_harmless():
    stream = SpeakerStream(
        diarizer=Diarizer(),
        gate=AudioOnlyGate(SpeakerSettings(enabled=True)),
        executor=ThreadPoolExecutor(max_workers=1),
    )
    for _ in range(10):
        stream.push_audio(_chunk())
    assert stream._queue.qsize() <= 2
    await stream.start()
    await stream.finish()
    await stream.close()
    for _ in range(10):
        stream.push_audio(_chunk())
    assert stream._queue.qsize() <= 2


class Speaking(Diarizer):
    def push(self, pcm):
        return np.array([[0.9, 0.0, 0.0, 0.0]])


class Broken(Diarizer):
    def push(self, pcm):
        raise RuntimeError("diarizer lost its GPU")


async def _settle(done, tries=200):
    for _ in range(tries):
        if done():
            return
        await asyncio.sleep(0.01)


@pytest.mark.anyio
async def test_audio_outside_a_session_never_reaches_stt():
    released = []

    async def on_stt_audio(item):
        released.append(item)

    stream = SpeakerStream(
        diarizer=Diarizer(),
        gate=AudioOnlyGate(SpeakerSettings(enabled=True)),
        executor=ThreadPoolExecutor(max_workers=1),
        stt_delay_secs=0.1,
        on_stt_audio=on_stt_audio,
    )
    for _ in range(10):
        stream.push_audio(_chunk())
    await stream.start()
    await asyncio.sleep(0.2)
    await stream.finish()
    await stream.close()
    assert released == []
    for _ in range(100):
        stream.push_audio(_chunk())
    assert len(stream._stt_line) == 0 and stream._queue.qsize() == 0


@pytest.mark.anyio
async def test_a_raising_host_callback_is_logged_and_the_stream_keeps_going(caplog):
    verdicts, released = [], []

    async def on_verdict(item):
        verdicts.append(item)
        if len(verdicts) == 1:
            raise RuntimeError("host verdict bug")

    async def on_stt_audio(item):
        released.append(item)
        if len(released) == 1:
            raise RuntimeError("host stt bug")

    stream = SpeakerStream(
        diarizer=Speaking(),
        gate=AudioOnlyGate(SpeakerSettings(enabled=True)),
        executor=ThreadPoolExecutor(max_workers=1),
        stt_delay_secs=0.05,
        on_verdict=on_verdict,
        on_stt_audio=on_stt_audio,
    )
    await stream.start()
    for _ in range(3):
        stream.push_audio(_chunk())
        await asyncio.sleep(0.05)
    await _settle(lambda: len(verdicts) >= 3 and len(released) >= 3)
    await stream.finish()
    await stream.close()
    assert len(verdicts) >= 3 and len(released) >= 3
    assert "host verdict bug" in caplog.text and "host stt bug" in caplog.text


@pytest.mark.anyio
async def test_a_failing_stream_task_is_logged(caplog):
    stream = SpeakerStream(
        diarizer=Broken(),
        gate=AudioOnlyGate(SpeakerSettings(enabled=True)),
        executor=ThreadPoolExecutor(max_workers=1),
    )
    await stream.start()
    stream.push_audio(_chunk())
    await _settle(lambda: "diarizer lost its GPU" in caplog.text)
    await stream.close()
    assert "diarize" in caplog.text and "diarizer lost its GPU" in caplog.text


@pytest.mark.anyio
async def test_a_stream_serves_one_session():
    stream = SpeakerStream(
        diarizer=Diarizer(),
        gate=AudioOnlyGate(SpeakerSettings(enabled=True)),
        executor=ThreadPoolExecutor(max_workers=1),
    )
    await stream.start()
    with pytest.raises(RuntimeError, match="one session"):
        await stream.start()
    await stream.finish()
    await stream.close()
    with pytest.raises(RuntimeError, match="one session"):
        await stream.start()


def test_the_host_can_share_its_model_threads():
    """A host whose models are shared process-wide passes its own executors."""
    diarize, separate, embed = (ThreadPoolExecutor(max_workers=1) for _ in range(3))
    settings = SpeakerSettings(identity="fusion", vision_asd=True)
    stream = SpeakerStream(
        diarizer=Diarizer(),
        gate=FusionGate(settings, FaceTrackBuffer(), fsm_state=lambda: "active"),
        executor=diarize,
        stt_delay_secs=0.5,
        separator=Separator(),
        separator_executor=separate,
        embedder=SimpleNamespace(disabled=False),
        embedding_executor=embed,
    )
    assert stream._executor is diarize
    assert stream._separator_executor is separate
    assert stream._embeddings._executor is embed
