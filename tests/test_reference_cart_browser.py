"""The order layout stays in the sidebar while cart edits and totals remain shared."""

import shutil
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from test_menu_batch import catalog as catalog

from trendcoffee.api import create_app


@pytest.mark.parametrize(
    "width,height,rail_width",
    [
        (1440, 1000, 340),
        (768, 1000, 300),
        (375, 1000, 375),
        (667, 375, 300),
        (812, 375, 300),
        (320, 568, 320),
    ],
)
def test_reference_cart_rail_and_editing(catalog, width, height, rail_width):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")
    server = uvicorn.Server(
        uvicorn.Config(create_app(service=catalog), host="127.0.0.1", port=0, log_level="error")
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
                page.set_default_timeout(5000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}/")
                for name in ["Cà phê muối", "Cà phê sữa", "Trà Bắc"]:
                    page.get_by_role("button", name="Xem " + name, exact=True).click()
                    page.locator(".product-add").get_by_role("button", name="Thêm").click()
                page.get_by_role("button", name="Mang đi", exact=True).click()
                cart = page.get_by_role("complementary", name="Giỏ hàng và thanh toán")
                box = cart.bounding_box()
                assert abs(box["width"] - rail_width) <= 1, box
                assert abs(box["x"] + box["width"] - width) <= 1, box
                expect(page.locator(".menu-workspace")).to_be_visible()
                expect(page.locator(".cart-review")).to_have_count(0)
                expect(
                    cart.get_by_role("button", name="Mang đi", exact=True)
                ).to_have_attribute("aria-pressed", "true")
                cards = cart.locator(".cart-line")
                expect(cards).to_have_count(3)
                milk = cards.filter(has=page.get_by_role("heading", name="Cà phê sữa", exact=True))
                expect(milk.locator(".kfc-cart-line-total")).to_have_text("40.000đ")
                milk.get_by_role("button", name="Tăng Cà phê sữa", exact=True).click()
                expect(milk.get_by_label("Số lượng Cà phê sữa", exact=True)).to_have_text("2")
                expect(cart.locator(".kfc-cart-summary-value > strong")).to_have_text("182.000đ")
                milk.get_by_role("button", name="Giảm Cà phê sữa", exact=True).click()
                expect(cart.locator(".kfc-cart-summary-value > strong")).to_have_text("142.000đ")
                milk.get_by_text("Tùy chỉnh", exact=True).click()
                milk.get_by_role("textbox", name="Ghi chú cho Cà phê sữa").fill("ít đá")
                expect(milk.locator(".kfc-cart-note")).to_have_text("ít đá")
                milk.get_by_role("button", name="Bỏ Cà phê sữa", exact=True).click()
                expect(cards).to_have_count(2)
                cart.get_by_role("button", name="Xóa tất cả", exact=True).click()
                expect(cards).to_have_count(0)
                expect(page.locator(".checkout-dock-action")).to_be_disabled()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                output = Path("output")
                output.mkdir(exist_ok=True)
                page.screenshot(path=str(output / f"inline-cart-{width}-{height}.png"))
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(5)
        assert not worker.is_alive()
