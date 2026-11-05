"""Trend speaks up on its own: it asks a quiet guest, and warns before the time limit.

User decisions 2026-11-05: no on-screen countdown; a quiet guest is asked a question that
fits where they are (nothing chosen, cart, order awaiting payment, paid) and the session
does not end for being quiet. Fixtures only: the Codex turn is recorded, not run.
"""

import asyncio

from test_claim_guard import delegating_host

from trendcoffee.session_notices import (
    QR_SENTENCE,
    guest_situation,
    idle_nudge_turn,
    time_warning_turn,
)

LATTE = {"item": {"id": "latte", "name": "Latte"}, "quantity": 2, "options": {}}


async def session(svc, refuse=False):
    host, _, events, _, _ = await delegating_host(svc, refuse=refuse)
    now = host.clock()
    host.session_timing = {**host.session_timing, "idle_seconds": 120.0}
    host.started = host.activity_at = host.guest_activity_at = now
    host.warned, host.idle_nudge = False, None
    events.clear()
    return host, events, now


async def step(host, at):
    await host._session_step(at)
    await asyncio.sleep(0.01)  # Trend speaks from a task


def test_the_situation_follows_where_the_guest_is():
    assert guest_situation([])[0] == "nothing"
    state, facts = guest_situation([LATTE], "takeaway")
    assert state == "cart" and "2 × Latte" in facts and "takeaway" in facts
    assert "not chosen yet" in guest_situation([LATTE])[1]
    order = {"id": "o1", "merchant": {"state": "created"}, "payment_status": "unverified"}
    assert guest_situation([], order=order)[0] == "awaiting_payment"
    assert guest_situation([], order=order, paid=True)[0] == "paid"
    assert guest_situation([], order={**order, "payment_status": "paid"})[0] == "paid"


def test_each_situation_asks_its_own_question_and_changes_nothing():
    asks = {
        "nothing": "would like to drink or eat",
        "cart": "pay for these now or add something else",
        "awaiting_payment": "Call kiosk_payment once",
        "paid": "anything else",
    }
    for state, ask in asks.items():
        text = idle_nudge_turn(state, "facts.", 120)
        assert ask in text and "about 120 seconds" in text and "own words" in text
        assert "Never add, change, remove or order anything" in text
        assert "Do not say the session will end" in text
    assert QR_SENTENCE in idle_nudge_turn("awaiting_payment", "", 120)
    assert "action=view" in idle_nudge_turn("cart", "", 120)


def test_a_quiet_guest_is_asked_and_the_session_stays_open(svc):
    async def run():
        host, events, start = await session(svc)
        await step(host, start + 119)
        assert host.codex.turns == []
        await step(host, start + 121)
        ((thread, text),) = host.codex.turns
        assert thread == host.thread_id
        assert "has not chosen anything" in text and "would like to drink or eat" in text
        assert not any(e["type"] == "warning" for e in events), "Trend says it, not the screen"
        await step(host, start + 300)  # still quiet, long after: no end, no second question
        assert host.active and len(host.codex.turns) == 1
        assert not any(e["type"] == "ended" for e in events)
        assert host.audio_metrics["idle_nudges"] == 1
        await host.close()

    asyncio.run(run())


def test_the_question_follows_the_cart(svc):
    async def run():
        host, _, start = await session(svc)
        host.cart, host.fulfillment = [LATTE], ""
        await step(host, start + 121)
        ((_, text),) = host.codex.turns
        assert "Cart, not ordered yet: 2 × Latte" in text
        assert "pay for these now or add something else" in text
        await host.close()

    asyncio.run(run())


def test_a_guest_who_acts_is_asked_again_after_the_next_quiet_stretch(svc):
    async def run():
        host, _, start = await session(svc)
        await step(host, start + 121)
        before = host.guest_activity_at
        await host.command({"type": "activity", "generation": host.generation})
        assert host.guest_activity_at > before, "a screen touch is the guest's own activity"
        host.activity_at = host.guest_activity_at = start + 130  # that touch, in test time
        await step(host, start + 200)
        assert len(host.codex.turns) == 1
        await step(host, start + 251)
        assert len(host.codex.turns) == 2
        await host.close()

    asyncio.run(run())


def test_trend_warns_before_the_time_limit_and_the_limit_still_ends_it(svc):
    async def run():
        host, events, start = await session(svc)
        host.activity_at = host.guest_activity_at = start + 540
        await step(host, start + 541)  # 60 s before the 600 s limit (+1 s off the boundary)
        ((_, text),) = host.codex.turns
        assert text == time_warning_turn(60)
        await step(host, start + 601)
        assert not host.active
        assert any(e["type"] == "ended" and e.get("reason") == "time_limit" for e in events)
        await host.close()

    asyncio.run(run())


def test_the_screen_asks_only_when_trend_cannot(svc):
    async def run():
        host, events, start = await session(svc, refuse=True)
        await step(host, start + 121)
        (warning,) = [e for e in events if e["type"] == "warning"]
        assert warning["message"] == "Bạn cần Trend giúp gì thêm không?"
        assert host.active
        await host.close()

    asyncio.run(run())


def test_a_warning_waits_until_trend_has_finished_speaking(svc):
    """2026-11-05: a time warning cut "Dạ, hiểu rồi, mình sẽ..." mid-sentence."""

    async def run():
        host, events, start = await session(svc)
        host.playing = True  # Trend is still saying its previous reply
        await step(host, start + 121)
        await asyncio.sleep(0.25)
        assert host.codex.turns == [], "not while Trend is speaking"
        host.playing = False
        await asyncio.sleep(0.25)
        ((_, text),) = host.codex.turns
        assert text == idle_nudge_turn(*host.guest_situation(), 120)
        await host.close()

    asyncio.run(run())


def test_a_warning_for_a_session_that_ended_meanwhile_is_dropped(svc):
    async def run():
        host, events, start = await session(svc)
        host.playing = True
        await step(host, start + 121)
        await host.end("idle")
        host.playing = False
        await asyncio.sleep(0.25)
        assert host.codex.turns == []
        assert not any(e["type"] == "warning" for e in events)
        await host.close()

    asyncio.run(run())
