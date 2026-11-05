"""Before a session ends, Trend says so in its own words; the screen shows no countdown.

User request 2026-11-05: replace the on-screen idle notice with Trend's voice. Fixtures
only: the Codex turn is recorded, not run.
"""

import asyncio

from test_claim_guard import delegating_host

from trendcoffee.session_notices import idle_warning_turn, time_warning_turn


async def session(svc, refuse=False):
    host, _, events, _, _ = await delegating_host(svc, refuse=refuse)
    now = host.clock()
    host.session_timing = {**host.session_timing, "idle_seconds": 120.0}
    host.started = host.activity_at = host.guest_activity_at = now
    host.warned, host.idle_warning = False, None
    events.clear()
    return host, events, now


async def step(host, at):
    await host._session_step(at)
    await asyncio.sleep(0.01)  # the warning is spoken from a task


def test_the_turns_ask_for_a_short_warning_in_trends_own_words_and_no_action():
    for text in (idle_warning_turn(30), time_warning_turn(60)):
        assert "own words" in text and "one short sentence" in text
        assert "Do not call any tool" in text and "not a guest message" in text
    assert "about 30 seconds" in idle_warning_turn(30)
    assert "about 60 seconds" in time_warning_turn(60)


def test_trend_warns_of_idleness_and_the_screen_shows_nothing(svc):
    async def run():
        host, events, start = await session(svc)
        await step(host, start + 88)
        assert host.codex.turns == []
        await step(host, start + 91)  # a quarter of 120 s before the end (+1 s of margin)
        ((thread, text),) = host.codex.turns
        assert thread == host.thread_id and text == idle_warning_turn(30)
        assert not any(e["type"] == "warning" for e in events), "no on-screen countdown"
        await step(host, start + 95)
        assert len(host.codex.turns) == 1, "once per idle stretch"
        assert host.active
        await host.close()

    asyncio.run(run())


def test_trend_speaking_the_warning_does_not_keep_the_session_open(svc):
    async def run():
        host, events, start = await session(svc)
        await step(host, start + 91)  # warned: ends at +121
        host.activity_at = start + 95  # Trend's own playback of the warning
        await step(host, start + 120)
        assert host.active
        await step(host, start + 121)
        assert not host.active, "ends when Trend said it would"
        assert any(e["type"] == "ended" and e.get("reason") == "idle" for e in events)
        await host.close()

    asyncio.run(run())


def test_a_guest_who_comes_back_keeps_the_session(svc):
    async def run():
        host, _, start = await session(svc)
        await step(host, start + 91)  # warned: would end at +121
        before = host.guest_activity_at
        await host.command({"type": "activity", "generation": host.generation})
        assert host.guest_activity_at > before, "a screen touch is the guest's own activity"
        host.activity_at = host.guest_activity_at = start + 100  # that touch, in test time
        await step(host, start + 125)
        assert host.active and host.idle_warning is None, "past the warned end, still on"
        await step(host, start + 191)
        assert len(host.codex.turns) == 2, "a new idle stretch gets a new warning"
        await host.close()

    asyncio.run(run())


def test_trend_warns_before_the_time_limit(svc):
    async def run():
        host, events, start = await session(svc)
        host.activity_at = host.guest_activity_at = start + 540
        await step(host, start + 541)  # 60 s before the 600 s limit (+1 s off the boundary)
        ((_, text),) = host.codex.turns
        assert text == time_warning_turn(60)
        assert not any(e["type"] == "warning" for e in events)
        await host.close()

    asyncio.run(run())


def test_the_screen_says_it_only_when_trend_cannot(svc):
    async def run():
        host, events, start = await session(svc, refuse=True)
        await step(host, start + 91)
        (warning,) = [e for e in events if e["type"] == "warning"]
        assert warning["message"] == "Phiên sẽ kết thúc sau 30 giây nếu không có tương tác."
        assert host.audio_metrics["spoken_warnings"] == 1
        await host.close()

    asyncio.run(run())


def test_a_warning_waits_until_trend_has_finished_speaking(svc):
    """2026-11-05: a time warning cut "Dạ, hiểu rồi, mình sẽ..." mid-sentence."""

    async def run():
        host, events, start = await session(svc)
        host.playing = True  # Trend is still saying its previous reply
        await step(host, start + 91)
        await asyncio.sleep(0.25)
        assert host.codex.turns == [], "not while Trend is speaking"
        host.playing = False
        await asyncio.sleep(0.25)
        ((_, text),) = host.codex.turns
        assert text == idle_warning_turn(30)
        await host.close()

    asyncio.run(run())


def test_a_warning_for_a_session_that_ended_meanwhile_is_dropped(svc):
    async def run():
        host, events, start = await session(svc)
        host.playing = True
        await step(host, start + 91)
        await host.end("idle")
        host.playing = False
        await asyncio.sleep(0.25)
        assert host.codex.turns == []
        assert not any(e["type"] == "warning" for e in events)
        await host.close()

    asyncio.run(run())
