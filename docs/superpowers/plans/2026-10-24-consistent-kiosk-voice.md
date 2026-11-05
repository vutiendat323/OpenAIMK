# Consistent kiosk voice implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement each task.

**Goal:** One selected voice for greeting, conversation and farewell.
**Architecture:** Prebuilt native v3 clips keyed by voice, with a guest-captured voice.
**Tech Stack:** Existing Python, native Codex, aiortc/av, WAV and browser playback.
**Spec:** `docs/superpowers/specs/2026-10-24-consistent-kiosk-voice-design.md`

## Global constraints

- Keep both existing Vietnamese boundary sentences and immediate playback.
- Voice changes during a guest apply to the next guest only.
- Rendering uses isolated native threads, no business tools or real microphone.
- Preserve the existing native conversation and business configuration.

## Review focus

- A changed preference must not change the departing guest's farewell.
- Missing clips must not expose a partially supported voice.
- Rendering must reject a wrong/partial transcript or empty audio.
- Native/network teardown must not delay an already cached farewell.
- Default Codex voice needs its own clips generated without an override.

## Task 1: Capture and route boundary voices

Files: `trendcoffee/kiosk.py`, `tests/test_voice_settings.py`.

- [x] Add failing tests with distinguishable WAV fixtures for Maple and Rio,
  mid-guest preference changes and an unprepared native voice.
- [x] Load `static/voice/<voice-or-default>/<kind>.wav` and include the voice in
  announcement metadata. Capture `session_voice` at guest start and use it for
  both boundaries. Filter unprepared choices from `voice_options()`.
- [x] Verify with `.venv/bin/python -m pytest tests/test_voice_settings.py -q`.

## Task 2: Prepare native speech assets

Files: `scripts/prepare_voice_clips.py`, `tests/test_voice_clips.py`,
`trendcoffee/static/voice/`, `docs/workflows/kiosk-voice.md`.

- [x] Test rejection of wrong transcripts, empty or inconsistent audio; include
  the native default and completeness checks for all generated voice assets.
- [x] Add the reproducible rendering command using exact-repeat native speech,
  bounded capture, transcript validation and atomic WAV writes.
- [x] Generate both phrases for all accessible installed v3 voices plus the default;
  record native voice, transcript and PCM hashes in the generated manifest.
- [x] Run backend/browser regression tests, frontend tests/build and lint.
- [x] Restart the owned API when idle, verify the deployed catalog and record
  evidence/remaining limits in `docs/evals/consistent-kiosk-voice.md`.

## Execution result

All 23 accessible voices and the unoverridden default have both recordings.
Porto/Selva failed three attempts each, and an isolated probe confirmed upstream
`forbidden` responses; the selection filter excludes them. This resolves the
planned all-catalog preparation to all accessible choices without substituting a
different voice. Native conversation configuration remains unchanged.

Routing regressions: 3 RED then GREEN, voice settings 12 passed. Independent
review found the renderer/browser size mismatch; two regressions failed before
the fix and passed afterward. Final suite: 234 passed; frontend 20 passed;
build and targeted lint/format passed. Deployed while idle and verified.
