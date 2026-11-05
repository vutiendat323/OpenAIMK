# Remote camera without a local capture device

## Failure and fix

Vision exited with `RuntimeError: Cannot open any camera (tried: 0)` when the C920 was absent. The backend accepted browser SDP but VisionVideoBridge then failed to connect to port 9876. Mission Control consequently showed Disconnected even with a browser peer connected.

`main.py` now keeps the service and workers running after a local open or read failure, retries capture every 2 seconds, and releases failed capture handles. Remote frames still enter through the existing WS server and CameraRouter. The backend API, FSM and voice pipeline are unchanged.

## Evidence

- Three new regression tests in `tests/test_camera_service.py` reproduced startup failure, lack of local recovery, and service exit on local read failure before the fix; all pass afterward.
- Focused startup/router/source-reset/intrinsics/remote-WS tests: **37 passed**.
- Vision behavior suite with pytest + pytest-asyncio: **373 passed, 1 skipped**. This run excludes `tests/test_imports.py` and `tests/application/test_ports.py` for the environment issues below.
- Isolated live Vision on port 9877, pinned to a nonexistent local device: HTTP/WS stayed available; remote JPEG input selected remote and the monitor received **16 decoded frames** with the expected pixels. Test process was stopped afterward.
- Real headless browser on `http://127.0.0.1:5173/kiosk`, with Chromium synthetic camera and no query flag: clicked Remote Camera, SDP returned **200**, WebRTC video bytes were sent, and the running Vision logged `source local -> remote`. Clicking off closed the peer, cleared the toggle and logged `source remote -> local`.
- Only Vision was restarted to load the change. Backend and frontend processes were preserved. Launcher reports all three services healthy.
- `git diff --check` passed.

## Full-suite limits

The unrestricted run encountered unrelated environment failures: `tests/application/test_ports.py::test_adapter_has_every_member_of_its_port` calls Python 3.13's `typing.get_protocol_members`, absent in the Vision Python 3.12 environment. `tests/test_imports.py` recursively scans `.venv` and tries importing installed dependencies as `vision..venv...` service modules. The original unrestricted run was stopped after these failures; the behavior suite above excludes these two files. No changes were made to those tests.

Browser E2E used synthetic video, not the user's physical phone camera. The live no-local smoke used real Vision face model wiring with CPU, depth/spoof/ASD disabled; audiovisual identity accuracy was not assessed by these video transport checks.

## Self-evaluation

Accuracy 4/5: runtime logs, live frame pixels, browser RTP and tests support the fix; physical phone not exercised. Completeness 4/5: startup, local disconnect/recovery and remote button on/off covered; full suite has the documented environment failures. Clarity 4/5: report ties symptom to camera-dependent process exit, with evidence. Actionability 4/5: fix loaded in running Vision; no URL flag needed. Conciseness 4/5: single runtime file changed, with focused regressions. Overall **4.0/5**; next verification is the user's physical remote device. This assessment distinguishes media transport success from ASD/Fusion accuracy.
