"""Real browser journey against a disposable local-only database, never the merchant site."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest


def exercise_async_guest_boundaries(browser, base):
    """Hold replies to verify checkout locking and guest isolation after dismissing detail."""
    from playwright.sync_api import expect

    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.clock.install()
    page.route("**/api/sessions", lambda route: route.abort(), times=1)
    page.goto(base)
    page.get_by_role("button", name="Thử kết nối lại", exact=True).wait_for()
    with page.expect_response("**/api/sessions") as session_response:
        page.get_by_role("button", name="Thử kết nối lại", exact=True).click()
    token = session_response.value.json()["session_token"]
    page.get_by_role("button", name="Xem Cà phê đen", exact=True).wait_for()
    page.get_by_role("button", name="Xem Cà phê đen", exact=True).click()
    page.locator(".product-add").get_by_role("button", name="Thêm").click()
    page.get_by_role("button", name="Mang đi", exact=True).click()
    page.locator(".kfc-cart-customize").click()
    page.get_by_role("textbox", name="Ghi chú cho Cà phê đen").press_sequentially("ít đá", delay=5)
    page.get_by_role("textbox", name="Ghi chú cho đơn hàng").press_sequentially(
        "gọi khi đến nơi", delay=5
    )
    page.get_by_role("button", name="Xem Cà phê đen", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Đóng", exact=True).click()
    held = []
    page.route("**/api/checkout", lambda route: held.append(route))
    with page.expect_request("**/api/checkout"):
        page.get_by_role("button", name="Thanh toán", exact=True).click()
    expect(page.get_by_role("button", name="Tăng Cà phê đen", exact=True)).to_be_disabled()
    expect(page.get_by_role("button", name="Bỏ Cà phê đen", exact=True)).to_be_disabled()
    expect(page.get_by_role("button", name="Khách tiếp theo", exact=True)).to_have_count(0)
    expect(page.get_by_role("dialog")).to_have_count(0)
    route = held.pop()
    committed = route.fetch().json()
    assert committed["lines"][0]["note"] == "ít đá"
    assert committed["order_note"] == "gọi khi đến nơi"
    route.fulfill(status=502, json={"error": "upstream_error"})
    page.unroute("**/api/checkout")
    expect(page.get_by_role("button", name="Thanh toán", exact=True)).to_be_enabled()
    page.get_by_role("button", name="Mang đi", exact=True).click()
    page.get_by_role("button", name="Tăng Cà phê đen", exact=True).click()
    page.get_by_role("button", name="Giảm Cà phê đen", exact=True).click()
    # Whitespace normalization must not turn a lost-response retry into a new order.
    page.get_by_role("textbox", name="Ghi chú cho Cà phê đen").fill("ít đá  ")
    with page.expect_response("**/api/checkout") as retry:
        page.get_by_role("button", name="Thanh toán", exact=True).click()
    assert retry.value.json()["id"] == committed["id"]
    expect(page.get_by_text("Đã lưu yêu cầu của bạn!", exact=True)).to_be_visible()
    expect(page.locator(".cart-line")).to_have_count(0)
    assert (
        len(
            page.request.get(
                base + "/api/progress", headers={"Authorization": "Bearer " + token}
            ).json()["orders"]
        )
        == 1
    )

    # An identical new cart is a new order; a lost response still retries that same order.
    page.get_by_role("button", name="Xem Cà phê đen", exact=True).click()
    page.locator(".product-add").get_by_role("button", name="Thêm").click()
    committed_again = []

    def lose_checkout_response(route):
        committed_again.append(route.fetch().json())
        route.abort()

    page.route("**/api/checkout", lose_checkout_response, times=1)
    page.get_by_role("button", name="Thanh toán", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Kết nối chưa ổn định")
    with page.expect_response("**/api/checkout") as retried:
        page.get_by_role("button", name="Thanh toán", exact=True).click()
    assert retried.value.json()["id"] == committed_again[0]["id"]
    assert retried.value.json()["id"] != committed["id"]
    expect(page.locator(".cart-line")).to_have_count(0)
    assert (
        len(
            page.request.get(
                base + "/api/progress", headers={"Authorization": "Bearer " + token}
            ).json()["orders"]
        )
        == 2
    )
    with page.expect_response("**/api/sessions"):
        page.reload()
    page.get_by_role("button", name="Xem Cà phê đen", exact=True).wait_for()
    expect(page.locator(".checkout-result")).to_have_count(0)
    page.set_viewport_size({"width": 375, "height": 812})
    expect(page.get_by_role("button", name="Khách tiếp theo", exact=True)).to_have_count(0)
    page.get_by_role("button", name="Xem Cà phê đen", exact=True).click()
    page.locator(".product-add").get_by_role("button", name="Thêm").click()
    page.clock.fast_forward(91000)
    # No on-screen countdown any more (2026-11-05): Trend speaks the warning in a voice session.
    expect(page.get_by_text("không tương tác", exact=False)).to_have_count(0)
    expect(page.locator(".cart-line")).to_have_count(1)
    expect(page.get_by_role("dialog")).to_have_count(0)
    page.clock.fast_forward(30000)
    page.get_by_role("button", name="Xem Cà phê đen", exact=True).wait_for()
    expect(page.locator(".cart-line")).to_have_count(0)
    expect(page.get_by_role("button", name="Thanh toán", exact=True)).to_be_disabled()
    page.close()


def test_customer_and_staff_browser_journey(tmp_path):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium-browser") or shutil.which("chromium")
    if not executable:
        pytest.skip("Local Chromium executable required for browser QA")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    staff_token = "temporary-browser-test-secret"
    # Only the disposable test database gets refreshed fixture timestamps.
    # Production catalog freshness remains enforced and is tested separately.
    from datetime import UTC, datetime

    from trendcoffee.service import Service

    fixture = json.loads(Path("data/trendcoffee-public.json").read_text())
    verified = datetime.now(UTC).isoformat()
    for item in fixture["menu"]["items"]:
        item["verified_at"] = verified
    for doc in fixture["knowledge"]:
        doc["verified_at"] = verified
        doc.pop("expires_at", None)
    Service(tmp_path / "browser.db").ingest(fixture)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "trendcoffee",
            "serve",
            "--port",
            str(port),
            "--db",
            str(tmp_path / "browser.db"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={
            **os.environ,
            "TREND_STAFF_TOKEN": staff_token,
            "OPENAI_API_KEY": "",
            "TREND_OPENAI_MODEL": "",
            "TREND_MERCHANT_ENABLED": "0",
            "TREND_CODEX_VOICE": "0",
        },
    )
    report = {
        "target": "disposable localhost server",
        "console_errors": [],
        "network_errors": [],
        "responsive": [],
        "accessibility": [],
        "visual_regression": "INCONCLUSIVE: no approved screenshot baseline",
        "core_web_vitals": "Not established by a single synthetic session; no field INP claim",
    }
    artifacts = Path(".runtime/qa")
    artifacts.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(100):
            try:
                with urlopen(base + "/health", timeout=0.1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError("Temporary HTTP server did not start")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=executable, headless=True, args=["--no-sandbox"]
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: report["console_errors"].append(str(error)))
            page.on(
                "response",
                lambda response: (
                    report["network_errors"].append(
                        {"url": response.url.split("?")[0], "status": response.status}
                    )
                    if response.status >= 400
                    else None
                ),
            )
            page.on(
                "console",
                lambda message: (
                    report["console_errors"].append(message.text)
                    if message.type == "error"
                    else None
                ),
            )
            page.goto(base)
            page.get_by_role("button", name="Xem Cà phê đen", exact=True).wait_for()
            assert page.locator(".product-card").count() == 51
            axe = artifacts / "axe.min.js"

            def audit(target, name):
                if not axe.exists():
                    return
                target.wait_for_timeout(250)
                target.evaluate(axe.read_text())
                result = target.evaluate(
                    "async () => (await axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))"
                )
                report["accessibility"].append({"page": name, "violations": result})
                assert not result, result

            for width in [375, 768, 1080, 1440]:
                page.set_viewport_size({"width": width, "height": 1000})
                page.wait_for_timeout(100)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(artifacts / f"customer-{width}.png"))
                report["responsive"].append({"width": width, "overflow": False})
            audit(page, "customer-menu")
            page.get_by_role("button", name="Cà phê", exact=True).click()
            assert page.locator(".product-card").count() == 15
            page.get_by_label("Tìm món", exact=True).fill("ca phe den")
            assert page.locator(".product-card").count() == 1
            page.get_by_role("button", name="Xem Cà phê đen", exact=True).click()
            dialog = page.get_by_role("dialog", name="Cà phê đen", exact=True)
            expect(dialog).to_be_visible()
            expect(page.locator(".option-note")).to_have_count(0)
            for width, height in [(1440, 1000), (851, 605), (375, 812), (667, 375)]:
                page.set_viewport_size({"width": width, "height": height})
                page.screenshot(
                    path=str(artifacts / f"product-popup-{width}.png"), animations="disabled"
                )
                box = dialog.bounding_box()
                assert box and box["x"] >= 0 and box["y"] >= 0, box
                assert box["x"] + box["width"] <= width + 1, box
                assert box["y"] + box["height"] <= height + 1, box
                assert dialog.evaluate("e => e.scrollWidth <= e.clientWidth")
            page.set_viewport_size({"width": 1440, "height": 1000})
            dialog.press("Escape")
            expect(dialog).to_have_count(0)
            opener = page.get_by_role("button", name="Xem Cà phê đen", exact=True)
            expect(opener).to_be_focused()
            opener.click()
            dialog.get_by_role("button", name="Tăng số lượng", exact=True).click()
            assert (
                dialog.get_by_role("group").count() == 1
            )  # only published size, no invented ice/sugar
            page.screenshot(path=str(artifacts / "product-panel.png"))
            audit(page, "product-panel")
            page.evaluate("document.documentElement.dataset.theme = 'dark'")
            page.screenshot(path=str(artifacts / "product-popup-dark.png"), animations="disabled")
            audit(page, "product-popup-dark")
            page.evaluate("document.documentElement.dataset.theme = 'light'")
            dialog.get_by_role("button", name="Thêm vào giỏ (70.000đ)", exact=True).click()
            page.get_by_role("button", name="Thanh toán", exact=True).click()
            page.get_by_role("alert").get_by_text(
                "Bạn chọn dùng tại quán hoặc mang đi trước nhé."
            ).wait_for()
            page.get_by_role("button", name="Mang đi", exact=True).click()
            page.get_by_role("button", name="Thanh toán", exact=True).click()
            expect(page.get_by_role("dialog")).to_have_count(0)
            page.get_by_text("Đã lưu yêu cầu của bạn!", exact=True).wait_for()
            page.locator("#checkout-panel .checkout-check").click()
            page.get_by_text("Chờ tiếp nhận", exact=True).wait_for()
            page.get_by_text("Thanh toán: Chưa xác minh", exact=True).wait_for()
            audit(page, "progress")
            page.get_by_role("button", name="Đóng tiến độ", exact=True).click()
            expect(page.get_by_role("button", name="Hỗ trợ", exact=True)).to_have_count(0)
            expect(page.locator("#support-panel-title")).to_have_count(0)
            staff = browser.new_page()
            staff.on("pageerror", lambda error: report["console_errors"].append(str(error)))
            staff.goto(base + "/staff.html")
            staff.get_by_label("Mã truy cập nhân viên").fill(staff_token)
            staff.get_by_role("button", name="Mở hàng đợi", exact=True).click()
            staff.get_by_role("button", name="Tiếp nhận", exact=True).click()
            staff.get_by_text("accepted · Thanh toán: unverified", exact=True).wait_for()
            page.get_by_role("button", name="Tiến độ", exact=True).click()
            page.get_by_role("button", name="Cập nhật tiến độ", exact=True).click()
            page.get_by_text("Đã tiếp nhận", exact=True).wait_for()
            page.get_by_role("button", name="Đóng tiến độ", exact=True).click()
            page.reload()
            page.get_by_role("button", name="Tiến độ", exact=True).click()
            page.get_by_text("Chưa có yêu cầu nào", exact=True).wait_for()
            assert page.evaluate("localStorage.length") == 0
            page.get_by_role("button", name="Đóng tiến độ", exact=True).click()
            # Touch checkout on the smallest viewport.
            page.set_viewport_size({"width": 375, "height": 812})
            page.get_by_role("button", name="Xem Cà phê đen", exact=True).click()
            page.locator(".product-add").get_by_role("button", name="Thêm").click()
            page.get_by_role("button", name="Tại quán", exact=True).click()
            page.get_by_label("Số bàn", exact=True).fill("05")
            page.get_by_role("button", name="Thanh toán", exact=True).click()
            page.get_by_text("Đã lưu yêu cầu của bạn!", exact=True).wait_for()
            expect(page.get_by_role("dialog")).to_have_count(0)
            audit(page, "mobile-review")
            page.screenshot(path=str(artifacts / "mobile-review.png"))
            if axe.exists():
                staff.evaluate(axe.read_text())
                result = staff.evaluate(
                    "async () => (await axe.run()).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.length}))"
                )
                report["accessibility"].append({"page": "staff", "violations": result})
                assert not result
            staff.screenshot(path=str(artifacts / "staff.png"))
            assert not report["console_errors"]
            assert not report["network_errors"]
            report["interactions"] = [
                "menu selection",
                "explicit fulfillment",
                "single-action checkout without popups",
                "pending order",
                "staff acceptance",
            ]
            report["verdict"] = (
                "Local functional checks passed; visual regression INCONCLUSIVE; production not assessed"
            )
            exercise_async_guest_boundaries(browser, base)
            report["async_regressions"] = [
                "boot retry",
                "pending checkout locks cart",
                "network retry preserves checkout ID",
                "removed chat and support UI",
                "mobile reset",
                "idle warning and reset",
            ]
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=5)
        Path("docs/evals/browser-qa.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
