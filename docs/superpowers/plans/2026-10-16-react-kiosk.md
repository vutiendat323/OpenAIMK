# Trend Coffee React Kiosk Implementation Plan

User approved implementation after reviewing the kiosk design and React/TypeScript/Vite/Tailwind/shadcn stack.

## Accepted design and scope
- Forest green, warm ivory and terracotta; actual Trend Coffee product photos.
- Left category rail, central product grid, sticky order sidebar; touch-friendly portrait/mobile layout.
- Product dialog exposes only supported choices. Explicit pickup mode/table; server quote and confirmation remain authoritative.
- Assistant, support, consented preferences and progress remain accessible in sheets.
- Shared kiosk resets guest identity and private state for the next customer; warn before idle reset.
- Keep Python/FastAPI/SQLite/MCP. Build the SPA into existing package static assets; preserve staff console.
- No merchant writes, real payments, public publication or AGENTS.md changes.

## Tasks
- [x] Write failing reducer tests for line quantities/options, quote invalidation, session reset and late-response protection. Add browser acceptance for kiosk filtering, detail dialog, order and support journeys.
- [x] Scaffold frontend, install approved packages and shadcn components. Download/optimize primary product photos with a reproducible asset script.
- [x] Implement typed API client, reducer and kiosk UI, including immutable quote confirmation and isolated guest sessions.
- [x] Build into Python static output, test desktop/portrait/mobile, inspect screenshots, run axe and complete integration/regression/build checks.
- [x] Independent final review; address material findings; update README and progress ledger.

Review focus: asynchronous quote races, unsupported customizations, session/idle privacy, false payment success, touch reachability, stale catalog and offline errors. No Git metadata exists; work directly in the selected workspace and record evidence in docs/PROGRESS.md.
