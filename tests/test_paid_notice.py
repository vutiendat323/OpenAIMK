"""A verified payment reaches the guest and Trend's context, whoever found it first.

The screen's QR poll, the invoice worker and a voice tool can each be the first to see
the merchant report an order as paid. Fixtures only: no merchant, payment or printer.
"""

import asyncio

from test_claim_guard import Delegating, delegating_host

from trendcoffee.claim_guard import paid_summary, paid_turn

PAID = {"status": "paid", "source": "merchant"}


def place(svc, token, checkout_id="1"):
    return svc.checkout(
        token,
        [{"item_id": "coffee", "quantity": 2, "options": {"ice": "ít"}, "note": "ít đường"}],
        "takeaway",
        checkout_id=checkout_id,
    )


async def merchant_pays(svc, order):
    """What a QR poll or the invoice worker records, from a worker thread."""
    await asyncio.to_thread(
        svc._save_order, order, payment={**PAID, "order_id": order["id"]}, payment_status="paid"
    )
    await asyncio.sleep(0.05)


def test_the_service_tells_listeners_once_when_an_order_becomes_paid(svc):
    heard = []
    svc.paid_listeners.append(lambda session, order: heard.append((session, order["id"])))
    token = svc.new_session()
    order = place(svc, token)
    svc._save_order(order, payment={"status": "pending"}, payment_status="unverified")
    assert heard == [], "a pending payment is not paid"
    svc._save_order(order, payment=PAID, payment_status="paid")
    svc._save_order(order, payment=PAID, payment_status="paid")
    assert heard == [(svc.session_id(token), order["id"])], "once, for this guest's session"


def test_a_failing_listener_never_fails_the_save(svc):
    def broken(session, order):
        raise RuntimeError("listener bug")

    svc.paid_listeners.append(broken)
    order = place(svc, svc.new_session())
    saved = svc._save_order(order, payment=PAID, payment_status="paid")
    assert saved["payment_status"] == "paid"


def test_the_summary_carries_the_order_context():
    order = {
        "lines": [
            {"name": "Cà phê sữa", "quantity": 2, "options": {"ice": "ít"}, "note": "ít đường"}
        ],
        "total_vnd": 60000,
        "fulfillment": "at_table",
        "table_label": "Bàn 5",
        "payment": {"merchant_order_id": "TC-42"},
    }
    summary = paid_summary(order)
    for part in ("2 × Cà phê sữa (ít)", "ít đường", "60000 VND", "tại bàn Bàn 5", "TC-42"):
        assert part in summary
    text = paid_turn(order)
    assert "kiosk_payment" in text and "own words" in text
    assert "Đơn đã được thanh toán" not in text, "no fixed paid sentence"
    assert "Do not create another order" in text


def test_a_payment_found_by_the_screen_is_told_to_trend_with_the_order(svc):
    async def run():
        host, _, events, _, _ = await delegating_host(svc)
        order = place(svc, host.token)
        events.clear()
        await merchant_pays(svc, order)
        ((thread, text),) = host.codex.turns
        assert thread == host.thread_id
        assert "Cà phê sữa" in text and "60000 VND" in text and "mang đi" in text
        assert "If it reports paid" in text and "own words" in text
        assert any(e["type"] == "view" and e.get("view") == "payment" for e in events)
        assert host.audio_metrics["paid_notices"] == 1
        await merchant_pays(svc, order)
        assert len(host.codex.turns) == 1, "one notice per paid order"
        await host.close()

    asyncio.run(run())


def test_a_paid_result_a_voice_tool_already_reported_is_not_announced_again(svc):
    async def run():
        host, _, _, on_tool, _ = await delegating_host(svc)
        order = place(svc, host.token)
        original = host._tool

        async def tool(name, args):
            if name == "kiosk_payment":
                # The merchant reports paid during the guest's own payment check.
                await merchant_pays(svc, order)
                return {"order_id": order["id"], "payment": {"status": "paid"}}
            return await original(name, args)

        host._tool = tool
        await on_tool({"tool": "kiosk_payment", "arguments": {}, "callId": "p1"})
        await asyncio.sleep(0.05)
        assert host.codex.turns == []
        assert "paid_notices" not in host.audio_metrics
        await host.close()

    asyncio.run(run())


def test_a_concurrent_unrelated_tool_does_not_hide_the_notice(svc):
    async def run():
        host, _, _, on_tool, _ = await delegating_host(svc)
        order = place(svc, host.token)
        original = host._tool

        async def tool(name, args):
            if name == "kiosk_menu":
                await merchant_pays(svc, order)  # the QR poll sees it meanwhile
            return await original(name, args)

        host._tool = tool
        await on_tool({"tool": "kiosk_menu", "arguments": {"queries": ["cà phê"]}, "callId": "m"})
        await asyncio.sleep(0.05)
        assert len(host.codex.turns) == 1
        await host.close()

    asyncio.run(run())


def test_another_guests_payment_is_not_announced(svc):
    async def run():
        host, _, _, _, _ = await delegating_host(svc)
        await merchant_pays(svc, place(svc, svc.new_session()))
        assert host.codex.turns == []
        await host.close()

    asyncio.run(run())


def test_a_refused_turn_still_gives_the_voice_the_order_context(svc):
    async def run():
        host, _, _, _, _ = await delegating_host(svc, refuse=True)
        order = place(svc, host.token)
        await merchant_pays(svc, order)
        ((thread, role, note),) = host.codex.notes
        assert (thread, role) == (host.thread_id, "developer")
        assert "Cà phê sữa" in note and "Do not create another order" in note
        assert "Đơn đã được thanh toán" not in note, "the voice never states paid by itself"
        await host.close()

    asyncio.run(run())


def test_no_notice_after_the_guest_session_ended(svc):
    async def run():
        host, _, _, _, _ = await delegating_host(svc)
        order = place(svc, host.token)
        await host.end("idle")
        await merchant_pays(svc, order)
        assert host.codex.turns == []
        await host.close()

    asyncio.run(run())


def test_a_closed_host_stops_listening(svc):
    async def run():
        host, _, _, _, _ = await delegating_host(svc)
        assert isinstance(host.codex, Delegating)
        await host.close()
        assert host._order_paid not in svc.paid_listeners

    asyncio.run(run())
