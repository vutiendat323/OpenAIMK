"""Server WebRTC bridge: its only input is post-Fusion PCM, never a device."""

import asyncio
import base64
import contextlib
import json
import math
import socket
import time
from array import array
from collections import deque
from fractions import Fraction

from aiortc import (
    AudioStreamTrack,
    RTCConfiguration,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.jitterbuffer import JitterFrame
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame, AudioResampler

from .speaker import speech_capture


class FilteredTrack(AudioStreamTrack):
    MAX_PENDING = 32  # 2.56s: covers delayed Fusion/TSE release without evicting onset.

    def __init__(self):
        super().__init__()
        self.pending = deque()
        self.tail = bytearray()
        self.samples = 0
        self.origin = None
        self.speech_started = False
        self.metrics = {"packets": 0, "underflow_frames": 0, "max_buffer_ms": 0, "buffer_ms": 0}

    def push(self, pcm):
        if self.readyState == "live" and len(pcm) == 2560:
            # recv() already supplies startup silence. Queuing Fusion's masked
            # startup batches would put those pauses in front of the first words.
            if not self.speech_started:
                if not any(pcm):
                    return
                self.speech_started = True
            if len(self.pending) >= self.MAX_PENDING:
                raise BufferError("native_input_backlog")
            self.pending.append(pcm)
            self.metrics["packets"] += 1
            self.metrics["buffer_ms"] = len(self.pending) * 80 + len(self.tail) / 32
            self.metrics["max_buffer_ms"] = max(
                self.metrics["max_buffer_ms"], self.metrics["buffer_ms"]
            )

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError
        if self.origin is None:
            self.origin = time.monotonic()
        deadline = self.origin + self.samples / 16000
        await asyncio.sleep(max(0, deadline - time.monotonic()))
        if time.monotonic() - deadline > 0.2:
            self.origin = time.monotonic() - self.samples / 16000
            # Re-anchor the clock, retaining the bounded approved speech.
            # A scheduler stall must not erase the customer's first words.
        if not self.tail and self.pending:
            self.tail.extend(self.pending.popleft())
        if self.speech_started and not self.tail:
            self.metrics["underflow_frames"] += 1
        pcm = bytes(self.tail[:640])
        del self.tail[:640]
        self.metrics["buffer_ms"] = len(self.pending) * 80 + len(self.tail) / 32
        pcm += bytes(640 - len(pcm))
        frame = AudioFrame(format="s16", layout="mono", samples=320)
        frame.planes[0].update(pcm)
        frame.sample_rate = 16000
        frame.pts, frame.time_base = self.samples, Fraction(1, 16000)
        self.samples += 320
        return frame

    def stop(self):
        self.pending.clear()
        self.tail.clear()
        super().stop()


# A lost packet up to this length keeps its duration as smoothed silence.
# Longer jumps are codec pauses or new phrases, which the browser handles.
LOSS_FILL_MAX_SAMPLES = 5760  # 120 ms at 48 kHz
RAMP_SAMPLES = 240  # 5 ms at 48 kHz


class ArrivalAudioBuffer:
    """Decode each native audio packet when it arrives, in sequence order.

    aiortc's audio JitterBuffer(capacity=16, prefetch=4) holds every packet behind
    a lost one until 16 later packets arrive (320 ms of 20 ms Opus), then discards
    good packets with it. The browser's playback buffer already absorbs network
    jitter, so this buffer only rejects late and duplicate packets.
    """

    SEQUENCE_RESET = 3000  # a larger forward jump is a new sender sequence

    def __init__(self):
        self.last = None
        self.metrics = {
            "packets": 0,
            "lost": 0,
            "late": 0,
            "concealed_ms": 0,
            "arrival_gaps_over_100ms": 0,
            "max_arrival_gap_ms": 0,
            "max_send_ms": 0,
        }

    def add(self, packet):
        sequence = packet.sequence_number
        if self.last is not None:
            delta = (sequence - self.last) & 0xFFFF
            if delta == 0 or delta >= 0x8000:
                self.metrics["late"] += 1
                return False, None
            if delta <= self.SEQUENCE_RESET:
                self.metrics["lost"] += delta - 1
        self.last = sequence
        data = getattr(packet, "_data", b"")
        if not data:
            return False, None
        self.metrics["packets"] += 1
        return False, JitterFrame(data=data, timestamp=packet.timestamp)


class NativePeer:
    def __init__(self, native, thread, on_event):
        self.native, self.thread, self.on_event = native, thread, on_event
        self.peer = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self.track = FilteredTrack()
        self.peer.addTrack(self.track)
        self.output_buffer = ArrivalAudioBuffer()
        self.capture = speech_capture("native")
        # The WebRTC speaker uses native's steady 20 ms clock, so it receives every
        # frame; the socket path forwards only speech and its surrounding pauses.
        self.continuous = False
        for receiver in self.peer.getReceivers():
            if receiver._RTCRtpReceiver__kind == "audio":
                receiver._RTCRtpReceiver__jitter_buffer = self.output_buffer
        self.channel = self.peer.createDataChannel("oai-events")
        self.ready = asyncio.get_running_loop().create_future()
        self.tasks = set()
        self.closed = False
        self.failed = False
        self.connect_tasks = set()
        connect = self.peer._RTCPeerConnection__connect

        async def owned_connect():
            # aiortc schedules this coroutine without retaining its task. Own
            # it so a cancelled handshake cannot restart a closed transport.
            if self.closed:
                return
            task = asyncio.current_task()
            self.connect_tasks.add(task)
            try:
                await connect()
            except Exception:
                self.failed = True
                if not self.ready.done():
                    self.ready.set_exception(RuntimeError("native_webrtc_failed"))
                self.offer("thread/realtime/error", {})
            finally:
                self.connect_tasks.discard(task)

        self.peer._RTCPeerConnection__connect = owned_connect
        self.assistant_speaking = False
        self.transcript_turns = {}
        self.transcript_serial = 0
        self.output = asyncio.Queue(maxsize=64)
        self.sender = self.spawn(self._send())

        @self.channel.on("message")
        def message(raw):
            try:
                event = json.loads(raw)
            except (ValueError, TypeError):
                return
            self.handle_event(event)

        @self.peer.on("track")
        def received(track):
            if track.kind == "audio":
                self.spawn(self.receive_audio(track))

        @self.peer.on("connectionstatechange")
        async def changed():
            if not self.closed and self.peer.connectionState in ("failed", "closed"):
                self.failed = True
                if not self.ready.done():
                    self.ready.set_exception(RuntimeError("native_webrtc_failed"))
                self.offer("thread/realtime/error", {})

    def transcript_turn(self, role, native_id=None):
        if role not in self.transcript_turns:
            self.transcript_serial += 1
            self.transcript_turns[role] = native_id or f"{role}-{self.transcript_serial}"
        return self.transcript_turns[role]

    def handle_event(self, event):
        kind = event.get("type")
        if kind == "session.started" and not self.ready.done():
            self.ready.set_result(True)
        elif kind in ("error", "session.closed"):
            self.failed = True
            if not self.ready.done():
                self.ready.set_exception(RuntimeError("native_webrtc_unavailable"))
            self.offer("thread/realtime/error", {})
        elif kind == "turn.created":
            turn = event.get("turn", {})
            if turn.get("role") in ("user", "assistant"):
                self.transcript_turn(turn["role"], turn.get("id"))
            if turn.get("role") == "assistant":
                self.assistant_speaking = True
                self.offer("thread/realtime/assistantTurn/started", {"turnId": turn.get("id")})
            if turn.get("role") == "user" and turn.get("id"):
                self.offer("thread/realtime/userTurn/started", {"turnId": turn["id"]})
        elif kind == "turn.done":
            turn = event.get("turn", {})
            role, text = turn.get("role"), turn.get("transcript", "")
            if role == "assistant":
                self.assistant_speaking = False
            if role in ("user", "assistant") and text:
                self.offer(
                    "thread/realtime/transcript/done",
                    {
                        "role": role,
                        "text": str(text)[:4000],
                        "turnId": self.transcript_turn(role, turn.get("id")),
                    },
                )
            self.transcript_turns.pop(role, None)
        elif kind in ("input_transcript.added", "output_transcript.added"):
            item = event.get("item", {})
            role = "user" if kind == "input_transcript.added" else "assistant"
            self.offer(
                "thread/realtime/transcript/delta",
                {
                    "role": role,
                    "delta": str(item.get("text", ""))[:1000],
                    "turnId": self.transcript_turn(role),
                },
            )
        elif kind in ("session.input_transcript.delta", "session.output_transcript.delta"):
            role = "user" if kind == "session.input_transcript.delta" else "assistant"
            self.offer(
                "thread/realtime/transcript/delta",
                {
                    "role": role,
                    "delta": str(event.get("delta", ""))[:1000],
                    "turnId": self.transcript_turn(role),
                },
            )

    def spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def offer(self, method, params):
        if self.closed:
            return
        if self.output.full():
            # Only control events use this queue. Fail explicitly rather than
            # silently discarding a transcript or turn boundary.
            while not self.output.empty():
                self.output.get_nowait()
            method, params = "thread/realtime/error", {}
        self.output.put_nowait((method, {"threadId": self.thread, **params}))

    async def _send(self):
        while not self.closed:
            method, params = await self.output.get()
            await self.on_event(method, params)

    async def receive_audio(self, track):
        # Match the browser's playback clock. Per-packet 24→48 kHz browser
        # resampling restarts its filter at each join and creates audible clicks.
        resampler = AudioResampler(format="s16", layout="mono", rate=48000)
        last_speech = 0
        onset = deque(maxlen=8)
        expected = None  # pts of the next frame when no packet is lost
        last_sample = 0
        fade_in = False
        arrived = None
        try:
            while not self.closed:
                frame = await track.recv()
                # Numbers only: a delay here starves the browser's playback buffer.
                previous, arrived = arrived, time.monotonic()
                if self.assistant_speaking and previous is not None:
                    gap = round((arrived - previous) * 1000)
                    metrics = self.output_buffer.metrics
                    metrics["max_arrival_gap_ms"] = max(metrics["max_arrival_gap_ms"], gap)
                    metrics["arrival_gaps_over_100ms"] += gap > 100
                chunks = []
                missing = 0
                if frame.pts is not None and frame.time_base:
                    if expected is not None and frame.pts > expected:
                        missing = round((frame.pts - expected) * frame.time_base * 48000)
                    expected = frame.pts + round(
                        frame.samples / frame.sample_rate / frame.time_base
                    )
                if 0 < missing <= LOSS_FILL_MAX_SAMPLES:
                    # Keep a lost packet's duration, or the browser's playback
                    # buffer drains by one packet per loss. Ramp to silence and
                    # fade the next packet in, so neither edge is a click.
                    fill = array("h", bytes(missing * 2))
                    ramp = min(RAMP_SAMPLES, missing)
                    for i in range(ramp):
                        fill[i] = round(last_sample * (ramp - 1 - i) / ramp)
                    chunks.append(fill)
                    fade_in = True
                    self.output_buffer.metrics["concealed_ms"] += round(missing / 48)
                for output in resampler.resample(frame):
                    samples = array("h", bytes(output.planes[0])[: output.samples * 2])
                    if self.capture is not None:
                        level = round(math.sqrt(sum(v * v for v in samples) / max(1, len(samples))))
                        self.capture.log(arrived, frame.pts if frame.pts is not None else -1, level)
                        self.capture.write(samples.tobytes())
                    if fade_in and samples:
                        ramp = min(RAMP_SAMPLES, len(samples))
                        for i in range(ramp):
                            samples[i] = round(samples[i] * (i + 1) / ramp)
                        fade_in = False
                    chunks.append(samples)
                for samples in chunks:
                    if samples:
                        last_sample = samples[-1]
                    pcm = samples.tobytes()
                    # Native turn boundaries protect soft phonemes. Idle Opus
                    # comfort noise must not continually duck customer speech.
                    threshold = 4 if self.assistant_speaking else 64
                    audible = any(abs(value) > threshold for value in samples)
                    now = time.monotonic()
                    onset.append(pcm)
                    if audible:
                        last_speech = now
                    # A breath/thinking pause is still part of the assistant's
                    # media timeline. Removing it starves browser playback and
                    # toggles speaking/listening mid-sentence. Only gate idle RTP.
                    if self.continuous or self.assistant_speaking or now - last_speech < 0.25:
                        for data in onset:
                            # Media uses backpressure directly: dropping an old
                            # packet here removes phonemes and creates clicks.
                            sending = time.monotonic()
                            await self.on_event(
                                "thread/realtime/outputAudio/delta",
                                {
                                    "threadId": self.thread,
                                    "audio": {
                                        "data": base64.b64encode(data).decode("ascii"),
                                        "sampleRate": 48000,
                                        "numChannels": 1,
                                    },
                                },
                            )
                            metrics = self.output_buffer.metrics
                            metrics["max_send_ms"] = max(
                                metrics["max_send_ms"], round((time.monotonic() - sending) * 1000)
                            )
                        onset.clear()
        except (MediaStreamError, asyncio.CancelledError):
            pass
        except Exception:
            self.offer("thread/realtime/error", {})

    def prefer_default_route(self):
        # aioice has no interface setting in RTCConfiguration. Scope this
        # candidate-gathering hook to this peer; never change global interfaces.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
                route.connect(("1.1.1.1", 443))  # route lookup; sends no packet
                address = route.getsockname()[0]
        except OSError:
            return
        transports = {self.peer.sctp.transport.transport}
        transports.update(t.receiver.transport.transport for t in self.peer.getTransceivers())
        for transport in transports:
            connection = transport.iceGatherer._connection
            original = connection.get_component_candidates

            async def gather(component, addresses, timeout=5, original=original):
                selected = [address] if address in addresses else addresses
                return await original(component, selected, timeout)

            connection.get_component_candidates = gather

    async def start(self):
        self.prefer_default_route()
        await self.peer.setLocalDescription(await self.peer.createOffer())
        answer = await self.native.start_voice(self.thread, self.peer.localDescription.sdp)
        await self.peer.setRemoteDescription(RTCSessionDescription(answer, "answer"))
        await asyncio.wait_for(self.ready, 25)

    def push(self, pcm):
        self.track.push(pcm)

    async def close(self):
        self.closed = True
        if not self.ready.done():
            self.ready.cancel()
        self.track.stop()
        if self.capture is not None:
            self.capture.close()
        if self.channel.readyState == "open":
            with contextlib.suppress(Exception):
                self.channel.send(json.dumps({"type": "session.close"}))
        for task in list(self.connect_tasks):
            task.cancel()
        await asyncio.gather(*self.connect_tasks, return_exceptions=True)
        # aioice 0.10.2 can leave connectivity-check transactions alive when
        # negotiation is cancelled. Their timers must stop before UDP closes.
        transports = {self.peer.sctp.transport.transport}
        transports.update(t.receiver.transport.transport for t in self.peer.getTransceivers())
        checks = {
            pair.task
            for transport in transports
            for pair in transport.iceGatherer._connection._check_list
            if pair.task is not None and not pair.task.done()
        }
        for task in checks:
            task.cancel()
        await asyncio.gather(*checks, return_exceptions=True)
        await self.peer.close()
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
