"""Invoice trigger, ownership and durable at-most-once CUPS submission; no real printing."""

import copy
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from test_merchant import connect, place, remote_order

from trendcoffee.invoices import InvoicePrinter
from trendcoffee.service import ServiceError


class Printer:
    def __init__(self):
        self.holds = self.releases = 0
        self.observed = "processing"
        self.uncertain = False

    def prepare(self, pdf, directory):
        assert pdf.read_bytes().startswith(b"%PDF-")
        return pdf

    def hold(self, payload, title):
        self.holds += 1
        if self.uncertain:
            raise TimeoutError("printer acknowledgment lost")
        return "GP-C180I-12"

    def verify_held(self, job_id, title):
        assert job_id == "GP-C180I-12"

    def release(self, job_id):
        self.releases += 1

    def job_state(self, job_id, title):
        return self.observed


def setup(svc, merchant=None):
    remote = remote_order()
    remote["payment"]["statusMessage"] = "pending"
    calls = []
    merchant = {} if merchant is None else merchant

    def handler(request):
        calls.append(request.url.path)
        if merchant.get("reject") and request.method == "GET":
            return httpx.Response(403, json={"message": "forbidden"})
        if request.url.path.endswith("/invoice/export/public"):
            assert request.method == "POST"
            return httpx.Response(
                200, content=b"%PDF-1.4\nfixture", headers={"content-type": "application/pdf"}
            )
        return httpx.Response(200, json={"result": copy.deepcopy(remote)})

    connect(svc, handler)
    printer = Printer()
    svc.invoices = InvoicePrinter(svc, printer)
    token, _, order = place(svc)
    return token, order, remote, printer, calls


def complete(remote):
    remote["status"] = "paid"
    remote["payment"].update(statusCode="completed", statusMessage="completed")
    remote["invoice"] = {"slug": "official-invoice-1"}


def test_only_merchant_completed_payment_and_official_invoice_print(svc):
    token, order, remote, printer, calls = setup(svc)
    svc.invoices.process_once(force=True)
    assert printer.holds == 0  # merely showing/scanning a QR is not payment evidence
    remote["status"] = "paid"
    svc.invoices.process_once(force=True)
    assert printer.holds == 0
    complete(remote)
    svc.invoices.process_once(force=True)
    assert printer.holds == printer.releases == 1
    assert svc.invoice_status(token, order["id"])["state"] == "submitted"
    printer.observed = "completed"
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] == "completed"
    svc.print_invoice(token, order["id"])
    svc.invoices.process_once(force=True)
    assert printer.holds == 1
    assert calls.count("/api/latest/invoice/export/public") == 1


def test_concurrent_workers_and_restart_never_create_second_invoice_job(svc):
    token, order, remote, printer, _ = setup(svc)
    complete(remote)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: svc.invoices.process_once(force=True), range(4)))
    assert printer.holds == printer.releases == 1
    restarted = InvoicePrinter(svc, printer)
    restarted.process_once(force=True)
    assert printer.holds == 1
    assert svc.invoice_status(token, order["id"])["state"] in {"submitted", "processing"}


def test_uncertain_spool_is_not_repeated_and_other_guest_cannot_print(svc):
    token, order, remote, printer, _ = setup(svc)
    complete(remote)
    printer.uncertain = True
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] == "unknown"
    svc.invoices.process_once(force=True)
    assert printer.holds == 1 and printer.releases == 0
    with pytest.raises(ServiceError, match="order_not_found"):
        svc.print_invoice(svc.new_session(), order["id"])


def test_wrong_merchant_order_never_downloads_or_prints(svc):
    _, _, remote, printer, calls = setup(svc)
    complete(remote)
    remote["slug"] = "different-order"
    svc.invoices.process_once(force=True)
    assert printer.holds == 0
    assert "/api/latest/invoice/export/public" not in calls


@pytest.mark.parametrize("field", ["statusCode", "statusMessage"])
def test_incomplete_payment_evidence_never_prints(svc, field):
    _, _, remote, printer, calls = setup(svc)
    complete(remote)
    remote["payment"].pop(field)
    svc.invoices.process_once(force=True)
    assert printer.holds == 0
    assert "/api/latest/invoice/export/public" not in calls


