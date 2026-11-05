"""Trend's speech to the kiosk browser over WebRTC.

Native delivers speech slightly slower than real time and sometimes stalls. Passing
that timing to the browser makes its low-latency jitter buffer (NetEQ) stretch and
conceal inside words. Instead, the API holds about half a second at the start of a
reply and sends to the browser on a steady 20 ms clock with contiguous timestamps.
The buffer is corrected only inside pauses (quiet frames are dropped or added);
speech frames are never changed or skipped.
"""

import asyncio
import os
import time
import wave
from array import array
from collections import deque
from fractions import Fraction
from pathlib import Path

from aiortc import AudioStreamTrack, RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame

RATE = 48000
FRAME_SAMPLES = 960  # 20 ms
FRAME_BYTES = FRAME_SAMPLES * 2
FRAME_MS = 20
TARGET_MS = 500  # speech held before a reply starts; absorbs native's slow delivery
REBUFFER_MS = 200  # after native stalls inside speech
BAND_MS = 100  # the buffer may drift this far from the target before a pause corrects it
PREROLL_FRAMES = 5  # quiet frames kept in front of a word while waiting to start
PAUSE_FRAMES = 3  # a correction needs at least 60 ms of continuous quiet
IDLE_AFTER = 0.5  # this long with nothing to send restarts with the full target
STOP_AFTER = 0.4  # this long without audible speech ends playback for Fusion and the screen
AUDIBLE = 64  # 16-bit sample level above native's idle comfort noise
MAX_QUEUE_FRAMES = 30 * RATE // FRAME_SAMPLES
SILENCE = bytes(FRAME_BYTES)


class SpeechCapture:
    """Opt-in WAV of Trend's own speech, never the guest's, for diagnosing sound quality."""

    def __init__(self, path, max_seconds=300):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.wav = wave.open(str(path), "wb")
        self.wav.setnchannels(1)
        self.wav.setsampwidth(2)
        self.wav.setframerate(RATE)
        self.room = int(max_seconds * RATE) * 2
        self.timing = open(Path(path).with_suffix(".csv"), "w")  # noqa: SIM115

    def log(self, *values):
        """One line of numbers per frame (time, then stage-specific values)."""
        if self.timing is not None and self.room > 0:
            self.timing.write(f"{values[0]:.6f}," + ",".join(str(v) for v in values[1:]) + "\n")

    def write(self, pcm):
        if self.wav is None or self.room <= 0:
            return
        chunk = bytes(pcm[: self.room])
        self.room -= len(chunk)
        self.wav.writeframes(chunk)

    def close(self):
        if self.wav is not None:
            self.wav.close()
            self.wav = None
        if self.timing is not None:
            self.timing.close()
            self.timing = None


def speech_capture(stage):
    """A capture for this stage when TREND_SPEECH_CAPTURE_DIR is set, otherwise None."""
    folder = os.environ.get("TREND_SPEECH_CAPTURE_DIR")
    if not folder:
        return None
    return SpeechCapture(Path(folder) / f"{stage}-{time.strftime('%Y%m%d-%H%M%S')}.wav")


def audible(pcm):
    samples = array("h", pcm)
    return max(samples) > AUDIBLE or -min(samples) > AUDIBLE


