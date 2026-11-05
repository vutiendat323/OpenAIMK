"""Live table reads and selection use merchant evidence; never contact the real shop."""

import asyncio
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import Client
from test_kiosk_runtime import FakeCodex
from test_merchant import remote_order
from test_service import line

from trendcoffee.agent import Agent
from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost
from trendcoffee.mcp_server import create_server
from trendcoffee.merchant import MerchantClient
from trendcoffee.service import ServiceError


@pytest.fixture
def tables():
    # Merchant list order, rather than numeric/name order, determines the first free table.
    return [
        {"name": "3", "slug": "three", "status": "reserved", "location": None},
        {"name": "7", "slug": "seven", "status": "available", "location": "Tầng 1"},
        {"name": "5", "slug": "five", "status": "available", "location": ""},
        {"name": "9", "slug": "nine", "status": "occupied", "location": None},
        {"name": "10", "slug": "ten", "status": "new-state", "location": None},
    ]


def merchant(svc, tables, posted=None):
    def handle(request):
        if request.method == "GET" and request.url.path.endswith("/tables"):
            assert request.url.params["branch"] == "ba9355f797"
            return httpx.Response(200, json={"result": copy.deepcopy(tables)})
        assert request.method == "POST" and request.url.path.endswith("/orders/public")
        body = json.loads(request.content)
        if posted is not None:
            posted.append(body)
        return httpx.Response(200, json={"result": remote_order()})

    svc.merchant = MerchantClient(transport=httpx.MockTransport(handle))


def test_http_tables_are_fresh_and_unknown_status_is_never_free(svc, tables):
    merchant(svc, tables)
    with TestClient(create_app(service=svc)) as client:
        response = client.get("/api/tables")
        assert response.status_code == 200
        data = response.json()
        assert data["live"] is True
        assert data["source"] == "merchant_api"
        assert data["fetched_at"]
        assert data["total"] == 5 and data["available_count"] == 2
        assert data["first_available"]["name"] == "7"
        assert data["tables"][-1]["available"] is False
        tables[1]["status"] = "reserved"
        refreshed = client.get("/api/tables").json()
        assert refreshed["first_available"]["name"] == "5"
        assert refreshed["available_count"] == 1
        specific = client.get("/api/tables", params={"table_label": "Bàn 03"}).json()
        assert len(specific["tables"]) == 1
        assert specific["tables"][0]["status"] == "reserved"
        assert specific["available_count"] == 0


def test_auto_checkout_binds_first_free_table_and_retry_ignores_later_availability(svc, tables):
    posted = []
    merchant(svc, tables, posted)
    token = svc.new_session()
    order = svc.checkout(token, [line(quantity=2)], "at_table", checkout_id="auto-table")
    assert order["table_label"] == "7"
    assert posted[0]["table"] == "seven" and posted[0]["type"] == "at-table"
    tables[1]["status"] = "reserved"
    svc.merchant = MerchantClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    again = svc.checkout(token, [line(quantity=2)], "at_table", checkout_id="auto-table")
    assert again["id"] == order["id"] and again["table_label"] == "7"
    assert len(posted) == 1


def test_explicit_table_is_preserved_instead_of_switching_to_first_free(svc, tables):
    posted = []
    merchant(svc, tables, posted)
    order = svc.checkout(
        svc.new_session(), [line(quantity=2)], "at_table", "Bàn 05", checkout_id="specific"
    )
    assert order["table_label"] == "Bàn 05"
    assert posted[0]["table"] == "five"


@pytest.mark.parametrize("failure", ["full", "offline", "local"])
def test_auto_selection_does_not_invent_a_table_or_create_an_order(svc, tables, failure):
    merchant(svc, tables)
    expected = "no_available_tables"
    if failure == "full":
        for table in tables:
            table["status"] = "reserved"
    elif failure == "offline":
        svc.merchant = MerchantClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
        expected = "merchant_rejected"
    else:
        svc.merchant = None
        expected = "table_required"
    token = svc.new_session()
    with pytest.raises(ServiceError, match=expected):
        svc.checkout(token, [line(quantity=2)], "at_table", checkout_id="cannot-assign")
    assert svc.progress(token)["orders"] == []


@pytest.mark.parametrize("result", [None, {}, [None], [{"name": "5", "status": "available"}]])
def test_malformed_live_tables_fail_without_claiming_availability(svc, result):
    svc.merchant = MerchantClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"result": result}))
    )
    with TestClient(create_app(service=svc)) as client:
        response = client.get("/api/tables")
        assert response.status_code == 502
        assert response.json()["error"] == "merchant_invalid_response"


