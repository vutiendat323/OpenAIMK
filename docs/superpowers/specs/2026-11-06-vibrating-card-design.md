# Vibrating pickup cards for dine-in orders — design

Date: 2026-11-06. Status: agreed with the user in conversation (updated after the builder check); awaiting approval of this document.

## Intent

The shop has a set of 16 self-service vibrating pickup cards (pagers) numbered 1–16, with
a charging base; the FPOS F16 shown by the user is only an example model. When a meal is
ready, staff make the right card vibrate themselves on the pager base, and the guest comes
to the counter. Today the kiosk does not tell anyone which card belongs to which order.

The kiosk should give every order a card number, put it where staff and guest see
it (merchant order/printed invoice, kiosk screen, Trend's voice), so staff can map an order
to a card and the guest knows which card is theirs.

## Decisions made by the user

1. **Software only records the card number.** It never triggers vibration; staff do that
   by hand on the pager base. No hardware integration.
2. **Every order gets a card, takeaway (`takeaway`, "mang đi") as well as dine-in
   (`at_table`).** (The user first said takeaway needs no card, then changed this on
   2026-11-06: "update provided card for order 'mang đi'".) Every new order advances the
   counter.
3. **The kiosk chooses the card, not the guest,** by rotating 1 → 2 → … → 16 → 1. It does
   not track whether a card is busy and does not look at order status. Nobody tells the
   kiosk a card was returned. (Rotating through 16 keeps reuse far apart in practice.)
4. **For dine-in, the table is still chosen as today** (automatically, first available live merchant
   table, or the table the guest names). The card is in addition to the table.
5. **Printed invoice — two places.**

   a. **The kiosk's own bold header** (`printer.py`, printed above the merchant's PDF on
   every invoice; today `AI ORDER,QUY KHACH VUI LONG DOI 15 / NHAN MON TAI QUAY NHE`)
   becomes, for an order with card 7:

   ```
   THẺ RUNG SỐ 7
   ```

   in **Vietnamese with diacritics**, and **without the table**. This is the one place the
   card is sure to be on paper: nobody has verified that the merchant PDF prints the
   description (`docs/PROGRESS.md`, 2026-11-04). Orders without a card (made before this
   change) keep today's header.

   b. **The merchant order description — layout A** (the merchant prints it on the official
   invoice, if at all). For a dine-in order with card 7 and table 05:

   ```
   AI ORDER
   THẺ RUNG SỐ 7 · Bàn 05
   Khi thẻ rung, mời quý khách đến quầy nhận món. Cảm ơn quý khách!
   Kiosk <order id>
   <order note, if any>
   ```

   For takeaway *(my call, following layout A)*: the second line is `THẺ RUNG SỐ 7 · Mang đi`,
   the rest identical. Orders without a card keep today's description.
6. **Kiosk screen:** the card number alone, very large (e.g. a big "7"), in the payment
   panel in the sidebar. Nothing is written next to it: no "Thẻ rung của bạn" caption, no
   pickup instruction, no table line. (What happens to the panel's existing content is my
   call, under "How" below.)
7. **The fixed QR sentence includes the card.** Trend's entire reply when the QR is ready
   must be exactly:

   > Bạn quét QR trên màn hình để thanh toán nhé, thẻ rung của bạn là số 7.

   with the real card number, for every order that has a card (now all new orders). This
   replaces the earlier locked sentence "Bạn quét QR trên màn hình để thanh toán nhé."
   (CLAUDE.md, `docs/evals/qr-checkout-flow.md`, `codex_voice.py`, `claim_guard.py`,
   `session_notices.QR_SENTENCE`); that old sentence remains only for an order without a
   card.

## Goals

- Every new order has a card number 1–16, assigned once and stable for that order.
- Staff see the card on the printed invoice (bold header) and on the merchant order
  (description).
- The guest sees the number on the kiosk and hears it from Trend.

## Non-goals

- Triggering, pairing or monitoring the physical pagers.
- Tracking which cards are in use or returned; refusing orders when "all cards are busy".
- Letting the guest pick a card number.
- Changing table selection, payment verification, or how/when invoices are printed (only
  the header content changes).

## Anti-goals (failure even if it "works")

- A retry/idempotent re-checkout of the same order gets a different card number, or the
  merchant description no longer matches the order on retry (`merchant_order_mismatch`).
- Trend says a card number that is not the order's real card.
- The printed header shows broken/missing Vietnamese characters, or the old "đợi 15 phút /
  nhận món tại quầy" text for an order with a card.
- The counter restarts at 1 after an API restart and hands out numbers already in use.
- Any claim that the card has vibrated / the meal is ready.

## Constraints

- Business facts only from real tool results; the card number reaches Trend through the
  checkout/payment tool result, never invented.
- Preserve idempotent checkout (`checkout_changed` rules, stable checkout IDs) and the
  merchant description check on retries; existing orders without a card must still verify.
- Keep the native voice prompt and the role-bearing startup instructions aligned
  (`codex_voice.py`), and `claim_guard.py`'s QR handling consistent with the new sentence.
- Fixtures only in tests: no real merchant orders, payments or printer jobs. The printer's
  ESC/POS text mode is ASCII today, so the accented header most likely has to be printed as
  a raster image (like the PDF pages); verify with a generated payload/preview, not a real
  job. Paper output is to be checked by the user.
- Deployment: changing the description format needs both the API and the Codex-launched
  `trendcoffee mcp` processes restarted, or the second invoice worker marks new orders
  `merchant_order_mismatch` (happened 2026-11-04).
- Ruff/Prettier rules; build the frontend before viewing; restart only when the kiosk is idle.

## How (decided in conversation)

- Card assigned **when the order is created** (so it is in the merchant description before
  the QR is shown). An abandoned unpaid order still consumes its number; that is fine.
  Changing fulfillment (takeaway ↔ dine-in) on a retry does not matter for the card, since
  both get one.
- The counter **persists across restarts**.
- A retry of the same checkout keeps the same card.
- Where the card appears (user, 2026-11-06, replacing my earlier proposal that Trend repeat
  the card when payment is verified): **on the printed invoice header and in the order
  information staff see, i.e. the merchant order description/note.** Trend says the card in
  the QR sentence; the paid reply stays free-worded with no required card mention.
- The big number appears on the kiosk **from when the QR is shown** and stays through paid
  *(my guess; the user did not object)*.
- Payment panel *(my call; the user did not choose between keeping or removing the panel's
  current content)*: keep everything the panel shows today (QR, amount, expiry, "Đã thanh
  toán" with its confirmation line) and **add** the big number with no caption beside it.
  Removing the payment confirmation would delete the only on-screen proof of payment.

## Left to the builder

- Where the card is stored (e.g. a field such as `vibrating_card` on the quote/order data)
  and how the next number is derived (e.g. from the last dine-in order's card, or a stored
  counter), as long as it persists and stays stable for retries.
- Concurrency handling so two simultaneous dine-in checkouts do not get the same number.
- Card count as a constant (16) unless trivially configurable.
- Exact React placement/styling of the big number inside the existing payment panel.
- How the tool result exposes the card to Codex and how `claim_guard` verifies the sentence.
- Showing the card in the staff queue JSON (local queue mode) if it falls out naturally.
