# Trend Coffee Kiosk

React + TypeScript + Vite, Tailwind CSS, shadcn/ui (Radix) and local Vietnamese fonts. The existing FastAPI service owns prices, quotes, sessions and order state.

```bash
npm ci
npm run dev       # http://127.0.0.1:5173; /api proxies to FastAPI :8080
npm run test      # reducer regressions
npm run lint
npm run format:check
npm run build     # emits into ../trendcoffee/static, preserving staff console
```

Start FastAPI from the repository root with `uv run trendcoffee serve`. The Python wheel includes the built kiosk, so Node is needed only for frontend development/builds. Rebuild after editing `src/`.

`public/menu-images.json` records original public image URLs. To refresh downloaded WebP assets from a previously fetched public consumer menu:

```bash
uv run --with pillow python frontend/scripts/sync-images.py --menu /path/to/public-menu.json
```

Run that command from the repository root. Asset refresh is independent of the backend catalog freshness check; do not infer availability from an image. Two products have no published photo and use a neutral placeholder.

Guest capability stays in memory; reload or “Khách tiếp theo” starts a new guest. After the first user interaction, the idle warning appears at 90 seconds and the session resets at 120 seconds without further interaction. An untouched screen does not repeatedly recreate guest sessions. Ending a screen session does not cancel submitted requests. Progress is refreshed when opened and on demand. No POS or payment connection is implied.
