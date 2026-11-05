"""Differential check: OpenJarvis's speaker code against this library's.

Part 1 feeds seeded diarizer rows, Vision ``faces`` events, pushed ASD windows,
FSM states and voice embeddings through both versions of the gates and the
console. Part 2 feeds seeded microphone audio, diarizer rows, bot playback and
a fake separator through OpenJarvis's SpeakerAudioProcessor (in a Pipecat
pipeline) and through SpeakerStream, with and without the STT delay. Every
verdict, lock state, label, turn verdict, console snapshot and released STT
chunk is compared. Part 0 compares the syntax trees of every ported symbol and
method and allows only the differences the spec's API changes name.

Part 2 does not drive the Vision ASD wait or track pin, in-stream embeddings,
TSE under a fusion lock (enrollment needs ASD-confirmed speech), kept_onset or
drain(), and compares release order and content, not timing. Those paths rest
on Part 0: their code is identical to OpenJarvis's.

Read-only for OpenJarvis. Run from ``OpenJarvis/`` with its environment, which
carries both packages' dependencies and Pipecat:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../Audio/src \\
        .venv/bin/python ../Audio/tools/parity_check.py

Exit status 0 when everything matches, 1 on the first mismatch.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import importlib.util
import json
import random
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from openjarvis.kiosk.evaluate import get_config
from openjarvis.server.voice import speaker as oj_speaker
from openjarvis.server.voice import speaker_console as oj_console
from openjarvis.server.voice import speaker_identity as oj_identity

from audio.application.console import SpeakerConsole
from audio.application.ports import LiveKey
from audio.application.stream import AudioChunk, SpeakerStream
from audio.domain.evidence import FaceTrackBuffer
from audio.domain.fusion import FusionGate
from audio.domain.gate import AudioOnlyGate, SpeakerTracker
from audio.domain.identity import EmbeddingJob, SlotIdentity
from audio.domain.settings import SpeakerSettings
from audio.domain.verdict import Verdict

SEEDS = range(8)
STREAM_SEEDS = range(3)
ROWS = 600
STREAM = "s"
FUSION = {
    "enabled": True,
    "diarizer": "sortformer",
    "vision_faces": True,
    "vision_asd": True,
    "identity": "fusion",
}
OLD = SimpleNamespace(
    settings=oj_speaker.SpeakerSettings,
    faces=oj_speaker.FaceTrackBuffer,
    gate=oj_speaker.AudioOnlyGate,
    fusion=oj_identity.FusionGate,
    tracker=oj_speaker.SpeakerTracker,
    job=oj_identity.EmbeddingJob,
    slot_identity=oj_identity.SlotIdentity,
)
NEW = SimpleNamespace(
    settings=SpeakerSettings,
    faces=FaceTrackBuffer,
    gate=AudioOnlyGate,
    fusion=FusionGate,
    tracker=SpeakerTracker,
    job=EmbeddingJob,
    slot_identity=SlotIdentity,
)


# ---------------------------------------------------------------------------
# Part 1: gates, lock and console
# ---------------------------------------------------------------------------


def scenario(seed: int) -> list[SimpleNamespace]:
    """One customer (track 1, slot 0) mostly speaking, a bystander sometimes.

    Two solo stretches (the customer alone, Light-ASD high) let fusion lock in
    each active session; the rest is random overlap, MAR and bystander speech.
    """
    rng = random.Random(seed)
    fsm, steps = "idle", []
    for i in range(ROWS):
        t = 100.0 + i * 0.08
        fsm = {20: "active", 380: "cleanup", 420: "active"}.get(i, fsm)
        solo = 30 <= i < 80 or 430 <= i < 480
        customer = solo or rng.random() < 0.6
        tracks = [
            {
                "track_id": 1,
                "distance_m": rng.choice([0.6, 0.9, 1.3]),
                "mouth_activity": 0.9 if customer else round(rng.random() * 0.4, 2),
                "facing": True,
            }
        ]
        if rng.random() < 0.5:
            tracks.append(
                {
                    "track_id": 2,
                    "distance_m": rng.choice([0.5, 1.1, 2.0]),
                    "mouth_activity": round(rng.random(), 2),
                    "facing": rng.random() < 0.7,
                }
            )
        asd = None
        if i % 2 == 0:
            high = solo or rng.random() < 0.7
            asd = {
                "stream_id": STREAM,
                "track_id": 1 if solo or rng.random() < 0.8 else 2,
                "t0": t - 1.0,
                "frame_secs": 0.04,
                "probabilities": [
                    0.9 if high else round(rng.random(), 2) for _ in range(25)
                ],
            }
        probs = [0.9 if customer else 0.0] + [
            0.0 if solo else rng.choice([0.0, 0.0, 0.0, 0.0, 0.0, 0.2, 0.55, 0.9])
            for _ in range(3)
        ]
        embedding = None
        if i % 25 == 5:
            embedding = (
                rng.randrange(4),
                [rng.gauss(0.0, 1.0) for _ in range(192)],
                rng.random() < 0.5,
            )
        faces = None
        if rng.random() < 0.9:
            faces = {"event": "faces", "ts": t, "tracks": tracks}
        steps.append(
            SimpleNamespace(
                t=t,
                fsm=fsm,
                faces=faces,
                asd=asd,
                probs=probs,
                bot=rng.random() < 0.1,
                embedding=embedding,
            )
        )
    return steps


def run_gate(impl, steps, *, fused: bool):
    settings = impl.settings(**FUSION)
    faces = impl.faces()
    faces.set_asd_stream(STREAM)
    faces.use_pushed_asd(True)
    fsm = {"state": "idle"}
    if fused:
        gate = impl.fusion(settings, faces, fsm_state=lambda: fsm["state"])
    else:
        gate = impl.gate(settings, faces)
    tracker = impl.tracker(settings, diarized=True)
    tracker.begin_span()
    rows = []
    clock = [0.0]
    with patch("time.time", lambda: clock[0]):
        for i, step in enumerate(steps):
            clock[0] = step.t + 0.05
            fsm["state"] = step.fsm
            if step.faces is not None:
                faces.add(copy.deepcopy(step.faces))
            if step.asd is not None:
                faces.add_asd(copy.deepcopy(step.asd))
            verdict = gate.frame(
                step.probs, bot_speaking=step.bot, t=step.t, asd_stream_id=STREAM
            )
            if verdict is not None:
                tracker.record(verdict)
            row = {
                "verdict": verdict.value if verdict is not None else None,
                "overlap": gate.overlap,
                "target": gate.target,
                "evidence": gate.last_evidence_detail,
                "asd_counts": dict(gate.asd_counts),
            }
            if i % 25 == 24:
                row["turn"] = tracker.close_turn().value
                tracker.begin_span()
            if fused:
                lock = gate.lock
                if step.embedding is not None:
                    slot, vector, confirmed = step.embedding
                    job = impl.job(
                        epoch=lock.epoch,
                        slot=slot,
                        segment_end=step.t,
                        seconds=1.0,
                        pcm=np.zeros(1, np.int16),
                        target_confirmed=confirmed,
                    )
                    row["embedding_applied"] = lock.observe_embedding(
                        job, np.asarray(vector, np.float32)
                    )
                row.update(
                    {
                        "lock_state": lock.state.value,
                        "epoch": lock.epoch,
                        "target_track": lock.target_track,
                        "target_slots": sorted(lock.target_slots),
                        "labels": [lock.label(slot).value for slot in range(4)],
                        "echo_rejects": gate.echo_rejects,
                        "row_voices": list(gate.row_voices),
                        "row_is_target": gate.row_is_target,
                        "source": gate.last_source,
                        "events": [event.fields() for event in lock.drain_events()],
                    }
                )
            rows.append(json.dumps(row, default=str))
    return rows, gate, settings


class Bridge:
    def __init__(self):
        self.asd_late = 0
        self.asd_age_ms = []

    def offer_telemetry(self, snapshot):
        pass


def console_outputs(old_gate, old_settings, new_gate, new_settings, *, fused):
    old = oj_console.SpeakerConsole(
        SimpleNamespace(
            _gate=old_gate,
            _fusion=old_gate if fused else None,
            _vision_audio=Bridge(),
            _bot_audible_until=0.0,
            _separator=None,
            _enrolled=0,
            _tracker=SimpleNamespace(bargein_blocked=2),
            stt_masked_no_verdict=3,
        ),
        old_settings,
    )
    distance = LiveKey(
        "approach_threshold_m",
        (0.1, 6.0),
        lambda: get_config().approach_threshold_m,
        lambda value: None,
    )
    new = SpeakerConsole(
        SimpleNamespace(
            gate=new_gate,
            fusion=new_gate if fused else None,
            bridge=Bridge(),
            bot_audible_until=0.0,
            tse_ready=False,
            stt_masked_no_verdict=3,
            bargein_blocked=2,
        ),
        new_settings,
        live_keys=(distance,),
    )
    pcm = (np.sin(np.arange(1600) / 7.0) * 9000).astype(np.int16).tobytes()
    outputs = []
    with patch("time.time", lambda: 500.0):
        for console, reject in (
            (old, oj_speaker.Verdict.REJECT),
            (new, Verdict.REJECT),
        ):
            console.verdict(reject, 499.0)
            console.audio(pcm)
            steps = [console.snapshot(), console.tune("voice_match", 0.7)]
            try:
                console.tune("voice_reject", 0.9)
            except ValueError as exc:
                steps.append(str(exc))
            steps.append(console.snapshot())
            outputs.append(json.dumps(steps, allow_nan=False))
    return outputs


def part_one() -> bool:
    for seed in SEEDS:
        steps = scenario(seed)
        for fused in (False, True):
            old_rows, old_gate, old_settings = run_gate(OLD, steps, fused=fused)
            new_rows, new_gate, new_settings = run_gate(NEW, steps, fused=fused)
            for i, (old_row, new_row) in enumerate(
                zip(old_rows, new_rows, strict=True)
            ):
                if old_row != new_row:
                    print(f"seed {seed} fused={fused} row {i} differs")
                    print(f"  old: {old_row}\n  new: {new_row}")
                    return False
            old_out, new_out = console_outputs(
                old_gate, old_settings, new_gate, new_settings, fused=fused
            )
            if old_out != new_out:
                print(f"seed {seed} fused={fused} console differs")
                print(f"  old: {old_out}\n  new: {new_out}")
                return False
            rows = [json.loads(row) for row in new_rows]
            verdicts = Counter(row["verdict"] for row in rows)
            locked = sum(row.get("lock_state") == "LOCKED" for row in rows)
            kind = "fusion" if fused else "audio-only"
            print(
                f"gates seed {seed} {kind}: {len(rows)} rows match, console "
                f"matches; verdicts={dict(verdicts)} locked_rows={locked}"
            )
    return True


# ---------------------------------------------------------------------------
# Part 2: SpeakerAudioProcessor (Pipecat) against SpeakerStream
# ---------------------------------------------------------------------------

FRAME_SAMPLES = 320  # 20 ms microphone frames
ROW_SAMPLES = 1280  # one 80 ms diarizer row per fake diarizer chunk
STT_DELAY = 0.3


class RowDiarizer:
    frame_secs = 0.08
    chunk_samples = ROW_SAMPLES

    def __init__(self, rows):
        self.rows = list(rows)

    def reset(self):
        pass

    def push(self, pcm):
        return np.array([self.rows.pop(0) if self.rows else (0.0, 0.0, 0.0, 0.0)])


class HalfSeparator:
    window_samples = ROW_SAMPLES * 20
    enroll_samples = ROW_SAMPLES * 2

    def separate(self, mix, enroll):
        return (mix * 0.5).astype(np.float32)


def stream_scenario(seed: int):
    rng = random.Random(1000 + seed)
    patterns = [
        (0.9, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.9, 0.9, 0.0, 0.0),
        (0.0, 0.9, 0.0, 0.0),
    ]
    rows, frames, bot = [], [], {}
    for _ in range(6):
        rows += [rng.choice(patterns)] * 4
    for _ in range(len(rows) * 4):
        if rng.random() < 0.05:
            bot[len(frames)] = rng.choice(["start", "stop"])
        level = rng.randrange(200, 4000)
        frames.append(np.full(FRAME_SAMPLES, level, np.int16).tobytes())
    return rows, frames, bot


def audio_only_gate(impl):
    return impl.gate(impl.settings(enabled=True))


def voice_locked_gate(impl):
    """Locked on track 7 / slot 0, whose voice already matches the customer."""
    now = time.time()
    faces = impl.faces()
    for k in range(-2, 60):
        faces.add(
            {
                "event": "faces",
                "ts": now + k * 0.1,
                "tracks": [{"track_id": 7, "distance_m": 0.8, "mouth_activity": 0.0}],
            }
        )
    gate = impl.fusion(impl.settings(**FUSION), faces, fsm_state=lambda: "active")
    gate.lock.observe_fsm("active", now - 1.0)
    for i in range(6):
        gate.lock.observe_row(
            now - 0.45 + i * 0.08, [0], anchor=7, anchor_asd_accept=True
        )
    gate.lock.voiceprint.enroll(np.ones(4, np.float32), 2.0)
    gate.lock.slots[0] = impl.slot_identity(voice_sim=0.9)
    return gate


async def run_old(gate, rows, frames, bot, *, separator, delay):
    from openjarvis.server.voice.speaker_audio import SpeakerAudioProcessor
    from openjarvis.server.voice.transcription import SttAudioFrame
    from openjarvis.server.voice.turn_detection import SpeakerVerdictFrame
    from pipecat.frames.frames import (
        BotStartedSpeakingFrame,
        BotStoppedSpeakingFrame,
        EndFrame,
        InputAudioRawFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    verdicts, stt = [], []

    class Collector(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, SpeakerVerdictFrame):
                verdicts.append(
                    (
                        frame.verdict.value,
                        frame.locked,
                        frame.overlap_target,
                        frame.source,
                    )
                )
            if isinstance(frame, SttAudioFrame):
                stt.append((frame.audio, frame.verdict, frame.reason))
            await self.push_frame(frame, direction)

    processor = SpeakerAudioProcessor(
        diarizer=RowDiarizer(rows),
        gate=gate,
        executor=ThreadPoolExecutor(max_workers=1),
        stt_delay_secs=delay,
        separator=separator,
        separator_executor=ThreadPoolExecutor(max_workers=1),
    )
    worker = PipelineWorker(
        Pipeline([processor, Collector()]),
        cancel_on_idle_timeout=False,
        enable_rtvi=False,
        enable_turn_tracking=False,
    )
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)

    async def drive():
        # Pipecat starts the pipeline asynchronously; feed audio only after the
        # processor has handled StartFrame, as SpeakerStream.start() returns.
        while processor._worker is None:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        for i, audio in enumerate(frames):
            event = bot.get(i)
            if event == "start":
                await processor.queue_frame(
                    BotStartedSpeakingFrame(), FrameDirection.UPSTREAM
                )
                await asyncio.sleep(0.01)
            elif event == "stop":
                await processor.queue_frame(
                    BotStoppedSpeakingFrame(), FrameDirection.UPSTREAM
                )
                await asyncio.sleep(0.01)
            await worker.queue_frame(
                InputAudioRawFrame(audio=audio, sample_rate=16_000, num_channels=1)
            )
            await asyncio.sleep(0.02)
        await asyncio.sleep(STT_DELAY + 0.2)
        await worker.queue_frame(EndFrame())

    await runner.add_workers(worker)
    await asyncio.wait_for(asyncio.gather(runner.run(), drive()), timeout=60)
    return verdicts, stt


async def run_new(gate, rows, frames, bot, *, separator, delay):
    verdicts, stt = [], []

    async def on_verdict(item):
        verdicts.append(
            (
                item.verdict.value,
                item.locked,
                item.overlap_target,
                item.source,
            )
        )

    async def on_stt_audio(item):
        stt.append((item.audio, item.verdict, item.reason))

    stream = SpeakerStream(
        diarizer=RowDiarizer(rows),
        gate=gate,
        executor=ThreadPoolExecutor(max_workers=1),
        stt_delay_secs=delay,
        separator=separator,
        separator_executor=ThreadPoolExecutor(max_workers=1),
        on_verdict=on_verdict,
        on_stt_audio=on_stt_audio,
    )
    await stream.start()
    await asyncio.sleep(0.05)
    for i, audio in enumerate(frames):
        event = bot.get(i)
        if event == "start":
            stream.bot_started()
            await asyncio.sleep(0.01)
        elif event == "stop":
            stream.bot_stopped()
            await asyncio.sleep(0.01)
        stream.push_audio(AudioChunk(audio=audio, sample_rate=16_000, num_channels=1))
        await asyncio.sleep(0.02)
    await asyncio.sleep(STT_DELAY + 0.2)
    await stream.finish()
    await stream.close()
    return verdicts, stt


def part_two() -> bool:
    configs = [
        ("audio-only", audio_only_gate, False, STT_DELAY),
        ("audio-only+tse", audio_only_gate, True, STT_DELAY),
        ("audio-only no-delay", audio_only_gate, False, 0.0),
        ("fusion-locked", voice_locked_gate, False, STT_DELAY),
        ("fusion-locked+tse", voice_locked_gate, True, STT_DELAY),
        ("fusion-locked no-delay", voice_locked_gate, False, 0.0),
    ]
    for seed in STREAM_SEEDS:
        rows, frames, bot = stream_scenario(seed)
        for name, build, tse, delay in configs:
            old = asyncio.run(
                run_old(
                    build(OLD),
                    rows,
                    frames,
                    bot,
                    separator=HalfSeparator() if tse else None,
                    delay=delay,
                )
            )
            new = asyncio.run(
                run_new(
                    build(NEW),
                    rows,
                    frames,
                    bot,
                    separator=HalfSeparator() if tse else None,
                    delay=delay,
                )
            )
            for label, old_items, new_items in (
                ("verdicts", old[0], new[0]),
                ("stt", old[1], new[1]),
            ):
                if old_items != new_items:
                    print(f"stream seed {seed} {name}: {label} differ")
                    print(f"  old: {len(old_items)} items, new: {len(new_items)}")
                    for i, (a, b) in enumerate(zip(old_items, new_items)):
                        if a != b:
                            print(f"  first difference at {i}: {a!r} != {b!r}")
                            break
                    return False
            reasons = Counter(reason for _, _, reason in new[1])
            print(
                f"stream seed {seed} {name}: {len(new[0])} verdicts and "
                f"{len(new[1])} STT chunks match; reasons={dict(reasons)}"
            )
    return True


# ---------------------------------------------------------------------------
# Part 0: syntax trees of the ported code
# ---------------------------------------------------------------------------

OJ_MODULES = [
    "speaker",
    "speaker_identity",
    "speaker_embedding",
    "speaker_audio",
    "speaker_vision",
    "speaker_console",
]
RENAMED = {
    "SpeakerAudioProcessor": "SpeakerStream",
    "LIVE_SPEAKER_KEYS": "SPEAKER_LIVE_KEYS",
}
# What the spec's API changes rewrite (settings path, console source, live
# keys, store, bridge save, logging, frames become calls); nothing else may
# differ. Members are compared one by one inside classes.
EXPECTED = {
    "load_speaker_settings": None,  # explicit path and table
    "save_speaker_values": None,  # became TomlSettingsStore
    "LIVE_SPEAKER_KEYS": None,  # the host's distance key became a LiveKey
    "logger": None,  # loguru -> logging
    "__all__": None,
    "SpeakerConsole": {"__init__", "tune", "values", "snapshot", "publish"},
    # save through the console; loguru "{}" -> logging "%s"
    "VisionAudioBridge": {"_console_command", "_send", "_run"},
    "SpeakerAudioProcessor": {
        "__doc__",  # "for Gemini (SttAudioFrame)" -> "for STT (SttAudio)"
        "__init__",
        "process_frame",
        "cleanup",
        "_diarize",  # push_frame -> _push_verdict
        "_push_stt",  # push_frame -> _deliver_stt
        "_stop",  # Pipecat cancel_task -> asyncio
        "_enqueue",  # InputAudioRawFrame -> AudioChunk annotations
        "_can_separate",
        "_separate",
    },
}


def _symbols(tree: ast.Module) -> dict[str, ast.AST]:
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                found[node.targets[0].id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found[node.target.id] = node
    return found


def _members(node: ast.ClassDef) -> dict[str, str]:
    members = {"__doc__": ast.get_docstring(node) or ""}
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            members[child.name] = ast.dump(child)
    return members


def part_zero() -> bool:
    ported: dict[str, list[ast.AST]] = {}
    for path in sorted(_audio_root().rglob("*.py")):
        for name, node in _symbols(ast.parse(path.read_text())).items():
            ported.setdefault(name, []).append(node)
    same, ok = 0, True
    for module in OJ_MODULES:
        origin = importlib.util.find_spec(f"openjarvis.server.voice.{module}").origin
        for name, node in _symbols(ast.parse(Path(origin).read_text())).items():
            expected = EXPECTED.get(name, set())
            if expected is None:
                continue
            candidates = ported.get(RENAMED.get(name, name), [])
            if not candidates:
                print(f"ast {module}.{name}: missing in audio")
                ok = False
                continue
            if isinstance(node, ast.ClassDef):
                old = _members(node)
                differs = set()
                for new_node in candidates:
                    new = _members(new_node)
                    differs = {
                        k for k in old.keys() | new.keys() if old.get(k) != new.get(k)
                    }
                    differs -= set(new) - set(old)  # members the port added
                    if differs <= expected:
                        break
                if not differs <= expected:
                    print(
                        f"ast {module}.{name}: unexpected {sorted(differs - expected)}"
                    )
                    ok = False
                    continue
            elif not any(ast.dump(node) == ast.dump(c) for c in candidates):
                print(f"ast {module}.{name}: differs")
                ok = False
                continue
            same += 1
    print(f"ast: {same} ported symbols match OpenJarvis up to the spec's API changes")
    return ok


def _audio_root() -> Path:
    return Path(importlib.util.find_spec("audio").origin).parent


def main() -> int:
    return 0 if part_zero() and part_one() and part_two() else 1


if __name__ == "__main__":
    sys.exit(main())
