# Selected camera and guest departure — 2026-10-28

User-reported failures: kiosk/device feeds alternated despite selecting a camera; manually started guests did not end when they left.

## Changes

- Kiosk registration now sends the explicit `camera_source` to Visual. CameraRouter pins that source for the controller's stream. Device frame gaps do not admit kiosk frames, and local selection rejects remote frames. Legacy callers without this field retain their previous fallback behavior.
- Explicit source selection clears the prior frame/scene. Presence and faces results captured before source selection are withheld, including late worker results. A rejected video registration is retried without consuming another controller's perception stream.
- Browser camera capture follows the selected source. Losing the kiosk camera reports an error rather than silently opening the device camera. Server camera forwarding rejects device frames while local is selected.
- Departure and stale-camera leave signals apply to manually started guests too. The explicit start can bind the first fresh nearby owner immediately; it also overrides the auto-restart block for that same owner. Fresh empty-camera observations end an unbound manual guest after the existing three-second departure window.
- Ending revokes active voice/state and cancels pending connection tasks, starts native teardown before waiting for Fusion/UI notification, clears the host token/cart/quote/fulfillment/table/note, and creates no prepared idle call. Persisted orders/session history are retained.

## Verification

- Root suite: **300 passed in 119.15s** (`output/camera-departure-full.txt`). Covers manual/automatic departure, missing camera updates, bystanders, guest departure during native connection, stale tools and clearing guest state.
- Focused Visual: **39 passed** (`output/camera-router-tests.txt`), including sparse/interrupted selected-source frames, source release and late perception results.
- Browser subset: **11 passed** (`output/camera-departure-browser.txt`), including local/device selection, no implicit local-to-device fallback, selected voice and idle/active transitions. These are also in the root suite.
- Frontend TypeScript/Vite build, oxlint and changed backend lint/format passed.
- Broad Visual run was not all green: its import sweep recursively includes the local `.venv`, so that run was interrupted; excluding that sweep yielded 407 passed and 13 environment failures (Python 3.12 lacks `typing.get_protocol_members`; pytest-asyncio is absent). Logs: `output/camera-visual-full.txt`, `output/camera-visual-tests.txt`. No unrelated environment/test framework changes were made.
- No real merchant order, payment, printer action, native quota probe or physical customer departure test was performed.

## Runtime

The initial restart was deferred because a customer session was active. The user then explicitly authorized interrupting that test session and applying the fix. Both owned services were restarted; Visual PID 622507 and API PID 622268 were listening at final check. The API reported session_active=false, voice_ready=false and voice_prepared=false. The browser needs a reload for new camera capture logic. Physical two-camera switching/departure remains field verification.


## Self-evaluation

Accuracy 4/5: protocol/source routing and lifecycle tests pass; physical camera behavior is not directly measured. Completeness 4/5: both user-reported issues and runtime activation addressed; no fresh frame means departure cannot be inferred until an owner or valid absence is observed, with existing idle timeout as fallback. Clarity 4/5: camera selection and failure behavior documented; legacy callers retain a distinct fallback mode. Actionability 4/5: new services are running, browser reload remains necessary. Conciseness 4/5: shared router gains one optional source field and existing lifecycle is reused. Overall 4.0/5.
