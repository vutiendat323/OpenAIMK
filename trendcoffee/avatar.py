"""Local-only LiveTalking transport. Each browser owns one upstream session."""

import base64
import binascii
import contextlib
import ipaddress
import json
import logging
import os
from urllib.parse import urlsplit

import httpx
from fastapi import WebSocket, WebSocketDisconnect

from .service import ServiceError


def pcm_packet(packet):
    rate, channels = packet.get("sampleRate"), packet.get("numChannels")
    if type(rate) is not int or not 8000 <= rate <= 96000 or type(channels) is not int:
        raise ValueError("invalid_pcm")
    if channels not in (1, 2):
        raise ValueError("invalid_pcm")
    encoded = packet.get("data")
    if not isinstance(encoded, str) or len(encoded) > 600000:
        raise ValueError("invalid_pcm")
    try:
        pcm = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("invalid_pcm") from error
    # Bound every packet to 200 ms; no accumulating unbounded utterances.
    if not pcm or len(pcm) % (2 * channels) or len(pcm) > rate * channels * 2 // 5:
        raise ValueError("invalid_pcm")
    return pcm, rate, channels


class AvatarBridge:
    def __init__(self, url, *, client=None):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "http"
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("avatar_requires_loopback")
        try:
            if not ipaddress.ip_address(parsed.hostname).is_loopback:
                raise ValueError("avatar_requires_loopback")
        except (TypeError, ValueError) as error:
            raise ValueError("avatar_requires_loopback") from error
        self.url = url.rstrip("/")
        self.client = client or httpx.AsyncClient(timeout=10, trust_env=False)
        self.owned_client = client is None
        self.session = None
        self.epoch = 0

    async def call(self, path, **kwargs):
        response = await self.client.post(self.url + path, **kwargs)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("code", 0) != 0:
            raise ValueError("avatar_upstream_error")
        return result

    async def offer(self, sdp):
        if self.session or not isinstance(sdp, str) or not 1 <= len(sdp) <= 100000:
            raise ValueError("invalid_offer")
        result = await self.call("/offer", json={"sdp": sdp, "type": "offer"})
        if result.get("type") != "answer" or not result.get("sdp") or not result.get("sessionid"):
            raise ValueError("invalid_answer")
        self.session = result["sessionid"]
        return {"sdp": result["sdp"], "type": "answer"}

    async def reset(self, epoch):
        if not self.session or type(epoch) is not int or epoch <= self.epoch:
            raise ValueError("invalid_epoch")
        await self.call("/trend/reset", json={"sessionid": self.session, "epoch": epoch})
        self.epoch = epoch

    async def audio(self, epoch, packet):
        if not self.session or type(epoch) is not int or epoch != self.epoch:
            return False
        pcm, rate, channels = pcm_packet(packet)
        await self.call(
            "/trend/pcm",
            content=pcm,
            headers={
                "X-Session-ID": str(self.session),
                "X-Epoch": str(epoch),
                "X-Sample-Rate": str(rate),
                "X-Channels": str(channels),
                "Content-Type": "application/octet-stream",
            },
        )
        return True

    async def action(self, action):
        actions = {"idle": 1, "wave": 2, "smile": 3}
        if not self.session or action not in actions:
            raise ValueError("invalid_action")
        try:
            await self.call(
                "/set_audiotype",
                json={"sessionid": self.session, "audiotype": actions[action]},
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 409:
                return False
            raise
        return True

    async def close(self):
        try:
            if self.session:
                await self.call("/trend/close", json={"sessionid": self.session})
        finally:
            if self.owned_client:
                await self.client.aclose()


def install_avatar_routes(app, service):
    url = os.environ.get("TREND_AVATAR_URL", "")
    # Validate configuration at startup, never accept a URL from a guest.
    if url:
        parsed = urlsplit(url)
        if parsed.hostname not in ("127.0.0.1", "::1") or parsed.scheme != "http":
            raise ValueError("avatar_requires_loopback")

    @app.get("/api/avatar/status")
    async def avatar_status():
        status = {
            "enabled": bool(url),
            "engine": "livetalking",
            "local": True,
            "poster": "/avatars/trend-live.png",
            "ready": False,
            "actions": [],
        }
        if url:
            try:
                async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
                    response = await client.get(url + "/trend/health")
                    response.raise_for_status()
                    health = response.json()
                    status["ready"] = health.get("ready") is True
                    status["video_only"] = health.get("video_only") is True
                    if health.get("model") in ("ditto", "wav2lip", "musetalk"):
                        status["model"] = health["model"]
                        if health["model"] == "ditto":
                            status["engine"] = "ditto"
                    status["actions"] = [
                        name
                        for name in ("idle", "wave", "smile")
                        if name in health.get("actions", [])
                    ]
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                pass
        return status

    @app.websocket("/api/avatar")
    async def avatar_socket(socket: WebSocket):
        expected = (
            ("https" if socket.url.scheme == "wss" else "http")
            + "://"
            + socket.headers.get("host", "")
        )
        if not url or socket.headers.get("origin") != expected:
            await socket.close(code=1008)
            return
        import asyncio

        await socket.accept()
        bridge = AvatarBridge(url)
        try:
            auth = await asyncio.wait_for(socket.receive_text(), 5)
            if len(auth) > 4096:
                raise ValueError("invalid_auth")
            auth = json.loads(auth)
            if auth.get("type") != "auth":
                raise ValueError("invalid_auth")
            service.memory(auth.get("token", ""))
            await socket.send_json({"type": "ready", "flow_control": True})
            while True:
                raw = await socket.receive_text()
                if len(raw) > 700000:
                    raise ValueError("packet_too_large")
                message = json.loads(raw)
                kind = message.get("type")
                if kind == "offer":
                    result = await bridge.offer(message.get("sdp"))
                    await socket.send_json({"type": "answer", **result})
                elif kind == "reset":
                    await bridge.reset(message.get("epoch"))
                elif kind == "audio":
                    await bridge.audio(message.get("epoch"), message.get("audio", {}))
                    await socket.send_json({"type": "audio_ack", "epoch": message.get("epoch")})
                elif kind == "action":
                    available = await bridge.action(message.get("action"))
                    await socket.send_json({"type": "action", "available": available})
                else:
                    raise ValueError("invalid_avatar_command")
        except (httpx.HTTPError, TimeoutError) as error:
            logging.getLogger(__name__).warning(
                "Avatar upstream unavailable: %s", type(error).__name__
            )
            with contextlib.suppress(Exception):
                await socket.close(code=1011, reason="avatar_unavailable")
        except (ValueError, TypeError, AttributeError, ServiceError):
            with contextlib.suppress(Exception):
                await socket.close(code=1008)
        except WebSocketDisconnect:
            pass
        finally:
            with contextlib.suppress(Exception):
                await bridge.close()
