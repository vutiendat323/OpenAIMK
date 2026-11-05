# Product popup implementation plan

**Goal:** Replace inline product details with a centered KFC reference styled popup using the existing synchronized public catalog, as confirmed by the user.

**Architecture:** Keep ProductPanel's existing item/options/onAdd contract and use the installed Radix Dialog. Preserve catalog IDs, size options, integer pricing, checkout validation, guest reset and lock guards. Remove synthetic fallback description and staff customization note.

**Files:** OrderDialogs.tsx owns accessible modal and product controls; App.tsx removes inline scrolling and hides the modal during idle; index.css owns responsive popup styling; translations.ts owns fixed UI labels. Existing browser journeys are adapted to close the modal before interacting with checkout.

- [x] Implement modal with image, category, title/price, published description/options, quantity and full width add button.
- [x] Verify close/Escape/focus return, amount calculation, reopening reset, viewport containment, dark theme and guest reset using isolated browser service.
- [x] Build/typecheck, lint/format and run affected browser journeys; record results.

**Constraints:** Data remains the current verified public snapshot; no live merchant mutations. No additional dependencies. Desktop two columns, phone one column with contained scrolling. Do not invent description or customization choices.
