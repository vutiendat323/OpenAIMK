"""Web choices must reach native voice without changing an active guest."""

import asyncio
import base64
import struct
import wave

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.codex_voice import CodexVoice
from trendcoffee.kiosk import InteractionHost


@pytest.fixture
def boundary_clips(tmp_path, monkeypatch):
    import trendcoffee.kiosk as kiosk

    root = tmp_path / "voice"
    clips = {}
    for voice, sample in (("default", 100), ("maple", 200), ("rio", 300)):
        for kind in ("greeting", "goodbye"):
            path = root / voice / f"{kind}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            pcm = struct.pack("<h", sample + (kind == "goodbye")) * 480
            with wave.open(str(path), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(48000)
                target.writeframes(pcm)
            clips[voice, kind] = pcm
    monkeypatch.setattr(kiosk, "VOICE_CLIPS", root, raising=False)
    kiosk.boundary_speech.cache_clear()
    yield clips
    kiosk.boundary_speech.cache_clear()


def test_boundary_audio_uses_the_selected_native_voice(boundary_clips):
    from trendcoffee.kiosk import boundary_speech

    for voice in (None, "maple", "rio"):
        for kind in ("greeting", "goodbye"):
            clip = boundary_speech(kind, voice)
            assert clip["voice"] == voice
            assert (
                base64.b64decode(clip["audio"]["data"]) == boundary_clips[voice or "default", kind]
            )


def test_farewell_keeps_guest_voice_after_preference_changes(svc, boundary_clips):
    async def run():
        events = []
        native = VoiceCodex()

        class Fusion:
            async def begin(self, *args):
                pass

            async def playback(self, playing):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        host = InteractionHost(svc, codex=native, fusion=Fusion())

        async def send(event):
            events.append(event)

        try:
            await host.attach(svc.new_session(), send, voice="maple")
            await host.begin(manual=True)
            greeting = next(e for e in events if e["type"] == "announcement")
            assert greeting["announcement"]["voice"] == "maple"
            await host.set_voice("rio")
            assert native.voice == "maple"
            await host.end("next_guest")
            goodbye = next(e for e in events if e["type"] == "ended")
            assert goodbye["announcement"]["voice"] == "maple"
            assert (
                base64.b64decode(goodbye["announcement"]["audio"]["data"])
                == boundary_clips["maple", "goodbye"]
            )
            await host.begin(manual=True)
            greeting = [e for e in events if e["type"] == "announcement"][-1]
            assert greeting["announcement"]["voice"] == "rio"
        finally:
            await host.close()

    asyncio.run(run())


def test_only_voices_with_both_boundary_clips_are_selectable(svc, boundary_clips):
    import trendcoffee.kiosk as kiosk

    async def run():
        host = InteractionHost(svc, codex=VoiceCodex())
        assert await host.voice_options() == ["maple", "rio"]
        (kiosk.VOICE_CLIPS / "rio/goodbye.wav").unlink()
        assert await host.voice_options() == ["maple"]
        with pytest.raises(kiosk.KioskError, match="invalid_voice"):
            await host.set_voice("rio")
        await host.close()

    asyncio.run(run())


def test_native_catalog_uses_only_v3_voices_and_caches_the_result():
    async def run():
        native = CodexVoice(".")
        calls = []

        async def start():
            pass

        async def request(method, params):
            calls.append(method)
            return {"voices": {"v1": ["ember"], "v2": ["marin"], "v3": ["cove", "rio"]}}

        native.start, native.request = start, request
        assert await native.list_voices() == ["cove", "rio"]
        assert await native.list_voices() == ["cove", "rio"]
        assert calls == ["thread/realtime/listVoices"]

    asyncio.run(run())


@pytest.mark.parametrize("transport", ["webrtc", "websocket"])
def test_native_start_uses_the_voice_captured_for_that_thread(transport):
    async def run():
        native = CodexVoice(".")
        requests = []

        async def start():
            pass

        async def request(method, params, **kwargs):
            requests.append((method, params))
            if method == "thread/start":
                return {"thread": {"id": "fixture"}}
            if method == "thread/realtime/start":
                if transport == "webrtc":
                    native.sdp["fixture"].set_result("answer")
                else:
                    native.started["fixture"].set_result({})
            return {}

        native.start, native.request = start, request
        native.voice = "maple"
        thread = await native.create_thread([], None, None)
        native.voice = "cove"  # A preference for the next thread.
        if transport == "webrtc":
            assert await native.start_voice(thread, "offer") == "answer"
        else:
            await native.start_audio(thread)
        assert requests[-1][1]["voice"] == "maple"
        assert requests[-1][1]["version"] == "v3"

    asyncio.run(run())


class VoiceCodex(FakeCodex):
    async def start_filtered_voice(self, thread):
        pass

    async def list_voices(self):
        return ["cove", "maple", "rio"]


def test_web_voice_options_come_from_native_catalog(svc):
    host = InteractionHost(svc, codex=VoiceCodex())
    with TestClient(create_app(service=svc, kiosk_host=host)) as client:
        assert client.get("/api/kiosk/voices").json() == {"voices": ["cove", "maple", "rio"]}


def test_web_voice_change_is_deferred_without_resetting_current_guest(svc):
    async def run():
        native = VoiceCodex()
        host = InteractionHost(svc, codex=native)

        async def send(event):
            pass

        await host.attach(svc.new_session(), send, voice="maple")
        assert native.voice == "maple"
        host.active = True
        host.cart = [{"item": {"id": "coffee"}, "quantity": 2}]
        await host.command({"type": "voice_setting", "voice": "rio"})
        assert host.voice == "rio" and native.voice == "maple"
        assert host.active and host.cart[0]["quantity"] == 2
        await host.end("next_guest")
        assert native.voice == "rio"
        await host.close()

    asyncio.run(run())


@pytest.mark.parametrize("voice", ["marin", "not-a-voice", True, {}])
def test_auth_rejects_unsupported_voice_before_attaching_controller(svc, voice):
    host = InteractionHost(svc, codex=VoiceCodex())
    with TestClient(create_app(service=svc, kiosk_host=host)) as client:
        token = client.post("/api/sessions").json()["session_token"]
        with client.websocket_connect("/api/kiosk", headers={"origin": "http://testserver"}) as ws:
            ws.send_json({"type": "auth", "session_token": token, "voice": voice})
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
        assert host.controller is None
