"""Manual browser smoke with fake devices and an isolated fixture DB.
Run: PYTHONPATH=tests:. .venv/bin/python tests/browser_voice_smoke.py
"""

import asyncio
import base64
import json
import math
import shutil
import struct
import threading
import time
from pathlib import Path

import uvicorn
from conftest import svc
from playwright.async_api import async_playwright
from test_kiosk_runtime import FakeCodex
from test_menu_batch import catalog

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost


async def main():
    folder = Path(".runtime/voice-browser")
    folder.mkdir(parents=True, exist_ok=True)
    database = folder / str(time.time_ns())
    database.mkdir()
    service = svc.__wrapped__(database)
    service = catalog.__wrapped__(service)
    milk_id = service.menu("cà phê sữa")[0]["id"]
    host = InteractionHost(service, codex=FakeCodex())
    app = create_app(service=service, kiosk_host=host)
    voice_connections = []

    async def observed_app(scope, receive, send):
        if scope["type"] == "websocket" and scope["path"] == "/api/kiosk":
            voice_connections.append(send)
        await app(scope, receive, send)

    server = uvicorn.Server(
        uvicorn.Config(
            observed_app,
            host="127.0.0.1",
            port=8091,
            log_level="error",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.05)
    errors = []
    accessibility = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                executable_path=shutil.which("chromium"),
                args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
            )
            context = await browser.new_context(permissions=["camera", "microphone"])
            page = await context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "console",
                lambda message: errors.append(message.text) if message.type == "error" else None,
            )
            axe = Path(".runtime/qa/axe.min.js")
            if axe.exists():

                async def serve_axe(route):
                    await route.fulfill(content_type="application/javascript", body=axe.read_text())

                await page.route("**/qa-axe.js", serve_axe)
            await page.goto("http://127.0.0.1:8091")
            await page.locator(".avatar-stage > img").wait_for()
            assert await page.locator(".avatar-stage > img").evaluate(
                "image => image.complete && image.naturalWidth > 0"
            )
            assert await page.locator(".product-card").count() == 51
            await page.screenshot(path=str(folder / "avatar-desktop-off.png"))
            await page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for()
            await page.get_by_role("button", name="Bắt đầu nói", exact=True).click()
            await page.get_by_text("Trợ lý giọng nói chưa được bật.", exact=False).wait_for()
            await page.get_by_role("button", name="Xem Cà phê sữa", exact=True).click()
            await page.locator(".product-add").get_by_role("button", name="Thêm").click()
            await page.get_by_role("button", name="Mang đi", exact=True).click()
            await page.wait_for_timeout(200)
            assert host.cart[0]["quantity"] == 1 and host.fulfillment == "takeaway"
            tool, _ = host.codex.callbacks[host.thread_id]
            future = asyncio.run_coroutine_threadsafe(
                tool(
                    {
                        "tool": "kiosk_cart",
                        "arguments": {"action": "add", "item_id": milk_id, "quantity": 1},
                    }
                ),
                host.tick_task.get_loop(),
            )
            await asyncio.wrap_future(future)
            await page.wait_for_timeout(200)
            assert host.cart[0]["quantity"] == 2

            await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(
                    tool(
                        {
                            "tool": "kiosk_menu",
                            "arguments": {
                                "query": "trái cây",
                                "item_ids": ["03d9fe8299", "009d435ea6"],
                            },
                        }
                    ),
                    host.tick_task.get_loop(),
                )
            )
            await page.get_by_role("button", name="Xem Trà vải đào", exact=True).wait_for()
            await page.get_by_role("button", name="Xem Cam tươi.", exact=True).wait_for()
            assert await page.locator(".product-card").count() == 2
            assert (
                await page.get_by_role("textbox", name="Tìm món", exact=True).input_value()
                == "trái cây"
            )
            await page.screenshot(path=str(folder / "menu-semantic-recommendation.png"))

            # Speech-search candidates must remain visible even when their
            # catalog name differs from the recognized phrase in the search box.
            for query in ["trà bắp miền Bắc", "trà bắp miền Nam", "trà bắp trà Nam"]:
                await asyncio.wrap_future(
                    asyncio.run_coroutine_threadsafe(
                        tool({"tool": "kiosk_menu", "arguments": {"query": query}}),
                        host.tick_task.get_loop(),
                    )
                )
                await page.get_by_role("button", name="Xem Trà Bắc", exact=True).wait_for()
                assert (
                    await page.get_by_role("textbox", name="Tìm món", exact=True).input_value()
                    == query
                )
                assert 1 <= await page.locator(".product-card").count() <= 3
            await page.screenshot(path=str(folder / "menu-spoken-candidates.png"))
            await page.get_by_role("textbox", name="Tìm món", exact=True).fill("vải")
            await page.get_by_role("button", name="Xem Trà vải đào", exact=True).wait_for()
            assert await page.get_by_role("button", name="Xem Trà Bắc", exact=True).count() == 0
            await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(
                    tool({"tool": "kiosk_menu", "arguments": {"query": "nước sao hỏa"}}),
                    host.tick_task.get_loop(),
                )
            )
            await page.wait_for_function(
                "() => document.querySelectorAll('.product-card').length === 0"
            )
            await page.get_by_role("button", name="Xóa tìm kiếm", exact=True).click()
            await page.wait_for_function(
                "() => document.querySelectorAll('.product-card').length === 51"
            )

            # Notes stay editable while the server is still acknowledging earlier keys.
            original_emit = host.emit

            async def delayed_state(kind, **data):
                if kind == "state":
                    await asyncio.sleep(0.06)
                await original_emit(kind, **data)

            host.emit = delayed_state
            await page.get_by_label("Chỉnh sửa Cà phê sữa", exact=True).click()
            item_note = page.get_by_role("textbox", name="Ghi chú cho Cà phê sữa", exact=True)
            await item_note.press_sequentially("ít đá nhé", delay=1)
            assert await item_note.input_value() == "ít đá nhé"
            for _ in range(100):
                if host.cart[0].get("note") == "ít đá nhé":
                    break
                await asyncio.sleep(0.02)
            assert host.cart[0]["note"] == "ít đá nhé"
            await page.get_by_text("Ghi chú cho đơn", exact=True).click()
            order_note = page.get_by_role("textbox", name="Ghi chú cho đơn hàng", exact=True)
            await order_note.press_sequentially("gọi tên Linh khi xong", delay=1)
            assert await order_note.input_value() == "gọi tên Linh khi xong"
            for _ in range(150):
                if host.order_note == "gọi tên Linh khi xong":
                    break
                await asyncio.sleep(0.02)
            assert host.order_note == "gọi tên Linh khi xong"
            host.emit = original_emit
            await page.get_by_role("textbox", name="Tìm món", exact=True).click()
            await page.screenshot(path=str(folder / "notes-voice-editing.png"))

            # UI fixture events exercise real PCM playback and the actual analyser graph.
            # They establish presentation behavior, not physical AV Fusion quality.
            async def conversation():
                await host.emit("status", status="listening", message="Trend đang lắng nghe bạn.")
                await host.emit("fusion", locked=True)
                await host.emit("transcript", role="user", text="Cho mình hai cà phê sữa mang đi.")
                await host.emit(
                    "transcript",
                    role="assistant",
                    text="Mình đã thêm hai cà phê sữa. Bạn kiểm tra giỏ nhé.",
                )
                pcm = b"".join(
                    struct.pack("<h", int(9000 * math.sin(2 * math.pi * 220 * i / 16000)))
                    for i in range(32000)
                )
                await host.emit(
                    "audio",
                    audio={
                        "data": base64.b64encode(pcm).decode(),
                        "sampleRate": 16000,
                        "numChannels": 1,
                    },
                )

            await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(conversation(), host.tick_task.get_loop())
            )
            await page.wait_for_function(
                "() => document.querySelector('.avatar-assistant')?.dataset.phase === 'speaking'"
            )
            await page.wait_for_function(
                "() => [...document.querySelectorAll('.assistant-wave span')].some(e => parseFloat(e.style.height) > 6)"
            )
            assert (
                await page.get_by_role("log", name="Hội thoại bằng giọng nói")
                .get_by_text("Cho mình hai cà phê sữa mang đi.", exact=True)
                .is_visible()
            )
            await page.screenshot(path=str(folder / "avatar-desktop-speaking.png"))
            # Voice checkout can happen while the whole-order note still has focus.
            await order_note.focus()
            order = await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(
                    tool({"tool": "kiosk_checkout", "arguments": {}}),
                    host.tick_task.get_loop(),
                )
            )
            assert order["lines"][0]["note"] == "ít đá nhé"
            assert order["order_note"] == "gọi tên Linh khi xong"
            await page.wait_for_function(
                "() => document.querySelectorAll('.cart-line').length === 0"
            )
            assert host.order_note == ""
            assert await page.locator('textarea[aria-label="Ghi chú cho đơn hàng"]').count() == 0
            before = host.token
            assert (
                await page.get_by_role("button", name="Kết thúc phiên nói", exact=True).count() == 0
            )
            await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(host.end("next_guest"), host.tick_task.get_loop())
            )
            await page.get_by_role("button", name="Bắt đầu nói", exact=True).wait_for()
            assert host.cart == []
            assert (
                await page.locator('textarea[aria-label="Ghi chú cho đơn hàng"]').input_value()
                == ""
            )
            assert (
                await page.get_by_text("Cho mình hai cà phê sữa mang đi.", exact=True).count() == 0
            )
            await page.get_by_role("button", name="Bắt đầu nói", exact=True).click()
            await page.get_by_text("Trợ lý giọng nói chưa được bật.", exact=False).wait_for()
            assert host.token != before and host.cart == []

            async def restart_connection():
                await voice_connections[-1]({"type": "websocket.close", "code": 1012})
                async with asyncio.timeout(3):
                    while host.controller is not None:
                        await asyncio.sleep(0.01)
                # A real API restart also resets its guest generation counter.
                host.generation = 0

            await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(restart_connection(), host.tick_task.get_loop())
            )
            async with asyncio.timeout(5):
                while len(voice_connections) < 2 or host.controller is None:
                    await asyncio.sleep(0.05)
            await page.get_by_role("button", name="Bắt đầu nói", exact=True).click()
            await page.get_by_text("Trợ lý giọng nói chưa được bật.", exact=False).wait_for()
            assert host.generation == 1
            await page.get_by_role("button", name="Tắt micro", exact=True).click()
            await page.get_by_role("button", name="Bật micro", exact=True).wait_for()
            count = len(voice_connections)
            await page.wait_for_timeout(1000)
            assert len(voice_connections) == count  # explicit mic-off never reconnects
            if axe.exists():
                await page.add_script_tag(url="/qa-axe.js")
            for width, height in [(1440, 1000), (768, 1024), (375, 812)]:
                await page.set_viewport_size({"width": width, "height": height})
                await page.wait_for_timeout(200)
                await page.screenshot(path=str(folder / f"{width}.png"))
                if axe.exists():
                    violations = await page.evaluate(
                        "async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v => ({id: v.id, nodes: v.nodes.map(n => ({html: n.html, targets: n.target}))}))"
                    )
                    accessibility.append({"width": width, "violations": violations})
                    assert not violations, violations
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    f"overflow at {width}"
                )
            print(
                json.dumps(
                    {
                        "browser_errors": errors,
                        "axe": accessibility,
                        "shared_cart": True,
                        "avatar_loaded": True,
                        "waveform_from_playback": True,
                        "voice_conversation": True,
                        "next_guest_isolated": True,
                        "reconnected_after_server_restart": True,
                        "breakpoints": [1440, 768, 375],
                    },
                    ensure_ascii=False,
                )
            )
            await browser.close()
            assert not errors
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 5)


if __name__ == "__main__":
    asyncio.run(main())
