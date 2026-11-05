# Merchant category rail — 2026-10-27

The kiosk previously hardcoded four category shortcuts plus “Tất cả”, including
renaming merchant “món trà” to “Trà trái cây” and “món bánh” to “Bánh ngọt”. It
omitted other merchant categories, and dropped product best-seller/new flags.

## Source and behavior

Read-only verification of the public merchant website confirmed:

- [`GET /api/latest/catalogs`](https://trendcoffee.net/api/latest/catalogs)
  supplies ordered IDs/names: sinh tố, món ăn, nước giải khát, cà phê, món bánh,
  giá tùy chỉnh, bia/ rượu vang, món trà.
- The official customer menu bundle
  [`index-1sPxsUUR.js`](https://trendcoffee.net/assets/index-1sPxsUUR.js)
  prepends “Tất cả”, “Bán chạy” and “Món mới”; the latter two use product
  `isTopSell` and `isNew`, rather than invented catalog groups.
- The current branch/day public menu contains 51 approved variants: four marked
  top seller and one new. Empty categories do not authorize adding products from
  the general products endpoint.

`sync-public` now fetches both public menu and category endpoints. Product rows
retain category IDs and the two flags. The same ingestion transaction replaces
the ordered category snapshot and product rows. A small `menu_categories` table
is added with `CREATE TABLE IF NOT EXISTS`; existing guest/order tables remain.
`Service.menu_search` reads both tables in one snapshot and includes categories
even when a search finds no products. Legacy imports use their own recorded
category metadata or, if absent, their actual product groups.

The UI uses merchant IDs for category filtering, preserves source order and
names (trim trailing spaces and capitalize the first letter for display), and
uses the real flags for best-seller/new filters. Icon mappings affect presentation
only; an unfamiliar category gets a generic icon and still appears. Categories
are refreshed with the existing six-hour menu sync, not on each category click.
Existing tabs need reload after a sync.

## Verification

Witnessed the six backend and three Chromium regressions fail before the fix.
They cover source IDs/flags, ordered empty categories, dynamic category changes,
atomic rollback, the actual sync endpoint, legacy imports, and real category/tag
filtering at 1440/768/375 px. The browser fixture adds “Nước theo mùa” without
changing UI code, proving the list is data-driven.

Final root suite: **276 passed in 71.12 seconds**; frontend: **21 passed**.
Production build, Ruff, oxlint, Prettier and patch whitespace checks passed.
Independent read-only review found no material defects; temporary-database probes
also verified existing seed import and migration from the old schema. An optional
coverage gap remains for exercising ID-less legacy data through Chromium; its
backend fallback and normal browser path are separately covered.

Evidence: `output/merchant-categories-public.json`,
`output/merchant-categories-pytest.txt` and browser fixture screenshots
`output/merchant-categories-{1440,768,375}.png`. Tests/probes use disposable
databases and public GETs; no real order, payment or print request was created.

The production local database was refreshed using `trendcoffee sync-public`
after validation; the merchant itself was only read. Runtime verification is
recorded separately in `output/merchant-categories-runtime.json`.

Deployed Visual PID 258073 and API PID 258113 listen on 9877/8080; health is
`ok` and native voice is prepared. Chromium loaded the deployed assets and actual
`/api/menu` at 1440/768/375 px, with only guest creation and voice-control requests
intercepted to avoid affecting a real guest. All 11 choices match merchant order;
counts passed for 51 total, 4 best sellers, 1 new, 15 coffees, 10 cakes, 17 teas,
9 smoothies and all four empty groups. No page errors or horizontal overflow.
Screenshots: `output/merchant-categories-deployed-{1440,768,375}.png`.

## Self-evaluation

| Axis | Score | Evidence / improvement |
| --- | --- | --- |
| Accuracy | 4 | IDs/order/flags verified against public GETs and official UI code; categories remain a synchronized snapshot rather than per-click live data. |
| Completeness | 4 | Source → persistence → API → filters covered; ID-less legacy browser coverage could be added if that deployment mode is used. |
| Clarity | 4 | Exact names replace aliases and empty categories show no invented products; longer category names wrap in the narrow rail. |
| Actionability | 4 | Local snapshot refreshed and production assets built; existing tabs require reload. |
| Conciseness | 4 | Small ingestion/API/UI change; separate metadata storage is needed to retain empty merchant groups and their order. |

Overall 4.0/5. Self-check: the displayed categories now come from merchant data;
catalog membership and best-seller/new flags are not guessed from drink names.
