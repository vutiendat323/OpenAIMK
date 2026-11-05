"""Navigation against isolated local fixtures; no merchant or native connection."""

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


def test_agent_display_tools_emit_navigation_without_checkout(svc):
    async def run():
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=FakeCodex())
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        tool, _ = host.codex.callbacks[host.thread_id]
        try:
            for name, args, view in [
                ("kiosk_menu", {}, "menu"),
                ("kiosk_cart", {"action": "view"}, "cart"),
                ("kiosk_payment", {}, "payment"),
                ("kiosk_progress", {}, "progress"),
            ]:
                await tool({"tool": name, "arguments": args})
                assert [e for e in events if e["type"] == "view"][-1]["view"] == view
            assert svc.progress(host.token)["orders"] == []
            assert host.cart == []
        finally:
            await host.close()

    asyncio.run(run())


@pytest.mark.parametrize("width", [1440, 768, 375])
@pytest.mark.parametrize("merchant_connected", [True, False])
def test_customer_navigation_sidebar(svc, width, tmp_path, merchant_connected):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")
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
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=executable, args=["--no-sandbox"])
            try:
                page = browser.new_page(viewport={"width": width, "height": 1000})
                page.set_default_timeout(5000)
                errors, submissions = [], []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on(
                    "request",
                    lambda r: (
                        submissions.append(r.url)
                        if r.method == "POST" and r.url.endswith("/api/checkout")
                        else None
                    ),
                )

                def connected_menu(route):
                    response = route.fetch()
                    data = response.json()
                    data["merchant_connected"] = merchant_connected
                    route.fulfill(response=response, json=data)

                page.route("**/api/menu", connected_menu)
                page.route(
                    "**/api/tables",
                    lambda route: route.fulfill(
                        json={
                            "tables": [
                                {
                                    "id": "2",
                                    "name": "2",
                                    "status": "available",
                                    "available": True,
                                    "location": "",
                                }
                            ],
                            "first_available": {"name": "2"},
                            "available_count": 1,
                            "live": True,
                            "fetched_at": "2026-10-31T00:00:00Z",
                        }
                    ),
                )
                page.goto(f"http://127.0.0.1:{port}")
                toggle = page.get_by_role("button", name="Mở hoặc đóng thanh bên")
                expect(toggle).to_be_visible()
                panel = page.locator("#checkout-panel")
                expect(panel).to_be_hidden()
                toggle.click()
                expect(panel).to_be_visible()
                assert panel.evaluate("e => getComputedStyle(e).outlineStyle") == "none"
                if width == 1440:
                    resize = page.get_by_role("separator", name="Thay đổi độ rộng thanh bên")
                    before = panel.bounding_box()["width"]
                    handle = resize.bounding_box()
                    x, y = handle["x"] + handle["width"] / 2, handle["y"] + 100
                    page.mouse.move(x, y)
                    page.mouse.down()
                    page.mouse.move(x - 80, y, steps=4)
                    page.mouse.up()
                    assert panel.bounding_box()["width"] > before + 70
                    resize.focus()
                    page.keyboard.press("ArrowRight")
                    assert panel.bounding_box()["width"] < before + 70
                panel.get_by_role("button", name="Thanh toán", exact=True).click()
                expect(
                    panel.get_by_text("Chưa có đơn hàng để hiển thị QR thanh toán.")
                ).to_be_visible()
                panel.get_by_role("button", name="Đơn đã đặt", exact=True).click()
                expect(panel.locator("#progress-panel-title")).to_be_visible()
                expect(panel.get_by_text("Chưa có yêu cầu nào", exact=True)).to_be_visible()
                expect(panel.get_by_role("button", name="Cập nhật tiến độ")).to_have_count(0)
                empty_preview = Path("output/kiosk-navigation")
                empty_preview.mkdir(parents=True, exist_ok=True)
                panel.screenshot(path=str(empty_preview / f"orders-empty-{width}.png"))
                assert not submissions
                expect(page.locator(".checkout-dock-action")).to_be_disabled()
                expect(page.locator(".checkout-dock-cancel")).to_be_visible()
                panel.get_by_role("button", name="Đóng thanh bên", exact=True).click()
                expect(panel).to_be_hidden()
                expect(toggle).to_be_focused()
                page.get_by_role("button", name="Xem Cà phê sữa", exact=True).click()
                page.locator(".product-add").get_by_role(
                    "button", name="Thêm vào giỏ", exact=False
                ).click()
                dock = page.locator(".checkout-dock")
                expect(dock.locator(".dock-product")).to_contain_text("Cà phê sữa")
                expect(dock.locator(".dock-product")).to_contain_text("1 × 30.000đ")
                expect(dock.locator(".dock-total strong")).to_have_text("30.000đ")
                preview = Path("output/kiosk-navigation")
                preview.mkdir(parents=True, exist_ok=True)
                dock.screenshot(path=str(preview / f"dock-cart-{width}.png"))
                dock.get_by_role("button", name="Bỏ món Cà phê sữa").click()
                expect(dock.locator(".dock-product")).to_have_count(0)
                expect(dock.locator(".dock-total strong")).to_have_text("0đ")
                page.get_by_role("button", name="Xem Cà phê sữa", exact=True).click()
                page.locator(".product-add").get_by_role(
                    "button", name="Thêm vào giỏ", exact=False
                ).click()
                header_cart = page.locator(".header-actions").get_by_role(
                    "button", name="Xem giỏ hàng"
                )
                expect(header_cart.locator(".checkout-dock-count")).to_have_text("1")
                header_cart.click()
                expect(panel.locator(".kfc-cart")).to_be_visible()
                page.locator(".checkout-dock-action").click()
                expect(panel.get_by_role("alert")).to_contain_text(
                    "Bạn chọn dùng tại quán hoặc mang đi"
                )
                panel.get_by_role("combobox", name="Tại quán", exact=True).click()
                if merchant_connected:
                    page.get_by_role("option", name="Bàn 2 - Bàn trống", exact=True).click()
                else:
                    expect(page.get_by_role("listbox")).to_contain_text(
                        "Chưa kết nối danh sách bàn"
                    )
                    expect(panel.locator("input#table-label")).to_have_count(0)
                    expect(page.locator(".kiosk-keyboard-wrapper")).to_have_count(0)
                    page.keyboard.press("Escape")
                expect(
                    panel.get_by_role("combobox", name="Tại quán", exact=True)
                ).to_have_attribute("aria-pressed", "true")
                panel.get_by_role("button", name="Mang đi", exact=True).click()
                page.locator(".checkout-dock-action").click()
                expect(panel.locator(".checkout-result")).to_be_visible()
                panel.get_by_role("button", name="Đơn đã đặt", exact=True).click()
                expect(panel.locator(".kfc-order-card")).to_have_count(1)
                expect(panel.locator("#progress-panel-title")).to_be_visible()
                assert len(submissions) == 1
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                output = Path("output/kiosk-navigation")
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / f"navigation-{width}.png"))
                page.keyboard.press("Escape")
                expect(panel).to_be_hidden()
                expect(toggle).to_be_focused()
                toggle.click()
                expect(panel.locator("#progress-panel-title")).to_be_visible()
                if width <= 1000:
                    page.locator(".sidebar-backdrop").click(position={"x": 2, "y": 200})
                    expect(panel).to_be_hidden()
                page.reload()
                expect(panel).to_be_hidden()
                toggle.click()
                panel.get_by_role("button", name="Đơn đã đặt", exact=True).click()
                expect(panel.get_by_text("Chưa có yêu cầu nào", exact=True)).to_be_visible()
                expect(panel.locator(".kfc-order-card")).to_have_count(0)
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(5)


