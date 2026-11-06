"""Business rules shared by HTTP, MCP and the local customer agent."""

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

from .menu_matching import match_menu
from .store import Store


class ServiceError(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code, self.status = code, status


def normalize(value):
    value = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    return "".join(c for c in value if unicodedata.category(c) != "Mn")


def now_iso():
    return datetime.now(UTC).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# Pickup cards (user decisions 2026-11-06): every new order takes one of 16 cards, rotating
# 1..16; staff make the card vibrate by hand. The number moves on only past a PAID order: an
# unpaid order, even one whose QR is still valid, leaves the number where it is, so the next
# order gets the same card. Local-queue orders (no merchant payment) keep the number they got.
CARD_COUNT = 16


def _next_card(db):
    """The card after the latest paid order, inside the caller's write transaction."""
    rows = db.execute(
        "SELECT data FROM orders WHERE json_extract(data,'$.vibrating_card') IS NOT NULL"
        " ORDER BY rowid DESC"
    )
    for (data,) in rows:
        order = json.loads(data)
        if order.get("payment_status") == "paid" or "merchant" not in order:
            return order["vibrating_card"] % CARD_COUNT + 1
    return 1


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


class Service:
    catalog_max_age = 24 * 3600

    def __init__(self, path, merchant=None, printer=None):
        self.store = Store(path)
        self.merchant = merchant
        from .invoices import InvoicePrinter
        from .printer import CupsPrinter

        queue = os.environ.get("TREND_PRINT_QUEUE", "")
        if printer is None and queue:
            printer = CupsPrinter(queue)
        self.invoices = InvoicePrinter(self, printer) if printer else None
        # Called as listener(session_id, order), from any thread, once per order when a
        # merchant-verified payment first marks it paid (QR poll, invoice worker or a tool).
        self.paid_listeners = []

    @staticmethod
    def session_id(token):
        return hashlib.sha256(str(token).encode()).hexdigest()

    def _session(self, db, token):
        sid = self.session_id(token)
        row = db.execute("SELECT expires FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row or row["expires"] < time.time():
            raise ServiceError("invalid_session", 401)
        return sid

    def new_session(self):
        token = secrets.token_urlsafe(32)
        sid = hashlib.sha256(token.encode()).hexdigest()
        with self.store.connect(write=True) as db:
            # Expired guest data is removed on new-session creation, at most daily lifetime.
            expired = [
                r[0] for r in db.execute("SELECT id FROM sessions WHERE expires<?", (time.time(),))
            ]
            for old in expired:
                for table in ["events", "handoffs", "orders", "quotes", "working", "memory"]:
                    db.execute(f"DELETE FROM {table} WHERE session=?", (old,))
                db.execute("DELETE FROM sessions WHERE id=?", (old,))
            db.execute("INSERT INTO sessions VALUES (?,?)", (sid, time.time() + 30 * 86400))
        return token

    def ingest(self, bundle):
        """Operator-only import of curated source data; never a customer tool."""
        with self.store.connect(write=True) as db:
            for doc in bundle.get("knowledge", []):
                if not all(
                    doc.get(k) for k in ["id", "title", "text", "source_url", "verified_at"]
                ):
                    raise ServiceError("invalid_knowledge")
                if not doc["source_url"].startswith("https://trendcoffee.net/"):
                    raise ServiceError("untrusted_source")
                doc = dict(doc)
                verified = timestamp(doc["verified_at"])
                if verified > time.time() + 300:
                    raise ServiceError("future_evidence")
                maximum = verified + (86400 if doc["id"] == "menu_snapshot" else 30 * 86400)
                expires = (
                    min(timestamp(doc["expires_at"]), maximum) if doc.get("expires_at") else maximum
                )
                doc["expires_at"] = datetime.fromtimestamp(expires, UTC).isoformat()
                db.execute(
                    "INSERT OR REPLACE INTO knowledge VALUES (?,?,?,?)",
                    (doc["id"], encode(doc), doc.get("approved") is True, expires),
                )
                db.execute("DELETE FROM knowledge_fts WHERE id=?", (doc["id"],))
                db.execute(
                    "INSERT INTO knowledge_fts VALUES (?,?)",
                    (doc["id"], normalize(doc["title"] + " " + doc["text"])),
                )
            if "menu" in bundle:
                items = bundle["menu"].get("items", [])
                db.execute("DELETE FROM menu")
                db.execute("DELETE FROM menu_categories")
                categories = bundle["menu"].get("categories", [])
                if not isinstance(categories, list):
                    raise ServiceError("invalid_menu_categories")
                seen = set()
                for position, category in enumerate(categories):
                    if not isinstance(category, dict):
                        raise ServiceError("invalid_menu_categories")
                    category = {
                        "source_url": bundle["menu"].get("source_url", ""),
                        "verified_at": bundle["menu"].get("verified_at"),
                        **category,
                    }
                    if (
                        not isinstance(category.get("id"), str)
                        or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", category["id"])
                        or category["id"] in seen
                        or not isinstance(category.get("name"), str)
                        or not 1 <= len(category["name"].strip()) <= 200
                        or not isinstance(category.get("source_url"), str)
                        or not category["source_url"].startswith("https://trendcoffee.net/")
                        or not isinstance(category.get("verified_at"), str)
                    ):
                        raise ServiceError("invalid_menu_categories")
                    timestamp(category["verified_at"])
                    seen.add(category["id"])
                    category = {**category, "name": category["name"].strip()}
                    db.execute(
                        "INSERT INTO menu_categories VALUES (?,?,?)",
                        (category["id"], position, encode(category)),
                    )
                for item in items:
                    price = item.get("price_vnd")
                    if (
                        type(price) is not int
                        or not 0 <= price <= 10000000
                        or not item.get("id")
                        or not item.get("name")
                        or not item.get("source_url", "").startswith("https://trendcoffee.net/")
                        or item.get("availability") not in ["unknown", "available", "sold_out"]
                    ):
                        raise ServiceError("invalid_catalog_item")
                    timestamp(item["verified_at"])
                    db.execute("INSERT INTO menu VALUES (?,?)", (item["id"], encode(item)))

    def search(self, query, limit=4):
        tokens = re.findall(r"[a-z0-9]+", normalize(query))[:24]
        if not tokens:
            return []
        match = " OR ".join('"' + token + '"' for token in tokens)
        with self.store.connect() as db:
            rows = db.execute(
                """SELECT k.data FROM knowledge_fts f
                JOIN knowledge k ON k.id=f.id WHERE knowledge_fts MATCH ?
                AND k.approved=1 AND k.expires>?
                ORDER BY bm25(knowledge_fts) LIMIT ?""",
                (match, time.time(), min(max(limit, 1), 8)),
            )
            return [json.loads(row[0]) for row in rows]

    def menu(self, query=""):
        return self.menu_search(query)["items"]

    def tables(self, table_label=None):
        if not self.merchant:
            raise ServiceError("live_tables_unavailable", 503)
        return self.merchant.tables(table_label)

    def resolve_table(self, table_label=None):
        if table_label is not None and (
            not isinstance(table_label, str) or len(table_label.strip()) > 50
        ):
            raise ServiceError("invalid_table_label")
        label = (table_label or "").strip()
        if not self.merchant:
            if not label:
                raise ServiceError("table_required")
            return label
        result = self.tables(label or None)
        if label:
            if not result["tables"]:
                raise ServiceError("merchant_table_not_found", 404)
            return result["tables"][0]["name"]
        if not result["first_available"]:
            raise ServiceError("no_available_tables", 409)
        return result["first_available"]["name"]

    def menu_search(self, query="", queries=None, *, item_ids=None):
        with self.store.connect() as db:
            db.execute("BEGIN")  # Read products and category metadata from one snapshot.
            items = [json.loads(row[0]) for row in db.execute("SELECT data FROM menu ORDER BY id")]
            categories = [
                json.loads(row[0])
                for row in db.execute("SELECT data FROM menu_categories ORDER BY position")
            ]
        if not categories:
            # Legacy/local snapshots have no category list; retain their actual product groups.
            groups = {}
            for item in items:
                name = item.get("category", "").strip()
                if name:
                    ident = item.get("category_id") or name
                    groups.setdefault(ident, {"id": ident, "name": name})
            categories = list(groups.values())
        for item in items:
            item["stale"] = time.time() - timestamp(item["verified_at"]) > self.catalog_max_age
        if item_ids is not None:
            if (
                not isinstance(item_ids, list)
                or not 1 <= len(item_ids) <= 20
                or any(not isinstance(ident, str) for ident in item_ids)
            ):
                raise ServiceError("invalid_menu_selection")
            by_id = {item["id"]: item for item in items}
            if any(ident not in by_id for ident in item_ids):
                raise ServiceError("item_not_found", 404)
            return {
                **match_menu([], []),
                "categories": categories,
                "items": [by_id[ident] for ident in dict.fromkeys(item_ids)],
                "selection": "agent",
            }
        terms = ([query] if query.strip() else []) + (queries or [])
        if not terms:
            return {**match_menu(items, []), "categories": categories}
        if len(terms) > 20 or any(not isinstance(q, str) or len(q) > 500 for q in terms):
            raise ServiceError("invalid_menu_queries")

        result = match_menu(items, terms)
        result["categories"] = categories
        if result["requires_clarification"]:
            # An unmatched phrase can be a preference rather than a product name.
            # Let the model inspect the full source instead of inferring absence.
            result.update(catalog=items, requires_catalog_review=True)
        return result

    def remember(self, token, key, value, consent=False):
        if consent is not True:
            raise ServiceError("consent_required")
        if (
            key not in ["taste", "preferred_name"]
            or not isinstance(value, str)
            or not 0 < len(value.strip()) <= 200
        ):
            raise ServiceError("invalid_preference")
        with self.store.connect(write=True) as db:
            sid = self._session(db, token)
            db.execute("INSERT OR REPLACE INTO memory VALUES (?,?,?)", (sid, key, value.strip()))
        return {"saved": True, "scope": "this_guest_session", "expires_in_days_at_most": 30}

    def memory(self, token):
        with self.store.connect() as db:
            sid = self._session(db, token)
            return dict(db.execute("SELECT key,value FROM memory WHERE session=?", (sid,)))

    def forget(self, token):
        with self.store.connect(write=True) as db:
            sid = self._session(db, token)
            db.execute("DELETE FROM memory WHERE session=?", (sid,))
        return {"deleted": True}

    def _lines(self, db, lines):
        if not isinstance(lines, list) or not 1 <= len(lines) <= 20:
            raise ServiceError("invalid_lines")
        result = []
        for line in lines:
            if not isinstance(line, dict):
                raise ServiceError("invalid_lines")
            quantity = line.get("quantity")
            if type(quantity) is not int or not 1 <= quantity <= 100:
                raise ServiceError("invalid_quantity")
            row = db.execute("SELECT data FROM menu WHERE id=?", (line.get("item_id"),)).fetchone()
            if not row:
                raise ServiceError("item_not_found")
            item = json.loads(row[0])
            if time.time() - timestamp(item["verified_at"]) > self.catalog_max_age:
                raise ServiceError("stale_catalog")
            if item["availability"] == "sold_out":
                raise ServiceError("sold_out")
            options = line.get("options", {})
            if not isinstance(options, dict) or any(
                key not in item.get("options", {}) or value not in item["options"][key]
                for key, value in options.items()
            ):
                raise ServiceError("invalid_options")
            note = line.get("note", "")
            if not isinstance(note, str) or len(note) > 300:
                raise ServiceError("invalid_note")
            note = note.strip()
            result.append(
                {
                    "item_id": item["id"],
                    "name": item["name"],
                    "quantity": quantity,
                    "options": options,
                    "note": note,
                    "unit_price_vnd": item["price_vnd"],
                    "subtotal_vnd": item["price_vnd"] * quantity,
                    "catalog_fingerprint": hashlib.sha256(row[0].encode()).hexdigest(),
                }
            )
        if sum(line["quantity"] for line in result) > 100:
            raise ServiceError("quantity_limit")
        return result

    def quote(
        self,
        token,
        lines,
        fulfillment=None,
        table_label=None,
        *,
        checkout_id=None,
        order_note="",
    ):
        if not isinstance(order_note, str) or len(order_note) > 1000:
            raise ServiceError("invalid_note")
        order_note = order_note.strip()
        if fulfillment is None:
            raise ServiceError("fulfillment_required")
        auto_table = fulfillment == "at_table" and (
            table_label is None or isinstance(table_label, str) and not table_label.strip()
        )
        if auto_table:
            # Reuse the durable selection on a lost-response retry, even if the merchant is down.
            previous = None
            with self.store.connect() as db:
                sid = self._session(db, token)
                if checkout_id:
                    quote_id = hashlib.sha256((sid + ":" + checkout_id).encode()).hexdigest()
                    row = db.execute(
                        "SELECT data FROM quotes WHERE id=? AND session=?", (quote_id, sid)
                    ).fetchone()
                    previous = json.loads(row[0]) if row else None
            if previous:
                if not previous.get("table_auto_selected"):
                    raise ServiceError("checkout_changed", 409)
                table_label = previous["table_label"]
            else:
                table_label = self.resolve_table()
        elif fulfillment == "at_table" and (
            not isinstance(table_label, str) or not 1 <= len(table_label.strip()) <= 50
        ):
            raise ServiceError("table_required")
        if fulfillment not in ["takeaway", "at_table"]:
            raise ServiceError("delivery_quote_requires_live_route")
        with self.store.connect(write=True) as db:
            sid = self._session(db, token)
            quote_id = (
                hashlib.sha256((sid + ":" + checkout_id).encode()).hexdigest()
                if checkout_id
                else uuid4().hex
            )
            if checkout_id:
                row = db.execute(
                    "SELECT data FROM quotes WHERE id=? AND session=?", (quote_id, sid)
                ).fetchone()
                if row:
                    previous = json.loads(row[0])
                    fields = ("item_id", "quantity", "options", "note")
                    requested = []
                    for line in lines:
                        if not isinstance(line, dict):
                            continue
                        note = line.get("note", "")
                        if not isinstance(note, str) or len(note) > 300:
                            raise ServiceError("invalid_note")
                        requested.append(
                            {
                                "item_id": line.get("item_id"),
                                "quantity": line.get("quantity"),
                                "options": line.get("options", {}),
                                "note": note.strip(),
                            }
                        )
                    if (
                        len(requested) != len(lines)
                        or requested
                        != [
                            {
                                k: line.get(k, "" if k == "note" else {})
                                if k in ("options", "note")
                                else line[k]
                                for k in fields
                            }
                            for line in previous["lines"]
                        ]
                        or previous["fulfillment"] != fulfillment
                        or previous.get("table_auto_selected", False) != auto_table
                        or (
                            not auto_table
                            and previous["table_label"]
                            != (table_label if fulfillment == "at_table" else None)
                        )
                        or previous.get("order_note", "") != order_note
                    ):
                        raise ServiceError("checkout_changed", 409)
                    return previous
            priced = self._lines(db, lines)
            mode = "merchant_api" if self.merchant else "local_queue_only"
            quote = {
                "id": quote_id,
                "confirmation_token": secrets.token_urlsafe(24),
                "lines": priced,
                "order_note": order_note,
                "total_vnd": sum(x["subtotal_vnd"] for x in priced),
                "currency": "VND",
                "fulfillment": fulfillment,
                "table_label": table_label if fulfillment == "at_table" else None,
                "table_auto_selected": auto_table,
                "total_kind": "listed_items_only",
                "notice": "Tạm tính theo giá niêm yết; chưa đối soát ưu đãi/phí và còn món. Chờ nhân viên xác nhận.",
                "expires_at": time.time() + 300,
                "mode": mode,
            }
            db.execute(
                "INSERT INTO quotes VALUES (?,?,?,?,?)",
                (quote["id"], sid, quote["confirmation_token"], encode(quote), quote["expires_at"]),
            )
        return quote

    def checkout(
        self, token, lines, fulfillment=None, table_label=None, *, checkout_id, order_note=""
    ):
        """Place the chosen cart and return its QR in one idempotent customer action."""
        if not isinstance(checkout_id, str) or not 1 <= len(checkout_id) <= 100:
            raise ServiceError("invalid_checkout_id")
        quote = self.quote(
            token, lines, fulfillment, table_label, checkout_id=checkout_id, order_note=order_note
        )
        return self.submit(token, quote["id"], quote["confirmation_token"], True)

    def _event(self, db, sid, entity, event):
        db.execute(
            "INSERT INTO events(session,entity,type,created_at) VALUES (?,?,?,?)",
            (sid, entity, event, now_iso()),
        )

    def submit(self, token, quote_id, confirmation_token, user_confirmed=False):
        if user_confirmed is not True:
            raise ServiceError("confirmation_required")
        with self.store.connect(write=True) as db:
            sid = self._session(db, token)
            row = db.execute(
                "SELECT * FROM quotes WHERE id=? AND session=?", (quote_id, sid)
            ).fetchone()
            if not row or not hmac.compare_digest(
                row["token"].encode(), str(confirmation_token).encode()
            ):
                raise ServiceError("invalid_confirmation", 403)
            existing = db.execute("SELECT data FROM orders WHERE quote=?", (quote_id,)).fetchone()
            if existing:
                return json.loads(existing[0])
            if row["expires"] < time.time():
                raise ServiceError("quote_expired", 409)
            quote = json.loads(row["data"])
            current = self._lines(db, quote["lines"])
            legacy_compatible_lines = [
                {**line, "note": line.get("note", "")} for line in quote["lines"]
            ]
            if current != legacy_compatible_lines:
                raise ServiceError("catalog_changed", 409)
            order = {
                k: v for k, v in quote.items() if k not in ["confirmation_token", "expires_at"]
            }
            order.update(
                id=uuid4().hex,
                quote_id=quote_id,
                status="pending_acceptance",
                payment_status="unverified",
                delivery="local_queue_only",
                created_at=now_iso(),
                vibrating_card=_next_card(db),
            )
            if self.merchant and quote.get("mode") == "merchant_api":
                order["merchant"] = {"state": "creating"}
            db.execute(
                "INSERT INTO orders VALUES (?,?,?,?)", (order["id"], quote_id, sid, encode(order))
            )
            self._event(db, sid, order["id"], "pending_acceptance")
        return self._send_merchant(order) if "merchant" in order else order

    def _save_order(self, order, **updates):
        with self.store.connect(write=True) as db:
            row = db.execute(
                "SELECT session,data FROM orders WHERE id=?", (order["id"],)
            ).fetchone()
            current = json.loads(row["data"])
            was_paid = current.get("payment_status") == "paid"
            if (
                current.get("payment", {}).get("status") == "paid"
                and current["payment"].get("source") == "merchant"
            ):
                updates.pop("payment", None)
                updates.pop("payment_status", None)
            current.update(updates)
            db.execute("UPDATE orders SET data=? WHERE id=?", (encode(current), order["id"]))
            if self.invoices and updates.get("merchant", {}).get("state") == "created":
                self.invoices.track(current, db=db)
        if not was_paid and current.get("payment_status") == "paid":
            self._paid(row["session"], current)
        return current

    def _paid(self, session, order):
        """Tell listeners, after the paid state is committed; a listener never fails a save."""
        for listener in list(self.paid_listeners):
            try:
                listener(session, json.loads(encode(order)))
            except Exception:
                logging.getLogger(__name__).exception("Paid-order listener failed")

    def _send_merchant(self, order):
        from .merchant import MerchantError

        try:
            catalog = {i["id"]: i for i in self.menu()}
            hidden = getattr(self.merchant, "hidden_voucher", None)
            voucher = hidden(order) if hidden else None
            if voucher:
                # Recorded before the POST: validation must know the merchant may discount it.
                order = self._save_order(order, merchant={**order["merchant"], "voucher": voucher})
                remote = self.merchant.create(order, catalog, voucher=voucher)
            else:
                remote = self.merchant.create(order, catalog)
            slug = self.merchant.reference(remote)
            order = self._save_order(
                order,
                merchant={**order["merchant"], "state": "created", "order_slug": slug},
                delivery="merchant_api",
            )
            if not all(key in remote for key in ("branch", "subtotal", "orderItems")):
                remote = self.merchant.fetch(order)
            payment = self.merchant.payment(remote, order)
            if payment["status"] == "pending" and not payment["qr_image"]:
                # Record the attempt BEFORE the POST; reads/retries must never re-initiate blindly.
                order = self._save_order(
                    order, merchant={**order["merchant"], "payment_initiated": True}
                )
                self.merchant.initiate(order)
                remote = self.merchant.fetch(order)
                payment = self.merchant.payment(remote, order)
            return self._save_order(
                order,
                payment=payment,
                payment_status="paid" if payment["status"] == "paid" else "unverified",
            )
        except MerchantError as exc:
            state = (
                "review_required"
                if order["merchant"].get("order_slug")
                else "uncertain"
                if exc.uncertain
                else "rejected"
            )
            return self._save_order(
                order,
                merchant={**order["merchant"], "state": state, "error": exc.code},
                payment={"status": state, "qr_image": None},
            )

    def payment(self, token, order_id):
        """The order's payment state, with its pickup card for the screen and Trend."""
        result = self._payment(token, order_id)  # checks the order belongs to this session
        with self.store.connect() as db:
            row = db.execute(
                "SELECT json_extract(data,'$.vibrating_card') FROM orders WHERE id=?", (order_id,)
            ).fetchone()
        return {**result, "vibrating_card": row[0] if row else None}

    def _payment(self, token, order_id):
        with self.store.connect() as db:
            sid = self._session(db, token)
            row = db.execute(
                "SELECT data FROM orders WHERE id=? AND session=?", (order_id, sid)
            ).fetchone()
            if not row:
                raise ServiceError("order_not_found", 404)
            order = json.loads(row[0])
        merchant = order.get("merchant", {})
        if not self.merchant or not merchant.get("order_slug"):
            state = merchant.get("state", "not_connected")
            if state == "creating" and time.time() - timestamp(order["created_at"]) > 30:
                state = "uncertain"
            return {
                "order_id": order_id,
                "status": state,
                "qr_image": None,
                "payment_connected": False,
            }
        if merchant["state"] == "review_required" and merchant.get("error") in {
            "merchant_order_mismatch",
            "merchant_payment_mismatch",
        }:
            return {
                "order_id": order_id,
                "status": "review_required",
                "qr_image": None,
                "payment_connected": True,
            }
        from .merchant import MerchantError

        try:
            payment = self.merchant.payment(self.merchant.fetch(order), order)
            saved = self._save_order(
                order,
                payment=payment,
                payment_status="paid" if payment["status"] == "paid" else order["payment_status"],
            )
            if payment["status"] == "paid" and self.invoices:
                # Print now: do not wait for this order's turn in the polling queue.
                self.invoices.wake(order_id)
            return saved["payment"]
        except MerchantError:
            return {
                "order_id": order_id,
                "status": "unavailable",
                "qr_image": None,
                "payment_connected": True,
            }

    def _invoice_order(self, token, order_id):
        with self.store.connect() as db:
            sid = self._session(db, token)
            row = db.execute(
                "SELECT data FROM orders WHERE id=? AND session=?", (order_id, sid)
            ).fetchone()
            if not row:
                raise ServiceError("order_not_found", 404)
            return json.loads(row[0])

    def print_invoice(self, token, order_id):
        """Idempotently request this guest's official paid invoice; never force/reprint."""
        order = self._invoice_order(token, order_id)
        if self.invoices is None:
            raise ServiceError("invoice_printing_disabled", 503)
        if not self.merchant or not order.get("merchant", {}).get("order_slug"):
            raise ServiceError("merchant_order_required", 409)
        self.invoices.track(order)
        return self.invoices.status(order_id)

    def invoice_status(self, token, order_id):
        self._invoice_order(token, order_id)
        return (
            self.invoices.status(order_id)
            if self.invoices
            else {
                "order_id": order_id,
                "state": "disabled",
            }
        )

    def progress(self, token):
        with self.store.connect() as db:
            sid = self._session(db, token)
            return {
                "orders": [
                    json.loads(r[0])
                    for r in db.execute(
                        "SELECT data FROM orders WHERE session=? ORDER BY rowid DESC LIMIT 100",
                        (sid,),
                    )
                ],
                "handoffs": [
                    json.loads(r[0])
                    for r in db.execute(
                        "SELECT data FROM handoffs WHERE session=? ORDER BY rowid DESC LIMIT 100",
                        (sid,),
                    )
                ],
                "events": [
                    dict(r)
                    for r in db.execute(
                        "SELECT id,entity,type,created_at FROM events WHERE session=? ORDER BY id DESC LIMIT 200",
                        (sid,),
                    )
                ],
                "mode": "merchant_api" if self.merchant else "local_queue_only",
            }

    def handoff(self, token, reason):
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
            raise ServiceError("invalid_reason")
        with self.store.connect(write=True) as db:
            sid = self._session(db, token)
            result = {
                "id": uuid4().hex,
                "reason": reason.strip(),
                "status": "queued_local",
                "delivered": False,
                "created_at": now_iso(),
            }
            db.execute("INSERT INTO handoffs VALUES (?,?,?)", (result["id"], sid, encode(result)))
            self._event(db, sid, result["id"], "handoff_queued_local")
        return result

    def staff_queue(self):
        with self.store.connect() as db:
            return {
                "orders": [
                    json.loads(r[0])
                    for r in db.execute("SELECT data FROM orders ORDER BY rowid DESC LIMIT 100")
                ],
                "handoffs": [
                    json.loads(r[0])
                    for r in db.execute("SELECT data FROM handoffs ORDER BY rowid DESC LIMIT 100")
                ],
            }

    def staff_update(self, order_id, status=None, payment_status=None):
        transitions = {
            "pending_acceptance": ["accepted", "rejected", "cancelled"],
            "accepted": ["preparing", "cancelled"],
            "preparing": ["ready", "cancelled"],
            "ready": ["completed", "cancelled"],
        }
        payments = {
            "unverified": ["paid", "failed"],
            "failed": ["paid"],
            "paid": ["refund_pending"],
            "refund_pending": ["refunded", "paid"],
        }
        if (status is None) == (payment_status is None):
            raise ServiceError("one_transition_required")
        with self.store.connect(write=True) as db:
            row = db.execute("SELECT session,data FROM orders WHERE id=?", (order_id,)).fetchone()
            if not row:
                raise ServiceError("order_not_found", 404)
            order = json.loads(row["data"])
            key, target, allowed = (
                ("status", status, transitions)
                if status is not None
                else ("payment_status", payment_status, payments)
            )
            if target not in allowed.get(order[key], []):
                raise ServiceError("invalid_transition", 409)
            order[key] = target
            db.execute("UPDATE orders SET data=? WHERE id=?", (encode(order), order_id))
            self._event(db, row["session"], order_id, key + ":" + target)
        return order

    def staff_handoff(self, handoff_id, status):
        transitions = {"queued_local": ["acknowledged"], "acknowledged": ["resolved"]}
        with self.store.connect(write=True) as db:
            row = db.execute(
                "SELECT session,data FROM handoffs WHERE id=?", (handoff_id,)
            ).fetchone()
            if not row:
                raise ServiceError("handoff_not_found", 404)
            result = json.loads(row["data"])
            if status not in transitions.get(result["status"], []):
                raise ServiceError("invalid_transition", 409)
            result.update(status=status, delivered=True, updated_at=now_iso())
            db.execute("UPDATE handoffs SET data=? WHERE id=?", (encode(result), handoff_id))
            self._event(db, row["session"], handoff_id, "handoff:" + status)
        return result

    def working_draft(self, token, lines=None, clear=False):
        """Short-lived conversation state, separate from opt-in retained preferences."""
        with self.store.connect(write=True) as db:
            sid = self._session(db, token)
            if clear:
                db.execute("DELETE FROM working WHERE session=?", (sid,))
                return None
            if lines is not None:
                self._lines(db, lines)
                db.execute(
                    "INSERT OR REPLACE INTO working VALUES (?,?,?)",
                    (sid, encode(lines), time.time() + 900),
                )
                return lines
            row = db.execute("SELECT data,expires FROM working WHERE session=?", (sid,)).fetchone()
            return json.loads(row["data"]) if row and row["expires"] > time.time() else None
