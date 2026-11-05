"""Touch auto-selection and delayed table responses against isolated merchant fixtures."""

import shutil
import threading
import time

import pytest
import uvicorn
from test_live_tables import merchant
from test_live_tables import tables as tables

from trendcoffee.api import create_app


@pytest.fixture
def table_app(svc, tables):
    merchant(svc, tables)
    server = uvicorn.Server(
        uvicorn.Config(create_app(service=svc), host="127.0.0.1", port=0, log_level="error")
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
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(5)
        assert not thread.is_alive()


@pytest.fixture
def page(table_app):
    from playwright.sync_api import sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium needed")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(table_app)
            page.get_by_role("button", name="Xem Cà phê sữa", exact=True).wait_for()
            yield page
        finally:
            browser.close()


def test_touch_auto_selects_first_free_and_refreshes_after_switching_mode(page, tables):
    from playwright.sync_api import expect

    page.get_by_role("combobox", name="Tại quán", exact=True).click()
    table_select = page.locator("#table-label")
    expect(page.locator(".cart-table-trigger")).to_have_count(0)
    expect(page.locator(".topbar .fulfillment")).to_have_count(0)
    expect(page.locator(".topbar .table-control")).to_have_count(0)
    expect(page.get_by_role("listbox")).to_be_visible()
    expect(table_select).to_have_attribute("aria-description", "Bàn 7")
    expect(page.get_by_role("option", name="Bàn 3 - Đã đặt")).to_have_attribute("aria-disabled", "true")
    expect(page.get_by_role("option", name="Bàn 9 - Không xác định")).to_have_attribute("aria-disabled", "true")
    page.get_by_role("option", name="Bàn 5 - Bàn trống").click()
    expect(table_select).to_have_attribute("aria-description", "Bàn 5")
    expect(page.get_by_role("listbox")).to_have_count(0)
    page.get_by_role("button", name="Mang đi", exact=True).click()
    tables[1]["status"] = "reserved"
    page.get_by_role("combobox", name="Tại quán", exact=True).click()
    expect(table_select).to_have_attribute("aria-description", "Bàn 5")
    page.keyboard.press("Escape")
    for table in tables:
        table["status"] = "reserved"
    page.get_by_role("button", name="Mang đi", exact=True).click()
    page.get_by_role("combobox", name="Tại quán", exact=True).click()
    expect(table_select).not_to_have_attribute("aria-description")
    page.keyboard.press("Escape")
    expect(page.get_by_role("alert")).to_contain_text("chưa có bàn trống")


@pytest.mark.parametrize("later", ["takeaway", "next_guest"])
def test_delayed_table_read_does_not_override_newer_customer_choice(page, later):
    from playwright.sync_api import expect

    page.clock.install()
    held = []
    page.route("**/api/tables", lambda route: held.append(route))
    with page.expect_request("**/api/tables"):
        page.get_by_role("combobox", name="Tại quán", exact=True).click()
    expect(page.get_by_role("listbox")).to_be_visible()
    expect(page.get_by_role("status")).to_contain_text("Đang tải bàn")
    page.keyboard.press("Escape")
    route = held.pop()
    response = route.fetch()
    if later == "takeaway":
        page.get_by_role("button", name="Mang đi", exact=True).click()
    else:
        with page.expect_response("**/api/sessions"):
            page.clock.fast_forward(121000)
    route.fulfill(response=response)
    page.wait_for_timeout(100)
    expect(page.get_by_label("Số bàn", exact=True)).to_have_count(0)
