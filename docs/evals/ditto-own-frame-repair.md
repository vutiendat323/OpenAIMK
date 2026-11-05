# Per-frame source repair — 2026-11-02

The user rejected the previous fixed-frame renderer throughout the clip and asked
whether the images had actually been reviewed. They had been viewed as contact
sheets, but the assessment was wrong: changed face shape was allowed through and
the preset was selected despite failed appearance acceptance. Passing logic tests
did not justify that selection.

## Corrected source/render boundary

The rejected code reused frame-zero appearance features for every head pose,
combined them with other frames' geometry, added predicted displacement to all
expression points, bypassed Ditto's normal expression protection, and then warped
the face outline/lips in 2D. All of those custom retarget/outline operations have
now been removed from the active renderer.

The replacement preserves the source frame's own geometry/feature pair:

1. During registration, prepare only the lips of each 512px source crop using
   real closed-mouth pixels from original frame zero. Eye spacing and eye roll
   set the donor scale/rotation, not the speaking frame's changing lip width.
   The mask covers the union of old/new lip contours; it excludes the chin,
   eyes, nose, hair and neck. Outside that mask the prepared pixels are exact.
2. Extract **both** appearance features and source geometry from that same
   prepared crop. The original full-frame body/background image is unchanged.
   The temporary crop encoder adapter is restored even if registration fails.
3. At runtime, render from **this frame's** features and source keypoints.
   Use Ditto's normal motion-stitch path, with source-relative speech displacement
   on its supported lip points. Other face structure and the source eye state
   remain protected. The decoder still generates one complete RGB face, not a
   mouth-only output patch.
4. Composite the complete generated face inside the current original facial
   outline. There is no cross-frame outline triangulation, independent mouth
   rotation, or reuse of frame-zero appearance features in runtime rendering.
   Neck/hair/collar stay original before stream encoding. Head pose follows the
   source body; no independent audio pose is imposed on it.

`reference_frame: 0` now selects the real closed mouth donor during registration,
not a fixed appearance-feature frame. The CLI help was corrected. The source
asset was concurrently relocated from the repository root into `output/`; the
profile now points at `output/Tạo_video_chân_thực_cô_0e3fdbe0_1080p.mp4`, still the
same approved character/clip (1080×1920, 239 frames, 24 FPS). The wave-source
lookup supports that relocation too. No rejected standing person was restored.

## Checks actually performed

- Same-frame/same-drive diagnostics isolated full-expression protection from
  the fixed-appearance transfer. Removing full-expression displacement alone
  was insufficient; the fixed appearance/pose transfer still changed the face.
- Six direct per-frame renders were inspected beside the original source.
  Source-crop differences outside the mouth mask were exactly zero in each.
- The actual local server was exercised with two prerecorded greetings and a
  no-packet silent gap. It captured 238 frames, 720×1280, 9.917 s, 24 encoded FPS,
  148 generated faces (~15/s), with no engine error. The server was terminated
  after capture. It was not tested with a real guest or physical speakers.
- All **238 decoded output frames** were viewed in six numbered contact sheets,
  not only a small set of selected good frames. In that inspection the head no
  longer acquired the conspicuously different viewing angle of the rejected
  fixed-frame result. Pursed shapes remain, notably around frames 52–55 and
  176–179. This is an inspection finding, **not user visual acceptance**.
- Current focused suite: **129 passing tests**; Ruff lint/format pass. Regressions
  cover the mouth-only preparation boundary, donor width independent of source
  speech, encoder restoration, protected non-lip expression points, per-frame
  feature/keypoint pairing, whole-face output scope and source/poster consistency.
  Obsolete tests enforcing the rejected retarget/2D-warp behavior were removed
  along with that behavior; the prior files are preserved for history.
- The prior full-suite run remains non-green (567 passed / 29 failed / 4 skipped,
  including UI/audio browser cases and two MCP interpreter failures subsequently
  passing under the backend interpreter). It was not rerun wholesale for this
  focused repair. See the previous report and its named failure log; these failures
  are not claimed resolved.

The same metric script now reports speech opening p95/max 0.150/0.166, rest opening
mean 0.006, absolute mouth tilt p95 2.65° (rejected fixed-frame: 4.56° in this run).
These geometry numbers do not grade naturalness or phoneme accuracy. The preview
audio was muxed afterwards; it is not evidence of acoustic synchronization.
The measured neural throughput is ~15 faces/s, not 24 newly generated faces/s.

## Artifacts and active state

- [Video](../../output/avatar-quality-review/own-frame-repair/talking-head.mp4)
- [Original / rejected fixed-frame / per-frame renderer](../../output/avatar-quality-review/own-frame-repair/before-after.png)
- [All frames 0–39](../../output/avatar-quality-review/own-frame-repair/all-frames-1.png),
  [40–79](../../output/avatar-quality-review/own-frame-repair/all-frames-2.png),
  [80–119](../../output/avatar-quality-review/own-frame-repair/all-frames-3.png),
  [120–159](../../output/avatar-quality-review/own-frame-repair/all-frames-4.png),
  [160–199](../../output/avatar-quality-review/own-frame-repair/all-frames-5.png),
  [200–237](../../output/avatar-quality-review/own-frame-repair/all-frames-6.png)
- [Metrics](../../output/avatar-quality-review/own-frame-repair/metrics.json),
  [live report](../../output/avatar-quality-review/own-frame-repair/live-health.json),
  [tests](../../output/avatar-quality-review/own-frame-repair/tests.log)

The engine uses the selected profile with the repaired per-frame path; services
are stopped. The rejected fixed-frame implementation/profile/tests are preserved
under `.runtime/backup-rejected-reference/`. This is a reviewable correction,
not a claim that every visual defect, jerk, or mouth/audio delay has been solved.

## Self-evaluation

Accuracy 4/5: source/render pairing, mask scope and transport are verified; visual
acceptance remains human. Completeness 3/5: per-frame appearance transfer is
repaired, but pursing, physical sync and prior suite failures remain. Clarity 4/5:
whole-face generation and source preparation are distinguished; donor-frame flag
naming is historical. Actionability 4/5: complete preview and every-frame sheets
are provided, with rollback. Conciseness 4/5: implementation detail stays here.
Average 3.8/5. The user's latest verdict remains rejection of the prior result;
no acceptance of this one is assumed.
