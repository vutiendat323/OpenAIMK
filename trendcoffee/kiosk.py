"""One physical kiosk, one guest authority, native Codex voice and scoped tools."""

import asyncio
import base64
import contextlib
import json
import logging
import math
import secrets
import struct
import time
import wave
from array import array
from collections import OrderedDict, deque
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

from .camera_rtc import CameraPeer
from .claim_guard import (
    PAID,
    TAKEOVER_NOTE,
    UNBACKED_RESULT_NOTE,
    UNVERIFIED_PAID_NOTE,
    ClaimGuard,
    paid_note,
    paid_turn,
    recovery_turn,
    says_paid,
    spoken_items,
)
from .codex_voice import CodexVoice
from .kiosk_timing import KioskTiming
from .service import ServiceError
from .session_notices import (
    fallback_text,
    guest_situation,
    idle_nudge_turn,
    time_warning_turn,
)
from .speaker import SpeakerPeer


class KioskError(ServiceError):
    pass


VOICE_CLIPS = Path(__file__).parent / "static/voice"
SPEECH_RMS = 300  # 16-bit RMS, about -41 dBFS: quieter than this is not usable speech
BOUNDARY_TEXT = {
    "greeting": "Chào bạn, Trend có thể giúp bạn chọn món gì?",
    "goodbye": "Tạm biệt bạn, hẹn gặp lại tại Trend Coffee.",
}


SPEAKER_STOP_DELAY = 0.15
BROWSER_SPEAKER_STATS = (
    "packetsReceived",
    "packetsLost",
    "jitter",
    "jitterBufferDelay",
    "jitterBufferEmittedCount",
    "totalSamplesReceived",
    "concealedSamples",
    "silentConcealedSamples",
    "concealmentEvents",
    "insertedSamplesForDeceleration",
    "removedSamplesForAcceleration",
    "audioLevel",
    "totalAudioEnergy",
)