@pytest.mark.parametrize("channel", ["voice", "touch"])
def test_kiosk_reads_live_tables_and_auto_selects_on_fulfillment(svc, tables, channel):
    merchant(svc, tables)

    async def run():
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=FakeCodex())
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        tool, _ = host.codex.callbacks[host.thread_id]
        try:
            available = await tool({"tool": "kiosk_tables", "arguments": {}})
            assert available["available_count"] == 2
            assert host.fulfillment == ""  # A status question never selects or orders.
            if channel == "voice":
                selected = await tool(
                    {"tool": "kiosk_fulfillment", "arguments": {"fulfillment": "at_table"}}
                )
            else:
                selected = await host.command(
                    {
                        "type": "action",
                        "generation": host.generation,
                        "action": {"type": "fulfillment", "value": "at_table"},
                    }
                )
            assert selected["tableLabel"] == "7"
            assert events[-1]["tableLabel"] == "7"
            tables[1]["status"] = "reserved"
            fresh = await tool({"tool": "kiosk_tables", "arguments": {"table_label": "7"}})
            assert fresh["tables"][0]["status"] == "reserved"
            assert fresh["available_count"] == 0
            again = await tool(
                {"tool": "kiosk_fulfillment", "arguments": {"fulfillment": "at_table"}}
            )
            assert again["tableLabel"] == "7"
            assert svc.progress(host.token)["orders"] == []
        finally:
            await host.close()

    asyncio.run(run())


def test_mcp_tables_and_auto_checkout_use_the_same_live_merchant_contract(svc, tables):
    posted = []
    merchant(svc, tables, posted)

    async def run():
        async with Client(create_server(svc)) as client:
            response = await client.call_tool("get_tables", {})
            assert not response.is_error
            assert response.structured_content["first_available"]["name"] == "7"
            checkout = await client.call_tool(
                "checkout_order",
                {
                    "session_token": svc.new_session(),
                    "lines": [line(quantity=2)],
                    "fulfillment": "at_table",
                    "checkout_id": "mcp-table",
                },
            )
            assert not checkout.is_error
            assert checkout.structured_content["table_label"] == "7"
            assert posted[0]["table"] == "seven"

    asyncio.run(run())


def test_voice_controlled_touch_table_edit_accepts_empty_and_intermediate_prefix(svc, tables):
    merchant(svc, tables)

    async def run():
        async def send(event):
            pass

        host = InteractionHost(svc, codex=FakeCodex())
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        try:
            await host._tool("kiosk_fulfillment", {"fulfillment": "at_table"})
            for text in ("", "1", "10"):
                state = await host.command(
                    {
                        "type": "action",
                        "generation": host.generation,
                        "action": {"type": "table", "value": text},
                    }
                )
                assert state["tableLabel"] == text
        finally:
            await host.close()

    asyncio.run(run())


def test_local_text_agent_answers_table_status_from_new_merchant_reads(svc, tables):
    merchant(svc, tables)
    token = svc.new_session()
    agent = Agent(svc)
    reply = asyncio.run(agent.chat(token, "Quán hiện còn bàn trống không?"))
    assert reply["intent"] == "tables"
    assert reply["tables"]["available_count"] == 2
    assert "7" in reply["reply"]
    tables[1]["status"] = "reserved"
    reply = asyncio.run(agent.chat(token, "Tình trạng bàn 7 hiện tại?"))
    assert reply["tables"]["tables"][0]["status"] == "reserved"
    assert "đã được giữ" in reply["reply"]
    assert svc.progress(token)["orders"] == []


@pytest.mark.parametrize(
    "wording", ["tại bàn", "tại bàn nhé", "tại bàn ạ", "tại bàn nhé ạ", "tại quán", "tại quán ạ"]
)
@pytest.mark.parametrize("separate_turn", [False, True])
def test_local_agent_auto_selects_table_for_explicit_at_table_choice(
    svc, tables, separate_turn, wording
):
    merchant(svc, tables)
    token = svc.new_session()
    agent = Agent(svc)
    if separate_turn:
        first = asyncio.run(agent.chat(token, "Cho cà phê sữa"))
        assert first["intent"] == "clarify_fulfillment"
        reply = asyncio.run(agent.chat(token, wording))
    else:
        reply = asyncio.run(agent.chat(token, "Cho cà phê sữa " + wording))
    assert reply["quote"]["table_label"] == "7"
    assert reply["quote"]["fulfillment"] == "at_table"
    assert svc.progress(token)["orders"] == []
