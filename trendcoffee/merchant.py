"""Trend Coffee's published guest checkout contract; never manufactures payment QR data."""

import base64
import os
import re
import time
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

import httpx

from .service import ServiceError, normalize, timestamp

BASE = "https://trendcoffee.net/api/latest"
BRANCH = "ba9355f797"
# Leads the merchant order description, which the merchant prints on the invoice
# (user decision 2026-11-04). Not verified on paper yet.
AI_ORDER_NOTICE = (
    "AI ORDER\n"
    "Quý khách vui lòng đợi khoảng 15 phút và nhận món tại quầy thanh toán. "
    "Cảm ơn quý khách!"
)


# With a pickup card (user decisions 2026-11-06) the notice names the card, and the table or
# takeaway, so staff can match the order to the card they make vibrate.
CARD_NOTICE = "Khi thẻ rung, mời quý khách đến quầy nhận món. Cảm ơn quý khách!"


def card_notice(order):
    card = "THẺ RUNG SỐ " + str(order["vibrating_card"])
    if order.get("fulfillment") == "takeaway":
        card += " · Mang đi"
    elif order.get("table_label"):
        card += " · Bàn " + str(order["table_label"])
    return "AI ORDER\n" + card + "\n" + CARD_NOTICE


def order_description(order, *, legacy=False):
    """The kiosk's merchant description; `legacy` is the form used before the notice."""
    if legacy:
        notice = ""
    elif order.get("vibrating_card"):
        notice = card_notice(order) + "\n"
    else:
        notice = AI_ORDER_NOTICE + "\n"
    text = notice + "Kiosk " + order["id"]
    return text + ("\n" + order["order_note"] if order.get("order_note") else "")


class MerchantError(ServiceError):
    def __init__(self, code, *, uncertain=False):
        super().__init__(code, 502)
        self.uncertain = uncertain


def from_environment():
    return MerchantClient() if os.environ.get("TREND_MERCHANT_ENABLED") == "1" else None


def table_key(label):
    value = normalize(label).strip().removeprefix("ban ").strip()
    return str(int(value)) if value.isascii() and value.isdigit() else value


