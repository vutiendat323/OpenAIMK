"""Every new order gets a pickup card 1-16, rotating (user decisions 2026-11-06).

Staff make the card vibrate by hand; the kiosk only records which card goes with which
order. Fixtures only: no merchant, payment or printer.
"""

import json

from trendcoffee.service import Service

LINE = {"item_id": "coffee", "quantity": 1, "options": {"ice": "ít"}, "note": ""}


def order(svc, checkout_id="1", fulfillment="takeaway", table=None, token=None):
    token = token or svc.new_session()
    return svc.checkout(token, [LINE], fulfillment, table, checkout_id=checkout_id)


def test_cards_rotate_one_to_sixteen_across_takeaway_and_dine_in(svc):
    cards = [
        order(svc, fulfillment="at_table" if i % 2 else "takeaway", table="05")["vibrating_card"]
        for i in range(17)
    ]
    assert cards == [*range(1, 17), 1]


def test_a_retried_checkout_keeps_its_card(svc):
    token = svc.new_session()
    first = order(svc, token=token)
    again = order(svc, token=token)
    assert again["id"] == first["id"]
    assert again["vibrating_card"] == first["vibrating_card"] == 1


def test_the_rotation_survives_a_restart(svc):
    for _ in range(3):
        order(svc)
    restarted = Service(svc.store.path)
    assert order(restarted)["vibrating_card"] == 4


def test_two_services_on_one_database_hand_out_distinct_cards(svc):
    other = Service(svc.store.path)  # the API and the MCP server share one database
    cards = [order(svc if i % 2 else other)["vibrating_card"] for i in range(4)]
    assert cards == [1, 2, 3, 4]


def test_orders_before_cards_do_not_break_the_rotation(svc):
    first = order(svc)
    with svc.store.connect(write=True) as db:
        db.execute(
            "INSERT INTO orders VALUES (?,?,?,?)",
            ("legacy", None, None, json.dumps({"id": "legacy", "status": "pending_acceptance"})),
        )
    assert first["vibrating_card"] == 1
    assert order(svc)["vibrating_card"] == 2


def test_payment_reports_the_card(svc):
    token = svc.new_session()
    placed = order(svc, token=token)
    assert svc.payment(token, placed["id"])["vibrating_card"] == placed["vibrating_card"]


NOTICE = "Khi thẻ rung, mời quý khách đến quầy nhận món. Cảm ơn quý khách!"


def test_dine_in_description_names_card_and_table():
    from trendcoffee.merchant import order_description

    carded = {
        "id": "abc",
        "vibrating_card": 7,
        "fulfillment": "at_table",
        "table_label": "05",
        "order_note": "ít đá",
    }
    assert order_description(carded) == (
        f"AI ORDER\nTHẺ RUNG SỐ 7 · Bàn 05\n{NOTICE}\nKiosk abc\nít đá"
    )


def test_takeaway_description_says_mang_di():
    from trendcoffee.merchant import order_description

    carded = {"id": "abc", "vibrating_card": 12, "fulfillment": "takeaway", "table_label": None}
    assert order_description(carded) == f"AI ORDER\nTHẺ RUNG SỐ 12 · Mang đi\n{NOTICE}\nKiosk abc"


def test_dine_in_without_table_label_names_only_the_card():
    from trendcoffee.merchant import order_description

    carded = {"id": "abc", "vibrating_card": 3, "fulfillment": "at_table", "table_label": None}
    assert order_description(carded) == f"AI ORDER\nTHẺ RUNG SỐ 3\n{NOTICE}\nKiosk abc"


def test_orders_without_a_card_keep_todays_description():
    from trendcoffee.merchant import order_description

    old = {"id": "abc", "fulfillment": "at_table", "table_label": "05"}
    assert order_description(old) == (
        "AI ORDER\nQuý khách vui lòng đợi khoảng 15 phút và nhận món tại quầy thanh toán. "
        "Cảm ơn quý khách!\nKiosk abc"
    )
    assert order_description(old, legacy=True) == "Kiosk abc"


def test_validate_accepts_a_carded_guest_order_echo(svc):
    from test_merchant import connect, remote_order
    from test_service import line

    from trendcoffee.merchant import MerchantClient, order_description

    body = {}

    def handler(request):
        if request.method == "POST":
            body.update(json.loads(request.content))
        remote = remote_order(description=body.get("description"), type=body.get("type"))
        remote.pop("branch")
        return __import__("httpx").Response(200, json={"result": remote})

    connect(svc, handler)
    placed = svc.checkout(svc.new_session(), [line(quantity=2)], "takeaway", checkout_id="c1")
    assert body["description"] == order_description(placed)
    assert "THẺ RUNG SỐ 1 · Mang đi" in body["description"]
    echo = remote_order(description=body["description"], type="take-out")
    echo.pop("branch")
    MerchantClient.validate(svc.merchant, echo, placed)  # does not raise


# User decision 2026-11-06 (later the same day): the number advances only past a PAID order.
# An unpaid order gives its number back once its QR has expired; a live QR keeps it.
NOW = 1_800_000_000.0


def merchant_order(card, paid=False, expires_in=-60, created_ago=1000, qr=True):
    order = {
        "id": f"o{card}-{paid}-{expires_in}",
        "vibrating_card": card,
        "payment_status": "paid" if paid else "unverified",
        "merchant": {"state": "created"},
        "created_at": __import__("datetime")
        .datetime.fromtimestamp(NOW - created_ago, __import__("datetime").UTC)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    if qr:
        order["payment"] = {"status": "paid" if paid else "pending", "expires_at": NOW + expires_in}
    return order


def next_card_after(svc, *orders):
    from trendcoffee.service import _next_card

    with svc.store.connect(write=True) as db:
        for order in orders:
            db.execute(
                "INSERT INTO orders VALUES (?,?,?,?)", (order["id"], None, None, json.dumps(order))
            )
        return _next_card(db)


def test_the_afternoon_of_2026_11_06_gives_unpaid_numbers_back(svc):
    """Paid 3, 4 and 11; every other order's QR expired unpaid -> the next order gets 12."""
    paid = {3, 4, 11}
    orders = [merchant_order(card, paid=card in paid) for card in range(1, 13)]
    assert next_card_after(svc, *orders) == 12


def test_a_paid_order_moves_the_number_on(svc):
    assert next_card_after(svc, merchant_order(7, paid=True)) == 8


def test_a_skipped_order_gives_its_number_to_the_next_guest(svc):
    assert next_card_after(svc, merchant_order(6, paid=True), merchant_order(7)) == 7


def test_a_live_unpaid_qr_does_not_move_the_number_on(svc):
    """User 2026-11-06 20:45: while a QR is still valid and unpaid, keep the current number."""
    live = merchant_order(7, expires_in=300)
    assert next_card_after(svc, merchant_order(6, paid=True), live) == 7


def test_an_order_still_waiting_for_its_qr_does_not_move_the_number_on(svc):
    creating = merchant_order(7, created_ago=20, qr=False)
    assert next_card_after(svc, merchant_order(6, paid=True), creating) == 7


def test_the_evening_of_2026_11_06_keeps_card_fourteen(svc):
    """Paid 13; then 14 and 15 were given while 14's QR was still live -> the next is 14."""
    orders = [
        merchant_order(13, paid=True),
        merchant_order(14, expires_in=500),
        merchant_order(15, expires_in=700),
    ]
    assert next_card_after(svc, *orders) == 14


def test_after_card_sixteen_comes_one(svc):
    assert next_card_after(svc, merchant_order(16, paid=True)) == 1
