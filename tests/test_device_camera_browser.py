"""Device-camera frames reach the API over WebRTC, with socket JPEGs as the fallback.

Both paths must keep delivering while page timers are throttled (background tab).
"""

import shutil
import threading
import time

import pytest
import uvicorn
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost


class RefusingCamera:
    """A server that cannot answer WebRTC: the browser must keep sending JPEGs."""

    def __init__(self, on_jpeg):
        pass

    async def answer(self, sdp):
        raise ValueError("no WebRTC camera")

    async def close(self):
        pass


@pytest.mark.parametrize("transport", ["webrtc", "socket_fallback"])
def test_device_camera_frames_reach_the_api_when_page_timer_is_throttled(
    svc, record_property, transport
):
    from playwright.sync_api import sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")
    host = InteractionHost(svc, codex=FakeCodex())
    if transport == "socket_fallback":
        host.camera_factory = RefusingCamera
    frames = []

    async def camera_frame(jpeg):
        assert jpeg[:2] == b"\xff\xd8"
        frames.append(time.monotonic())

    host.camera_frame = camera_frame
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(service=svc, kiosk_host=host), host="127.0.0.1", port=0, log_level="error"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        with sync_playwright() as p:
            browser = p.chromium.launch(
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
                page.add_init_script("""
                    navigator.permissions.query = async () => ({state: 'prompt'});
                    const interval = window.setInterval.bind(window);
                    window.setInterval = (callback, delay, ...args) =>
                        interval(callback, delay < 70 ? 1000 : delay, ...args);
                    window.__socketJpegs = 0;
                    const socketSend = WebSocket.prototype.send;
                    WebSocket.prototype.send = function (data) {
                        if (data instanceof Uint8Array && data[0] === 2) window.__socketJpegs++;
                        return socketSend.call(this, data);
                    };
                """)
                page.goto(f"http://127.0.0.1:{port}/")
                page.get_by_role("button", name="Cài đặt", exact=True).click()
                page.get_by_role("combobox", name="Nguồn camera").click()
                page.get_by_role("option", name="Camera thiết bị này", exact=True).click()
                page.get_by_role("dialog").get_by_role("button", name="Đóng", exact=True).click()
                page.get_by_role("button", name="Bật micro", exact=True).click()
                page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for()
                page.wait_for_timeout(2500)
                # Receiving real JPEGs at the API, not merely testing timer callbacks.
                assert len(frames) >= 15, f"Only {len(frames)} camera frames in 2.5 seconds"
                record_property("camera_frames_in_2_5_seconds", len(frames))
                record_property(
                    "camera_fps", round((len(frames) - 1) / (frames[-1] - frames[0]), 1)
                )
                assert not host.active  # Camera must work while waiting for a guest too.
                socket_jpegs = page.evaluate("window.__socketJpegs")
                page.wait_for_timeout(1000)
                socket_jpegs_later = page.evaluate("window.__socketJpegs") - socket_jpegs
                if transport == "webrtc":
                    assert host.camera_peer is not None and host.camera_peer.connected
                    assert host.camera_peer.metrics["forwarded"] >= 10
                    assert socket_jpegs_later == 0, "no socket JPEGs once WebRTC carries video"
                    record_property("socket_jpegs_before_webrtc", socket_jpegs)
                else:
                    assert host.camera_peer is None
                    assert socket_jpegs_later >= 5
                page.get_by_role("button", name="Tắt micro", exact=True).click()
                page.wait_for_timeout(300)
                stopped = len(frames)
                page.wait_for_timeout(300)
                assert len(frames) == stopped
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(5)


def test_the_chosen_camera_source_survives_a_page_reload(svc):
    """A laptop that chose its own camera keeps it; a fresh browser keeps the kiosk camera."""
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")
    host = InteractionHost(svc, codex=FakeCodex())
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(service=svc, kiosk_host=host), host="127.0.0.1", port=0, log_level="error"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=executable,
                args=[
                    "--no-sandbox",
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                ],
            )
            try:
                picker = None
                for context_index in range(2):
                    page = browser.new_context(permissions=["camera", "microphone"]).new_page()
                    page.add_init_script(
                        "navigator.permissions.query = async () => ({state: 'prompt'})"
                    )
                    page.goto(f"http://127.0.0.1:{port}/")
                    page.get_by_role("button", name="Cài đặt", exact=True).click()
                    picker = page.get_by_role("combobox", name="Nguồn camera")
                    expect(picker).to_contain_text("Camera tại kiosk")  # default per browser
                    if context_index == 0:
                        picker.click()
                        page.get_by_role("option", name="Camera thiết bị này", exact=True).click()
                        page.reload()
                        page.get_by_role("button", name="Cài đặt", exact=True).click()
                        picker = page.get_by_role("combobox", name="Nguồn camera")
                        expect(picker).to_contain_text("Camera thiết bị này")
                        page.get_by_role("dialog").get_by_role(
                            "button", name="Đóng", exact=True
                        ).click()
                        page.get_by_role("button", name="Bật micro", exact=True).click()
                        page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for()
                        assert host.camera_source == "device"
                        page.get_by_role("button", name="Tắt micro", exact=True).click()
                        page.wait_for_timeout(300)
                    page.context.close()
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(5)
