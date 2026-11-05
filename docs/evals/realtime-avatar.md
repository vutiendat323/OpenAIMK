# Trend avatar acceptance — 2026-10-29

**Visual acceptance failed on further user review.** The neutral-source/compositing changes below
passed transport and pixel-preservation tests but the user supplied five further unacceptable
mouth/expression frames. Those checks did not establish acceptable facial realism. Crop/padding
variants and an isolated MuseTalk 1.5 comparison are under evaluation; no replacement model has
yet been accepted or deployed.

## Native MuseTalk result rejected; controlled diagnosis

The user explicitly confirmed that the native-prepared 123 clip still fails naturalness.
Eight controlled samples separate VAE reconstruction from synthesis and compare FP16 with FP32.
The VAE-only control retains lip shape substantially better in inspected frames; FP32 synthesis
is visually almost unchanged (lower-face RGB MAE 0.023–0.027 / 255, not a quality score).
Paired chin-margin 0/10/20px trials alter mouth opening but provide no consistently convincing
source-like lip/tooth detail in inspected samples. No candidate promoted; source acceptance and
realtime performance remain unresolved. Report: `output/avatar-quality-review/muse-diagnosis-123/REVIEW.md`.

## Native MuseTalk preparation completed — new 123 clip

Prepared `123_Tạo_video_chân_thực_cô_48e0af4f.mp4` with LiveTalking's native MuseTalk v1.5
landmark/extra-margin/face-parsing pipeline, replacing the experimental Wav2Lip-crop shortcut
for this evaluation.200frames/boxes/latents/masks validated. Rendered source audio8s and kiosk
greeting2.68s, plus a moving side-by-side head comparison. All outputs fully decoded successfully;
active kiosk manifest/poster unchanged. The inspected lips/teeth remain softer than source;
perceptual quality and live realtime performance are not accepted. Full report and reproduction:
`output/avatar-quality-review/muse-prepared-123/REVIEW.md`.

## Lip appearance rejected again — 2026-10-29 20:14 local

User supplied three further mouth crops and explicitly expects the original talking clip's lip
appearance. Eight offline CPU samples compared the original1080p source, MuseTalk on720p and
MuseTalk on1080p. Higher source resolution alone still visibly softens synthesized lips/teeth;
no candidate was deployed. These samples use greeting audio different from the source, so they
do not compare exact phoneme shape or prove synchronization accuracy.

The experimental MuseTalk importer reuses Wav2Lip crops/custom masks, unlike the upstream
landmark-based MuseTalk preparation plus v1.5 chin margin/face parsing. Previous experiments
therefore do not establish a correctly prepared MuseTalk model's quality ceiling. Faithful
preparation remains outstanding. Detailed scope and images:
`output/avatar-quality-review/lips-1080/REVIEW.md`, `comparison-025.jpg`.

## Latest instrumented correction — 2026-10-29 19:47 local

A subsequent user trial confirmed missing words while silent and during interruption. At the first
instrumented snapshot, native input had zero underflow frames; Fusion rejected a known TARGET
with ASD unavailable after a timeout and mouth score 0.308. The longer session subsequently had
one input underflow and also explicit negative ASD rejections (score 0.015). These are distinct
cases; the correction below only addresses temporarily missing visual evidence. Snapshots are
`output/voice-live-target-rejection.json` and `output/voice-live-before-edge-recovery.json`.

`SpeakerStream` now defers a rejected word edge only when it was a locked solo TARGET, ASD timed
out, and there was no explicit negative ASD, other/unknown/bot label, overlap or mask. It releases
that edge only next to an ACCEPT row of the same recorded target, within 320ms before or 240ms
after. An identity change, missing timeline span, mask, explicit rejection or lack of nearby
confirmation keeps the audio silenced. The host additionally requires the fresh current owner.
New reasons `kept_target_onset`/`kept_target_tail` make recovered edges inspectable. The failing
trace test previously released zeros immediately; it now retains onset/middle/tail samples.
93 Audio application/host-contract tests and 66 focused root tests pass.

The user separately reported ongoing listening/speaking label changes during longer replies.
A real Chromium fixture with a 500ms clause pause reproduced two speaking starts. A presentation-only
`SpeakingIndicator` now holds the label for 750ms across a short pause; native playback notifications
to Fusion remain immediate. User interruption, session reset and microphone shutdown clear the label
immediately. The same browser fixture now reports one speaking start and one final listening state,
with the intentional pause still audible (10.5s span for 10s speech plus 500ms pause). This does not
hide audio loss: the PCM continuity test remains separate. Manual Stop is available even when the
avatar visual stream is absent. Frontend 31 tests, TypeScript/Vite build, lint and formatting pass.

