"""Real WebRTC epoch regression: retired 440Hz must not follow new 880Hz speech.

Run with the prepared LiveTalking interpreter, against an otherwise idle local engine.
This measures received media, not physical-speaker mute latency.
"""

import argparse
import asyncio
import base64
import json
import time
from pathlib import Path

import numpy as np
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from av import AudioResampler

from trendcoffee.avatar import AvatarBridge


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    args = parser.parse_args()
    bridge = AvatarBridge(args.url)
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    tasks, detected = [], []
    ready = asyncio.Event()

    async def receive(track):
        resampler = AudioResampler(format="s16", layout="mono", rate=16000)
        while True:
            frame = await track.recv()
            if track.kind != "audio":
                ready.set()
                continue
            for mono in resampler.resample(frame):
                samples = mono.to_ndarray().ravel().astype(float)
                if np.max(np.abs(samples)) < 500:
                    continue
                spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
                frequency = np.argmax(spectrum) * 16000 / len(samples)
                tone = 440 if abs(frequency - 440) < 60 else 880 if abs(frequency - 880) < 60 else 0
                if tone:
                    detected.append((time.monotonic(), tone))

    @pc.on("track")
    def track(track):
        tasks.append(asyncio.create_task(receive(track)))

    async def tone(epoch, frequency, packets):
        for packet in range(packets):
            ticks = np.arange(1280) + packet * 1280
            raw = (np.sin(ticks * 2 * np.pi * frequency / 16000) * 10000).astype("<i2")
            await bridge.audio(
                epoch,
                {
                    "data": base64.b64encode(raw.tobytes()).decode(),
                    "sampleRate": 16000,
                    "numChannels": 1,
                },
            )
            await asyncio.sleep(0.08)

    try:
        pc.addTransceiver("audio", direction="recvonly")
        pc.addTransceiver("video", direction="recvonly")
        await pc.setLocalDescription(await pc.createOffer())
        answer = await bridge.offer(pc.localDescription.sdp)
        await bridge.reset(1)
        await pc.setRemoteDescription(RTCSessionDescription(**answer))
        await asyncio.wait_for(ready.wait(), 15)
        await bridge.action("wave")
        await tone(1, 440, 12)
        await bridge.reset(2)
        reset = time.monotonic()
        await tone(2, 880, 20)
        await asyncio.sleep(1)
        new = [stamp for stamp, kind in detected if stamp >= reset and kind == 880]
        assert any(kind == 440 for _, kind in detected), "old tone was never rendered"
        assert len(new) >= 20, "new turn did not resume"
        retired = sum(kind == 440 and stamp > new[0] + 0.04 for stamp, kind in detected)
        result = {
            "retired_tone_frames_after_new_turn": retired,
            "new_tone_frames": len(new),
            "first_new_audio_after_reset_ms": round((new[0] - reset) * 1000, 1),
            "note": "RTP epoch check, not acoustic interruption latency.",
        }
        Path("output/avatar-interrupt.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
        assert retired == 0, result
    finally:
        await pc.close()
        await bridge.close()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


asyncio.run(main())
