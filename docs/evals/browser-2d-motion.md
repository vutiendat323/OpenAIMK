# 2D mouth and body motion correction — 2026-10-31

> Cancelled 2026-11-01: 2D was removed from the kiosk. This record is historical.

> Mouth sections below are superseded by "Lip-sync shape correction" at the end.

## User feedback and cause

The user reported that the mouth barely articulated and the head/hands/body did not
move like `Woman_greeting_customers_at_counter_b58d415e_1080p.mp4`, and supplied
`image.png_3ae5f671.jpg`. The new image is a 204×381 screenshot of that clip's
hands-down pose. V1 had no arm/body rig; ordinary RMS0.05 produced only0.246 mouth
drive, and head tilt stayed below a degree. More draw FPS did not fix that absence.

## Implemented correction

- Use the supplied video for genuine source head, arm and torso motion. The silent
  forward/reverse loop avoids a hard cut from clasped hands to hands-down.
- Offline MediaPipe tracks all239 original frames; the palindrome contains478 frames
  at24 FPS over19.916667 seconds. No live face inference or new voice engine.
- The high-resolution poster and closed/medium/open mouth artwork come from the same
  video, matching the new reference. Existing3D mode and mode-selection rules remain.
- The live mouth atlas replaces the prerecorded mouth. Actual assistant output energy
  drives articulation with stronger quiet-speech response; at RMS0.05 drive is now
  about0.61. Atlas blending remains continuous across the drive range.
- Face anchors use the actual presented video mediaTime, including loop resets. Source
  eyes/head/body remain intact. Silence/interruption closes the mouth independently.
- Reduced motion freezes optional source motion while mouth playback remains available.
  A frame-loop preference check also covers changes where Chromium updates matches
  without delivering a MediaQueryList change event.

This is a video-body/live-mouth hybrid, not a newly built full skeletal rig.
The source cuts off the feet; no foot motion is reconstructed.

## Evidence

[Before/after](../../output/avatar-quality-review/browser-2d-motion/before-after.mp4) ·
[New preview with sound](../../output/avatar-quality-review/browser-2d-motion/preview.mp4).

The preview uses actual browser playback of the prerecorded native Maple fixture:
speech → interruption → resumed speech → rest. It isolates the portrait stage.
H.264/AAC,720×1290,30 FPS,185 decoded frames,6.171 seconds. Preview recording cadence
is separate from render and source-body cadence. The comparison uses the original V1
preview and the revised character source requested by the user, not a matched-pixel
same-source perceptual experiment.

Clean RTX3060/Chromium ANGLE Vulkan measurements, without preview recording:

| Viewport | Draw submissions/s | Frame interval p95 | Source body FPS |
|---|---:|---:|---:|
| 1080×1920 |60.00|22.50 ms|24|
| 1440×1000 |60.00|20.40 ms|24|

[Portrait metrics](../../output/avatar-quality-review/browser-2d-motion/gpu-1080.json) ·
[Desktop metrics](../../output/avatar-quality-review/browser-2d-motion/gpu-1440.json).
These are short foreground fixture measurements, not physical monitor scanout,
60 generated body poses, phoneme recognition or physical acoustic synchronization.
Source video callbacks measured approximately24 frames/s; mouth-drive changes were
42/0.985 s and40/0.986 s in the initial speech window.

Actual rendered-pixel checks:
- Hands region mean absolute RGB change across2.2 s: V1 about0.94/255 →30.20/255.
  Revised head region change40.53/255. These are image-change checks, not skeletal scores.
- At the open source-mouth frame,319 sampled pixels met the dark-mouth criterion;
  with assistant silence the rendered count was0. The source's speaking mouth is
  visibly concealed; the live audio controls the replacement.
- An early preview had bright skin halos. Corner-based color estimation sampled jaw
  shadows; replaced with cheek bands and a bounded ±0.025 RGB correction.
  Sampled skin-ring RGB MAE23.8 →1.13/255. No threshold was relaxed.
- Closed/open/rest close-ups of the final decoded preview were inspected after the fix.
  Human naturalness acceptance remains with the user.

## Verification

-44 frontend tests pass; TypeScript/Vite production build and oxlint pass.
-13 GPU browser cases pass in42.27 s: selection/persistence, quiet mouth, speech,
  interruption/late packets, actual hand/head pixels, source-mouth concealment,
  source loop reset, reduced motion, texture limits/upload errors, context loss,
  and invalid metadata fallback.
- Final preview recording test passed independently in9.35 s.
- Touched Python files pass Ruff; touched TypeScript files pass Prettier.
- Independent review verified shader orientation/samplers, actual loop reset, reduced
  motion and cleanup. A reproduced malformed-metadata fallback bug was fixed and its
  null-skin/missing-dimension regressions pass.
