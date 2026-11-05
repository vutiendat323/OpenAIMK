# Remote laptop/phone camera selection — 2026-10-21

## Problem and behavior

The user opens the kiosk on a home laptop through SSH local forwarding. Camera
telemetry refers to the server C920. Previously healthy local telemetry prevented
browser video capture, and Visual rejected remote frames while local frames were fresh.

Choose **Camera thiết bị này** before **Bật micro** to request device camera and
microphone together. The preference travels through authenticated kiosk attachment
and the owned Visual stream. Default **Camera tại kiosk** retains C920 priority.
The selected device stream can override local priority after steady frames arrive;
lost frames/disconnection fall back to C920. Camera choice is fixed while armed;
turning off the microphone ends the controller session, so change source before ordering.

Use SSH forwarding such as:

    ssh -N -L 8080:127.0.0.1:8080 user@server

Then open http://127.0.0.1:8080 on the laptop. Source selection concerns the
device running that browser; the SSH tunnel itself does not forward camera hardware.

## Reproduction and regression evidence

- Executing the old syncCamera(true) path requested browser video zero times.
- Actual local-priority CameraRouter rejected an explicitly selected remote frame.
- New socket/Visual/browser regressions failed before implementation and passed afterward.
- Review caught combined-stream teardown on video loss. An ended video track now leaves
  microphone/controller alive; only audio-track loss triggers full teardown.
- A second browser regression reproduced frozen JPEG transmission after camera loss:
  packet count grew 10 to 14 in 250 ms with live audio. Live/unmuted video checks
  before capture and JPEG completion stop transmission, allowing stale-frame fallback.
- Independent review confirmed both findings resolved with no remaining material findings.

## Final validation

- Root pytest: **212 passed in 52.42 seconds** on the final source/build.
- Visual router/remote-video suites: **29 passed**; frontend Vitest: **20 passed**.
- Production TypeScript/Vite build, Ruff lint/format, oxlint and Prettier passed.
- Built-browser smoke passed at **1440/768/375 px**, zero browser errors and axe violations;
  shared cart, guest isolation and reconnect-after-server-restart remained covered.
- Actual camera/microphone quality on the home laptop or phone remains unverified.
  Tests used fake capture, isolated databases and merchant/native fixtures.
  No real merchant order, payment or printer job was issued.

## Deployment

API 8080 and Visual 9877 were stopped before this task's deployment. Started both
with the owned-process launcher after verification: API pid 114439, Visual pid 114400.
Both ports listened; /health returned ok and the served JavaScript included the new
camera selector/protocol. A passive Visual read reported local_camera_available=true.
No camera-selection command or customer business action was sent by the live check.
Recheck runtime rather than treating this deployment observation as permanent status.

## Self-evaluation

Overall **4.6/5**.

| Axis | Score | Evidence / limit |
|---|---|---|
| Accuracy | 4 | Source, real-browser regressions and live served bundle verified; physical remote capture unverified |
| Completeness | 4 | Source selection, ownership, fallback and camera loss covered; the user must grant/test their physical device |
| Clarity | 5 | UI names, server-local meaning and SSH steps are explicit |
| Actionability | 5 | Built frontend and both services running at deployment check |
| Conciseness | 5 | One source selector; existing media/socket/router lifecycle reused |

Next improvement: verify camera/microphone and Fusion with the user's actual home
laptop after browser permission. Self-check: this assessment should match the user's
experience because fixture success and unverified physical capture are stated separately.
