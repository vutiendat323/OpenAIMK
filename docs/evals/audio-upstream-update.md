# Audio upstream update — 2026-10-21

## Applied change

Fast-forwarded the actual Audio checkout from `f0f168eb` to upstream main
`7538d7859849cfe3124e49121dea755087fe68d0`. GitHub branch tips were checked again
before fetching. All TARGET diarizer slots of the locked customer now count as
one voice; an additional non-target slot still triggers overlap handling.

Visual HEAD already matches the latest `origin/feat/mouth-activity` at
`a2289d5eb2e0efba457f6c204293c5bdd6581de1`. Its existing camera, ownership,
captured-frame freshness and PAD patches were preserved. No model, reasoning
effort, service tier, native acknowledgment or checkout behavior was changed.

## Integration evidence

Added `tests/test_fusion_identity.py`, using the production perception Python,
actual local FusionGate and native `accepted_pcm` guard, with synthetic evidence.
Before updating Audio, the regression failed: duplicate customer slots produced
UNCERTAIN and silenced PCM. After fast-forward, they produce ACCEPT and preserve
PCM without separation. Another active slot remains UNCERTAIN/silenced, and
stale evidence remains silenced.

- Full Audio suite: **279 passed, 3 skipped in 7.13 s**. The skipped model tests
  are not evidence of GPU/model correctness.
- Full kiosk suite: **213 passed in 51.98 s**.
- Current Visual camera/source/presence/provenance/mouth checks: **48 passed**.
- Ruff lint/format and Audio/Visual diff whitespace checks passed.
- Independent review found no material issues in the gate change or integration.
- OpenJarvis parity tooling was not run: the workspace has no sibling OpenJarvis
  checkout. The intentional upstream behavior change is covered by its regression
  and the added host-boundary test.

## Runtime verification

Both services stopped during validation; the API log ended with an orderly
shutdown, without establishing its cause. No stop command was issued by this
update task. Started the owned launcher after the suites passed and no API
session remained reachable: Visual pid 146382, API pid 146421 and its new Audio
worker pid 146428. Both ports 9877/8080 listen; HTTP health is ok, kiosk is enabled,
and the final status reports voice_prepared=true. No customer session, audio,
merchant order, payment or printer job was issued by verification.

The fix is now in the runtime checkout and a newly started Audio worker uses
that checkout. Physical microphone/Fusion/speaker quality and useful-result
latency were not measured. This change does not establish that intermittent
native cold handshakes or the 1–2-second useful-response target are resolved.

## Self-evaluation

Accuracy 4/5: exact upstream commit, red/green host regression and live process
checks verified; physical audio unmeasured. Completeness 4/5: update deployed and
regressions passed; GPU cases skipped and OpenJarvis parity unavailable. Clarity
5/5: applied Audio update is distinguished from already-current Visual. Actionability
5/5: new worker running. Conciseness 5/5: upstream patch reused, one host regression.
Overall 4.6/5. Next improvement: measure actual customer audio after device permission.
