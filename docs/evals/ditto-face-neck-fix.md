# Original-identity whole-face renderer — 2026-11-02

**Rejected and superseded.** The user subsequently rejected the fixed-frame
renderer throughout the clip for changed face shape. Its feature-frame-zero
retargeting, full-expression bypass and contour/lip warping were removed from
the active engine. See [per-frame source repair](ditto-own-frame-repair.md).
Do not interpret the historical selected-preset text below as current approval.

The rejected V2 rebuilt source is no longer used. The renderer now uses one real
closed-mouth frame (frame 0) from the approved original clip as its fixed identity.
It generates the entire face from that identity, then retargets the result to each
original video's head pose and facial outline. This removes the second generated
source pass and prevents the generated crop from overwriting the original neck,
hair, collar and body.

This is a concrete renderer/configuration change, not visual acceptance. The user
has not yet reviewed this result. It does not claim every distorted/pursed frame
is eliminated, or that physical speaker synchronization is solved.

## Rendering and attachment

- `trendcoffee/avatar_whole_face.py`: retarget all expression coordinates, align
  the facial contour, preserve the generated mouth shape while matching the
  source's lip-to-eye angle, and feather the entire face inside its outline.
  Eyes, cheeks and mouth are all generated; this is not a mouth-only composite.
- `scripts/ditto_realtime.py`: `reference_frame` selects the real identity frame.
  Its keypoint/feature pair stays together. Source speech cannot supply mouth
  pixels to this renderer. Rest fades the full expression toward that real closed
  identity while Ditto continues generating through silence.
- Motion prediction in this mode starts from the fixed identity each window,
  rather than feeding predicted identity/expression history back into the next
  window. A same-audio/same-pose diagnostic showed that feedback changed the smile
  and pursed shape across repeated utterances. The ordinary path keeps its existing
  chaining behavior. See `conditioning-comparison.png` in the evidence directory.
- Contour detection/alignment runs on the presenter, once per new face. GPU
  rendering proceeds in parallel. The first implementation serialized these
  steps and was slow; it was corrected before delivery. Sparse displacement maps
  and a face-sized output ROI avoid repeated full-image warps.

Head pose follows the original clip's head/body pose so the neck remains attached.
Audio drives the facial expression, including non-mouth expression points. This
preset does **not** add independent audio-driven pitch/yaw/roll to an unchanged
body; that earlier option remains incompatible with this reference renderer.

## Configuration and rollback

The selected `.runtime/trend-avatar.json` now uses the approved
`Tạo_video_chân_thực_cô_0e3fdbe0_1080p.mp4`, `reference_frame: 0`, `lip_factor: 0.5`,
`composite: full-face`, full TensorRT and `closed_source: false`. The constructor
enables continuous silence processing for this mode. Launcher flags and both
served/public posters were updated. The two posters use the original first frame,
matching the selected source. No UI source, speech playback or merchant code changed.

The prior profile, posters and edited existing engine/launcher files are preserved
in `.runtime/backup-face-neck-fix/`. Services and isolated server 8011 are stopped
after verification. The next ordinary avatar launch selects this renderer.

## Verification and limits

The isolated WebRTC fixture sends two prerecorded Maple greetings with a two-second
no-packet gap. The server is owned and terminated by the fixture. Its final capture
has 238 frames (720×1280, 24 FPS encoded, 9.917 s), about 146 generated faces and no
engine error. Neural throughput remains about 15 faces/s; encoded FPS repeats
faces. This is not a smoothness acceptance or a physical speaker-sync result.

The preview's audio is muxed after capture using the fixture WAV. It cannot
establish acoustic synchronization; the approximate packet-gap timing also differs
slightly from that WAV. The face comparison pairs the exact same source/body frames,
not necessarily the same audio phoneme. Do not grade phoneme correctness by
comparing the original clip's different spoken content with the new greeting.

Pixel regressions cover full-face replacement (eyes, cheeks and mouth), original
neck/hair preservation, affine placement, chin attachment, lip guide rotation,
identity/pose separation, expression/rest fade, fixed conditioning and per-face
alignment caching. The posterior/source consistency and launcher configuration
were also checked. **126 focused tests pass**; details are in `pytest-focused.log`.
Ruff lint and formatting pass.

Final fixture measurements: encoded neck-region difference from its matched
original frame falls from 8.20 to 1.95 RGB levels (encoding still contributes).
Speech aperture p95 is 0.139, maximum 0.161; quiet-window mean is 0.006.
These support containment of neck replacement and excessive opening, not aesthetic
acceptance. **Mouth tilt is still unresolved:** measured absolute p95 is 4.38°,
versus 2.46° in rejected V2. The geometric lip-guide operation passes its coordinate
regression, but has not established an end-to-end improvement in perceived mouth
tilt. Some visibly pursed shapes remain. Do not report all mouth defects fixed.

Full Python verification was attempted. The ordinary backend interpreter lacks
NumPy/OpenCV/Torch, producing 10 collection errors. A combined avatar/backend
environment ran **567 passed, 29 failed, 4 skipped**. The failures are recorded by
name in `full-suite-failures.txt`; they include UI selectors, kiosk voice boundaries,
the paused avatar-audio browser fixture (19 silent frames observed), and two MCP
subprocess environment failures. The two MCP cases pass when rerun with the actual
backend interpreter. The remaining browser/audio failures are not claimed fixed
or conclusively pre-existing; no frontend source was changed in this repair.
The final focused suite was rerun after the last renderer changes.

## Evidence

All artifacts are under `output/avatar-quality-review/face-neck-fix/`:

- [Live preview](../../output/avatar-quality-review/face-neck-fix/fixed-talking-head.mp4)
- [Original / rejected V2 / repaired renderer](../../output/avatar-quality-review/face-neck-fix/before-after.png)
- [Timeline contact sheet](../../output/avatar-quality-review/face-neck-fix/live-contact.png)
- [Measured geometry and encoded neck difference](../../output/avatar-quality-review/face-neck-fix/metrics.json)
- [WebRTC/engine report](../../output/avatar-quality-review/face-neck-fix/live-health.json)
- [Focused tests](../../output/avatar-quality-review/face-neck-fix/pytest-focused.log)
- [Full-suite failures](../../output/avatar-quality-review/face-neck-fix/full-suite-failures.txt)
- `live_fixture.py`, `review_fixture.py`, `measure_fixture.py` reproduce the fixture,
  comparisons and measurements. These are local diagnostic scripts, not application
  dependencies. Registration cache/checkpoints are diagnostic, not selected sources.

## Self-evaluation

Accuracy 4/5: pixel/transport evidence supports attachment and throughput claims;
perceptual quality remains unapproved. Completeness 3/5: a working renderer and
selected configuration are delivered; some mouth shapes, physical sync and
full-suite browser failures remain unresolved. Clarity 4/5: generated expression
and source head pose are distinguished; the UI review is still necessary.
Actionability 4/5: runnable preset, preview and rollback are provided; human
acceptance is outstanding. Conciseness 4/5: diagnostics stay in this report.
Average 3.8/5. Highest priorities: user visual review of the preview, then measured
speaker sync. The user may still reject the mouth; this report does not assume approval.
