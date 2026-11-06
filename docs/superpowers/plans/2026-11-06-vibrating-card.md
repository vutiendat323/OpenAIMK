# Vibrating Pickup Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every new order gets a pickup card number 1–16 (rotating), shown on the printed invoice header, in the merchant order description, on the kiosk payment panel, and in Trend's QR sentence.

**Architecture:** `Service.submit` assigns `order["vibrating_card"]` inside its existing `BEGIN IMMEDIATE` transaction from the last numbered order (persistent, race-free, stable on retries). Every consumer reads that one field: `merchant.order_description`, `CupsPrinter.prepare` (via `InvoiceWorker._prepare`), kiosk tool results (`qr_reply` from `session_notices.qr_sentence`), and the React payment panel.

**Tech Stack:** Python 3.12, FastAPI, SQLite (JSON in `orders.data`), ImageMagick `magick` CLI (already installed, like `pdftoppm`), React 19/TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-06-vibrating-card-design.md`

## Global Constraints

- Card numbers 1–16, rotating 1 → 16 → 1 across **all** new orders (takeaway and dine-in); no busy tracking.
- QR sentence, exact: `Bạn quét QR trên màn hình để thanh toán nhé, thẻ rung của bạn là số {card}.`; orders without a card keep exactly `Bạn quét QR trên màn hình để thanh toán nhé.`
- Printed header, exact text: `THẺ RUNG SỐ {card}` (Vietnamese diacritics, no table); orders without a card keep `AI ORDER,QUY KHACH VUI LONG DOI 15\nNHAN MON TAI QUAY NHE`.
- Merchant description (card 7): `AI ORDER\nTHẺ RUNG SỐ 7 · Bàn 05\nKhi thẻ rung, mời quý khách đến quầy nhận món. Cảm ơn quý khách!\nKiosk <id>[\n<order_note>]`; takeaway uses `· Mang đi`; no card → today's text.
- Kiosk panel: add only the big number (no caption); keep all current panel content.
- Fixtures only: no real merchant orders, payments or printer jobs. Ruff (100 cols), Prettier (single quotes, no semicolons).
- Python tests: `.venv/bin/pytest -q <file>`; lint: `.venv/bin/ruff check trendcoffee tests && .venv/bin/ruff format --check trendcoffee tests`; frontend: `cd frontend && npm test && npm run lint && npm run format:check && npm run build`.

## Review Focus

1. Retry of the same checkout (`checkout_id` re-quote, or `submit` of an already-submitted quote) must return the same card — pinned in Task 1.
2. Two orders created back-to-back on two `Service` instances over one DB file (API + MCP processes) get consecutive, distinct cards — pinned in Task 1.
3. Orders created before this change (no `vibrating_card`) keep today's description, header and QR sentence, and still pass `MerchantClient.validate` — pinned in Tasks 2, 3, 4.
4. A table label missing on a dine-in order (`table_label` None) must not print `Bàn None` — pinned in Task 2.
5. `magick` missing or failing must not silently print a card-less receipt for a carded order: `prepare` raises, the invoice job retries like any other prepare failure — pinned in Task 3.

---

### Task 1: Assign the card when an order is created

**Files:**
- Modify: `trendcoffee/service.py` (`submit`, `payment`; new `CARD_COUNT`, `_next_card`)
- Test: `tests/test_vibrating_card.py` (create)

**Interfaces:**
- Produces: `order["vibrating_card"]: int` (1–16) on every order created from now on; `Service.payment(token, order_id)` results carry `"vibrating_card": int | None`.

- [ ] **Step 1: Write the failing tests** in `tests/test_vibrating_card.py`, using the existing `svc` fixture and the local (non-merchant) checkout path as other service tests do (`svc.new_session()`, `svc.checkout(token, lines, "takeaway", checkout_id="1")`, a real catalog `item_id`):

```python
def test_cards_rotate_one_to_sixteen_across_takeaway_and_dine_in(svc): ...
    # 17 orders alternating "takeaway"/"at_table" (table "05") -> cards [1..16, 1]
def test_a_retried_checkout_keeps_its_card(svc): ...
    # same token + checkout_id twice -> same order id and same vibrating_card
def test_the_rotation_survives_a_restart(svc, tmp_path): ...
    # 3 orders, then a new Service on the same db path -> next order gets card 4
def test_two_services_on_one_database_hand_out_distinct_cards(svc): ...
    # a second Service on the same db path (the API and MCP processes share one file);
    # alternate orders between the two -> cards 1, 2, 3, 4 with no repeat
