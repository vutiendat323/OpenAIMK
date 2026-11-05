# Browser 2D avatar Implementation Plan

> For agentic workers: use superpowers:executing-plans for inline implementation.

**Goal:** Add the supplied character as an output-audio-driven browser rig with a saved 3D/2D setting.
**Architecture:** Keep native PCM ownership in VoicePlayer. A small motion module reads output-only audio features and a WebGL image rig presents bounded facial motion.
**Tech Stack:** Existing React/TypeScript/Vite/Vitest, native WebGL/Web Audio; no new dependencies.
**Spec:** ../specs/2026-10-31-browser-2d-avatar-design.md (approved in conversation).

## Global constraints
- Default 3D. Change mode only with microphone off; saved browser preference.
- Keep source art, native voice and Fusion; no avatar transport/inference in 2D.
- No live merchant/payment/printer/microphone actions; recorded fixtures only.
- 60 FPS and ≤50 ms audio-feature-to-render lag are measured targets, not promises.
- No usable root Git repository: work in the current authorized workspace, no commits/worktrees.

## Review focus
- Barge-in plus delayed audio must not resume the previous assistant turn.
- Output silence and microphone-only input must leave the mouth at rest.
- Asset/graphics failure must preserve audio and show the original image.
- Microphone setup/reconnect must not change mode mid-stream.
- High/low refresh, hidden tabs and teardown must not leak loops or alter motion speed.

## Task 1: Output-driven motion and playback interruption
Files: frontend/src/avatar2dMotion.ts, frontend/src/avatar2dMotion.test.ts,
frontend/src/voiceAudio.ts, frontend/src/voiceAudio.test.ts.
Interface: AvatarMotion.sample(audio, dt, time, reducedMotion) returns normalized Pose;
audioFeatures(samples, bins, playing) returns {level, brightness, playing}.
- [x] Add behavioral motion and audio interruption tests; run and observe RED.
- [x] Implement bounded time-based motion and VoicePlayer interrupt/resume; observe GREEN.

## Task 2: Renderer and integration
Files: frontend/src/avatar2d.ts, frontend/src/components/Avatar2D.tsx,
frontend/src/useKioskVoice.ts, frontend/src/components/AvatarAssistant.tsx,
frontend/src/components/SettingsDialog.tsx, frontend/src/translations.ts,
frontend/src/index.css, frontend/public/avatars/2d/.
Interface: renderer takes a canvas, source URL and output-feature reader; React owns its lifetime.
- [x] Add browser regression: default/saved choices, disabled active picker, no 2D avatar transport.
- [x] Observe RED against built current UI.
- [x] Implement renderer, output-only reader and mode-aware playback; copy exact source art/provenance.
- [x] Build, run regression plus 3D playback/settings tests; inspect close-up poses.

## Task 3: Verification and evidence
Files: tests/test_avatar_2d_browser.py, docs/evals/browser-2d-avatar.md, docs/ONBOARDING.md, CLAUDE.md.
- [x] Feed prerecorded audio through real browser playback; capture rest/speech/blink/interruption.
- [x] Measure foreground frame cadence, draw time and changed-pose rate; report environment and limits.
- [x] Run frontend suite/build/lint, changed-file formatting, focused Python/browser regressions.
- [x] Fresh independent review; fix material findings, record results and preview.

## Execution ledger
- Design approved. Reviewer clarified microphone-off switching, output-only drive and interruption.
- Ruling: inline implementation is within explicit implementation approval; no additional plan approval.
- Pre-flight: Task 2 consumes Task 1's exact audio and pose types; no conflicting interfaces found.

- Task1 complete: motion/audio tests RED→GREEN;42 frontend suite passes.
- Task2 complete: browser selection RED→GREEN;7 hardware browser cases pass; graphics faults fixed after independent review.
- Task3 complete with reported limits: decoded MP4 preview and clean GPU metrics saved; full Python collection blocked by dependencies; one audio-gap regression remains failed. No all-suite-green claim.
