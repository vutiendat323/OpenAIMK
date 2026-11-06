"""Trend must not state a kiosk result that no kiosk tool produced.

Sentences come from real kiosk transcripts of 2026-11-03/04 in which the voice layer
answered without delegating to Codex.
"""

import asyncio

import pytest
from test_speaker import native_audio, speaker_host

from trendcoffee.claim_guard import ClaimGuard

FABRICATED = [
    "Bạn quét QR trên màn hình để thanh toán nhé.",
    "Dạ, một Matcha Coco mang đi nhé. Đã vào giỏ rồi đó, bạn muốn thanh toán luôn không?",
    "Đơn cam tươi mang đi đã tạo xong, bạn quét QR trên màn hình để thanh toán nhé.",
    "Menu Trend đang mở trên màn hình rồi đó, bạn xem món nào ưng rồi nói mình nhé.",
    "Mình đã thêm hai latte mang đi vào đơn rồi, tổng tiền hiển thị trên màn hình.",
    "Dạ, thêm một Matcha Coco dùng tại bàn nhé. Đã có một Matcha Coco tại bàn trong giỏ rồi.",
    "Đơn đã được thanh toán.",
]

ACKNOWLEDGEMENTS = [
    "Dạ, có ngay!",
    "Dạ, mình mở menu ngay nha.",
    "Dạ, một trà vải đào mang đi nhé!",
    "Dạ, mình thêm cà phê sữa vào giỏ cho bạn nhé.",
    "Dạ, một vải đào vào giỏ ngay nhé.",
    "Bạn muốn mình thêm một Cam tươi mang đi và tạo đơn ngay không?",
    "Dạ, chào bạn! Trend đang nghe bạn đây.",
]


@pytest.mark.parametrize("sentence", FABRICATED)
def test_a_result_with_no_tool_behind_it_is_caught(sentence):
    guard = ClaimGuard()
    guard.guest("Đúng rồi, thanh toán giúp mình luôn", 10.0)
    assert guard.reply("a1", sentence, 12.0)


@pytest.mark.parametrize("sentence", ACKNOWLEDGEMENTS)
def test_acknowledgements_and_questions_are_not_results(sentence):
    guard = ClaimGuard()
    guard.guest("Cho mình một trà vải đào mang đi", 10.0)
    assert not guard.reply("a1", sentence, 11.0)


def test_a_result_after_a_tool_for_this_request_plays():
    guard = ClaimGuard()
    guard.guest("Cho mình một trà vải đào mang đi", 10.0)
    guard.tool(11.0)
    assert not guard.reply("a1", FABRICATED[0], 14.0)


def test_codex_may_start_the_tool_just_before_the_guest_transcript_arrives():
    guard = ClaimGuard()
    guard.tool(9.0)
    guard.guest("Cho mình một trà vải đào mang đi", 10.0)
    assert not guard.reply("a1", FABRICATED[0], 14.0)


def test_a_tool_from_an_earlier_request_does_not_cover_a_new_one():
    guard = ClaimGuard()
    guard.guest("Cho mình một trà vải đào mang đi", 10.0)
    guard.tool(11.0)
    guard.guest("Có Tạo lại đơn cam tươi mang đi nhanh lên", 40.0)
    assert guard.reply("a2", FABRICATED[2], 45.0)


def test_a_short_interjection_keeps_the_current_request():
    guard = ClaimGuard()
    guard.guest("Thêm hai phô mai chanh dây, thanh toán giúp mình luôn", 10.0)
    guard.tool(12.0)
    guard.guest("Mang về", 13.0)
    guard.guest("nhé", 14.0)
    assert not guard.reply("a1", FABRICATED[0], 15.0)


def test_a_claim_split_over_deltas_is_caught_once_per_reply():
    guard = ClaimGuard()
    guard.guest("Mình muốn thanh toán luôn", 10.0)
    assert not guard.reply("a1", "Bạn quét", 11.0)
    assert guard.reply("a1", "Bạn quét QR trên màn hình để thanh toán nhé.", 11.2)
    assert not guard.reply("a1", "Bạn quét QR trên màn hình để thanh toán nhé. Cảm ơn", 11.4)
    assert guard.reply("a2", FABRICATED[1], 12.0), "a new reply is checked again"
    assert guard.blocked == 2


