"""An order-required payment read must retain the real pending cart for reasoning."""

import asyncio

import pytest
from test_kiosk_runtime import FakeCodex

from trendcoffee.kiosk import InteractionHost


@pytest.mark.parametrize("connected", [False, True])
def test_payment_without_order_returns_pending_cart_without_placing_it(svc, connected):
    async def run():
        svc.merchant = object() if connected else None  # No order/payment HTTP call is needed.
        host = InteractionHost(svc, codex=FakeCodex())
        host.token = svc.new_session()
        host.active, host.generation = True, 1
        await host._tool("kiosk_cart", {"action": "add", "item_id": "coffee", "quantity": 1})
        await host._tool("kiosk_fulfillment", {"fulfillment": "takeaway"})
        before = host.snapshot()
        result = await host._tool("kiosk_payment", {})
        assert result["payment"]["status"] == "order_required"
        assert result["payment_connected"] is connected
        assert result["pending_cart"] == before
        assert result["pending_cart"]["cart"][0]["item"]["id"] == "coffee"
        assert result["pending_cart"]["fulfillment"] == "takeaway"
        assert host.snapshot() == before
        assert svc.progress(host.token)["orders"] == []
        assert not result["qr_available"]

    asyncio.run(run())
