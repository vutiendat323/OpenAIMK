"""Code-driven Pet selection, voice playback and layout without talking-head transport."""

import asyncio
import base64
import shutil
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import uvicorn
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost


@contextmanager
def pet_kiosk(svc, width=1440, disable_webgl=False):
    from playwright.sync_api import sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")

    class ConnectingCodex(FakeCodex):
        async def create_thread(self, *args):
            await asyncio.Event().wait()

    host = InteractionHost(svc, codex=ConnectingCodex())
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(service=svc, kiosk_host=host), host="127.0.0.1", port=0, log_level="error"
        )
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=executable,
                args=[
                    "--no-sandbox",
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    "--autoplay-policy=no-user-gesture-required",
                    *(
                        ["--disable-webgl"]
                        if disable_webgl
                        else ["--enable-unsafe-swiftshader", "--use-angle=swiftshader"]
                    ),
                ],
            )
            try:
                page = browser.new_page(
                    viewport={"width": width, "height": 900 if width > 1000 else 812},
                    permissions=["microphone", "camera"],
                )
                # Start unarmed so settings can change without interrupting a guest.
                page.add_init_script(
                    "navigator.permissions.query = async () => ({state: 'prompt'})"
                )
                # Wobnimo renders in a shared offscreen WebGL canvas and presents on a 2D canvas.
                page.add_init_script("""
                    const getContext = HTMLCanvasElement.prototype.getContext;
                    HTMLCanvasElement.prototype.getContext = function (...args) {
                        const context = getContext.apply(this, args);
                        if (args[0] === 'webgl2' && context) window.petGraphicsCanvas = this;
                        return context;
                    };
                """)
                page.set_default_timeout(8000)
                page.goto(f"http://127.0.0.1:{port}/")
                yield page, host
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(timeout=5)


def choose_character(page, name):
    page.get_by_role("button", name="Cài đặt", exact=True).click()
    page.get_by_role("combobox", name="Nhân vật", exact=True).click()
    page.get_by_role("option", name=name, exact=True).click()
    page.get_by_role("button", name="Đóng", exact=True).click()


def test_pet_only_tracks_pointer_near_its_panel(svc):
    from playwright.sync_api import expect

    with pet_kiosk(svc) as (page, _host):
        choose_character(page, "Pet")
        pet = page.locator(".assistant-pet")
        expect(pet).to_have_attribute("data-renderer", "webgl")
        rect = pet.bounding_box()
        page.evaluate("""() => {
            window.petPointerLeaves = 0;
            window.menuPointerMoves = 0;
            document.addEventListener('pointerleave', () => window.petPointerLeaves++);
            window.addEventListener('pointermove', () => window.menuPointerMoves++);
        }""")
        right = rect["x"] + rect["width"]
        middle = rect["y"] + rect["height"] / 2
        page.mouse.move(right - 10, middle)
        page.mouse.move(right + 24, middle)
        assert page.evaluate("window.petPointerLeaves") == 0
        page.mouse.move(right + 25, middle)
        assert page.evaluate("window.petPointerLeaves") == 1
        # The cursor remains on the page/menu; only the Pet's tracking is cleared.
        page.mouse.move(1100, middle)
        assert page.evaluate("window.petPointerLeaves") == 2
        assert page.evaluate("window.menuPointerMoves") == 4
        page.mouse.move(right - 10, middle)
        assert page.evaluate("window.petPointerLeaves") == 2
        expect(pet.locator("canvas")).to_have_attribute("aria-label", "Volt, idle")


