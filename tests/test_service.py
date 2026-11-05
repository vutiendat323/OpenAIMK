import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from trendcoffee.service import ServiceError


def stamp(days=0):
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def line(**kwargs):
    return {"item_id": "coffee", "quantity": 1, "options": {}, **kwargs}


def test_retrieval_is_accent_insensitive_sourced_and_approved(svc):
    hits = svc.search("dia chi Nguyen Cong Tru")
    assert hits[0]["id"] == "address"
    assert hits[0]["source_url"].startswith("https://trendcoffee.net/")
    assert svc.search("miễn phí") == []
    assert svc.search("sinh nhật") == []
    assert svc.search('" OR *') == []


def test_memory_requires_consent_is_scoped_and_deletable(svc):
    a, b = (svc.new_session(), svc.new_session())
    with pytest.raises(ServiceError, match="consent_required"):
        svc.remember(a, "taste", "ít ngọt", consent=False)
    svc.remember(a, "taste", "ít ngọt", consent=True)
    assert svc.memory(a) == {"taste": "ít ngọt"}
    assert svc.memory(b) == {}
    svc.forget(a)
    assert svc.memory(a) == {}


def test_quote_keeps_different_cups_separate_and_requires_confirmation(svc):
    token = svc.new_session()
    q = svc.quote(
        token, [line(options={"ice": "ít"}), line(options={"ice": "vừa"})], fulfillment="takeaway"
    )
    assert q["total_vnd"] == 60000
    assert len(q["lines"]) == 2
    with pytest.raises(ServiceError, match="confirmation_required"):
        svc.submit(token, q["id"], q["confirmation_token"], False)
    order = svc.submit(token, q["id"], q["confirmation_token"], True)
    assert order["status"] == "pending_acceptance"
    assert order["payment_status"] == "unverified"
    assert order["delivery"] == "local_queue_only"


