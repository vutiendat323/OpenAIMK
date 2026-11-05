#!/usr/bin/env python3
"""Prepare boundary clips with the same native v3 voices used by the kiosk.

Run: PYTHONPATH=. .venv/bin/python scripts/prepare_voice_clips.py
Only the two fixed source recordings are sent as synthetic input. No customer
microphone, business tool, merchant action or unrelated application is used.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import re
import subprocess
import time
import wave
from pathlib import Path

from av import AudioResampler
from av import open as av_open

from trendcoffee.codex_voice import CodexVoice
from trendcoffee.kiosk import BOUNDARY_TEXT

ROOT = Path(__file__).resolve().parent.parent
VOICE_CLIPS = ROOT / "frontend/public/voice"
# VoicePlayer accepts at most 600,000 base64 characters in one chunk.
MAX_PCM_BYTES = 450000


def validate_capture(text, transcript, packets):
    def normalize(value):
        return re.sub(r"[\W_]+", "", value).casefold()

    if not transcript or normalize(transcript) != normalize(text):
        raise ValueError(f"unexpected speech transcript: {transcript!r}")
    if any(p["sampleRate"] != 48000 or p["numChannels"] != 1 for p in packets):
        raise ValueError("inconsistent speech audio format")
    pcm = b"".join(base64.b64decode(p["data"], validate=True) for p in packets)
    if not pcm or len(pcm) % 2 or len(pcm) > MAX_PCM_BYTES or not any(pcm):
        raise ValueError("empty, silent or invalid speech audio")
    return pcm


class BoundaryRenderer(CodexVoice):
    async def request(self, method, params, **kwargs):
        if method == "thread/realtime/start":
            params = {
                **params,
                "prompt": (
                    "Repeat exactly what the user says, in Vietnamese. No additions, no "
                    "commentary, no delegation and no tools. Do not answer the sentence as "
                    "a question; only repeat it. The user will say one of these sentences: "
                    + " / ".join(BOUNDARY_TEXT.values())
                ),
                "realtimeStartInstructions": "Repeat only the exact Vietnamese user sentence.",
                "initialItems": [],
                "delegationAckFiller": False,
            }
        return await super().request(method, params, **kwargs)


def source_pcm(kind):
    resampler = AudioResampler(format="s16", layout="mono", rate=16000)
    pcm = bytearray()
    with av_open(str(VOICE_CLIPS / f"{kind}.wav")) as source:
        for frame in source.decode(audio=0):
            for output in resampler.resample(frame):
                pcm.extend(bytes(output.planes[0])[: output.samples * 2])
        for output in resampler.resample(None):
            pcm.extend(bytes(output.planes[0])[: output.samples * 2])
    return bytes(pcm)


async def render(native, voice, kinds):
    packets, transcripts = [], []
    last_audio = 0
    failed = False

    async def reject_tool(params):
        raise RuntimeError("no_business_tools_in_boundary_rendering")

    async def event(method, params):
        nonlocal last_audio, failed
        if method.endswith(("/error", "/closed")):
            failed = True
        elif method.endswith("outputAudio/delta"):
            if len(packets) >= 600:
                failed = True
                return
            packets.append(params["audio"])
            last_audio = time.monotonic()
        elif method.endswith("transcript/done") and params.get("role") == "assistant":
            transcripts.append(params.get("text", ""))

    native.voice = voice
    thread = await native.create_thread([], reject_tool, event)
    try:
        await native.start_filtered_voice(thread)
        for kind in kinds:
            packets.clear()
            transcripts.clear()
            last_audio = 0
            pcm = source_pcm(kind)
            for offset in range(0, len(pcm), 2560):
                await native.append_audio(thread, pcm[offset : offset + 2560].ljust(2560, b"\0"))
                await asyncio.sleep(0.08)
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if failed:
                    raise RuntimeError("native_boundary_rendering_failed")
                if packets and transcripts and time.monotonic() - last_audio >= 0.6:
                    break
                await asyncio.sleep(0.1)
            transcript = " ".join(transcripts)
            pcm = validate_capture(BOUNDARY_TEXT[kind], transcript, packets)
            yield kind, pcm, transcript
    finally:
        await native.stop_voice(thread)


def existing_clip(voice, kind, record):
    if record.get("text") != BOUNDARY_TEXT[kind]:
        return False
    try:
        with wave.open(str(VOICE_CLIPS / voice / f"{kind}.wav")) as source:
            pcm = source.readframes(source.getnframes())
            return (
                source.getframerate() == 48000
                and source.getnchannels() == 1
                and source.getsampwidth() == 2
                and 0 < len(pcm) <= MAX_PCM_BYTES
                and hashlib.sha256(pcm).hexdigest() == record.get("sha256")
            )
    except (OSError, wave.Error):
        return False


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice", action="append", help="Prepare just this voice; default is all.")
    parser.add_argument(
        "--force", action="store_true", help="Regenerate previously verified clips."
    )
    args = parser.parse_args()
    native = BoundaryRenderer(ROOT)
    manifest_path = VOICE_CLIPS / "catalog.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"voices": {}}
    unavailable = manifest.setdefault("unavailable", {})
    manifest["renderer"] = subprocess.check_output(
        [native.executable, "--version"], text=True
    ).strip()
    failures = []
    try:
        catalog = await native.list_voices()
        manifest["native_catalog"] = catalog
        names = args.voice or ["default", "maple", "rio", "cove", *catalog]
        if any(name not in ["default", *catalog] for name in names):
            raise ValueError("A requested voice is not in the native v3 catalog")
        for name in dict.fromkeys(names):
            voice = None if name == "default" else name
            records = manifest["voices"].setdefault(name, {})
            for attempt in range(3):
                kinds = [
                    kind
                    for kind in BOUNDARY_TEXT
                    if args.force or not existing_clip(name, kind, records.get(kind, {}))
                ]
                if not kinds:
                    break
                try:
                    async for kind, pcm, transcript in render(native, voice, kinds):
                        directory = VOICE_CLIPS / name
                        directory.mkdir(parents=True, exist_ok=True)
                        temporary = directory / f".{kind}.tmp.wav"
                        with wave.open(str(temporary), "wb") as target:
                            target.setnchannels(1)
                            target.setsampwidth(2)
                            target.setframerate(48000)
                            target.writeframes(pcm)
                        temporary.replace(directory / f"{kind}.wav")
                        records[kind] = {
                            "voice": voice,
                            "version": "v3",
                            "text": BOUNDARY_TEXT[kind],
                            "transcript": BOUNDARY_TEXT[kind],
                            "native_transcript": transcript,
                            "sha256": hashlib.sha256(pcm).hexdigest(),
                            "seconds": round(len(pcm) / 96000, 3),
                        }
                        if set(records) == set(BOUNDARY_TEXT):
                            unavailable.pop(name, None)
                        temporary_manifest = manifest_path.with_suffix(".tmp.json")
                        temporary_manifest.write_text(
                            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
                        )
                        temporary_manifest.replace(manifest_path)
                        print(f"{name}: {kind} verified ({len(pcm) / 96000:.2f}s)", flush=True)
                    break
                except (RuntimeError, ValueError, TimeoutError) as exc:
                    print(
                        f"{name}: attempt {attempt + 1} failed: {type(exc).__name__}: {exc}",
                        flush=True,
                    )
                    if attempt == 2:
                        failures.append(name)
                        unavailable[name] = {"reason": f"{type(exc).__name__}: {exc}"}
                        temporary_manifest = manifest_path.with_suffix(".tmp.json")
                        temporary_manifest.write_text(
                            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
                        )
                        temporary_manifest.replace(manifest_path)
        if failures:
            raise SystemExit("Clips not prepared: " + ", ".join(failures))
    finally:
        await native.close()


if __name__ == "__main__":
    asyncio.run(main())
