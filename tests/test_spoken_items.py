"""What Trend reads out loud about drinks must also be on the customer's screen.

2026-11-04: 20 of 90 replies that named menu items or prices had no display tool behind them
(advice and search answers read from the catalog in the prompt). Acknowledgements such as
"Dạ, một trà vải đào mang đi nhé!" name a drink too, but a tool follows and shows it.
"""

import asyncio

from test_speaker import speaker_host

from trendcoffee.claim_guard import spoken_items

CATALOG = [
    {"id": "a1", "name": "Trà vải đào"},
    {"id": "a2", "name": "Cà phê sữa"},
    {"id": "a3", "name": "Cà phê sữa đá"},
    {"id": "a4", "name": "Trà"},  # too short to be a drink name in speech
    {"id": "a5", "name": "Matcha Coco"},
]


def test_drinks_named_in_speech_are_found_in_the_order_they_are_said():
    text = "Có matcha coco mát lạnh và Trà Vải Đào thơm nhẹ nha bạn."
    assert spoken_items(text, CATALOG) == ["a5", "a1"]


def test_a_longer_name_replaces_the_shorter_name_inside_it():
    assert spoken_items("Mình có cà phê sữa đá nè", CATALOG) == ["a3"]
    assert spoken_items("Mình có cà phê sữa nè", CATALOG) == ["a2"]


def test_short_names_and_unrelated_words_are_not_drinks():
    assert spoken_items("Trà là thức uống truyền thống, bạn chọn gì nhé?", CATALOG) == []
    assert spoken_items("", CATALOG) == []


def test_the_screen_gets_at_most_six_drinks():
    catalog = [{"id": f"i{n}", "name": f"Món số {n:02d} đặc biệt"} for n in range(10)]
    text = " ".join(f"món số {n:02d} đặc biệt" for n in range(10))
    assert len(spoken_items(text, catalog)) == 6


async def voice(svc, delay=0.05):
    events = []

    async def send(event):
        events.append(event)

    host, speakers = speaker_host(svc)
    host.show_delay = delay
    await host.attach(svc.new_session(), send)
    await host.begin(manual=True)
    on_tool, on_event = host.codex.callbacks[host.thread_id]
    items = host.service.menu()[:2]
    return host, events, on_tool, on_event, items


async def says(on_event, who, text, turn):
    await on_event("thread/realtime/transcript/done", {"role": who, "text": text, "turnId": turn})


def views(events):
    return [e for e in events if e["type"] == "view"]


def test_drinks_named_without_any_tool_are_shown_on_the_screen(svc):
    async def run():
        host, events, _, on_event, items = await voice(svc)
        events.clear()
        await says(on_event, "user", "Tìm cho tôi những món gợi ý nhé", "u1")
        await says(
            on_event, "assistant", f"Mình gợi ý {items[0]['name']} và {items[1]['name']}.", "a1"
        )
        assert views(events) == [], "not immediately: a tool may still answer"
        await asyncio.sleep(0.2)
        (shown,) = views(events)
        assert shown["view"] == "menu"
        assert shown["item_ids"] == [items[0]["id"], items[1]["id"]]
        assert host.audio_metrics["shown_for_speech"] == 1
        await host.close()

    asyncio.run(run())


def test_nothing_extra_is_shown_when_a_kiosk_tool_answered_the_request(svc):
    async def run():
        host, events, on_tool, on_event, items = await voice(svc)
        await says(on_event, "user", "Cho mình xem món đó nhé bạn", "u1")
        await says(on_event, "assistant", f"Dạ, {items[0]['name']} mang đi nhé!", "a1")
        events.clear()
        await on_tool({"tool": "kiosk_menu", "arguments": {"query": "x"}, "callId": "c1"})
        shown_by_tool = len(views(events))
        await asyncio.sleep(0.2)
        assert len(views(events)) == shown_by_tool == 1, "only the tool's own view"
        assert host.audio_metrics.get("shown_for_speech", 0) == 0
        await host.close()

    asyncio.run(run())


def test_replies_without_drink_names_show_nothing(svc):
    async def run():
        host, events, _, on_event, _ = await voice(svc)
        events.clear()
        await says(on_event, "user", "Bạn có nghe mình nói không", "u1")
        await says(on_event, "assistant", "Dạ, mình đang nghe bạn đây.", "a1")
        await asyncio.sleep(0.2)
        assert views(events) == []
        await host.close()

    asyncio.run(run())


