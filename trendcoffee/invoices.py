"""Durable invoice printing, independent of the guest's page or voice session."""

import asyncio
import hashlib
import json
import logging
import sqlite3
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from .merchant import MerchantError
from .service import timestamp

# A QR is valid for 15 minutes; after 30 more minutes an unpaid order stops being
# polled, so stale orders cannot delay the next paid invoice. A payment the kiosk
# verifies later puts it back in the queue (`wake`).
ABANDON_AFTER = 45 * 60


class InvoicePrinter:
    lease_seconds = 120

    def __init__(self, service, printer):
        self.service, self.store, self.printer = service, service.store, printer
        self.stopping = threading.Event()

    def track(self, order, *, db=None):
        """Enroll a newly created checkout, or an explicitly requested invoice, once."""
        merchant_id = order.get("merchant", {}).get("order_slug")
        if not merchant_id:
            return
        if db is None:
            with self.store.connect(write=True) as connection:
                self.track(order, db=connection)
            return
        title = "Trend-invoice-" + hashlib.sha256(merchant_id.encode()).hexdigest()[:24]
        db.execute(
            """INSERT OR IGNORE INTO print_jobs
            (order_id,merchant_order_id,title,updated) VALUES (?,?,?,?)""",
            (order["id"], merchant_id, title, time.time()),
        )

    def status(self, order_id):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT order_id,state,job_id,error FROM print_jobs WHERE order_id=?", (order_id,)
            ).fetchone()
        return dict(row) if row else {"order_id": order_id, "state": "not_requested"}

    def wake(self, order_id):
        """A verified payment: check this order on the next pass, even if it was abandoned."""
        with self.store.connect(write=True) as db:
            db.execute(
                """UPDATE print_jobs SET state='waiting',error='',next_check=0,updated=?
                WHERE order_id=? AND state IN ('waiting','abandoned')""",
                (time.time(), order_id),
            )

    @staticmethod
    def _past_payment_window(order):
        try:
            placed = timestamp(order["created_at"])
        except (KeyError, TypeError, ValueError, AttributeError):
            return False
        return order.get("payment_status") != "paid" and time.time() - placed > ABANDON_AFTER

    def _change(self, order_id, before, after, *, delay=2, **values):
        values.update(state=after, updated=time.time(), next_check=time.time() + delay)
        with self.store.connect(write=True) as db:
            result = db.execute(
                "UPDATE print_jobs SET "
                + ",".join(f"{k}=?" for k in values)
                + " WHERE order_id=? AND state=?",
                (*values.values(), order_id, before),
            )
            return result.rowcount == 1

    def process_once(self, *, force=False):
        if self.stopping.is_set() or not self.service.merchant:
            return
        now = time.time()
        with self.store.connect(write=True) as db:
            # Reads/rasterization can safely retry after a crash. Spooling/release cannot.
            db.execute(
                """UPDATE print_jobs SET state='waiting',next_check=0
                WHERE state='checking' AND updated<?""",
                (now - self.lease_seconds,),
            )
            db.execute(
                """UPDATE print_jobs SET state='unknown',error='printer_acknowledgment_lost'
                WHERE state IN ('submitting','releasing') AND updated<?""",
                (now - self.lease_seconds,),
            )
            rows = db.execute(
                """SELECT p.*,o.data FROM print_jobs p JOIN orders o ON o.id=p.order_id
                WHERE p.state IN ('waiting','held','submitted','processing')
                AND (? OR next_check<=?) ORDER BY next_check LIMIT 8""",
                (force, now),
            ).fetchall()
        for row in rows:
            if self.stopping.is_set():
                break
            if row["state"] == "waiting":
                if self._change(row["order_id"], "waiting", "checking"):
                    self._prepare(row)
            elif row["state"] == "held":
                self._release(row)
            else:
                self._observe(row)

    def _prepare(self, row):
        oid, stage = row["order_id"], "checking"
        try:
            order = json.loads(row["data"])
            if order["merchant"]["order_slug"] != row["merchant_order_id"]:
                raise MerchantError("merchant_order_mismatch")
            merchant = self.service.merchant
            remote = merchant.fetch(order)
            document = merchant.invoice_pdf(remote, order)
            payment = merchant.payment(remote, order)
            self.service._save_order(
                order,
                payment=payment,
                payment_status="paid" if payment["status"] == "paid" else order["payment_status"],
            )
            if document is None:
                if payment["status"] != "paid" and self._past_payment_window(order):
                    self._change(oid, stage, "abandoned", error="payment_" + payment["status"])
                    return
                self._change(oid, stage, "waiting", error="")
                return
            invoice_id, content = document
            with tempfile.TemporaryDirectory(prefix="trendcoffee-invoice-") as directory:
                directory = Path(directory)
                pdf = directory / "invoice.pdf"
                pdf.write_bytes(content)
                payload = self.printer.prepare(pdf, directory, card=order.get("vibrating_card"))
                if self.stopping.is_set():
                    self._change(oid, stage, "waiting")
                    return
                # The unique invoice ID and CAS precede the first irreversible side effect.
                if not self._change(oid, stage, "submitting", invoice_id=invoice_id, error=""):
                    return
                stage = "submitting"
                if self.stopping.is_set():
                    self._change(oid, stage, "waiting")
                    return
                job_id = self.printer.hold(payload, row["title"])
                self._change(oid, stage, "held", job_id=job_id)
                stage = "held"
                self._release({**dict(row), "job_id": job_id})
        except sqlite3.IntegrityError:
            self._change(oid, stage, "failed", error="invoice_already_registered")
        except MerchantError as exc:
            terminal = exc.code.endswith(("mismatch", "invalid"))
            if not terminal and stage == "checking":
                try:
                    stale = self._past_payment_window(json.loads(row["data"]))
                except (TypeError, ValueError):
                    stale = False
                if stale:
                    self._change(oid, stage, "abandoned", error=exc.code)
                    return
            self._change(oid, stage, "failed" if terminal else "waiting", delay=10, error=exc.code)
        except Exception:
            self._change(
                oid,
                stage,
                "unknown" if stage != "checking" else "waiting",
                delay=10,
                error="printer_acknowledgment_lost"
                if stage != "checking"
                else "invoice_prepare_failed",
            )

    def _release(self, row):
        if self.stopping.is_set():
            return
        try:
            self.printer.verify_held(row["job_id"], row["title"])
        except ValueError:
            self._change(row["order_id"], "held", "unknown", error="printer_job_identity_mismatch")
            return
        except Exception:
            self._change(
                row["order_id"], "held", "held", delay=10, error="printer_status_unavailable"
            )
            return
        if self.stopping.is_set() or not self._change(row["order_id"], "held", "releasing"):
            return
        try:
            if self.stopping.is_set():
                self._change(row["order_id"], "releasing", "held")
                return
            self.printer.release(row["job_id"])
            self._change(row["order_id"], "releasing", "submitted", error="")
        except Exception:
            self._change(row["order_id"], "releasing", "unknown", error="printer_release_uncertain")

    def _observe(self, row):
        try:
            state = self.printer.job_state(row["job_id"], row["title"])
            if state in {"pending", "pending-held", "processing-stopped"}:
                state = "processing"
            confirmed = state in {"processing", "completed", "failed"}
            self._change(
                row["order_id"],
                row["state"],
                state if confirmed else row["state"],
                delay=2 if confirmed else 10,
                error="" if confirmed else "printer_completion_unconfirmed",
            )
        except Exception:
            # Keep observing the same submitted job, never submit another invoice.
            self._change(
                row["order_id"],
                row["state"],
                row["state"],
                delay=10,
                error="printer_status_unavailable",
            )

    async def run(self, stop):
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.process_once)
            except Exception:
                logging.getLogger(__name__).exception("Invoice worker iteration failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=2)
            except TimeoutError:
                pass


@asynccontextmanager
async def invoice_worker(service):
    worker = service.invoices
    if worker is None:
        yield
        return
    worker.stopping.clear()
    stop = asyncio.Event()
    task = asyncio.create_task(worker.run(stop))
    try:
        yield
    finally:
        worker.stopping.set()
        stop.set()
        await task
