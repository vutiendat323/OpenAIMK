"""Operator observations follow the gate; live tuning preserves its identity."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from audio.application.console import SpeakerConsole
from audio.domain.evidence import FaceTrackBuffer
from audio.domain.fusion import FusionGate
from audio.domain.settings import SpeakerSettings
from audio.domain.signal import audio_levels
from audio.domain.verdict import Verdict
from audio.infrastructure.config.toml_store import TomlSettingsStore
from audio.infrastructure.vision.asd_bridge import VisionAudioBridge


def _console():
    settings = SpeakerSettings(identity="fusion", vision_asd=True)
    gate = FusionGate(settings, FaceTrackBuffer(), fsm_state=lambda: "active")
    gate.lock.observe_fsm("active", 1.0)
    for i in range(settings.lock_asd_frames):
        gate.lock.observe_row(1.0 + i * 0.08, [0], anchor=7, anchor_asd_accept=True)
    bridge = VisionAudioBridge("ws://localhost:9876", "session", FaceTrackBuffer())
    source = SimpleNamespace(
        gate=gate,
        fusion=gate,
        bridge=bridge,
        bot_audible_until=0,
        tse_ready=False,
        stt_masked_no_verdict=3,
        bargein_blocked=2,
    )
    console = SpeakerConsole(source, settings)
    bridge.console = console
    return console


def test_audio_observations_are_bounded_and_do_not_overflow_int16():
    assert audio_levels(b"pcm")["rms_dbfs"] is None
    silence = audio_levels(np.zeros(320, np.int16).tobytes())
    assert silence["rms_dbfs"] == -96 and silence["peak"] == 0
    loud = audio_levels(np.full(4000, -32768, np.int16).tobytes())
    assert loud["rms_dbfs"] == 0 and loud["peak"] == 1
    assert len(loud["waveform"]) <= 64


def test_live_thresholds_reach_the_gate_and_lock_without_resetting_identity():
    console = _console()
    gate = console.source.gate
    assert gate.lock.locked
    before = (gate.lock.epoch, gate.lock.target_track, set(gate.lock.target_slots))
    console.tune("asd_accept_prob", 0.8)
    console.tune("voice_match", 0.75)
    console.tune("mouth_active", 0.6)
    assert gate._asd_accept == 0.8 and gate._mouth_active == 0.6
    assert gate.lock._s.voice_match == 0.75
    assert before == (gate.lock.epoch, gate.lock.target_track, gate.lock.target_slots)


@pytest.mark.parametrize(
    "key,value",
    [
        ("voice_match", 0.4),
        ("voice_reject", 0.8),
        ("asd_accept_prob", 0.2),
        ("asd_reject_prob", 0.9),
        ("mouth_active", float("nan")),
        ("mouth_active", True),
        ("identity", "none"),
    ],
)
def test_invalid_live_changes_leave_the_gate_settings_intact(key, value):
    console = _console()
    before = console.settings
    with pytest.raises(ValueError):
        console.tune(key, value)
    assert console.settings is before
    assert console.source.gate.settings is before


def test_snapshot_uses_actual_verdict_and_counters():
    console = _console()
    console.verdict(Verdict.REJECT, 12.0)
    snapshot = console.snapshot()
    assert snapshot["verdict"] == Verdict.REJECT.value
    assert snapshot["verdict_ts"] == 12
    assert snapshot["target_track"] == 7 and snapshot["locked"]
    assert snapshot["stt_masked_no_verdict_frames"] == 3
    assert snapshot["bargein_blocked"] == 2
    assert snapshot["audio"]["ts"] is None
    json.dumps(snapshot, allow_nan=False)


def test_save_updates_only_speaker_values_and_preserves_preset_comments(tmp_path):
    path = tmp_path / "preset.toml"
    path.write_text(
        "# merchant configuration\n[agent]\nmax_turns = 8\n"
        "[voice.speaker]\nvoice_match = 0.65 # tuned\n"
    )
    TomlSettingsStore(path).save({"voice_match": 0.8})
    source = path.read_text()
    assert "max_turns = 8" in source and "# merchant configuration" in source
    assert "voice_match = 0.8 # tuned" in source
    assert not list(tmp_path.glob(".console-*"))


@pytest.mark.asyncio
async def test_console_commands_return_gate_confirmation():
    console = _console()
    bridge = console.source.bridge
    bridge._stream_id = "stream"
    sent = []

    async def send(payload):
        sent.append(json.loads(payload))

    await bridge._console_command(
        SimpleNamespace(send=send),
        {
            "request_id": "request",
            "action": "set",
            "key": "voice_match",
            "value": 0.8,
        },
        "stream",
    )
    assert sent == [
        {
            "cmd": "voice_command_result",
            "stream_id": "stream",
            "request_id": "request",
            "ok": True,
            "key": "voice_match",
            "value": 0.8,
        }
    ]
    assert console.source.gate.lock._s.voice_match == 0.8