class MerchantClient:
    def __init__(self, *, transport=None):
        self.transport = transport

    def _request(self, method, path, data=None):
        try:
            with httpx.Client(
                timeout=4, transport=self.transport, follow_redirects=False
            ) as client:
                with client.stream(method, BASE + path, json=data) as response:
                    if not 200 <= response.status_code < 300:
                        raise MerchantError(
                            "merchant_rejected", uncertain=response.status_code >= 500
                        )
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 2_000_000:
                            raise MerchantError("merchant_invalid_response", uncertain=True)
                        chunks.append(chunk)
                    import json

                    body = json.loads(b"".join(chunks))
                    if not isinstance(body, dict) or "result" not in body:
                        raise MerchantError("merchant_invalid_response", uncertain=True)
                    return body["result"]
        except httpx.HTTPError:
            raise MerchantError("merchant_unreachable", uncertain=True) from None
        except (ValueError, TypeError):
            raise MerchantError("merchant_invalid_response", uncertain=True) from None

    def tables(self, table_label=None):
        """Read current public table state in merchant order; selecting is not reserving."""
        if table_label is not None and (
            not isinstance(table_label, str) or not 1 <= len(table_label.strip()) <= 50
        ):
            raise ServiceError("invalid_table_label")
        remote = self._request("GET", "/tables?branch=" + BRANCH)
        if not isinstance(remote, list):
            raise MerchantError("merchant_invalid_response")
        tables, ids, names = [], set(), set()
        for row in remote:
            if not isinstance(row, dict):
                raise MerchantError("merchant_invalid_response")
            name, ident = row.get("name"), row.get("slug")
            status, location = row.get("status", "unknown"), row.get("location") or ""
            if (
                not isinstance(name, str)
                or not 1 <= len(name.strip()) <= 50
                or not isinstance(ident, str)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", ident)
                or ident in ids
                or table_key(name) in names
                or not isinstance(status, str)
                or not 1 <= len(status) <= 50
                or not isinstance(location, str)
                or len(location) > 200
            ):
                raise MerchantError("merchant_invalid_response")
            ids.add(ident)
            names.add(table_key(name))
            tables.append(
                {
                    "id": ident,
                    "name": name.strip(),
                    "status": status,
                    "available": status == "available",
                    "location": location,
                }
            )
        if table_label is not None:
            tables = [t for t in tables if table_key(t["name"]) == table_key(table_label)]
        available = [t for t in tables if t["available"]]
        from .service import now_iso

        return {
            "source": "merchant_api",
            "source_url": BASE + "/tables?branch=" + BRANCH,
            "branch": BRANCH,
            "live": True,
            "fetched_at": now_iso(),
            "tables": tables,
            "total": len(tables),
            "available_count": len(available),
            "first_available": available[0] if available else None,
            "reservation_created": False,
        }

    def create(self, order, catalog):
        table = ""
        if order["fulfillment"] == "at_table":
            tables = self.tables(order["table_label"])["tables"]
            if len(tables) != 1:
                raise MerchantError("merchant_table_not_found")
            table = tables[0]["id"]
        for line in order["lines"]:
            item = catalog[line["item_id"]]
            if item.get("branch_id", BRANCH) != BRANCH or any(
                k != "size" or v != item.get("variant_name") for k, v in line["options"].items()
            ):
                raise MerchantError("merchant_unsupported_options")
        return self._request(
            "POST",
            "/orders/public",
            {
                "type": "take-out" if order["fulfillment"] == "takeaway" else "at-table",
                "timeLeftTakeOut": 0,
                "deliveryTo": "",
                "deliveryPhone": "",
                "table": table,
                "branch": BRANCH,
                "owner": "",
                "approvalBy": "",
                "orderItems": [
                    {
                        "quantity": line["quantity"],
                        "variant": line["item_id"],
                        "promotion": None,
                        "note": line.get("note", ""),
                    }
                    for line in order["lines"]
                ],
                "voucher": None,
                "description": order_description(order),
            },
        )

    def reference(self, remote):
        slug = remote.get("slug") if isinstance(remote, dict) else None
        if not isinstance(slug, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", slug):
            raise MerchantError("merchant_invalid_response", uncertain=True)
        return slug

    def validate(self, remote, order):
        if self.reference(remote) != order["merchant"]["order_slug"]:
            raise MerchantError("merchant_order_mismatch")
        branch = remote.get("branch")
        if isinstance(branch, dict):
            branch = branch.get("slug")
        branch_matches = branch == BRANCH
        if "branch" not in remote:
            # Guest order responses omit branch; bind them to our echoed creation request.
            # Orders placed before the AI ORDER notice still carry the legacy form.
            expected = (order_description(order), order_description(order, legacy=True))
            branch_matches = remote.get("description") in expected and remote.get("type") == (
                "take-out" if order["fulfillment"] == "takeaway" else "at-table"
            )
        expected = Counter()
        actual = Counter()
        for line in order["lines"]:
            expected[line["item_id"]] += line["quantity"]
        lines = remote.get("orderItems")
        if not isinstance(lines, list):
            raise MerchantError("merchant_order_mismatch")
        for line in lines:
            if not isinstance(line, dict):
                raise MerchantError("merchant_order_mismatch")
            variant = line.get("variant", {})
            ident = variant.get("slug") if isinstance(variant, dict) else variant
            qty = line.get("quantity")
            if not isinstance(ident, str) or type(qty) is not int or qty <= 0:
                raise MerchantError("merchant_order_mismatch")
            actual[ident] += qty
        if (
            not branch_matches
            or type(remote.get("subtotal")) is not int
            or remote["subtotal"] != order["total_vnd"]
            or actual != expected
        ):
            raise MerchantError("merchant_order_mismatch")

    def fetch(self, order):
        return self._request("GET", "/orders/" + order["merchant"]["order_slug"])

    def initiate(self, order):
        return self._request(
            "POST",
            "/payment/initiate/public",
            {
                "orderSlug": order["merchant"]["order_slug"],
                "paymentMethod": "bank-transfer",
            },
        )

    def _image(self, value):
        if not isinstance(value, str) or not value or len(value) > 1_500_000:
            raise MerchantError("merchant_invalid_qr")
        if value.startswith("https://"):
            try:
                url = urlparse(value)
                port = url.port
            except ValueError:
                raise MerchantError("merchant_invalid_qr") from None
            if (
                url.hostname
                not in {"trendcoffee.net", "trendcoffee.s3.ap-southeast-1.amazonaws.com"}
                or port not in (None, 443)
                or url.username
                or url.password
            ):
                raise MerchantError("merchant_invalid_qr")
            try:
                with httpx.Client(
                    timeout=4, transport=self.transport, follow_redirects=False
                ) as client:
                    with client.stream("GET", value) as response:
                        if response.status_code != 200:
                            raise MerchantError("merchant_invalid_qr")
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > 1_000_000:
                                raise MerchantError("merchant_invalid_qr")
                            chunks.append(chunk)
                        raw = b"".join(chunks)
            except httpx.HTTPError:
                raise MerchantError("merchant_invalid_qr") from None
        else:
            match = re.fullmatch(r"data:image/(png|jpeg);base64,([A-Za-z0-9+/=\r\n]+)", value)
            if not match:
                raise MerchantError("merchant_invalid_qr")
            try:
                raw = base64.b64decode(match[2], validate=True)
            except ValueError:
                raise MerchantError("merchant_invalid_qr") from None
        kind = (
            "png"
            if raw.startswith(b"\x89PNG\r\n\x1a\n")
            else "jpeg"
            if raw.startswith(b"\xff\xd8\xff")
            else None
        )
        if kind is None or len(raw) > 1_000_000:
            raise MerchantError("merchant_invalid_qr")
        return f"data:image/{kind};base64," + base64.b64encode(raw).decode()

    def payment(self, remote, order):
        self.validate(remote, order)
        created = remote.get("createdAt") or order["created_at"]
        if not isinstance(created, str):
            raise MerchantError("merchant_invalid_response")
        try:
            created_at = timestamp(created)
        except (ValueError, AttributeError):
            try:
                created_at = datetime.strptime(
                    created.split(" (")[0], "%a %b %d %Y %H:%M:%S GMT%z"
                ).timestamp()
            except ValueError:
                raise MerchantError("merchant_invalid_response") from None
        expires = min(created_at, timestamp(order["created_at"])) + 900
        result = {
            "order_id": order["id"],
            "merchant_order_id": order["merchant"]["order_slug"],
            "amount_vnd": order["total_vnd"],
            "expires_at": expires,
            "status": "pending",
            "qr_image": None,
            "source": "merchant",
            "payment_connected": True,
        }
        payment = remote.get("payment") or {}
        if not isinstance(payment, dict):
            raise MerchantError("merchant_invalid_response")
        state = remote.get("status", "")
        if not isinstance(state, str):
            raise MerchantError("merchant_invalid_response")
        if state in {"cancelled", "failed"} or payment.get("statusCode") == "cancelled":
            result["status"] = "cancelled"
        elif state == "paid" or payment.get("statusCode") == "completed":
            if payment.get("amount") != order["total_vnd"]:
                raise MerchantError("merchant_payment_mismatch")
            result["status"] = "paid"
        elif time.time() >= expires:
            result["status"] = "expired"
        elif payment.get("qrCode"):
            if (
                payment.get("amount") != order["total_vnd"]
                or payment.get("paymentMethod") != "bank-transfer"
            ):
                raise MerchantError("merchant_payment_mismatch")
            result["qr_image"] = self._image(payment["qrCode"])
        return result

    def invoice_pdf(self, remote, order):
        """Official invoice only after validated merchant completion; no invented receipt."""
        verified = self.payment(remote, order)
        payment = remote.get("payment") or {}
        if (
            verified["status"] != "paid"
            or remote.get("status") not in {"paid", "completed"}
            or payment.get("statusCode") != "completed"
            or payment.get("statusMessage") != "completed"
        ):
            return None
        invoice = remote.get("invoice")
        if invoice is None:
            return None
        if (
            not isinstance(invoice, dict)
            or not isinstance(invoice.get("slug"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", invoice["slug"])
        ):
            raise MerchantError("merchant_invoice_mismatch")
        try:
            with httpx.Client(
                timeout=10, transport=self.transport, follow_redirects=False
            ) as client:
                with client.stream(
                    "POST",
                    BASE + "/invoice/export/public",
                    json={"order": order["merchant"]["order_slug"]},
                    headers={"Accept": "application/pdf"},
                ) as response:
                    if (
                        response.status_code != 200
                        or response.headers.get("content-type", "").split(";")[0]
                        != "application/pdf"
                    ):
                        raise MerchantError("merchant_invoice_unavailable")
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 5 * 1024 * 1024:
                            raise MerchantError("merchant_invoice_invalid")
            if not data.startswith(b"%PDF-"):
                raise MerchantError("merchant_invoice_invalid")
            return invoice["slug"], bytes(data)
        except httpx.HTTPError:
            raise MerchantError("merchant_invoice_unavailable") from None