def test_empty_screen_does_not_keep_restarting_guest_sessions(svc):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")
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
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=executable, args=["--no-sandbox"])
            try:
                page = browser.new_page()
                page.clock.install()
                sessions = []
                page.on(
                    "request",
                    lambda r: (
                        sessions.append(1)
                        if r.method == "POST" and r.url.endswith("/api/sessions")
                        else None
                    ),
                )
                page.goto(f"http://127.0.0.1:{port}")
                toggle = page.get_by_role("button", name="Mở hoặc đóng thanh bên")
                expect(toggle).to_be_visible()
                assert len(sessions) == 1
                page.clock.fast_forward(121000)
                expect(toggle).to_be_visible()
                page.wait_for_timeout(100)
                assert len(sessions) == 1, "Untouched screen keeps recreating sessions"
                toggle.click()
                page.clock.fast_forward(91000)
                expect(page.locator(".idle-notice")).to_be_visible()
                page.clock.fast_forward(30000)
                expect(toggle).to_be_visible()
                expect(page.locator("#checkout-panel")).to_be_hidden()
                assert len(sessions) == 2, "Touched guest must still expire for privacy"
                page.clock.fast_forward(121000)
                expect(toggle).to_be_visible()
                assert len(sessions) == 2, "Expired guest must not restart repeatedly"
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(5)