def test_nothing_is_verified_before_any_tool_ran():
    guard = ClaimGuard()
    assert guard.reply("a1", FABRICATED[3], 1.0)


class Codex:
    """Records developer notes sent to the realtime voice layer."""

    def __init__(self, base):
        self.base = base
        self.notes = []

    def __getattr__(self, name):
        return getattr(self.base, name)

    async def append_text(self, thread, role, text):
        self.notes.append((thread, role, text))


async def voice_host(svc):
    events = []

    async def send(event):
        events.append(event)

    host, speakers = speaker_host(svc)
    host.codex = Codex(host.codex)
    await host.attach(svc.new_session(), send)
    await host.command({"type": "speaker_offer", "sdp": "offer"})
    await host.begin(manual=True)
    on_tool, on_event = host.codex.callbacks[host.thread_id]
    return host, speakers[0], events, on_tool, on_event


def test_the_kiosk_stops_an_unbacked_result_and_asks_the_voice_to_delegate(svc):
    async def run():
        host, speaker, events, _, on_event = await voice_host(svc)
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Đúng rồi, thanh toán giúp mình luôn", "turnId": "u1"},
        )
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        speaker.calls.clear()
        events.clear()
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": FABRICATED[0], "turnId": "a1"},
        )
        assert speaker.calls == ["interrupt"], "the rest of this reply is not played"
        assert {"type": "voice_turn", "role": "user"}.items() <= next(
            e for e in events if e["type"] == "voice_turn"
        ).items(), "the browser also stops its playback"
        assert host.audio_metrics["unbacked_claims"] == 1
        await asyncio.sleep(0.01)  # sent from a task: the event comes from Codex's reader
        (thread, role, note), *_ = host.codex.notes
        assert (thread, role) == (host.thread_id, "developer")
        assert "Delegate" in note and "no kiosk tool ran" in note
        pushed = len(speaker.pushed)
        await on_event("thread/realtime/outputAudio/delta", native_audio(b"\x10\x00" * 960))
        assert len(speaker.pushed) == pushed, "later audio of the stopped reply is dropped"
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a2"})
        await on_event("thread/realtime/outputAudio/delta", native_audio(b"\x11\x00" * 960))
        assert speaker.pushed[-1] == b"\x11\x00" * 960, "the next reply plays"
        await host.close()

    asyncio.run(run())


def test_the_kiosk_lets_a_tool_backed_result_play(svc):
    async def run():
        host, speaker, _, on_tool, on_event = await voice_host(svc)
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Cho mình xem giỏ hàng hiện tại", "turnId": "u1"},
        )
        await on_tool({"tool": "kiosk_cart", "arguments": {"action": "view"}, "callId": "c1"})
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        speaker.calls.clear()
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": "Giỏ hàng đã mở trên màn hình rồi nha.", "turnId": "a1"},
        )
        assert "interrupt" not in speaker.calls
        await asyncio.sleep(0.01)
        assert host.codex.notes == []
        assert host.audio_metrics.get("unbacked_claims", 0) == 0
        await host.close()

    asyncio.run(run())


def test_codex_voice_sends_the_note_as_realtime_developer_text(tmp_path):
    from trendcoffee.codex_voice import CodexVoice

    async def run():
        voice = CodexVoice(tmp_path)
        sent = []

        async def request(method, params, *, timeout=None):
            sent.append((method, params, timeout))
            return {}

        voice.request = request
        await voice.append_text("thread-1", "developer", "note")
        assert sent == [
            (
                "thread/realtime/appendText",
                {"threadId": "thread-1", "role": "developer", "text": "note"},
                5,
            )
        ]

    asyncio.run(run())


def test_paid_is_verified_only_by_a_tool_result_that_says_paid():
    from trendcoffee.claim_guard import says_paid

    assert says_paid({"payment_status": "paid"})
    assert says_paid({"status": "paid", "order_id": "o1"})
    assert says_paid({"payment": {"status": "paid"}})
    assert not says_paid({"payment_status": "unverified", "payment": {"status": "pending"}})
    assert not says_paid({"qr_available": True})
    assert not says_paid(None)


