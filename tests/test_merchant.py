"""Merchant HTTP boundary: no requests to the real coffee shop."""

import base64
import copy
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from test_service import line

from trendcoffee.api import create_app
from trendcoffee.service import ServiceError

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nfixture-qr").decode()


def remote_order(**changes):
    return {
        "slug": "merchant123",
        "subtotal": 60000,
        "branch": {"slug": "ba9355f797"},
        "status": "pending",
        "orderItems": [{"variant": {"slug": "coffee"}, "quantity": 2}],
        "payment": {
            "qrCode": PNG,
            "amount": 60000,
            "paymentMethod": "bank-transfer",
            "statusCode": "pending",
        },
        **changes,
    }


def connect(svc, handler):
    from trendcoffee.merchant import MerchantClient

    svc.merchant = MerchantClient(transport=httpx.MockTransport(handler))
    return svc


def place(svc):
    token = svc.new_session()
    quote = svc.quote(token, [line(quantity=2)], "takeaway")
    return token, quote, svc.submit(token, quote["id"], quote["confirmation_token"], True)


def test_confirmed_order_uses_merchant_qr_and_same_quote_never_posts_twice(svc):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/orders/public"):
            import json

            body = json.loads(request.content)
            assert body["orderItems"] == [
                {"quantity": 2, "variant": "coffee", "promotion": None, "note": ""}
            ]
            assert body["type"] == "take-out"
        return httpx.Response(200, json={"result": remote_order()})

    connect(svc, handler)
    token, q, order = place(svc)
    assert order["merchant"]["order_slug"] == "merchant123"
    assert order["payment"]["qr_image"] == PNG
    assert order["payment_status"] == "unverified"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: svc.submit(token, q["id"], q["confirmation_token"], True), range(6))
        )
    assert {r["id"] for r in results} == {order["id"]}
    assert calls.count(("POST", "/api/latest/orders/public")) == 1
    # Existing QR requires no second payment-initiation POST.
    assert not any(method == "POST" and "payment" in path for method, path in calls)


def test_guest_order_without_branch_is_bound_to_echoed_kiosk_reference(svc):
    body = {}

    def handler(request):
        import json

        if request.method == "POST":
            body.update(json.loads(request.content))
        remote = remote_order(description=body["description"], type=body["type"])
        remote.pop("branch")
        return httpx.Response(200, json={"result": remote})

    connect(svc, handler)
    _, _, order = place(svc)
    assert order["merchant"]["state"] == "created"
    assert order["payment"]["qr_image"] == PNG


def test_merchant_receives_item_and_order_notes_and_echo_is_exact(svc):
    body = {}

    def handler(request):
        import json

        if request.method == "POST":
            body.update(json.loads(request.content))
        remote = remote_order(description=body.get("description"), type=body.get("type"))
        remote.pop("branch")
        return httpx.Response(200, json={"result": remote})

    connect(svc, handler)
    token = svc.new_session()
    order = svc.checkout(
        token,
        [line(quantity=2, note="less ice")],
        "takeaway",
        checkout_id="note-order",
        order_note="call on arrival",
    )
    assert body["orderItems"][0]["note"] == "less ice"
    assert body["description"] == (
        "THẺ SỐ 1 - Mang đi. Khi thẻ rung, mời bạn đến quầy nhận món. Cảm ơn bạn! "
        f"Ghi chú của khách: call on arrival. (AI ORDER - Kiosk {order['id']})"
    )
    assert order["merchant"]["state"] == "created"


def test_an_order_created_with_the_previous_description_still_validates(svc):
    """Orders placed before the AI ORDER notice keep their payment and invoice checks."""
    from trendcoffee.merchant import MerchantClient

    body = {}

    def handler(request):
        import json

        if request.method == "POST":
            body.update(json.loads(request.content))
        remote = remote_order(description=body["description"], type=body["type"])
        remote.pop("branch")
        return httpx.Response(200, json={"result": remote})

    connect(svc, handler)
    _, _, order = place(svc)
    legacy = remote_order(description=f"Kiosk {order['id']}", type="take-out")
    legacy.pop("branch")
    MerchantClient.validate(svc.merchant, legacy, order)  # does not raise
    legacy["description"] = f"Kiosk {order['id']} altered"
    with pytest.raises(Exception, match="merchant_order_mismatch"):
        MerchantClient.validate(svc.merchant, legacy, order)


