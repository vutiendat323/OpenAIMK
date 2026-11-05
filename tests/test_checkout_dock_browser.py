"""The footer cancels a draft and submits through the existing local checkout once."""

import shutil
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from trendcoffee.api import create_app


@pytest.mark.parametrize("width", [1279, 375, 320])
def test_dock_cancel_cart_and_checkout(svc, width):
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
            try:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.set_default_timeout(5000)
                submissions, errors = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "request",
                    lambda request: (
                        submissions.append(request.url)
                        if request.method == "POST" and request.url.endswith("/api/checkout")
                        else None
                    ),
                )
                page.goto(f"http://127.0.0.1:{port}")
                dock = page.locator(".checkout-dock")
                action = dock.locator(".checkout-dock-action")
                expect(action).to_be_disabled()

                def add_coffee():
                    page.get_by_role("button", name="Xem Cà phê sữa", exact=True).click()
                    page.locator(".product-add").get_by_role(
                        "button", name="Thêm vào giỏ", exact=False
                    ).click()
                    expect(dock.locator(".checkout-dock-count")).to_have_text("1")
                    expect(dock.locator(".dock-total strong")).to_have_text("30.000đ")

                add_coffee()
                dock.get_by_role("button", name="Hủy", exact=True).click()
                expect(dock.locator(".checkout-dock-count")).to_have_text("0")
                expect(action).to_be_disabled()
                assert not submissions

                add_coffee()
                output = Path("output")
                output.mkdir(exist_ok=True)
                dock.screenshot(path=str(output / f"kfc-footer-{width}.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                dock.get_by_role("button", name="Xem giỏ hàng", exact=True).click()
                cart = page.locator(".kfc-cart")
                expect(cart).to_be_visible()
                assert not submissions
                expect(page.locator(".menu-workspace")).to_be_visible()
                expect(page.locator(".cart-review")).to_have_count(0)
                cart.get_by_role("button", name="Tăng Cà phê sữa", exact=True).click()
                expect(cart.locator(".kfc-cart-line-total")).to_have_text("60.000đ")
                expect(cart.get_by_label("Tổng số món", exact=True)).to_have_text("2")
                cart.get_by_text("Tùy chỉnh", exact=True).click()
                cart.get_by_label("Ghi chú cho Cà phê sữa", exact=True).fill("ít đá")
                cart.get_by_role("button", name="Mang đi", exact=True).click()
                expect(cart.locator(".kfc-add-more")).to_have_count(0)
                expect(cart.locator(".kfc-cart-footer")).to_have_count(0)
                expect(dock.locator(".checkout-dock-count")).to_have_text("2")
                expect(cart.locator(".kfc-cart-note")).to_have_text("ít đá")
                cart.get_by_role("button", name="Xóa tất cả", exact=True).click()
                expect(cart.locator(".cart-line")).to_have_count(0)
                expect(action).to_be_disabled()
                page.keyboard.press("Escape")
                add_coffee()
                page.screenshot(path=str(output / f"cart-sidebar-{width}.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                action.click()
                expect(page.locator(".checkout-result")).to_be_visible()
                expect(dock.get_by_role("button", name="Đơn mới", exact=True)).to_have_count(0)
                action.click()
                assert len(submissions) == 1
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(5)
        assert not worker.is_alive()