@pytest.mark.parametrize("slug", [None, 123, "", "../another-order"])
def test_invalid_official_invoice_identity_never_prints(svc, slug):
    token, order, remote, printer, calls = setup(svc)
    complete(remote)
    remote["invoice"]["slug"] = slug
    svc.invoices.process_once(force=True)
    assert printer.holds == 0
    assert "/api/latest/invoice/export/public" not in calls
    assert svc.invoice_status(token, order["id"])["state"] == "failed"


@pytest.mark.parametrize("kind", ["html", "redirect", "oversize", "signature"])
def test_untrusted_invoice_document_never_reaches_printer(svc, kind):
    from trendcoffee.merchant import MerchantClient

    token, order, remote, printer, _ = setup(svc)
    complete(remote)

    def handler(request):
        if not request.url.path.endswith("/invoice/export/public"):
            return httpx.Response(200, json={"result": remote})
        if kind == "redirect":
            return httpx.Response(302, headers={"location": "https://elsewhere.invalid/invoice"})
        content = b"%PDF-" + b"0" * (5 * 1024 * 1024) if kind == "oversize" else b"not-pdf"
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "text/html" if kind == "html" else "application/pdf"},
        )

    svc.merchant = MerchantClient(transport=httpx.MockTransport(handler))
    svc.invoices.process_once(force=True)
    assert printer.holds == printer.releases == 0
    assert svc.invoice_status(token, order["id"])["state"] in {"waiting", "failed"}


def test_restart_resumes_known_held_job_but_never_repeats_uncertain_release(svc):
    token, order, _, printer, _ = setup(svc)
    svc.invoices._change(order["id"], "waiting", "held", job_id="GP-C180I-12")
    InvoicePrinter(svc, printer).process_once(force=True)
    assert printer.holds == 0 and printer.releases == 1
    with svc.store.connect(write=True) as db:
        db.execute("UPDATE print_jobs SET state='releasing',updated=0")
    InvoicePrinter(svc, printer).process_once(force=True)
    assert printer.releases == 1
    assert svc.invoice_status(token, order["id"])["state"] == "unknown"


def test_transient_held_job_lookup_retries_without_respooling(svc):
    token, order, _, printer, _ = setup(svc)
    svc.invoices._change(order["id"], "waiting", "held", job_id="GP-C180I-12")
    verify = printer.verify_held

    def unavailable(*args):
        raise TimeoutError("temporary IPP failure")

    printer.verify_held = unavailable
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] == "held"
    assert printer.holds == printer.releases == 0
    printer.verify_held = verify
    svc.invoices.process_once(force=True)
    assert printer.holds == 0 and printer.releases == 1


def test_unconfirmed_job_completion_keeps_observing_same_job(svc):
    token, order, remote, printer, _ = setup(svc)
    complete(remote)
    svc.invoices.process_once(force=True)
    printer.observed = "unknown"  # queued in device or missing completion reason
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] in {"submitted", "processing"}
    printer.observed = "completed"
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] == "completed"
    assert printer.holds == printer.releases == 1


def test_shutdown_during_held_verification_defers_release_until_restart(svc):
    token, order, _, printer, _ = setup(svc)
    svc.invoices._change(order["id"], "waiting", "held", job_id="GP-C180I-12")
    verify = printer.verify_held
    printer.verify_held = lambda *args: svc.invoices.stopping.set()
    svc.invoices.process_once(force=True)
    assert printer.releases == 0
    assert svc.invoice_status(token, order["id"])["state"] == "held"
    printer.verify_held = verify
    InvoicePrinter(svc, printer).process_once(force=True)
    assert printer.holds == 0 and printer.releases == 1


def test_old_orders_are_not_retroactively_printed_on_startup(svc):
    from trendcoffee.printer import CupsPrinter

    _, order, _, _, _ = setup(svc)
    with svc.store.connect(write=True) as db:
        db.execute("DELETE FROM print_jobs")
    worker = InvoicePrinter(
        svc, CupsPrinter("GP-C180I", run=lambda *a, **k: pytest.fail("real print"))
    )
    worker.process_once(force=True)
    assert worker.status(order["id"])["state"] == "not_requested"


