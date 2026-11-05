"""Measure actual received frames and record a local prerecorded-PCM preview."""

import argparse
import asyncio
import base64
import hashlib
import json
import queue
import subprocess
import threading
import time
import wave
from pathlib import Path

import av
import cv2
import numpy as np
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription

from trendcoffee.avatar import AvatarBridge

ROOT = Path(__file__).resolve().parents[1]


class Recorder:
    def __init__(self, path, fps):
        self.path, self.fps = path, fps
        self.queue = queue.Queue(maxsize=12)
        self.dropped = self.frames = 0
        self.error = None
        self.worker = threading.Thread(target=self.run)
        self.worker.start()

    def push(self, frame):
        try:
            self.queue.put_nowait(frame)
        except queue.Full:
            self.dropped += 1

    def run(self):
        try:
            with av.open(str(self.path), "w") as output:
                stream = None
                first_pts = None
                while (frame := self.queue.get()) is not None:
                    if stream is None:
                        stream = output.add_stream("libx264", rate=self.fps)
                        stream.width, stream.height, stream.pix_fmt = (
                            frame.width,
                            frame.height,
                            "yuv420p",
                        )
                        stream.options = {"preset": "ultrafast", "crf": "18", "threads": "2"}
                        first_pts = frame.pts
                    frame.pts -= first_pts
                    for packet in stream.encode(frame):
                        output.mux(packet)
                    self.frames += 1
                if stream is not None:
                    for packet in stream.encode():
                        output.mux(packet)
        except Exception as error:
            self.error = str(error)

    def close(self):
        self.queue.put(None, timeout=5)
        self.worker.join(10)
        assert not self.worker.is_alive() and self.error is None, self.error


