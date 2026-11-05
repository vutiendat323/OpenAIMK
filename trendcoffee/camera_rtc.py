"""The guest's own camera (device mode) over WebRTC.

The browser sends its camera as a WebRTC video track instead of JPEG packets on the
kiosk socket. The API decodes the track (aiortc), keeps at most 15 frames per second
and encodes each kept frame as a 640x480 JPEG, so Visual receives exactly what the
socket path delivered before and its interface does not change.
"""

import asyncio
import contextlib
import time
from fractions import Fraction

import av
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError

WIDTH, HEIGHT = 640, 480
MAX_FPS = 15
# Keep a frame when at least this long has passed since the last kept frame; the
# small margin keeps a 15 fps camera at 15 fps despite timing jitter.
MIN_INTERVAL = 1 / MAX_FPS - 0.005
JPEG_QSCALE = 5  # fixed quality (lower is better); ~0.7 ms per 640x480 frame
MAX_JPEG_BYTES = 256000  # the kiosk camera path accepts at most this size
RECEIVING_WINDOW = 1.0  # seconds without a frame before the socket fallback resumes


class CameraPeer:
    """One browser connection that sends the guest's camera."""

    def __init__(self, on_jpeg, clock=time.monotonic):
        self.on_jpeg = on_jpeg
        self.clock = clock
        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self.reader = None
        self.encoder = None
        self.last_frame_at = None
        self.last_kept_at = None
        self.metrics = {
            "frames": 0,
            "forwarded": 0,
            "send_errors": 0,
            "oversize": 0,
            "max_gap_ms": 0,
        }

        @self.pc.on("track")
        def on_track(track):
            if track.kind == "video" and self.reader is None:
                self.reader = asyncio.create_task(self.read(track))

    async def answer(self, sdp):
        await self.pc.setRemoteDescription(RTCSessionDescription(sdp, "offer"))
        if not any(t.kind == "video" for t in self.pc.getTransceivers()):
            raise ValueError("camera_offer_without_video")
        await self.pc.setLocalDescription(await self.pc.createAnswer())
        if not any(
            t.kind == "video" and t.currentDirection in ("recvonly", "sendrecv")
            for t in self.pc.getTransceivers()
        ):
            raise ValueError("camera_offer_not_receivable")
        return self.pc.localDescription.sdp

    @property
    def connected(self):
        return self.pc.connectionState == "connected"

    def receiving(self):
        """True while video frames keep arriving; the socket JPEG path then stays idle."""
        return (
            self.last_frame_at is not None and self.clock() - self.last_frame_at < RECEIVING_WINDOW
        )

    def encode(self, frame):
        if self.encoder is None:
            encoder = av.CodecContext.create("mjpeg", "w")
            encoder.width, encoder.height, encoder.pix_fmt = WIDTH, HEIGHT, "yuvj420p"
            encoder.time_base = Fraction(1, MAX_FPS)
            encoder.qmin = encoder.qmax = JPEG_QSCALE
            self.encoder = encoder
        image = frame.reformat(format="yuvj420p", width=WIDTH, height=HEIGHT)
        return b"".join(bytes(packet) for packet in self.encoder.encode(image))

    async def read(self, track):
        metrics = self.metrics
        with contextlib.suppress(MediaStreamError):
            while True:
                frame = await track.recv()
                now = self.clock()
                metrics["frames"] += 1
                if self.last_frame_at is not None:
                    gap = round((now - self.last_frame_at) * 1000, 1)
                    metrics["max_gap_ms"] = max(metrics["max_gap_ms"], gap)
                self.last_frame_at = now
                if self.last_kept_at is not None and now - self.last_kept_at < MIN_INTERVAL:
                    continue
                self.last_kept_at = now
                jpeg = await asyncio.to_thread(self.encode, frame)
                if len(jpeg) > MAX_JPEG_BYTES:
                    metrics["oversize"] += 1
                    continue
                try:
                    await self.on_jpeg(jpeg)
                except Exception:
                    # Visual may be reconnecting; the next frame tries again.
                    metrics["send_errors"] += 1
                    continue
                metrics["forwarded"] += 1

    async def close(self):
        if self.reader is not None:
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
            self.reader = None
        await self.pc.close()
