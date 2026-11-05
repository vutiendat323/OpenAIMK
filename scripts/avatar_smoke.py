import argparse
import asyncio
import base64
import json
import time
import wave
from pathlib import Path

import numpy as np
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription

from trendcoffee.avatar import AvatarBridge


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--wave", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    bridge = AvatarBridge(args.url)
    tasks = []
    times = []
    audio = 0
    audible = 0

    async def receive(track):
        nonlocal audio, audible
        while True:
            frame = await track.recv()
            if track.kind == "video":
                times.append(time.monotonic())
                if len(times) == 1:
                    frame.to_image().save(
                        str(Path(__file__).resolve().parent.parent / "output/avatar-current.png")
                    )
            else:
                audio += 1
                if np.abs(frame.to_ndarray().astype(np.int32)).max() > 100:
                    audible += 1

    @pc.on("track")
    def on_track(track):
        tasks.append(asyncio.create_task(receive(track)))

    try:
        pc.addTransceiver("audio", direction="recvonly")
        pc.addTransceiver("video", direction="recvonly")
        await pc.setLocalDescription(await pc.createOffer())
        answer = await bridge.offer(pc.localDescription.sdp)
        await bridge.reset(1)
        await pc.setRemoteDescription(RTCSessionDescription(**answer))
        with wave.open(
            str(
                Path(__file__).resolve().parent.parent
                / "frontend/public/voice/default/greeting.wav"
            )
        ) as f:
            rate, channels, raw = f.getframerate(), f.getnchannels(), f.readframes(f.getnframes())
        start = time.monotonic()
        for _ in range(args.repeats):
            if args.wave:
                assert await bridge.action("wave")
            step = rate * channels * 2 * 80 // 1000
            for i in range(0, len(raw), step):
                tick = time.monotonic()
                await bridge.audio(
                    1,
                    {
                        "data": base64.b64encode(raw[i : i + step]).decode(),
                        "sampleRate": rate,
                        "numChannels": channels,
                    },
                )
                await asyncio.sleep(max(0, 0.08 - (time.monotonic() - tick)))
        await asyncio.sleep(2)
        await bridge.reset(2)
        result = {
            "video_frames": len(times),
            "audio_frames": audio,
            "audible_frames": audible,
            "first_video_ms": round((times[0] - start) * 1000, 1) if times else None,
            "final_fps": round((len(times) - 1) / (times[-1] - times[0]), 2)
            if len(times) > 1
            else 0,
            "wave_requested": args.wave,
            "repeats": args.repeats,
            "note": "Synthetic fixture, no perceptual skew or acoustic interrupt-tail measurement.",
        }
        print(json.dumps(result), flush=True)
        Path(Path(__file__).resolve().parent.parent / "output/avatar-smoke.json").write_text(
            json.dumps(result, indent=2)
        )
        assert len(times) > 50 and audible > 0, result
    finally:
        await pc.close()
        await bridge.close()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


asyncio.run(main())