def test_a_session_that_ended_shows_nothing(svc):
    async def run():
        host, events, _, on_event, items = await voice(svc, delay=0.15)
        await says(on_event, "user", "Gợi ý cho mình món nào đó", "u1")
        await says(on_event, "assistant", f"Thử {items[0]['name']} nhé.", "a1")
        events.clear()
        await host.end("next_guest")
        await asyncio.sleep(0.3)
        assert views(events) == []
        await host.close()

    asyncio.run(run())


def test_drinks_named_after_a_menu_view_that_lacks_them_are_added_to_the_screen(svc):
    """2026-11-04 15:27: the screen showed other dishes, Trend read "trà nhài hoa cúc" aloud."""

    async def run():
        host, events, on_tool, on_event, items = await voice(svc)
        other = host.service.menu()[-1]
        await says(on_event, "user", "Tìm cho mình những món gợi ý nhé", "u1")
        await on_tool(
            {"tool": "kiosk_menu", "arguments": {"item_ids": [other["id"]]}, "callId": "m1"}
        )
        events.clear()
        await says(on_event, "assistant", f"Mình gợi ý {items[0]['name']} nhé.", "a1")
        await asyncio.sleep(0.2)
        (shown,) = views(events)
        assert set(shown["item_ids"]) == {other["id"], items[0]["id"]}, "what was shown stays"
        order = [item["id"] for item in host.service.menu()]
        assert shown["item_ids"] == sorted(shown["item_ids"], key=order.index), "menu order"
        await host.close()

    asyncio.run(run())


def test_a_menu_view_that_already_shows_the_named_drink_is_left_alone(svc):
    async def run():
        host, events, on_tool, on_event, items = await voice(svc)
        await says(on_event, "user", "Tìm cho mình những món gợi ý nhé", "u1")
        await on_tool(
            {"tool": "kiosk_menu", "arguments": {"item_ids": [items[0]["id"]]}, "callId": "m1"}
        )
        events.clear()
        await says(on_event, "assistant", f"Có {items[0]['name']} nè bạn.", "a1")
        await asyncio.sleep(0.2)
        assert views(events) == []
        await host.close()

    asyncio.run(run())


def test_the_whole_menu_on_screen_already_shows_every_drink(svc):
    async def run():
        host, events, on_tool, on_event, items = await voice(svc)
        await says(on_event, "user", "Cho mình xem cả menu nhé bạn", "u1")
        await on_tool({"tool": "kiosk_menu", "arguments": {}, "callId": "m1"})
        events.clear()
        await says(on_event, "assistant", f"Có {items[0]['name']} nè bạn.", "a1")
        await asyncio.sleep(0.2)
        assert views(events) == []
        await host.close()

    asyncio.run(run())


def test_a_cart_screen_is_never_replaced_by_a_menu_of_spoken_drinks(svc):
    async def run():
        host, events, on_tool, on_event, items = await voice(svc)
        await says(on_event, "user", "Cho mình xem giỏ hàng nhé bạn", "u1")
        await on_tool({"tool": "kiosk_cart", "arguments": {"action": "view"}, "callId": "c1"})
        events.clear()
        await says(on_event, "assistant", f"Dạ, {items[0]['name']} mang đi nhé.", "a1")
        await asyncio.sleep(0.2)
        assert views(events) == []
        await host.close()

    asyncio.run(run())


def test_a_menu_shown_for_an_earlier_request_does_not_count_for_a_new_one(svc):
    async def run():
        host, events, on_tool, on_event, items = await voice(svc)
        other = host.service.menu()[-1]
        await says(on_event, "user", "Cho mình xem món này nhé bạn", "u1")
        await on_tool(
            {"tool": "kiosk_menu", "arguments": {"item_ids": [other["id"]]}, "callId": "m1"}
        )
        await asyncio.sleep(0.05)
        await says(on_event, "user", "Còn món nào khác không bạn", "u2")
        events.clear()
        await says(on_event, "assistant", f"Thử {items[0]['name']} nhé.", "a2")
        await asyncio.sleep(0.2)
        (shown,) = views(events)
        assert items[0]["id"] in shown["item_ids"]
        await host.close()

    asyncio.run(run())
