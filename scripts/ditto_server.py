"""Local, single-peer WebRTC transport for the warmed Ditto engine."""

import argparse
import asyncio
import sys
import uuid
from collections import deque
from fractions import Fraction
from pathlib import Path

import numpy as np
from aiohttp import web
from aiortc import (
    MediaStreamTrack,
    RTCBundlePolicy,
    RTCConfiguration,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame, VideoFrame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trendcoffee.avatar_pcm import AvatarPCMStream


class ClockTrack(MediaStreamTrack):
    def __init__(self, session, kind, rate):
        super().__init__()
        self.session, self.kind, self.rate = session, kind, rate
        self.started = None
        self.tick = 0

    async def pace(self):
        if self.readyState != "live":
            raise MediaStreamError
        loop = asyncio.get_running_loop()
        if self.started is None:
            self.started = loop.time()
        # Skip expired clock slots instead of bursting stale RTP after a stall.
        elapsed_tick = int((loop.time() - self.started) * self.rate)
        skipped = max(0, elapsed_tick - self.tick)
        self.tick += skipped
        await asyncio.sleep(max(0, self.started + self.tick / self.rate - loop.time()))
        if self.readyState != "live":
            raise MediaStreamError
        self.tick += 1
        return skipped


class AudioTrack(ClockTrack):
    def __init__(self, session):
        super().__init__(session, "audio", 50)

    async def recv(self):
        skipped = await self.pace()
        for _ in range(min(skipped, len(self.session.audio_queue))):
            self.session.audio_queue.popleft()
        raw = self.session.audio_queue.popleft() if self.session.audio_queue else bytes(1920)
        frame = AudioFrame(format="s16", layout="mono", samples=960)
        frame.planes[0].update(raw)
        frame.sample_rate, frame.time_base = 48000, Fraction(1, 48000)
        frame.pts = (self.tick - 1) * 960
        return frame


class VideoTrack(ClockTrack):
    def __init__(self, session):
        super().__init__(
            session, "video", getattr(session.transport.engine, "PRESENTATION_FPS", 24)
        )

    async def recv(self):
        await self.pace()
        while self.readyState == "live":
            latest = self.session.transport.engine.latest_frame()
            if latest is not None and latest[0] == self.session.generation:
                frame = VideoFrame.from_ndarray(latest[1], format="rgb24")
                frame.pts, frame.time_base = (
                    round((self.tick - 1) * 90000 / self.rate),
                    Fraction(1, 90000),
                )
                return frame
            await asyncio.sleep(0.01)
        raise MediaStreamError


class Session:
    def __init__(self, transport):
        self.transport = transport
        self.sid = uuid.uuid4().hex
        self.pc = RTCPeerConnection(
            RTCConfiguration(iceServers=[], bundlePolicy=RTCBundlePolicy.MAX_BUNDLE)
        )
        self.epoch = 0
        self.generation = transport.next_generation()
        self.audio_queue = deque()
        self.converter = AvatarPCMStream(preserve_original=False)
        self.fmt = None
        self.pcm_lock = asyncio.Lock()
        self.audio, self.video = None, VideoTrack(self)
        transport.engine.reset(self.generation)


class DittoTransport:
    def __init__(self, engine):
        self.engine, self.session = engine, None
        self.generation = 0
        self.offer_lock = asyncio.Lock()

    def next_generation(self):
        self.generation += 1
        return self.generation

    def lookup(self, sid):
        if self.session is None or self.session.sid != sid:
            raise web.HTTPNotFound()
        return self.session

    async def retire(self, session):
        if self.session is session:
            self.session = None
            self.engine.reset(self.next_generation())
        session.audio_queue.clear()
        if session.audio is not None:
            session.audio.stop()
        session.video.stop()
        await session.pc.close()

    async def offer(self, request):
        data = await object_json(request)
        if (
            data.get("type") != "offer"
            or not isinstance(data.get("sdp"), str)
            or not 1 <= len(data["sdp"]) <= 100000
        ):
            raise web.HTTPBadRequest()
        async with self.offer_lock:
            if self.session is not None:
                raise web.HTTPConflict()
            session = Session(self)
            self.session = session
            try:
                await session.pc.setRemoteDescription(RTCSessionDescription(data["sdp"], "offer"))
                kinds = {t.kind for t in session.pc.getTransceivers()}
                if "video" not in kinds:
                    raise ValueError("video required")
                if "audio" in kinds:
                    session.audio = AudioTrack(session)
                    session.pc.addTrack(session.audio)
                session.pc.addTrack(session.video)
                await session.pc.setLocalDescription(await session.pc.createAnswer())
                sending = {"sendonly", "sendrecv"}
                if not any(
                    t.kind == "video" and t.currentDirection in sending
                    for t in session.pc.getTransceivers()
                ):
                    raise ValueError("receivable video required")
                if session.audio is not None and not any(
                    t.sender.track is session.audio and t.currentDirection in sending
                    for t in session.pc.getTransceivers()
                ):
                    session.audio.stop()
                    session.audio = None
                session.converter = AvatarPCMStream(preserve_original=session.audio is not None)
            except Exception as error:
                await self.retire(session)
                raise web.HTTPBadRequest(reason="invalid offer") from error

            @session.pc.on("connectionstatechange")
            async def connection_changed():
                if session.pc.connectionState in ("failed", "closed") and self.session is session:
                    await self.retire(session)

            description = session.pc.localDescription
            return web.json_response(
                {"sdp": description.sdp, "type": description.type, "sessionid": session.sid}
            )

    async def reset(self, request):
        data = await object_json(request)
        session = self.lookup(data.get("sessionid"))
        epoch = data.get("epoch")
        if type(epoch) is not int or epoch <= session.epoch:
            raise web.HTTPBadRequest()
        session.epoch = epoch
        session.generation = self.next_generation()
        session.audio_queue.clear()
        session.converter = AvatarPCMStream(preserve_original=session.audio is not None)
        session.fmt = None
        self.engine.reset(session.generation)
        return web.json_response({"code": 0})

    async def pcm(self, request):
        session = self.lookup(request.headers.get("X-Session-ID"))
        try:
            epoch, rate, channels = (
                int(request.headers[key]) for key in ("X-Epoch", "X-Sample-Rate", "X-Channels")
            )
        except (KeyError, ValueError) as error:
            raise web.HTTPBadRequest() from error
        if rate not in range(8000, 96001) or channels not in (1, 2):
            raise web.HTTPBadRequest()
        raw = await request.read()
        if not raw or len(raw) % (channels * 2) or len(raw) > rate * channels * 2 // 5:
            raise web.HTTPBadRequest()
        async with session.pcm_lock:
            generation = session.generation

            def check():
                if (
                    self.session is not session
                    or epoch <= 0
                    or session.epoch != epoch
                    or session.generation != generation
                ):
                    raise web.HTTPConflict()

            check()
            if session.fmt is not None and session.fmt != (rate, channels):
                raise web.HTTPBadRequest(reason="format changed without reset")
            session.fmt = (rate, channels)
            frames = session.converter.push(raw, rate, channels)
            deadline = asyncio.get_running_loop().time() + 2
            while session.audio is not None and len(session.audio_queue) + len(frames) > 25:
                if asyncio.get_running_loop().time() >= deadline:
                    raise web.HTTPServiceUnavailable(reason="avatar audio backlog")
                await asyncio.sleep(0.01)
                check()
            check()
            for model, original in frames:
                self.engine.push(
                    generation, np.frombuffer(model, dtype="<i2").astype(np.float32) / 32768
                )
                if session.audio is not None:
                    session.audio_queue.append(original)
        return web.json_response({"code": 0})

    async def close(self, request):
        data = await object_json(request)
        session = self.lookup(data.get("sessionid"))
        await self.retire(session)
        return web.json_response({"code": 0})

    async def action(self, request):
        data = await object_json(request)
        self.lookup(data.get("sessionid"))
        kind = data.get("audiotype")
        if type(kind) is not int or kind not in (1, 2, 3):
            raise web.HTTPBadRequest()
        if not self.engine.action({1: "idle", 2: "wave", 3: "smile"}[kind]):
            raise web.HTTPConflict(reason="action unavailable")
        return web.json_response({"code": 0})

    async def health(self, request):
        status = self.engine.status
        status = status() if callable(status) else status
        return web.json_response(
            {
                **status,
                "model": "ditto",
                "poster": "/avatars/trend-live.png",
                "video_fps": getattr(self.engine, "PRESENTATION_FPS", 24),
                "video_only": True,
            }
        )

    async def shutdown(self, app):
        if self.session:
            await self.retire(self.session)
        await asyncio.to_thread(self.engine.close)


async def object_json(request):
    try:
        data = await request.json()
    except (ValueError, UnicodeDecodeError) as error:
        raise web.HTTPBadRequest() from error
    if not isinstance(data, dict):
        raise web.HTTPBadRequest()
    return data


def create_app(transport):
    app = web.Application(client_max_size=100000)
    app.router.add_post("/offer", transport.offer)
    for path, handler in (
        ("reset", transport.reset),
        ("pcm", transport.pcm),
        ("close", transport.close),
    ):
        app.router.add_post("/trend/" + path, handler)
    app.router.add_get("/trend/health", transport.health)
    app.router.add_post("/set_audiotype", transport.action)
    app.on_cleanup.append(transport.shutdown)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--render-fps", type=float, help="Neural mouth render target, 6..24")
    parser.add_argument("--motion-stride-ms", type=int, choices=(80, 120, 160, 200))
    parser.add_argument(
        "--renderer-backend", choices=("pytorch", "tensorrt", "tensorrt-mouth"), default="pytorch"
    )
    parser.add_argument(
        "--expression-mode", choices=("absolute", "source-relative"), default="source-relative"
    )
    parser.add_argument(
        "--lip-opening-limit",
        type=float,
        default=0.0,
        help="Soft limit on vertical lip displacement in keypoint units; zero disables",
    )
    parser.add_argument(
        "--presentation-lead-ms",
        type=float,
        help="How far behind received audio poses are shown; must exceed the motion stride",
    )
    parser.add_argument(
        "--closed-source",
        action="store_true",
        help="The source clip was rebuilt with a closed mouth on every frame",
    )
    parser.add_argument(
        "--plain-ditto",
        action="store_true",
        help="Trial: upstream relative drive and source smoothing, no kiosk mouth layers",
    )
    parser.add_argument("--lip-factor", type=float, help="Trial: vertical lip compression")
    parser.add_argument(
        "--no-wave",
        action="store_true",
        help="Do not load the waving clip; only the source clip is ever shown",
    )
    parser.add_argument(
        "--whole-head",
        action="store_true",
        help="Paste the whole generated head (hair, ears, neck edge) like upstream, not only the face oval",
    )
    parser.add_argument(
        "--lip-width", type=float, help="Share of sideways/forward lip motion kept (pursing)"
    )
    parser.add_argument(
        "--turn-gain",
        type=float,
        help="With --drive-head: share of yaw/pitch used, so the gaze stays on the camera",
    )
    parser.add_argument(
        "--head-gain", type=float, help="With --drive-head: share of the model's head motion used"
    )
    parser.add_argument(
        "--rest-source", type=Path, help="Clip shown, without the GPU, while Trend is not speaking"
    )
    parser.add_argument(
        "--reference-frame",
        type=int,
        help="Real closed mouth donor at frame zero; each video frame keeps its own full-face features",
    )
    parser.add_argument(
        "--drive-head",
        action="store_true",
        help="Trial: audio also drives head pose, added to the clip's own",
    )
    parser.add_argument(
        "--ditto-silence",
        action="store_true",
        help="Trial: keep generating faces through silence until the guest ends",
    )
    parser.add_argument(
        "--composite",
        choices=("mouth", "full-face"),
        default="mouth",
        help="Generated pixels shown: the lips only, or the whole face on its own source frame",
    )
    parser.add_argument(
        "--gpu-budget", type=float, help="Fraction of engine work time, 0 < value <= 1"
    )
    args = parser.parse_args()
    from scripts.ditto_realtime import DittoEngine
    from scripts.livetalking_local import configure_local_video

    configure_local_video()
    engine = DittoEngine(
        source_path=args.source.resolve(),
        root=Path(__file__).resolve().parent.parent,
        gpu_budget=args.gpu_budget,
        render_fps=args.render_fps,
        motion_stride_ms=args.motion_stride_ms,
        renderer_backend=args.renderer_backend,
        expression_mode=args.expression_mode,
        lip_opening_limit=args.lip_opening_limit,
        composite=args.composite,
        closed_source=args.closed_source,
        plain_ditto=args.plain_ditto,
        lip_factor=args.lip_factor,
        lip_width=args.lip_width,
        whole_head=args.whole_head,
        wave=not args.no_wave,
        drive_head=args.drive_head,
        ditto_silence=args.ditto_silence,
        reference_frame=args.reference_frame,
        rest_source=args.rest_source.resolve() if args.rest_source else None,
        head_gain=args.head_gain,
        turn_gain=args.turn_gain,
        presentation_lead_ms=args.presentation_lead_ms,
    )
    # Warm up before binding the service; no GPU work runs on the asyncio loop.
    engine.start()
    web.run_app(create_app(DittoTransport(engine)), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
