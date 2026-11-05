# Browser 2D avatar — 2026-10-31

V1 history. Superseded by [the body/mouth correction](browser-2d-motion.md) after user visual feedback.

## Delivered behavior

Settings → General → Character (VI: Cài đặt → Chung → Nhân vật) offers 3D and 2D.
3D remains the default. Explicit choices persist as `trendcoffee.avatar`.
Turn the microphone off to change character; this avoids replacing playback mid-turn.
The 3D label identifies the existing photo/Ditto path, not a conventional 3D mesh.

2D uses the supplied JPG, localized mouth/eyelid mesh deformation, slight head motion
and breathing. Mouth opening follows actual assistant output audio, not microphone
input or transcript timing. Blink/head movement also runs quietly at rest.
Reduced motion disables optional movement. Native voice playback and Fusion remain
in the existing path; 2D skips the avatar HTTP status, WebSocket and WebRTC transport.

The source JPEG is copied byte-for-byte:
`a83bc1d641d9d0fced7d8807fff7306ec02d6c1f8454e67cfc8affbc83ad6da3`.
Its actual dimensions are 1536×2752. GPU upload is downscaled to at most 2048px or
the device limit; the stored source is unchanged. No new runtime dependencies.
The supplied greeting MP4 is a gesture reference; it is not used for arbitrary speech.

## Architecture / files

- `frontend/src/avatar2dMotion.ts`: output audio features and bounded elapsed-time motion.
- `frontend/src/avatar2d.ts`: WebGL mesh, upload sizing, rendering, visibility and disposal.
- `frontend/src/components/Avatar2D.tsx`: React lifetime and original-image fallback.
- `useKioskVoice.ts`: persisted mode, output-only reader and mode-aware player creation.
- `voiceAudio.ts`: plain-player interrupt/resume rejects delayed interrupted-turn PCM.
- Settings/AvatarAssistant/translations/CSS: selection and existing-stage integration.
- `frontend/public/avatars/2d/`: exact source and provenance. Build copies it to static.
- `tests/test_avatar_2d_browser.py`: isolated server, fake microphone and native Maple WAV.

The Interface between audio playback and the visual Module is a reader returning
`{ level, brightness, playing }`. The Module owns visual timing and GPU resources;
it owns no microphone, native connection, merchant state or secondary audio queue.

## Measured evidence

