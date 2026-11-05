import pytest

from trendcoffee.ingest import normalize_menu
from trendcoffee.service import ServiceError


def raw(items=None, has_next=False):
    return {
        "timestamp": "2026-10-16T15:27:55Z",
        "result": {"hasNext": has_next, "items": [{"slug": "menu", "menuItems": items or []}]},
    }


def product(**overrides):
    p = {
        "name": "Cà phê đen",
        "slug": "product",
        "isActive": True,
        "isHidden": False,
        "isGift": False,
        "isCustomPrice": False,
        "catalog": {"name": "cà phê"},
        "variants": [{"slug": "variant", "price": 35000, "size": {"name": "tiêu chuẩn"}}],
    }
    p.update(overrides)
    return {"slug": "menu-item", "isLocked": False, "product": p}


def test_refresh_filters_non_customer_products_and_preserves_provenance():
    bundle = normalize_menu(
        raw(
            [
                product(),
                product(isActive=False),
                product(isGift=True),
                product(isCustomPrice=True),
                product(isHidden=True),
            ]
        ),
        "https://trendcoffee.net/api/latest/menu/specific/public?date=2026-10-16&branch=test&page=1",
    )
    assert len(bundle["menu"]["items"]) == 1
    item = bundle["menu"]["items"][0]
    assert item["price_vnd"] == 35000
    assert item["availability"] == "unknown"
    assert item["verified_at"] == "2026-10-16T15:27:55Z"
    assert item["options"] == {"size": ["tiêu chuẩn"]}


def test_refresh_rejects_incomplete_or_malformed_snapshots():
    with pytest.raises(ServiceError):
        normalize_menu(raw([product()], has_next=True), "https://trendcoffee.net/")
    with pytest.raises(ServiceError):
        normalize_menu({"statusCode": 401}, "https://trendcoffee.net/")


def test_concurrent_http_benchmark_reports_sample_count_and_percentiles():
    from trendcoffee.benchmark import run

    report = run(requests=20, concurrency=4)
    assert report["requests"] == 20
    assert report["errors"] == 0
    assert report["p95_ms"] >= report["p50_ms"]
    assert report["transport"] == "in_process_http"
    assert report["concurrency"] == 4


def test_refresh_rejects_missing_nested_menu_items():
    with pytest.raises(ServiceError):
        normalize_menu({"result": {"hasNext": False, "items": [{}]}}, "https://trendcoffee.net/")
