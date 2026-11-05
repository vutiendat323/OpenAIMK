"""Exercise the local Ditto WebRTC endpoint with prerecorded PCM, never live voice."""

import argparse
import asyncio
import base64
import json
import time
import wave
from pathlib import Path

import numpy as np
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from PIL import Image, ImageDraw

from trendcoffee.avatar import AvatarBridge

ROOT = Path(__file__).resolve().parents[1]


async def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--output", type=Path, default=ROOT / "output/ditto-webrtc")
    parser.add_argument(
        "--legacy-audio", action="store_true", help="Also negotiate legacy RTP audio"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    bridge = AvatarBridge(args.url)
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    tasks, video_times, audio_times, samples, acknowledgements = [], [], [], [], []
    audible = 0
    phase = "connect"
    counts = {}

    async def receive(track):
        nonlocal audible
        while True:
            frame = await track.recv()
            now = time.monotonic()
            if track.kind == "audio":
                audio_times.append(now)
                if np.abs(frame.to_ndarray().astype(np.int32)).max() > 100:
                    audible += 1
            else:
                video_times.append(now)
                counts[phase] = counts.get(phase, 0) + 1
                if phase != "connect" and counts[phase] % 6 == 0 and len(samples) < 24:
                    samples.append((phase, frame.to_ndarray(format="rgb24").copy()))

    @pc.on("track")
    def track_received(track):
        tasks.append(asyncio.create_task(receive(track)))

    async def health():
        return (await bridge.client.get(args.url + "/trend/health")).json()

    async def feed(epoch, repeats):
        with wave.open(str(ROOT / "frontend/public/voice/default/greeting.wav"), "rb") as wav:
            rate, channels = wav.getframerate(), wav.getnchannels()
            raw = wav.readframes(wav.getnframes())
        raw *= repeats
        step = rate * channels * 2 * 80 // 1000
        origin = time.monotonic()
        for index, offset in enumerate(range(0, len(raw), step)):
            await asyncio.sleep(max(0, origin + index * 0.08 - time.monotonic()))
            tick = time.monotonic()
            await bridge.audio(
                epoch,
                {
                    "data": base64.b64encode(raw[offset : offset + step]).decode(),
                    "sampleRate": rate,
                    "numChannels": channels,
                },
            )
            acknowledgements.append((time.monotonic() - tick) * 1000)

    try:
        if args.legacy_audio:
            pc.addTransceiver("audio", direction="recvonly")
        pc.addTransceiver("video", direction="recvonly")
        await pc.setLocalDescription(await pc.createOffer())
        answer = await bridge.offer(pc.localDescription.sdp)
        if not args.legacy_audio:
            assert "m=audio " not in answer["sdp"]
        await bridge.reset(1)
        await pc.setRemoteDescription(RTCSessionDescription(**answer))
        await asyncio.sleep(0.5)
        before = await health()
        phase = "speech"
        await feed(1, 3)
        speech = await health()
        phase = "interrupt"
        tick = time.monotonic()
        await bridge.reset(2)
        reset_ms = (time.monotonic() - tick) * 1000
        reset = await health()
        assert reset["audio_buffer_samples"] == 0
        phase = "wave"
        assert await bridge.action("wave")
        await feed(2, 2)
        waved = await health()
        assert await bridge.action("idle")
        phase = "smile"
        assert await bridge.action("smile")
        await asyncio.sleep(0.5)
        await bridge.reset(3)
        final = await health()
        assert final["ready"] and final["error"] is None
        assert speech["generated_frames"] > before["generated_frames"]
        assert len(video_times) > 50
        assert audible > 0 if args.legacy_audio else not audio_times
        sheet = Image.new("RGB", (960, 300 * ((len(samples) + 3) // 4)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, (label, pixels) in enumerate(samples):
            x, y = (i % 4) * 240, (i // 4) * 300
            sheet.paste(Image.fromarray(pixels).crop((240, 90, 480, 370)), (x, y + 20))
            draw.text((x + 4, y + 4), f"{label} sample {i}", fill="black")
        sheet.save(args.output / "received-mouth-frames.jpg")
        for label, pixels in samples:
            if label == "wave":
                Image.fromarray(pixels).save(args.output / "wave-speaking.jpg")
                break
        report = dict(
            before=before,
            speech=speech,
            wave=waved,
            final=final,
            reset_http_ms=reset_ms,
            video_frames=len(video_times),
            audio_frames=len(audio_times),
            audible_frames=audible,
            video_only=not args.legacy_audio,
            video_rtp_fps=(len(video_times) - 1) / (video_times[-1] - video_times[0]),
            audio_gap_p95_ms=float(np.percentile(np.diff(audio_times) * 1000, 95))
            if len(audio_times) > 1
            else None,
            pcm_ack_p95_ms=float(np.percentile(acknowledgements, 95)),
            note="Synthetic PCM, not microphone recognition or acoustic speaker quality; RTP FPS may repeat a generated face.",
        )
        (args.output / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), flush=True)
    finally:
        try:
            await bridge.close()
        finally:
            await pc.close()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(run())
