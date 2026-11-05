# Browser 2D avatar alongside the existing 3D avatar

Date: 2026-10-31. Status: approved by the user and implemented; see ../../evals/browser-2d-avatar.md for verification limits.

## Intent and chosen approach

The user wants the supplied 2D café character to move its mouth, eyes and head during
live native voice conversation, with a lighter renderer and lower visual latency.
Keep the existing avatar and offer 3D/2D selection in Settings.
The user selected an image rig rendered in the browser.

Alternatives considered:
- Browser image rig (selected): reuses the exact supplied artwork, no neural video
  inference or avatar WebRTC in 2D; articulation is approximate and motion must stay small.
- Live2D: offers more detailed articulation but requires separate art layers and a
  completed rig, neither of which is present. Defer that dependency.

The current photo-based Ditto implementation is labeled 3D to match the requested UI;
this label does not assert that Ditto is a conventional 3D model.

## Assets and appearance

- Identity/source: `image.png_11399199_2K.jpg`. Preserve its face, warm skin,
  clothing and colors; copy it to frontend public assets with a calibrated manifest.
- Gesture reference: `Woman_greeting_customers_at_counter_b58d415e_1080p.mp4`,
  1080×1920, 24 FPS, 9.963 seconds. Its hairstyle/background differ; it is a
  reference, not a replacement for the JPG or arbitrary live speech.
- Use a textured mesh with localized deformations. Preserve original mouth interior;
  do not synthesize large teeth or paste a geometric mouth over the artwork.
- The source mouth is open. Calibrate a narrow resting smile and bounded speech
  aperture, then inspect close-ups for compressed lips or eyelids before acceptance.
- A flat image cannot reveal unseen head angles or arm positions. Limit head turn,
  keep hands intact and expose only gestures actually implemented.

## Module, Interface and Seam

A browser 2D Module owns mesh deformation, drawing, blink timing, smoothing,
source loading, fallback and rendering diagnostics. Its Interface accepts a canvas,
asset calibration and a reader for actual assistant output audio/state; it owns no
microphone, merchant action, native connection or business state.

The Seam is between output playback and visual presentation. There will be two real
Adapters: the existing Ditto path and the browser image rig. Keep the existing
VoicePlayer as audio owner in 2D; do not add a parallel audio queue or speech engine.

Native PCM → existing VoicePlayer/AudioWorklet → output analyser → speaker
                                               ↓
                                      2D audio features → mesh → display

Read only the output analyser for 2D mouth motion. Existing audioLevels mixes input
and output for the waveform, so it must not be reused blindly for the mouth.
No native audio buffer changes or extra network wait are part of this change.

## Settings and lifecycle

- Settings > General: “Nhân vật” / “Character”, options “3D” and “2D”.
- Default stays 3D; save explicit selection with the existing browser preference pattern.
- Changes apply immediately while the microphone is off. Disable the mode picker while
  the microphone is enabled or setup is busy and show “Tắt micro trước khi đổi nhân vật.”
  The existing player is created when the microphone is enabled; this timing avoids
  replacing it mid-conversation or during farewell playback.
- In 2D, create VoicePlayer directly. Skip avatar status fetch, avatar socket, WebRTC
  and neural avatar work; keep guest speaker ownership and camera Fusion.
- Closing an old 3D peer releases that peer. Do not globally stop the managed avatar
  process because another tab may still use 3D; any remaining baseline GPU allocation
  must be distinguished from per-session work.
- Stop, guest end, interrupt, failed setup and unmount reset mouth drive and release
  drawing resources; old guest events cannot drive the next guest. Preserve audio
  suspend/resume semantics in plain VoicePlayer as well: barge-in must stop old PCM
  and reject delayed packets until an assistant turn resumes.
- Hidden tabs pause drawing; reduced motion disables optional head/breath movement.
  Renderer/source failure shows the source image and preserves voice playback.

## Motion and performance

- Mouth opening follows actual output energy, with a noise gate and fast attack,
  smooth release. Frequency features may vary width/roundness but are heuristic,
  not Vietnamese phoneme recognition.
- Eyes blink with staggered timing; head makes bounded small motions tied to speech
  emphasis. Timing uses elapsed seconds so high refresh displays do not speed it up.
- Use native browser WebGL/requestAnimationFrame, no new runtime library or GPU model.
- Target 60 FPS on a foreground 60 Hz display; rendering must adapt to device limits.
- Measure frame intervals and rendering cost separately from useful changed poses.
  Target audio-feature-to-render lag p95 ≤50 ms after output audio energy changes;
  report the measurement method and do not call a software proxy acoustic sync.
- This work reduces avatar transport/inference cost in 2D. It does not establish
  lower native-model response latency or user acceptance of naturalness.

## Files expected to change

- `frontend/src/useKioskVoice.ts`: mode preference, output-only feature reader,
  mode-aware player creation and session cleanup.
- `frontend/src/components/SettingsDialog.tsx`, `translations.ts`: selection and hint.
- `frontend/src/components/AvatarAssistant.tsx`: render the chosen visual Adapter.
- New small 2D rendering/motion Module and tests in `frontend/src/`.
- `frontend/public/avatars/2d/`: source image and calibration/provenance.
- Focused browser fixture under `tests/`; architecture/evaluation documentation.
- Production build output under `trendcoffee/static/`.

## Verification and acceptance

1. Motion tests cover silence, known output audio, bounds, independent blink timing,
   frame-rate-independent smoothing, interruption/reset, delayed PCM rejection and invalid/nonfinite input.
2. Browser tests cover 3D default, saved 2D on reload, immediate microphone-off switch,
   picker disabled while microphone enabled, no avatar transport in 2D, output-only response, preserved cart and speech.
3. Run existing 3D playback regressions and relevant settings/guest lifecycle fixtures.
4. Run frontend tests, type/build/lint and format checks for changed files.
5. Capture actual browser screenshots and a recorded native-audio fixture, including
   silence → speech → interrupt → resumed speech and 2D/3D selection.
6. Measure FPS and frame timing at portrait kiosk and desktop sizes. Report browser
   environment/hardware, shader render cost, drawn pose changes and limits.
7. Review mouth/eyes/head close-ups before claiming readiness. A passing fixture or
   smooth frame cadence does not prove subjective naturalness.

Use prerecorded/local fixtures only. Do not start managed kiosk processes or perform
merchant, payment, printer or live microphone actions for this implementation.
Builder check completed: clarified mode activation, plain-VoicePlayer interruption,
and mesh-only art limitations. No unresolved product question was identified.

Root has no CodeGraph index or usable Git repository at inspection.
