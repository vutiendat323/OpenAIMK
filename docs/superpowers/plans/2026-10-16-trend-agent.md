# Trend Coffee Agent Implementation Plan

> For agentic workers: use superpowers:executing-plans. Execute inline in the current session as requested by the user.

**Goal:** runnable low-latency service foundation with Skill, Workflow, Memory, RAG, Progress and MCP.
**Architecture:** shared Python domain service over SQLite; HTTP and stdio MCP adapters; optional bounded read-only LLM synthesis.
**Tech Stack:** Python 3.12+, FastAPI, SQLite FTS5, official MCP SDK, pytest, static browser console.
**Spec:** docs/superpowers/specs/2026-10-16-trend-agent-design.md

## Global constraints
Preserve AGENTS.md. No production writes. Local queue delivery is explicitly labeled. Separate staff authority, payment and order states. Prices are integer VND. Preference retention requires consent. No API key needed for core.

## Review focus
- Cross-session order/memory access is rejected.
- Repeated confirmation and concurrent requests produce one request per confirmation.
- Changed prices, unsupported choices and sold-out items reject submission.
- Unverified payments and undelivered handoffs never become success claims.
- Stale/unapproved knowledge and upstream model failures fail conservatively.

## Tasks
- [x] 1. Tests first: persistence, sourced retrieval, consent/isolation, quote/submit/state invariants in tests/test_service.py. Confirm missing implementation failure. Implement trendcoffee/store.py and service.py; rerun tests.
- [x] 2. Tests first: HTTP auth, validation, customer workflow, staff authority and timings in tests/test_api.py. Implement api.py, agent.py and optional model adapter. Check ordinary requests work without keys.
- [x] 3. Implement stdio MCP with the same service; real client initialize/list/call checks. Add repeatable CLI init/import/serve/benchmark commands and a lockfile.
- [x] 4. Create and behavior-test .agents/skills/trendcoffee-service/SKILL.md, workflow and memory documentation. Import public evidence conservatively and retain reproducible source metadata.
- [x] 5. Build static console for customer interaction, memory control, catalog/quote confirmation and progress. Browser smoke check. Run regression suite, concurrent latency benchmark and independent review; fix findings and document measured limits.
