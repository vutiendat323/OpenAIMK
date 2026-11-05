"""The model can reason over the whole catalog and display actual selected IDs."""

import asyncio

import pytest
from test_kiosk_runtime import FakeCodex
from test_menu_batch import catalog as catalog_fixture

from trendcoffee.codex_voice import CodexVoice
from trendcoffee.kiosk import InteractionHost
from trendcoffee.service import ServiceError


@pytest.fixture
def catalog(svc):
    return catalog_fixture.__wrapped__(svc)


def test_unknown_preference_returns_full_catalog_for_reasoning(catalog):
    result = catalog.menu_search("trái cây")
    assert result["requires_catalog_review"] is True
    assert len(result["catalog"]) == 51
    names = {item["name"] for item in result["catalog"]}
    assert {"Trà vải đào", "Cam tươi.", "Yaourt Xoài Đá Xay"} <= names


def test_meaning_based_selection_displays_ids_without_text_matching(catalog):
    async def run():
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(catalog, codex=FakeCodex())
        await host.attach(catalog.new_session(), send)
        await host.begin(manual=True)
        try:
            call, _ = host.codex.callbacks[host.thread_id]
            result = await call(
                {
                    "tool": "kiosk_menu",
                    "arguments": {
                        "query": "trái cây",
                        "item_ids": ["03d9fe8299", "009d435ea6"],
                    },
                }
            )
            assert [item["name"] for item in result["items"]] == ["Trà vải đào", "Cam tươi."]
            view = next(event for event in reversed(events) if event["type"] == "view")
            assert view["item_ids"] == ["03d9fe8299", "009d435ea6"]
            assert host.cart == []
            assert catalog.progress(host.token)["orders"] == []
        finally:
            await host.close()

    asyncio.run(run())


def test_selected_menu_ids_are_validated_atomically(catalog):
    with pytest.raises(ServiceError, match="item_not_found"):
        catalog.menu_search(item_ids=["03d9fe8299", "invented-fruit"])


def test_backing_codex_has_entire_catalog_while_voice_delegates_without_copying_it(catalog):
    async def run():
        native = CodexVoice(".")
        captured = []

        async def start():
            pass

        async def request(method, params, **kwargs):
            captured.append((method, params))
            if method == "thread/start":
                return {"thread": {"id": "guest"}}
            if method == "thread/realtime/start":
                native.started["guest"].set_result({})
            return {}

        native.start, native.request = start, request
        await native.create_thread([], None, None, catalog.menu())
        await native.start_audio("guest")
        instructions = captured[0][1]["developerInstructions"]
        for name in ["Trà vải đào", "Cam tươi.", "Yaourt Xoài Đá Xay", "Cà phê đen"]:
            assert name in instructions
        assert '"id":"03d9fe8299"' in instructions
        assert '"price_vnd":58000' in instructions
        voice = captured[1][1]
        assert "Codex holds the full current menu" in voice["prompt"]
        assert "03d9fe8299" not in voice["prompt"]
        assert "03d9fe8299" not in voice["realtimeStartInstructions"]
        await native.stop_voice("guest")
        assert "guest" not in native.instructions

    asyncio.run(run())
