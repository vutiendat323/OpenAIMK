"""Model process: copied Audio ports, no STT/LLM/TTS implementation here.

stdin/stdout are private JSONL IPC. Raw PCM exists only in memory. All library
prints go to stderr so they cannot corrupt or masquerade as protocol messages.
"""

import asyncio
import base64
import contextlib
import json
import os
import sys
import time
from pathlib import Path

from .av_transport import FusionPreroll

WIRE = sys.stdout
sys.stdout = sys.stderr
ROOT = Path(__file__).resolve().parent.parent


def write(event):
    WIRE.write(json.dumps(event, ensure_ascii=False) + "\n")
    WIRE.flush()


class Worker:
    def __init__(self):
        self.stream = self.faces_task = None
        self.generation = None
        self.track_id = None
        self.output = asyncio.Queue(maxsize=16)
        self.last_level = 0.0
        self.bridge = None
        self.preroll = FusionPreroll()

    def load(self):
        import audio
        import torch
        from audio.infrastructure.nemo.sortformer import SortformerDiarizer
        from audio.infrastructure.nemo.titanet import TitaNetEmbedder
        from audio.infrastructure.tse.bsrnn import TseSeparator

        if not Path(audio.__file__).resolve().is_relative_to(ROOT / "Audio/src"):
            raise RuntimeError("audio_import_outside_workspace")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.diarizer = SortformerDiarizer(device=device)
        self.embedder = TitaNetEmbedder(device=device)
        checkpoint = os.environ.get(
            "TREND_TSE_MODEL", str(ROOT / ".runtime/models/bsrnn_spk_emb_100.ts")
        )
        self.separator = TseSeparator(checkpoint, device=device)

    async def begin(self, message):
        from audio.application.stream import SpeakerStream
        from audio.domain.evidence import FaceTrackBuffer
        from audio.domain.fusion import FusionGate
        from audio.domain.settings import settings_from_mapping
        from audio.infrastructure.vision.asd_bridge import VisionAudioBridge

        await self.end()
        self.generation = message["generation"]
        generation = self.generation
        self.track_id = message.get("track_id")
        self.faces = FaceTrackBuffer()
        url = os.environ.get("TREND_VISUAL_URL", "ws://127.0.0.1:9877")
        bridge = VisionAudioBridge(url, message["session_id"], self.faces)
        self.bridge = bridge
        settings = settings_from_mapping(
            {
                "enabled": True,
                "diarizer": "sortformer",
                "diarizer_latency": "ultra_low",
                "vision_faces": True,
                "vision_asd": True,
                "identity": "fusion",
                "stt_mask": True,
                "stt_mask_delay_secs": 0.7,
                "separator": "tse",
                "anchor_max_m": 0.8,
                "embedder_model": "titanet_small",
            }
        )
        gate = FusionGate(
            settings,
            self.faces,
            fsm_state=lambda: "active" if self.generation == generation else "idle",
        )

        async def audio(item):
            if self.generation != generation:
                return
            fresh = self.faces.fresh(time.time(), max_age=1.0) and bridge.ready
            # A row retains its own face evidence. Early accepted words wait
            # for that same face's lock rather than being irrevocably silenced.
            packets = self.preroll.push(
                pcm=item.audio,
                verdict=item.verdict,
                reason=item.reason,
                track_id=item.track_id,
                locked_track=gate.lock.target_track if gate.locked else None,
                owner_track=self.track_id,
                fresh=fresh,
                now=time.monotonic(),
            )
            for pcm, reason in packets:
                await self.offer_pcm(
                    {
                        "type": "pcm",
                        "generation": generation,
                        "data": base64.b64encode(pcm).decode("ascii"),
                        "accepted": any(pcm),
                        "reason": reason,
                    }
                )

        async def verdict(item):
            if self.generation == generation:
                evidence = gate.last_evidence_detail or {}
                self.offer(
                    {
                        "type": "fusion",
                        "generation": generation,
                        "locked": item.locked,
                        "verdict": item.verdict.value,
                        "source": item.source,
                        "tse_ready": self.stream.tse_ready,
                        # Numeric/category diagnostics only; no PCM, transcript,
                        # face IDs or embeddings leave this observation.
                        "diagnostics": {
                            "input_rms": round(self.last_level, 1),
                            "asd_probability": evidence.get("probability"),
                            "mouth": evidence.get("mouth"),
                            "labels": list(evidence.get("labels", {}).values()),
                            "echo_rejects": gate.echo_rejects,
                            "asd_late": bridge.asd_late,
                            "asd_wait_timed_out": bridge.last_wait_timed_out,
                        },
                    }
                )

        self.stream = SpeakerStream(
            diarizer=self.diarizer,
            gate=gate,
            separator=self.separator,
            embedder=self.embedder,
            stt_delay_secs=0.7,
            vision_audio=bridge,
            on_stt_audio=audio,
            on_verdict=verdict,
        )
        self.faces_task = asyncio.create_task(self.listen_faces(url, generation))
        await self.stream.start()
        # start() schedules the Visual handshake; it does not await its completion.
        try:
            async with asyncio.timeout(10):
                while not self.media_ready():
                    await asyncio.sleep(0.05)
        except TimeoutError:
            print(self.media_report(time.time(), "begin"), file=sys.stderr, flush=True)
            raise

    def media_missing(self, now):
        """The conditions that keep the voice session from starting (empty when ready)."""
        missing = []
        if not self.stream:
            missing.append("no_stream")
        if not (self.bridge and self.bridge.ready):
            missing.append("asd_bridge_not_ready")
        faces = getattr(self, "faces", None)
        if faces is None:
            missing.append("no_faces")
        elif not faces.fresh(now, max_age=1.0):
            missing.append("faces_stale")
        elif faces.anchor(now, 0.8) is None:
            missing.append("no_live_face_within_0.8m")
        if self.stream and not all(
            task is not None and not task.done()
            for task in (self.stream._worker, self.stream._releaser)
        ):
            missing.append("fusion_tasks_stopped")
        return missing

    def media_ready(self):
        return not self.media_missing(time.time())

    def media_report(self, now, stage="check"):
        """One stderr line (av-worker.log) explaining a media wait; numbers only."""
        missing = self.media_missing(now)
        faces = getattr(self, "faces", None)
        tracks = faces.tracks_at(now) if faces is not None else []
        distances = [t["distance_m"] for t in tracks if t.get("distance_m") is not None]
        nearest = f"{min(distances):.2f} m" if distances else "none"
        bridge = self.bridge
        state = (
            "absent"
            if bridge is None
            else f"ready={bool(bridge.ready)} terminal={getattr(bridge, '_terminal', None)} "
            f"closed={getattr(bridge, '_closed', None)} version={getattr(bridge, '_version', None)}"
        )
        return (
            f"[av_worker] media not ready at {time.strftime('%H:%M:%S')} ({stage}): "
            f"{','.join(missing) or 'ready'}; faces {len(tracks)} "
            f"(live {sum(t.get('is_live') is True for t in tracks)}), nearest {nearest}; "
            f"asd bridge {state}"
        )

    def offer(self, event):
        if self.output.full():
            # Telemetry may be coalesced; it must never evict approved PCM.
            return
        self.output.put_nowait(event)

    async def offer_pcm(self, event):
        # Apply backpressure to the delayed-audio releaser rather than dropping
        # customer words when multiple verdict-covered chunks arrive together.
        await self.output.put(event)

    async def send(self):
        while True:
            event = await self.output.get()
            if event.get("generation") == self.generation:
                await asyncio.to_thread(write, event)

    async def listen_faces(self, url, generation):
        import websockets

        last_seq = -1
        while self.generation == generation:
            try:
                async with websockets.connect(url, max_size=1048576, close_timeout=1) as socket:
                    await socket.send(json.dumps({"cmd": "faces"}))
                    async for raw in socket:
                        event = json.loads(raw)
                        if event.get("event") != "faces":
                            continue
                        seq, captured = event.get("frame_seq"), event.get("captured_at")
                        if (
                            type(seq) is not int
                            or seq <= last_seq
                            or type(captured) not in (int, float)
                            or not 0 <= time.time() - captured <= 1.0
                        ):
                            continue
                        last_seq = seq
                        # No anti-spoof result is not a live-person result.
                        event["tracks"] = [
                            p for p in event.get("tracks", []) if p.get("is_live") is True
                        ]
                        event["ts"] = captured
                        self.faces.add(event)
            except Exception:
                await asyncio.sleep(1)

    async def command(self, message):
        kind = message.get("type")
        if kind == "begin":
            started = time.monotonic()
            try:
                await self.begin(message)
            except Exception:
                import traceback

                print(
                    f"[av_worker] begin failed after {time.monotonic() - started:.1f}s "
                    f"(generation {message.get('generation')}):\n{traceback.format_exc()}",
                    file=sys.stderr,
                    flush=True,
                )
                await self.end()
                await asyncio.to_thread(
                    write,
                    {
                        "type": "error",
                        "generation": message["generation"],
                        "request_id": message["request_id"],
                    },
                )
            else:
                print(
                    f"[av_worker] begin ready after {time.monotonic() - started:.1f}s "
                    f"(generation {message.get('generation')})",
                    file=sys.stderr,
                    flush=True,
                )
                await asyncio.to_thread(
                    write,
                    {
                        "type": "session_ready",
                        "generation": self.generation,
                        "request_id": message["request_id"],
                    },
                )
            return
        if message.get("generation") != self.generation:
            return
        if kind == "end":
            await self.end()
        elif kind == "check_ready":
            # The native handshake can outlast one camera/liveness frame.
            # Wait for fresh evidence without tearing down that new voice call
            # on a transient miss. Audio remains fail-closed throughout.
            deadline = time.monotonic() + 3
            ready = self.media_ready()
            while (
                not ready
                and self.generation == message["generation"]
                and time.monotonic() < deadline
            ):
                await asyncio.sleep(0.05)
                ready = self.media_ready()
            if not ready:
                print(self.media_report(time.time(), "check_ready"), file=sys.stderr, flush=True)
            await asyncio.to_thread(
                write,
                {
                    "type": "session_ready" if ready else "error",
                    "generation": self.generation,
                    "request_id": message["request_id"],
                },
            )
        elif kind == "playback" and self.stream:
            (self.stream.bot_started if message.get("playing") else self.stream.bot_stopped)()
        elif kind == "audio" and self.stream:
            import numpy as np
            from audio.application.stream import AudioChunk

            pcm = base64.b64decode(message["data"], validate=True)
            if len(pcm) != 2560:
                return
            # Raw-level VAD is bookkeeping only; accepted PCM and native VAD
            # decide actual turns. This level must never authorize a tool.
            level = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
            self.last_level = float(np.sqrt(np.mean(level * level)))
            for task in (self.stream._worker, self.stream._releaser):
                if task is None or task.done():
                    raise RuntimeError("fusion_processing_stopped")
            self.stream.push_audio(AudioChunk(pcm, 16000, 1))

    async def end(self):
        self.generation = None
        self.preroll.clear()
        self.bridge = None
        if self.faces_task:
            self.faces_task.cancel()
            await asyncio.gather(self.faces_task, return_exceptions=True)
            self.faces_task = None
        if self.stream:
            # Privacy boundary: drop delayed/TSE audio; do not call finish().
            await self.stream.close()
            self.stream = None
        while not self.output.empty():
            self.output.get_nowait()


async def main():
    worker = Worker()
    await asyncio.to_thread(worker.load)
    write({"type": "ready"})
    sender = asyncio.create_task(worker.send())
    try:
        while raw := await asyncio.to_thread(sys.stdin.buffer.readline, 65537):
            if len(raw) > 65536:
                raise RuntimeError("ipc_frame_too_large")
            await worker.command(json.loads(raw))
    finally:
        sender.cancel()
        await worker.end()
        with contextlib.suppress(asyncio.CancelledError):
            await sender


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        import traceback

        traceback.print_exc(file=sys.stderr)
        write({"type": "fatal", "error": type(error).__name__})
        raise SystemExit(1) from None