def test_orders_before_cards_do_not_break_the_rotation(svc): ...
    # insert an order row whose data has no vibrating_card (latest row) -> next order still
    # continues from the last numbered order
def test_payment_reports_the_card(svc): ...
    # svc.payment(token, order["id"])["vibrating_card"] == order["vibrating_card"]
```

- [ ] **Step 2:** Run `.venv/bin/pytest -q tests/test_vibrating_card.py` — Expected: FAIL (`KeyError: 'vibrating_card'`).

- [ ] **Step 3: Implement** `CARD_COUNT = 16` and `_next_card(db) -> int` in `trendcoffee/service.py`: read the latest order that has a card (`SELECT json_extract(data,'$.vibrating_card') FROM orders WHERE json_extract(data,'$.vibrating_card') IS NOT NULL ORDER BY rowid DESC LIMIT 1`), return `last % CARD_COUNT + 1`, or 1 when none. In `submit`, add `vibrating_card=_next_card(db)` to the new order's `order.update(...)` (same write transaction, after the `existing` early return). In `payment`, add `"vibrating_card": order.get("vibrating_card")` to every returned dict (wrap the existing body rather than editing each `return`).

- [ ] **Step 4:** Run `.venv/bin/pytest -q tests/test_vibrating_card.py tests/test_service*.py tests/test_kiosk_runtime.py` — Expected: PASS.

- [ ] **Step 5: Commit** `feat: assign a rotating pickup card to every new order`.

### Task 2: Card in the merchant order description

**Files:**
- Modify: `trendcoffee/merchant.py` (`order_description`, new `CARD_NOTICE`)
- Test: `tests/test_vibrating_card.py`

**Interfaces:**
- Consumes: `order["vibrating_card"]`, `order["fulfillment"]`, `order["table_label"]` (Task 1).
- Produces: `order_description(order, *, legacy=False) -> str` (signature unchanged).

- [ ] **Step 1: Write the failing tests:**

```python
def test_dine_in_description_names_card_and_table():
    order = {"id": "abc", "vibrating_card": 7, "fulfillment": "at_table", "table_label": "05",
             "order_note": "ít đá"}
    assert order_description(order) == (
        "AI ORDER\nTHẺ RUNG SỐ 7 · Bàn 05\n"
        "Khi thẻ rung, mời quý khách đến quầy nhận món. Cảm ơn quý khách!\nKiosk abc\nít đá")
def test_takeaway_description_says_mang_di(): ...   # second line "THẺ RUNG SỐ 7 · Mang đi"
def test_dine_in_without_table_label_names_only_the_card(): ...  # "THẺ RUNG SỐ 7", no "Bàn"
def test_orders_without_a_card_keep_todays_description(): ...
    # == "AI ORDER\nQuý khách vui lòng đợi khoảng 15 phút và nhận món tại quầy thanh toán. "
    #    "Cảm ơn quý khách!\nKiosk abc"
def test_validate_accepts_a_carded_guest_order_echo(): ...
    # reuse the existing validate fixture pattern from the merchant tests: remote without
    # "branch", description == order_description(carded order) -> no MerchantError
```

- [ ] **Step 2:** Run the new tests — Expected: FAIL.
- [ ] **Step 3: Implement** in `order_description`: when `order.get("vibrating_card")` and not `legacy`, build the first lines as `"AI ORDER\nTHẺ RUNG SỐ {n}" + (" · Mang đi" | " · Bàn {table}" | "") + "\n" + CARD_NOTICE` with `CARD_NOTICE = "Khi thẻ rung, mời quý khách đến quầy nhận món. Cảm ơn quý khách!"`; otherwise today's text. `validate` needs no change (it compares against `order_description(order)`).
- [ ] **Step 4:** Run `.venv/bin/pytest -q tests/test_vibrating_card.py tests/test_merchant*.py tests/test_invoice_printing.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: put the pickup card in the merchant order description`.

### Task 3: Card header on the printed invoice

**Files:**
- Modify: `trendcoffee/printer.py` (`prepare`, new `card_header`, raster-strip helper), `trendcoffee/invoices.py` (`_prepare` passes the card)
- Test: `tests/test_printer.py`, `tests/test_invoice_printing.py` (fake `Printer.prepare` gains `card=None` and records it)

**Interfaces:**
- Consumes: `order["vibrating_card"]` (Task 1).
- Produces: `card_header(card: int) -> str` returning `f"THẺ RUNG SỐ {card}"`; `CupsPrinter.prepare(pdf: Path, directory: Path, card: int | None = None) -> Path`.

- [ ] **Step 1: Write the failing tests** in `tests/test_printer.py`:

```python
def test_a_carded_invoice_starts_with_the_card_as_a_raster_header(tmp_path):
    # fake run: "magick" -> writes P4 8x2 header PBM to its output path (last arg,
    # "pbm:" prefix stripped); "pdftoppm" -> one 8x2 page as in the existing raster test.
    # prepare(..., card=7):
    #   magick args contain "label:THẺ RUNG SỐ 7" and "-extent" with width 8
    #   payload has no b"AI ORDER," and no b"QUY KHACH"
    #   first raster strip is the header bitmap, then the page bitmap
