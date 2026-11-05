"""Opt-in real GPU/WebRTC regression; fake voice events, isolated guest database.

TREND_TEST_AVATAR_URL=http://127.0.0.1:8010 .venv/bin/pytest -q tests/test_avatar_browser.py
Requires the prepared local engine and a built frontend. Never contacts merchant/native voice.
"""

import json
import os
import shutil
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from trendcoffee.api import create_app
from trendcoffee.kiosk import boundary_speech


def test_greeting_interrupt_reconnect_and_next_guest(svc, monkeypatch):
    from playwright.sync_api import expect, sync_playwright

    url = os.getenv("TREND_TEST_AVATAR_URL")
    if not url:
        pytest.skip("Set TREND_TEST_AVATAR_URL for hardware acceptance")
    monkeypatch.setenv("TREND_AVATAR_URL", url)
    server = uvicorn.Server(
        uvicorn.Config(create_app(service=svc), host="127.0.0.1", port=0, log_level="error")
    )
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=shutil.which("chromium"),
                args=[
                    "--no-sandbox",
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )
            page = browser.new_page(
                permissions=["microphone", "camera"], viewport={"width": 1440, "height": 900}
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""
                navigator.permissions.query = async () => ({state: 'prompt'});
                localStorage.setItem('trendcoffee.voice', 'maple');
                window.avatarSockets = [];
                const Socket = WebSocket;
                window.WebSocket = class extends Socket {
                    constructor(...args) { super(...args); if (String(args[0]).endsWith('/api/avatar')) window.avatarSockets.push(this); }
                };
            """)
            page.route("**/api/kiosk/status", lambda route: route.fulfill(json={"enabled": True}))
            page.route(
                "**/api/kiosk/voices", lambda route: route.fulfill(json={"voices": ["maple"]})
            )
            sockets = []

            def kiosk(ws):
                sockets.append(ws)

                def message(raw):
                    if not isinstance(raw, str):
                        return
                    data = json.loads(raw)
                    if data["type"] == "auth":
                        ws.send(
                            json.dumps({"type": "camera", "generation": 0, "local_available": True})
                        )

                ws.on_message(message)

            page.route_web_socket("**/api/kiosk", kiosk)
            page.goto(f"http://127.0.0.1:{port}/")
            page.get_by_role("button", name="Bật micro", exact=True).click()
            page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for(timeout=30000)
            video = page.locator(".avatar-stage video")
            page.wait_for_function(
                "() => document.querySelector('.avatar-stage video').readyState >= 2", timeout=20000
            )

            def emit(kind, generation=1, **fields):
                sockets[-1].send(json.dumps({"type": kind, "generation": generation, **fields}))

            def speech(native=False):
                clip = boundary_speech("greeting", "maple")
                if native:
                    emit("audio", audio=clip["audio"])
                else:
                    emit("announcement", announcement=clip)
                expect(page.locator(".avatar-assistant")).to_have_attribute(
                    "data-phase", "speaking", timeout=10000
                )

            emit("session", voice="maple")
            emit("status", status="listening")
            speech()
            page.wait_for_timeout(4500)
            assert page.evaluate("avatarSockets.length") == 1
            expect(video).to_be_visible()
            expect(page.locator(".avatar-stage img")).to_be_hidden()
            # Repeat an utterance, interrupt mid-stream, then allow a new assistant turn.
            speech()
            emit("voice_turn", role="user")
            expect(page.locator(".avatar-assistant")).not_to_have_attribute(
                "data-phase", "speaking", timeout=500
            )
            page.wait_for_timeout(500)
            emit("voice_turn", role="assistant")
            speech(native=True)
            if os.getenv("TREND_TEST_GESTURES") == "1":
                Path("output/avatar-browser").mkdir(parents=True, exist_ok=True)
                video.screenshot(path="output/avatar-browser/trend-talking.png")
            page.wait_for_timeout(4500)
            if os.getenv("TREND_TEST_GESTURES") == "1":
                page.get_by_role("button", name="Cài đặt", exact=True).click()
                page.get_by_role("button", name="Vẫy tay", exact=True).click()
                page.get_by_role("dialog").get_by_role("button", name="Đóng", exact=True).click()
                page.wait_for_timeout(2400)
                assert (
                    httpx.get(url + "/trend/health", trust_env=False).json()["animation"] == "wave"
                )
                Path("output/avatar-browser").mkdir(parents=True, exist_ok=True)
                video.screenshot(path="output/avatar-browser/trend-wave.png")
                # Live PCM must not cancel the hand action or wait six seconds for it to end.
                speech(native=True)
                video.screenshot(path="output/avatar-browser/trend-wave-speaking.png")
                assert (
                    httpx.get(url + "/trend/health", trust_env=False).json()["animation"] == "wave"
                )
                page.wait_for_timeout(4500)
                page.get_by_role("button", name="Cài đặt", exact=True).click()
                page.get_by_role("button", name="Mỉm cười", exact=True).click()
                page.wait_for_timeout(300)
                assert (
                    httpx.get(url + "/trend/health", trust_env=False).json()["animation"] == "smile"
                )
                page.get_by_role("button", name="Đứng chờ", exact=True).click()
                page.wait_for_timeout(300)
                assert (
                    httpx.get(url + "/trend/health", trust_env=False).json()["animation"] == "idle"
                )
                page.get_by_role("dialog").get_by_role("button", name="Đóng", exact=True).click()
            # Loss of avatar transport must reconnect without losing guest/voice ownership.
            page.evaluate("avatarSockets.at(-1).close()")
            page.wait_for_function(
                "() => avatarSockets.length >= 2 && document.querySelector('.avatar-stage video').readyState >= 2",
                timeout=30000,
            )
            recovered_sockets = page.evaluate("avatarSockets.length")
            assert 2 <= recovered_sockets <= 4  # old engine session may still be closing
            speech()
            page.wait_for_timeout(4500)
            emit("ended", generation=2, announcement=boundary_speech("goodbye", "maple"))
            page.wait_for_timeout(4000)
            emit("session", generation=3, voice="maple")
            emit("status", generation=3, status="listening")
            emit("announcement", generation=3, announcement=boundary_speech("greeting", "maple"))
            expect(page.locator(".avatar-assistant")).to_have_attribute(
                "data-phase", "speaking", timeout=10000
            )
            page.wait_for_timeout(4500)
            assert page.evaluate("avatarSockets.length") == recovered_sockets
            expect(video).to_be_visible()
            expect(page.locator(".avatar-stage img")).to_be_hidden()
            assert not errors
            output = Path("output/avatar-browser")
            output.mkdir(parents=True, exist_ok=True)
            for width in (375, 768, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                page.screenshot(path=str(output / f"kiosk-{width}.png"))
                stage = page.locator(".avatar-stage").bounding_box()
                scene = page.locator(".assistant-scene").bounding_box()
                assert abs(stage["x"] - scene["x"]) < 2
                assert stage["width"] <= width
            page.get_by_role("button", name="Tắt micro", exact=True).click()
            expect(page.locator(".avatar-stage img")).to_have_attribute(
                "src", "/avatars/trend-live.png"
            )
            page.get_by_role("button", name="Bật micro", exact=True).click()
            page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for(timeout=30000)
            page.wait_for_function(
                "() => document.querySelector('.avatar-stage video').readyState >= 2", timeout=20000
            )
            browser.close()
    finally:
        server.should_exit = True
        worker.join(10)