def test_the_kiosk_stops_a_paid_claim_that_no_tool_verified(svc):
    """Seen in a real-model run 2026-11-04: QR shown, order pending, Trend said it was paid."""

    async def run():
        host, speaker, events, on_tool, on_event = await voice_host(svc)
        await on_event(
            "thread/realtime/transcript/done",
            {
                "role": "user",
                "text": "Chọn một Latte cho tôi, thanh toán ngân hàng",
                "turnId": "u1",
            },
        )
        await on_tool({"tool": "kiosk_cart", "arguments": {"action": "view"}, "callId": "c1"})
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        speaker.calls.clear()
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": "Đơn đã được thanh toán.", "turnId": "a1"},
        )
        assert speaker.calls == ["interrupt"], "a tool ran, but none verified payment"
        assert host.audio_metrics["unbacked_claims"] == 1
        await asyncio.sleep(0.01)
        (_, role, note), *_ = host.codex.notes
        assert role == "developer" and "not verified as paid" in note
        await host.close()

    asyncio.run(run())


def test_a_paid_claim_after_a_verified_paid_result_plays(svc):
    async def run():
        host, speaker, _, on_tool, on_event = await voice_host(svc)
        original = host._tool

        async def tool(name, args):
            if name == "kiosk_payment":
                return {"payment_status": "paid", "payment": {"status": "paid"}}
            return await original(name, args)

        host._tool = tool
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Đơn của tôi đã thanh toán chưa", "turnId": "u1"},
        )
        await on_tool({"tool": "kiosk_payment", "arguments": {}, "callId": "p1"})
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        speaker.calls.clear()
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": "Đơn đã được thanh toán.", "turnId": "a1"},
        )
        assert "interrupt" not in speaker.calls
        await host.close()

    asyncio.run(run())


class Delegating(Codex):
    """A Codex that can run a turn for the host; records turns and can refuse them."""

    def __init__(self, base, refuse=False):
        super().__init__(base)
        self.turns, self.refuse = [], refuse

    async def start_turn(self, thread, text):
        if self.refuse:
            raise RuntimeError("codex_request_rejected")
        self.turns.append((thread, text))


async def delegating_host(svc, refuse=False):
    host, speaker, events, on_tool, on_event = await voice_host(svc)
    host.codex = Delegating(host.codex.base, refuse=refuse)
    return host, speaker, events, on_tool, on_event


async def claim(on_event, request, reply, turn):
    await on_event(
        "thread/realtime/transcript/done", {"role": "user", "text": request, "turnId": f"u{turn}"}
    )
    await on_event("thread/realtime/assistantTurn/started", {"turnId": f"a{turn}"})
    await on_event(
        "thread/realtime/transcript/delta",
        {"role": "assistant", "delta": reply, "turnId": f"a{turn}"},
    )
    await asyncio.sleep(0.02)


def test_a_stopped_claim_makes_the_kiosk_run_the_guests_request_itself(svc):
    """2026-11-04 16:00: Trend said "để mình lên đơn", never delegated, then claimed a QR."""

    async def run():
        host, speaker, _, _, on_event = await delegating_host(svc)
        await claim(
            on_event, "Gen ơi hãy giúp mình cho mình một latte mang đi nhé", FABRICATED[0], 1
        )
        ((thread, text),) = host.codex.turns
        assert thread == host.thread_id
        assert "một latte mang đi" in text, "the guest's own words"
        assert "No kiosk tool has run" in text and "kiosk tools" in text
        ((_, role, note),) = host.codex.notes
        assert role == "developer" and "do not delegate that same request" in note
        assert "relay" in note and "every new guest request" in note
        await host.close()

    asyncio.run(run())


def test_the_recent_conversation_is_given_to_the_turn(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Cho mình một cà phê sữa nhé bạn", "turnId": "u0"},
        )
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "assistant", "text": "Bạn muốn mang đi hay uống tại bàn?", "turnId": "a0"},
        )
        await claim(on_event, "Mang đi nha bạn", FABRICATED[0], 1)
        ((_, text),) = host.codex.turns
        assert "cà phê sữa" in text and "mang đi hay uống tại bàn" in text and "Mang đi nha" in text
        await host.close()

    asyncio.run(run())


