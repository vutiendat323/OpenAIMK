"""The guest's own camera (device mode) over WebRTC.

The browser sends its camera as a WebRTC video track instead of JPEG packets on the
kiosk socket. The API decodes the track (aiortc), keeps at most 15 frames per second
(Visual analyses at most 15) and encodes each kept frame as a 640x480 JPEG, so Visual's
interface does not change. 30 fps (2026-11-05) made every connection's video stop after
about one second, so the device camera stays at 15.
"""

import asyncio
import logging
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
# A connection that stays up while its video stops (2026-11-05: 34 frames, then none for
# minutes) is dropped after this long; the browser then reconnects it, socket JPEGs meanwhile.
STALL_SECONDS = 2.0


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
        self.track_at = None  # when the video track began to be read
        self.metrics = {
            "frames": 0,
            "forwarded": 0,
            "send_errors": 0,
            "oversize": 0,
            "max_gap_ms": 0,
        }

        @self.pc.on("connectionstatechange")
        def on_state():
            # Evidence for a camera that stops after a few frames (2026-11-05).
            self.metrics["state"] = self.pc.connectionState
            if self.pc.connectionState in ("failed", "closed", "disconnected"):
                logging.getLogger(__name__).warning(
                    "Device camera connection %s at %s after %s frames",
                    self.pc.connectionState,
                    time.strftime("%H:%M:%S"),
                    self.metrics["frames"],
                )

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

    def stalled(self, now):
        """True when this connection's video gave no frame for STALL_SECONDS.

        That includes a track that ended (2026-11-05: it ended after 34 frames each time
        while the page still counted the connection as up, so no camera reached Visual)."""
        since = self.last_frame_at if self.last_frame_at is not None else self.track_at
        return self.reader is not None and since is not None and now - since > STALL_SECONDS

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
        self.track_at = self.clock()
        try:
            await self._read(track, metrics)
        except MediaStreamError:
            metrics["track_ended"] = True
            logging.getLogger(__name__).warning(
                "Device camera track ended at %s after %s frames (connection %s)",
                time.strftime("%H:%M:%S"),
                metrics["frames"],
                self.pc.connectionState,
            )

    async def _read(self, track, metrics):
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
