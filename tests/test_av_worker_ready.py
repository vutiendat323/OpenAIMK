"""Session readiness uses live Visual evidence and actual processing tasks."""

import asyncio
import importlib
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def test_worker_requires_visual_handshake_fresh_live_face_and_running_pipeline(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "Audio/src"))
    from audio.domain.evidence import FaceTrackBuffer

    stdout = sys.stdout
    try:
        worker_module = importlib.import_module("trendcoffee.av_worker")
    finally:
        sys.stdout = stdout

    async def run():
        worker = worker_module.Worker()
        worker.faces = FaceTrackBuffer()
        processing = asyncio.get_running_loop().create_future()
        worker.stream = SimpleNamespace(_worker=processing, _releaser=processing)
        worker.bridge = SimpleNamespace(ready=False)
        assert not worker.media_ready()
        worker.bridge.ready = True
        assert not worker.media_ready()
        worker.faces.add({"ts": time.time() - 2, "tracks": [{"track_id": 7, "distance_m": 0.5}]})
        assert not worker.media_ready()
        worker.faces.add({"ts": time.time(), "tracks": []})
        assert not worker.media_ready()
        worker.faces.add({"ts": time.time(), "tracks": [{"track_id": 7, "distance_m": 0.5}]})
        assert worker.media_ready()
        worker.bridge.ready = False
        assert not worker.media_ready()
        worker.bridge.ready = True
        processing.set_result(None)
        assert not worker.media_ready()

    asyncio.run(run())


def test_worker_acknowledges_only_completed_session_initialization(monkeypatch):
    stdout = sys.stdout
    try:
        worker_module = importlib.import_module("trendcoffee.av_worker")
    finally:
        sys.stdout = stdout
    messages = []
    monkeypatch.setattr(worker_module, "write", messages.append)

    async def run():
        worker = worker_module.Worker()
        initializing, ready = asyncio.Event(), asyncio.Event()

        async def begin(message):
            worker.generation = message["generation"]
            initializing.set()
            await ready.wait()

        worker.begin = begin
        command = asyncio.create_task(
            worker.command({"type": "begin", "generation": 8, "request_id": 3})
        )
        await initializing.wait()
        assert not messages
        ready.set()
        await command
        assert messages == [{"type": "session_ready", "generation": 8, "request_id": 3}]
        worker.media_ready = lambda: False
        await worker.command({"type": "check_ready", "generation": 8, "request_id": 4})
        assert messages[-1] == {"type": "error", "generation": 8, "request_id": 4}

    asyncio.run(run())