def test_one_request_is_recovered_once(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await claim(on_event, "Cho mình một latte mang đi nhé bạn", FABRICATED[0], 1)
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": FABRICATED[2], "turnId": "a2"},
        )
        await asyncio.sleep(0.02)
        assert len(host.codex.turns) == 1, "no second turn for the same request"
        await host.close()

    asyncio.run(run())


def test_a_refused_turn_falls_back_to_asking_the_voice_to_delegate(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc, refuse=True)
        await claim(on_event, "Cho mình một latte mang đi nhé bạn", FABRICATED[0], 1)
        ((_, role, note),) = host.codex.notes
        assert "Delegate" in note and "Do not delegate" not in note
        await host.close()

    asyncio.run(run())


def test_an_unverified_paid_claim_runs_a_real_payment_check(svc):
    async def run():
        host, _, _, on_tool, on_event = await delegating_host(svc)
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Đơn của tôi đã thanh toán chưa bạn", "turnId": "u1"},
        )
        await on_tool({"tool": "kiosk_cart", "arguments": {"action": "view"}, "callId": "c1"})
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": "Đơn đã được thanh toán.", "turnId": "a1"},
        )
        await asyncio.sleep(0.02)
        ((_, text),) = host.codex.turns
        assert "kiosk_payment" in text and "đã thanh toán chưa" in text
        await host.close()

    asyncio.run(run())


def test_codex_voice_starts_a_turn_with_the_text(tmp_path):
    from types import SimpleNamespace

    from trendcoffee.codex_voice import CodexVoice

    async def run():
        codex = CodexVoice(tmp_path)
        codex.process = SimpleNamespace(returncode=None)
        sent = []

        async def request(method, params, *, timeout=None):
            sent.append((method, params))
            return {}

        codex.request = request
        await codex.start_turn("thread-1", "do it")
        assert sent == [
            ("turn/start", {"threadId": "thread-1", "input": [{"type": "text", "text": "do it"}]})
        ]

    asyncio.run(run())


@pytest.mark.parametrize(
    "sentence",
    [
        "Đơn đã được thanh toán.",
        "Tuyệt quá, bạn đã thanh toán thành công rồi nhé!",
        "Thanh toán xong rồi, Cà phê sữa của bạn sắp có ngay.",
        "Trend đã nhận được thanh toán, cảm ơn bạn nhiều!",
        "Đơn của bạn đã thanh toán rồi đó.",
    ],
)
def test_a_freely_worded_paid_result_is_still_recognised(sentence):
    """The paid reply is not a fixed sentence (2026-11-05), so the guard reads its meaning."""
    from trendcoffee.claim_guard import PAID

    assert PAID.search(sentence)


@pytest.mark.parametrize(
    "sentence",
    [
        "Bạn quét QR trên màn hình để thanh toán nhé.",
        "Bạn muốn thanh toán luôn không?",
        "QR vẫn đang chờ thanh toán nhé.",
    ],
)
def test_payment_wording_that_claims_nothing_is_not_a_paid_result(sentence):
    from trendcoffee.claim_guard import PAID

    assert not PAID.search(sentence)


# 2026-11-05: "Bạn quét Q.." was cut although the QR was real. A guest remark of three or
# more words while Codex was still working moved the request past the tool, so the guard
# treated the real result as made up.


def test_a_remark_while_codex_works_does_not_cut_the_real_result():
    guard = ClaimGuard()
    guard.guest("Cho mình một kem tươi mang đi", 10.0)
    guard.tool(12.0)  # kiosk_checkout: the QR is on screen
    guard.guest("Ừ nhanh nha bạn ơi", 16.0)
    assert not guard.reply("a1", FABRICATED[0], 18.0)


def test_a_long_acknowledgement_does_not_use_up_the_tool_result():
    guard = ClaimGuard()
    guard.guest("Cho mình một kem tươi mang đi", 10.0)
    guard.tool(12.0)
    guard.done("Dạ, kem tươi mang đi, để mình đặt luôn nhé. Bạn chờ mình chút nha.", 13.0)
    guard.guest("Ừ nhanh nha bạn ơi", 16.0)
    assert not guard.reply("a1", FABRICATED[0], 18.0)


