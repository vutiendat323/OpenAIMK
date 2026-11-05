"""Ctrl+Alt+K turns the on-screen keyboard off and on; turning it on shows it again."""

import shutil
import threading
import time

import pytest
import uvicorn
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost

KEYBOARD = ".kiosk-keyboard-wrapper"


def test_ctrl_alt_k_twice_hides_then_shows_the_keyboard_for_the_focused_field(svc):
    """2026-11-05: the second press changed the setting but showed nothing, because the field
    kept its focus and never fired another focus event."""
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
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(f"http://127.0.0.1:{port}")
                expect(page.get_by_role("heading", name="Thực đơn")).to_be_visible()
                field = page.locator("input[type=text], input:not([type]), textarea").first
                field.click()
                expect(page.locator(KEYBOARD)).to_be_visible()
                page.keyboard.press("Control+Alt+k")
                expect(page.locator(KEYBOARD)).to_have_count(0)
                page.keyboard.press("Control+Alt+k")
                expect(page.locator(KEYBOARD)).to_be_visible()  # same field, still focused
                page.keyboard.press("Control+Alt+k")
                expect(page.locator(KEYBOARD)).to_have_count(0)
                page.keyboard.press("Control+Alt+k")
                expect(page.locator(KEYBOARD)).to_be_visible()
                field.blur()
                page.keyboard.press("Control+Alt+k")  # off with no field focused
                page.keyboard.press("Control+Alt+k")  # on again: nothing to show yet
                expect(page.locator(KEYBOARD)).to_have_count(0)
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(timeout=5)
