# Merchant checkout and multiple drinks

The kiosk launcher and project MCP configuration enable `TREND_MERCHANT_ENABLED=1`. Direct `trendcoffee serve` remains local unless that variable is set. Set it to `0` before starting the launcher for local-only operation. Environment changes require restarting the relevant service/MCP process.

## Customer flow

1. For preferences/recommendations, reason over the full catalog supplied to native sessions, or read MCP `get_menu()` without a query. Select suitable actual item IDs and display them with `kiosk_menu(item_ids=[...])` / `get_menu(item_ids=[...])`. Literal keyword overlap is unnecessary. For named drinks, queries remain a convenience: resolve all requested drinks independently. Uncertain results include the full `catalog`; review it before concluding no item fits. Ask briefly only when the intended specific drink remains unclear.
2. Add all resolved lines in one `kiosk_cart(action="add", lines=[...])`, or pass all lines to MCP `checkout_order`. Batch validation is atomic; quantities/options/notes remain attached to each item. `lines[].note` holds an optional item request (300 characters); `order_note` holds a whole-order request (1000 characters). Native voice uses `kiosk_order_note` for the latter. Distinct notes keep otherwise identical cups separate. Existing cart rows have stable keys while editing. Notes travel to merchant item `note` fields and the exact kiosk order description.
3. Once requested drinks and fulfillment are known, place the cart immediately with `kiosk_checkout` or `POST /api/checkout` (`checkout_order` for MCP). For `at_table` without a customer-specified table, select the first `status=available` table in the live merchant list. Touch selection fills the table input; native fulfillment selects it on the server; direct checkout/draft resolves it when `table_label` is omitted. Preserve explicit table choices and the durable selection on checkout retries. No available table or failed live data blocks automatic selection; offer takeaway for the customer to choose. The initial order request or the single **Thanh toán** button authorizes checkout without a second confirmation or payment-method selection. Product/table questions and browsing do not place orders or reserve tables.
4. Create one merchant order, retain its reference, retrieve its payment QR and show the original image. Customers scan using their bank app. Payment polling reads only that guest's stored merchant reference.
5. Hide QR after expiry/cancellation/payment. Expiry hides the image but allows two minutes of reconciliation polling plus manual refresh. Only merchant evidence marks the merchant payment paid.
6. When configured, the independent [invoice worker](invoice-printing.md) waits for merchant payment completion and the official PDF, then prints once. Closing the page or ending the voice session does not cancel the print job.

All customer surfaces are inline: product options, cart, order/QR and progress. There are no review, success, payment or reset dialogs/sheets. The returned payment is rendered immediately; polling starts three seconds later instead of delaying QR display with another GET. A next-guest action clears the screen directly. An idle notice does not block interaction. The text-chat shortcut and the entire support/preferences panel have been deleted, including their frontend state, API wrappers and styles.

The order rail stays on the right at desktop, tablet and phone sizes. Product rows
show centered thumbnails, names, unit prices and quantity controls; totals multiply
unit price by quantity. Click a product thumbnail/name to expand its note editor;
the removal icon stays visible beside quantity controls. The order note disclosure
is below the fulfillment caption.
The checkout action and subtotal remain at the bottom while items scroll, with
whole-rail scrolling on short screens. QR/result display expands the available
width (full row on small screens), keeping the original merchant QR readable.
The former floating mobile cart bar is replaced by this persistent rail.

Touch checkout uses one HTTP request containing cart lines, fulfillment and a stable `checkout_id`. Its session-scoped quote/order survives retries; reusing an ID with a different payload fails. Native checkout likewise retains a stable key for the current cart and returns the existing order if checkout is repeated after the cart was submitted. Server pricing and merchant QR validation still run; there is no transcript confirmation grammar or post-quote turn counter.

## Verified public contract

Read-only inspection on 2026-10-17 found these calls in the official [application bundle](https://trendcoffee.net/assets/index-DmriD68d.js) and [payment screen](https://trendcoffee.net/assets/index-DW_5KOyj.js):

- `POST /api/latest/orders/public`: `type` (`take-out`/`at-table`), branch, table slug, `orderItems` containing `variant`, `quantity`, `promotion`, `note`; response reference `result.slug`.
- `GET /api/latest/tables?branch=ba9355f797`: names map to merchant table slugs. Fresh read-only verification on 2026-10-26 confirmed names, slugs, locations and `status` values `available`/`reserved`. HTTP `/api/tables`, MCP `get_tables` and native `kiosk_tables` read this endpoint on every call; optional `table_label` filters one table. Responses include `fetched_at`, counts and `first_available`. Only `available` means free; unknown states remain unconfirmed. `reserved` does not prove someone is seated. Selection is not a reservation and can change afterward. Local-only mode returns `live_tables_unavailable` for status queries and retains manual table entry.
- `POST /api/latest/payment/initiate/public`: `{orderSlug, paymentMethod: "bank-transfer"}`.
- `GET /api/latest/orders/{slug}`: retrieve order data and `payment.qrCode`, `payment.amount`, payment/order status. A slug-only creation response is followed with this GET.

The adapter verifies the merchant reference, item IDs/quantities and subtotal before displaying payment, and checks payment amount/method. When the response includes a branch, it must match the submitted branch. The guest order response observed on 2026-10-19 omits this field; in that case it must echo the exact `Kiosk <local order UUID>` description and fulfillment type sent when creating the order. An explicitly incorrect or null branch still fails validation. It supports merchant PNG/JPEG data images or images fetched from exact merchant-owned hosts, with size/redirect restrictions. It does not generate its own bank account or QR. The 15-minute window comes from the merchant's [payment instructions](https://trendcoffee.net/payment-instructions).

## Retry and recovery

The local quote has one durable order record. Creation is claimed before the network POST; repeating the same quote never creates another merchant order. If creation response is lost, `uncertain` requires staff reconciliation. Once a merchant reference exists, read-only refreshes can recover QR/status; they never create a replacement order or repeat payment initiation. Mismatched amounts/items require staff review and suppress QR. Concurrent delayed reads cannot overwrite merchant-verified paid status.

## Validation boundary

Automated HTTP and browser checks use isolated databases and `httpx.MockTransport`; they send no real merchant orders or payments. Public GETs and frontend code inspection verify the observed contract, not a completed merchant checkout. A permitted live order, actual QR decoding in a bank app, and real settlement remain field acceptance steps.
