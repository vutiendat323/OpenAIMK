# Product details popup — 2026-10-28

Replaced the inline ProductPanel with the existing Radix Dialog. The popup uses the user-approved synchronized public catalog, preserving catalog IDs, integer VND prices, published option values and checkout validation. Category, name, description, size and image come from the existing catalog/image map. Missing descriptions are omitted; the synthetic fallback description and staff customization note were removed.

The reference layout uses a large image at left and product information at right, title and unit price together, quantity controls on one row and a red full width rounded add button showing quantity × unit price. Category is hidden and the quantity label follows the selected UI language (`Số lượng` / `Quantity`). Phones stack the image above the information. The popup scrolls inside the viewport on short screens. Close, outside click and Escape dismiss it; focus returns to the opener. Adding closes the popup. Guest reset and assistant idle remove it. Existing sold-out, stale catalog and submission guards remain.

Validation:

- Production TypeScript/Vite build, oxlint and Prettier passed; 21 frontend tests passed.
- 19 affected browser tests passed in 72.65s: customer/staff journey, merchant fixture checkout, reference cart, settings and idle transitions. All use disposable services; no real merchant order/payment/printer action.
- After removing obsolete inline CSS and fixing back-button shape, reran the customer/staff journey: 1 passed in 9.10s, including popup geometry at 1440×1000, 851×605, 375×812 and 667×375; Escape/focus return; quantity/amount; cart/checkout and guest isolation.
- Light and dark axe audits in the final journey reported no violations. The dark audit also found a pre-existing empty-cart text contrast issue; its text now uses the dark muted palette.
- Screenshots: `.runtime/qa/product-popup-{1440,851,375,667}.png` and `.runtime/qa/product-popup-dark.png`. Desktop/mobile and dark screenshots inspected. Exact font/pixel identity to the photographed KFC UI is not claimed.
- Logs: `output/product-popup-browser.txt`, `output/product-popup-final.txt`, `output/product-popup-build.txt`.

Self-evaluation: accuracy 4/5 (real catalog values preserved; stock remains snapshot-based by design), completeness 4/5 (requested fields and modal behavior covered; no exact design-source font), clarity 4/5 (labels localized; screenshot review remains subjective), actionability 5/5 (built assets ready to serve), conciseness 4/5 (removed old panel CSS; retained existing component contract). Overall 4.2/5. Further visual refinement should use operator feedback on the installed kiosk.
