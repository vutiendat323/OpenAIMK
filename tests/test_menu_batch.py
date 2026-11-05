"""A spoken list is several catalog queries, and batch additions are atomic."""

import asyncio
import json
from pathlib import Path

import pytest
from test_kiosk_runtime import FakeCodex
from test_service import stamp

from trendcoffee.kiosk import InteractionHost


@pytest.fixture
def catalog(svc):
    bundle = json.loads(Path("data/trendcoffee-public.json").read_text())
    for item in bundle["menu"]["items"]:
        item["verified_at"] = stamp()
    svc.ingest({"menu": bundle["menu"]})
    return svc


@pytest.mark.parametrize(
    "query",
    [
        "cà phê muối cà phê sữa trà bắc",
        "ca phe muoi, ca phe sua va tra bac",
        "cafe muoi; cafe sua; tra bac",
    ],
)
def test_combined_menu_query_finds_every_named_drink(catalog, query):
    assert {i["name"] for i in catalog.menu(query)} == {"Cà phê muối", "Cà phê sữa", "Trà Bắc"}


def test_menu_reply_names_at_most_two_drinks_without_hiding_other_matches(catalog):
    from trendcoffee.agent import Agent

    names = {"Cà phê muối", "Cà phê sữa", "Trà Bắc"}
    reply = asyncio.run(
        Agent(catalog).chat(
            catalog.new_session(), "Cà phê muối, cà phê sữa và Trà Bắc giá bao nhiêu?"
        )
    )
    assert {item["name"] for item in reply["menu"]} == names
    assert 1 <= sum(name in reply["reply"] for name in names) <= 2
    assert len(reply["reply"].split()) <= 30


def test_search_reports_unmatched_drink_without_hiding_known_drinks(catalog):
    found = catalog.menu_search(queries=["cà phê muối", "nước sao hỏa", "trà bắc"])
    assert {i["name"] for i in found["items"]} == {"Cà phê muối", "Trà Bắc"}
    assert found["unmatched"] == ["nước sao hỏa"]
    assert len(found["matches"]) == 3


def test_chat_preserves_all_drinks_quantities_and_total(catalog):
    from trendcoffee.agent import Agent

    result = asyncio.run(
        Agent(catalog).chat(
            catalog.new_session(), "Cho 1 cafe muoi, 2 cafe sua va 1 tra bac mang di"
        )
    )
    assert [
        (i["name"], i["quantity"])
        for i in sorted(result["quote"]["lines"], key=lambda i: i["name"])
    ] == [("Cà phê muối", 1), ("Cà phê sữa", 2), ("Trà Bắc", 1)]
    assert result["quote"]["total_vnd"] == 182000


def test_chat_accepts_reported_lychee_peach_takeaway_request(catalog):
    from trendcoffee.agent import Agent

    result = asyncio.run(
        Agent(catalog).chat(catalog.new_session(), "Cho tao một trà vải đào mang đi")
    )
    assert result["intent"] == "quote"
    assert result["quote"]["fulfillment"] == "takeaway"
    assert result["quote"]["total_vnd"] == 58000
    assert [(line["item_id"], line["quantity"]) for line in result["quote"]["lines"]] == [
        ("03d9fe8299", 1)
    ]


def test_real_mcp_search_and_multi_line_quote(catalog):
    import sys

    from mcp import Client, StdioServerParameters

    async def run():
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "trendcoffee", "mcp", "--db", str(catalog.store.path)],
            env={"TREND_MERCHANT_ENABLED": "0"},
        )
        async with Client(server) as client:
            fruit = (
                await client.call_tool(
                    "get_menu",
                    {
                        "query": "trái cây",
                        "item_ids": ["03d9fe8299", "009d435ea6"],
                    },
                )
            ).structured_content
            assert [item["name"] for item in fruit["items"]] == ["Trà vải đào", "Cam tươi."]
            found = (
                await client.call_tool("get_menu", {"query": "cà phê muối cà phê sữa trà bắc"})
            ).structured_content
            assert len(found["items"]) == 3
            token = (await client.call_tool("create_guest_session", {})).structured_content[
                "session_token"
            ]
            result = (
                await client.call_tool(
                    "draft_order",
                    {
                        "session_token": token,
                        "fulfillment": "takeaway",
                        "lines": [
                            {"item_id": i["id"], "quantity": 1, "options": {}}
                            for i in found["items"]
                        ],
                    },
                )
            ).structured_content
            assert len(result["lines"]) == 3
            assert result["total_vnd"] == 142000

    asyncio.run(run())


def test_native_batch_cart_adds_three_drinks_and_rolls_back_invalid_line(catalog):
    async def run():
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(catalog, codex=FakeCodex())
        await host.attach(catalog.new_session(), send)
        await host.begin(manual=True)
        call, _ = host.codex.callbacks[host.thread_id]
        try:
            found = await call(
                {
                    "tool": "kiosk_menu",
                    "arguments": {"queries": ["cà phê muối", "cà phê sữa", "trà bắc"]},
                }
            )
            assert len(found["items"]) == 3
            lines = [
                {"item_id": i["id"], "quantity": 2 if i["name"] == "Trà Bắc" else 1}
                for i in found["items"]
            ]
            result = await call(
                {
                    "tool": "kiosk_cart",
                    "callId": "three",
                    "arguments": {"action": "add", "lines": lines},
                }
            )
            assert len(result["cart"]) == 3
            assert sum(i["quantity"] for i in result["cart"]) == 4
            await call(
                {
                    "tool": "kiosk_cart",
                    "callId": "three",
                    "arguments": {"action": "add", "lines": lines},
                }
            )
            assert sum(i["quantity"] for i in host.cart) == 4
            before = host.snapshot()
            with pytest.raises(Exception, match="item_not_found"):
                await call(
                    {
                        "tool": "kiosk_cart",
                        "arguments": {
                            "action": "add",
                            "lines": [lines[0], {"item_id": "missing", "quantity": 1}],
                        },
                    }
                )
            assert host.snapshot() == before
            menu_event = next(e for e in events if e.get("view") == "menu")
            assert len(menu_event["item_ids"]) == 3
        finally:
            await host.close()

    asyncio.run(run())
