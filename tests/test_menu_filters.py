"""Price and category questions are answered by one filtered menu read.

2026-11-07: a category question searched by keyword ("trà") returned at most three
suggestions, and price questions ("món nào dưới 40 nghìn", "rẻ nhất") had no tool support,
so Codex reasoned over the whole snapshot in extra steps and could miss items. Structured
filters return every matching item, ordered by price when asked, and the screen shows them.
"""

import asyncio
import json
import sys

import pytest
from test_kiosk_runtime import FakeCodex
from test_menu_batch import catalog as catalog_fixture

from trendcoffee.codex_voice import compact_catalog
from trendcoffee.kiosk import TOOLS, InteractionHost
from trendcoffee.service import ServiceError


@pytest.fixture
def catalog(svc):
    return catalog_fixture.__wrapped__(svc)


def categories(result):
    return {item["category"] for item in result["items"]}


@pytest.mark.parametrize("name", ["trà", "món trà", "Món Trà", "tra", "tea", "a87d969ab5"])
def test_a_category_returns_every_item_in_it_not_three_suggestions(catalog, name):
    result = catalog.menu_search(category=name)
    assert categories(result) == {"món trà"}
    assert len(result["items"]) == 17
    assert result["filters"]["category"] == "món trà"


@pytest.mark.parametrize(
    ("name", "expected"),
    [("cà phê", "cà phê"), ("cafe", "cà phê"), ("bánh", "món bánh"), ("sinh tố", "sinh tố")],
)
def test_every_published_category_can_be_named_the_way_guests_say_it(catalog, name, expected):
    assert categories(catalog.menu_search(category=name)) == {expected}


def test_a_price_ceiling_returns_every_item_at_or_under_it_cheapest_first(catalog):
    result = catalog.menu_search(max_price_vnd=40000, sort="price_asc")
    prices = [item["price_vnd"] for item in result["items"]]
    assert prices and all(price <= 40000 for price in prices)
    assert prices == sorted(prices)
    every = [i for i in catalog.menu() if i["price_vnd"] <= 40000]
    assert len(prices) == len(every)


def test_most_expensive_first_and_a_price_floor(catalog):
    result = catalog.menu_search(min_price_vnd=60000, sort="price_desc")
    prices = [item["price_vnd"] for item in result["items"]]
    assert prices and min(prices) >= 60000
    assert prices == sorted(prices, reverse=True)


def test_category_and_price_combine(catalog):
    result = catalog.menu_search(category="cà phê", max_price_vnd=40000, sort="price_asc")
    assert categories(result) == {"cà phê"}
    assert all(item["price_vnd"] <= 40000 for item in result["items"])
    assert result["items"][0]["name"] == "Cà phê đen"


def test_a_named_drink_can_be_searched_inside_a_category(catalog):
    result = catalog.menu_search(queries=["đào"], category="trà")
    assert "Trà vải đào" in {item["name"] for item in result["items"]}
    assert categories(result) == {"món trà"}


def test_an_unknown_category_is_reported_with_the_real_categories(catalog):
    result = catalog.menu_search(category="bia")
    assert result["items"] == []
    assert result["unknown_category"] == "bia"
    assert {c["name"] for c in result["categories"]} == {
        "cà phê",
        "món bánh",
        "món trà",
        "sinh tố",
    }


def test_no_item_in_a_price_range_is_an_empty_answer_not_an_error(catalog):
    result = catalog.menu_search(max_price_vnd=1000)
    assert result["items"] == [] and result["filters"]["max_price_vnd"] == 1000


@pytest.mark.parametrize(
    "filters",
    [
        {"max_price_vnd": -1},
        {"min_price_vnd": True},
        {"max_price_vnd": "40k"},
        {"min_price_vnd": 50000, "max_price_vnd": 40000},
        {"sort": "name"},
        {"category": ""},
        {"category": "x" * 101},
    ],
)
def test_malformed_filters_are_rejected(catalog, filters):
    with pytest.raises(ServiceError):
        catalog.menu_search(**filters)


def test_the_voice_tool_offers_the_filters():
    (menu,) = [tool for tool in TOOLS if tool["name"] == "kiosk_menu"]
    properties = menu["inputSchema"]["properties"]
    assert {"category", "min_price_vnd", "max_price_vnd", "sort"} <= set(properties)


def test_the_kiosk_shows_exactly_the_filtered_items(catalog):
    async def run():
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(catalog, codex=FakeCodex())
        await host.attach(catalog.new_session(), send)
        await host.begin(manual=True)
        try:
            tool, _ = host.codex.callbacks[host.thread_id]
            events.clear()
            result = await tool(
                {
                    "tool": "kiosk_menu",
                    "arguments": {"category": "trà", "max_price_vnd": 50000},
                    "callId": "f1",
                }
            )
            (view,) = [e for e in events if e["type"] == "view"]
            assert view["item_ids"] == [item["id"] for item in result["items"]]
            assert len(view["item_ids"]) >= 1
            assert host.cart == []
        finally:
            await host.close()

    asyncio.run(run())


def test_the_mcp_menu_tool_accepts_the_filters(catalog):
    from mcp import Client, StdioServerParameters

    async def run():
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "trendcoffee", "mcp", "--db", str(catalog.store.path)],
            env={"TREND_MERCHANT_ENABLED": "0"},
        )
        async with Client(server) as client:
            result = (
                await client.call_tool("get_menu", {"category": "sinh tố", "sort": "price_desc"})
            ).structured_content
            assert {item["category"] for item in result["items"]} == {"sinh tố"}
            prices = [item["price_vnd"] for item in result["items"]]
            assert prices == sorted(prices, reverse=True)

    asyncio.run(run())


def test_the_menu_snapshot_keeps_every_item_and_drops_only_repeated_fields(catalog):
    items = catalog.menu()
    items[0] = {**items[0], "availability": "sold_out"}
    text = compact_catalog(items)
    legend, body = text.split("\n")
    data = json.loads(body)
    assert [row["id"] for row in data] == [item["id"] for item in items]
    assert all(row["price_vnd"] == item["price_vnd"] for row, item in zip(data, items, strict=True))
    assert data[0]["availability"] == "sold_out", "a sold-out item stays marked"
    assert '"availability":"unknown"' not in text and '"stale":false' not in text
    # The single published size is stated once instead of on all 51 items.
    assert '"options"' not in body
    assert "tiêu chuẩn" in legend
    old = json.dumps(
        [
            {
                k: i[k]
                for k in (
                    "id",
                    "name",
                    "category",
                    "description",
                    "price_vnd",
                    "options",
                    "availability",
                    "stale",
                )
                if k in i
            }
            for i in items
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert len(text) < 0.75 * len(old)