def test_a_result_already_read_out_cannot_be_repeated_as_new():
    guard = ClaimGuard()
    guard.guest("Cho mình một kem tươi mang đi", 10.0)
    guard.tool(12.0)
    assert not guard.reply("a1", FABRICATED[0], 14.0)
    guard.done(FABRICATED[0], 15.0)
    guard.guest("Bao nhiêu tiền vậy bạn", 20.0)
    assert guard.reply("a2", FABRICATED[0], 22.0)


def test_an_old_unread_tool_result_does_not_cover_a_much_later_claim():
    guard = ClaimGuard()
    guard.guest("Cho mình một kem tươi mang đi", 10.0)
    guard.tool(12.0)
    guard.guest("Ừ nhanh nha bạn ơi", 16.0)
    assert guard.reply("a1", FABRICATED[0], 12.0 + 31)


def test_the_kiosk_plays_the_real_qr_after_a_guest_remark(svc):
    """End to end through the host: the reply is not interrupted."""

    async def run():
        host, speaker, _, on_tool, on_event = await voice_host(svc)
        clock = [1000.0]
        host.clock = lambda: clock[0]
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Cho mình một kem tươi mang đi", "turnId": "u1"},
        )
        clock[0] += 2
        await on_tool({"tool": "kiosk_cart", "arguments": {"action": "view"}, "callId": "c1"})
        clock[0] += 4
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Ừ nhanh nha bạn ơi", "turnId": "u2"},
        )
        clock[0] += 2
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        speaker.calls.clear()
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": FABRICATED[0], "turnId": "a1"},
        )
        assert "interrupt" not in speaker.calls
        assert host.audio_metrics.get("unbacked_claims", 0) == 0
        await host.close()

    asyncio.run(run())


def test_a_guest_turn_that_cuts_trend_off_is_logged_and_counted(svc, caplog):
    """ "Dạ, k..." cut: a guest turn (or Trend's own echo) interrupted the reply. Numbers only."""

    async def run():
        host, speaker, _, _, on_event = await voice_host(svc)
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        speaker.queued_ms = 480  # most of the reply is still waiting to play
        with caplog.at_level("WARNING", logger="trendcoffee.kiosk"):
            await on_event("thread/realtime/userTurn/started", {"turnId": "u2"})
        assert "interrupt" in speaker.calls
        assert host.audio_metrics["reply_cuts"] == {"count": 1, "dropped_ms": 480, "unmeasured": 0}
        assert "cut Trend off" in caplog.text and "480 ms" in caplog.text
        speaker.queued_ms = 0  # nothing left of a reply: not a cut
        await on_event("thread/realtime/userTurn/started", {"turnId": "u3"})
        assert host.audio_metrics["reply_cuts"]["count"] == 1
        await host.close()

    asyncio.run(run())


def test_a_cut_while_the_browser_plays_trend_is_counted_without_a_duration(svc, caplog):
    """Avatar 3D plays in the browser (no server speaker): a cut is still logged."""

    async def run():
        host, _, _, _, on_event = await voice_host(svc)
        host.speaker = None  # Avatar 3D: the browser player reports playback instead
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        host.playing = True
        with caplog.at_level("WARNING", logger="trendcoffee.kiosk"):
            await on_event("thread/realtime/userTurn/started", {"turnId": "u2"})
        assert host.audio_metrics["reply_cuts"] == {"count": 1, "dropped_ms": 0, "unmeasured": 1}
        assert "cut Trend off" in caplog.text and "an unmeasured part" in caplog.text
        host.playing = False  # Trend silent: a guest turn is not a cut
        await on_event("thread/realtime/userTurn/started", {"turnId": "u3"})
        assert host.audio_metrics["reply_cuts"]["count"] == 1
        await host.close()

    asyncio.run(run())


