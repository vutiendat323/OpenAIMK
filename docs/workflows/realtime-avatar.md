# Local Trend realtime avatar

The kiosk uses `Female_staff_member_standing_3128c196.mp4` as its neutral idle/speech source and
`Café_assistant_waving_hand_a1410f2d_1080p.mp4` for gestures. Avatar rendering and motion run locally
on the RTX 3060; existing native Codex voice is retained as agreed. No source-clip audio is mixed
into conversation, and no cloud TTS/video-generation service runs in the avatar pipeline.

**Active profile: Ditto**, selected by `.runtime/trend-avatar.json`. The launcher
runs `scripts/ditto_server.py`; the old LiveTalking preparation sections below are
legacy procedures and will change the engine selection if run.

Presentation is 24 FPS from the actual source video. The prepared
`tensorrt-mouth` profile measured 15.6 generated mouth FPS in speech and 16.0
during waving; changed-pose rates are separate. Rest restores the original source
smile. Native voice stays independent. [Measurements, accuracy contract and review clip](../evals/avatar-neural-throughput.md).

## Start the prepared kiosk

```bash
cd /home/metek/Projects/OpenAIMK
.venv/bin/python scripts/kiosk.py start
.venv/bin/python scripts/kiosk.py status
```

Open `http://127.0.0.1:8080`, refresh an existing tab, and select **Bật micro / Turn on microphone**.
Wait for readiness; stand in front of the camera or select **Bắt đầu nói**. A new guest triggers
one wave. Speech continues through the waving clip using the local Ditto mouth worker.

In **Cài đặt / Settings**, while the microphone is on, use **Vẫy tay / Wave**, **Mỉm cười / Smile**,
or **Đứng chờ / Idle**. Actions finish automatically; interruption cancels the current action and
pending speech. Idle cancels a selected gesture; an ongoing conversation keeps its speech motion.
Smile uses the selected source expression in the active Ditto profile.

```bash
curl http://127.0.0.1:8080/api/avatar/status
```

Expect `enabled: true`, `ready: true`, `actions: ["idle", "wave", "smile"]`.
The launcher starts Visual (9877), the selected avatar (8010) and API (8080). Warm-up continues after
startup returns. Logs: `.runtime/kiosk-{visual,avatar,api}.log`.
Use `.venv/bin/python scripts/kiosk.py stop`; add `--service avatar`, `api` or `visual` to target
one owned process. Unrelated processes on occupied ports are never replaced.

## Verify the active Ditto profile

`/api/avatar/status` should report `engine: "ditto"`, `ready: true`, and
`video_only: true`. `/trend/health` on port 8010 reports `presentation_fps: 24`,
`published_fps`, `rendered_fps` and processing timings separately.
The prepared neural target is a ceiling, not measured throughput. The partial
decoder cache is bound to both source videos and requires every mouth/gesture
region to fit its validated rectangle. See the measurement document for cache
preparation after a source, weight or TensorRT change.

Use an **exclusive warmed test instance** on 8011 for hardware verification:

```bash
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/ditto_cadence.py \
  --url http://127.0.0.1:8011 --output output/avatar-smoothness
```

Do not compete with an active kiosk peer or run a second GPU model while real
voice is in use. The active source needs no Wav2Lip/MuseTalk asset rebuild to start.

## Legacy LiveTalking asset rebuild

The original MP4s remain untouched at the repository root. Run with the prepared upstream
interpreter; face detection/cropping uses upstream's own avatar builder, not a manually composed
set of models:

```bash
.runtime/livetalking-venv/bin/python scripts/prepare_trend_avatar.py \
  --talking 'Female_staff_member_standing_3128c196.mp4' \
  --wave 'Café_assistant_waving_hand_a1410f2d_1080p.mp4' \
  --idle-source talking
npm --prefix frontend run build
```

Prepared frames: 720×1280/25fps. The neutral original is 720×1280/24fps, 10 seconds; the waving
original is 1080×1920/24fps. Both sets use 256×256 Wav2Lip face
crops. The script rejects a missing face and writes `.runtime/trend-avatar.json` only after both
sets succeed. Hash-named datasets are cached. Source audio is extracted into
`.runtime/trend-avatar/{talking,wave}-source.wav` for local QA.

The manifest selects all 250 neutral frames for both idle and speech, 149 waving frames and the
35-frame smile ending. `--talking` names the speech-animation source; a neutral closed-mouth clip
is preferred to a clip already speaking. `--idle-source talking` shares that source without
resetting its frame position when speech starts/stops. Legacy manifests still use the waving
clip's first 18 frames for idle. The launcher reads the manifest automatically. The matching poster is
`frontend/public/avatars/trend-live.png`. Restart the avatar after rebuilding assets when no guest
is active. If preparing on a new machine, install the upstream environment/model first; the script
is an asset importer, not a fresh-machine installer.

Upstream checkout: `.runtime/LiveTalking`, pinned `c7269433a2b6ecebcd9342445d2ecc882c98b0da`.
Interpreter: `.runtime/livetalking-venv`; model: `models/wav2lip.pth`. The upstream S3FD preparation
weight downloads once to `.runtime/torch/hub/checkpoints`; rendering thereafter is local.

## Legacy LiveTalking runtime behavior

