"""A hidden 10% voucher on every order (user decision 2026-11-06).

The shop's private voucher "Testmon" is attached to each merchant order while it is usable;
guests are never told. The merchant applies it only when given the voucher's slug (a real
probe on 2026-11-06: code "Testmon" was ignored, slug "2b155921ee" gave 31500 of 35000).
Fixtures only: the merchant is a mock transport.
"""

import copy
import json
import time
from datetime import UTC, datetime

import httpx
from test_merchant import PNG, connect
from test_service import line

SLUG = "2b155921ee"


def iso(offset):
    return datetime.fromtimestamp(time.time() + offset, UTC).isoformat().replace("+00:00", "Z")


def voucher(**changes):
    return {
        "code": "Testmon",
        "slug": SLUG,
        "type": "percent_order",
        "value": 10,
        "isActive": True,
        "remainingUsage": 18,
        "minOrderValue": 0,
        "startDate": iso(-3600),
        "endDate": iso(86400),
        "voucherPaymentMethods": [{"paymentMethod": "bank-transfer"}],
        "voucherProducts": [{"product": {"variants": [{"slug": "coffee"}]}}],
        **changes,
    }


def merchant(svc, offer=None, discount=6000, applied=True, paid=False):
    """A merchant that serves the voucher lookup and applies `discount` to a 60000 order."""
    state = {"posted": [], "lookups": 0}
    offer = voucher() if offer is None else offer

    def handler(request):
        if request.url.path.endswith("/voucher/specific/public"):
            state["lookups"] += 1
            assert request.url.params["code"] == "Testmon"
            if offer == "error":
                return httpx.Response(500, json={"message": "down"})
            return httpx.Response(200, json={"result": offer})
        if request.method == "POST" and request.url.path.endswith("/orders/public"):
            state["posted"].append(json.loads(request.content))
        body = state["posted"][-1]
        used = applied and body.get("voucher") == SLUG
        subtotal = 60000 - discount if used else 60000
        remote = {
            "slug": "merchant123",
            "subtotal": subtotal,
            "originalSubtotal": 60000,
            "status": "paid" if paid else "pending",
            "description": body["description"],
            "type": body["type"],
            "orderItems": [{"variant": {"slug": "coffee"}, "quantity": 2}],
            "voucher": {"slug": SLUG, "code": "Testmon"} if used else None,
            "payment": {
                "qrCode": PNG,
                "amount": subtotal,
                "paymentMethod": "bank-transfer",
                "statusCode": "completed" if paid else "pending",
            },
        }
        return httpx.Response(200, json={"result": copy.deepcopy(remote)})

    connect(svc, handler)
    svc.merchant.voucher_code = "Testmon"
    return state


def place(svc, checkout_id="1"):
    token = svc.new_session()
    order = svc.checkout(token, [line(quantity=2)], "takeaway", checkout_id=checkout_id)
    return token, order


def test_a_usable_voucher_is_attached_and_the_qr_asks_for_the_discounted_amount(svc):
    state = merchant(svc)
    token, order = place(svc)
    assert state["posted"][0]["voucher"] == SLUG
    payment = svc.payment(token, order["id"])
    assert payment["status"] == "pending" and payment["qr_image"]
    assert payment["amount_vnd"] == 54000
    assert order["total_vnd"] == 60000, "the listed total is unchanged"


def test_a_paid_discounted_order_is_paid(svc):
    merchant(svc, paid=True)
    token, order = place(svc)
    assert svc.payment(token, order["id"])["status"] == "paid"


def test_no_voucher_when_it_cannot_be_used(svc):
    for offer in (
        voucher(remainingUsage=0),
        voucher(isActive=False),
        voucher(endDate=iso(-60)),
        voucher(startDate=iso(3600)),
        voucher(value=20),
        voucher(type="fixed_order"),
        voucher(minOrderValue=100000),
        voucher(voucherPaymentMethods=[{"paymentMethod": "cash"}]),
        voucher(voucherProducts=[{"product": {"variants": [{"slug": "other"}]}}]),
        "error",
    ):
        state = merchant(svc, offer=offer)
        token, order = place(svc, checkout_id=f"c-{len(json.dumps(offer))}-{time.time()}")
        assert state["posted"][-1]["voucher"] is None, offer
        payment = svc.payment(token, order["id"])
        assert payment["amount_vnd"] == 60000 and payment["status"] == "pending", offer


def test_a_merchant_that_ignores_the_voucher_charges_the_listed_price(svc):
    merchant(svc, applied=False)
    token, order = place(svc)
    payment = svc.payment(token, order["id"])
    assert payment["status"] == "pending" and payment["amount_vnd"] == 60000


def test_a_discount_beyond_ten_percent_is_never_accepted(svc):
    merchant(svc, discount=6001)
    token, order = place(svc)
    assert svc.payment(token, order["id"])["status"] == "review_required"


def test_the_voucher_is_looked_up_at_most_once_a_minute(svc):
    state = merchant(svc)
    place(svc, "a")
    place(svc, "b")
    assert state["lookups"] == 1


def test_trend_never_sees_the_voucher_in_a_tool_result(svc):
    from trendcoffee.kiosk import public_order

    merchant(svc)
    _, order = place(svc)
    assert "voucher" not in json.dumps(public_order(order)).lower()
    assert "discount" not in json.dumps(public_order(order)).lower()


def test_the_kiosk_merchant_uses_the_hidden_voucher(monkeypatch):
    from trendcoffee.merchant import from_environment

    monkeypatch.setenv("TREND_MERCHANT_ENABLED", "1")
    assert from_environment().voucher_code == "Testmon"