API was restarted only after the guest session ended. This correction is deployed, but acoustic
input completeness and visual quality have not yet been accepted. Explicit negative ASD rejection
and changing diarizer identities remain possible causes to investigate in future real traces.

## Follow-up: user retest still failed

The user retested the direct-speaker/AGC-off build and still reported missing words and repeated
listening/speaking changes, both while the assistant was silent and during interruption. That build
is **not accepted as a fix** for input completeness or conversation state.

A new deterministic native-output test reproduced a specific gap: during an assistant turn with
an 800ms quiet pause, the existing amplitude gate forwarded only 79 of 100 RTP-decoded packets.
The browser exhausted its PCM queue and restarted on the next clause. `NativePeer.receive_audio`
now retains the entire media clock while the native assistant turn is active; idle comfort noise
outside turns remains gated. The regression now receives all 100 packets, including all 40 silent
packets; all 12 native-peer tests pass. This is a reproduced contributor, not a claim that every
observed state change has been explained.

A second regression increased real Chromium main-thread stalls from 45ms to 120ms, consistent
with the observed input-delivery stalls. The 80ms minimum speaker buffer then failed sample
continuity (maximum sample error 0.5493) and emitted extra speaking transitions. Raising the browser
player's minimum startup buffer to 160ms (maximum 200ms) passed the same render test; this adds about
80ms of startup latency on low-latency devices. It does not excuse missing speech or GPU lag.

An actual native-voice probe after the media-clock repair recognized the full prerecorded greeting
and returned 341 packets/6.82s of 48kHz PCM (maximum packet gap 84.7ms), without any business tools.
Artifacts: `output/native-voice-continuity.json`, `output/native-voice-continuity-48k.wav`.
The physical microphone and Fusion were not part of that probe.

Input diagnosis is now exposed numerically in `/api/kiosk/status`:
`native_input_transport` counts missing-input render frames and maximum queued duration;
`fusion_verdicts` and `fusion_last_accept/reject/uncertain` expose input RMS, ASD/mouth scores,
category labels, echo rejection counts and late ASD evidence. No raw speech, transcript, face ID
or embedding is included. These measurements distinguish model rejection from a starved native
input clock without lowering identity thresholds. Focused Python regressions: 60 passed.

The last pre-instrumentation live session had 967 microphone packets (maximum delivery gap 204.3ms),
984 Fusion packets (maximum gap 474.9ms), 172 silenced-reject packets and 106 kept packets. These
aggregate counts alone cannot attribute the missing words to a particular rejection or gap.
Physical mic completeness, UI stability on real conversation and visual quality remain unresolved.

## Latest voice recovery — 2026-10-29 15:45 local

**Overall acceptance remains open.** The user still reported intermittent recording, clipped words,
raspy/stuttering playback and unacceptable generated faces after earlier passing tests. Historical
measurements below are not evidence that those real-world symptoms were resolved.

Changes deployed in this iteration:

- Native 48kHz PCM now goes directly to the existing browser AudioWorklet speaker. The avatar gets
  a visual copy; its returned RTP audio is not connected to output. Initial avatar negotiation and
  reconnects do not block voice, and visual recovery cannot clear the native speaker queue.
  Explicit user interruption and guest boundaries still stop both paths.
- Browser `autoGainControl` and `noiseSuppression` are false; `echoCancellation` stays true.
  No system volume was changed. Existing tabs require reload/rearming to apply new constraints.
- The staged post-handshake Fusion readiness check waits up to three seconds for fresh evidence
  instead of rejecting a session on one transient missing camera frame. Identity/liveness checks
  remain enforced.

Verification:

- New regression reproduced zero independently delivered speaker samples when the avatar socket
  stalled. After separation it preserves all 192,000 expected PCM samples through visual recovery;
  explicit interruption stops subsequent PCM. Frontend: 30 tests passed, build and lint passed.
- Real Chromium, built UI, simulated native events: a renderer that never answers SDP and drops
  its socket every three seconds cannot stop a 10-second utterance. Output span 10.02s, zero
  interior silent 20ms windows, one speaking→listening transition. This case runs without a GPU.
- Same Chromium/UI test against the running GPU/WebRTC engine: 500 native packets, 10.02s output,
  zero interior silent windows; one speaking→listening transition. The avatar received all 500
  copied packets over 9.986s. These tests measure browser-rendered PCM, not acoustic speaker quality.