@pytest.mark.parametrize("width", [1440, 375])
def test_pet_selection_persists_and_voice_never_connects_talking_head(svc, width):
    from playwright.sync_api import expect

    with pet_kiosk(svc, width) as (page, host):
        expect(page.locator(".avatar-assistant")).to_have_attribute("data-engine", "livetalking")
        choose_character(page, "Pet")
        pet = page.locator(".assistant-pet")
        expect(pet).to_have_attribute("data-state", "idle")
        expect(pet).to_have_attribute("data-renderer", "webgl")
        expect(pet.locator("canvas")).to_be_visible()
        expect(pet.locator("canvas")).to_have_attribute("aria-label", "Volt, idle")
        pet.locator("canvas").dblclick()
        expect(pet.locator("canvas")).to_have_attribute("aria-label", "Volt, celebrating")
        expect(pet.locator("canvas")).to_have_attribute("aria-label", "Volt, idle", timeout=7000)
        page.reload()
        expect(page.locator(".avatar-assistant")).to_have_attribute("data-engine", "pet")
        expect(pet).to_have_attribute("data-renderer", "webgl")
        page.screenshot(path=f"output/pet-soft-green-{width}.png")
        avatar_requests = []
        errors = []
        page.on(
            "request",
            lambda request: (
                avatar_requests.append(request.url) if "/api/avatar" in request.url else None
            ),
        )
        page.on(
            "websocket",
            lambda ws: avatar_requests.append(ws.url) if "/api/avatar" in ws.url else None,
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.get_by_role("button", name="Bật micro", exact=True).click()
        page.get_by_role("button", name="Bắt đầu nói", exact=True).click()
        expect(page.locator(".menu-workspace")).to_be_visible()
        loop = host.tick_task.get_loop()

        def emit(kind, **values):
            asyncio.run_coroutine_threadsafe(host.emit(kind, **values), loop).result(3)

        emit("status", status="listening", message="Đang lắng nghe")
        expect(pet).to_have_attribute("data-state", "listening")
        expect(pet.locator("canvas")).to_have_attribute("aria-label", "Volt, listening")
        stage = page.locator(".avatar-stage").bounding_box()
        emit("transcript", role="assistant", text="Mình giúp bạn chọn món. " * 20)
        expect(page.get_by_role("log")).to_contain_text("Mình giúp bạn chọn món.")
        assert page.locator(".avatar-stage").bounding_box() == stage
        page.get_by_role("button", name="Cài đặt", exact=True).click()
        expect(page.get_by_role("combobox", name="Nhân vật", exact=True)).to_be_disabled()
        page.get_by_role("button", name="Đóng", exact=True).click()
        # The actual PCM player, not a transcript or a timer, drives the speaking state.
        emit("voice_turn", role="assistant")
        emit(
            "audio",
            audio={
                "data": base64.b64encode(b"\x10\x00" * 48000).decode(),
                "sampleRate": 48000,
                "numChannels": 1,
            },
        )
        expect(pet).to_have_attribute("data-state", "speaking")
        expect(pet.locator("canvas")).to_have_attribute("aria-label", "Volt, speaking")
        emit("voice_turn", role="user")
        expect(pet).to_have_attribute("data-state", "listening")
        emit("status", status="connecting", message="Đang kết nối")
        expect(pet).to_have_attribute("data-state", "thinking")
        expect(pet.locator("canvas")).to_have_attribute("aria-label", "Volt, thinking")
        emit("status", status="unavailable", message="Tiếp tục trên màn hình")
        expect(pet).to_have_attribute("data-state", "error")
        expect(pet.locator("canvas")).to_have_attribute("aria-label", "Volt, error")
        emit("status", status="listening", message="Đang lắng nghe")
        expect(pet).to_have_attribute("data-state", "listening")
        output = Path("output/pet")
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / f"pet-{width}.png"))
        page.get_by_role("button", name="Tắt micro", exact=True).click()
        expect(pet).to_have_attribute("data-state", "idle")
        assert not avatar_requests, avatar_requests
        assert not errors, errors
        # The upstream shared renderer rebuilds its shader after a real context loss.
        page.evaluate("""() => {
            window.petContextLoss = window.petGraphicsCanvas.getContext('webgl2')
                .getExtension('WEBGL_lose_context');
            window.petContextLoss.loseContext();
        }""")
        page.wait_for_function("window.petGraphicsCanvas.getContext('webgl2').isContextLost()")
        page.evaluate("window.petContextLoss.restoreContext()")
        page.wait_for_function("""() => {
            if (window.petGraphicsCanvas.getContext('webgl2').isContextLost()) return false;
            const canvas = document.querySelector('.pet-webgl');
            const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
            return pixels.some((value, index) => index % 4 === 3 && value > 0);
        }""")
        assert not errors, errors
        choose_character(page, "Avatar 3D")
        expect(page.locator(".avatar-assistant")).to_have_attribute("data-engine", "livetalking")
        expect(page.locator(".avatar-stage > img")).to_be_visible()
        expect(pet).to_have_count(0)
        page.reload()
        expect(page.locator(".avatar-assistant")).to_have_attribute("data-engine", "livetalking")
        # Switching back still attempts the current talking-head transport.
        avatar_requests.clear()
        page.route("**/api/avatar/status", lambda route: route.fulfill(status=404, body="{}"))
        page.get_by_role("button", name="Bật micro", exact=True).click()
        page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for()
        assert any("/api/avatar/status" in url for url in avatar_requests), avatar_requests
        page.get_by_role("button", name="Tắt micro", exact=True).click()


