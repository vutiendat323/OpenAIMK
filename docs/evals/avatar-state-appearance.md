# Avatar appearance across states — 2026-10-30

The user reported a sharp, warmly colored idle avatar becoming a softer,
differently colored character while listening/speaking. Two separate defects were
reproduced and fixed; this supersedes the previous `123_…` appearance selection.

## Causes and corrections

1. **Different source clips.** The poster and idle used
   `Female_staff_member_standing_3128c196.mp4`, while speech used
   `123_Tạo_video_chân_thực_cô_48e0af4f.mp4`. The latter already has different skin,
   lighting, body pose and detail before inference or encoding. Comparing the
   720×1280 poster against the active source's first frame failed with RGB MAE
   **20.17/255**. Selected the existing standing clip as the common non-gesture
   source, retaining the preferred sharp poster. The same check now passes at
   **0.009/255**, attributable to the existing poster's decode/preparation path.
2. **Whole-face neural replacement.** The previous Ditto putback replaced a broad
   face region, modifying eyes, hair, cheeks and texture although only speech
   expression was needed. `avatar_appearance.composite_mouth` now preserves the
   original RGB frame outside a feathered mouth/lower-jaw region. Source lip
   landmarks are captured during the SDK's existing registration pass, with no
   second detector/model or additional GPU inference. The mouth interior is fully
   replaced so closed source lips are not superimposed on the generated mouth.
3. **Different idle/speech frame clocks.** The idle loop used modulo indexing,
   while speech used mirrored indexing. This could jump body/head pose when a
   source loop reversed. Both now use the same source frame index.

The explicit wave action retains the supplied waving clip and uses the same
source-preserving mouth composition while speaking. Its sampled background is
`[228,234,221]`, versus standing `[227,234,222]`. No global recolor, smoothing,
sharpening/restoration model, resolution reduction or audio change is introduced.
Poster equality is also checked by a local installed-asset regression test, skipped
when there is no installed Ditto manifest.

## Real model comparison

Same prerecorded greeting, fixed seed 17, five motion steps. Three sources × three
audio contexts (0.8 / 1.4 / 2.0 s) were rendered on the actual RTX 3060. This was
performed while the kiosk had no active voice, after stopping its owned avatar.

In the measured upper-face crop, whole-face replacement changed source pixels by
**4.06/255 mean RGB MAE** across nine cases. The new compositor's difference is
**exactly zero** in that region for all nine cases, before video encoding. This
proves source-pixel preservation in the sampled region; it is not an objective
naturalness score or a claim of lossless WebRTC.

- [Before / deployed source-preserving result / source](../../output/avatar-quality-review/state-appearance/deployed-appearance-comparison.jpg)
- [Same-source compositor comparisons](../../output/avatar-quality-review/state-appearance/mouth-region-comparison.jpg)
- Source metadata: `output/avatar-quality-review/state-appearance/sources.json`.
- Per-case measurements: `mouth-region-metrics.json` in the same directory.

The before/deployed comparison intentionally includes the previous source choice;
the same-source comparison isolates the compositor change. Source frames are
appearance references and do not depict the new utterance's correct phoneme.

## Verification and deployment

**69 focused tests passed** using the prepared avatar NumPy/OpenCV environment.
Regression checks cover exact preservation of original upper face/background,
fully replaced mouth, affine placement, feathering, offscreen geometry, existing
landmark-pass reuse, pose mutation, common idle/speech indexing, source/poster
agreement, transport, PCM and epochs. The compositor integration and shared-clock
tests were observed failing before their respective fixes. Ruff lint and format
passed for all four changed Python files.

The browser/GPU regression did **not** pass on this attempt: it observed seven
avatar-socket connections instead of one and upstream HTTP errors. A real kiosk
voice session was subsequently confirmed active. This run is not counted as a
passing browser result; further GPU/peer tests were deferred to avoid competing
with that session. The engine remained ready, reported no inference error and
continued generating frames for the running kiosk. WebRTC compression has not been
isolated as an additional quality loss in this change.

The existing managed avatar was restarted with the new source/compositor. Visual,
avatar and API were checked listening on 9877/8010/8080; avatar ready, no error,
work-time budget still 0.8. Current source is recorded in
`.runtime/trend-avatar.json`; previous selection is retained in
`.runtime/trend-avatar.before-appearance.json`. No merchant/payment/printer actions
or new microphone recordings were used for tests.

## Remaining boundary

The generated lip/tooth interior is still Ditto output. Preserving the original
eyes, skin, hair and body does not establish that generated teeth match the
original character. This patch addresses the reported state-dependent source,
color and whole-face detail changes; anatomy and perceived sharpness of the
generated mouth remain subject to visual acceptance.

## Self-evaluation

Accuracy 4/5: actual source/pixel measurements, real model outputs, browser failure
and scope of evidence are explicit. Completeness 4/5: source consistency and
upper-face preservation are deployed; uninterrupted browser acceptance remains
unverified while real voice is active. Clarity 4/5: source choice, compositor and
codec effects are separated. Actionability 4/5: installed-asset test, persistent
source choice and comparison artifacts; GPU comparison runner remains an
experimental script in `.runtime/evaluate_state_appearance.py`. Conciseness 4/5:
detailed evidence stays here. Average 4.0/5. Improvements by impact: verify browser
behavior when the real session is idle; evaluate lip/tooth interior separately
from preserved upper-face detail. Would the user agree? Perceptual acceptance has
not yet been reported for this version.