def test_mcp_worker_prints_after_checkout_page_is_gone_and_tools_are_scoped(svc):
    import asyncio

    from mcp import Client

    from trendcoffee.mcp_server import create_server

    token, order, remote, printer, _ = setup(svc)
    complete(remote)

    async def exercise():
        async with Client(create_server(svc)) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            assert {"print_invoice", "get_invoice_status"} <= names
            result = await client.call_tool(
                "print_invoice", {"session_token": token, "order_id": order["id"]}
            )
            assert not result.is_error
            for _ in range(100):
                if printer.releases:
                    break
                await asyncio.sleep(0.02)
            assert printer.holds == printer.releases == 1
            other = svc.new_session()
            result = await client.call_tool(
                "get_invoice_status", {"session_token": other, "order_id": order["id"]}
            )
            assert result.is_error
            result = await client.call_tool(
                "get_invoice_status", {"session_token": token, "order_id": order["id"]}
            )
            assert result.structured_content["state"] == "submitted"

    asyncio.run(exercise())


def test_http_invoice_routes_are_scoped_and_do_not_allow_force_reprint(svc):
    from fastapi.testclient import TestClient

    from trendcoffee.api import create_app

    token, order, _, printer, _ = setup(svc)
    with TestClient(create_app(service=svc)) as client:
        path = f"/api/orders/{order['id']}/invoice"
        assert client.get(path).status_code == 401
        other = {"Authorization": "Bearer " + svc.new_session()}
        assert client.post(path, headers=other).status_code == 404
        own = {"Authorization": "Bearer " + token}
        assert client.post(path, headers=own).json()["state"] in {"checking", "waiting"}
        assert client.get(path, headers=own).status_code == 200
    assert printer.holds == 0


def make_old(svc, order, seconds):
    """Pretend the order was placed `seconds` ago."""
    import json
    from datetime import UTC, datetime

    from trendcoffee.service import encode

    with svc.store.connect(write=True) as db:
        row = db.execute("SELECT data FROM orders WHERE id=?", (order["id"],)).fetchone()
        data = json.loads(row[0])
        data["created_at"] = datetime.fromtimestamp(time.time() - seconds, UTC).isoformat()
        db.execute("UPDATE orders SET data=? WHERE id=?", (encode(data), order["id"]))


def test_a_paid_order_the_kiosk_sees_prints_on_the_next_pass(svc):
    token, order, remote, printer, _ = setup(svc)
    svc.invoices.process_once(force=True)  # QR shown, not paid: checked again later
    complete(remote)
    svc.invoices.process_once()
    assert printer.holds == 0, "not due yet"
    assert svc.payment(token, order["id"])["status"] == "paid"
    svc.invoices.process_once()  # no force: the paid order is due at once
    assert printer.holds == printer.releases == 1


@pytest.mark.parametrize("answer", ["expired", "rejected"])
def test_unpaid_orders_past_the_qr_and_grace_stop_polling_the_merchant(svc, answer):
    merchant = {}
    token, order, _, printer, calls = setup(svc, merchant)
    make_old(svc, order, 46 * 60)  # 15 min QR + 30 min grace have passed
    merchant["reject"] = answer == "rejected"
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] == "abandoned"
    asked = len(calls)
    svc.invoices.process_once(force=True)
    assert len(calls) == asked, "no more merchant requests for an abandoned order"
    assert printer.holds == 0


def test_a_late_payment_brings_an_abandoned_order_back_to_print(svc):
    token, order, remote, printer, _ = setup(svc)
    make_old(svc, order, 46 * 60)
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] == "abandoned"
    complete(remote)
    assert svc.payment(token, order["id"])["status"] == "paid"
    svc.invoices.process_once()
    assert printer.holds == printer.releases == 1


def test_a_paid_order_waiting_for_its_invoice_is_never_abandoned(svc):
    token, order, remote, printer, _ = setup(svc)
    make_old(svc, order, 3 * 3600)
    complete(remote)
    remote["invoice"] = None  # paid; the merchant has not issued the invoice yet
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] == "waiting"
    remote["invoice"] = {"slug": "official-invoice-1"}
    svc.invoices.process_once(force=True)
    assert printer.holds == 1


def test_a_recent_unpaid_order_keeps_waiting(svc):
    token, order, _, _, _ = setup(svc)
    make_old(svc, order, 10 * 60)
    svc.invoices.process_once(force=True)
    assert svc.invoice_status(token, order["id"])["state"] == "waiting"