def test_missing_branch_echo_does_not_accept_a_prefix_of_order_note(svc):
    body = {}

    def handler(request):
        import json

        if request.method == "POST":
            body.update(json.loads(request.content))
        remote = remote_order(
            description=body.get("description") + " altered", type=body.get("type")
        )
        remote.pop("branch")
        return httpx.Response(200, json={"result": remote})

    connect(svc, handler)
    token = svc.new_session()
    order = svc.checkout(
        token,
        [line(quantity=2, note="less ice")],
        "takeaway",
        checkout_id="echo-mismatch",
        order_note="call",
    )
    assert order["merchant"]["error"] == "merchant_order_mismatch"


@pytest.mark.parametrize(
    "changes",
    [
        {"description": "another kiosk order"},
        {"type": "at-table"},
        {"branch": {"slug": "wrong-branch"}},
    ],
)
def test_missing_branch_fallback_rejects_wrong_order_echo_or_explicit_branch(svc, changes):
    body = {}

    def handler(request):
        import json

        if request.method == "POST":
            body.update(json.loads(request.content))
        remote = remote_order(description=body["description"], type=body["type"])
        remote.pop("branch")
        remote.update(changes)
        return httpx.Response(200, json={"result": remote})

    connect(svc, handler)
    _, _, order = place(svc)
    assert order["merchant"]["error"] == "merchant_order_mismatch"
    assert not order.get("payment", {}).get("qr_image")


def test_missing_qr_is_initiated_for_exact_merchant_reference_then_displayed(svc):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        data = (
            remote_order(payment=None)
            if request.url.path.endswith("/orders/public")
            else remote_order()
        )
        if request.url.path.endswith("/payment/initiate/public"):
            import json

            assert json.loads(request.content) == {
                "orderSlug": "merchant123",
                "paymentMethod": "bank-transfer",
            }
            data = data["payment"]
        return httpx.Response(200, json={"result": data})

    connect(svc, handler)
    _, _, order = place(svc)
    assert order["payment"]["qr_image"] == PNG
    assert calls.count("/api/latest/payment/initiate/public") == 1


def test_slug_only_create_response_is_followed_before_payment_initiation(svc):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        data = (
            {"slug": "merchant123"}
            if request.url.path.endswith("/orders/public")
            else remote_order()
        )
        return httpx.Response(200, json={"result": data})

    connect(svc, handler)
    _, _, order = place(svc)
    assert order["payment"]["qr_image"] == PNG
    assert calls == [
        ("POST", "/api/latest/orders/public"),
        ("GET", "/api/latest/orders/merchant123"),
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"createdAt": 123},
        {"status": {}},
        {"orderItems": [None]},
        {
            "payment": {
                "qrCode": "https://trendcoffee.net:bad/qr",
                "amount": 60000,
                "paymentMethod": "bank-transfer",
            }
        },
    ],
)
def test_malformed_merchant_response_stays_a_recoverable_domain_state(svc, changes):
    connect(svc, lambda _: httpx.Response(200, json={"result": remote_order(**changes)}))
    token, _, order = place(svc)
    assert order["merchant"]["order_slug"] == "merchant123"
    assert order["merchant"]["state"] == "review_required"
    assert not order.get("payment", {}).get("qr_image")
    assert svc.payment(token, order["id"])["status"] in {"unavailable", "review_required"}


