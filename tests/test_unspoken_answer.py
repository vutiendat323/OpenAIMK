"""Codex answered, but the voice never said it: the kiosk asks for the answer again.

Sentences are from real kiosk rollouts of 2026-11-07 (08:33 and 09:09-09:11).
"""

import asyncio

import pytest
from test_claim_guard import delegating_host

from trendcoffee.claim_guard import promises, relay_turn, said

LATTE_QUESTION = "Bạn muốn dùng tại quán hay mang đi cho ly Latte này ạ?"
LATTE_ACK = "Dạ, một latte nhé! Mình làm ngay cho bạn đây."


@pytest.mark.parametrize(
    ("answer", "spoken"),
    [
        (
            "Bạn chọn giúp mình hình thức nhận món nhé: mang đi hay dùng tại bàn?",
            "Mình đang chờ hệ thống xác nhận giúp bạn nha, có gì mình báo liền. "
            "Bạn mang đi hay dùng tại bàn ạ?",
        ),
        (
            "Bạn quét QR trên màn hình để thanh toán nhé, thẻ của bạn là số 15.",
            "Bạn quét QR trên màn hình để thanh toán nhé, thẻ của bạn là số 15.",
        ),
    ],
)
def test_a_reply_that_carries_the_answer_counts_as_said(answer, spoken):
    assert said(answer, spoken)


@pytest.mark.parametrize(
    ("answer", "spoken"),
    [
        (LATTE_QUESTION, LATTE_ACK),
        (
            "Mình chưa nghe rõ ý bạn ở câu vừa rồi ạ. Bạn muốn dùng tại quán hay mang đi ly "
            "Latte này?",
            "Dạ, để mình hiểu đúng ý bạn nha. Mình xem tình huống này ngay đây.",
        ),
        (
            "Mình chưa thấy chè bắp trong thực đơn hiện tại ạ. Bạn muốn chọn món khác mang đi "
            "không?",
            "Dạ, một chè bắp mang đi luôn nhé, mình làm ngay đây.",
        ),
    ],
)
def test_an_acknowledgement_is_not_the_answer(answer, spoken):
    assert not said(answer, spoken)


def test_the_relay_turn_repeats_the_exact_answer_without_tools():
    text = relay_turn(LATTE_QUESTION)
    assert LATTE_QUESTION in text
    assert "no tool" in text


def test_promising_to_look_is_a_promise():
    """09:11: "mình xem ngay nhé" with no delegation; the takeover never ran."""
    for text in (
        "Dạ, một kem tươi với hai trà vải đào, mình xem ngay nhé.",
        "Dạ, để mình xem cho bạn nha.",
        "Mình xem liền cho bạn đây.",
    ):
        assert promises(text), text
    assert not promises("Bạn xem thử menu trên màn hình nhé.")


def test_codex_answers_reach_the_kiosk():
    from trendcoffee.codex_voice import FORWARDED_EVENTS

    assert "item/completed" in FORWARDED_EVENTS


async def answered(on_event, text, phase="final_answer"):
    await on_event(
        "item/completed",
        {
            "threadId": "t",
            "turnId": "c1",
            "item": {"type": "agentMessage", "text": text, "phase": phase},
        },
    )


async def guest_asks(host, on_event, request="Một latte"):
    host.relay_wait = 0.05
    await on_event(
        "thread/realtime/transcript/done", {"role": "user", "text": request, "turnId": "u1"}
    )


async def trend_says(on_event, text, turn="a1"):
    await on_event("thread/realtime/assistantTurn/started", {"turnId": turn})
    await on_event(
        "thread/realtime/transcript/done", {"role": "assistant", "text": text, "turnId": turn}
    )


def test_an_answer_trend_never_said_is_asked_for_again(svc, caplog):
    """09:09:40 Codex asked "tại quán hay mang đi?"; the guest heard only the acknowledgement."""

    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await guest_asks(host, on_event)
        with caplog.at_level("WARNING", logger="trendcoffee.kiosk"):
            await answered(on_event, LATTE_QUESTION)
            await trend_says(on_event, LATTE_ACK)
            await asyncio.sleep(0.3)
        ((thread, text),) = host.codex.turns
        assert thread == host.thread_id and LATTE_QUESTION in text
        assert host.audio_metrics["unspoken_answers"] == 1
        assert "did not say it" in caplog.text
        await host.close()

    asyncio.run(run())


def test_an_answer_trend_said_is_left_alone(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await guest_asks(host, on_event)
        await answered(on_event, LATTE_QUESTION)
        await trend_says(on_event, "Dạ, bạn dùng tại quán hay mang đi ly latte này ạ?")
        await asyncio.sleep(0.3)
        assert host.codex.turns == []
        await host.close()

    asyncio.run(run())


def test_a_new_guest_turn_drops_the_old_answer(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await guest_asks(host, on_event)
        await answered(on_event, LATTE_QUESTION)
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Mang đi nha", "turnId": "u2"},
        )
        await asyncio.sleep(0.3)
        assert host.codex.turns == []
        await host.close()

    asyncio.run(run())


def test_the_answer_is_asked_for_once_per_guest_request(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await guest_asks(host, on_event)
        await answered(on_event, LATTE_QUESTION)
        await asyncio.sleep(0.3)
        await answered(on_event, LATTE_QUESTION)  # the repeat is lost too
        await asyncio.sleep(0.3)
        assert len(host.codex.turns) == 1
        await host.close()

    asyncio.run(run())


def test_progress_commentary_is_not_an_answer(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await guest_asks(host, on_event)
        await answered(on_event, "Mình đang kiểm tra menu.", phase="commentary")
        await asyncio.sleep(0.3)
        assert host.codex.turns == []
        await host.close()

    asyncio.run(run())


def test_the_kiosk_waits_while_trend_is_still_speaking(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await guest_asks(host, on_event)
        host.playing = True
        await answered(on_event, LATTE_QUESTION)
        await asyncio.sleep(0.3)
        assert host.codex.turns == [], "Trend may still be saying it"
        await trend_says(on_event, "Dạ, bạn dùng tại quán hay mang đi ly latte này ạ?")
        host.playing = False
        await asyncio.sleep(0.3)
        assert host.codex.turns == []
        await host.close()

    asyncio.run(run())
