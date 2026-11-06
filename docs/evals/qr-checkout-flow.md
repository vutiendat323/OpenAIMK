# Short order-to-QR service flow — 2026-11-03

Customer request: stop repeated sales questions and confirmations; when the drink
and fulfillment are known, place the correct cart and show the bank-payment QR.
A ready QR should produce only “Bạn quét QR trên màn hình để thanh toán nhé.”

Update 2026-11-06 (user decision): every new order has a pickup card 1–16, and the exact
sentence names it: “Bạn quét QR trên màn hình để thanh toán nhé, thẻ của bạn là số N.”
The kiosk tools return it as `qr_reply`; orders made before cards keep the sentence above.

## Findings and changes

- The supplied historical Latte trace searched the catalog, then checked out
  without adding Latte. Menu lookup does not change a cart. Instructions now
  require adding/updating every newly requested item and checking the returned
  actual cart before checkout. Exact, fresh catalog items can be added directly.
  Existing authorized touch selections remain in the cart; a new spoken item is
  not a reason to silently remove them. Guest resets remain unchanged.
- “Chọn giúp/chọn cho mình ... mang đi” delegates choosing and ordering a suitable
  actual item. With clear constraints and fulfillment, choose/add/checkout in
  that turn without asking “bạn chốt không?”. Advice-only “gợi ý” still does not
  authorize an order. Missing critical information or no suitable actual item
  remains a legitimate reason to ask a concise question.
- A payment read with no submitted order returned `payment_connected=false`,
  even with a configured merchant adapter. It also omitted the pending cart.
  A real Luna/medium fixture reproduced the agent stopping after this read
  despite Latte and takeaway already being selected. The result now uses the
  configured adapter for that flag when there is no order, and includes the
  guest's `pending_cart`. The read itself still does not place an order.
  `payment_connected` means configured adapter, not a fresh network-health proof.
- Pending QR-ready replies now take precedence over general response-length
  guidance: exactly the short QR instruction, without order recap or confirmation.
  Merchant-verified paid status instead gets “Đơn đã được thanh toán.”, without
  another payment/order. (Superseded 2026-11-05: the paid reply is now worded
  naturally by Trend, not this fixed sentence; see PROGRESS.md.) Payment-status questions refresh through `kiosk_payment`;
  cached progress alone is not a fresh payment check.
- Native voice stays within Trend Coffee and delegates uncertain drink wording
  instead of treating it as an apartment-search conversation. Fulfillment and
  payment answers are delegated with their earlier context.
- The historical `local_queue_only` orders cannot provide a merchant QR. Current
  API mode was verified as `merchant_api`; a read-only live table request returned
  100 tables, 92 available at 07:31 UTC. Merchant connection errors are described
  briefly, rather than suggesting takeaway as a cure for an offline payment API.
  No old local order was converted into a merchant order.

## Evidence

Repeatable semantic probe:
`PYTHONPATH=. .venv/bin/python output/checkout-flow/evaluate.py fixed choose`
(substitute `pay`, `latte`, `advice`, `view`; paid case label `final-refresh`).
It uses real GPT-6-Luna / medium, Fast disabled, with a temporary database and
`httpx.MockTransport` merchant. It never connects to the shop for an order/payment.

| Case | Observed result |
| --- | --- |
| Delegated ice-cream choice, takeaway | Actual Affogato selected, added and checked out; one fixture QR, no question; exact QR-only sentence. |
| “Thanh toán giúp tôi”, existing Latte/takeaway cart | `kiosk_payment` → `kiosk_checkout`; one QR, no repeated item/fulfillment question. |
| Add Latte, dine in, with an earlier touch pastry selection | Latte actually added before checkout; earlier authorized pastry preserved; live fixture table auto-selected; one QR, no table-number question. |
| Advice only | One actual menu suggestion; no cart/order mutation. |
| View existing QR with a pending cart | Payment read only; no new order. |
| Already paid at merchant | Fresh payment read; paid response, QR hidden; zero new order posts. |

The initial choose probe already placed an order but failed the concise-response
check. Initial pay probe produced no order/QR despite a ready cart. Adding cart
context alone exposed the misleading connection flag; correcting both contract
and instructions made the pay case pass. Paid-status evaluation first used stale
cached progress; explicit fresh payment routing corrected it. Artifacts are in
`output/checkout-flow/` with before/after/fixed labels.

- 93 focused backend tests pass, covering the new connected/disconnected payment
  contract, cart/lifecycle, merchant validation, live tables, menu reasoning and
  native model/startup configuration. New contract assertions failed before fixes.
- 2 built-browser QR tests pass at desktop/mobile, including merchant image,
  expiry, paid settlement, no duplicate checkout, and guest reload. Old test
  selectors were updated for the existing closed sidebar and checkout dock;
  no frontend product source changed.
- Changed Python Ruff lint and formatting pass. Independent review's important
  paid-without-QR ambiguity was fixed and re-reviewed.
- API restarted only after guest/microphone idle: 477443 → 496852, original
  environment and merchant mode preserved. Visual/avatar remained 449662/449682.
  Health: ok / merchant_api / live_pos_connected=true. Luna medium remains non-Fast.

These are individual reasoning and browser fixture checks, not a latency SLA,
a physical voice-recognition guarantee, a bank scan or a real merchant settlement.
The model runs took roughly 5–12 seconds for the final cases; native speech/audio
latency was not measured again in this task.

## Self-evaluation

Applied `agent-self-evaluation`: accuracy 4/5 (before/after failures and assertions;
real bank acceptance untested), completeness 4/5 (reported flow and read-only/paid
countercases covered; physical voice follow-up remains), clarity 4/5 (QR-only
success versus actual error/paid distinction), actionability 4/5 (activated API
and repeatable artifacts), conciseness 4/5 (two production files, small additive
contract). Overall 4.0/5. Highest-impact next check: customer visual/voice acceptance
on the current merchant-connected kiosk. Would the user agree: the flow now avoids
extra confirmation in the tested cases while retaining real order/payment evidence.
