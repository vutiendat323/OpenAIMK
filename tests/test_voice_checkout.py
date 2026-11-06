"""The initial order request goes straight to a merchant QR, without re-confirmation."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from test_kiosk_runtime import FakeCodex
from test_menu_batch import catalog as catalog
from test_merchant import PNG

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost
from trendcoffee.merchant import MerchantClient


@pytest.mark.parametrize("channel", ["voice", "touch", "http"])
def test_initial_checkout_submits_once_and_shows_qr(catalog, channel):
    posted = []
    remote = {
        "slug": "lychee-peach-test",
        "subtotal": 58000,
        "status": "pending",
        "orderItems": [{"variant": {"slug": "03d9fe8299"}, "quantity": 1}],
        "payment": {
            "qrCode": PNG,
            "amount": 58000,
            "paymentMethod": "bank-transfer",
            "statusCode": "pending",
        },
    }

    def merchant(request):
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["type"] == "take-out"
            assert payload["orderItems"][0]["variant"] == "03d9fe8299"
            posted.append(payload)
            remote.update(description=payload["description"], type=payload["type"])
        return httpx.Response(200, json={"result": remote})

    catalog.merchant = MerchantClient(transport=httpx.MockTransport(merchant))
    if channel == "http":
        with TestClient(create_app(service=catalog)) as client:
            token = catalog.new_session()
            headers = {"Authorization": "Bearer " + token}
            payload = {
                "checkout_id": "first-intent",
                "lines": [{"item_id": "03d9fe8299", "quantity": 1, "options": {}}],
                "fulfillment": "takeaway",
            }
            response = client.post("/api/checkout", headers=headers, json=payload)
            assert response.status_code == 200
            order = response.json()
            assert order["payment"]["qr_image"] == PNG
            again = client.post("/api/checkout", headers=headers, json=payload)
            assert again.json()["id"] == order["id"]
            assert len(posted) == 1
        return

    async def run():
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(catalog, codex=FakeCodex())
        await host.attach(catalog.new_session(), send)
        await host.begin(manual=True)
        tool, _ = host.codex.callbacks[host.thread_id]
        try:
            await tool(
                {
                    "tool": "kiosk_cart",
                    "arguments": {"action": "add", "item_id": "03d9fe8299", "quantity": 1},
                }
            )
            await tool({"tool": "kiosk_fulfillment", "arguments": {"fulfillment": "takeaway"}})

            async def checkout():
                if channel == "voice":
                    return await tool({"tool": "kiosk_checkout", "arguments": {}})
                return await host.command({"type": "checkout", "generation": host.generation})

            order = await checkout()
            assert order["merchant"]["state"] == "created"
            assert order["total_vnd"] == 58000
            assert order["qr_available"]
            assert (await checkout())["id"] == order["id"]
            assert len(posted) == 1
            assert not any(event["type"] == "quote" for event in events)
            displayed = next(event["order"] for event in events if event["type"] == "order")
            assert displayed["payment"]["qr_image"] == PNG
        finally:
            await host.close()

    asyncio.run(run())


def test_one_checkout_call_adds_the_requested_drinks_and_places_them(catalog):
    """One tool call instead of kiosk_cart + kiosk_checkout: one model round trip less.

    Measured 2026-11-04: each extra sequential call costs the voice turn about 1.8 s.
    """
    posted = []

    def merchant(request):
        payload = json.loads(request.content) if request.method == "POST" else None
        if payload:
            posted.append(payload)
        lines = (payload or posted[-1])["orderItems"]
        total = sum(58000 * line["quantity"] for line in lines)
        return httpx.Response(
            200,
            json={
                "result": {
                    "slug": "one-call",
                    "subtotal": total,
                    "status": "pending",
                    "description": (payload or posted[-1])["description"],
                    "type": (payload or posted[-1])["type"],
                    "orderItems": [
                        {"variant": {"slug": line["variant"]}, "quantity": line["quantity"]}
                        for line in lines
                    ],
                    "payment": {
                        "qrCode": PNG,
                        "amount": total,
                        "paymentMethod": "bank-transfer",
                        "statusCode": "pending",
                    },
                }
            },
        )

    catalog.merchant = MerchantClient(transport=httpx.MockTransport(merchant))

    async def run():
        async def send(event):
            pass

        host = InteractionHost(catalog, codex=FakeCodex())
        await host.attach(catalog.new_session(), send)
        await host.begin(manual=True)
        tool, _ = host.codex.callbacks[host.thread_id]
        try:
            order = await tool(
                {
                    "tool": "kiosk_checkout",
                    "arguments": {
                        "lines": [{"item_id": "03d9fe8299", "quantity": 2}],
                        "fulfillment": "takeaway",
                    },
                    "callId": "one",
                }
            )
            assert order["qr_available"] and order["fulfillment"] == "takeaway"
            assert [(line["item_id"], line["quantity"]) for line in order["lines"]] == [
                ("03d9fe8299", 2)
            ], "the returned order lets Codex verify the requested drinks"
            assert host.cart == [] and len(posted) == 1
        finally:
            await host.close()

    asyncio.run(run())


def test_checkout_lines_follow_the_cart_tool_rules(catalog):
    from jsonschema import Draft202012Validator

    from trendcoffee.kiosk import TOOLS

    schema = next(t for t in TOOLS if t["name"] == "kiosk_checkout")["inputSchema"]
    valid = Draft202012Validator(schema).is_valid
    assert valid(
        {"lines": [{"item_id": "x", "quantity": 1, "note": "ít đá"}], "fulfillment": "takeaway"}
    )
    assert not valid({"lines": []}), "empty lines are not an order"
    assert not valid({"lines": [{"item_id": "x", "quantity": 0}]})
    assert not valid({"lines": [{"item_id": "x", "quantity": 1, "price": 1}]})


def test_the_prompt_asks_for_one_checkout_call_with_lines():
    from trendcoffee.codex_voice import INSTRUCTIONS

    flat = " ".join(INSTRUCTIONS.split())
    assert "call kiosk_checkout ONCE with lines=" in flat
    assert "Never checkout an older cart instead of adding the customer's newly named" in flat


def test_qr_sentence_names_the_card():
    """User decision 2026-11-06: exact sentence, with the order's real pickup card."""
    from trendcoffee.session_notices import qr_sentence

    assert qr_sentence(7) == (
        "Bạn quét QR trên màn hình để thanh toán nhé, thẻ rung của bạn là số 7."
    )
    assert qr_sentence(None) == "Bạn quét QR trên màn hình để thanh toán nhé."


