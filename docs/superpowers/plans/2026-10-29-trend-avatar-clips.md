# Activate the supplied Trend clips

Inputs: `Tạo_video_chân_thực_cô_0e3fdbe0_1080p.mp4` (9.963s, talking) and
`Café_assistant_waving_hand_a1410f2d_1080p.mp4` (5.973s, waving), 1080×1920/24fps,
48kHz stereo. Keep originals and existing native voice. Prepare runtime frames at 720×1280,
25fps with upstream Wav2Lip's avatar builder and the existing model. Source audio is retained
as local QA WAVs, never mixed into live speech.

- [x] Inspect both sources; prepare all face boxes/crops locally, reject missing faces.
- [x] Add deterministic controller tests: one-shot wave, independent smile, idle, reset/guest isolation.
- [x] Add source-frame selection around the same Wav2Lip model so waving can lip-sync speech.
- [x] Carry epoch through GPU/render output; clear queued media on reset and reject stale output.
- [x] Integrate manifest into launcher and matching poster into kiosk.
- [x] Expose operator gesture controls in Settings and use wave automatically on greeting.
- [x] Validate real browser + GPU: speech during wave, smile, idle, interrupt/reconnect/new guest.
- [x] Deploy prepared avatar on 8010, confirm API readiness and warm FPS/voice signal.

Smile uses the final 35 waving-clip frames; idle uses its initial 18 still-handed frames.
These are sourced expressions, not newly synthesized facial emotions. LiveTalking requires no
additional TTS or generative-video cloud service. S3FD (upstream preparation dependency) is cached
locally after its first download; runtime rendering requires no network model download.

## Neutral-source correction after visual review

The user supplied `Female_staff_member_standing_3128c196.mp4` (720×1280/24fps, 10 seconds).
The current manifest supersedes the original talking source/18-frame idle choice above.

- [x] Compare old and new sources with identical audio features across 50 sampled frames.
- [x] Use all 250 neutral frames for idle/speech and preserve frame position across speech changes.
- [x] Preserve original eyes; feather the generated lower face without mixing original lips.
- [x] Reproduce compression blocks separately with actual VP8; raise local video quality.
- [x] Cover continuous motion, manifest compatibility/ranges and compositing with regressions.
- [x] Exercise real browser speech/gestures, interruption/reconnect and continuous speaker output.
- [x] Deploy the neutral manifest/poster and retain previous assets for rollback.

Transport tests and sharper source eyes do not establish perfect mouth realism. See the acceptance
record and `output/avatar-quality-review/` for comparison frames and the real WebRTC preview.