def test_a_failing_header_render_raises_instead_of_printing_without_the_card(tmp_path):
    # fake magick raises subprocess.CalledProcessError -> prepare raises
@pytest.mark.skipif(shutil.which("magick") is None, reason="ImageMagick not installed")
def test_the_real_header_render_fits_the_paper(tmp_path):
    # real CupsPrinter("GP-C180I").prepare with pdftoppm faked; the header strip is 576
    # dots wide (stride 72) and contains ink
```

In `tests/test_invoice_printing.py`: `test_the_invoice_worker_passes_the_order_card_to_the_printer` — a paid carded order prints with `Printer.prepared_cards == [order["vibrating_card"]]`.

- [ ] **Step 2:** Run `.venv/bin/pytest -q tests/test_printer.py tests/test_invoice_printing.py` — Expected: the new tests FAIL; existing pass.
- [ ] **Step 3: Implement.** In `prepare`, when `card` is set: render via `self._command(["magick", "-background", "white", "-fill", "black", "-font", "Noto-Sans-Bold", "-pointsize", "56", f"label:{card_header(card)}", "-gravity", "center", "-extent", f"{self.width_dots}x", "-monochrome", f"pbm:{directory / 'header.pbm'}"])` (verified 2026-11-06: 576×78 with correct diacritics), and write it with the same strip writer used for pages (extract the existing PBM-read/trim/strip loop into one helper used for header and pages). Without `card`, keep the ASCII `AI_ORDER_NOTICE` exactly as today. `_command` runs with `LC_ALL=C`; pass the label as UTF-8 (verify ImageMagick reads it correctly under `LC_ALL=C` in the real-render test; if not, override `LC_ALL` to `C.UTF-8` for that call only). In `InvoiceWorker._prepare`, call `self.printer.prepare(pdf, directory, card=order.get("vibrating_card"))`.
- [ ] **Step 4:** Run `.venv/bin/pytest -q tests/test_printer.py tests/test_invoice_printing.py` — Expected: PASS. Then write one preview to the scratchpad (no `lp`): run `prepare` on a fixture PDF with `card=7`, convert `header.pbm` to PNG and look at it.
- [ ] **Step 5: Commit** `feat: print the pickup card as the invoice header`.

### Task 4: Trend says the card in the QR sentence

**Files:**
- Modify: `trendcoffee/session_notices.py` (`qr_sentence`, `QR_SENTENCE` kept for no-card), `trendcoffee/kiosk.py` (`kiosk_checkout` both returns, `kiosk_payment`, `guest_situation` → nudge), `trendcoffee/codex_voice.py` (the native voice instructions near lines 18–21/32–35 and the Codex instructions near line 155), `trendcoffee/claim_guard.py` (`UNVERIFIED_PAID_NOTE`)
- Test: `tests/test_vibrating_card.py`, `tests/test_voice_tone.py`, `tests/test_spoken_warnings.py`

**Interfaces:**
- Consumes: `order["vibrating_card"]`, `Service.payment(...)["vibrating_card"]` (Task 1).
- Produces: `qr_sentence(card: int | None) -> str`; tool results gain `"qr_reply": str` whenever `"qr_available": True`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_qr_sentence_names_the_card():
    assert qr_sentence(7) == "Bạn quét QR trên màn hình để thanh toán nhé, thẻ rung của bạn là số 7."
    assert qr_sentence(None) == "Bạn quét QR trên màn hình để thanh toán nhé."
def test_checkout_result_carries_the_exact_qr_reply(svc): ...
    # host from tests/test_claim_guard.delegating_host (merchant fixture with a QR):
    # kiosk_checkout result["qr_reply"] == qr_sentence(result["vibrating_card"])
def test_payment_tool_carries_the_qr_reply(svc): ...   # kiosk_payment while pending
def test_voice_prompts_tell_trend_to_say_the_qr_reply(): ...
    # "qr_reply" in VOICE_INSTRUCTIONS and in the Codex developer instructions;
    # "thẻ rung của bạn là số" appears as the example in both
```