- Two direct native-packet AudioWorklet render tests passed, including 45ms UI stalls and packet
  jitter. Focused Python input/identity/playout/worker/kiosk/API regressions: 68 passed.
- Actual default microphone opened by Chromium: AGC=false, noise suppression=false, echo
  cancellation=true, mono 48kHz. Default USB input stayed at 100%/0dB throughout a six-second
  constraint check; raw speech was not saved. Evidence: `output/microphone-constraints-check.json`.
  This does not establish long-session stability or absence of acoustic clipping.
- An earlier actual native-voice probe preserved the full prerecorded greeting transcript and
  returned 486 packets/9.72s of 48kHz PCM, maximum delivery gap 122.6ms. It bypassed physical
  microphone/Fusion, so it does not prove the user's two lost-word examples are fixed.
  Evidence: `output/native-voice-recovery.json` and `output/native-voice-recovery-48k.wav`.

Remaining: user's acoustic retest of both exact sentences and speaker output, timing under sustained
Fusion load, and visual/perceptual lip-sync acceptance. Separating voice from the renderer can expose
video lag; no new A/V skew claim is made. The Wav2Lip visual model is unchanged and remains visually
rejected. MuseTalk/TensorRT experiments are not activated by this voice repair.

Self-review: accuracy 4/5 (browser evidence scoped; acoustics unverified), completeness 2/5
(user-visible speech and visual acceptance still outstanding), clarity 4/5 (current path separated
from historical evidence), actionability 4/5 (built and running, reload needed), conciseness 4/5
(details retained here). Average 3.6/5. Next priority is the user's live retest; do not equate passing
synthetic transport tests with a completed avatar feature.

## Delivered behavior

The kiosk uses the supplied green-apron Trend character throughout live video, idle and the poster.
The former gold-dress sample is no longer selected. The neutral source
`Female_staff_member_standing_3128c196.mp4` and original waving clip were prepared locally with
upstream Wav2Lip's avatar generator (250 neutral + 149 waving frames). Runtime is 720×1280/25fps;
the original MP4s remain untouched. Existing native Codex voice is preserved; source-clip
audio is available as local QA WAVs and is not mixed into customer conversation.

A new guest triggers a one-shot wave. The same Wav2Lip model lip-syncs that waving source while
speech continues. Operator controls in Settings select Wave, Smile and Idle. Smile is the final
35 frames of the waving clip; idle and speech share the full neutral clip without rewinding when
the speaking state changes. Actions finish or are
cancelled on interruption/reset. Epoch checks reject retired audio at inference and media-publish
boundaries, and reset clears already-queued video/audio. WebRTC recovers without changing identity.

## Regression fixes

Whole greeting WAVs previously flooded transport/engine queues. Browser PCM is now paced with one
unacknowledged packet; the engine waits for input capacity (bounded at 500ms) instead of rejecting
normal cold-start bursts. A stalled renderer has a bounded timeout and reconnect path. The new
flow-control test failed with four packets sent before the first acknowledgment; it passes with one.

Custom upstream action audio would preempt conversation. The motion adapter selects source frames
instead, allowing gestures and live speech together. Both datasets use the existing model weights;
there is no second voice model or generative-video cloud service.

## Evidence

Initial integration measurements below predate the neutral-source correction; see the later
sections for the current audio and face-quality checks.

- 63 focused Python tests passed: controller, avatar protocol/auth, launcher, API, native peer,
  kiosk runtime. Controller tests cover wave completion during speech, smile selection, idle,
  interruption and 99 repeated guest-reset boundaries.
- 28 frontend tests passed, including slow engine acknowledgment, bounded greeting streaming,
  clearing pending speech and immediate local gain mute. TypeScript/Vite build, oxlint,
  Ruff lint/format and changed-file Prettier checks passed.
- Real Chromium/GPU lifecycle test with gestures passed against an isolated local engine:
  full greeting, native audio event, wave with speech, Smile/Idle controls, interrupt/resume,
  forced WebSocket loss, reconnection, next guest and microphone disarm/rearm. Uses simulated
  voice events and an isolated service database; it does not create merchant orders.
- Real GPU/WebRTC sustained fixture: 20 utterances with wave requests, 1438 video / 2872 audio
  frames, 2142 audio frames containing signal, **25.0 received FPS**, **226.8ms first video** after
  SDP application. About 57 seconds of received video; not a 30-minute soak or percentile claim.