Native voice PCM → browser AudioWorklet → speaker. A copy goes through the authenticated
same-origin WebSocket → loopback LiveTalking → WebRTC video. Returned avatar RTP audio is not
connected to the speaker or the UI speaking indicator. Renderer startup, missing acknowledgments
and reconnection therefore cannot discard or mute the native speaker queue. Explicit interruption,
guest changes and microphone shutdown still clear both paths.

The visual copy is paced with at most one unacknowledged PCM packet; the engine applies input
backpressure. A stalled engine reconnects with bounded backoff while native playback continues.
This prioritizes uninterrupted voice. Video can lag under GPU load; end-to-end lip/audio alignment
after this separation has not yet been accepted or measured acoustically.

Microphone constraints disable browser automatic gain control and noise suppression, retaining
echo cancellation. Fusion still decides whose audio reaches native voice. Reload the page and
rearm the microphone to apply these constraints; an existing browser capture keeps its old settings.
No OS input/output volume is changed by this update.

`trendcoffee/avatar_motion.py` selects frames. `scripts/livetalking_motion.py` uses the existing
Wav2Lip model for both talking and waving, so custom video does not preempt voice. Only model features use 16kHz. The browser speaker receives the original native 48kHz PCM directly.
`trendcoffee/avatar_composite.py` retains source eyes/forehead and blends the generated lower face
with feathered edges. The mouth interior is fully replaced, avoiding a mixture of generated and
closed source lips. This reduces whole-face blur/rectangular seams; it does not guarantee that
every synthesized mouth or tooth shape is photorealistic.
The avatar process configures VP8/H.264 at a 3Mbps starting bitrate, adapting within 1.5–6Mbps
for the local kiosk/LAN. Upstream VP8's 500kbps start visibly softened moving faces. This setting
is confined to the avatar process; it does not alter native voice's WebRTC connection.
The avatar's internal audio clock remains at 20ms; the first corresponding video frame releases
its internal utterance onset. This clock is used for rendering, not audible playback.
`trendcoffee/avatar_playout.py` rejects retired video/audio epochs at the output boundary.
Reset cancels motion, clears queued media and rejects retired epochs at inference and publish
boundaries. Browser interruption clears the native AudioWorklet immediately; physical-speaker
latency is a separate measurement.

The wrapper exposes no chat/TTS/admin/upload route, binds HTTP to loopback, and uses no public
STUN/TURN. WebRTC needs direct host-candidate connectivity; an SSH HTTP tunnel alone is insufficient.
Direct API starts without `TREND_AVATAR_URL` use direct audio and the Trend poster. The launcher
sets the local engine URL automatically.

Native voice retains silence inside an active assistant turn, preserving the playback clock.
The AudioWorklet uses a 160–200ms startup buffer to absorb native packet jitter and UI stalls.
The UI takes speaking state from native PCM consumption in the AudioWorklet, with a 750ms
presentation-only grace period across clause pauses. Fusion receives actual playback changes
immediately; the label grace period never extends microphone gating. Explicit interruption and
guest/microphone reset clear the label immediately. Idle RTP noise and avatar reconnections
cannot restart the speaking indicator.

## Legacy LiveTalking verification

```bash
.venv/bin/pytest -q tests/test_avatar.py tests/test_avatar_motion.py tests/test_kiosk_launcher.py
.venv/bin/pytest -q tests/test_prepare_trend_avatar.py
.runtime/livetalking-venv/bin/python -m unittest discover -s tests -p test_avatar_composite.py
npm --prefix frontend test
.venv/bin/pytest -q tests/test_avatar_pcm.py tests/test_avatar_playout.py
TREND_TEST_AVATAR_URL=http://127.0.0.1:8011 \
  .venv/bin/pytest -q tests/test_avatar_audio_browser.py -s
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/avatar_audio_quality.py
TREND_TEST_GESTURES=1 TREND_TEST_AVATAR_URL=http://127.0.0.1:8011 \
  .venv/bin/pytest -q tests/test_avatar_browser.py
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/avatar_smoke.py \
  --url http://127.0.0.1:8011 --wave --repeats 20
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/avatar_interrupt_smoke.py \
  --url http://127.0.0.1:8011
```

For isolated hardware testing, start another wrapper on 8011 with `--motion-config
.runtime/trend-avatar.json --checkout .runtime/LiveTalking --model wav2lip --batch_size 4
--listenport 8011`. Each engine permits one WebRTC session; avoid competing with an open kiosk.
Browser tests use isolated guest storage and simulated voice events, never merchant orders.
Artifacts: `output/avatar-browser/`, `output/avatar-smoke.json`, `output/avatar-interrupt.json`.
See `docs/evals/realtime-avatar.md` for measured results and their limits.
The neutral-source review artifact is `output/avatar-quality-review/neutral-avatar-preview.mp4`:
real local WebRTC video/audio using the prerecorded greeting, including speech, wave and smile.

### Warm appearance and excessive opening

The selected standing face and warm color are intentional. The user’s other clip is an expression reference, not permission to replace the face or recolor it. The installed `lip_opening_limit: 0.035` is forwarded as `--lip-opening-limit`; zero disables it. This soft limit acts on centered vertical speech displacement before the neural warp, leaving small articulation, lateral smile movement and the source-smile rest path intact. See [validation and current FPS limitation](../evals/avatar-opening-limit.md).