class SpeakerTrack(AudioStreamTrack):
    """48 kHz mono speech for the browser on a steady 20 ms clock."""

    def __init__(self, on_playing, capture=None, clock=time.monotonic, sleep=asyncio.sleep):
        super().__init__()
        self.on_playing = on_playing
        self.capture = capture
        self.clock, self.sleep = clock, sleep
        self.frames = deque()  # (pcm, audible)
        self.suspended = False
        self.primed = False
        self.need_ms = TARGET_MS
        self.word_waiting_since = None
        self.empty_since = None
        self.starved_at = None  # speech ran out mid-word; an underrun if speech returns
        self.quiet_run = 0
        self.origin = None
        self.sent = 0
        self.playing = False
        self.quiet_timer = None
        self.metrics = {
            "underruns": 0,
            "dropped_quiet": 0,
            "added_quiet": 0,
            "max_queue_ms": 0,
            "overflow": 0,
            # Trend's audio that arrived after a guest turn stopped the reply and before the
            # next reply began; it is never played. Nonzero inside a reply = lost speech.
            "ignored_suspended_ms": 0,
        }

    def buffered_ms(self):
        return len(self.frames) * FRAME_MS

    def push(self, pcm):
        if self.suspended and pcm:
            self.metrics["ignored_suspended_ms"] += len(pcm) * FRAME_MS // FRAME_BYTES
        if self.suspended or self.readyState != "live" or not pcm or len(pcm) % 2:
            return
        count = -(-len(pcm) // FRAME_BYTES)
        if len(self.frames) + count > MAX_QUEUE_FRAMES:
            self.metrics["overflow"] += 1
            return
        for start in range(0, len(pcm), FRAME_BYTES):
            # Only a clip's last frame can be short; it ends in silence.
            frame = bytes(pcm[start : start + FRAME_BYTES]).ljust(FRAME_BYTES, b"\0")
            self.frames.append((frame, audible(frame)))
        self.metrics["max_queue_ms"] = max(self.metrics["max_queue_ms"], self.buffered_ms())

    def _drop(self):
        self.frames.clear()
        self.primed, self.need_ms = False, TARGET_MS
        self.word_waiting_since = self.empty_since = self.starved_at = None
        if self.quiet_timer is not None:
            self.quiet_timer.cancel()
            self.quiet_timer = None
        if self.playing:
            self.playing = False
            self.on_playing(False)

    def interrupt(self):
        """The guest started speaking: drop the reply that is still queued."""
        self.suspended = True
        self._drop()

    def resume(self):
        self.suspended = False

    def clear(self):
        """A new guest: no audio or suspension carries over."""
        self.suspended = False
        self._drop()

    def _quiet(self):
        self.quiet_timer = None
        if self.playing:
            self.playing = False
            self.on_playing(False)

    def _report(self, pcm, loud):
        # Playback for Fusion and the screen follows audible speech. Native also
        # sends quiet frames between phrases, which must not duck the microphone.
        if not loud:
            return
        if not self.playing:
            self.playing = True
            self.on_playing(True)
        if self.quiet_timer is not None:
            self.quiet_timer.cancel()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self.quiet_timer = loop.call_later(STOP_AFTER, self._quiet)

    def _wait_for_speech(self, now):
        """Not playing yet: keep only a short preroll of quiet, hold the next words."""
        first_word = next((i for i, (_, loud) in enumerate(self.frames) if loud), None)
        if first_word is None:
            while len(self.frames) > PREROLL_FRAMES:
                self.frames.popleft()
            self.word_waiting_since = None
            return False
        while first_word > PREROLL_FRAMES:
            self.frames.popleft()
            first_word -= 1
        if self.word_waiting_since is None:
            self.word_waiting_since = now
        if (
            self.buffered_ms() <= self.need_ms
            and now - self.word_waiting_since < self.need_ms / 1000
        ):
            return False
        self.primed, self.word_waiting_since = True, None
        if self.starved_at is not None and now - self.starved_at < 3.0:
            self.metrics["underruns"] += 1
        self.starved_at = None
        return True

    def next_frame(self, now):
        frame, loud = self._next(now)
        self._report(frame, loud)
        if self.capture is not None:
            self.capture.log(now, self.buffered_ms(), int(self.primed))
            self.capture.write(frame)
        return frame

    def _next(self, now):
        if not self.primed and not self._wait_for_speech(now):
            return SILENCE, False
        if not self.frames:
            # Native did not deliver in time: an unavoidable gap, then a short rebuffer.
            if self.empty_since is None:
                self.empty_since = now
                if self.quiet_run < PAUSE_FRAMES:
                    self.starved_at = now
                    self.primed, self.need_ms = False, REBUFFER_MS
            if now - self.empty_since >= IDLE_AFTER:
                self.primed, self.need_ms = False, TARGET_MS
            self.quiet_run += 1
            return SILENCE, False
        self.empty_since = None
        pcm, loud = self.frames[0]
        if not loud and self.quiet_run >= PAUSE_FRAMES:
            if self.buffered_ms() > TARGET_MS + BAND_MS and len(self.frames) > 1:
                self.frames.popleft()  # shorten the pause by one frame
                self.metrics["dropped_quiet"] += 1
                pcm, loud = self.frames[0]
            elif self.buffered_ms() < TARGET_MS - BAND_MS:
                self.metrics["added_quiet"] += 1  # lengthen the pause by one frame
                self.quiet_run += 1
                return SILENCE, False
        self.frames.popleft()
        self.quiet_run = 0 if loud else self.quiet_run + 1
        return pcm, loud

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError
        if self.origin is None:
            self.origin = self.clock()
        deadline = self.origin + self.sent / RATE
        await self.sleep(max(0, deadline - self.clock()))
        now = self.clock()
        if now - deadline > 0.2:
            # A scheduler stall must not make the sender burst old frames.
            self.origin = now - self.sent / RATE
        frame = AudioFrame(format="s16", layout="mono", samples=FRAME_SAMPLES)
        frame.planes[0].update(self.next_frame(now))
        frame.sample_rate = RATE
        frame.pts, frame.time_base = self.sent, Fraction(1, RATE)
        self.sent += FRAME_SAMPLES
        return frame

    def stop(self):
        self.frames.clear()
        if self.quiet_timer is not None:
            self.quiet_timer.cancel()
            self.quiet_timer = None
        if self.capture is not None:
            self.capture.close()
        super().stop()


class SpeakerPeer:
    """One browser connection that receives Trend's speech."""

    def __init__(self, on_playing):
        self.track = SpeakerTrack(on_playing, capture=speech_capture("speaker"))
        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))

    async def answer(self, sdp):
        await self.pc.setRemoteDescription(RTCSessionDescription(sdp, "offer"))
        if not any(t.kind == "audio" for t in self.pc.getTransceivers()):
            raise ValueError("speaker_offer_without_audio")
        self.pc.addTrack(self.track)
        await self.pc.setLocalDescription(await self.pc.createAnswer())
        if not any(
            t.sender.track is self.track and t.currentDirection in ("sendonly", "sendrecv")
            for t in self.pc.getTransceivers()
        ):
            raise ValueError("speaker_offer_not_receivable")
        return self.pc.localDescription.sdp

    @property
    def connected(self):
        return self.pc.connectionState == "connected"

    def push(self, pcm):
        self.track.push(pcm)

    def interrupt(self):
        self.track.interrupt()

    def buffered_ms(self):
        return self.track.buffered_ms()

    def resume(self):
        self.track.resume()

    def clear(self):
        self.track.clear()

    @property
    def metrics(self):
        return self.track.metrics

    async def close(self):
        self.track.stop()
        await self.pc.close()