- Real RTP interruption regression: 440Hz old turn → reset → 880Hz new turn. **0 retired-tone
  frames after the new turn**, 80 detected new-tone frames, first new audio 441.2ms after reset.
  This verifies stale media rejection, not physical-speaker mute latency.
- Artifacts: `output/avatar-browser/trend-wave.png`, `trend-wave-speaking.png`, `trend-talking.png`,
  viewport screenshots (375/768/1440px), `output/avatar-smoke.json`, `output/avatar-interrupt.json`.
  Wave image visibly shows the supplied Trend character raising her hand. Compact stage is centered.

## Final deployment check

Visual, avatar and API were started through the managed launcher with the prepared Trend manifest.
Live `/api/avatar/status` reports enabled/ready and idle/wave/smile. Authenticated `/api/avatar`
returns `flow_control: true`; `/api/kiosk/voices` returns the existing Codex voice list. The deployed
page loads the 720px Trend poster and an enabled microphone button without page errors. A short
protocol check created an isolated guest session but did not start a voice/customer/order flow.

## Scope of the evidence

The browser uses real WebRTC/LiveTalking/CUDA and fake kiosk voice events; actual native voice
behavior is covered by existing native-peer/kiosk tests, not a recorded live customer conversation.
No perceptual A/V-skew benchmark, physical-speaker interruption measurement, 30-minute active-Fusion
soak, full accessibility audit or Core Web Vitals audit was performed. No previous visual baseline
exists, so screenshots are inspection evidence rather than a visual-regression pass.

Runtime remains one local avatar session. The prepared environment is not a fresh-machine installer.
Preparation downloaded upstream S3FD once; subsequent preparation and runtime use the local cache.
No merchant order, payment or print job was created for these checks.

## Background seam fix

The source poster's pale-green background was (228,234,221), while the card/letterbox used
(245,246,240). A live-page pixel probe measured a 19-level RGB step across the poster's bottom
edge. The card and idle viewport now share #e4eadd; the stage gradient and compact control backplate
were removed. Poster/video elements fit the 9:16 content bounds using container units; a narrow
CSS edge mask smooths remaining spatial color variation in the source clips. No per-frame pixel
processing or changes to voice/model data were introduced.

The original probe now measures a 1-level step. Real Chromium/GPU lifecycle regression passed
in 43.73s, including speech and gestures; 375/768/1440px captures inspected. Build/typecheck,
oxlint and changed-file Prettier passed. This measurement targets the reported light-theme seam,
not a claim that every background pixel in the original video is uniform.

## Output-audio regression: source-sized packets and speaker capture

Earlier FPS/audible-frame checks did not establish audio fidelity. A new deterministic test sent
continuous native-sized 20ms packets with callback jitter: 4s input became 4.32s output with five
20ms silent frames inside it. Upstream's 10ms input wait synthesized silence before the next
20ms packet arrived. That wait was replaced for active PCM, and utterance pre-roll added.

Playback now preserves original 48kHz PCM while deriving a separate 16kHz model copy. Unit tests
verify exact original bytes, including low bits. Audio has its own 20ms RTP clock and emits actual
silence when empty; it no longer waits for GPU batches or forces the receiver to repeat audio.
The first corresponding video frame releases the source onset. Source send pacing uses a
cumulative media clock with bounded catch-up, rather than accumulating callback overhead.

The UI's previous instantaneous 40ms peak detector changed speaking on every phoneme pause;
its regression produced twelve alternating notifications in 480ms. It now latches speaking
through pauses and closes after the source tail drains, preventing idle comfort-noise restarts.
Explicit stop/interrupt still mutes immediately.

Evidence after correction:

- Direct real WebRTC fixture: 4s in / 4.0s out, zero interior silent frames; 12kHz component
  survives at measured amplitude 1257.5 (source 1800). Speaker audio is no longer low-passed by
  the model's 16kHz input. `output/avatar-audio-quality/{source,avatar}.wav` and `metrics.json`.
- Real Chromium AudioWorklet capture, 500 packets / 10s, five deliberate 45ms UI stalls:
  zero interior silent frames, 9.96s detected output span (within 60ms codec margin), exactly
  one speaking transition followed by listening. Sender span 9.9864s. Receiver mean jitter-buffer
  delay fell from approximately 183ms to 33ms in the measured runs. This metric is not total
  end-to-end latency or a percentile guarantee.
