# Realtime Avatar Implementation Plan

Goal: Upgrade the existing avatar with local LiveTalking, retaining native Codex voice.
Architecture: PCM → authenticated same-origin socket → loopback LiveTalking → WebRTC A/V.
Tech stack: FastAPI/httpx, LiveTalking Wav2Lip, aiortc/AV, React/TypeScript.

## Scope agreed with user

Avatar local; existing voice retained. Use upstream sample avatar for initial acceptance.
Trend identity, waving and expressions require video/action assets; static images are insufficient.
No manual model composition: use upstream Wav2Lip/avatar preparation and isolated environment.

## Acceptance criteria

Single avatar on RTX 3060 12GB. No external TTS/LLM/STUN in avatar process.
PCM packets bounded and frame-aligned, persistent resampling to 16kHz/20ms, stale epochs rejected.
Immediate local mute on stop. Same-origin guest auth, no upstream session IDs exposed.
Action IDs idle=1/wave=2/smile=3 must have configured clips; missing clips return errors.
Do not change merchant behavior or place real orders during acceptance.
Hardware targets: >=25 final FPS, <=80ms A/V skew, <=100ms interrupt tail and 30min soak.
These are acceptance targets, not measured performance claims.

## Tasks and files

- [x] `trendcoffee/avatar.py`: PCM validation, isolated transport, authenticated socket/status.
- [x] `trendcoffee/api.py`: opt-in route registration via TREND_AVATAR_URL.
- [x] `scripts/livetalking_local.py`: upstream wrapper, loopback, PCM/reset/close/action routes,
  disable TTS/LLM/public STUN and persistent AV resampler.
- [x] `frontend/src/avatarPlayer.ts`: WebRTC media, bounded PCM streaming, local mute/teardown.
- [x] `useKioskVoice.ts`, `AvatarAssistant.tsx`: integrate inside existing avatar area.
- [x] Run focused backend/frontend tests, lint, formatting and production build.
- [x] Pin upstream, prepare environment/model/sample avatar and launch local acceptance engine.
- [x] Reproduce greeting burst regression; pace PCM, clear pending speech on interrupt.
- [x] Recover WebRTC/socket transport, retain sample identity in poster, cancel pending negotiation.
- [x] Real Chromium/GPU lifecycle acceptance: greeting/audio, interrupt/resume, reconnect,
  next guest, disarm/rearm; centered layouts at 375/768/1440px.
- [x] Launch Visual/avatar/API together; verify model readiness, live kiosk page, and ownership
  after engine changes working directory.
- [x] Measure warm received FPS and first frame with Visual process running (25 FPS, 139.4ms).
- [ ] Measure perceptual A/V skew, acoustic interrupt tail, and 30min Fusion-active soak;
  verify no stale GPU/RTP audio after reset.
- [x] Prepare supplied Trend talking/waving clips; validate simultaneous gesture/speech and deploy.
  Follow-up: `2026-10-29-trend-avatar-clips.md`.

## Verification

`.venv/bin/python -m pytest tests/test_avatar.py tests/test_api.py -q`
`npm --prefix frontend test`
`npm --prefix frontend run lint`
`npm --prefix frontend run build`

## Alternatives and review focus

Direct browser access exposes upstream admin/cloud routes. Replacing native voice contradicts
selected scope. Keep PCM bridge. Review resampler continuity, queue bounds, partial-frame tail,
negotiation cancellation, guest transitions and audio already queued in GPU/RTP on interruption.
