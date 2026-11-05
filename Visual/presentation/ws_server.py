"""WebSocket server thread — reads SharedState at 5 Hz, pushes JSON events.

Every client gets the 3-event presence stream the kiosk agent consumes.  A
client that sends {"cmd": "monitor"} also gets the console stream: telemetry
JSON plus the camera frame as a binary JPEG, and may send {"cmd": "set"}
for the live-tunable config keys.  Plain HTTP GET / on the same port serves
the console (console/: index.html plus its css, js and any other assets).

One voice session may stream its audio for active-speaker detection
(asd_audio_start / asd_audio / asd_audio_stop).  Protocol v2 also lets that
socket pin ASD to one track (asd_track) and pushes each ASD result to it as
soon as it is published (event "asd").  The stream belongs to the
socket that started it; packets are validated and copied into AVBuffer here,
and the model runs in its own worker, never in this handler.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import mimetypes
import os
import struct
import threading
import time
import uuid
from urllib.parse import unquote

import cv2
import numpy as np
from jinja2 import Environment, FileSystemLoader, select_autoescape

from Visual.domain.active_speaker import BIN_STEP_SECS
from Visual.presentation.console_settings import save_live_values

_log = logging.getLogger(__name__)

_CONSOLE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "console"))
_TEMPLATES = Environment(loader=FileSystemLoader(_CONSOLE_DIR),
                         autoescape=select_autoescape(("html",)), auto_reload=True)
MONITOR_RATE = 1 / 15   # seconds; matches the track loop cap
FACES_RATE = 0.1     # s; per-face mouth activity for voice clients (10 Hz)
JPEG_QUALITY = 75
MAX_COMMAND_CHARS = 8192   # an 80 ms asd_audio packet is ~3.5 KB of JSON
ASD_PACKET_BYTES = 2560    # 1280 int16 samples: 80 ms at 16 kHz mono
ASD_PROTOCOL_VERSIONS = (1, 2)  # 2 adds asd_track pins and pushed asd events
# Remote WebRTC video: binary messages of an 8-byte little-endian float64
# capture time followed by one JPEG.  A 640x480 JPEG is ~40-80 KB.
VIDEO_HEADER = struct.Struct("<d")
MAX_VIDEO_FRAME_BYTES = 2 * 1024 * 1024

# Config keys the running pipeline re-reads every frame, so a write from the
# console takes effect immediately.  (lo, hi) is enforced here: this writes
# into a live pipeline.
LIVE_KEYS = {
    "face_ipd_m": (0.040, 0.090),
    "distance_threshold": (0.10, 6.0),
    "asd_audio_offset_secs": (-1.0, 1.0),
}

# ---------------------------------------------------------------------------
# Event builder (pure logic — easy to test without a running server)
# ---------------------------------------------------------------------------

class VisionWSServer:
    """Reads SharedState at 5 Hz and pushes presence events to WS clients."""

    PUSH_RATE = 0.2  # seconds (5 Hz)

    def __init__(self, state, host: str = "0.0.0.0", port: int = 9876, cfg=None,
                 config_path: str | None = None, router=None):
        self._state = state
        self._host = host
        self._port = port
        self._cfg = cfg
        self._config_path = config_path
        self._clients: set = set()
        self._monitors: set = set()
        self._faces_clients: set = set()
        self._asd_owner = None       # the socket whose audio stream is current
        self._asd_stream: str | None = None
        self._asd_version: int | None = None
        self._asd_sent_t0: float | None = None
        self._asd_published: asyncio.Event | None = None
        self._rate_mark = (time.perf_counter(), 0)
        self._camera_fps = 0.0
        self._voice_owner = None
        self._voice_stream = None
        self._voice_session = None
        self._voice_data = None
        self._voice_received_at = 0.0
        self._voice_pending = {}
        # Remote camera: the CameraRouter, and the one socket whose frames it takes.
        self._router = router
        self._video_owner = None
        self._video_stream: str | None = None
        self._video_selected_at: float | None = None

    # -- event building (pure, testable) ------------------------------------

    def _build_event(self) -> dict:
        """The presence event, as the Scene classifies it (see SceneSnapshot.event)."""
        scene = self._state.scene.snapshot()
        event = scene.event(time.time())
        event.update(frame_seq=scene.face_frame_seq, captured_at=scene.face_captured_at)
        if self._video_selected_at is not None and (
                scene.face_captured_at is None or scene.face_captured_at < self._video_selected_at):
            event.update(event="no_person", frame_seq=-1, captured_at=None)
        if self._router is not None:
            event["local_camera_available"] = self._router.local_available
        return event

    def _connect_event(self) -> dict:
        """Synthetic event sent when a client connects (always no_person)."""
        return {"event": "no_person", "ts": time.time()}

    # -- console stream (pure, testable) -------------------------------------

    def _info_event(self) -> dict:
        """Sent once when a console subscribes: camera and tunable values."""
        c = self._cfg
        return {
            "event": "info",
            "camera": f"Camera {c.camera_id} ({c.camera_width} x {c.camera_height})" if c else "Camera",
            "live": {k: getattr(c, k) for k in LIVE_KEYS if hasattr(c, k)} if c else {},
            "bounds": {k: list(v) for k, v in LIVE_KEYS.items()},
            "can_save": self._config_path is not None,
        }

    def _faces_event(self) -> dict:
        """Every tracked face with its mouth activity, for the voice speaker gate."""
        width = float(getattr(self._cfg, "camera_width", 640) or 640)
        now = time.time()
        # Only a result still within 1 s of its window's end; it keeps its own
        # audio t0 however many faces events carry it.
        result = self._state.asd.latest_result(now)
        tracks = []
        scene = self._state.scene.snapshot()
        if self._video_selected_at is not None and (
                scene.face_captured_at is None or scene.face_captured_at < self._video_selected_at):
            return {"event": "faces", "ts": now, "tracks": [],
                    "frame_seq": -1, "captured_at": None}
        pad_fresh = scene.spoof_captured_at is not None and 0 <= now - scene.spoof_captured_at <= 1.5
        for p in scene.people:
            x1, _, x2, _ = p.box
            asd, prob = None, None
            if result is not None and result.track_id == p.id:
                probs = [float(v) for v in result.probabilities]
                asd = {"stream_id": result.stream_id, "t0": result.audio_t0,
                       "frame_secs": BIN_STEP_SECS, "probabilities": probs}
                prob = (probs[-1] + probs[-2]) / 2
            tracks.append({
                "track_id": p.id,
                "is_live": p.spoof_flag is False and pad_fresh,
                "distance_m": round(p.dist, 2) if p.dist > 0 else None,
                "facing": p.dist > 0,
                "cx_norm": (x1 + x2) / 2 / width,
                "mouth_activity": None if p.mouth is None else round(p.mouth, 3),
                "active_speaker_probability": prob,
                "asd": asd,
            })
        return {"event": "faces", "ts": now, "tracks": tracks,
                "frame_seq": scene.face_frame_seq, "captured_at": scene.face_captured_at}

    def _monitor_event(self) -> dict:
        """One telemetry frame for the console: rates, timings, the scene."""
        scene = self._state.scene.snapshot()
        now = time.perf_counter()
        t0, f0 = self._rate_mark
        frame_seq = self._state.frame_seq
        if now - t0 >= 0.5:
            self._camera_fps = round((frame_seq - f0) / (now - t0), 1)
            self._rate_mark = (now, frame_seq)

        r = lambda v, n=3: None if v is None else round(float(v), n)
        rows = [{
            "id": p.id,
            "box": [round(v, 1) for v in p.box],
            "dist": round(p.dist, 3),
            "raw": r(p.raw),
            "kps": None if p.kps is None else [[round(x, 1), round(y, 1)] for x, y in p.kps],
            "gate": p.gate,
            "spoof": r(p.spoof),
            "spoof_flag": p.spoof_flag,
            "body_m": r(p.body_m),
            "mouth_activity": r(p.mouth),
        } for p in scene.people]
        timings = self._state.timings()
        return {
            "event": "monitor",
            "ts": time.time(),
            "fps": self._camera_fps,
            "timing_ms": {"track": round(timings["track"], 1),
                          "spoof": round(timings["spoof"], 1)},
            "threshold": self._cfg.distance_threshold if self._cfg else 1.0,
            "live": {k: getattr(self._cfg, k) for k in LIVE_KEYS
                     if hasattr(self._cfg, k)},
            "nearest_id": None if scene.nearest is None else scene.nearest.id,
            "tracks": rows,
            "bodies": [{"box": [round(float(v), 1) for v in b["box"]],
                        "dist": round(b["dist"], 3)} for b in scene.bodies],
            "voice": self._voice_event(),
            "asd": self._console_asd(),
        }

    def _voice_event(self) -> dict:
        age = time.monotonic() - self._voice_received_at
        status = "idle" if self._voice_owner is None else "live" if (
            self._voice_data is not None and age <= 1.5) else "stale"
        return {"status": status, "session_id": self._voice_session,
                "data": self._voice_data if status == "live" else None}

    def _console_asd(self) -> dict:
        result = self._state.asd.latest_result(time.time())
        return {"status": self._state.asd_status,
                "track_id": result.track_id if result is not None else None,
                "probability": float(np.mean(result.probabilities[-2:]))
                if result is not None else None,
                "pinned_track": self._state.asd.pinned_track,
                "active": self._state.asd.active}

    def _start_voice_monitor(self, websocket, data) -> dict:
        stream, session = data.get("stream_id"), data.get("session_id")
        reply = {"event": "voice_monitor_status", "stream_id": stream,
                 "status": "invalid"}
        if not all(isinstance(v, str) and 0 < len(v) <= 128 for v in (stream, session)):
            return reply
        if self._voice_owner is not None and self._voice_owner is not websocket:
            return {**reply, "status": "busy"}
        if stream != self._voice_stream:
            self._release_voice_monitor(websocket)
            self._voice_data = None
        self._voice_owner, self._voice_stream = websocket, stream
        self._voice_session = session
        return {**reply, "status": "ready"}

    def _voice_telemetry(self, websocket, data) -> None:
        if (websocket is not self._voice_owner
                or data.get("stream_id") != self._voice_stream):
            return
        snapshot = data.get("data")
        if not isinstance(snapshot, dict):
            return
        # Reject non-finite JSON before it can poison the monitor stream.
        try:
            json.dumps(snapshot, allow_nan=False)
        except (TypeError, ValueError):
            return
        self._voice_data = snapshot
        self._voice_received_at = time.monotonic()

    def _release_voice_monitor(self, websocket) -> None:
        if websocket is not self._voice_owner:
            return
        self._voice_owner = self._voice_stream = self._voice_session = None
        self._voice_data = None
        for future in list(self._voice_pending.values()):
            if not future.done():
                future.set_result({"ok": False, "error": "Voice session disconnected"})

    async def _voice_command(self, action: str, **values) -> dict:
        if self._voice_owner is None:
            return {"ok": False, "error": "Start a kiosk voice session first"}
        if len(self._voice_pending) >= 32:
            return {"ok": False, "error": "Too many pending voice commands"}
        request_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._voice_pending[request_id] = future
        try:
            await self._voice_owner.send(json.dumps({
                "event": "voice_command", "stream_id": self._voice_stream,
                "request_id": request_id, "action": action, **values,
            }))
            return await asyncio.wait_for(future, timeout=5.0)
        except (TimeoutError, OSError):
            return {"ok": False, "error": "Voice command timed out or disconnected"}
        except Exception:
            _log.exception("console voice command failed")
            return {"ok": False, "error": "Voice connection failed"}
        finally:
            self._voice_pending.pop(request_id, None)

    def _voice_command_result(self, websocket, data) -> None:
        if (websocket is not self._voice_owner
                or data.get("stream_id") != self._voice_stream):
            return
        request_id = data.get("request_id")
        if not isinstance(request_id, str):
            return
        future = self._voice_pending.get(request_id)
        if future is not None and not future.done():
            future.set_result({"ok": data.get("ok") is True,
                               "key": data.get("key"), "value": data.get("value"),
                               "error": str(data.get("error", ""))[:200]})

    async def _save_settings(self) -> dict:
        values = {k: getattr(self._cfg, k) for k in LIVE_KEYS if hasattr(self._cfg, k)}
        try:
            await asyncio.to_thread(save_live_values, self._config_path, values)
            vision = {"ok": True}
        except (OSError, ValueError) as exc:
            vision = {"ok": False, "error": str(exc)}
        voice = await self._voice_command("save") if self._voice_owner else {
            "ok": True, "skipped": True}
        return {"event": "save_result", "ok": vision["ok"] and voice["ok"],
                "vision": vision, "voice": voice}

    def _apply_set(self, data: dict) -> dict:
        """Validate and apply one live config write from the console."""
        key = data.get("key")
        bounds = LIVE_KEYS.get(key)
        if bounds is None or self._cfg is None or not hasattr(self._cfg, key):
            return {"event": "set_result", "ok": False, "key": key, "error": "not settable"}
        try:
            if isinstance(data.get("value"), bool):
                raise ValueError("not a number")
            value = float(data.get("value"))
        except (TypeError, ValueError):
            return {"event": "set_result", "ok": False, "key": key, "error": "not a number"}
        lo, hi = bounds
        if math.isnan(value) or not lo <= value <= hi:
            return {"event": "set_result", "ok": False, "key": key, "error": f"outside {lo}-{hi}"}
        # Config is a frozen dataclass; save_correction() writes the same way.
        object.__setattr__(self._cfg, key, value)
        _log.info("[ws] console set %s = %s", key, value)
        return {"event": "set_result", "ok": True, "key": key, "value": value}

    def _frame_jpeg(self) -> bytes | None:
        frame = self._state.get_latest_frame()
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        return buf.tobytes() if ok else None

    # -- WebSocket handler --------------------------------------------------

    async def _handler(self, websocket):
        """One handler per connected client."""
        self._clients.add(websocket)
        try:
            await websocket.send(json.dumps(self._connect_event()))
            async for raw in websocket:
                await self._on_message(websocket, raw)
        finally:
            self._clients.discard(websocket)
            self._monitors.discard(websocket)
            self._faces_clients.discard(websocket)
            self._release_asd(websocket)
            self._release_voice_monitor(websocket)
            self._release_video(websocket)

    async def _on_message(self, websocket, raw) -> None:
        """Presence clients never send anything; the console sends commands."""
        if isinstance(raw, (bytes, bytearray)):  # only remote video is binary
            self._video_frame(websocket, raw)
            return
        if len(raw) > MAX_COMMAND_CHARS:  # bounded before parsing
            return
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return
        cmd = data.get("cmd") if isinstance(data, dict) else None
        if cmd == "monitor":
            self._monitors.add(websocket)
            await websocket.send(json.dumps(self._info_event()))
        elif cmd == "faces":
            self._faces_clients.add(websocket)
        elif cmd == "set":
            if websocket in self._monitors:
                await websocket.send(json.dumps(self._apply_set(data)))
        elif cmd == "save_settings" and websocket in self._monitors:
            await websocket.send(json.dumps(await self._save_settings()))
        elif cmd == "voice_set" and websocket in self._monitors:
            result = await self._voice_command("set", key=data.get("key"), value=data.get("value"))
            result["key"] = data.get("key")
            await websocket.send(json.dumps({"event": "voice_set_result",
                                             "key": data.get("key"), **result}))
        elif cmd == "voice_monitor_start":
            await websocket.send(json.dumps(self._start_voice_monitor(websocket, data)))
        elif cmd == "voice_telemetry":
            self._voice_telemetry(websocket, data)
        elif cmd == "voice_command_result":
            self._voice_command_result(websocket, data)
        elif cmd == "asd_audio_start":
            await websocket.send(json.dumps(self._asd_start(websocket, data)))
        elif cmd == "asd_audio":
            self._asd_audio(websocket, data)
        elif cmd == "asd_track":
            await websocket.send(json.dumps(self._asd_track(websocket, data)))
        elif cmd == "asd_audio_stop":
            if data.get("stream_id") == self._asd_stream:
                self._release_asd(websocket)
        elif cmd == "video_start":
            await websocket.send(json.dumps(self._video_start(websocket, data)))
        elif cmd == "video_stop":
            if websocket is self._video_owner and data.get("stream_id") == self._video_stream:
                self._release_video(websocket)

    # -- remote WebRTC camera -------------------------------------------------

    def _video_start(self, websocket, data: dict) -> dict:
        """A voice session explicitly selects its own camera over the C920."""
        stream_id = data.get("stream_id")
        reply = lambda status: {"event": "video_status", "status": status,
                                "stream_id": stream_id if isinstance(stream_id, str) else None}
        if not all(isinstance(data.get(k), str) and data.get(k)
                   for k in ("session_id", "stream_id")):
            return reply("invalid")
        if self._router is None:
            return reply("unavailable")
        if self._video_owner is not None and self._video_owner is not websocket:
            return reply("busy")
        prefer_remote = data.get("prefer_remote", False)
        if type(prefer_remote) is not bool:
            return reply("invalid")
        camera_source = data.get("camera_source")
        if camera_source not in (None, "local", "device"):
            return reply("invalid")
        self._video_owner, self._video_stream = websocket, stream_id
        self._video_selected_at = time.time() if camera_source is not None else None
        self._router.select_remote(stream_id, prefer_remote=prefer_remote,
                                   camera_source=camera_source)
        return reply("ready")

    def _video_frame(self, websocket, raw: bytes) -> None:
        """Decode one owner frame and hand it to the router; drop anything else."""
        if (websocket is not self._video_owner or self._router is None
                or not VIDEO_HEADER.size < len(raw) <= MAX_VIDEO_FRAME_BYTES):
            return
        (ts,) = VIDEO_HEADER.unpack_from(raw)
        if not math.isfinite(ts):
            return
        frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8, offset=VIDEO_HEADER.size),
                             cv2.IMREAD_COLOR)
        if frame is None:
            return
        self._router.remote_frame(self._video_stream, frame, ts)

    def _release_video(self, websocket) -> None:
        """The owner left or stopped: the C920 takes over on its next frame."""
        if websocket is self._video_owner:
            self._router.release_remote(self._video_stream)
            self._video_owner, self._video_stream = None, None
            self._video_selected_at = None

    # -- active-speaker audio (spec 6.1) -------------------------------------

    def _asd_start(self, websocket, data: dict) -> dict:
        stream_id = data.get("stream_id")
        reply = lambda status: {"event": "asd_audio_status", "status": status,
                                "stream_id": stream_id if isinstance(stream_id, str) else None}
        version = data.get("version")
        exact = (("sample_rate", 16000), ("channels", 1))
        if not (type(version) is int and version in ASD_PROTOCOL_VERSIONS
                and all(type(data.get(k)) is int and data.get(k) == v for k, v in exact)
                and all(isinstance(data.get(k), str) and data.get(k)
                        for k in ("session_id", "stream_id"))):
            return reply("invalid")
        if self._state.asd_status != "ready":
            return reply(self._state.asd_status)
        if self._asd_owner is not None and self._asd_owner is not websocket:
            return reply("busy")
        self._asd_owner, self._asd_stream = websocket, stream_id
        self._asd_version, self._asd_sent_t0 = version, None
        self._state.asd.start_stream(stream_id)
        return reply("ready")

    def _asd_audio(self, websocket, data: dict) -> None:
        """Validate one 80 ms packet and hand AVBuffer its own copy of the samples."""
        if websocket is not self._asd_owner or data.get("stream_id") != self._asd_stream:
            return
        seq, t0, b64 = data.get("seq"), data.get("t0"), data.get("pcm16_b64")
        if (type(seq) is not int or seq < 0 or type(t0) not in (int, float)
                or not math.isfinite(t0) or not isinstance(b64, str)):
            return
        try:
            pcm = base64.b64decode(b64, validate=True)
        except ValueError:  # binascii.Error, or non-ASCII text
            return
        if len(pcm) != ASD_PACKET_BYTES:
            return
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.int16)  # a copy
        self._state.asd.push_audio(self._asd_stream, seq, float(t0), samples)

    def _asd_track(self, websocket, data: dict) -> dict:
        """Pin ASD to the backend's locked customer (v2 owner only); null unpins."""
        stream_id, track_id = data.get("stream_id"), data.get("track_id")
        valid_id = track_id is None or (type(track_id) is int and track_id >= 0)
        reply = lambda status: {"event": "asd_track_status",
                                "stream_id": stream_id if isinstance(stream_id, str) else None,
                                "track_id": track_id if type(track_id) is int else None,
                                "status": status}
        if (websocket is not self._asd_owner or self._asd_version != 2
                or stream_id != self._asd_stream or not valid_id):
            return reply("invalid")
        self._state.asd.pin_track(track_id)
        return reply("cleared" if track_id is None else "pinned")

    def _asd_event(self) -> dict | None:
        """The newest ASD result for the v2 owner, once per window."""
        if self._asd_owner is None or self._asd_version != 2:
            return None
        result = self._state.asd.latest_result(time.time())
        if (result is None or result.stream_id != self._asd_stream
                or result.audio_t0 == self._asd_sent_t0):
            return None
        self._asd_sent_t0 = result.audio_t0
        return {"event": "asd", "stream_id": result.stream_id, "track_id": result.track_id,
                "t0": result.audio_t0, "frame_secs": BIN_STEP_SECS,
                "probabilities": [float(v) for v in result.probabilities]}

    def _publish_listener(self, loop):
        """Runs on the ASD worker thread: wake the push loop on the WS loop."""
        def listener(_result) -> None:
            loop.call_soon_threadsafe(self._asd_published.set)
        return listener

    async def _asd_push_loop(self):
        """Send each published ASD window to the v2 owner as soon as it lands.

        Coalescing, never a queue: publishes that land during a send leave one
        wake-up, and only the newest result goes out.
        """
        while True:
            await self._asd_published.wait()
            self._asd_published.clear()
            # One bad result must not end every later push (CancelledError is
            # a BaseException and still stops the loop).
            try:
                owner, event = self._asd_owner, self._asd_event()
                if owner is None or event is None:
                    continue
                payload = json.dumps(event)
            except Exception:
                _log.exception("WS asd event error")
                continue
            try:
                await owner.send(payload)
            except Exception as e:
                _log.debug("WS asd send error: %s", e)

    def _release_asd(self, websocket) -> None:
        """Stop and clear *websocket*'s own stream; anyone else's is untouched."""
        if websocket is self._asd_owner:
            self._state.asd.stop_stream(self._asd_stream)
            self._asd_owner, self._asd_stream, self._asd_version = None, None, None

    def _process_request(self, connection, request):
        """Serve the console folder on plain HTTP GET; let upgrades through.

        ``/`` and ``/console`` are its index.html; any other path is a file
        inside the folder (css, js, images), typed by its extension.  A path
        that resolves outside the folder is a 404.
        """
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return None
        path = request.path.split("?", 1)[0]
        is_index = path in ("/", "/console", "/console/", "/index.html")
        name = "index.html" if is_index else unquote(path).lstrip("/")
        if not is_index and name.split("/", 1)[0] not in ("css", "js", "img"):
            return connection.respond(404, "Not found\n")
        file = os.path.realpath(os.path.join(_CONSOLE_DIR, name))
        if not file.startswith(_CONSOLE_DIR + os.sep) or not os.path.isfile(file):
            return connection.respond(404, "Not found\n")
        if is_index:
            body = _TEMPLATES.get_template("templates/dashboard.html").render().encode("utf-8")
        else:
            with open(file, "rb") as f:
                body = f.read()
        ctype = mimetypes.guess_type(file)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        response = connection.respond(200, "")
        response.body = body
        for key, value in (("Content-Type", ctype), ("Content-Length", str(len(body))),
                           ("Cache-Control", "no-store")):
            if key in response.headers:
                del response.headers[key]
            response.headers[key] = value
        return response

    async def _push_loop(self):
        """Read SharedState at 5 Hz, broadcast to all connected clients."""
        while True:
            await asyncio.sleep(self.PUSH_RATE)
            event = self._build_event()
            if not self._clients:
                continue
            payload = json.dumps(event)
            results = await asyncio.gather(
                *(client.send(payload) for client in self._clients),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    _log.debug("WS send error: %s", r)

    async def _monitor_loop(self):
        """Push telemetry + the camera frame to subscribed consoles."""
        while True:
            await asyncio.sleep(MONITOR_RATE)
            if not self._monitors:
                continue
            payload = json.dumps(self._monitor_event())
            frame = self._frame_jpeg()
            for client in list(self._monitors):
                try:
                    await client.send(payload)
                    if frame is not None:
                        await client.send(frame)
                except Exception as e:
                    _log.debug("WS console send error: %s", e)
                    self._monitors.discard(client)

    async def _faces_loop(self):
        """Per-face mouth activity at 10 Hz for subscribed voice clients."""
        while True:
            await asyncio.sleep(FACES_RATE)
            if not self._faces_clients:
                continue
            payload = json.dumps(self._faces_event())
            for client in list(self._faces_clients):
                try:
                    await client.send(payload)
                except Exception as e:
                    _log.debug("WS faces send error: %s", e)
                    self._faces_clients.discard(client)

    # -- thread entry point -------------------------------------------------

    def _run_loop(self):
        """Run the asyncio event loop (called from daemon thread)."""
        asyncio.run(self._serve())

    async def _serve(self):
        """Start the WebSocket server and push loop."""
        import websockets

        async with websockets.serve(self._handler, self._host, self._port,
                                    process_request=self._process_request):
            _log.info("VisionWSServer listening on ws://%s:%s", self._host, self._port)
            asyncio.create_task(self._push_loop())
            asyncio.create_task(self._monitor_loop())
            asyncio.create_task(self._faces_loop())
            self._asd_published = asyncio.Event()
            self._state.asd.set_publish_listener(
                self._publish_listener(asyncio.get_running_loop()))
            asyncio.create_task(self._asd_push_loop())
            await asyncio.Future()  # run forever

    def start(self):
        """Launch the server in a daemon thread."""
        t = threading.Thread(target=self._run_loop, daemon=True, name="ws-server")
        t.start()
        _log.info("VisionWSServer thread started")