def test_quote_submission_is_idempotent_under_concurrency(svc):
    token = svc.new_session()
    q = svc.quote(token, [line(quantity=2)], fulfillment="takeaway")

    def submit(_):
        return svc.submit(token, q["id"], q["confirmation_token"], True)["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(submit, range(16)))
    assert len(set(ids)) == 1
    assert len(svc.progress(token)["orders"]) == 1


def test_one_step_checkout_is_idempotent_and_scoped_to_guest(svc):
    token = svc.new_session()

    def checkout(_):
        return svc.checkout(token, [line()], "takeaway", checkout_id="first-request")["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(checkout, range(16)))
    assert len(set(ids)) == 1
    with pytest.raises(ServiceError, match="checkout_changed"):
        svc.checkout(token, [line(quantity=2)], "takeaway", checkout_id="first-request")
    other = svc.checkout(svc.new_session(), [line()], "takeaway", checkout_id="first-request")
    assert other["id"] != ids[0]
    assert len(svc.progress(token)["orders"]) == 1


def test_notes_are_validated_quoted_and_checkout_idempotency_binds_them(svc):
    token = svc.new_session()
    lines = [line(note="  less ice  "), line(note="no sugar")]
    q = svc.quote(token, lines, "takeaway", order_note="  call when ready  ")
    assert [item["note"] for item in q["lines"]] == ["less ice", "no sugar"]
    assert q["order_note"] == "call when ready"
    order = svc.checkout(
        token, lines, "takeaway", checkout_id="notes", order_note="call when ready"
    )
    retry = svc.checkout(
        token, lines, "takeaway", checkout_id="notes", order_note="call when ready"
    )
    assert retry["id"] == order["id"]
    with pytest.raises(ServiceError, match="checkout_changed"):
        svc.checkout(token, lines, "takeaway", checkout_id="notes", order_note="ring bell")
    with pytest.raises(ServiceError, match="checkout_changed"):
        svc.checkout(
            token,
            [line(note="different")],
            "takeaway",
            checkout_id="notes",
            order_note="call when ready",
        )


def test_notes_reject_wrong_type_and_over_limit(svc):
    token = svc.new_session()
    for invalid_line in (line(note=3), line(note="x" * 301)):
        with pytest.raises(ServiceError, match="invalid_note"):
            svc.quote(token, [invalid_line], "takeaway")
    with pytest.raises(ServiceError, match="invalid_note"):
        svc.quote(token, [line()], "takeaway", order_note="x" * 1001)


def test_pending_pre_notes_quote_remains_submittable(svc):
    token = svc.new_session()
    q = svc.quote(token, [line()], "takeaway")
    legacy_line = dict(q["lines"][0])
    legacy_line.pop("note")
    q["lines"] = [legacy_line]
    q.pop("order_note")
    with svc.store.connect(write=True) as db:
        db.execute("UPDATE quotes SET data=? WHERE id=?", (json.dumps(q), q["id"]))
    order = svc.submit(token, q["id"], q["confirmation_token"], True)
    assert order["lines"][0].get("note", "") == ""


def test_changed_price_rejects_old_confirmation(svc):
    token = svc.new_session()
    q = svc.quote(token, [line()], fulfillment="takeaway")
    svc.ingest(
        {
            "menu": {
                "items": [
                    {
                        "id": "coffee",
                        "name": "Cà phê sữa",
                        "price_vnd": 35000,
                        "options": {"ice": ["ít", "vừa"]},
                        "availability": "unknown",
                        "source_url": "https://trendcoffee.net/menu",
                        "verified_at": stamp(),
                    }
                ]
            }
        }
    )
    with pytest.raises(ServiceError, match="catalog_changed"):
        svc.submit(token, q["id"], q["confirmation_token"], True)


@pytest.mark.parametrize(
    "lines",
    [
        [],
        [line(quantity=0)],
        [line(quantity=1.5)],
        [line(quantity=True)],
        [line(quantity=101)],
        [line(options={"ice": "nhiều"})],
        [line(options={"size": "L"})],
        [line(item_id="sold")],
    ],
)
def test_invalid_and_unavailable_orders_are_rejected(svc, lines):
    with pytest.raises(ServiceError):
        svc.quote(svc.new_session(), lines, fulfillment="takeaway")


def test_cross_session_access_and_bad_token_rejected(svc):
    a, b = (svc.new_session(), svc.new_session())
    q = svc.quote(a, [line()], fulfillment="takeaway")
    with pytest.raises(ServiceError):
        svc.submit(b, q["id"], q["confirmation_token"], True)
    with pytest.raises(ServiceError):
        svc.submit(a, q["id"], "wrong", True)
    with pytest.raises(ServiceError):
        svc.memory("not-a-session")


def test_staff_transitions_keep_payment_separate_and_emit_progress(svc):
    token = svc.new_session()
    q = svc.quote(token, [line()], fulfillment="takeaway")
    order = svc.submit(token, q["id"], q["confirmation_token"], True)
    with pytest.raises(ServiceError, match="invalid_transition"):
        svc.staff_update(order["id"], status="completed")
    svc.staff_update(order["id"], status="accepted")
    assert svc.progress(token)["orders"][0]["payment_status"] == "unverified"
    svc.staff_update(order["id"], payment_status="paid")
    assert svc.progress(token)["orders"][0]["status"] == "accepted"
    assert len(svc.progress(token)["events"]) == 3


def test_handoff_reports_local_queue_not_delivery(svc):
    token = svc.new_session()
    h = svc.handoff(token, "Khách báo thiếu một ly")
    assert h["delivered"] is False
    assert h["status"] == "queued_local"
    assert svc.progress(token)["handoffs"][0]["id"] == h["id"]


def test_handoff_can_be_acknowledged_and_resolved_by_staff(svc):
    token = svc.new_session()
    request = svc.handoff(token, "Thiếu một ly")
    result = svc.staff_handoff(request["id"], "acknowledged")
    assert result["delivered"] is True
    assert result["status"] == "acknowledged"
    result = svc.staff_handoff(request["id"], "resolved")
    assert result["status"] == "resolved"
    assert len(svc.progress(token)["events"]) == 3


def test_malformed_mcp_line_returns_domain_error_instead_of_crashing(svc):
    with pytest.raises(ServiceError, match="invalid_lines"):
        svc.quote(svc.new_session(), ["bad-line"], fulfillment="takeaway")


def test_restart_reopens_persistent_wal_database(svc):
    from trendcoffee.service import Service

    token = svc.new_session()
    svc.remember(token, "taste", "ít ngọt", consent=True)
    reopened = Service(svc.store.path)
    assert reopened.memory(token)["taste"] == "ít ngọt"
    with reopened.store.connect() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_old_approved_knowledge_without_explicit_expiry_is_not_current(svc):
    svc.ingest(
        {
            "knowledge": [
                {
                    "id": "old-implicit",
                    "title": "Địa chỉ cũ",
                    "text": "Mô tả cũ không được trả lời.",
                    "source_url": "https://trendcoffee.net/",
                    "verified_at": "2000-01-01T00:00:00Z",
                    "approved": True,
                }
            ]
        }
    )
    assert svc.search("Mô tả cũ không được trả lời") == []


def test_expired_quote_requires_new_review(svc):
    token = svc.new_session()
    q = svc.quote(token, [line()], fulfillment="takeaway")
    with svc.store.connect(write=True) as db:
        db.execute("UPDATE quotes SET expires=0 WHERE id=?", (q["id"],))
    with pytest.raises(ServiceError, match="quote_expired"):
        svc.submit(token, q["id"], q["confirmation_token"], True)


def test_stale_menu_cannot_be_quoted_and_bad_import_preserves_catalog(svc):
    old = svc.menu()
    with pytest.raises(ServiceError):
        svc.ingest({"menu": {"items": [{"id": "bad", "price_vnd": -1}]}})
    assert svc.menu() == old
    stale = {key: value for key, value in old[0].items() if key != "stale"}
    stale["verified_at"] = "2000-01-01T00:00:00Z"
    svc.ingest({"menu": {"items": [stale]}})
    with pytest.raises(ServiceError, match="stale_catalog"):
        svc.quote(
            svc.new_session(),
            [{"item_id": stale["id"], "quantity": 1, "options": {}}],
            fulfillment="takeaway",
        )