def speech_pcm(audio):
    """48 kHz mono PCM16 for the speaker, from a native or boundary-clip payload."""
    if not isinstance(audio, dict) or not isinstance(audio.get("data"), str):
        return b""
    pcm = base64.b64decode(audio["data"])
    rate, channels = audio.get("sampleRate"), audio.get("numChannels")
    if rate == 48000 and channels == 1:
        return pcm[: len(pcm) // 2 * 2]
    if channels not in (1, 2) or not isinstance(rate, int) or not 8000 <= rate <= 96000:
        return b""
    from av import AudioFrame, AudioResampler

    width = 2 * channels
    frame = AudioFrame(
        format="s16", layout="mono" if channels == 1 else "stereo", samples=len(pcm) // width
    )
    frame.planes[0].update(pcm[: len(pcm) // width * width])
    frame.sample_rate = rate
    resampler = AudioResampler(format="s16", layout="mono", rate=48000)
    out = [*resampler.resample(frame), *resampler.resample(None)]
    return b"".join(bytes(f.planes[0])[: f.samples * 2] for f in out)


@lru_cache(maxsize=64)
def boundary_speech(kind, voice=None):
    with wave.open(str(VOICE_CLIPS / (voice or "default") / f"{kind}.wav")) as source:
        audio = {
            "data": base64.b64encode(source.readframes(source.getnframes())).decode("ascii"),
            "sampleRate": source.getframerate(),
            "numChannels": source.getnchannels(),
        }
    return {"text": BOUNDARY_TEXT[kind], "voice": voice, "audio": audio}


class PresencePolicy:
    def __init__(self, *, threshold=0.6, enter_seconds=2.0, leave_seconds=3.0, freshness=1.5):
        self.threshold, self.enter_seconds = threshold, enter_seconds
        self.leave_seconds, self.freshness = leave_seconds, freshness
        self.active = False
        self.track_id = None
        self.candidate = None
        self.since = None
        self.absent_since = None
        self.last_received = None
        self.last_seq = -1
        self.blocked_track = None

    def observe(self, event, now, wall, *, authorized=False):
        seq, captured = event.get("frame_seq"), event.get("captured_at")
        if (
            type(seq) is not int
            or seq <= self.last_seq
            or type(captured) not in (int, float)
            or not math.isfinite(captured)
            or not -0.5 <= wall - captured <= self.freshness
        ):
            return self.tick(now)
        if self.last_received is not None and now - self.last_received > self.freshness:
            self.since = None
        self.last_received, self.last_seq = now, seq
        track = event.get("track_id")
        distance = event.get("nearest_m", 0)
        near = (
            event.get("event") == "person_near"
            and type(distance) in (float, int)
            and math.isfinite(distance)
            and 0 < distance < self.threshold
            and type(track) is int
        )
        if self.active:
            owner = next(
                (p for p in event.get("tracks", []) if p.get("track_id") == self.track_id), None
            )
            value = (owner.get("distance_m") or owner.get("body_m") or 0) if owner else 0
            present = bool(owner and type(value) in (int, float) and 0 < value < self.threshold)
            if not event.get("tracks"):
                present = near and track == self.track_id
            if present:
                self.absent_since = None
            elif self.absent_since is None:
                self.absent_since = now
            return self.tick(now)
        if not near:
            self.candidate = self.since = None
            self.blocked_track = None
            if authorized:
                if self.absent_since is None:
                    self.absent_since = now
                if now - self.absent_since >= self.leave_seconds:
                    return "leave"
            return None
        self.absent_since = None
        if track == self.blocked_track and not authorized:
            return None
        if authorized:
            self.blocked_track = None
        if track != self.candidate or self.since is None:
            self.candidate, self.since = track, now
        if authorized or now - self.since + 1e-6 >= self.enter_seconds:
            self.active, self.track_id = True, track
            self.absent_since = None
            return "enter"
        return None

    def tick(self, now):
        if self.last_received is not None and now - self.last_received > self.freshness:
            self.since = None
            if self.active and self.absent_since is None:
                self.absent_since = self.last_received + self.freshness
        if (
            self.active
            and self.absent_since is not None
            and now - self.absent_since >= self.leave_seconds
        ):
            self.active = False
            self.candidate = self.since = self.absent_since = None
            self.track_id = None
            return "leave"
        return None

    def reset(self, *, block=False):
        if block:
            self.blocked_track = self.track_id
        self.active = False
        self.track_id = self.candidate = self.since = self.absent_since = None


def _tool(name, description, properties=None, required=()):
    return {
        "type": "function",
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties or {},
            "required": list(required),
            "additionalProperties": False,
        },
    }


TEXT = {"type": "string"}
SCREEN_TOOLS = {
    "kiosk_cart",
    "kiosk_checkout",
    "kiosk_payment",
    "kiosk_progress",
    "kiosk_tables",
    "kiosk_fulfillment",
}


# Voice tools whose result can report a paid order to Codex.
PAYMENT_TOOLS = ("kiosk_payment", "kiosk_checkout")
PAID_NOTICE_WAIT = 20.0  # seconds a paid notice waits for such a tool call to finish


def screen_order(menu, ids):
    """`ids` in menu order, so an added drink does not reshuffle what was already shown."""
    wanted = set(ids)
    return [item["id"] for item in menu if item["id"] in wanted]


LINES = {
    "type": "array",
    "minItems": 1,
    "maxItems": 20,
    "items": {
        "type": "object",
        "properties": {
            "item_id": TEXT,
            "quantity": {"type": "integer", "minimum": 1, "maximum": 100},
            "options": {"type": "object", "additionalProperties": {"type": "string"}},
            "note": {"type": "string", "maxLength": 300},
        },
        "required": ["item_id", "quantity"],
        "additionalProperties": False,
    },
}
TOOLS = [
    _tool(
        "kiosk_tables",
        "Read LIVE merchant table status now, optionally for table_label. Use this for free-table/count/current-status questions. Only status=available means free. This read does not select, reserve or order. Report missing live data honestly.",
        {"table_label": TEXT},
    ),
    _tool(
        "kiosk_menu",
        "Read the whole current menu with no arguments. For preferences/recommendations, reason over the whole catalog and show your chosen real item_ids; query may label the customer's request. Text queries are only a convenience for named drinks, never evidence that no suitable drink exists. This tool displays choices; it does not order them.",
        {
            "query": TEXT,
            "queries": {"type": "array", "items": TEXT, "minItems": 1, "maxItems": 20},
            "item_ids": {"type": "array", "items": TEXT, "minItems": 1, "maxItems": 20},
        },
    ),
    _tool(
        "kiosk_cart",
        "Show/add/set/remove/clear cart. For multiple drinks use action=add, lines=[{item_id,quantity,options,note},...]; item notes are requests and may not be possible. Never concatenate names into one item_id. Exact catalog IDs/options only.",
        {
            "action": {"enum": ["view", "add", "set", "remove", "clear"]},
            "item_id": TEXT,
            "line_key": TEXT,
            "quantity": {"type": "integer", "minimum": 1, "maximum": 100},
            "options": {"type": "object", "additionalProperties": {"type": "string"}},
            "note": {"type": "string", "maxLength": 300},
            "lines": LINES,
        },
        ["action"],
    ),
    _tool(
        "kiosk_order_note",
        "Set an optional whole-order request note (up to 1000 characters). It is a request, not a promise that the merchant can accommodate it.",
        {"note": {"type": "string", "maxLength": 1000}},
        ["note"],
    ),
    _tool(
        "kiosk_fulfillment",
        "Set the customer's explicit fulfillment choice. At-table with no table_label automatically selects the first available live merchant table; retain an already selected table. Preserve a table the customer specifies. Selection does not reserve it.",
        {"fulfillment": {"enum": ["takeaway", "at_table"]}, "table_label": TEXT},
        ["fulfillment"],
    ),
    _tool(
        "kiosk_checkout",
        "Place the requested cart now and display the returned payment QR inline. No approval or second customer turn is needed. Pass newly requested drinks as lines=[{item_id,quantity,options,note},...] to add them to the cart and order them in this one call (same rules as kiosk_cart add). Supply fulfillment here when known; at-table auto-selects the first available live table if none is selected or specified. Repeating checkout without cart changes returns the same order.",
        {"lines": LINES, "fulfillment": {"enum": ["takeaway", "at_table"]}, "table_label": TEXT},
    ),
    _tool(
        "kiosk_payment",
        "Show the merchant-generated payment QR for this guest's submitted order and refresh its real status. Never invent QR or approve funds.",
    ),
    _tool("kiosk_progress", "Show this guest's actual local request progress."),
    _tool(
        "kiosk_knowledge",
        "Retrieve sourced current Trend Coffee facts.",
        {"query": TEXT},
        ["query"],
    ),
    _tool(
        "kiosk_support",
        "Save customer's support message locally; not delivered to the merchant.",
        {"reason": TEXT},
        ["reason"],
    ),
]


class InteractionHost:
    def __init__(
        self,
        service,
        *,
        codex=None,
        visual_url=None,
        fusion=None,
        clock=time.monotonic,
        wall=time.time,
        speaker_factory=SpeakerPeer,
        camera_factory=CameraPeer,
        timing=None,
    ):
        self.service = service
        # Staff-tuned session boundaries; a guest keeps the values their session began with.
        self.timing = timing or KioskTiming()
        self.session_timing = dict(self.timing.values)
        # In device-camera mode the browser sends its camera over WebRTC; JPEG packets
        # on the kiosk socket remain the fallback until that video arrives.
        self.camera_factory = camera_factory
        self.camera_peer = None
        # Trend's speech reaches the browser over WebRTC once it negotiates a speaker;
        # until then, or if that connection drops, PCM events use the kiosk socket.
        self.speaker_factory = speaker_factory
        self.speaker = None
        self.playback_lock = asyncio.Lock()
        self.playback_tasks = set()
        self._speaker_stop = None
        self.codex = codex or CodexVoice(Path(__file__).resolve().parent.parent)
        self.visual_url = visual_url
        self.fusion = fusion
        self.voice_active = False
        self.voice_ready = False
        self.voice_connection = None
        self.recovery_task = None
        self.last_microphone_at = None
        self.microphone_ready = asyncio.Event()
        self.require_microphone = False
        self.last_accepted_audio_at = None
        self.audio_gate = {"locked": False, "source": None, "reason": "not_started"}
        self.audio_metrics = {}
        self._audio_packet_times = {}
        self.playing = False
        self._playback_stopped_at = None
        self.closing = False
        self.last_audio_at = 0
        self.clock, self.wall = clock, wall
        self.policy = PresencePolicy(**self._presence_limits())
        self.generation = 0
        self.thread_id = None
        self.session_wall = 0.0  # wall time the current guest session began
        # Seconds to let a delegated tool show its own result before speech is shown.
        self.show_delay = 4.0
        self.screen = None  # what the last display tool put on the guest's screen
        self._voice_failure_stage = None
        self.token = ""
        self.active = False
        self.cart = []
        self.fulfillment = ""
        self.table_label = ""
        self.order_note = ""
        self.quote = None
        self.revision = 0
        self.send = None
        self.controller = None
        self.camera_source = "local"
        self.voice = None
        self.session_voice = None
        self.greeted = False
        self.vision = None
        self.vision_task = self.tick_task = self.start_task = None
        self.manual = False
        self.started = self.activity_at = 0
        # The guest's own activity (speech, touch, cart); Trend's speech is not counted, so
        # Trend's own question does not reset the guest's quiet stretch.
        self.guest_activity_at = 0
        self.idle_nudge = None  # guest_activity_at when Trend last asked a quiet guest
        self.warned = False
        self.calls = OrderedDict()
        self.submitted = {}
        self.cleanup_tasks = set()
        self.lock = asyncio.Lock()
        # A merchant-verified payment can be found by the screen's QR poll, the invoice worker
        # or a voice tool; the guest hears about each paid order once (see _order_paid).
        self.loop = None
        self.paid_seen = set()  # orders this guest was told about, by a notice or a tool
        self.paid_reported = set()  # orders a voice tool result already reported as paid
        self.payment_reads = 0  # voice kiosk_payment/kiosk_checkout calls in progress
        self.payment_reads_idle = asyncio.Event()
        self.payment_reads_idle.set()
        listeners = getattr(service, "paid_listeners", None)
        if listeners is not None:
            listeners.append(self._order_paid)

    async def voice_options(self):
        try:
            return [
                voice
                for voice in await self.codex.list_voices()
                if all((VOICE_CLIPS / voice / f"{kind}.wav").is_file() for kind in BOUNDARY_TEXT)
            ]
        except Exception as exc:
            raise KioskError("voice_options_unavailable", 503) from exc

    async def validate_voice(self, voice):
        if voice is not None and (
            not isinstance(voice, str) or voice not in await self.voice_options()
        ):
            raise KioskError("invalid_voice")

    async def set_voice(self, voice):
        await self.validate_voice(voice)
        self.voice = voice
        if not self.active:
            self.codex.voice = voice
        return {"voice": voice, "applies": "next_session" if self.active else "next_voice"}

    async def attach(
        self, token, send, *, camera_source="local", voice=None, require_microphone=False
    ):
        self.service.memory(token)
        if camera_source not in ("local", "device"):
            raise KioskError("invalid_camera_source")
        await self.validate_voice(voice)
        if self.controller is not None:
            raise KioskError("kiosk_busy", 409)
        self.controller = secrets.token_urlsafe(24)
        self.loop = asyncio.get_running_loop()
        self.camera_source = camera_source
        logging.getLogger(__name__).warning(
            "Kiosk controller attached at %s (camera %s)", time.strftime("%H:%M:%S"), camera_source
        )
        self.require_microphone = require_microphone
        self.voice = self.codex.voice = voice
        self.send = send
        await self.emit("status", status="waiting", message="Đang chờ khách trước kiosk.")
        return self.controller

    async def warmup(self):
        # Warm only local audio/vision models; no idle Codex thread or voice call.
        work = [self.fusion.start()] if self.fusion else []
        results = await asyncio.gather(*work, return_exceptions=True)
        return all(not isinstance(result, BaseException) for result in results)

    def start_background(self):
        if self.visual_url and self.vision_task is None:
            self.vision_task = asyncio.create_task(self._vision_loop())
        if self.tick_task is None:
            self.tick_task = asyncio.create_task(self._ticks())

    async def emit(self, kind, **data):
        if self.send is not None:
            await asyncio.wait_for(
                self.send({"type": kind, "generation": self.generation, **data}), 2
            )

    def snapshot(self):
        return {
            "cart": self.cart,
            "fulfillment": self.fulfillment,
            "tableLabel": self.table_label,
            "orderNote": self.order_note,
            "quote": self.quote,
            "revision": self.revision,
        }

    def audio_packet(self, stage):
        now = self.clock()
        metric = self.audio_metrics.setdefault(stage, {"packets": 0, "max_gap_ms": 0})
        metric["packets"] += 1
        previous = self._audio_packet_times.get(stage)
        if previous is not None:
            metric["max_gap_ms"] = max(metric["max_gap_ms"], round((now - previous) * 1000, 1))
        self._audio_packet_times[stage] = now

    def _speaker_ready(self):
        return self.speaker is not None and self.speaker.connected

    async def _speaker_offer(self, sdp):
        if not isinstance(sdp, str) or not sdp or len(sdp) > 12000:
            raise KioskError("invalid_speaker_offer")
        await self._close_speaker()
        speaker = self.speaker_factory(self._speaker_playing)
        try:
            answer = await asyncio.wait_for(speaker.answer(sdp), 10)
        except Exception as error:
            with contextlib.suppress(Exception):
                await speaker.close()
            raise KioskError("invalid_speaker_offer") from error
        self.speaker = speaker
        return {"sdp": answer}

    async def _camera_offer(self, sdp):
        if (
            self.camera_source != "device"
            or not isinstance(sdp, str)
            or not sdp
            or len(sdp) > 12000
        ):
            raise KioskError("invalid_camera_offer")
        await self._close_camera()
        camera = self.camera_factory(lambda jpeg: self.camera_frame(jpeg))
        try:
            answer = await asyncio.wait_for(camera.answer(sdp), 10)
        except Exception as error:
            with contextlib.suppress(Exception):
                await camera.close()
            raise KioskError("invalid_camera_offer") from error
        self.camera_peer = camera
        self.audio_metrics["camera_transport"] = camera.metrics
        return {"sdp": answer}

    async def _close_camera(self):
        camera, self.camera_peer = self.camera_peer, None
        if camera is not None:
            with contextlib.suppress(Exception):
                await camera.close()

    async def _close_speaker(self):
        speaker, self.speaker = self.speaker, None
        if self._speaker_stop is not None:
            self._speaker_stop.cancel()
            self._speaker_stop = None
        if speaker is not None:
            with contextlib.suppress(Exception):
                await speaker.close()

    def _speaker_playing(self, playing):
        """Called by the speaker clock when buffered speech starts or runs out."""
        if self._speaker_stop is not None:
            self._speaker_stop.cancel()
            self._speaker_stop = None
        if playing:
            self._schedule_playback(True)
        else:
            # The browser still plays its own short buffer and the room echo
            # decays after the last frame leaves; a short underrun is not a stop.
            self._speaker_stop = asyncio.get_running_loop().call_later(
                SPEAKER_STOP_DELAY, self._schedule_playback, False
            )

    def _schedule_playback(self, playing):
        task = asyncio.create_task(self._apply_playback(playing))
        self.playback_tasks.add(task)
        task.add_done_callback(self.playback_tasks.discard)

    async def _apply_playback(self, playing):
        async with self.playback_lock:
            if playing == self.playing:
                return
            self.playback_transition(playing)
            self.playing = playing
            if self.fusion and self.voice_active:
                with contextlib.suppress(Exception):
                    await self.fusion.playback(playing)
                self.activity_at = self.clock()
            with contextlib.suppress(Exception):
                await self.emit("speaking", playing=playing)

    def _announce(self, announcement):
        """Speak a boundary clip through the speaker; the event keeps only its text."""
        if not self._speaker_ready():
            return announcement
        self.speaker.push(speech_pcm(announcement["audio"]))
        return {**announcement, "audio": None}

    async def _assistant_audio(self, audio, thread=None):
        if hasattr(self.codex, "set_output_continuous"):
            self.codex.set_output_continuous(thread or self.thread_id, self._speaker_ready())
        if self._speaker_ready():
            pcm = speech_pcm(audio)
            if pcm:
                self.speaker.push(pcm)
            self.audio_metrics["speaker_transport"] = self.speaker.metrics
        else:
            await self.emit("audio", audio=audio)

    def _reply_cut(self, dropped_ms):
        """A guest turn began while Trend was speaking: the rest of the reply is not heard.

        Either the guest spoke over Trend or Trend's own voice came back through the
        microphone; fusion_recent around this time tells which. `dropped_ms` is known only
        for the server speaker (Pet); the browser player (Avatar 3D) does not report it.
        """
        cuts = self.audio_metrics.setdefault(
            "reply_cuts", {"count": 0, "dropped_ms": 0, "unmeasured": 0}
        )
        cuts["count"] += 1
        if dropped_ms:
            cuts["dropped_ms"] += dropped_ms
        else:
            cuts["unmeasured"] = cuts.get("unmeasured", 0) + 1
        logging.getLogger(__name__).warning(
            "A guest turn cut Trend off at %s; %s of the reply dropped",
            time.strftime("%H:%M:%S"),
            f"{dropped_ms} ms" if dropped_ms else "an unmeasured part",
        )

    def _recent_fusion(self, **values):
        """Numbers and categories only: the last 200 Fusion decisions (not plain silence)."""
        recent = self.audio_metrics.setdefault("fusion_recent", [])
        recent.append({"t": round(self.clock(), 2), **values})
        del recent[:-200]

    def playback_transition(self, playing):
        """Numbers only: a restart within 500 ms of a stop is a browser buffer underrun."""
        metric = self.audio_metrics.setdefault(
            "browser_playback", {"starts": 0, "stops": 0, "restarts_within_500ms": 0}
        )
        now = self.clock()
        if playing and not self.playing:
            metric["starts"] += 1
            stopped = self._playback_stopped_at
            metric["restarts_within_500ms"] += stopped is not None and now - stopped < 0.5
        elif not playing and self.playing:
            metric["stops"] += 1
            self._playback_stopped_at = now

    def audio_level(self, pcm):
        """Numbers only: how loud the microphone is, never its audio."""
        samples = array("h", pcm)
        rms = round(math.sqrt(sum(value * value for value in samples) / len(samples)))
        metric = self.audio_metrics.setdefault(
            "microphone_level", {"last_rms": 0, "peak_rms": 0, "speech_packets": 0, "packets": 0}
        )
        metric["packets"] += 1
        metric["last_rms"] = rms
        metric["peak_rms"] = max(metric["peak_rms"], rms)
        metric["speech_packets"] += rms >= SPEECH_RMS

    async def state(self):
        await self.emit("state", **self.snapshot())

    async def begin(self, *, manual=False):
        async with self.lock:
            generation = await self._initialize_guest(manual)
        if generation is not None:
            await self._connect_voice(generation)

    async def _initialize_guest(self, manual):
        if self.active:
            return
        self.generation += 1
        generation = self.generation
        self.active, self.manual = True, manual
        self.session_wall = self.wall()
        self.session_timing = dict(self.timing.values)
        self.screen = None
        self.session_voice = self.voice
        if self.speaker is not None:
            self.speaker.clear()
        self.greeted = False
        self.codex.voice = self.voice
        self.voice_ready = False
        self.last_microphone_at = None
        self.microphone_ready.clear()
        self.last_accepted_audio_at = None
        self.audio_gate = {"locked": False, "source": None, "reason": "not_started"}
        self.audio_metrics = {}
        if self.camera_peer is not None:  # the camera connection outlives a guest
            self.audio_metrics["camera_transport"] = self.camera_peer.metrics
        self._audio_packet_times = {}
        self.playing = False
        self._playback_stopped_at = None
        self.token = self.service.new_session()
        self.cart, self.fulfillment, self.table_label, self.quote = [], "", "", None
        self.order_note = ""
        self.revision = 0
        self.calls.clear()
        self.submitted.clear()
        self.paid_seen.clear()
        self.paid_reported.clear()
        self.started = self.activity_at = self.guest_activity_at = self.clock()
        self.warned = False
        self.idle_nudge = None
        await self.emit(
            "session",
            session_token=self.token,
            voice=self.session_voice,
            **self.snapshot(),
        )
        await self.emit(
            "status", status="connecting", message="Trend đang mở phiên trò chuyện mới…"
        )

        return generation

    async def _disconnect_voice(self):
        self.voice_connection = None
        self.voice_active = self.voice_ready = False
        thread, self.thread_id = self.thread_id, None
        if self.fusion:
            with contextlib.suppress(Exception):
                await self.fusion.end()
        if thread:
            await self._retire_voice(thread, self.session_wall)

    async def _drop_call(self):
        """End the realtime call but keep the guest's thread for the next call."""
        if not hasattr(self.codex, "end_call"):
            await self._disconnect_voice()
            return
        self.voice_connection = None
        self.voice_active = self.voice_ready = False
        if self.fusion:
            with contextlib.suppress(Exception):
                await self.fusion.end()
        if self.thread_id:
            with contextlib.suppress(Exception):
                await self.codex.end_call(self.thread_id)

    async def _connect_voice(self, generation):
        attempt = 0
        while self.active and generation == self.generation:
            if not self.active or generation != self.generation:
                return
            if self.thread_id and self.voice_connection is not None:
                await self._drop_call()  # a call that dropped mid-session
            if not self.active or generation != self.generation:
                return
            if attempt or self.voice_connection is None:
                await self.emit("status", status="connecting", message="Đang kết nối giọng nói…")
            self._voice_failure_stage = None
            if await self._open_voice(generation):
                return
            if self._voice_failure_stage in ("codex_thread", "codex_voice"):
                await self._disconnect_voice()  # this thread could not carry a call: replace it
            else:
                await self._drop_call()  # camera, microphone or A-V: keep the conversation
            if not self.active or generation != self.generation:
                return
            # Presence/idle limits own the retry lifetime. Never strand the
            # current guest after two failed calls and require a page reload.
            await asyncio.sleep(min(0.15 * 2**attempt, 2))
            attempt = min(attempt + 1, 5)

    async def _open_voice(self, generation):
        connection = object()
        self.voice_connection = connection
        transcript_buffers = {}
        # Results Trend states must come from a kiosk tool (see claim_guard.py).
        guard = ClaimGuard()
        reply_stopped = [False]
        paid_verified = [False]  # set only by a tool result that says paid
        paid_flagged = set()
        history = deque(maxlen=6)  # (role, text) of recent finished turns, for a recovery turn
        recovered = set()  # guest requests the kiosk already ran itself

        async def stop_unbacked_result(note=UNBACKED_RESULT_NOTE, *, payment=False):
            reply_stopped[0] = True
            if self.speaker is not None:
                self.speaker.interrupt()
            self.audio_metrics["unbacked_claims"] = self.audio_metrics.get("unbacked_claims", 0) + 1
            self._recent_fusion(claim="unbacked")  # when, never what
            logging.getLogger(__name__).warning(
                "Trend stated a result with no kiosk tool behind it at %s; reply stopped",
                time.strftime("%H:%M:%S"),
            )
            # The browser stops this reply as it does for a guest interruption.
            await self.emit("voice_turn", role="user")
            thread = self.thread_id
            request = guard.request_text
            key = (guard.request_at, payment)

            async def recover():
                # The voice never delegated: run the guest's request here, then tell the
                # voice so it neither repeats nor invents the result. If Codex refuses the
                # turn, fall back to asking the voice to delegate.
                told = note
                if request and key not in recovered and hasattr(self.codex, "start_turn"):
                    recovered.add(key)
                    try:
                        await self.codex.start_turn(
                            thread, recovery_turn(request, list(history), payment=payment)
                        )
                        told = TAKEOVER_NOTE
                    except Exception:
                        logging.getLogger(__name__).exception("Kiosk recovery turn failed")
                if hasattr(self.codex, "append_text"):
                    await self.codex.append_text(thread, "developer", told)

            if thread:
                # Not awaited here: this event arrives from Codex's own reader loop.
                task = asyncio.create_task(recover())
                self.cleanup_tasks.add(task)
                task.add_done_callback(self.cleanup_tasks.discard)

        def show_spoken_items(text):
            """Drinks Trend names without a kiosk tool behind them still reach the screen."""
            ids = spoken_items(text, self.service.menu())
            if not ids:
                return

            async def later():
                await asyncio.sleep(self.show_delay)
                if (
                    not self.active
                    or generation != self.generation
                    or self.voice_connection is not connection
                ):
                    return
                show = ids
                if guard.backed(self.clock()):
                    # A tool answered. Only a menu view for this request that lacks the drinks
                    # Trend named needs help; cart, payment and other screens are left alone.
                    screen = self.screen
                    if (
                        not screen
                        or screen["kind"] != "menu"
                        or guard.request_at is None
                        or screen["at"] < guard.request_at - 2.5
                        or screen["ids"] is None  # the whole menu is already on screen
                        or set(ids) <= screen["ids"]
                    ):
                        return
                    show = list(dict.fromkeys([*screen["ids"], *ids]))
                    show = [i for i in screen_order(self.service.menu(), show)]
                await self.emit("view", view="menu", query="", item_ids=show)
                self.audio_metrics["shown_for_speech"] = (
                    self.audio_metrics.get("shown_for_speech", 0) + 1
                )

            task = asyncio.create_task(later())
            self.cleanup_tasks.add(task)
            task.add_done_callback(self.cleanup_tasks.discard)

        async def tool(params):
            async with self.lock:
                self._check(generation)
                if self.voice_connection is not connection:
                    raise KioskError("stale_interaction", 409)
                call = params.get("callId")
                if call and call in self.calls:
                    return self.calls[call]
                name, args = params.get("tool"), params.get("arguments") or {}
                spec = next((t for t in TOOLS if t["name"] == name), None)
                if not spec or not Draft202012Validator(spec["inputSchema"]).is_valid(args):
                    raise KioskError("invalid_tool_arguments")
                guard.tool(self.clock())
                reads = name in PAYMENT_TOOLS
                if reads:
                    self.payment_reads += 1
                    self.payment_reads_idle.clear()
                try:
                    result = await self._tool(name, args)
                finally:
                    if reads:
                        self.payment_reads -= 1
                        if not self.payment_reads:
                            self.payment_reads_idle.set()
                if says_paid(result):
                    paid_verified[0] = True
                    payment = result.get("payment")
                    payment = payment if isinstance(payment, dict) else {}
                    # Codex already has this result: no separate paid notice for these orders.
                    self.paid_reported.update(
                        i
                        for i in (result.get("order_id"), result.get("id"), payment.get("order_id"))
                        if i
                    )
                if name == "kiosk_menu":
                    shown = [i["id"] for i in result.get("items", [])]
                    self.screen = {"kind": "menu", "ids": set(shown) or None, "at": self.clock()}
                elif name in SCREEN_TOOLS:
                    self.screen = {"kind": name, "ids": None, "at": self.clock()}
                if call:
                    self.calls[call] = result
                    while len(self.calls) > 128:
                        self.calls.popitem(last=False)
                return result

        async def event(method, params):
            if (
                not self.active
                or generation != self.generation
                or self.voice_connection is not connection
            ):
                return
            if (
                method
                in ("thread/realtime/userTurn/started", "thread/realtime/assistantTurn/started")
                and self.greeted
            ):
                if "/userTurn/" in method:
                    dropped = None
                    # Pet plays through the server speaker; Avatar 3D plays in the browser,
                    # which reports playback, so `playing` covers both characters.
                    speaking = self.playing
                    if self.speaker is not None:
                        dropped = self.speaker.buffered_ms()
                        self.speaker.interrupt()
                    self._recent_fusion(turn="user", dropped_ms=dropped)
                    if dropped or speaking:
                        self._reply_cut(dropped)
                else:
                    reply_stopped[0] = False
                    if self.speaker is not None:
                        self.speaker.resume()
                    self._recent_fusion(turn="assistant")
                await self.emit(
                    "voice_turn", role="user" if "/userTurn/" in method else "assistant"
                )
            elif method == "thread/realtime/transcript/delta" and self.greeted:
                role = params.get("role")
                turn_id = params.get("turnId")
                if role not in ("user", "assistant") or not turn_id:
                    return
                key = (role, str(turn_id))
                if key not in transcript_buffers:
                    self._recent_fusion(tr=role, final=False)  # when, never what
                text = (transcript_buffers.get(key, "") + str(params.get("delta", "")))[:4000]
                transcript_buffers[key] = text
                if role == "assistant" and guard.reply(str(turn_id), text, self.clock()):
                    await stop_unbacked_result()
                elif (
                    role == "assistant"
                    and not paid_verified[0]
                    and str(turn_id) not in paid_flagged
                    and PAID.search(text)
                ):
                    # A tool may have run, but none reported the order as paid.
                    paid_flagged.add(str(turn_id))
                    await stop_unbacked_result(UNVERIFIED_PAID_NOTE, payment=True)
                await self.emit(
                    "transcript",
                    role=role,
                    text=text[:4000],
                    turnId=str(turn_id),
                    partial=True,
                )
            elif method == "thread/realtime/transcript/done" and self.greeted:
                text = str(params.get("text", ""))[:4000]
                role = params.get("role")
                turn_id = params.get("turnId")
                if role in ("user", "assistant") and text.strip():
                    history.append((role, text.strip()[:240]))
                if role == "user":
                    self.activity_at = self.guest_activity_at = self.clock()
                    guard.guest(text, self.clock())
                elif (
                    role == "assistant"
                    and turn_id
                    and guard.reply(str(turn_id), text, self.clock())
                ):
                    await stop_unbacked_result()  # no partial text arrived for this reply
                if role == "assistant":
                    guard.done(text, self.clock())
                    show_spoken_items(text)
                if role in ("user", "assistant"):
                    self._recent_fusion(tr=role, final=True)
                if turn_id:
                    transcript_buffers.pop((role, str(turn_id)), None)
                await self.emit(
                    "transcript",
                    role=role,
                    text=text,
                    **({"turnId": str(turn_id)} if turn_id else {}),
                    partial=False,
                )
            elif (
                method == "thread/realtime/outputAudio/delta" and self.voice_active and self.greeted
            ):
                self.audio_packet("native_output")
                if hasattr(self.codex, "output_diagnostics"):
                    self.audio_metrics["native_output_transport"] = self.codex.output_diagnostics(
                        params.get("threadId")
                    )
                if reply_stopped[0]:
                    return  # the rest of a reply that stated a result no tool produced
                await self._assistant_audio(params.get("audio", {}), params.get("threadId"))
            elif method in ("thread/realtime/error", "thread/realtime/closed"):
                was_ready = self.voice_ready
                self.voice_active = self.voice_ready = False
                if was_ready:
                    # Evidence for how often and why calls drop mid-session.
                    logging.getLogger(__name__).warning(
                        "Voice call dropped at %s (%s, reason %s); reconnecting on the same thread",
                        time.strftime("%H:%M:%S"),
                        method.rsplit("/", 1)[-1],
                        str(params.get("reason", ""))[:80] or "-",
                    )
                if was_ready and (self.recovery_task is None or self.recovery_task.done()):
                    self.recovery_task = asyncio.create_task(self._connect_voice(generation))

        stage = "microphone"
        try:
            await self._wait_for_microphone(generation)
            stage = "codex_thread"
            # One guest, one conversation: a reconnect reuses the guest's thread when the
            # app-server still holds it, so the voice keeps the context and the session list
            # keeps one row per guest.
            thread = None
            if self.thread_id and hasattr(self.codex, "resume_thread"):
                try:
                    thread = await self.codex.resume_thread(self.thread_id, tool, event)
                except Exception:
                    old, self.thread_id = self.thread_id, None
                    await self._retire_voice(old, self.session_wall)
            created = thread is None
            if created:
                thread = await self.codex.create_thread(TOOLS, tool, event, self.service.menu())
            if not self.active or generation != self.generation:
                await self.codex.stop_voice(thread)
                return True
            self.thread_id = thread
            if created:
                self._name_thread_later(
                    thread, f"Kiosk {self._hhmm(self.session_wall)} — đang phục vụ"
                )
            if self.fusion is None:
                await self.emit(
                    "status",
                    status="unavailable",
                    message="Trợ lý giọng nói chưa được bật. Bạn vẫn có thể dùng màn hình.",
                )
                return True

            async def fused(event):
                if (
                    not self.active
                    or generation != self.generation
                    or self.voice_connection is not connection
                ):
                    return
                if event.get("type") == "pcm":
                    self.audio_packet("fusion_output")
                    self.audio_gate["reason"] = event.get("reason")
                    reasons = self.audio_metrics.setdefault("fusion_reasons", {})
                    reason = str(event.get("reason", "unknown"))
                    if reason != "silenced_no_voice" or event.get("accepted"):
                        backlog = {}
                        if event.get("accepted") and hasattr(self.codex, "input_diagnostics"):
                            queued = self.codex.input_diagnostics(thread).get("buffer_ms")
                            backlog = {"q": round(queued)} if queued is not None else {}
                        self._recent_fusion(
                            out=reason[:32], heard=bool(event.get("accepted")), **backlog
                        )
                    reasons[reason] = reasons.get(reason, 0) + 1
                    if not self.voice_active or not self.greeted:
                        return
                    pcm = base64.b64decode(event["data"], validate=True)
                    if len(pcm) == 2560:
                        await self.codex.append_audio(thread, pcm)
                        if hasattr(self.codex, "input_diagnostics"):
                            self.audio_metrics["native_input_transport"] = (
                                self.codex.input_diagnostics(thread)
                            )
                        self.audio_packet("native_input")
                        if event.get("accepted"):
                            self.last_accepted_audio_at = self.clock()
                            self.activity_at = self.guest_activity_at = self.clock()
                elif event.get("type") == "fusion":
                    verdict = str(event.get("verdict", "unknown"))
                    diagnostics = event.get("diagnostics")
                    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
                    probability = diagnostics.get("asd_probability")
                    mouth = diagnostics.get("mouth")
                    self._recent_fusion(
                        v=verdict[:16],
                        lock=bool(event.get("locked")),
                        p=round(probability, 2) if type(probability) is float else None,
                        mouth=round(mouth, 2) if type(mouth) is float else None,
                    )
                    counts = self.audio_metrics.setdefault("fusion_verdicts", {})
                    counts[verdict] = counts.get(verdict, 0) + 1
                    if isinstance(event.get("diagnostics"), dict):
                        self.audio_metrics["fusion_last_" + verdict.lower()] = event["diagnostics"]
                    self.audio_gate.update(
                        locked=event.get("locked", False), source=event.get("source")
                    )
                    now = self.clock()
                    if now - self.last_audio_at > 0.5:
                        self.last_audio_at = now
                        await self.emit(
                            "fusion", locked=event.get("locked", False), source=event.get("source")
                        )
                elif event.get("type") == "error":
                    was_ready = self.voice_ready
                    self.voice_active = False
                    self.voice_ready = False
                    await self.emit(
                        "status",
                        status="unavailable",
                        message="Trợ lý giọng nói bị gián đoạn. Bạn tiếp tục chọn món trên màn hình nhé.",
                    )
                    if was_ready and (self.recovery_task is None or self.recovery_task.done()):
                        self.recovery_task = asyncio.create_task(self._connect_voice(generation))

            stage = "av_fusion"
            await self.fusion.begin(generation, secrets.token_hex(16), fused, self.policy.track_id)
            self._check(generation)
            # Initialize Fusion and native voice before allowing guest audio through.
            self.voice_active = True
            await self.fusion.playback(self.playing)
            stage = "codex_voice"
            # The transport owns a 30 s handshake; do not cancel it at 20 s.
            await asyncio.wait_for(self.codex.start_filtered_voice(thread), 35)
            stage = "microphone"
            await self._wait_for_microphone(generation)
            stage = "av_check"
            if hasattr(self.fusion, "check_ready"):
                await self.fusion.check_ready()
            self._check(generation)
            if not self.voice_active:
                raise RuntimeError("native_voice_closed_during_start")
            self.voice_ready = True
            await self.emit(
                "status",
                status="listening",
                message="Bạn nói món muốn gọi nhé.",
            )
            self._check(generation)
            if not self.greeted:
                self.greeted = True
                await self.emit(
                    "announcement",
                    announcement=self._announce(boundary_speech("greeting", self.session_voice)),
                )
            return True
        except Exception:
            self._voice_failure_stage = stage
            if not self.active or generation != self.generation:
                return True
            logging.getLogger(__name__).exception("Voice connection failed at %s", stage)
            self.voice_active = self.voice_ready = False
            message = {
                "microphone": "Chưa nhận được âm thanh micro. Chạm màn hình và kiểm tra quyền micro.",
                "av_fusion": "Đang chờ camera thấy rõ khuôn mặt và kết nối A‑V…",
                "av_check": "Camera/A‑V bị gián đoạn. Trend đang kết nối lại…",
            }.get(stage, "Hội thoại chưa kết nối xong. Trend đang thử lại…")
            await self.emit("status", status="connecting", message=message)
            return False

    def _check(self, generation):
        if not self.active or generation != self.generation:
            raise KioskError("stale_interaction", 409)

    async def _wait_for_microphone(self, generation):
        if not self.require_microphone:
            return
        async with asyncio.timeout(30):
            while self.last_microphone_at is None or self.clock() - self.last_microphone_at > 1:
                self.microphone_ready.clear()
                await self.emit(
                    "status",
                    status="connecting",
                    message="Đang chờ micro. Chạm màn hình để bật âm thanh nếu trình duyệt đang tạm dừng.",
                )
                self._check(generation)
                if (
                    self.last_microphone_at is not None
                    and self.clock() - self.last_microphone_at <= 1
                ):
                    continue
                await self.microphone_ready.wait()
                self._check(generation)

    async def microphone(self, generation, pcm):
        self._check(generation)
        if len(pcm) == 2560:
            self.audio_packet("microphone")
            self.audio_level(pcm)
            self.last_microphone_at = self.clock()
            self.microphone_ready.set()
        if self.voice_active and self.fusion and len(pcm) == 2560:
            try:
                await self.fusion.audio(pcm)
            except Exception:
                was_ready = self.voice_ready
                self.voice_active = False
                self.voice_ready = False
                self.audio_gate["reason"] = "fusion_input_error"
                await self.emit(
                    "status",
                    status="unavailable",
                    message="Trợ lý giọng nói bị gián đoạn. Bạn tiếp tục bằng màn hình nhé.",
                )
                if was_ready and (self.recovery_task is None or self.recovery_task.done()):
                    self.recovery_task = asyncio.create_task(self._connect_voice(generation))

    def _changed(self):
        self.revision += 1
        self.quote = None
        self.activity_at = self.guest_activity_at = self.clock()

    async def _tool(self, name, args):
        self.activity_at = self.clock()
        if name == "kiosk_tables":
            return await asyncio.to_thread(self.service.tables, args.get("table_label"))
        if name == "kiosk_menu":
            query = str(args.get("query", ""))[:500]
            result = self.service.menu_search(
                query, args.get("queries"), item_ids=args.get("item_ids")
            )
            ids = [i["id"] for i in result["items"]]
            await self.emit(
                "view",
                view="menu",
                # An empty list means "show nothing" to the screen: when the search found no
                # dish, show the whole menu and do not filter it by the failed wording.
                query=(query or ", ".join(args.get("queries", []))) if ids else "",
                item_ids=ids or None,
            )
            return result
        if name == "kiosk_cart":
            action = args.get("action")
            if "lines" in args:
                if action != "add" or any(
                    k in args for k in ("item_id", "line_key", "quantity", "options", "note")
                ):
                    raise KioskError("invalid_cart_action")
                candidate = [dict(line) for line in self.cart]
                menu = {i["id"]: i for i in self.service.menu()}
                for line in args["lines"]:
                    item = menu.get(line["item_id"])
                    if item is None:
                        raise KioskError("item_not_found")
                    options = {
                        **{k: v[0] for k, v in item.get("options", {}).items() if v},
                        **line.get("options", {}),
                    }
                    note = line.get("note", "")
                    if not isinstance(note, str) or len(note) > 300:
                        raise KioskError("invalid_note")
                    identity_note = note.strip()
                    identity = item["id"] + json.dumps(
                        [sorted(options.items()), identity_note],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    existing = next(
                        (
                            i
                            for i in candidate
                            if i["item"]["id"] == item["id"]
                            and i["options"] == options
                            and i.get("note", "").strip() == identity_note
                        ),
                        None,
                    )
                    if existing:
                        existing["quantity"] += line["quantity"]
                    else:
                        candidate.append(
                            {
                                "key": identity + "#" + str(self.revision + len(candidate) + 1),
                                "item": item,
                                "quantity": line["quantity"],
                                "options": options,
                                "note": note,
                            }
                        )
                self.service.quote(
                    self.token,
                    [
                        {
                            "item_id": i["item"]["id"],
                            "quantity": i["quantity"],
                            "options": i["options"],
                            "note": i.get("note", ""),
                        }
                        for i in candidate
                    ],
                    "takeaway",
                )
                self.cart = candidate
                self._changed()
            elif action == "clear":
                self.cart = []
                self.order_note = ""
                self._changed()
            elif action in ("add", "set", "remove"):
                item_id, key = args.get("item_id"), args.get("line_key")
                selected_index = None
                if key is not None:
                    selected_index = next(
                        (i for i, line in enumerate(self.cart) if line["key"] == key), None
                    )
                    if selected_index is None:
                        raise KioskError("cart_line_not_found")
                    item_id = self.cart[selected_index]["item"]["id"]
                if not isinstance(item_id, str):
                    raise KioskError("invalid_cart_action")
                item = next((item for item in self.service.menu() if item["id"] == item_id), None)
                if item is None:
                    raise KioskError("item_not_found")
                provided_options = args.get("options")
                if provided_options is not None and not isinstance(provided_options, dict):
                    raise KioskError("invalid_options")
                defaults = {k: v[0] for k, v in item.get("options", {}).items() if v}
                if selected_index is not None:
                    selected = self.cart[selected_index]
                    options = (
                        provided_options if provided_options is not None else selected["options"]
                    )
                    note = args.get("note", selected.get("note", ""))
                else:
                    options = {**defaults, **(provided_options or {})}
                    note = args.get("note", "")
                if not isinstance(note, str) or len(note) > 300:
                    raise KioskError("invalid_note")
                identity_note = note.strip()
                options = {**defaults, **options}
                identity = item_id + json.dumps(
                    [sorted(options.items()), identity_note],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                if selected_index is None and action in ("set", "remove"):
                    candidates = [
                        i for i, line in enumerate(self.cart) if line["item"]["id"] == item_id
                    ]
                    if provided_options is not None:
                        candidates = [i for i in candidates if self.cart[i]["options"] == options]
                    if "note" in args:
                        candidates = [
                            i
                            for i in candidates
                            if self.cart[i].get("note", "").strip() == identity_note
                        ]
                    if len(candidates) > 1:
                        raise KioskError("ambiguous_cart_line")
                    if candidates:
                        selected_index = candidates[0]
                        selected = self.cart[selected_index]
                        options = {**defaults, **(provided_options or selected["options"])}
                        note = args.get("note", selected.get("note", ""))
                        identity_note = note.strip()
                        identity = item_id + json.dumps(
                            [sorted(options.items()), identity_note],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                selected = self.cart[selected_index] if selected_index is not None else None
                if action == "remove":
                    if selected_index is None:
                        raise KioskError("cart_line_not_found")
                    self.cart = [line for i, line in enumerate(self.cart) if i != selected_index]
                else:
                    quantity = args.get("quantity", 1)
                    if type(quantity) is not int or not 1 <= quantity <= 100:
                        raise KioskError("invalid_quantity")
                    if action == "add" and selected_index is None:
                        selected_index = next(
                            (
                                i
                                for i, line in enumerate(self.cart)
                                if line["item"]["id"] == item_id
                                and line["options"] == options
                                and line.get("note", "").strip() == identity_note
                            ),
                            None,
                        )
                        selected = self.cart[selected_index] if selected_index is not None else None
                    total = quantity + (selected["quantity"] if action == "add" and selected else 0)
                    # Shared business validator checks availability, options and total quantity.
                    updated = {
                        "key": selected["key"]
                        if selected
                        else identity + "#" + str(self.revision + 1),
                        "item": item,
                        "quantity": total,
                        "options": options,
                        "note": note,
                    }
                    candidate = list(self.cart)
                    if selected_index is None:
                        candidate.append(updated)
                    else:
                        candidate[selected_index] = updated
                    if len(candidate) > 20 or sum(line["quantity"] for line in candidate) > 100:
                        raise KioskError("quantity_limit")
                    self.service.quote(
                        self.token,
                        [{"item_id": item_id, "quantity": total, "options": options, "note": note}],
                        "takeaway",
                    )
                    self.cart = candidate
                self._changed()
            elif action != "view":
                raise KioskError("invalid_cart_action")
            if action != "view" and not self.cart:
                self.order_note = ""
            await self.state()
            if action == "view":
                await self.emit("view", view="cart")
            return self.snapshot()
        if name == "kiosk_order_note":
            note = args.get("note")
            if not isinstance(note, str) or len(note) > 1000:
                raise KioskError("invalid_note")
            if note != self.order_note:
                self.order_note = note
                self._changed()
            await self.state()
            return self.snapshot()
        if name == "kiosk_fulfillment":
            mode = args.get("fulfillment")
            table = str(args.get("table_label") or "").strip()[:50]
            if mode not in ("takeaway", "at_table"):
                raise KioskError("fulfillment_required")
            if mode == "at_table" and not table:
                if self.fulfillment == "at_table" and self.table_label:
                    table = self.table_label
                else:
                    try:
                        table = await asyncio.to_thread(self.service.resolve_table)
                    except ServiceError as error:
                        raise KioskError(error.code, error.status) from None
            table = table if mode == "at_table" else ""
            if (self.fulfillment, self.table_label) != (mode, table):
                self.fulfillment, self.table_label = mode, table
                self._changed()
            await self.state()
            return self.snapshot()
        if name == "kiosk_checkout":
            if args.get("lines"):
                # Add and order in one call: one model round trip less per spoken order.
                await self._tool("kiosk_cart", {"action": "add", "lines": args["lines"]})
            if args.get("fulfillment"):
                await self._tool(
                    "kiosk_fulfillment", {k: v for k, v in args.items() if k != "lines"}
                )
            if not self.cart and self.submitted:
                order = next(reversed(self.submitted.values()))
                await self.emit("order", order=order)
                return {
                    **order,
                    "payment": {
                        k: v for k, v in order.get("payment", {}).items() if k != "qr_image"
                    },
                    "qr_available": bool(order.get("payment", {}).get("qr_image")),
                }
            if not self.fulfillment:
                raise KioskError("fulfillment_required")
            checkout_id = str(self.revision)
            order = await asyncio.to_thread(
                self.service.checkout,
                self.token,
                [
                    {
                        "item_id": line["item"]["id"],
                        "quantity": line["quantity"],
                        "options": line["options"],
                        "note": line.get("note", ""),
                    }
                    for line in self.cart
                ],
                self.fulfillment,
                self.table_label or None,
                checkout_id=checkout_id,
                order_note=self.order_note,
            )
            self.submitted[checkout_id] = order
            self.cart = []
            self.order_note = ""
            self._changed()
            await self.state()
            await self.emit("order", order=order)
            return {
                **order,
                "payment": {k: v for k, v in order.get("payment", {}).items() if k != "qr_image"},
                "qr_available": bool(order.get("payment", {}).get("qr_image")),
            }
        if name == "kiosk_payment":
            orders = self.service.progress(self.token)["orders"]
            payment = (
                await asyncio.to_thread(self.service.payment, self.token, orders[0]["id"])
                if orders
                else {"status": "order_required", "qr_image": None}
            )
            result = {
                "payment_connected": (
                    bool(payment.get("payment_connected"))
                    if orders
                    else bool(self.service.merchant)
                ),
                "payment": {k: v for k, v in payment.items() if k != "qr_image"},
                "qr_available": bool(payment.get("qr_image")),
                "order_id": orders[0]["id"] if orders else None,
            }
            if not orders:
                result["pending_cart"] = self.snapshot()
            await self.emit("view", view="payment", payment=result)
            return result
        if name == "kiosk_progress":
            await self.emit("view", view="progress")
            return self.service.progress(self.token)
        if name == "kiosk_knowledge":
            return {"results": self.service.search(str(args.get("query", ""))[:500])}
        if name == "kiosk_support":
            return self.service.handoff(self.token, str(args.get("reason", ""))[:1000])
        raise KioskError("tool_not_permitted", 403)

    async def command(self, message):
        kind = message.get("type")
        if kind == "voice_setting":
            return await self.set_voice(message.get("voice"))
        if kind == "begin":
            if self.start_task is None or self.start_task.done():
                self.start_task = asyncio.create_task(self.begin(manual=True))
            return {"starting": True}
        if kind == "end":
            await self.end("next_guest")
            return {"ended": True}
        if kind == "speaker_offer":
            return await self._speaker_offer(message.get("sdp"))
        if kind == "camera_offer":
            return await self._camera_offer(message.get("sdp"))
        if kind == "speaker_stats":
            stats = message.get("stats")
            if isinstance(stats, dict):
                # Numbers only, from the browser's WebRTC playout (NetEQ).
                self.audio_metrics["browser_speaker"] = {
                    key: stats[key]
                    for key in BROWSER_SPEAKER_STATS
                    if type(stats.get(key)) in (int, float)
                }
            return {}
        self._check(message.get("generation"))
        if kind == "playback":
            self.playback_transition(message.get("playing") is True)
            self.playing = message.get("playing") is True
            if self.fusion and self.voice_active:
                await self.fusion.playback(self.playing)
                self.activity_at = self.clock()
            return {}
        if kind == "activity":
            self.activity_at = self.guest_activity_at = self.clock()
            return {}
        async with self.lock:
            self._check(message.get("generation"))
            if kind == "checkout":
                return await self._tool("kiosk_checkout", {})
            if kind == "payment":
                return await self._tool("kiosk_payment", {})
            if kind != "action":
                raise KioskError("invalid_kiosk_command")
            action = message.get("action", {})
            name = action.get("type")
            if name in ("add", "quantity", "remove", "clear"):
                args = {
                    "action": {
                        "add": "add",
                        "quantity": "set",
                        "remove": "remove",
                        "clear": "clear",
                    }[name]
                }
                if name == "add":
                    args.update(
                        item_id=action.get("item", {}).get("id"),
                        quantity=action.get("quantity"),
                        options=action.get("options", {}),
                        note=action.get("note", ""),
                    )
                elif name in ("quantity", "remove"):
                    args.update(line_key=action.get("key"), quantity=action.get("value"))
                return await self._tool("kiosk_cart", args)
            if name == "line_note":
                current = next(
                    (line for line in self.cart if line["key"] == action.get("key")), None
                )
                if current is None:
                    raise KioskError("invalid_cart_action")
                return await self._tool(
                    "kiosk_cart",
                    {
                        "action": "set",
                        "line_key": current["key"],
                        "quantity": current["quantity"],
                        "note": action.get("value", ""),
                    },
                )
            if name == "order_note":
                return await self._tool("kiosk_order_note", {"note": action.get("value", "")})
            if name in ("fulfillment", "table"):
                mode = action.get("value") if name == "fulfillment" else self.fulfillment
                table = action.get("value") if name == "table" else self.table_label
                # Touch edits are drafts: allow clearing and intermediate table-number prefixes.
                if (
                    mode == "at_table"
                    and not table
                    and (name == "table" or not self.service.merchant)
                ):
                    self.fulfillment, self.table_label = mode, ""
                    self._changed()
                    await self.state()
                    return self.snapshot()
                return await self._tool(
                    "kiosk_fulfillment", {"fulfillment": mode, "table_label": table}
                )
            raise KioskError("invalid_cart_action")

    async def observe(self, event):
        result = self.policy.observe(
            event, self.clock(), self.wall(), authorized=self.active and self.manual
        )
        if result == "enter" and not self.active:
            if self.start_task is None or self.start_task.done():
                self.start_task = asyncio.create_task(self.begin())
        elif result == "leave" and self.active:
            await self.end("customer_left")

    async def camera(self, jpeg):
        """A JPEG from the kiosk socket: the fallback while WebRTC video is not arriving."""
        if self.camera_peer is not None and self.camera_peer.receiving():
            return
        await self.camera_frame(jpeg)

    async def camera_frame(self, jpeg):
        if (
            self.camera_source == "device"
            and self.vision is not None
            and 2 <= len(jpeg) <= 256000
            and jpeg[:2] == b"\xff\xd8"
        ):
            await self.vision.send(struct.pack("<d", self.wall()) + jpeg)

    async def _vision_loop(self):
        import websockets

        delays = (1, 2, 4, 8, 15)
        attempt = 0
        while self.controller is not None:
            try:
                async with websockets.connect(
                    self.visual_url, max_size=2 * 1024 * 1024, close_timeout=1
                ) as socket:
                    self.vision = socket
                    stream = secrets.token_hex(16)
                    logging.getLogger(__name__).warning(
                        "Visual camera link open at %s (%s, stream %s)",
                        time.strftime("%H:%M:%S"),
                        self.camera_source,
                        stream[:8],
                    )
                    await socket.send(
                        json.dumps(
                            {
                                "cmd": "video_start",
                                "session_id": self.controller,
                                "stream_id": stream,
                                "prefer_remote": self.camera_source == "device",
                                "camera_source": self.camera_source,
                            }
                        )
                    )
                    await self.emit("sensor", connected=True)
                    attempt = 0
                    local_camera = None
                    async for raw in socket:
                        if isinstance(raw, str):
                            event = json.loads(raw)
                            if (
                                event.get("event") == "video_status"
                                and event.get("status") != "ready"
                            ):
                                raise RuntimeError(
                                    f"selected_camera_unavailable: {event.get('status')}"
                                )
                            available = event.get("local_camera_available")
                            if type(available) is bool and available != local_camera:
                                local_camera = available
                                await self.emit("camera", local_available=available)
                            if "event" in event and event["event"] != "faces":
                                await self.observe(event)
            except Exception as error:
                self.vision = None
                # Losing this link releases the device camera in Visual; say why.
                logging.getLogger(__name__).warning(
                    "Visual camera link lost at %s: %s: %s",
                    time.strftime("%H:%M:%S"),
                    type(error).__name__,
                    error,
                )
                with contextlib.suppress(Exception):
                    await self.emit("sensor", connected=False)
                if self.controller is None:
                    return
                await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
                attempt += 1
            finally:
                self.vision = None

    async def _ticks(self):
        while self.controller is not None:
            await asyncio.sleep(0.2)
            now = self.clock()
            if self.policy.tick(now) == "leave" and self.active:
                await self.end("sensor_or_customer_left")
            if not self.active:
                continue
            await self._session_step(now)

    async def _session_step(self, now):
        """One tick of a guest session: end it at the time limit, or have Trend speak up."""
        limit = self.session_limit(now)
        if limit == "time_limit":
            await self.end(limit)
        elif limit == "warning":
            self.warned = True
            seconds = self.session_timing["warning_seconds"]
            self._speak("time", time_warning_turn(seconds), fallback_text("time", seconds))
        elif limit == "idle_nudge":
            # A quiet guest is asked, never sent away (user decision 2026-11-05); the session
            # still ends when the guest leaves the camera or at the time limit.
            self.idle_nudge = self.guest_activity_at
            state, facts = self.guest_situation()
            self.audio_metrics["idle_nudges"] = self.audio_metrics.get("idle_nudges", 0) + 1
            self._speak(
                "nudge",
                idle_nudge_turn(state, facts, self.session_timing["idle_seconds"]),
                fallback_text("nudge"),
            )

    def session_limit(self, now):
        """'time_limit', 'warning' (once), 'idle_nudge' (once per quiet stretch) or None.

        Uses this guest's own limits. Trend speaking does not count as the guest's activity, so
        a guest who stays quiet after Trend's question is not asked again until they act.
        """
        limits = self.session_timing
        elapsed = now - self.started
        if elapsed >= limits["session_limit_seconds"]:
            return "time_limit"
        if self.idle_nudge is not None and self.guest_activity_at > self.idle_nudge:
            self.idle_nudge = None  # the guest acted: a new quiet stretch may be asked about
        if (
            limits["warning_seconds"] > 0
            and elapsed >= limits["session_limit_seconds"] - limits["warning_seconds"]
            and not self.warned
        ):
            return "warning"
        if self.idle_nudge is None and now - self.activity_at >= limits["idle_seconds"]:
            return "idle_nudge"
        return None

    def guest_situation(self):
        """Where this guest is: nothing chosen, cart, order awaiting payment, or paid."""
        order = next(reversed(self.submitted.values()), None) if self.submitted else None
        return guest_situation(
            self.cart,
            self.fulfillment,
            self.table_label,
            order,
            paid=bool(order and order.get("id") in self.paid_seen),
        )

    def _speak(self, kind, text, fallback):
        """Trend says it; the screen shows the fallback only if Trend cannot."""
        generation, thread = self.generation, self.thread_id
        self.audio_metrics["spoken_warnings"] = self.audio_metrics.get("spoken_warnings", 0) + 1

        async def speak():
            if thread and hasattr(self.codex, "start_turn"):
                try:
                    await self.codex.start_turn(thread, text)
                    return
                except Exception:
                    logging.getLogger(__name__).exception("Kiosk %s turn failed", kind)
            if self.active and generation == self.generation:
                await self.emit("warning", message=fallback)

        # Not awaited: a Codex request must not hold up the session clock.
        task = asyncio.create_task(speak())
        self.cleanup_tasks.add(task)
        task.add_done_callback(self.cleanup_tasks.discard)

    def _presence_limits(self):
        values = self.timing.values
        return {
            "threshold": values["presence_distance_m"],
            "enter_seconds": values["enter_seconds"],
            "leave_seconds": values["leave_seconds"],
        }

    def apply_timing(self):
        """New presence limits take effect between guests; a current guest keeps theirs."""
        if self.active:
            return False
        for name, value in self._presence_limits().items():
            setattr(self.policy, name, value)
        return True

    async def end(self, reason):
        async with self.lock:
            if not self.active:
                return
            self.active, self.voice_active, self.voice_ready = False, False, False
            self.codex.voice = self.voice
            self.voice_connection = None
            if self.recovery_task and self.recovery_task != asyncio.current_task():
                self.recovery_task.cancel()
            self.generation += 1
            self.policy.reset(block=reason in ("next_guest", "idle", "time_limit"))
            self.apply_timing()
            thread, self.thread_id = self.thread_id, None
            self.cart, self.quote = [], None
            self.token = ""
            self.fulfillment, self.table_label, self.order_note = "", "", ""
            self.playing = False
            if (
                self.start_task
                and not self.start_task.done()
                and self.start_task != asyncio.current_task()
            ):
                self.start_task.cancel()
            if thread:
                task = asyncio.create_task(self._retire_voice(thread, self.session_wall))
                self.cleanup_tasks.add(task)
                task.add_done_callback(self.cleanup_tasks.discard)
            if self.fusion:
                with contextlib.suppress(Exception):
                    await self.fusion.end()
            if self.speaker is not None:
                self.speaker.clear()
            await self.emit(
                "ended",
                reason=reason,
                announcement=(
                    self._announce(boundary_speech("goodbye", self.session_voice))
                    if reason != "disconnected"
                    else None
                ),
            )

    @staticmethod
    def _hhmm(wall):
        return time.strftime("%H:%M", time.localtime(wall))

    def _name_thread_later(self, thread, name):
        """Title the guest's Codex thread without holding back the greeting."""
        if not hasattr(self.codex, "name_thread"):
            return
        task = asyncio.create_task(self.codex.name_thread(thread, name))
        self.cleanup_tasks.add(task)
        task.add_done_callback(self.cleanup_tasks.discard)

    async def _retire_voice(self, thread, started=None):
        # Authority and media are already revoked; network teardown must not hold the kiosk.
        if started and hasattr(self.codex, "name_thread"):
            with contextlib.suppress(Exception):
                await self.codex.name_thread(
                    thread, f"Kiosk {self._hhmm(started)}–{self._hhmm(self.wall())}"
                )
        with contextlib.suppress(Exception):
            await self.codex.stop_voice(thread)  # also archives the thread

    async def detach(self, controller):
        if controller != self.controller:
            return
        logging.getLogger(__name__).warning(
            "Kiosk controller detached at %s", time.strftime("%H:%M:%S")
        )
        with contextlib.suppress(Exception):
            await self.end("disconnected")
        await self._close_speaker()
        await self._close_camera()
        self.controller, self.send = None, None
        tasks = [
            task
            for task in (self.start_task, self.recovery_task, self.vision_task, self.tick_task)
            if task is not None
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.start_task = self.recovery_task = self.vision_task = self.tick_task = None
        self.policy = PresencePolicy(**self._presence_limits())

    def _order_paid(self, session, order):
        """Service listener, called from any thread when an order first becomes paid."""
        loop = self.loop
        if loop is None or loop.is_closed():
            return
        with contextlib.suppress(RuntimeError):  # the loop closed meanwhile
            loop.call_soon_threadsafe(self._paid_on_loop, session, order)

    def _paid_on_loop(self, session, order):
        if (
            not self.active
            or not self.token
            or session != self.service.session_id(self.token)
            or order.get("id") in self.paid_seen
        ):
            return
        self.paid_seen.add(order.get("id"))
        task = asyncio.create_task(self._announce_paid(self.generation, order))
        self.cleanup_tasks.add(task)
        task.add_done_callback(self.cleanup_tasks.discard)

    async def _announce_paid(self, generation, order):
        """Show the paid order and let Trend, with the order's details, tell the guest."""
        # A voice payment read running now may be the one that found it; let it finish first.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.payment_reads_idle.wait(), PAID_NOTICE_WAIT)
        if (
            not self.active
            or generation != self.generation
            or order.get("id") in self.paid_reported
        ):
            return
        logging.getLogger(__name__).warning(
            "Merchant verified payment for the guest's order at %s", time.strftime("%H:%M:%S")
        )
        self.audio_metrics["paid_notices"] = self.audio_metrics.get("paid_notices", 0) + 1
        await self.emit("view", view="payment", order_id=order.get("id"))
        thread = self.thread_id
        if not thread:
            return  # no conversation: the screen alone tells the guest
        if hasattr(self.codex, "start_turn"):
            try:
                await self.codex.start_turn(thread, paid_turn(order))
                return
            except Exception:
                logging.getLogger(__name__).exception("Kiosk paid-order turn failed")
        if (
            hasattr(self.codex, "append_text")
            and self.active
            and generation == self.generation
            and thread == self.thread_id
        ):
            with contextlib.suppress(Exception):
                await self.codex.append_text(thread, "developer", paid_note(order))

    async def close(self):
        self.closing = True
        listeners = getattr(self.service, "paid_listeners", None)
        if listeners is not None and self._order_paid in listeners:
            listeners.remove(self._order_paid)
        await self.detach(self.controller)
        await asyncio.gather(*self.cleanup_tasks, return_exceptions=True)
        await self.codex.close()
        if self.fusion:
            await self.fusion.close()