Update `tests/test_voice_tone.py` (`QR_LINE` assertions) and `tests/test_spoken_warnings.py` (nudge for `awaiting_payment` with a carded order contains `qr_sentence(card)`).

- [ ] **Step 2:** Run those test files — Expected: new tests FAIL.
- [ ] **Step 3: Implement.** `qr_sentence` in `session_notices.py`. In `kiosk.py`, add `"qr_reply": qr_sentence(order.get("vibrating_card"))` next to each `qr_available` that is true (checkout: from the order; payment: from `payment["vibrating_card"]`). Rewrite the QR rule in both prompts to: when `qr_available=true` for a pending payment, the entire final reply is exactly the tool result's `qr_reply` (example: `Bạn quét QR trên màn hình để thanh toán nhé, thẻ rung của bạn là số 7.`); keep "no preamble, summary or question" and "do not repeat the order, total, fulfillment, table number". Same wording change in `UNVERIFIED_PAID_NOTE` and the `awaiting_payment` nudge (`guest_situation` passes the card through its facts so the nudge quotes `qr_sentence(card)`). Keep native and Codex instructions aligned (CLAUDE.md rule).
- [ ] **Step 4:** Run `.venv/bin/pytest -q tests/test_vibrating_card.py tests/test_voice_tone.py tests/test_spoken_warnings.py tests/test_claim_guard.py tests/test_kiosk_runtime.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: Trend names the pickup card when the QR is ready`.

### Task 5: Big card number on the kiosk payment panel

**Files:**
- Create: `frontend/src/vibratingCard.ts`, `frontend/src/vibratingCard.test.ts`
- Modify: `frontend/src/types.ts` (`Payment.vibrating_card?: number | null`, `Quote`/`Order` `vibrating_card?: number`), `frontend/src/components/PaymentQr.tsx` (new optional prop `card?: number`), `frontend/src/components/OrderDialogs.tsx` (pass `card={order.vibrating_card}`), `frontend/src/index.css` (`.payment-card-number`)

**Interfaces:**
- Consumes: `vibrating_card` on order and on `api.payment` results (Task 1).
- Produces: `shownCard(card?: number | null, payment?: Payment | null): number | null`.

- [ ] **Step 1: Write the failing test** `vibratingCard.test.ts`: `shownCard(7, null) === 7`; `shownCard(undefined, { status: 'pending', vibrating_card: 3 }) === 3`; `shownCard(undefined, { status: 'pending' }) === null`; values outside 1–16 or non-integers → `null`.
- [ ] **Step 2:** `cd frontend && npx vitest run src/vibratingCard.test.ts` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `shownCard`, then in `PaymentQr` render `<div className="payment-card-number" aria-label={t('Thẻ rung số') + ' ' + n}>{n}</div>` right under the `<h3>`, for any status, when `shownCard(card, payment)` is not null. Nothing else in the panel changes. CSS: very large bold numeral (about 96px, line-height 1, centered); add the `'Thẻ rung số'` translation (`'Pickup card'`).
- [ ] **Step 4:** `cd frontend && npm test && npm run lint && npm run format:check && npx tsc -b && npm run build` — Expected: all pass; build updates `trendcoffee/static`.
- [ ] **Step 5: Commit** `feat: show the pickup card number on the payment panel` (include rebuilt `trendcoffee/static`).

### Task 6: Docs, full verification and deployment

**Files:**
- Modify: `CLAUDE.md` (the two QR-sentence rules), `docs/evals/qr-checkout-flow.md`, `docs/PROGRESS.md` (new dated entry)

- [ ] **Step 1:** Update the QR rule text in `CLAUDE.md` and `docs/evals/qr-checkout-flow.md` to the carded sentence (old sentence only for orders without a card); add a PROGRESS entry: what changed, tests, "paper output not yet checked by the user".
- [ ] **Step 2:** Run the full suites: `.venv/bin/pytest -q --continue-on-collection-errors` (only the known environment-only failures may remain: browser tests, numpy imports), ruff check/format, frontend checks. Compare failures with `main` if any new one appears.
- [ ] **Step 3: Commit** `docs: pickup card rules`, push the branch, open a PR (body ends with the Claude Code line); do not merge without the user's request.
- [ ] **Step 4 (only when the user asks to deploy):** when `/api/kiosk/status` shows `session_active=false`, restart the API (`TREND_STAFF_TOKEN='TREND_STAFF'`) **and** the Codex-launched `trendcoffee mcp` processes (see PROGRESS 2026-11-04 "stale MCP invoice worker"; ask the user before stopping them), then have the user reload the kiosk page and check one printed receipt on paper.