def test_reply_audio_the_stopped_speaker_drops_is_logged_once(svc, caplog):
    """A reply lost with no logged cut (2026-11-05): audio after a guest turn, before the
    next assistant turn, is never played; the kiosk now says so."""
    from trendcoffee.speaker import SpeakerTrack

    async def run():
        host, _, _, _, on_event = await voice_host(svc)
        speaker = SpeakerTrack(lambda playing: None)
        speaker.connected = True
        host.speaker = speaker
        await on_event("thread/realtime/userTurn/started", {"turnId": "u1"})
        with caplog.at_level("WARNING", logger="trendcoffee.kiosk"):
            for _ in range(3):
                await on_event("thread/realtime/outputAudio/delta", native_audio(b"\x10\x00" * 960))
        assert speaker.metrics["ignored_suspended_ms"] > 0
        assert caplog.text.count("while the speaker was stopped") == 1
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a2"})
        ignored = speaker.metrics["ignored_suspended_ms"]
        await on_event("thread/realtime/outputAudio/delta", native_audio(b"\x10\x00" * 960))
        assert speaker.metrics["ignored_suspended_ms"] == ignored, "a new reply plays"
        host.speaker = None
        await host.close()

    asyncio.run(run())


def test_a_reply_naming_another_pickup_card_is_spotted():
    """2026-11-06 anti-goal: Trend must never name a card that is not the order's own."""
    from trendcoffee.claim_guard import wrong_card

    reply = "Bạn quét QR trên màn hình để thanh toán nhé, thẻ của bạn là số 7."
    assert wrong_card(reply, 4)
    assert not wrong_card(reply, 7)
    assert not wrong_card("Bạn quét QR trên màn hình để thanh toán nhé.", 4)
    assert wrong_card(reply, None), "no carded order: no card may be named"
    assert wrong_card("Thẻ số 12 của bạn nhé", 2)
    assert wrong_card("thẻ rung của bạn là số 7", 4), "the old wording is still spotted"
    assert not wrong_card("Mình có số thẻ ngân hàng", 4)


def test_the_kiosk_stops_a_reply_with_the_wrong_pickup_card(svc):
    async def run():
        host, speaker, _, on_tool, on_event = await voice_host(svc)
        host.submitted = {"1": {"id": "o1", "vibrating_card": 4}}
        original = host._tool

        async def tool(name, args):
            if name == "kiosk_payment":
                return {"qr_available": True, "payment": {"status": "pending"}}
            return await original(name, args)

        host._tool = tool
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Cho mình thanh toán đơn này nhé", "turnId": "u1"},
        )
        await on_tool({"tool": "kiosk_payment", "arguments": {}, "callId": "p1"})
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        speaker.calls.clear()
        right = "Bạn quét QR trên màn hình để thanh toán nhé, thẻ của bạn là số 4."
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": right, "turnId": "a1"},
        )
        assert "interrupt" not in speaker.calls
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a2"})
        speaker.calls.clear()
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "assistant", "delta": right.replace("số 4", "số 7"), "turnId": "a2"},
        )
        assert speaker.calls == ["interrupt"]
        assert host.audio_metrics["wrong_card_claims"] == 1
        await asyncio.sleep(0.05)
        notes = [note for _, role, note in host.codex.notes if role == "developer"]
        assert any("số 4" in note for note in notes)
        await host.close()

    asyncio.run(run())


# A (2026-11-06): Trend promised ("mình ghi liền cho bạn") and never handed the order to Codex
# (16:07, 20:38, 20:44); the guest waited until repeating. The kiosk now runs it itself.
REQUEST = "Cho mình một cà phê đen mang đi nha"
PROMISE = "Dạ, một cà phê đen mang đi nè, mình ghi liền cho bạn."


def test_promise_wording_is_recognised():
    from trendcoffee.claim_guard import promises

    for text in (
        "Dạ, cà phê đen mang đi, mình làm ngay cho bạn",
        "Dạ, một cà phê sữa mang đi nữa nha, mình gửi ngay cho bạn.",
        PROMISE,
        "Dạ, để mình lên đơn ngay cho bạn nhé.",
        "Dạ, mình đang chờ hệ thống trả kết quả, bạn đợi mình một chút nha.",
    ):
        assert promises(text), text
    for text in (
        "Bạn muốn uống gì hôm nay?",
        "Dạ, cảm ơn bạn, chúc bạn một ngày thật dễ thương nha.",
        "Bạn quét QR trên màn hình để thanh toán nhé.",
    ):
        assert not promises(text), text