def test_checkout_and_payment_results_carry_the_exact_qr_reply(catalog):
    from trendcoffee.claim_guard import UNVERIFIED_PAID_NOTE
    from trendcoffee.session_notices import qr_sentence

    remote = {
        "slug": "card-test",
        "subtotal": 58000,
        "status": "pending",
        "orderItems": [{"variant": {"slug": "03d9fe8299"}, "quantity": 1}],
        "payment": {
            "qrCode": PNG,
            "amount": 58000,
            "paymentMethod": "bank-transfer",
            "statusCode": "pending",
        },
    }

    def merchant(request):
        if request.method == "POST":
            payload = json.loads(request.content)
            remote.update(description=payload["description"], type=payload["type"])
        return httpx.Response(200, json={"result": remote})

    catalog.merchant = MerchantClient(transport=httpx.MockTransport(merchant))

    async def run():
        async def send(event):
            pass

        host = InteractionHost(catalog, codex=FakeCodex())
        await host.attach(catalog.new_session(), send)
        await host.begin(manual=True)
        tool, _ = host.codex.callbacks[host.thread_id]
        try:
            await tool(
                {
                    "tool": "kiosk_cart",
                    "arguments": {"action": "add", "item_id": "03d9fe8299", "quantity": 1},
                }
            )
            order = await tool({"tool": "kiosk_checkout", "arguments": {"fulfillment": "takeaway"}})
            assert order["qr_available"] and order["vibrating_card"] == 1
            assert order["qr_reply"] == qr_sentence(1)
            again = await tool({"tool": "kiosk_checkout", "arguments": {}})
            assert again["qr_reply"] == qr_sentence(1)
            payment = await tool({"tool": "kiosk_payment", "arguments": {}})
            assert payment["qr_available"] and payment["qr_reply"] == qr_sentence(1)
        finally:
            await host.close()

    asyncio.run(run())
    assert "qr_reply" in UNVERIFIED_PAID_NOTE
