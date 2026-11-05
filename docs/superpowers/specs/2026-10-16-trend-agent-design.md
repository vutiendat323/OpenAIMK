# Trend Coffee service system

## Intent and authorization
The user requested implementation of the proposed customer-service agent, including Skill, Workflow, Memory, RAG, Progress and MCP, with fast and correct customer responses. This spec makes those requirements executable. Implement locally in this session; no production orders or outbound customer messages.

## Choice
Use one Python 3.12+ process, FastAPI, SQLite WAL/FTS5 and the official MCP SDK. A vector database and agent swarm add remote calls and operational cost before a corpus warrants them. Plain static HTML provides a local review console. Runtime facts come from sourced knowledge and structured catalog tools; optional OpenAI synthesis is read-only and bounded by timeout. The core works without API keys.

## Boundaries
- One business service backs both HTTP and MCP; no duplicated transaction rules.
- Import only verified public facts. Published UI capabilities are labeled separately from confirmed operating policies. Catalog snapshots never claim live stock.
- Integer VND pricing, server-calculated totals, valid options per line, immutable confirmation token and idempotent request submission.
- Default mode is a local request queue, not a connected POS. A submitted request is pending staff acceptance. Staff-only transitions require a configured bearer secret. Payment and fulfillment states are separate.
- Opaque session capabilities isolate customers. Preferences require explicit consent; deletion is immediate. Do not store complete raw conversations or use shared personalized answer caches.
- FTS retrieval normalizes Vietnamese accents and returns source/date/evidence labels. Only approved knowledge is searchable. Web ingestion is an explicit CLI action, never part of a customer turn.
- Tool execution validates arguments and authority. LLMs never decide money, execute payments, acknowledge POS acceptance, or update staff states.

## Latency and progress
Targets, not promises: local API/chat p95 < 250 ms and local retrieval p95 < 100 ms on the development machine. Benchmark complete in-process HTTP requests and concurrent sessions; report sample count and p50/p95/p99. Optional LLM response timeout 4 s, bounded output and deterministic fallback; remote latency is separate. Persist workflow events for order/handoff progress; expose aggregate timings without customer content.

## Deliverables and checks
Runnable API and local console; stdio MCP; project-local discoverable skill; workflow contract; sourced knowledge importer; session memory; event log; operator endpoints; benchmark and regression tests. Validate duplicate submissions, changed prices, cross-session isolation, payment authority, sold-out items, unsupported options, stale/unapproved retrieval, request delivery wording and memory consent/deletion. Test MCP over a real stdio client and smoke-test the console. Preserve existing AGENTS.md per the user's original instruction.
