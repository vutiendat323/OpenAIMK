"""Spoken menu names resolve only against actual catalog items."""

import json
from pathlib import Path

import pytest

from trendcoffee.menu_matching import match_menu


@pytest.fixture
def items():
    return json.loads(Path("data/trendcoffee-public.json").read_text())["menu"]["items"]


@pytest.mark.parametrize("query", ["Trà Bắc", "TRA BAC", "trà bắc!", "Cho mình 2 ly Trà Bắc nhé"])
def test_exact_catalog_name_resolves_despite_speech_filler(items, query):
    result = match_menu(items, [query])
    assert [item["name"] for item in result["items"]] == ["Trà Bắc"]
    assert result["matches"][0]["resolved_item_ids"] == [result["items"][0]["id"]]
    assert result["requires_clarification"] is False


def test_unique_small_typo_resolves(items):
    result = match_menu(items, ["cafe muois"])
    assert [item["name"] for item in result["items"]] == ["Cà phê muối"]
    assert result["matches"][0]["match_type"] == "fuzzy"
    assert result["requires_clarification"] is False


@pytest.mark.parametrize("query", ["trà bắp miền Bắc", "trà bắp miền Nam", "trà bắp trà Nam"])
def test_uncertain_spoken_variant_suggests_real_tea(items, query):
    result = match_menu(items, [query])
    assert "Trà Bắc" in [item["name"] for item in result["items"]]
    match = result["matches"][0]
    assert match["requires_clarification"] is True
    assert match["resolved_item_ids"] == []
    assert 1 <= len(match["suggestions"]) <= 3
    assert set(match["item_ids"]) <= {item["id"] for item in items}
    assert result["unmatched"] == []


@pytest.mark.parametrize(
    "query",
    ["trà sen", "trà sao hỏa", "cà phê sao hỏa", "nước sao hỏa", "động cơ tên lửa"],
)
def test_generic_beverage_word_does_not_make_unknown_flavor_a_match(items, query):
    result = match_menu(items, [query])
    assert result["items"] == []
    assert result["unmatched"] == [query]
    assert result["matches"][0]["resolved_item_ids"] == []


def test_competing_near_names_require_clarification():
    items = [{"id": "north", "name": "Trà Bắc"}, {"id": "silver", "name": "Trà Bạc"}]
    result = match_menu(items, ["trà bát"])
    assert {item["id"] for item in result["items"]} == {"north", "silver"}
    assert result["requires_clarification"] is True
    assert result["matches"][0]["resolved_item_ids"] == []


def test_exact_name_beats_close_name():
    items = [{"id": "salt", "name": "Cà phê muối"}, {"id": "smell", "name": "Cà phê mùi"}]
    result = match_menu(items, ["ca phe mui"])
    assert [item["id"] for item in result["items"]] == ["smell"]
    assert result["requires_clarification"] is False


def test_exact_normalized_names_with_different_ids_are_ambiguous():
    items = [{"id": "north", "name": "Trà Bắc"}, {"id": "silver", "name": "Trà Bạc"}]
    result = match_menu(items, ["trà bắc"])
    assert {item["id"] for item in result["items"]} == {"north", "silver"}
    assert result["requires_clarification"] is True
    assert result["matches"][0]["resolved_item_ids"] == []


def test_generic_keyword_suggestions_are_bounded(items):
    result = match_menu(items, ["trà"])
    assert 1 <= len(result["items"]) <= 3
    assert result["requires_clarification"] is True
    assert result["matches"][0]["resolved_item_ids"] == []


def test_exact_catalog_name_can_contain_a_list_separator(items):
    result = match_menu(items, ["Bánh Croissant Ham & Cheese"])
    assert [item["name"] for item in result["items"]] == ["Bánh Croissant Ham & Cheese"]
    assert result["requires_clarification"] is False


def test_every_actual_catalog_name_round_trips_as_an_exact_match(items):
    for item in items:
        result = match_menu(items, [item["name"]])
        assert [found["id"] for found in result["items"]] == [item["id"]], item["name"]
        assert result["requires_clarification"] is False, item["name"]


def test_ambiguous_exact_name_in_a_list_keeps_other_resolved_drinks():
    items = [
        {"id": "north", "name": "Trà Bắc"},
        {"id": "silver", "name": "Trà Bạc"},
        {"id": "milk", "name": "Cà phê sữa"},
    ]
    result = match_menu(items, ["2 trà bắc 1 cà phê sữa"])
    assert result["matches"][0]["resolved_item_ids"] == ["milk"]
    assert {s["item_id"] for s in result["matches"][0]["suggestions"]} == {"north", "silver"}


def test_longest_exact_names_do_not_add_embedded_drinks(items):
    result = match_menu(items, ["Matcha latte và cà phê sữa"])
    assert {item["name"] for item in result["items"]} == {"Matcha latte", "Cà phê sữa"}
    assert result["requires_clarification"] is False


@pytest.mark.parametrize(
    "queries",
    [
        ["cà phê muối cà phê sữa trà bắc"],
        ["1 cafe muoi, 2 cafe sua va 3 tra bac"],
        ["1 cà phê muối", "2 cà phê sữa", "3 trà bắc"],
    ],
)
def test_all_drinks_in_spoken_lists_and_batch_queries_are_preserved(items, queries):
    result = match_menu(items, queries)
    assert {item["name"] for item in result["items"]} == {"Cà phê muối", "Cà phê sữa", "Trà Bắc"}
    assert [match["query"] for match in result["matches"]] == queries
    assert result["unmatched"] == []
    assert result["requires_clarification"] is False


def test_batch_keeps_exact_drinks_while_suggesting_uncertain_one(items):
    result = match_menu(items, ["2 cà phê sữa", "1 trà bắp miền Nam", "nước sao hỏa"])
    by_name = {item["name"]: item for item in result["items"]}
    assert set(by_name) == {"Cà phê sữa", "Trà Bắc"}
    assert result["matches"][0]["resolved_item_ids"] == [by_name["Cà phê sữa"]["id"]]
    assert result["matches"][1]["resolved_item_ids"] == []
    assert result["unmatched"] == ["nước sao hỏa"]


def test_one_combined_query_keeps_exact_drink_and_fuzzy_candidate(items):
    result = match_menu(items, ["2 cà phê sữa 1 trà bắp miền Nam"])
    assert {item["name"] for item in result["items"]} == {"Cà phê sữa", "Trà Bắc"}
    assert len(result["matches"][0]["resolved_item_ids"]) == 1
    assert result["requires_clarification"] is True


def test_empty_query_returns_full_catalog_without_clarification(items):
    result = match_menu(items, [])
    assert result["items"] == items
    assert result["matches"] == []
    assert result["requires_clarification"] is False
