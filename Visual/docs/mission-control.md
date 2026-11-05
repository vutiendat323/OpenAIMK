# Kiosk Mission Control

The console at `http://localhost:9876/` combines the existing camera,
tracking and proximity stream with observations from the OpenJarvis voice
pipeline. No browser microphone permission is needed: the console observes
the microphone already connected to the kiosk voice session.

## Operator workflow

- Use **VI / EN** in the header to switch the interface language immediately.
  The selection is saved in this browser; it does not change backend settings.
- Start a voice session on the kiosk to see waveform, dBFS, effective RNNoise
  status, the speaker gate's actual verdict, customer lock and voiceprint.
- Light-ASD shows synchronized speech probability for a face. A missing
  measurement is shown as unavailable, rather than zero confidence.
- Open **Live tuning** to change Vision geometry and audio/video offset, or
  the active session's ASD, mouth activity and voiceprint thresholds.
- **Kiosk activation distance** changes the backend's proximity evaluator.
  **Proximity alert threshold** changes the Vision console's distance alert.
- Controls wait for server confirmation. Invalid threshold pairs are rejected
  and the slider returns to its confirmed value.
- **Save settings** writes Vision's active YAML and OpenJarvis's active TOML
  preset. Each file is replaced atomically; the operation across both services
  is not a transaction. Partial failures are reported separately. With no
  active voice session, only Vision settings are saved.

The saved kiosk threshold is stored at `[kiosk].approach_threshold_m` in the
OpenJarvis preset. An explicit `KIOSK_APPROACH_THRESHOLD_M` environment value
still has priority on restart. Other thresholds stay in `[voice.speaker]`.
Live voice changes apply to the current session; use Save before starting a
new one to retain them.

The verdict lamp becomes standby when voice data is more than 1.5 seconds
old or its owning connection disappears. Silence is listening, not REJECT.
ASD, waveform and camera health alone do not establish voice quality; run
the operator's S1–S7 trials for that.

## Source layout

`presentation/console/templates/dashboard.html` composes `base.html`,
`camera.html`, `audio.html`, `status.html` and `drawer.html`. `knob.html`
provides the reusable slider markup. Vision renders these with Jinja2.

`console/js/console.js` owns camera rendering and the WebSocket connection;
`console/js/mission.js` owns audio, decision status, freshness and controls.
The root `console/index.html` is a generated compatibility snapshot so an
older server process can still serve the page during a source update.
After editing templates, refresh that snapshot with:

```bash
PYTHONDONTWRITEBYTECODE=1 Visual/.venv/bin/python - <<'PY'
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

root = Path("Visual/presentation/console")
env = Environment(loader=FileSystemLoader(root), autoescape=select_autoescape(("html",)))
page = env.get_template("templates/dashboard.html").render()
page = "\n".join(line.rstrip() for line in page.splitlines())
(root / "index.html").write_text(
    "<!-- Generated compatibility page. Source: templates/dashboard.html. -->\n"
    + page + "\n"
)
PY
```

## Connection contract

The existing `VisionAudioBridge` registers `voice_monitor_start` on its own
session socket. `voice_telemetry` carries one bounded observation at up to
10 Hz, including a reduced waveform; it is coalesced and sent after ASD
audio packets. There is no additional model inference or disk I/O on the
audio path. This monitoring channel also works when Light-ASD is disabled.

Only that stream's owner can publish observations or acknowledge controls.
Console sockets subscribe with `monitor`; `voice_set` forwards a validated
change to the backend with a request ID. The console receives a success only
after the gate applies it. Save runs disk writes outside the realtime path.
Pending commands are bounded, time out and fail when the owner disconnects.

Both Vision and OpenJarvis processes need to load the new Python code to
activate telemetry and controls. Existing presence and ASD v1/v2 streams
retain their contracts. Vision requires `Jinja2>=3.1,<4`.
