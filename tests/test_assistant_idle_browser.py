"""Idle assistant fills the viewport; an actual guest restores the ordering layout."""

import asyncio
import shutil
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost


@pytest.mark.parametrize(
    "width,height", [(1440, 1000), (1080, 1920), (768, 1000), (375, 812), (667, 375)]
)
def test_idle_assistant_and_guest_layout_transitions(svc, width, height):
    from playwright.sync_api import expect, sync_playwright

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
                ],
            )
            try:
                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    permissions=["microphone", "camera"],
                )
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.set_default_timeout(4000)
                page.goto(f"http://127.0.0.1:{port}/")
                begin = page.get_by_role("button", name="Bắt đầu nói", exact=True)
                begin.wait_for()

                def idle_fits():
                    expect(page.locator(".menu-workspace")).to_be_hidden()
                    expect(page.locator(".cart-sidebar")).to_be_hidden()
                    expect(page.locator(".topbar")).to_be_hidden()
                    for selector in [
                        ".avatar-assistant",
                        ".avatar-stage",
                        ".assistant-wave",
                        ".assistant-controls",
                    ]:
                        box = page.locator(selector).bounding_box()
                        assert box and box["width"] > 0 and box["height"] > 0
                        assert box["x"] >= -1 and box["y"] >= -1, (selector, box)
                        assert box["x"] + box["width"] <= width + 1, (selector, box)
                        assert box["y"] + box["height"] <= height + 1, (selector, box)
                    box = page.locator(".avatar-assistant").bounding_box()
                    assert abs(box["x"] + box["width"] / 2 - width / 2) <= 1
                    assert box["height"] >= height - 40
                    if height > 1000:
                        # Tall kiosk displays must scale the avatar with available height.
                        assert page.locator(".avatar-stage > img").evaluate(
                            """e => Math.min(e.clientHeight, e.clientWidth * e.naturalHeight /
                                e.naturalWidth) >= e.clientHeight * 0.85"""
                        )
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert page.evaluate("document.documentElement.scrollHeight <= innerHeight")

                idle_fits()
                page.evaluate("window.idleAvatar = document.querySelector('.avatar-assistant')")
                begin.click()
                expect(page.locator(".menu-workspace")).to_be_visible()
                expect(page.locator(".cart-sidebar")).to_be_hidden()
                expect(page.locator(".topbar")).to_be_visible()
                assert host.active
                loop = host.tick_task.get_loop()
                scene_before_reply = page.locator(".avatar-stage").bounding_box()
                # Long replies occupy their own area, never the character image.
                asyncio.run_coroutine_threadsafe(
                    host.emit(
                        "transcript",
                        role="assistant",
                        text="Đơn mang đi đã lưu. " * 12,
                        turnId="layout-test",
                        partial=False,
                    ),
                    loop,
                ).result(2)
                expect(page.get_by_role("log")).to_contain_text("Đơn mang đi đã lưu.")
                scene = page.locator(".avatar-stage").bounding_box()
                log = page.locator(".assistant-conversation").bounding_box()
                assert scene and scene["height"] > 0 and log
                assert abs(scene["height"] - scene_before_reply["height"]) < 1
                assert abs(scene["y"] - scene_before_reply["y"]) < 1
                assert (
                    scene["y"] + scene["height"] <= log["y"] + 1
                    or scene["x"] + scene["width"] <= log["x"] + 1
                ), (scene, log)
                for turn_id, role, text in [
                    ("customer-2", "user", "Mở menu lên giúp mình."),
                    ("reply-2", "assistant", "Nghe rồi, mình mở menu cho bạn đây."),
                    ("reply-3", "assistant", "Một phản hồi dài hơn. " * 16),
                ]:
                    asyncio.run_coroutine_threadsafe(
                        host.emit(
                            "transcript", role=role, text=text, turnId=turn_id, partial=False
                        ),
                        loop,
                    ).result(2)
                    expect(page.get_by_role("log")).to_contain_text(text.strip())
                    current = page.locator(".avatar-stage").bounding_box()
                    assert abs(current["height"] - scene_before_reply["height"]) < 1
                    assert abs(current["y"] - scene_before_reply["y"]) < 1
                    assert page.locator(".assistant-bubble").count() <= 2
                layout_output = Path("output/kiosk-navigation")
                layout_output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(layout_output / f"avatar-clear-{width}x{height}.png"))
                # An active guest may wait for native/Fusion; this is not kiosk idle.
                asyncio.run_coroutine_threadsafe(
                    host.emit("status", status="waiting", message="Đang chờ người nói."), loop
                ).result(2)
                expect(page.locator(".menu-workspace")).to_be_visible()
                page.get_by_role("button", name="Xem Cà phê sữa", exact=True).click()
                page.locator(".product-add").get_by_role(
                    "button", name="Thêm vào giỏ", exact=False
                ).click()
                expect(page.locator(".cart-line")).to_have_count(1)
                page.get_by_role("button", name="Cài đặt", exact=True).click()
                expect(page.get_by_role("dialog")).to_be_visible()
                page.get_by_role("combobox", name="Giọng nói", exact=True).click()
                expect(page.get_by_role("listbox")).to_be_visible()
                asyncio.run_coroutine_threadsafe(host.end("next_guest"), loop).result(2)
                expect(begin).to_be_visible()
                expect(page.get_by_role("dialog")).to_have_count(0)
                expect(page.get_by_role("listbox")).to_have_count(0)
                expect(page.get_by_role("log")).to_contain_text("Tạm biệt bạn")
                idle_fits()
                assert page.evaluate(
                    "window.idleAvatar === document.querySelector('.avatar-assistant')"
                )
                bubble = page.locator(".assistant-bubble").bounding_box()
                assert bubble and 0 <= bubble["y"] < bubble["y"] + bubble["height"] <= height
                assert abs(bubble["x"] + bubble["width"] / 2 - width / 2) <= 1
                output = Path("output")
                output.mkdir(exist_ok=True)
                page.screenshot(path=str(output / f"assistant-idle-{width}x{height}.png"))
                begin.click()
                expect(page.locator(".menu-workspace")).to_be_visible()
                expect(page.locator(".cart-sidebar")).to_be_hidden()
                expect(page.locator(".cart-line")).to_have_count(0)
                expect(page.locator(".assistant-conversation")).to_be_empty()
                page.get_by_role("button", name="Tắt micro", exact=True).click()
                expect(page.get_by_role("button", name="Bật micro", exact=True)).to_be_visible()
                expect(page.locator(".menu-workspace")).to_be_visible()
                expect(page.locator(".cart-sidebar")).to_be_hidden()
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(5)
