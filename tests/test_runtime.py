import asyncio
import json
import sys

from mcp import Client, StdioServerParameters


def test_optional_semantic_selection_is_whitelisted_and_timeout_bounded(svc):
    from trendcoffee.semantic import SemanticRouter

    async def fake_request(message, candidates):
        return ["address", "secret", "not-real"]

    router = SemanticRouter(fake_request, timeout=0.02)
    found = asyncio.run(router.select("where is the store", svc))
    assert [x["id"] for x in found] == ["address"]

    async def slow(*args):
        await asyncio.sleep(0.2)
        return ["address"]

    assert asyncio.run(SemanticRouter(slow, timeout=0.01).select("where", svc)) == []

    async def failure(*args):
        raise RuntimeError("provider unavailable")

    assert asyncio.run(SemanticRouter(failure).select("where", svc)) == []


def test_real_stdio_mcp_client_lists_and_calls_tools(tmp_path):
    async def exercise():
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "trendcoffee", "mcp", "--db", str(tmp_path / "mcp.db")],
            env={"TREND_MERCHANT_ENABLED": "0"},
        )
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert {
                "search_knowledge",
                "get_menu",
                "create_guest_session",
                "get_progress",
                "draft_order",
                "submit_request",
                "remember_preference",
                "forget_preferences",
                "request_handoff",
                "print_invoice",
                "get_invoice_status",
            } <= names
            assert not any("staff" in name or "mark_paid" in name for name in names)
            response = await client.call_tool("create_guest_session", {})
            data = response.structured_content
            token = data["session_token"]
            result = await client.call_tool("get_progress", {"session_token": token})
            assert result.structured_content["orders"] == []
            bad = await client.call_tool("get_progress", {"session_token": "wrong"})
            assert bad.is_error

    asyncio.run(exercise())


def test_actual_public_bundle_import(tmp_path):
    from pathlib import Path

    from trendcoffee.service import Service

    service = Service(tmp_path / "sources.db")
    bundle = json.loads(Path("data/trendcoffee-public.json").read_text())
    service.ingest(bundle)
    assert len(service.menu()) == 51
    assert all(item["availability"] == "unknown" for item in service.menu())
    assert service.search("thanh toán QR")
    assert all(d["approved"] for d in service.search("địa chỉ"))
