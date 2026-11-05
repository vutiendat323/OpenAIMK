"""Run from a prepared LiveTalking checkout with its own Python environment.

Usage: <LiveTalking python> /absolute/path/scripts/livetalking_local.py [upstream flags]
Only PCM, SDP and action endpoints are exposed. No TTS/LLM/cloud path is registered.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


def configure_local_video():
    from aiortc.codecs import h264, vpx

    # aiortc's default VP8 rate is 500kbps (max 1.5Mbps), which visibly
    # blocks moving faces in the 720x1280 kiosk stream. This process only
    # serves the local avatar; native voice runs in the separate API process.
    for codec in (vpx, h264):
        codec.MIN_BITRATE = 1_500_000
        codec.DEFAULT_BITRATE = 3_000_000
        codec.MAX_BITRATE = 6_000_000


def configure_avatar(opt, manifest):
    if not manifest:
        return
    engine = manifest.get("engine", "wav2lip")
    batch = manifest.get("batch_size", opt.batch_size)
    if engine not in ("wav2lip", "musetalk") or type(batch) is not int or not 1 <= batch <= 16:
        raise ValueError("invalid_avatar_engine")
    opt.model, opt.batch_size = engine, batch
    opt.avatar_id = manifest["avatar_id"]
    opt.customopt = []


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    parser.add_argument("--motion-config", type=Path)
    wrapper, remaining = parser.parse_known_args()
    manifest = json.loads(wrapper.motion_config.read_text()) if wrapper.motion_config else None
    checkout = wrapper.checkout.resolve()
    os.chdir(checkout)
    sys.path.insert(0, str(checkout))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    sys.argv = [sys.argv[0], *remaining]
    os.environ.setdefault(
        "TORCHINDUCTOR_CACHE_DIR",
        str(Path(__file__).resolve().parent.parent / ".runtime/torchinductor"),
    )
    configure_local_video()
    import app as upstream
    import config
    import numpy as np
    import registry
    from aiohttp import web
    from server.rtc_manager import RTCManager
    from server.session_manager import session_manager

    from trendcoffee.avatar_pcm import AvatarPCMStream

    if manifest and manifest.get("engine") == "musetalk":
        from avatars import musetalk_avatar
        from livetalking_muse import load_model, warm_up

        musetalk_avatar.load_model = lambda: load_model(manifest)
        musetalk_avatar.warm_up = warm_up

    original_parse = config.parse_args
    original_create = registry.create
    original_site = web.TCPSite
    streams = {}
    connections = {}
    offer_lock = asyncio.Lock()
    original_offer = RTCManager.handle_offer
    original_answer = RTCManager._create_pc_and_answer

    async def offer(manager, request):
        # Upstream counts built sessions, not placeholders; serialize admission.
        async with offer_lock:
            return await original_offer(manager, request)

    async def answer(manager, avatar, sid, description):
        before = set(manager.pcs)
        try:
            pc = await original_answer(manager, avatar, sid, description)
            if hasattr(avatar, "install_audio_clock"):
                avatar.install_audio_clock()
        except BaseException:
            for peer in manager.pcs - before:
                await peer.close()
                manager.pcs.discard(peer)
            session_manager.remove_session(sid)
            raise
        connections[sid] = pc

        @pc.on("connectionstatechange")
        async def closed():
            if pc.connectionState in ("closed", "failed"):
                connections.pop(sid, None)
                streams.pop(sid, None)

        return pc

    class NoTTS:
        def render(self, quit_event):
            pass

        def flush_talk(self):
            pass

    def create(category, name, **kwargs):
        if category == "tts":
            return NoTTS()
        if category == "avatar" and manifest:
            if name == "wav2lip":
                from livetalking_motion import MotionAvatar

                return MotionAvatar(manifest=manifest, **kwargs)
            if name == "musetalk":
                from livetalking_muse import MuseTalkMotionAvatar

                return MuseTalkMotionAvatar(manifest=manifest, **kwargs)
        return original_create(category, name, **kwargs)

    def parse():
        opt = original_parse()
        opt.stun = ""
        opt.max_session = 1
        opt.transport = "webrtc"
        configure_avatar(opt, manifest)
        return opt

    def site(runner, host, port, **kwargs):
        return original_site(runner, "127.0.0.1", port, **kwargs)

    def session(sid):
        avatar = session_manager.get_session(sid)
        if avatar is None:
            raise web.HTTPNotFound()
        return avatar

    async def reset(request):
        data = await request.json()
        sid, epoch = data["sessionid"], data["epoch"]
        avatar = session(sid)
        old = streams.get(sid)
        if type(epoch) is not int or epoch <= (old[0] if old else 0):
            raise web.HTTPBadRequest()
        if hasattr(avatar, "reset_motion"):
            avatar.reset_motion(epoch)
        else:
            avatar.flush_talk()
        streams[sid] = (epoch, AvatarPCMStream(), None)
        return web.json_response({"code": 0})

    async def pcm(request):
        sid = request.headers.get("X-Session-ID", "")
        avatar = session(sid)
        try:
            epoch = int(request.headers["X-Epoch"])
            rate = int(request.headers["X-Sample-Rate"])
            channels = int(request.headers["X-Channels"])
        except (ValueError, KeyError) as error:
            raise web.HTTPBadRequest() from error
        if rate not in range(8000, 96001) or channels not in (1, 2):
            raise web.HTTPBadRequest()
        current, converter, fmt = streams.get(sid, (0, None, None))
        if current != epoch:
            raise web.HTTPConflict()
        raw = await request.read()
        if not raw or len(raw) % (channels * 2) or len(raw) > rate * channels * 2 // 5:
            raise web.HTTPBadRequest()
        if fmt is not None and fmt != (rate, channels):
            raise web.HTTPBadRequest(reason="format changed without reset")
        frames = converter.push(raw, rate, channels)
        deadline = asyncio.get_running_loop().time() + 2
        while avatar.asr.queue.qsize() + len(frames) > 25:
            if asyncio.get_running_loop().time() >= deadline:
                raise web.HTTPServiceUnavailable(reason="avatar audio backlog")
            await asyncio.sleep(0.01)
            if streams.get(sid, (None,))[0] != epoch:
                raise web.HTTPConflict()
        for model, original in frames:
            avatar.put_audio_frame(
                np.frombuffer(model, dtype="<i2").astype(np.float32) / 32768,
                {"epoch": epoch, "pcm48": original},
            )
        streams[sid] = (epoch, converter, (rate, channels))
        return web.json_response({"code": 0})

    async def close(request):
        sid = (await request.json())["sessionid"]
        pc = connections.pop(sid, None)
        if pc is not None:
            await pc.close()
        streams.pop(sid, None)
        session_manager.remove_session(sid)
        return web.json_response({"code": 0})

    async def action(request):
        data = await request.json()
        avatar = session(data["sessionid"])
        kind = data.get("audiotype")
        if hasattr(avatar, "motion"):
            name = {1: "idle", 2: "wave", 3: "smile"}.get(kind)
            if not avatar.motion.action(name):
                raise web.HTTPBadRequest()
            return web.json_response({"code": 0})
        if kind not in getattr(avatar, "custom_audio_index", {}):
            raise web.HTTPConflict(reason="action asset missing")
        avatar.set_custom_state(kind)
        return web.json_response({"code": 0})

    async def health(request):
        opt = request.app["opt"]
        kinds = {item["audiotype"] for item in opt.customopt if item.get("audiopath")}
        motions = [getattr(avatar, "motion", None) for avatar in session_manager.sessions.values()]
        motion = next((value for value in motions if value is not None), None)
        return web.json_response(
            {
                "ready": True,
                "avatar": opt.avatar_id,
                "model": opt.model,
                "animation": motion.mode if motion else None,
                "poster": manifest["poster"] if manifest else "/avatars/livetalking-sample.png",
                "actions": ["idle", "wave", "smile"]
                if manifest
                else [name for name, kind in {"wave": 2, "smile": 3}.items() if kind in kinds],
            }
        )

    def routes(application):
        application.router.add_get("/trend/health", health)
        application.router.add_post("/trend/reset", reset)
        application.router.add_post("/trend/pcm", pcm)
        application.router.add_post("/trend/close", close)
        application.router.add_post("/set_audiotype", action)

    registry.create = create
    RTCManager.handle_offer = offer
    RTCManager._create_pc_and_answer = answer
    config.parse_args = parse
    web.TCPSite = site
    upstream.setup_routes = routes
    upstream.mp.set_start_method("spawn", force=True)
    upstream.main()


if __name__ == "__main__":
    main()
