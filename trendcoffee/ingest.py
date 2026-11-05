"""Explicit operator-only refresh of the published customer menu; never follows private APIs."""

import json
import re
import subprocess
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .service import ServiceError, now_iso

BRANCH = "ba9355f797"


def normalize_menu(data, source_url):
    if not isinstance(data, dict):
        raise ServiceError("invalid_public_source")
    result = data.get("result")
    if (
        not isinstance(result, dict)
        or result.get("hasNext") is not False
        or not isinstance(result.get("items"), list)
    ):
        raise ServiceError("incomplete_menu_snapshot")
    items = []
    seen = set()
    for menu in result["items"]:
        if not isinstance(menu, dict) or not isinstance(menu.get("menuItems"), list):
            raise ServiceError("malformed_menu_group")
        for entry in menu["menuItems"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("product"), dict):
                raise ServiceError("malformed_menu_item")
            product = entry["product"]
            if type(product.get("isActive")) is not bool:
                raise ServiceError("malformed_menu_product")
            if (
                entry.get("isLocked")
                or product.get("isActive") is not True
                or any(product.get(flag) for flag in ["isHidden", "isGift", "isCustomPrice"])
                or re.search(r"\btest\b", product.get("name", ""), flags=re.I)
            ):
                continue
            if not isinstance(product.get("variants"), list):
                raise ServiceError("malformed_menu_variants")
            for variant in product["variants"]:
                price = variant.get("price")
                if type(price) is not int or price <= 0 or not variant.get("slug"):
                    continue
                if variant["slug"] in seen:
                    raise ServiceError("duplicate_menu_variant")
                seen.add(variant["slug"])
                size = variant.get("size", {}).get("name", "")
                variants = product.get("variants", [])
                name = product["name"] + (f" ({size})" if len(variants) > 1 else "")
                items.append(
                    {
                        "id": variant["slug"],
                        "name": name,
                        "description": product.get("description", ""),
                        "category": product.get("catalog", {}).get("name", "").strip(),
                        "category_id": product.get("catalog", {}).get("slug", ""),
                        "is_top_sell": product.get("isTopSell") is True,
                        "is_new": product.get("isNew") is True,
                        "product_id": product["slug"],
                        "variant_name": size,
                        "branch_id": BRANCH,
                        "menu_item_id": entry.get("slug"),
                        "price_vnd": price,
                        "options": {"size": [size]} if size else {},
                        "source_url": source_url,
                        "verified_at": data.get("timestamp") or now_iso(),
                        "availability": "unknown",
                        "approved": True,
                        "evidence": "public_api",
                    }
                )
    observed = data.get("timestamp") or now_iso()
    prices = [item["price_vnd"] for item in items]
    description = f"Thực đơn công khai vừa kiểm chứng gồm {len(items)} lựa chọn món/biến thể. "
    if prices:
        description += f"Giá niêm yết từ {min(prices):,} đến {max(prices):,} đồng. "
    description += "Đây là bản chụp theo chi nhánh/ngày; tồn món cần xác minh khi đặt."
    return {
        "menu": {"items": items},
        "source_url": source_url,
        "knowledge": [
            {
                "id": "menu_snapshot",
                "title": "Thực đơn công khai đã kiểm chứng",
                "text": description,
                "verified_at": observed,
                "source_url": source_url,
                "approved": True,
                "evidence": "public_api",
            }
        ],
    }


def _public_json(url):
    # Match the public website request transport; no credentials, POSTs or private endpoints.
    response = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "15", url],
        capture_output=True,
        timeout=17,
        check=False,
    )
    if response.returncode:
        raise ServiceError("public_source_unavailable")
    if len(response.stdout) > 2_000_000:
        raise ServiceError("public_source_too_large")
    try:
        data = json.loads(response.stdout)
    except (ValueError, UnicodeError):
        raise ServiceError("invalid_public_source") from None
    return data


def sync_public():
    day = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    url = "https://trendcoffee.net/api/latest/menu/specific/public?" + urlencode(
        {"date": day, "branch": BRANCH, "page": 1}
    )
    bundle = normalize_menu(_public_json(url), url)
    category_url = "https://trendcoffee.net/api/latest/catalogs"
    data = _public_json(category_url)
    if not isinstance(data, dict) or not isinstance(data.get("result"), list):
        raise ServiceError("invalid_menu_categories")
    categories = []
    for row in data["result"]:
        if not isinstance(row, dict):
            raise ServiceError("invalid_menu_categories")
        categories.append(
            {
                "id": row.get("slug"),
                "name": row.get("name"),
                "source_url": category_url,
                "verified_at": data.get("timestamp") or now_iso(),
            }
        )
    bundle["menu"]["categories"] = categories
    return bundle
