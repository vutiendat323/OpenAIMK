# Order sidebar UI — 2026-10-28

The KFC reference layout is applied directly to the existing `Cart` inside
`#checkout-panel`. The mistakenly introduced full-screen `CartReview`, its state,
view class and navigation are removed.

- Header: My Order, Remove all, shared fulfillment buttons.
- Summary: total item count badge and subtotal.
- Horizontal item rows: photo, name, notes/customization, remove, quantities and
  line totals. Checkout is provided by the bottom dock; the sidebar has no duplicate
  payment button/price footer.
- Desktop retains assistant, category rail and menu alongside the right cart.
  Small phones keep the cart in the same document below the menu. Footer bag
  navigation scrolls to the existing cart.
- All changes use the existing cart dispatch and checkout function, including
  the submit lock, idempotency and QR handling. No extra review or route is used.
- Build/typecheck, oxlint, Prettier and changed-test Ruff passed. Browser evidence
  is in `output/cart-sidebar-corrected.png` and `output/cart-sidebar-{1279,375,320}.png`.
- The photographed kiosk supplies the layout reference; exact pixel equivalence
  to its perspective photos is not established.
