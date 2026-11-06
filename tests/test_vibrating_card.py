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