def test_pet_without_webgl_still_displays_robot(svc):
    from playwright.sync_api import expect

    with pet_kiosk(svc, disable_webgl=True) as (page, _host):
        choose_character(page, "Pet")
        expect(page.locator(".assistant-pet")).to_have_attribute("data-renderer", "fallback")
        expect(page.locator(".pet-fallback")).to_be_visible()
        page.wait_for_function("""() => {
            const image = document.querySelector('img.pet-fallback');
            return image?.complete && image.naturalWidth > 0;
        }""")
        expect(page.locator(".avatar-stage > img")).to_have_count(0)


def test_pet_hears_trend_through_the_webrtc_speaker_not_socket_pcm(svc):
    import math
    from array import array

    from playwright.sync_api import expect

    with pet_kiosk(svc) as (page, host):
        choose_character(page, "Pet")
        pet = page.locator(".assistant-pet")
        socket_pcm = []

        def watch(ws):
            if ws.url.endswith("/api/kiosk"):
                ws.on(
                    "framereceived",
                    lambda frame: (
                        socket_pcm.append(frame)
                        if isinstance(frame, str) and '"type": "audio"' in frame
                        else None
                    ),
                )

        page.on("websocket", watch)
        page.get_by_role("button", name="Bật micro", exact=True).click()
        page.get_by_role("button", name="Bắt đầu nói", exact=True).click()
        for _ in range(100):
            if host.speaker is not None and host.speaker.connected:
                break
            time.sleep(0.1)
        assert host.speaker is not None and host.speaker.connected, "speaker WebRTC connected"
        loop = host.tick_task.get_loop()

        def run(coroutine):
            return asyncio.run_coroutine_threadsafe(coroutine, loop).result(3)

        run(host.emit("status", status="listening", message="Đang lắng nghe"))
        tone = array(
            "h", (int(9000 * math.sin(2 * math.pi * 330 * i / 48000)) for i in range(48000 * 2))
        )
        audio = {
            "data": base64.b64encode(tone.tobytes()).decode(),
            "sampleRate": 48000,
            "numChannels": 1,
        }
        run(host._assistant_audio(audio))
        expect(pet).to_have_attribute("data-state", "speaking")
        # The level meter reads the received WebRTC track: speech reached the browser.
        heights = (
            "[...document.querySelectorAll('.assistant-wave span')]"
            ".map(s => parseFloat(s.style.height))"
        )
        peak = 0
        for _ in range(40):
            peak = max(peak, max(page.evaluate(heights)))
            if peak > 10:
                break
            time.sleep(0.05)
        assert peak > 10, f"wave height {peak}px"
        expect(pet).to_have_attribute("data-state", "listening", timeout=6000)
        assert not socket_pcm, "Trend's speech must not also travel as socket PCM"
        assert host.audio_metrics["speaker_transport"]["underruns"] == 0
        page.get_by_role("button", name="Tắt micro", exact=True).click()
        for _ in range(50):
            if host.speaker is None:
                break
            time.sleep(0.1)
        assert host.speaker is None, "turning the microphone off closes the speaker"
