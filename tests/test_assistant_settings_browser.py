"""General preferences apply immediately and preserve voice, camera and guest state."""

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
    "width,height", [(1440, 1000), (851, 605), (768, 1000), (375, 812), (667, 375)]
)
def test_settings_popup_preserves_choices_and_cart_and_returns_keyboard_focus(svc, width, height):
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
            try:
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.add_init_script(
                    "navigator.permissions.query = async () => ({state: 'prompt'});"
                )
                page.goto(f"http://127.0.0.1:{port}/")
                expect(page.get_by_role("button", name="Bật micro", exact=True)).to_be_visible()
                expect(page.get_by_role("combobox")).to_have_count(0)
                page.get_by_role("button", name="Xem Cà phê sữa", exact=True).click()
                page.locator(".product-add").get_by_role("button", name="Thêm").click()
                trigger = page.get_by_role("button", name="Cài đặt", exact=True)
                trigger.click()
                popup = page.get_by_role("dialog")
                expect(popup).to_have_accessible_name("Cài đặt")
                expect(popup).to_be_visible()
                picker = popup.get_by_role("combobox", name="Giọng nói", exact=True)
                expect(picker).to_have_text("Maple")
                picker.click()
                expect(page.get_by_role("listbox")).to_be_visible()
                page.keyboard.press("Escape")
                expect(popup).to_be_visible()
                expect(picker).to_be_focused()
                picker.click()
                page.get_by_role("option", name="Rio", exact=True).click()
                page.wait_for_function("() => localStorage.getItem('trendcoffee.voice') === 'rio'")
                popup.get_by_role("combobox", name="Nguồn camera", exact=True).click()
                page.get_by_role("option", name="Camera thiết bị này", exact=True).click()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                output = Path("output")
                output.mkdir(exist_ok=True)
                popup.get_by_role("button", name="Tối", exact=True).click()
                expect(page.locator("html")).to_have_attribute("data-theme", "dark")
                expect(popup).to_have_css("background-color", "rgb(32, 34, 37)")
                expect(page.locator(".product-card").first).to_have_css(
                    "background-color", "rgb(36, 42, 37)"
                )
                popup.get_by_role("button", name="Hệ thống", exact=True).click()
                page.emulate_media(color_scheme="dark")
                expect(page.locator("html")).to_have_attribute("data-theme", "dark")
                page.emulate_media(color_scheme="light")
                expect(page.locator("html")).to_have_attribute("data-theme", "light")
                popup.get_by_role("button", name="Sáng", exact=True).click()
                page.emulate_media(color_scheme="dark")
                expect(page.locator("html")).to_have_attribute("data-theme", "light")
                popup.get_by_role("combobox", name="Ngôn ngữ", exact=True).click()
                page.get_by_role("option", name="English", exact=True).click()
                expect(popup).to_have_accessible_name("Settings")
                expect(page.locator("html")).to_have_attribute("lang", "en")
                for section in ["Profile", "Data", "About"]:
                    popup.get_by_role("button", name=section, exact=True).click()
                    expect(popup.locator(".settings-content")).to_have_text("")
                popup.get_by_role("button", name="General", exact=True).click()
                expect(popup.get_by_role("combobox", name="Voice", exact=True)).to_have_text("Rio")
                expect(
                    popup.get_by_role("combobox", name="Camera source", exact=True)
                ).to_have_text("This device’s camera")
                box = popup.bounding_box()
                assert 0 <= box["x"] and box["x"] + box["width"] <= width
                assert 0 <= box["y"] and box["y"] + box["height"] <= height
                assert popup.evaluate("e => e.scrollWidth <= e.clientWidth")
                assert popup.locator(".settings-content").evaluate(
                    "e => e.scrollWidth <= e.clientWidth"
                )
                if width >= 792:
                    assert abs(box["width"] - 760) < 1
                popup.screenshot(
                    path=str(output / f"general-settings-light-{width}.png"), animations="disabled"
                )
                popup.get_by_role("button", name="Dark", exact=True).click()
                popup.screenshot(
                    path=str(output / f"general-settings-dark-{width}.png"), animations="disabled"
                )
                camera = popup.get_by_role("combobox", name="Camera source", exact=True)
                camera.click()
                menu = page.get_by_role("listbox")
                expect(menu).to_be_visible()
                expect(menu).to_have_css("background-color", "rgb(52, 54, 56)")
                selected = page.get_by_role("option", name="This device’s camera", exact=True)
                expect(selected).to_have_attribute("data-state", "checked")
                expect(selected.locator(".settings-select-check")).to_be_visible()
                menu_box = menu.bounding_box()
                assert 0 <= menu_box["x"] and menu_box["x"] + menu_box["width"] <= width
                assert 0 <= menu_box["y"] and menu_box["y"] + menu_box["height"] <= height
                menu.screenshot(
                    path=str(output / f"settings-camera-menu-{width}.png"), animations="disabled"
                )
                page.keyboard.press("Home")
                expect(page.get_by_role("option", name="Kiosk camera", exact=True)).to_be_focused()
                page.keyboard.press("Enter")
                expect(camera).to_have_text("Kiosk camera")
                camera.click()
                page.get_by_role("option", name="This device’s camera", exact=True).click()
                page.keyboard.press("Escape")
                expect(page.locator(".cart-line")).to_have_count(1)
                expect(page.get_by_role("button", name="Settings", exact=True)).to_be_focused()
                expect(
                    page.get_by_role("button", name="Turn on microphone", exact=True)
                ).to_be_visible()
                page.get_by_role("button", name="View cart").first.click()
                expect(page.get_by_role("heading", name="My cart", exact=True)).to_be_visible()
                expect(page.get_by_role("heading", name="Menu", exact=True)).to_be_visible()
                page.reload()
                expect(page.locator("html")).to_have_attribute("data-theme", "dark")
                expect(page.locator("html")).to_have_attribute("lang", "en")
                page.get_by_role("button", name="Settings", exact=True).click()
                expect(popup.get_by_role("button", name="Dark", exact=True)).to_have_attribute(
                    "aria-pressed", "true"
                )
                expect(popup.get_by_role("combobox", name="Voice", exact=True)).to_have_text("Rio")
                popup.get_by_role("combobox", name="Language", exact=True).click()
                page.get_by_role("option", name="Tiếng Việt", exact=True).click()
                popup.get_by_role("button", name="Sáng", exact=True).click()
                # Recheck the existing close/reopen and camera-selection behavior in Vietnamese.
                popup.get_by_role("combobox", name="Nguồn camera", exact=True).click()
                page.get_by_role("option", name="Camera thiết bị này", exact=True).click()
                page.keyboard.press("Escape")
                page.get_by_role("button", name="Xem Cà phê sữa", exact=True).click()
                page.locator(".product-add").get_by_role("button", name="Thêm").click()
                trigger.click()

                page.keyboard.press("Escape")
                expect(popup).to_have_count(0)
                expect(trigger).to_be_focused()
                expect(page.locator(".cart-line")).to_have_count(1)
                trigger.click()
                expect(popup.get_by_role("combobox", name="Giọng nói", exact=True)).to_have_text(
                    "Rio"
                )
                expect(popup.get_by_role("combobox", name="Nguồn camera", exact=True)).to_have_text(
                    "Camera thiết bị này"
                )
                popup.get_by_role("button", name="Đóng", exact=True).click()
                expect(popup).to_have_count(0)
                expect(page.get_by_role("combobox")).to_have_count(0)
                expect(page.get_by_role("button", name="Bật micro", exact=True)).to_be_visible()
                assert host.controller is None and not host.active
                assert not errors, errors
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
        assert not worker.is_alive()