async def promise_host(svc):
    host, speaker, events, on_tool, on_event = await delegating_host(svc)
    host.promise_wait = 0.05
    await on_event(
        "thread/realtime/transcript/done", {"role": "user", "text": REQUEST, "turnId": "u1"}
    )
    await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
    return host, on_event


async def promise(on_event, turn="a1"):
    await on_event(
        "thread/realtime/transcript/done", {"role": "assistant", "text": PROMISE, "turnId": turn}
    )


def test_a_promise_with_no_codex_turn_makes_the_kiosk_run_the_request(svc, caplog):
    async def run():
        host, on_event = await promise_host(svc)
        with caplog.at_level("WARNING", logger="trendcoffee.kiosk"):
            await promise(on_event)
            await asyncio.sleep(0.2)
        ((thread, text),) = host.codex.turns
        assert thread == host.thread_id and REQUEST in text
        assert host.audio_metrics["undelegated_promises"] == 1
        assert "promised" in caplog.text
        notes = [note for _, role, note in host.codex.notes if role == "developer"]
        assert any("running" in note for note in notes)
        await host.close()

    asyncio.run(run())


def test_a_promise_followed_by_a_codex_turn_is_left_alone(svc):
    async def run():
        host, on_event = await promise_host(svc)
        await promise(on_event)
        await on_event("turn/started", {"threadId": host.thread_id, "turn": {"id": "t1"}})
        await asyncio.sleep(0.2)
        assert host.codex.turns == []
        await host.close()

    asyncio.run(run())


def test_a_codex_turn_just_before_the_guest_transcript_counts(svc):
    """Codex often starts before the guest's transcript arrives (20:38:20 vs 20:38:21)."""

    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        host.promise_wait = 0.05
        await on_event("turn/started", {"threadId": host.thread_id, "turn": {"id": "t1"}})
        await on_event(
            "thread/realtime/transcript/done", {"role": "user", "text": REQUEST, "turnId": "u1"}
        )
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        await promise(on_event)
        await asyncio.sleep(0.2)
        assert host.codex.turns == []
        await host.close()

    asyncio.run(run())


def test_one_takeover_per_request(svc):
    async def run():
        host, on_event = await promise_host(svc)
        await promise(on_event, "a1")
        await asyncio.sleep(0.2)
        await promise(on_event, "a2")
        await asyncio.sleep(0.2)
        assert len(host.codex.turns) == 1
        await host.close()

    asyncio.run(run())


def test_codex_turn_starts_reach_the_kiosk():
    from trendcoffee.codex_voice import FORWARDED_EVENTS

    assert "turn/started" in FORWARDED_EVENTS


# 2026-11-06 20:38: after "Do not delegate it again ... wait for the result", Trend stopped
# delegating NEW orders for the rest of the session ("mình đang chờ hệ thống trả kết quả").
def test_takeover_notes_cover_only_the_one_request():
    from trendcoffee.claim_guard import takeover_note

    for promise_kind in (False, True):
        note = takeover_note(REQUEST, promise=promise_kind)
        assert f'"{REQUEST}"' in note, "the note names the one request it is about"
        assert "every new guest request" in note and "as usual" in note
        assert "wait for the result" not in note.lower()


def test_the_promise_takeover_tells_trend_to_keep_delegating_new_requests(svc):
    async def run():
        host, on_event = await promise_host(svc)
        await promise(on_event)
        await asyncio.sleep(0.2)
        notes = [note for _, role, note in host.codex.notes if role == "developer"]
        assert any(REQUEST in note and "every new guest request" in note for note in notes)
        await host.close()

    asyncio.run(run())


def test_the_unbacked_result_takeover_tells_trend_to_keep_delegating_new_requests(svc):
    async def run():
        host, _, _, _, on_event = await delegating_host(svc)
        await claim(on_event, REQUEST, FABRICATED[0], 1)
        await asyncio.sleep(0.05)
        notes = [note for _, role, note in host.codex.notes if role == "developer"]
        assert any(REQUEST in note and "every new guest request" in note for note in notes)
        await host.close()

    asyncio.run(run())