def test_table_label_uses_the_real_merchant_table_slug(svc):
    bodies = []

    def handler(request):
        if request.method == "GET" and request.url.path.endswith("/tables"):
            return httpx.Response(200, json={"result": [{"name": "3", "slug": "table-three"}]})
        import json

        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"result": remote_order()})

    connect(svc, handler)
    token = svc.new_session()
    q = svc.quote(token, [line(quantity=2)], "at_table", "Bàn 3")
    order = svc.submit(token, q["id"], q["confirmation_token"], True)
    assert bodies[0]["table"] == "table-three"
    assert bodies[0]["type"] == "at-table"
    assert order["payment"]["qr_image"] == PNG


def test_create_timeout_is_durable_uncertainty_not_a_second_order(svc):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("response lost", request=request)

    connect(svc, handler)
    token, q, order = place(svc)
    assert order["merchant"]["state"] == "uncertain"
    assert not order.get("payment", {}).get("qr_image")
    svc.submit(token, q["id"], q["confirmation_token"], True)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"subtotal": 99999},
        {"branch": {"slug": "other"}},
        {"orderItems": [{"variant": {"slug": "different"}, "quantity": 2}]},
        {"payment": {"qrCode": PNG, "amount": 99999, "paymentMethod": "bank-transfer"}},
    ],
)
def test_wrong_amount_branch_or_items_never_exposes_payment_qr(svc, changes):
    connect(svc, lambda _: httpx.Response(200, json={"result": remote_order(**changes)}))
    _, _, order = place(svc)
    assert not order.get("payment", {}).get("qr_image")
    assert order["merchant"]["state"] == "review_required"


def test_payment_refresh_is_scoped_and_only_merchant_can_report_paid(svc):
    current = remote_order()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"result": copy.deepcopy(current)})

    connect(svc, handler)
    token, _, order = place(svc)
    with TestClient(create_app(service=svc)) as client:
        other = client.post("/api/sessions").json()["session_token"]
        response = client.get(
            f"/api/orders/{order['id']}/payment", headers={"Authorization": "Bearer " + other}
        )
        assert response.status_code == 404
        assert len(calls) == 1
        current["status"] = "paid"
        current["payment"]["statusCode"] = "completed"
        response = client.get(
            f"/api/orders/{order['id']}/payment", headers={"Authorization": "Bearer " + token}
        )
        assert response.status_code == 200
        payment = response.json()
        assert payment["status"] == "paid"
        assert not payment.get("qr_image")
        assert svc.progress(token)["orders"][0]["payment_status"] == "paid"


def test_payment_expiry_hides_qr_and_does_not_create_replacement(svc):
    connect(
        svc,
        lambda _: httpx.Response(
            200, json={"result": remote_order(createdAt="2020-01-01T00:00:00Z")}
        ),
    )
    _, _, order = place(svc)
    assert not order.get("payment", {}).get("qr_image")
    assert order["payment"]["status"] == "expired"


def test_late_pending_refresh_cannot_overwrite_verified_paid(svc):
    import threading

    held, release = threading.Event(), threading.Event()
    refreshing = False

    def handler(request):
        if (
            refreshing
            and request.method == "GET"
            and threading.current_thread().name == "late-pending"
        ):
            held.set()
            assert release.wait(3)
            data = remote_order()
        else:
            data = remote_order(status="paid") if refreshing else remote_order()
        return httpx.Response(200, json={"result": data})

    connect(svc, handler)
    token, _, order = place(svc)
    refreshing = True
    late = []
    thread = threading.Thread(
        target=lambda: late.append(svc.payment(token, order["id"])), name="late-pending"
    )
    thread.start()
    try:
        assert held.wait(3)
        assert svc.payment(token, order["id"])["status"] == "paid"
    finally:
        release.set()
        thread.join(3)
    assert svc.progress(token)["orders"][0]["payment_status"] == "paid"
    assert late[0]["status"] == "paid"


def test_read_payment_without_merchant_never_fabricates_a_qr(svc):
    token, _, order = place(svc)
    with pytest.raises(ServiceError, match="order_not_found"):
        svc.payment(svc.new_session(), order["id"])
    assert svc.payment(token, order["id"])["status"] == "not_connected"
