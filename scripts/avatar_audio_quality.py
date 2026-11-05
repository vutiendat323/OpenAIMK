"""Capture sustained speech-like PCM through real avatar WebRTC and detect inserted gaps."""

import asyncio
import base64
import json
import time
import wave
from pathlib import Path

import numpy as np
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from av import AudioResampler

from trendcoffee.avatar import AvatarBridge


async def main():
    bridge = AvatarBridge("http://127.0.0.1:8011")
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    ready = asyncio.Event()
    tasks, received, native_received = [], [], []
    rate, seconds = 48000, 4
    t = np.arange(rate * seconds) / rate
    source = (
        8000 * np.sin(2 * np.pi * 1733 * t)
        + 2000 * np.sin(2 * np.pi * 373 * t)
        + 1800 * np.sin(2 * np.pi * 12000 * t)
    ).astype("<i2")

    async def receive(track):
        resampler = AudioResampler(format="s16", layout="mono", rate=16000)
        native = AudioResampler(format="s16", layout="mono", rate=48000)
        while True:
            frame = await track.recv()
            ready.set()
            if track.kind == "audio":
                for original in native.resample(frame):
                    native_received.append(original.to_ndarray().ravel().copy())
                for mono in resampler.resample(frame):
                    received.append(mono.to_ndarray().ravel().copy())

    @pc.on("track")
    def track(track):
        tasks.append(asyncio.create_task(receive(track)))

    try:
        pc.addTransceiver("audio", direction="recvonly")
        pc.addTransceiver("video", direction="recvonly")
        await pc.setLocalDescription(await pc.createOffer())
        answer = await bridge.offer(pc.localDescription.sdp)
        await bridge.reset(1)
        await pc.setRemoteDescription(RTCSessionDescription(**answer))
        await asyncio.wait_for(ready.wait(), 15)
        await asyncio.sleep(0.3)
        start = time.monotonic()
        for i in range(seconds * 50):
            # Same 20ms packets as native voice, including normal callback jitter.
            jitter = [0, 0.004, 0.012, 0.002, 0.007][i % 5]
            await asyncio.sleep(max(0, start + i * 0.02 + jitter - time.monotonic()))
            raw = source[i * 960 : (i + 1) * 960].tobytes()
            await bridge.audio(
                1, {"data": base64.b64encode(raw).decode(), "sampleRate": rate, "numChannels": 1}
            )
        await asyncio.sleep(2)
        pcm = np.concatenate(received)
        frames = pcm[: len(pcm) // 320 * 320].reshape(-1, 320)
        energy = np.sqrt(np.mean(frames.astype(float) ** 2, axis=1))
        active = np.where(energy > 1000)[0]
        assert len(active), "no audio returned"
        inside = energy[active[0] + 2 : active[-1] - 2]
        native_pcm = np.concatenate(native_received)
        high = native_pcm[: len(native_pcm) // 960 * 960].reshape(-1, 960).astype(float)
        peaks = np.abs(np.fft.rfft(high, axis=1))[:, 240] * 2 / 960
        high_amplitude = float(np.median(peaks[peaks > 100])) if np.any(peaks > 100) else 0
        result = {
            "twelve_khz_amplitude": round(high_amplitude, 1),
            "input_seconds": seconds,
            "output_span_seconds": round((active[-1] - active[0] + 1) * 0.02, 3),
            "silent_20ms_frames_inside_continuous_input": int(np.sum(inside < 300)),
            "minimum_middle_rms": round(float(inside.min()), 1),
        }
        output = Path("output/avatar-audio-quality")
        output.mkdir(exist_ok=True, parents=True)
        for name, samples, hz in [("source", source, rate), ("avatar", native_pcm, 48000)]:
            with wave.open(str(output / f"{name}.wav"), "wb") as file:
                file.setnchannels(1)
                file.setsampwidth(2)
                file.setframerate(hz)
                file.writeframes(samples.astype("<i2").tobytes())
        (output / "metrics.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
        assert result["silent_20ms_frames_inside_continuous_input"] <= 1, result
        assert result["output_span_seconds"] <= seconds + 0.06, result
        assert high_amplitude > 600, result
    finally:
        await pc.close()
        await bridge.close()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


asyncio.run(main())