async def run(url, output, min_neural_fps=0, audio_path=None):
    output.mkdir(exist_ok=True, parents=True)
    bridge = AvatarBridge(url)
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    rows, tasks, health, segments = [], [], {}, []
    recorder = Recorder(output / "received-video.mp4", 24)
    phase = "connect"
    gap_started = None
    rest_snapshot = False
    previous = None
    with wave.open(str(audio_path or ROOT / "frontend/public/voice/default/greeting.wav")) as wav:
        rate, channels = wav.getframerate(), wav.getnchannels()
        clip = wav.readframes(wav.getnframes())

    @pc.on("track")
    def track_received(track):
        async def receive():
            nonlocal previous, rest_snapshot
            while True:
                frame = await track.recv()
                now = time.monotonic()
                rgb = frame.to_ndarray(format="rgb24")
                gray = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (180, 320))
                delta = (
                    float(np.abs(gray.astype(float) - previous).mean())
                    if previous is not None
                    else 0
                )
                previous = gray.astype(float)
                if (
                    phase == "pcm-gap"
                    and gap_started is not None
                    and now - gap_started > 0.5
                    and not rest_snapshot
                ):
                    cv2.imwrite(
                        str(output / "relaxed-source-smile.jpg"),
                        cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                    )
                    rest_snapshot = True
                rows.append(
                    {
                        "at": now,
                        "phase": phase,
                        "sha": hashlib.sha256(rgb).hexdigest(),
                        "mae": delta,
                    }
                )
                recorder.push(frame)

        tasks.append(asyncio.create_task(receive()))

    async def snapshot(label):
        health[label] = (await bridge.client.get(url + "/trend/health")).json()

    async def feed(epoch, repeats):
        raw, origin = clip * repeats, time.monotonic()
        segments.append((origin, raw))
        step = rate * channels * 2 * 80 // 1000
        for index, offset in enumerate(range(0, len(raw), step)):
            await asyncio.sleep(max(0, origin + index * 0.08 - time.monotonic()))
            await bridge.audio(
                epoch,
                {
                    "data": base64.b64encode(raw[offset : offset + step]).decode(),
                    "sampleRate": rate,
                    "numChannels": channels,
                },
            )

    try:
        pc.addTransceiver("video", direction="recvonly")
        await pc.setLocalDescription(await pc.createOffer())
        answer = await bridge.offer(pc.localDescription.sdp)
        assert "m=audio " not in answer["sdp"]
        await bridge.reset(1)
        await pc.setRemoteDescription(RTCSessionDescription(**answer))
        await asyncio.sleep(0.6)
        phase = "speech"
        await feed(1, 2)
        await snapshot(phase)
        phase = "pcm-gap"
        gap_started = time.monotonic()
        await asyncio.sleep(1.3)
        await snapshot(phase)
        phase = "resumed"
        await feed(1, 1)
        await snapshot(phase)
        phase = "wave"
        assert await bridge.action("wave")
        await feed(1, 1)
        await snapshot(phase)
        phase = "interrupt"
        await bridge.reset(2)
        await asyncio.sleep(0.3)
        await snapshot(phase)
    finally:
        try:
            await bridge.close()
        finally:
            await pc.close()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.to_thread(recorder.close)

    cadence = {}
    for label in ("speech", "pcm-gap", "resumed", "wave"):
        selected = [r for r in rows if r["phase"] == label]
        if len(selected) < 2:
            raise AssertionError(f"No video in {label}")
        intervals = np.diff([r["at"] for r in selected]) * 1000
        cadence[label] = {
            "frames": len(selected),
            "received_fps": (len(selected) - 1) / (selected[-1]["at"] - selected[0]["at"]),
            "interval_p95_ms": float(np.percentile(intervals, 95)),
            "interval_max_ms": float(max(intervals)),
            "unique_decoded_frames": len({r["sha"] for r in selected}),
            "frame_difference_median": float(np.median([r["mae"] for r in selected])),
        }
    report = {
        "cadence": cadence,
        "health": health,
        "recording_frames": recorder.frames,
        "recording_drops": recorder.dropped,
        "note": "Decoded RTC cadence. Neural, source presentation and interpolated mouth are distinct. Preview audio is prerecorded reference +160ms; not physical acoustic sync.",
    }
    (output / "cadence.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "received-frame-times.json").write_text(json.dumps(rows, indent=2) + "\n")
    # Reference PCM is aligned to its feed clock plus native startup buffering.
    length = int((rows[-1]["at"] - rows[0]["at"] + 0.2) * rate) * channels * 2
    pcm = bytearray(length)
    for origin, raw in segments:
        offset = max(0, int((origin - rows[0]["at"] + 0.16) * rate)) * channels * 2
        if offset < length:
            count = min(length - offset, len(raw))
            pcm[offset : offset + count] = raw[:count]
    with wave.open(str(output / "reference.wav"), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(output / "received-video.mp4"),
            "-i",
            str(output / "reference.wav"),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output / "conversation-preview.mp4"),
        ],
        check=True,
    )
    print(
        json.dumps(
            {
                "cadence": cadence,
                "neural_fps": health["speech"]["rendered_fps"],
                "interpolated_mouth_frames": health["speech"]["interpolated_mouth_frames"],
            }
        ),
        flush=True,
    )
    assert recorder.dropped == 0
    assert all(c["received_fps"] >= 20 and c["interval_p95_ms"] < 65 for c in cadence.values())
    assert health["interrupt"]["audio_buffer_samples"] == 0
    assert health["pcm-gap"]["mouth_mode"] == "source"
    assert health["speech"]["rendered_fps"] >= min_neural_fps
    assert all(h["ready"] and h["error"] is None for h in health.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--output", type=Path, default=ROOT / "output/avatar-smoothness")
    parser.add_argument("--min-neural-fps", type=float, default=0)
    parser.add_argument("--audio", type=Path, help="Local prerecorded PCM WAV fixture")
    args = parser.parse_args()
    asyncio.run(run(args.url, args.output, args.min_neural_fps, args.audio))
