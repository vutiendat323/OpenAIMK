import asyncio

import pytest
from test_service import line

from trendcoffee.agent import Agent
from trendcoffee.service import ServiceError


def test_fulfillment_must_be_explicit_and_table_needs_label(svc):
    token = svc.new_session()
    with pytest.raises(ServiceError, match="fulfillment_required"):
        svc.quote(token, [line()])
    with pytest.raises(ServiceError, match="table_required"):
        svc.quote(token, [line()], fulfillment="at_table")
    q = svc.quote(token, [line()], fulfillment="at_table", table_label="Bàn 3")
    assert q["table_label"] == "Bàn 3"


def test_chat_remembers_pending_cups_and_only_asks_missing_fulfillment(svc):
    a, b = svc.new_session(), svc.new_session()
    agent = Agent(svc)
    first = asyncio.run(agent.chat(a, "Cho 2 ly cà phê sữa"))
    assert first["intent"] == "clarify_fulfillment"
    assert "quote" not in first
    second = asyncio.run(agent.chat(a, "mang đi"))
    assert second["quote"]["total_vnd"] == 60000
    assert second["quote"]["fulfillment"] == "takeaway"
    other = asyncio.run(agent.chat(b, "mang đi"))
    assert "quote" not in other


@pytest.mark.parametrize(
    "message", ["Cho cà phê sữa không đá mang đi", "Cho cà phê sữa thêm sữa mang đi"]
)
def test_unrepresented_customization_is_never_silently_discarded(svc, message):
    reply = asyncio.run(Agent(svc).chat(svc.new_session(), message))
    assert reply["intent"] == "clarify_options"
    assert "quote" not in reply


def test_vietnamese_quantity_and_negated_fulfillment(svc):
    token = svc.new_session()
    reply = asyncio.run(Agent(svc).chat(token, "Cho hai ly cà phê sữa mang đi"))
    assert reply["quote"]["total_vnd"] == 60000
    reply = asyncio.run(Agent(svc).chat(token, "Cho cà phê sữa ở bàn 3, không mang đi"))
    assert reply["quote"]["fulfillment"] == "at_table"
    assert reply["quote"]["table_label"] == "Bàn 3"
    reply = asyncio.run(Agent(svc).chat(token, "Không đặt cà phê sữa mang đi"))
    assert "quote" not in reply


@pytest.mark.parametrize("quantity", ["hai mươi", "mười một", "-2", "1.5"])
def test_unsupported_numeric_forms_require_clarification(svc, quantity):
    reply = asyncio.run(Agent(svc).chat(svc.new_session(), f"Cho {quantity} ly cà phê sữa mang đi"))
    assert "quote" not in reply
    assert reply["intent"] == "clarify_quantity"
