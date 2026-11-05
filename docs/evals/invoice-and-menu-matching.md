# Invoice printing and spoken menu matching — 2026-10-20

Implemented official merchant invoice printing with the supplied OpenJarvis CUPS pattern and tolerant catalog search. Software verification is complete; physical paid-invoice acceptance is unverified.

## Evidence

- Final `.venv/bin/python -m pytest -q`: **175 passed** in 40.36 seconds, including browser journeys.
- Independent invoice review reproduced three lifecycle gaps: transient held-job lookup, unconfirmed completion, shutdown during verification. Regression tests failed before fixes; all three passed afterward. Final independent review found no remaining substantive issue; **30 invoice/printer tests passed**.
- Frontend: **15 tests passed**, TypeScript/build, oxlint and Prettier passed. Ruff check and formatting passed for application/tests.
- Actual project MCP executable/config/environment exercised with an empty temporary database: **14 tools**, including `print_invoice` and `get_invoice_status`; no merchant request or printer submission.
- Installed `pdftoppm` converted a valid synthetic PDF through the actual adapter to **12,472 ESC/POS bytes**. No `lp` submission was made.
- `PYTHONPATH=tests:. .venv/bin/python tests/browser_voice_smoke.py`: all three reported “trà bắp…” variants displayed actual Trà Bắc candidates. Manual search cleared the voice override; an unknown drink showed zero cards. Zero console/page errors, axe violations or overflow at 1440/768/375. Screenshot: `.runtime/voice-browser/menu-spoken-candidates.png`.
- Production remained stopped on ports 8080/9877; GP-C180I was idle/enabled. Production database retained **35 orders**, no print ledger created by tests, zero locally verified paid orders available for live document acceptance.

## Operating limits

Merchant payment completion and a valid official invoice are required; scanning a QR alone cannot print. New checkouts enroll atomically once printing is configured. Existing orders are not automatically backfilled. Ambiguous spool/release outcomes do not create a second job. Known jobs continue read-only observation until confirmed or failed. New MCP tools require host reload; the configured printer worker starts with API/MCP when those processes next run.

No real merchant order/payment, official paid PDF, physical paper output or live customer speech recognition was exercised in this change. [Operator instructions](../workflows/invoice-printing.md) describe configuration and states.

## Self-evaluation

| Axis | Score | Evidence / improvement |
|---|---:|---|
| Accuracy | 4/5 | Mocked merchant evidence, real Poppler conversion and 175 passing tests; validate the actual paid PDF/thermal output during the next real completed transaction. |
| Completeness | 5/5 | Both active requests implemented: tolerant menu candidates/display and automatic durable invoice printing with scoped MCP/HTTP tools. |
| Clarity | 5/5 | Operator documentation distinguishes merchant completion, submitted CUPS job, confirmed completion and uncertainty. |
| Actionability | 4/5 | Launcher and project MCP configured for GP-C180I; currently stopped stack and host-controlled MCP reload defer live availability. |
| Conciseness | 5/5 | Two invoice tools, no new customer UI/confirmation flow; final response reports behavior and field-test limit briefly. |

Overall: **4.6/5**. Highest-impact remaining check: inspect physical output from the next genuine paid merchant invoice. Would the user agree? Likely on the requested fast flow and minimal UI; paper output still needs observed evidence.
