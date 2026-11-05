import asyncio
import base64
import struct

import httpx
import pytest

from trendcoffee.avatar import AvatarBridge, pcm_packet


def test_pcm_validation():
    packet = {
        "data": base64.b64encode(struct.pack("<hh", 1, -2)).decode(),
        "sampleRate": 16000,
        "numChannels": 1,
    }
    assert pcm_packet(packet) == (b"\x01\x00\xfe\xff", 16000, 1)
    for invalid in (
        {**packet, "sampleRate": 0},
        {**packet, "numChannels": 3},
        {**packet, "data": "%%%"},
        {**packet, "data": "AA=="},
    ):
        with pytest.raises(ValueError):
            pcm_packet(invalid)


def test_bridge_local_only():
    for url in (
        "https://example.com",
        "http://localhost:8010",
        "http://127.0.0.1:8010/x",
        "http://user@127.0.0.1:8010",
        "http://127.0.0.1:8010?x=1",
    ):
        with pytest.raises(ValueError):
            AvatarBridge(url)


def test_epoch_and_upstream_errors():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path == "/offer":
                return httpx.Response(
                    200, json={"sdp": "answer", "type": "answer", "sessionid": "s1"}
                )
            return httpx.Response(200, json={"code": 0})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            bridge = AvatarBridge("http://127.0.0.1:8010", client=client)
            await bridge.offer("offer")
            await bridge.reset(1)
            packet = {"data": "AAA=", "sampleRate": 16000, "numChannels": 1}
            assert not await bridge.audio(0, packet)
            assert await bridge.audio(1, packet)
            assert len([r for r in requests if r.url.path == "/trend/pcm"]) == 1
            with pytest.raises(ValueError):
                await bridge.reset(0)
            with pytest.raises(ValueError):
                await bridge.action("unknown")
            await bridge.close()

    asyncio.run(scenario())


def test_reject_upstream_application_error():
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"code": -1, "msg": "missing"})
            )
        ) as client:
            bridge = AvatarBridge("http://127.0.0.1:8010", client=client)
            with pytest.raises(ValueError):
                await bridge.offer("offer")

    asyncio.run(scenario())


def test_avatar_routes_require_origin_and_auth(svc, monkeypatch):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from trendcoffee.api import create_app

    monkeypatch.delenv("TREND_AVATAR_URL", raising=False)
    with TestClient(create_app(svc)) as client:
        assert client.get("/api/avatar/status").json()["enabled"] is False
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/avatar"):
            pass
    monkeypatch.setenv("TREND_AVATAR_URL", "http://127.0.0.1:8010")
    with TestClient(create_app(svc)) as client:
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/avatar"):
            pass
        with client.websocket_connect("/api/avatar", headers={"origin": "http://testserver"}) as ws:
            ws.send_json({"type": "auth", "token": svc.new_session()})
            assert ws.receive_json() == {"type": "ready", "flow_control": True}
            ws.send_json({"type": "unexpected"})
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


def test_native_assistant_turn_allows_avatar_to_resume():
    from trendcoffee.native_peer import NativePeer

    async def scenario():
        events = []

        async def receive(method, params):
            events.append((method, params))

        peer = NativePeer(None, "fixture", receive)
        try:
            peer.handle_event({"type": "turn.created", "turn": {"role": "assistant", "id": "a1"}})
            await asyncio.sleep(0)
            assert (
                "thread/realtime/assistantTurn/started",
                {"threadId": "fixture", "turnId": "a1"},
            ) in events
        finally:
            await peer.close()

    asyncio.run(scenario())


def test_status_advertises_video_only_capability(svc, monkeypatch):
    from fastapi.testclient import TestClient

    from trendcoffee.api import create_app

    original_client = httpx.AsyncClient
    monkeypatch.setenv("TREND_AVATAR_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            **kwargs,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"ready": True, "model": "ditto", "video_only": True}
                )
            ),
        ),
    )
    with TestClient(create_app(svc)) as client:
        status = client.get("/api/avatar/status").json()
        assert status["video_only"] is True
        assert status["engine"] == "ditto"


def test_missing_action_clip_does_not_terminate_audio_session():
    async def scenario():
        def handler(request):
            if request.url.path == "/set_audiotype":
                return httpx.Response(409)
            return httpx.Response(200, json={"code": 0})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            bridge = AvatarBridge("http://127.0.0.1:8010", client=client)
            bridge.session = "fixture"
            await bridge.reset(1)
            assert await bridge.action("wave") is False
            assert await bridge.audio(1, {"data": "AAA=", "sampleRate": 16000, "numChannels": 1})
            await bridge.close()

    asyncio.run(scenario())
