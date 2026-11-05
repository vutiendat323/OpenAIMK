"""Catalog scroll leaves the kiosk shell and assistant stationary."""

import shutil
import threading
import time

import pytest
import uvicorn
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost


@pytest.mark.parametrize("width,height", [(1440, 900), (375, 812), (667, 375)])
def test_menu_scroll_keeps_shell_stationary(svc, width, height):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")
    coffee = next(item for item in svc.menu() if item["id"] == "coffee")
    svc.ingest({"menu": {"items": [{**coffee, "id": f"coffee-{i}"} for i in range(40)]}})
    host = InteractionHost(svc, codex=FakeCodex())
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
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=executable, args=["--no-sandbox"])
            try:
                page = browser.new_page(
                    viewport={"width": width, "height": height}, reduced_motion="reduce"
                )
                page.goto(f"http://127.0.0.1:{port}")
                expect(page.get_by_role("heading", name="Thực đơn")).to_be_visible()
                stage = page.locator(".avatar-stage").bounding_box()
                poster = page.locator(".avatar-stage img").bounding_box()
                assert stage and poster
                assert poster["height"] <= stage["height"] + 1, (stage, poster)
                assert poster["width"] <= stage["width"] + 1, (stage, poster)
                menu = page.locator(".menu-workspace")
                fixed = [".seasonal-banner", ".topbar", ".avatar-assistant", ".checkout-dock"]
                before = [page.locator(selector).bounding_box() for selector in fixed]
                rail_before = page.locator(".category-rail").bounding_box()
                assert (
                    page.locator(".category-rail").evaluate("e => getComputedStyle(e).overflowY")
                    == "visible"
                )
                menu.evaluate("e => e.scrollTop = 600")
                button = page.get_by_role("button", name="Cuộn lên đầu trang")
                expect(button).to_be_visible()
                assert menu.evaluate("e => e.scrollTop") > 200
                assert page.locator(".category-rail").bounding_box()["y"] < rail_before["y"] - 200
                for selector, old in zip(fixed, before, strict=True):
                    current = page.locator(selector).bounding_box()
                    assert abs(current["y"] - old["y"]) < 1, selector
                    assert abs(current["height"] - old["height"]) < 1, selector
                assert page.evaluate("window.scrollY") == 0
                button.click()
                assert menu.evaluate("e => e.scrollTop") == 0
                expect(button).to_have_count(0)
                assert page.evaluate("document.documentElement.scrollHeight <= innerHeight + 1")
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(5)
