"""Category rail/filter behavior with merchant-sourced names, IDs and flags."""

import shutil
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from test_merchant_categories import category_catalog as category_catalog

from trendcoffee.api import create_app


@pytest.mark.parametrize("width", [1440, 768, 375])
def test_categories_match_merchant_order_names_and_product_flags(category_catalog, tmp_path, width):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium required")
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(service=category_catalog), host="127.0.0.1", port=0, log_level="error"
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
            try:
                page = browser.new_page(viewport={"width": width, "height": 1000})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{port}")
                rail = page.get_by_role("navigation", name="Danh mục thực đơn")
                expect(rail.get_by_role("button")).to_have_text(
                    [
                        "Tất cả",
                        "Bán chạy",
                        "Món mới",
                        "Món ăn",
                        "Cà phê",
                        "Món bánh",
                        "Món trà",
                        "Nước theo mùa",
                    ]
                )
                for name, expected in [
                    ("Bán chạy", "Cà phê sữa"),
                    ("Món mới", "Trà Bắc"),
                    ("Món bánh", "Bánh Tiramisu"),
                    ("Món trà", "Trà Bắc"),
                ]:
                    rail.get_by_role("button", name=name, exact=True).click()
                    expect(page.locator(".product-card")).to_have_count(1)
                    expect(
                        page.get_by_role("button", name="Xem " + expected, exact=True)
                    ).to_have_count(1)
                    expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
                rail.get_by_role("button", name="Nước theo mùa", exact=True).click()
                expect(page.locator(".product-card")).to_have_count(0)
                rail.get_by_role("button", name="Tất cả", exact=True).click()
                expect(page.locator(".product-card")).to_have_count(3)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                page.screenshot(path=str(tmp_path / f"merchant-categories-{width}.png"))
                output = Path("output")
                output.mkdir(exist_ok=True)
                page.screenshot(path=str(output / f"merchant-categories-{width}.png"))
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(5)
        assert not thread.is_alive()