- Original source byte preservation, video-onset gating, retired guest rejection and UI
  phoneme-pause/idle-noise behavior have regression tests. These are digital-output measurements,
  not a physical-loudspeaker or live customer recording.

Final checks for this audio fix: 69 focused Python/browser-source tests and 29 frontend tests
passed. The real avatar gesture/guest lifecycle test passed in 41.47s. Final RTP reset check
reported zero retired-tone frames after the new turn (first new audio 476.8ms after reset).
The managed API/avatar services were restarted; production status reports the Trend avatar ready.

## Neutral source and face compositing correction

User review found unacceptable mouth/face frames despite earlier transport tests. The supplied
neutral clip is 10 seconds, 720×1280/24fps, with closed lips and gentle head motion in sampled
frames. It replaces the already-speaking source for both idle and speech. The former source is
retained on disk; gestures still use the supplied waving clip.

Fifty matching audio-feature/frame samples were rendered for old and neutral sources. Neutral
source removes the preexisting open-mouth poses that compete with the generated mouth; this is
visual comparison evidence, not a quantitative perceptual-quality score. Source face crops remain
approximately 158×212 pixels before model resizing, so a 256-pixel model input does not restore
detail absent from the source.

The original compositor overwrote the whole face rectangle, including eyes. A regression fixture
showed a 180-level edge and modified eye pixels. The new lower-face mask preserves eyes/forehead,
feathers the boundary and fully replaces the mouth interior. In the 50 real-source composites,
the upper-face pixel difference is zero before video encoding. Four pixel tests pass. A controller
regression first failed by returning frame 0 on speech onset instead of continuing at frame 3;
the shared neutral range now continues through speech changes. Legacy manifests remain supported.

Final video review also exposed compression blocks when the head tilted. The same 250 source
frames were encoded/decoded with the actual aiortc VP8 codec, independently of lip synthesis.
At 500kbps, face PSNR averaged 34.58dB (worst frame 29.78dB); at 3Mbps it was 37.79dB
(worst 35.19dB). Encoder p95 in that run increased from 6.34ms to 8.75ms, below the 40ms frame
interval; this excludes inference/network time. `output/avatar-quality-review/codec/` contains
metrics and matched crops. The local wrapper now starts video at 3Mbps with 1.5–6Mbps adaptation,
confined to its own process. This addresses compression loss, not the model's mouth-generation limit.

Current verification:

- 77 focused Python tests passed, including manifest selection, continuous motion, gesture ranges,
  protocol, native voice and kiosk regressions; four compositor tests passed in the avatar venv.
- 29 frontend tests passed; TypeScript/Vite build and changed-file Ruff checks passed.
- Real Chromium/GPU gesture/interrupt/reconnect/next-guest test and speaker-capture test passed
  in 57.57s combined after the codec correction. The 500-packet fixture returned 10.0s of output with zero interior silent
  frames, zero concealed samples and one speaking transition, then listening. Mean measured
  receiver jitter-buffer delay was 42.0ms; this is not end-to-end latency.
- `output/avatar-quality-review/neutral-comparison/` holds matched source/render contact sheets.
  `neutral-avatar-preview.mp4` in its parent directory records real WebRTC with a local greeting
  fixture. `output/avatar-browser/` contains live speech/gesture captures.

The neutral manifest selects `trend_talking_b480c208ee17`; the managed avatar service was restarted
after the active voice session ended. The original native-voice API process was retained. Poster
and built static assets now use neutral frame 0. Prior manifest/poster are retained under
`.runtime/avatar-before-neutral/` for rollback.

Remaining limit: mouth/tooth synthesis can still soften or distort in individual phonemes and
poses. These checks establish motion continuity, source-eye preservation and transport behavior;
they do not establish perfect facial realism or replace perceptual acceptance across longer speech.

## Self-evaluation

Accuracy 4/5: hardware/browser evidence and exact measurement limits recorded; perceptual realism,
skew and acoustic latency are not fully measured. Completeness 3/5: supplied assets, wave/speech,
expression control, deployment and regressions covered; facial realism still has a model limit.
Clarity 4/5: source expressions distinguished from generated emotions; protocol crosses three layers.
Actionability 4/5: running kiosk plus one preparation command; fresh-machine setup still separate.
Conciseness 4/5: commands live in the runbook; detailed evidence retained here. Average 3.8/5.
Next improvements: broader perceptual mouth-quality review, active-Fusion long soak and acoustic
synchronization measurement. Visual quality must not be inferred from FPS or passing protocol tests.