- Prior broader Python limits remain documented in
  [V1 evaluation](browser-2d-avatar.md): root environment lacks numpy/cv2/torch and
  the paused audio-gap check measured19 rather than25±2 silent frames. This task does
  not claim those broader checks pass or alter the native AudioWorklet.

## Locations and reproduction

- `scripts/prepare_2d_body.py`: existing local CPU face model → video/atlas/anchors/poster.
- `frontend/src/avatar2d.ts`: video/atlas compositing, source clock and graphics lifetime.
- `frontend/src/avatar2dMotion.ts`: quiet-speech response and frame selection.
- `frontend/public/avatars/2d/`: prepared assets and provenance.
- `tests/test_avatar_2d_browser.py`: actual browser pixel, media and lifecycle checks.
- V1 source/renderer retained under `output/avatar-quality-review/browser-2d-motion/`.

```sh
.runtime/livetalking-venv/bin/python scripts/prepare_2d_body.py Woman_greeting_customers_at_counter_b58d415e_1080p.mp4
cd frontend
npm test
npm run build
cd ..
TREND_TEST_2D_GPU=1 .venv/bin/python -m pytest tests/test_avatar_2d_browser.py -q -s -p no:cacheprovider --tb=short
```

Static production assets are built. Managed kiosk processes were not started;
temporary fixture servers shut down. Select2D in Settings with microphone off;
select3D to return to the existing photo avatar. This correction does not establish
lower native-model answer latency. A full-body asset would be needed for foot motion.

## Self-evaluation

Accuracy4/5: actual pixels/media/frame timing checked; physical sync is unmeasured.
Completeness4/5: requested visible mouth/head/arms addressed; feet absent from source.
Clarity4/5: source24 FPS and drawing60 FPS distinguished; the hybrid is explicit.
Actionability4/5: build, preview, source provenance and regression commands available;
managed activation remains separate.
Conciseness4/5: user-facing result is brief; detailed evidence retained here.
Average4.0/5. Next: user visual review, then additional spoken phrases/longer sessions.
Would the user agree? Visual approval has not been assumed.

## Lip-sync shape correction — 2026-10-31

The user rejected the mouth as lip-sync not achieved. Measured causes, in order:

- Not timing or saturation: on the Maple greeting, drive reached ≥0.95 only 2.8% of
  speech and tracked the 30 ms envelope (r=0.85). The old preview's mouth/audio peak
  was r=0.81 at about 33 ms; that recorder offset is not physical speaker latency.
- Three atlas frames were crossfaded on one loudness axis, double-exposing lips from
  about 0.6–0.75 drive. The computed spectral value never reached the shader.
- Mouth size followed the prerecorded mouth's lip width, which ranged across
  0.28–0.51 eye widths, so the replacement pulsed with the hidden source speech.

Correction:

- Eight whole source mouths (frames 223, 212, 48, 88, 165, 62, 176, 93): rest, pressed,
  and small/large round, neutral and spread. They swap with a 90 ms hold, never blend.
- Loudness picks opening size; a spectral centroid across 300–3400 Hz, relative to a
  running center so every selected voice is covered, picks round/neutral/spread.
- The output analyser is now 1024 samples with no smoothing, so it resolves syllables
  instead of single pitch periods. The waveform meter reads the same analyser.
- Patch scale and angle come from the eyes. The mouth center is a fixed offset from the
  nose tip, because lip landmarks drifted 41 px vertically (10.5 px p95 per frame at
  1080p) with the hidden prerecorded speech, moving a closed mouth during silence.
  Part of that figure may be landmark noise, and the remaining 6.9 px p95 anchor step
  includes real head motion.
- A pinched small-round frame (79) was replaced by fuller frame 165. An interim
  immediate close-to-rest caused 16–18 ms flashes and was rejected.

Fresh evidence: [lip-sync preview](../../output/avatar-quality-review/browser-2d-motion/preview-lipsync-2.mp4).
RTX3060 Chromium, real analyser, Maple fixture; per-run shares and swap rates are in
`output/avatar-quality-review/browser-2d/metrics-*.json`. Earlier mouth assets are
kept as `v2-mouth-atlas.png` and `v2-motion.json` beside the preview.

This remains an acoustic approximation: shape selection is not phoneme recognition,
pressed lips do not guarantee m/b/p closure and Vietnamese accuracy is unmeasured.
Only one prerecorded phrase was measured. 3D shares the longer analyser; only its
unit tests were rerun. The 90 ms hold can drop short syllables. Acceptance pending.
