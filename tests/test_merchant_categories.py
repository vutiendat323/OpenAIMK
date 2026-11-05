"""Merchant categories/flags survive ingestion and drive UI without invented groups."""

import copy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from test_ingest import product, raw

from trendcoffee.api import create_app
from trendcoffee.ingest import normalize_menu, sync_public
from trendcoffee.service import ServiceError


@pytest.fixture
def category_catalog(svc):
    bundle = normalize_menu(
        raw(
            [
                product(
                    name="Cà phê sữa",
                    catalog={"slug": "coffee", "name": "cà phê"},
                    isTopSell=True,
                    isNew=False,
                ),
                product(
                    name="Trà Bắc",
                    slug="tea-product",
                    catalog={"slug": "tea", "name": "món trà"},
                    isNew=True,
                    variants=[{"slug": "tea", "price": 40000}],
                ),
                product(
                    name="Bánh Tiramisu",
                    slug="cake-product",
                    catalog={"slug": "cake", "name": "món bánh "},
                    variants=[{"slug": "cake", "price": 39000}],
                ),
            ]
        ),
        "https://trendcoffee.net/api/latest/menu/specific/public",
    )
    bundle["menu"]["categories"] = [
        {"id": "food", "name": "món ăn"},
        {"id": "coffee", "name": "cà phê"},
        {"id": "cake", "name": "món bánh "},
        {"id": "tea", "name": "món trà"},
        {"id": "seasonal", "name": "nước theo mùa"},
    ]
    for category in bundle["menu"]["categories"]:
        category.update(
            source_url="https://trendcoffee.net/api/latest/catalogs",
            verified_at="2026-10-27T00:00:00Z",
        )
    svc.ingest(bundle)
    return svc


def test_product_catalog_ids_and_merchant_flags_are_not_lost():
    result = normalize_menu(
        raw([product(catalog={"slug": "coffee", "name": "cà phê"}, isTopSell=True, isNew=True)]),
        "https://trendcoffee.net/menu",
    )["menu"]["items"][0]
    assert result["category_id"] == "coffee"
    assert result["is_top_sell"] is True and result["is_new"] is True


def test_api_includes_all_merchant_categories_in_original_order_even_when_empty(category_catalog):
    with TestClient(create_app(service=category_catalog)) as client:
        data = client.get("/api/menu").json()
        assert [(c["id"], c["name"]) for c in data["categories"]] == [
            ("food", "món ăn"),
            ("coffee", "cà phê"),
            ("cake", "món bánh"),
            ("tea", "món trà"),
            ("seasonal", "nước theo mùa"),
        ]
        assert len(data["items"]) == 3
        # Searching the menu does not erase categories that have no matching items.
        assert client.get("/api/menu?q=Cà phê sữa").json()["categories"] == data["categories"]


def test_category_replacement_removes_retired_groups_without_changing_products(category_catalog):
    updated = {"items": category_catalog.menu(), "categories": []}
    with TestClient(create_app(service=category_catalog)) as client:
        first = client.get("/api/menu").json()
        updated["categories"] = [dict(first["categories"][1], name="Cà phê mới")]
        category_catalog.ingest({"menu": updated})
        current = client.get("/api/menu").json()
        assert [(c["id"], c["name"]) for c in current["categories"]] == [("coffee", "Cà phê mới")]
        assert len(current["items"]) == 3


def test_invalid_category_refresh_rolls_back_the_previous_snapshot(category_catalog):
    with TestClient(create_app(service=category_catalog)) as client:
        before = client.get("/api/menu").json()
        categories = copy.deepcopy(before["categories"])
        categories.append(dict(categories[0]))
        with pytest.raises(ServiceError, match="invalid_menu_categories"):
            category_catalog.ingest({"menu": {"items": [], "categories": categories}})
        after = client.get("/api/menu").json()
        assert after["categories"] == before["categories"]
        assert after["items"] == before["items"]


def test_public_sync_fetches_the_actual_catalog_endpoint(monkeypatch):
    urls = []

    def fetch(command, **kwargs):
        url = command[-1]
        urls.append(url)
        data = (
            {"timestamp": "2026-10-27T00:00:00Z", "result": [{"slug": "tea", "name": "món trà"}]}
            if url.endswith("/catalogs")
            else raw([product()])
        )
        return SimpleNamespace(returncode=0, stdout=json.dumps(data).encode())

    monkeypatch.setattr("trendcoffee.ingest.subprocess.run", fetch)
    bundle = sync_public()
    assert "https://trendcoffee.net/api/latest/catalogs" in urls
    assert [(c["id"], c["name"]) for c in bundle["menu"]["categories"]] == [("tea", "món trà")]


def test_legacy_snapshots_use_real_category_names_instead_of_a_fixed_ui_list(svc):
    items = svc.menu()
    for item in items:
        item["category"] = "Danh mục merchant mới"
    svc.ingest({"menu": {"items": items}})
    with TestClient(create_app(service=svc)) as client:
        data = client.get("/api/menu").json()
        assert [c["name"] for c in data["categories"]] == ["Danh mục merchant mới"]