Hardware: Chromium headless, ANGLE Vulkan, NVIDIA GeForce RTX 3060, driver Vulkan1.4.351.
The GPU path was explicitly checked; default headless Chromium used SwiftShader.
Hardware flags follow [Chromium's headless GPU guidance](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/gpu/using-gpu-hardware-in-headless-chrome.md).
Output analysis uses the existing [Web Audio analyser](https://developer.mozilla.org/en-US/docs/Web/API/AnalyserNode);
drawing follows [requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame).

The clean measurements below exclude preview capture. They count actual GL draw
submissions and shader-mouth changes in the foreground fixture; they do not measure
physical monitor scanout or neural inference. Each full observation lasts about six seconds.

| Viewport | Full-run draw FPS | Frame interval p95 | Max interval | Changed mouth frames in ~1 s speech |
|---|---:|---:|---:|---:|
| 1080×1920 | 60.09 | 18.40 ms | 20.80 ms | 43 / 0.991 s |
| 1440×1000 | 60.11 | 18.50 ms | 21.00 ms | 42 / 0.991 s |

Raw evidence:
[portrait GPU metrics](../../output/avatar-quality-review/browser-2d/metrics-gpu-1080.json),
[desktop GPU metrics](../../output/avatar-quality-review/browser-2d/metrics-gpu-1440.json).

Earlier SwiftShader runs were about 27–40 draw FPS. Hardware acceleration matters.
CPU command-submission timing is not GPU execution time or total CPU consumption.
A separately running Ditto process may retain GPU memory for other 3D tabs; choosing
2D does not globally stop that process. Per-session neural/transport work is bypassed.

[Actual portrait preview with audio](../../output/avatar-quality-review/browser-2d/conversation-preview.mp4):
720×1290 H.264/AAC, 6.201 s, 185 decoded video frames at30 FPS. The preview isolates
the portrait stage for visual review and records real browser output audio:
speech → interruption → resumed speech → rest. Its 30 FPS recording is independent
of the renderer benchmark. Original-image rest and post-speech captures are in the
same output directory. The source face/color and bounded mouth were visually inspected
in still frames; naturalness remains subject to user review.

## Verification

- Frontend:42 tests pass; production TypeScript/Vite build passes; oxlint passes;
  changed-file Prettier checks pass. Touched Python test passes Ruff lint/format.
- New 2D GPU browser suite:7 passed in25.95 s. A later corrected full-portrait
  preview recording test passed independently in9.25 s.
- Related backend/browser run:41 passed,2 skipped,1 failed in106.70 s.
  The failure is
  `test_native_sized_packets_render_continuously_and_status_does_not_flicker[paused]`
  in `tests/test_avatar_audio_browser.py`: expected25±2 silent20ms frames, measured19;
  output span10.44 s. Isolated rerun reproduced the same result. The AudioWorklet
  PCM/recovery implementation was not changed by this task. This regression is
  reported unresolved; no broad “all Python tests pass” claim is made.
- Bare root suite stops collection with9 errors: missing `numpy`, `cv2`, `torch`
  in the root environment. Affected files: `test_avatar_appearance.py`,
  `test_avatar_expression.py`, `test_avatar_pose.py`, `test_avatar_presentation.py`,
  `test_ditto_realtime.py`, `test_ditto_roi.py`, `test_ditto_server.py`,
  `test_ditto_trt.py`, `test_prepare_ditto_mouth.py`. Six optional suites skipped.

Regression coverage includes default/persisted mode, picker locked while microphone
enabled, no avatar network path in2D, microphone-only mouth silence, interrupted/late
PCM rejection, resumed speech, no-WebGL fallback, context loss followed by visibility
change, upload failure and a simulated1024px texture limit. Independent review found
two material graphics-failure issues; both were reproduced RED, fixed and rechecked.
An initially premature fallback assertion was tightened to wait for source decoding.

Commands:
```sh
cd frontend
npm test
npm run lint
npm run build
cd ..
TREND_TEST_2D_GPU=1 .venv/bin/python -m pytest tests/test_avatar_2d_browser.py -q -s -p no:cacheprovider --tb=short
# Separate full-portrait preview, not the clean benchmark:
TREND_TEST_2D_GPU=1 TREND_TEST_2D_RECORD=1 .venv/bin/python -m pytest tests/test_avatar_2d_browser.py -k 'output_audio and 1080' -q -s -p no:cacheprovider --tb=short
```

## Limits and operations

Mouth/eye motion deforms existing pixels. It cannot reconstruct hidden lips, eyelids,
new teeth or large head angles; phoneme-level Vietnamese articulation is approximate.
The JPEG's open mouth is compressed to a narrow rest shape, which still needs user
acceptance. No unsupported arm-wave action is exposed in2D.

Eliminating avatar transport and inference removes those visual waits. Native-model
response latency, physical acoustic synchronization and the proposed ≤50ms
audio-feature-to-render lag target were not independently quantified. Do not infer
those from FPS. Extended-device/long-duration performance also remains unverified.

Static production assets are built. Onboarding/runtime status showed managed Visual,
avatar and HTTP processes stopped; this implementation started only isolated fixture
servers and did not start managed kiosk processes. Recheck status before operating.
Use3D in Settings to return to the existing avatar; its runtime profile is unchanged.

## Self-evaluation

| Axis | Score | Evidence / next improvement |
|---|---:|---|
| Accuracy |4/5| GPU/frame metrics and decoded preview verified; acoustic latency unmeasured. |
| Completeness |4/5| Requested selection and real output rig implemented; full Python gate remains limited above. |
| Clarity |4/5| Drawing cadence and changed-mouth count distinguished; preview needs human assessment. |
| Actionability |4/5| Settings path, commands and rollback provided; managed kiosk activation is a separate task. |
| Conciseness |4/5| Main result is short; failure details retained here for inspection. |

Average4.0/5. Next priorities: user review of rest/blink/mouth; characterize visual/audio
lag; resolve the existing audio-gap expectation and root test environment.
Would the user agree? That depends on their visual review; naturalness is not assumed.
