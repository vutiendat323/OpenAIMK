# Ditto WebRTC kiosk

The kiosk launcher reads `.runtime/trend-avatar.json`. The selected engine is:

```json
{
  "engine": "ditto",
  "source": "123_Tạo_video_chân_thực_cô_48e0af4f.mp4",
  "fps": 12
}
```

Other manifest fields remain available in the saved configuration. The launcher
starts `scripts/ditto_server.py` using `.runtime/livetalking-venv/bin/python`.
Model weights are local in `.runtime/Ditto/checkpoints`; optional libraries are
isolated in `.runtime/ditto-packages`. The source and action clips are local.

From `/home/metek/Projects/OpenAIMK`:

```sh
.venv/bin/python scripts/kiosk.py start --service avatar
curl -fsS http://127.0.0.1:8010/trend/health
.venv/bin/python scripts/kiosk.py start --service visual
.venv/bin/python scripts/kiosk.py start --service api
```

Wait for avatar health `ready: true` before enabling a voice session. The process
registers source/action features and warms compiled GPU kernels before binding
port 8010. Open http://127.0.0.1:8080 and refresh the browser after switching engines.
The model stays warm between browser connections. The launcher records process
identity and stops only its recorded workspace processes.

To restart the avatar after changing its manifest or code:

```sh
.venv/bin/python scripts/kiosk.py stop --service avatar
.venv/bin/python scripts/kiosk.py start --service avatar
```

The original configuration is saved in `.runtime/trend-avatar.before-ditto.json`.
To restore it:

```sh
.venv/bin/python scripts/kiosk.py stop --service avatar
cp .runtime/trend-avatar.before-ditto.json .runtime/trend-avatar.json
.venv/bin/python scripts/kiosk.py start --service avatar
```

## Runtime behavior

WebRTC uses localhost with no public ICE servers. The existing authenticated kiosk
API forwards SDP and PCM to the avatar service. Browser audio continues through
the native `VoicePlayer`; avatar RTP audio is muted by the kiosk frontend. GPU
work runs in a separate thread; reset invalidates old frames immediately without
waiting for CUDA. Queues retain at most four seconds of model input and one
published video frame, with a 500 ms transport audio bound.

The source video supplies appearance. Five-step audio-conditioned motion operates
on rolling past features; the fixed sampling noise reduces random frame changes.
This streaming sampler differs from the earlier 50-step offline quality review.
It is not established as visually equivalent to that review. Standing uses the
provided neutral clip; wave features are precomputed and speech continues to
drive the mouth while waving. The smile action uses the source smile expression.

The PyTorch warper and image decoder are separately compiled and retain GPU
features between stages. The motion decoder's guidance function is also compiled.
The scheduling clock counts inference time toward the video period and skips
missed deadlines instead of accumulating old frames.

## Verification evidence

Staging acceptance: `output/ditto-webrtc-staging/acceptance.json` and
`received-mouth-frames.jpg`. A synthetic PCM test measured approximately 12 FPS
RTP video; 81 new talking-face renders during 8.04 seconds of speech (about
10 FPS); mean motion update 23 ms; face render 75 ms; PCM acknowledgement P95
2.18 ms; audio packet gap P95 21.44 ms; reset HTTP response 0.93 ms. These are
local synthetic measurements, not microphone word accuracy, acoustic latency or
perceptual acceptance. WebRTC video may repeat the latest generated face.

The browser test verified video visibility, native audio flow, interruption,
connection recovery and a subsequent guest. CPU tests cover epoch rejection,
queue bounds, media clock stalls and render scheduling. 25 FPS is not claimed.

Re-run the real transport acceptance (no live voice or merchant activity):

```sh
PYTHONPATH=. .runtime/livetalking-venv/bin/python scripts/ditto_acceptance.py \
  --url http://127.0.0.1:8010 --output output/ditto-webrtc-production

TREND_TEST_AVATAR_URL=http://127.0.0.1:8010 \
  .venv/bin/pytest -q tests/test_avatar_browser.py
```

Logs: `.runtime/kiosk-avatar.log`. If health reports `ready: false` or a worker
error, inspect that log; a listening port alone is not an acceptance check.

## Active deployment, 2026-10-30

The selected manifest now sets `engine: ditto`, the supplied 720p source and
`fps: 12`. The managed avatar on 8010, API on 8080 and visual worker on 9877
are running. `/api/avatar/status` reports `engine: ditto`, `model: ditto`,
`ready: true` and idle/wave/smile actions.

The production-port synthetic acceptance completed with 171 video packets/frames,
710 audio frames and 531 audible frames. RTP video was 12.00 FPS, reset HTTP
response 1.26 ms, audio packet gap P95 21.30 ms and PCM acknowledgement P95 2.62 ms.
No worker error was reported; audio/model input was cleared at reset and stale
GPU results were discarded. Exact values are saved in
`output/ditto-webrtc-production/acceptance.json`. Only the renderer performance
should be compared with the earlier 14.38 FPS microbenchmark; the actual pipeline
also spends GPU time on audio features and motion synthesis.

Production Chromium acceptance with gestures enabled passed in 34.72 seconds.
The transport, scheduling, launcher and avatar route checks passed (25 CPU tests).
Changed Python files pass Ruff. Browser evidence is under `output/avatar-browser`.

Self-evaluation: accuracy 4/5 (real local measurements; no acoustic measurement),
completeness 4/5 (WebRTC deployed and actions/recovery verified; visual naturalness
still needs user judgment), clarity 4/5 (render and RTP rates distinguished),
actionability 4/5 (running services, restart and rollback commands), conciseness
4/5 (detailed evidence kept here). Average 4.0/5. No claim is made that the
five-step streaming mouth matches the earlier fifty-step quality review.
