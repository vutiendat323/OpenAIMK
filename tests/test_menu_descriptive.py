"""A descriptive search must show its dishes the first time, and never an empty screen.

2026-11-04: "Tìm cho mình những món có hoa" and "tìm cho tôi món trà" returned no items
(the words "món"/"có" were compared with drink names), the kiosk showed an empty menu, and
Trend read the answer from its catalog; the guest had to ask again before the dishes appeared.
"""

import asyncio

from test_kiosk_runtime import FakeCodex
from test_menu_batch import catalog as catalog

from trendcoffee.kiosk import InteractionHost


def names(result):
    return {item["name"] for item in result["items"]}


def test_descriptive_words_do_not_hide_the_dishes_asked_for(catalog):
    assert "Trà nhài hoa cúc" in names(catalog.menu_search(queries=["món có hoa"]))
    assert {"Trà vải đào", "Trà nhài hoa cúc", "Trà Bắc"} <= names(
        catalog.menu_search(queries=["món trà"])
    )
    assert names(catalog.menu_search(queries=["những món có kem"])), "a cream search finds dishes"
    assert names(catalog.menu_search(queries=["cho mình xem các loại cà phê"]))


def test_a_phrase_with_no_matching_dish_still_matches_nothing(catalog):
    result = catalog.menu_search(queries=["món sao hỏa"])
    assert result["items"] == [] and result["unmatched"] == ["món sao hỏa"]


def test_named_drinks_still_resolve_exactly(catalog):
    result = catalog.menu_search(queries=["cà phê muối", "trà bắc"])
    assert names(result) == {"Cà phê muối", "Trà Bắc"}


async def shown(catalog, **arguments):
    events = []

    async def send(event):
        events.append(event)

    host = InteractionHost(catalog, codex=FakeCodex())
    await host.attach(catalog.new_session(), send)
    await host.begin(manual=True)
    tool, _ = host.codex.callbacks[host.thread_id]
    events.clear()
    await tool({"tool": "kiosk_menu", "arguments": arguments, "callId": "m1"})
    views = [e for e in events if e["type"] == "view"]
    await host.close()
    return views


def test_a_search_that_finds_dishes_shows_those_dishes(catalog):
    async def run():
        (view,) = await shown(catalog, queries=["món có hoa"], query="Tìm các món có hoa")
        assert view["view"] == "menu" and view["item_ids"]

    asyncio.run(run())


def test_a_search_with_no_result_shows_the_whole_menu_not_an_empty_screen(catalog):
    async def run():
        (view,) = await shown(catalog, queries=["món sao hỏa"], query="Tìm món sao hỏa")
        assert view["view"] == "menu"
        assert view["item_ids"] is None, "no filter: the frontend treats [] as 'show nothing'"
        assert view["query"] == "", "the wording of a failed search must not filter the grid"

    asyncio.run(run())
