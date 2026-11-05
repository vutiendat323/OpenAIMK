# Live merchant tables — 2026-10-26

The customer-facing assistant previously said it could not check free tables. The
merchant table endpoint was used only for name-to-slug lookup during checkout,
and every ordering surface required a manually entered table label.

## Implemented behavior

- HTTP `GET /api/tables`, MCP `get_tables` and native `kiosk_tables` read the
  branch-scoped merchant endpoint on every call. Optional `table_label` filters
  the current result. Responses include source URL, retrieval time, raw merchant
  status, availability, count and first available table. Unknown states are
  never treated as free. A missing/unreachable merchant produces a domain error.
- Choosing `at_table` automatically selects the first `status=available` table
  in merchant list order when none is specified. Touch fills the editable input;
  native tools update the shared state; direct HTTP/MCP quote/checkout resolves
  an omitted label. Explicit customer choices remain intact. Local-only mode
  retains manual table entry. A selection does not reserve a table.
- A status question reads current data without selecting a table or ordering.
  Native instructions and the customer-service skill require the live tool
  instead of guessing or claiming the capability is absent. Full/unreachable
  tables produce an honest answer; takeaway requires the customer's choice.
- Durable automatic selections survive lost-response checkout retries even if
  availability changes or the merchant becomes unreachable. Name matching
  accepts Vietnamese `Bàn` prefixes and leading zeroes, and uses real slugs.
- Late touch reads cannot overwrite a newer table edit, takeaway selection or
  next guest. With voice controlling the cart, blank/intermediate table-input
  edits remain drafts and are resolved at checkout.

## Evidence

Witnessed failing tests for missing routes/tools, missing-label auto-selection,
touch auto-fill, voice-controlled table edits and Vietnamese polite suffixes
before the respective fixes. Merchant tests use `httpx.MockTransport`; browser
tests use real Chromium against disposable local servers/databases.

Independent review found and reproduced two gaps: controlled multi-digit table
editing and treating “nhé”/“ạ” as table names. Both have failing-then-passing
regressions. The latter includes single-turn and follow-up fulfillment variants.

An actual Codex native login with Luna/medium exercised the production dynamic
tools against isolated merchant fixtures. All five scenarios passed:

1. Report two available tables and first table 7; select/order nothing.
2. After merchant status changes, freshly report table 7 as reserved.
3. Choose at-table without a label and select the remaining free table 5.
4. With no tables free, offer takeaway without switching fulfillment.
5. On merchant failure, say current table status could not be retrieved.

See `output/live-tables-native-agent.json` and reproduction script
`.runtime/live-tables-agent-probe.py`. These are native text turns, not a physical
microphone/speaker test or a separate Realtime API.

A read-only live merchant GET succeeded at 2026-10-26 16:11:56 UTC: 100 tables,
93 marked available, first table 5. This is historical evidence, not current
availability. The complete public response is in
`output/live-tables-public-read.json`. No live order, payment or new print request
was created by these tests/probes.

## Verification limits

Frontend: 21 tests, production build, lint and formatting passed. Python lint and
formatting passed; the updated skill passed `quick_validate.py` with system Python.

Final backend/browser verification: **267 passed in 66.56 seconds**. All 31 new
table regressions are included. Earlier full-suite runs exposed
`test_timed_browser_playback_keeps_words_while_ui_thread_is_busy`: recorded sample
error 0.271811 exceeds 0.0001. Running this test alone reproduces the failure.
It also failed in an isolated run, then passed in the final full run, so the
failure is intermittent and remains a separate concern. It directly transpiles
unchanged `frontend/src/voiceAudio.ts` and loads unchanged
`frontend/public/voice-playback.js`, independently of the table implementation.
This task does not claim to fix playback or the earlier native voice latency target.
The full-suite result is recorded in `output/live-tables-pytest.txt`.

## Deployed runtime

Both owned services were stopped before deployment. Started them through
`scripts/kiosk.py start`: Visual PID 411107 listens on 9877 and API PID 411147
listens on 8080. Passive verification returned health `ok`, mode `merchant_api`,
`merchant_connected=true`, `voice_prepared=true`, no active guest or receiving
microphone, and live `/api/tables` with retrieval timestamp. See
`output/live-tables-runtime.json`. Existing browser tabs need reload; existing
MCP stdio connections need a reconnect to load the new tool registration.

## Self-evaluation

| Axis | Score | Evidence / next improvement |
| --- | --- | --- |
| Accuracy | 4 | Real read-only merchant response and native tool behavior verified; a selected table can change afterward because this is not a reservation. |
| Completeness | 4 | HTTP/MCP/native/touch, skill, failures and retries covered; physical spoken acceptance is still a field check. |
| Clarity | 4 | Live timestamps/status versus selection/reservation documented; operators should reload existing tabs/connections. |
| Actionability | 4 | Built frontend and executable regression/probe commands supplied; the separate playback failure remains visible. |
| Conciseness | 4 | Customer result stays short and engineering evidence lives here; the local text grammar adds maintenance surface. |

Overall 4.0/5. Highest-impact follow-ups: physical Vietnamese spoken acceptance,
and a separate diagnosis of the unchanged playback regression. Self-check: the
requested table capability is demonstrated; reservation success is not inferred,
and the final green suite does not establish a fix for intermittent playback.
