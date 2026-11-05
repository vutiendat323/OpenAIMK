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


def test_a_session_publishes_its_fusion_state_to_the_visual_console(monkeypatch):
    """2026-11-05: the Visual console never showed "TARGET LOCKED" or the audio monitor.

    `SpeakerStream` creates its operator console (which streams `voice_monitor_start` and
    `voice_telemetry` to Visual) only when it gets `speaker_settings`; the worker passed none.
    Levels and verdicts only: no PCM leaves through the console.
    """
    from types import ModuleType

    stdout = sys.stdout
    try:
        worker_module = importlib.import_module("trendcoffee.av_worker")
    finally:
        sys.stdout = stdout
    created = {}

    class Stream:
        def __init__(self, **kwargs):
            created.update(kwargs)

        async def start(self):
            pass

        async def close(self):
            pass

    class Faces:
        def fresh(self, now, max_age):
            return True

    class Bridge:
        ready = True

        def __init__(self, url, session_id, faces):
            pass

        def offer_telemetry(self, snapshot):
            pass

    fakes = {
        "audio": ModuleType("audio"),
        "audio.application": ModuleType("audio.application"),
        "audio.application.stream": SimpleNamespace(SpeakerStream=Stream),
        "audio.domain": ModuleType("audio.domain"),
        "audio.domain.evidence": SimpleNamespace(FaceTrackBuffer=Faces),
        "audio.domain.fusion": SimpleNamespace(
            FusionGate=lambda settings, faces, fsm_state: SimpleNamespace(settings=settings)
        ),
        "audio.domain.settings": SimpleNamespace(
            settings_from_mapping=lambda values: SimpleNamespace(**values)
        ),
        "audio.infrastructure": ModuleType("audio.infrastructure"),
        "audio.infrastructure.vision": ModuleType("audio.infrastructure.vision"),
        "audio.infrastructure.vision.asd_bridge": SimpleNamespace(VisionAudioBridge=Bridge),
    }
    for name, module in fakes.items():
        monkeypatch.setitem(sys.modules, name, module)

    async def run():
        worker = worker_module.Worker()
        worker.diarizer = worker.embedder = worker.separator = None  # models from load()
        worker.media_ready = lambda: True
        worker.listen_faces = lambda url, generation: asyncio.sleep(0)
        await worker.begin({"generation": 1, "session_id": "s1"})
        settings = created.get("speaker_settings")
        assert settings is not None, "without settings the stream has no console"
        assert settings.vision_asd and settings.identity == "fusion"
        assert created["gate"].settings is settings, "the console shows the gate's own settings"
        await worker.end()

    asyncio.run(run())
