"""Real speech playback at session boundaries, without a camera or model service."""

import asyncio
import shutil
import threading
import time

import pytest
import uvicorn
from test_kiosk_runtime import Clock, FakeCodex, observation

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost, boundary_speech


@pytest.mark.parametrize("native_failure", [False, True])
@pytest.mark.parametrize(
    "camera_source,browser_camera_missing", [("local", False), ("local", True), ("device", False)]
)
def test_greeting_waits_for_native_connection_and_goodbye_uses_guest_voice(
    svc, native_failure, browser_camera_missing, camera_source
):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium needed")

    ready = asyncio.Event()

    class ConnectingCodex(FakeCodex):
        async def create_thread(self, *args):
            if native_failure:
                raise RuntimeError("native_unavailable")
            return await super().create_thread(*args)

        async def start_filtered_voice(self, thread):
            await ready.wait()

    class Fusion:
        async def start(self):
            pass

        async def begin(self, *args):
            pass

        async def playback(self, playing):
            pass

        async def audio(self, pcm):
            pass

        async def end(self):
            pass

        async def close(self):
            pass

    clock = Clock()
    host = InteractionHost(svc, codex=ConnectingCodex(), fusion=Fusion(), clock=clock, wall=clock)
    original_command = host.command

    async def command_with_boundary(message):
        result = await original_command(message)
        if message.get("type") == "voice_setting" and message.get("voice") == "rio":
            # A guest notification can arrive before the settings acknowledgment.
            await host.emit(
                "session", session_token=host.token, voice=host.codex.voice, **host.snapshot()
            )
        return result

    host.command = command_with_boundary
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
                ],
            )
            try:
                page = browser.new_page(permissions=["camera", "microphone"])
                page.add_init_script(
                    """
                    window.captureRequests = [];
                    window.cameraPackets = 0;
                    const send = WebSocket.prototype.send;
                    WebSocket.prototype.send = function(data) {
                        if (data instanceof Uint8Array && data[0] === 2) window.cameraPackets++;
                        return send.call(this, data);
                    };
                    window.boundaryAnnouncements = [];
                    const BoundarySocket = window.WebSocket;
                    window.WebSocket = class extends BoundarySocket {
                        constructor(...args) {
                            super(...args);
                            this.addEventListener('message', ({data}) => {
                                if (typeof data !== 'string') return;
                                const event = JSON.parse(data);
                                if (event.announcement)
                                    window.boundaryAnnouncements.push(event.announcement);
                            });
                        }
                    };
                    const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                    navigator.mediaDevices.getUserMedia = async constraints => {
                        window.captureRequests.push(constraints);
                        if (constraints.video && CAMERA_MISSING)
                            throw new DOMException('Webcam owned by server', 'NotReadableError');
                        const stream = await capture(constraints);
                        if (constraints.video) window.lastVideoTrack = stream.getVideoTracks()[0];
                        if (constraints.audio) window.lastAudioTrack = stream.getAudioTracks()[0];
                        return stream;
                    };
                """.replace("CAMERA_MISSING", str(browser_camera_missing).lower())
                )
                page.add_init_script(
                    """navigator.permissions.query = async () => ({state: 'prompt'});"""
                )
                page.set_default_timeout(4000)
                delayed_open = (
                    camera_source == "local" and not native_failure and not browser_camera_missing
                )
                if delayed_open:
                    page.add_init_script(
                        """const OriginalSocket = window.WebSocket;
                        window.WebSocket = class extends OriginalSocket {
                            openDelivered = false;
                            get readyState() {
                                const state = super.readyState;
                                return !this.openDelivered && state === OriginalSocket.OPEN
                                    ? OriginalSocket.CONNECTING : state;
                            }
                            set onopen(handler) {
                                super.onopen = event => {
                                    window.voiceOpenWaiting = true;
                                    setTimeout(() => {
                                        this.openDelivered = true;
                                        handler.call(this, event);
                                    }, 800);
                                };
                            }
                        };"""
                    )
                # Start from a different valid voice so selecting Maple is a real change.
                page.add_init_script("""if (localStorage.getItem('trendcoffee.voice') === null)
                    localStorage.setItem('trendcoffee.voice', 'cove');""")
                page.goto(f"http://127.0.0.1:{port}/")
                # Configure before arming: the idle screen intentionally contains only the avatar.
                page.get_by_role("button", name="Cài đặt", exact=True).click()
                picker = page.get_by_role("combobox", name="Giọng nói", exact=True)
                picker.click()
                page.get_by_role("option", name="Maple", exact=True).click()
                page.wait_for_function(
                    "() => localStorage.getItem('trendcoffee.voice') === 'maple'"
                )
                if camera_source == "device":
                    page.get_by_role("combobox", name="Nguồn camera").click()
                    page.get_by_role("option", name="Camera thiết bị này", exact=True).click()
                page.get_by_role("dialog").get_by_role("button", name="Đóng", exact=True).click()
                page.get_by_role("button", name="Bật micro", exact=True).click()
                if delayed_open:
                    page.wait_for_function("() => window.voiceOpenWaiting === true")
                    page.get_by_role("button", name="Cài đặt", exact=True).click()
                    assert page.get_by_role("combobox", name="Giọng nói").is_disabled()
                    page.get_by_role("dialog").get_by_role(
                        "button", name="Đóng", exact=True
                    ).click()
                page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for(timeout=2500)
                assert host.codex.voice == "maple"
                expect(page.locator(".menu-workspace")).to_be_hidden()
                expect(page.locator(".cart-sidebar")).to_be_hidden()
                expect(
                    page.get_by_role("button", name="Nhắn tin với Trend", exact=True)
                ).to_have_count(0)
                expect(page.get_by_role("button", name="Hỗ trợ", exact=True)).to_have_count(0)
                expect(page.locator("#support-panel-title")).to_have_count(0)
                expect(
                    page.get_by_role("button", name="Tự chọn trên menu", exact=True)
                ).to_have_count(0)
                page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for()

                loop = host.tick_task.get_loop()

                def camera(available):
                    asyncio.run_coroutine_threadsafe(
                        host.emit("camera", local_available=available), loop
                    ).result(2)

                camera(True)
                if camera_source == "local":
                    assert page.evaluate("captureRequests.every(r => !r.video)")
                else:
                    page.wait_for_function("() => window.lastVideoTrack?.readyState === 'live'")
                    assert host.camera_source == "device"
                    assert page.evaluate("captureRequests[0].audio && !!captureRequests[0].video")
                    assert page.evaluate("captureRequests.filter(r => r.video).length") == 1
                camera(False)
                expected_captures = 1 if camera_source == "device" else 0
                page.wait_for_function(
                    "() => captureRequests.filter(r => r.video).length === "
                    + str(expected_captures)
                )
                if camera_source == "device":
                    page.wait_for_function("() => window.lastVideoTrack?.readyState === 'live'")
                camera(True)
                if camera_source == "device":
                    page.wait_for_function("() => window.lastVideoTrack?.readyState === 'live'")
                expect(page.get_by_role("button", name="Tắt micro", exact=True)).to_be_visible()

                async def approach():
                    for seq in range(11):
                        clock.value = 100 + seq * 0.2
                        await host.observe(observation(seq + 1, clock.value))

                asyncio.run_coroutine_threadsafe(approach(), host.tick_task.get_loop()).result(2)
                expect(page.get_by_role("log")).not_to_contain_text("Chào bạn")
                assert page.evaluate("boundaryAnnouncements.length") == 0
                expect(page.locator(".menu-workspace")).to_be_visible()
                expect(page.locator(".cart-sidebar")).to_be_visible()
                if not native_failure:
                    loop.call_soon_threadsafe(ready.set)
                    expect(page.get_by_role("log")).to_contain_text(
                        "Chào bạn, Trend có thể giúp bạn chọn món gì?", timeout=2000
                    )
                    assert page.evaluate("boundaryAnnouncements.at(-1).voice") == "maple"
                    assert (
                        page.evaluate("boundaryAnnouncements.at(-1).audio.data")
                        == boundary_speech("greeting", "maple")["audio"]["data"]
                    )
                page.get_by_role("button", name="Cài đặt", exact=True).click()
                picker.click()
                page.get_by_role("option", name="Rio", exact=True).click()
                page.wait_for_function("() => localStorage.getItem('trendcoffee.voice') === 'rio'")
                assert host.voice == "rio" and host.codex.voice == "maple" and host.active
                expect(
                    page.get_by_text("Giọng mới áp dụng từ phiên tiếp theo.", exact=True)
                ).to_be_visible()
                page.get_by_role("dialog").get_by_role("button", name="Đóng", exact=True).click()
                expect(
                    page.get_by_role("button", name="Kết thúc phiên nói", exact=True)
                ).to_have_count(0)

                async def leave():
                    for seq in range(12, 29):
                        clock.value = 100 + seq * 0.2
                        await host.observe(observation(seq, clock.value, distance=1.2))

                asyncio.run_coroutine_threadsafe(leave(), host.tick_task.get_loop()).result(2)
                expect(page.get_by_role("log")).to_contain_text(
                    "Tạm biệt bạn, hẹn gặp lại tại Trend Coffee.", timeout=2000
                )
                expect(page.get_by_role("log")).not_to_contain_text("Chào bạn")
                expect(page.get_by_role("button", name="Bắt đầu nói", exact=True)).to_be_visible()
                assert not host.active
                expect(page.locator(".menu-workspace")).to_be_hidden()
                expect(page.locator(".cart-sidebar")).to_be_hidden()
                assert host.codex.voice == "rio"
                assert page.evaluate("boundaryAnnouncements.at(-1).voice") == "maple"
                assert (
                    page.evaluate("boundaryAnnouncements.at(-1).audio.data")
                    == boundary_speech("goodbye", "maple")["audio"]["data"]
                )
                page.wait_for_function(
                    "() => [...document.querySelectorAll('.assistant-wave span')].some(e => parseFloat(e.style.height) > 6)",
                    timeout=2000,
                )
                page.get_by_role("button", name="Bắt đầu nói", exact=True).click()
                if not native_failure:
                    expect(page.get_by_role("log")).to_contain_text("Chào bạn")
                    expect(page.get_by_role("log")).not_to_contain_text("Tạm biệt")
                    assert page.evaluate("boundaryAnnouncements.at(-1).voice") == "rio"
                    assert (
                        page.evaluate("boundaryAnnouncements.at(-1).audio.data")
                        == boundary_speech("greeting", "rio")["audio"]["data"]
                    )
                else:
                    expect(page.get_by_role("log")).not_to_contain_text("Chào bạn")
                if camera_source == "device":
                    page.wait_for_function("() => window.cameraPackets > 0")
                    page.evaluate(
                        """() => {
                            window.lastVideoTrack.stop();
                            window.lastVideoTrack.dispatchEvent(new Event('ended'));
                        }"""
                    )
                    page.wait_for_function("() => window.lastAudioTrack?.readyState === 'live'")
                    expect(page.get_by_role("button", name="Tắt micro", exact=True)).to_be_visible()
                    assert host.active and host.controller is not None
                    page.wait_for_timeout(200)
                    count = page.evaluate("window.cameraPackets")
                    page.wait_for_timeout(250)
                    assert page.evaluate("window.cameraPackets") == count
                page.get_by_role("button", name="Tắt micro", exact=True).click()
                expect(page.locator(".avatar-assistant")).to_have_attribute("data-phase", "off")
                page.wait_for_timeout(250)
                expect(page.get_by_role("button", name="Bật micro", exact=True)).to_be_visible()
                page.reload()
                page.get_by_role("button", name="Cài đặt", exact=True).click()
                expect(page.get_by_role("combobox", name="Giọng nói", exact=True)).to_have_text(
                    "Rio"
                )
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(5)
