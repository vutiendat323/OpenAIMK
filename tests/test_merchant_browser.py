"""Exercise QR rendering, settlement polling and guest reset without live merchant writes."""

import copy
import shutil
import threading
import time

import httpx
import pytest
import uvicorn
from test_menu_batch import catalog as catalog

from trendcoffee.api import create_app
from trendcoffee.merchant import MerchantClient

IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


@pytest.mark.parametrize("start_width", [1440, 375])
def test_browser_multi_drink_checkout_shows_merchant_image_then_paid(
    catalog, tmp_path, start_width
):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium needed")
    current = {
        "slug": "merchant-browser",
        "branch": {"slug": "ba9355f797"},
        "subtotal": 142000,
        "status": "pending",
        "orderItems": [],
        "payment": {
            "amount": 142000,
            "qrCode": IMAGE,
            "paymentMethod": "bank-transfer",
            "statusCode": "pending",
        },
    }
    posted = []

    def handler(request):
        if request.method == "POST":
            import json

            body = json.loads(request.content)
            posted.append(body)
            current["orderItems"] = [
                {"variant": {"slug": i["variant"]}, "quantity": i["quantity"]}
                for i in body["orderItems"]
            ]
        return httpx.Response(200, json={"result": copy.deepcopy(current)})

    catalog.merchant = MerchantClient(transport=httpx.MockTransport(handler))
    server = uvicorn.Server(
        uvicorn.Config(create_app(service=catalog), host="127.0.0.1", port=0, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    errors = []
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
                page = browser.new_page(viewport={"width": start_width, "height": 900})
                page.on("pageerror", lambda error: errors.append(str(error)))
                requests = []
                page.on("request", lambda request: requests.append((request.method, request.url)))
                page.goto(f"http://127.0.0.1:{port}")
                page.get_by_label("Tìm món", exact=True).wait_for()
                page.get_by_label("Tìm món", exact=True).fill("ca phe muoi ca phe sua tra bac")
                expect(page.locator(".product-card")).to_have_count(3)
                for drink in ("Cà phê muối", "Cà phê sữa", "Trà Bắc"):
                    page.get_by_role("button", name="Xem " + drink, exact=True).click()
                    page.locator(".product-add").get_by_role("button", name="Thêm").click()
                page.locator(".checkout-dock-summary").click()
                page.get_by_role("button", name="Mang đi", exact=True).click()
                page.locator(".checkout-dock-action").click()
                expect(page.get_by_role("dialog")).to_have_count(0)
                result = page.locator(".checkout-result")
                expect(result.get_by_role("heading", name="THANK YOU!", exact=True)).to_be_visible()
                expect(result).not_to_contain_text("Đơn đã được gửi đến quán")
                expect(result.locator(".checkout-check")).to_have_text("CHECK")
                expect(result).to_have_css("border-radius", "0px")
                image = page.get_by_role("img", name="Mã QR thanh toán do Trend Coffee cung cấp")
                expect(image).to_be_in_viewport()
                expect(image).to_have_attribute("src", IMAGE)
                assert image.evaluate("image => image.complete && image.naturalWidth > 0")
                assert (
                    sum(
                        method == "POST" and url.endswith("/api/checkout")
                        for method, url in requests
                    )
                    == 1
                )
                assert not any(
                    url.endswith("/api/quotes") or url.endswith("/payment") for _, url in requests
                )
                assert len(posted) == 1 and len(posted[0]["orderItems"]) == 3
                for width in (1440, 768, 375):
                    page.set_viewport_size({"width": width, "height": 1050})
                    image.scroll_into_view_if_needed()
                    expect(image).to_be_in_viewport()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert image.bounding_box()["width"] >= 200
                    expect(page.locator(".payment-qr")).to_contain_text("142.000đ")
                    page.screenshot(path=str(tmp_path / f"merchant-qr-{width}.png"))
                # Expired QR stays hidden while late merchant settlement is still reconciled.
                import datetime

                current["createdAt"] = (
                    datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=901)
                ).isoformat()
                expect(image).to_have_count(0, timeout=7000)
                expect(
                    page.get_by_role("button", name="Cập nhật thanh toán", exact=True)
                ).to_be_visible()
                current["status"] = "paid"
                current["payment"]["statusCode"] = "completed"
                expect(
                    page.get_by_text("Quán đã xác nhận thanh toán thành công.", exact=True)
                ).to_be_visible(timeout=7000)
                expect(image).to_have_count(0)
                result.locator(".checkout-check").click()
                expect(page.locator(".service-panel")).to_be_visible()
                expect(
                    page.get_by_role("button", name="Kết thúc phiên · Khách tiếp theo", exact=True)
                ).to_have_count(0)
                page.reload()
                expect(page.locator(".payment-qr")).to_have_count(0)
                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(5)
        assert not thread.is_alive()
