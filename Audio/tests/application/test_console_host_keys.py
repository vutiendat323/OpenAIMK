"""Host-owned live keys, settings stores and degraded sources on the console."""

import asyncio
import json
import time
import tomllib
from types import SimpleNamespace

import pytest

from audio.application.console import SpeakerConsole
from audio.application.ports import LiveKey
from audio.domain.evidence import FaceTrackBuffer
from audio.domain.fusion import FusionGate
from audio.domain.gate import AudioOnlyGate
from audio.domain.settings import SpeakerSettings
from audio.infrastructure.config.toml_store import TomlSettingsStore
from audio.infrastructure.vision.asd_bridge import VisionAudioBridge

SPEAKER_KEYS = [
    "anchor_max_m",
    "mouth_active",
    "asd_accept_prob",
    "asd_reject_prob",
    "voice_match",
    "voice_reject",
    "bot_match",
]


class Bridge:
    def __init__(self):
        self.asd_late = 0
        self.asd_age_ms = []
        self.snapshots = []

    def offer_telemetry(self, snapshot):
        self.snapshots.append(snapshot)


class Monitor:
    def __init__(self):
        self.enabled = False

    def set_enabled(self, value):
        self.enabled = value

    def snapshot(self):
        return {"enabled": self.enabled}


class Store:
    def __init__(self):
        self.saved = []

    def save(self, values):
        self.saved.append(dict(values))


def _console(*, fused=True, **kwargs):
    settings = SpeakerSettings(identity="fusion", vision_asd=True)
    if fused:
        gate = FusionGate(settings, FaceTrackBuffer(), fsm_state=lambda: "active")
    else:
        gate = AudioOnlyGate(settings, FaceTrackBuffer())
    source = SimpleNamespace(
        gate=gate,
        fusion=gate if fused else None,
        bridge=Bridge(),
        bot_audible_until=0.0,
        tse_ready=False,
        stt_masked_no_verdict=0,
        bargein_blocked=0,
    )
    return SpeakerConsole(source, settings, **kwargs)


def _distance_key(cell):
    return LiveKey(
        "approach_threshold_m",
        (0.1, 6.0),
        lambda: cell[0],
        lambda value: cell.__setitem__(0, value),
    )


def test_host_key_is_tuned_through_its_setter_and_listed_first():
    distance = [1.0]
    console = _console(live_keys=(_distance_key(distance),))
    assert console.tune("approach_threshold_m", 1.4) == {
        "key": "approach_threshold_m",
        "value": 1.4,
    }
    assert distance == [1.4]
    assert list(console.values()) == ["approach_threshold_m", *SPEAKER_KEYS]
    snapshot = console.snapshot()
    assert snapshot["settings"]["approach_threshold_m"] == 1.4
    assert list(snapshot["bounds"]) == ["approach_threshold_m", *SPEAKER_KEYS]
    assert snapshot["bounds"]["approach_threshold_m"] == [0.1, 6.0]


@pytest.mark.parametrize("value", [0.05, 6.5, float("nan"), True, "1.0"])
def test_host_key_rejects_values_outside_its_bounds(value):
    distance = [1.0]
    console = _console(live_keys=(_distance_key(distance),))
    with pytest.raises(ValueError):
        console.tune("approach_threshold_m", value)
    assert distance == [1.0]


def test_without_host_keys_the_console_lists_only_speaker_settings():
    console = _console()
    assert list(console.values()) == SPEAKER_KEYS
    with pytest.raises(ValueError, match="Unsupported setting"):
        console.tune("approach_threshold_m", 1.0)


def test_a_host_key_may_not_shadow_a_speaker_setting():
    shadow = LiveKey("voice_match", (0.0, 1.0), lambda: 0.5, lambda value: None)
    with pytest.raises(ValueError, match="overlap"):
        _console(live_keys=(shadow,))


def test_save_without_a_store_is_refused():
    with pytest.raises(ValueError, match="No settings store configured"):
        _console().save({"voice_match": 0.7})


def test_save_writes_host_keys_to_their_own_table(tmp_path):
    path = tmp_path / "preset.toml"
    path.write_text("# kiosk preset\n[voice.speaker]\nvoice_match = 0.65 # tuned\n")
    store = TomlSettingsStore(path, key_tables={"approach_threshold_m": ("kiosk",)})
    console = _console(live_keys=(_distance_key([1.4]),), store=store)
    console.save(console.values())
    text = path.read_text()
    saved = tomllib.loads(text)
    assert saved["kiosk"]["approach_threshold_m"] == 1.4
    assert saved["voice"]["speaker"]["voice_match"] == 0.65
    assert text.startswith("# kiosk preset\n") and "# tuned" in text
    assert not list(tmp_path.glob(".console-*"))


def test_store_rejects_unknown_keys_and_leaves_the_file_alone(tmp_path):
    path = tmp_path / "preset.toml"
    path.write_text("[voice.speaker]\nvoice_match = 0.65\n")
    with pytest.raises(ValueError, match="Unsupported speaker setting"):
        TomlSettingsStore(path).save({"voice_match": 0.7, "identity": 1.0})
    assert path.read_text() == "[voice.speaker]\nvoice_match = 0.65\n"
    assert not list(tmp_path.glob(".console-*"))


def test_store_refuses_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        TomlSettingsStore(tmp_path / "absent.toml").save({"voice_match": 0.7})


def test_snapshot_without_fusion_reports_no_lock():
    snapshot = _console(fused=False).snapshot()
    assert (snapshot["locked"], snapshot["lock_state"], snapshot["target_track"]) == (
        False,
        "NONE",
        None,
    )
    assert snapshot["echo_rejects"] == 0
    json.dumps(snapshot, allow_nan=False)


def _bridge_for(console):
    bridge = VisionAudioBridge("ws://vision", "session", FaceTrackBuffer())
    bridge.console = console
    bridge._stream_id = "stream"
    return bridge


@pytest.mark.anyio
async def test_monitor_toggle_round_trips_through_the_bridge_and_is_never_saved(
    tmp_path,
):
    console = _console(target_audio_monitor=Monitor())
    bridge = _bridge_for(console)
    sent = []

    async def send(payload):
        sent.append(json.loads(payload))

    before = console.settings
    for enabled in (True, False):
        await bridge._console_command(
            SimpleNamespace(send=send),
            {
                "request_id": "toggle",
                "action": "set",
                "key": "target_audio_monitor",
                "value": enabled,
            },
            "stream",
        )
        assert sent[-1]["ok"] and sent[-1]["value"] is enabled
        assert console.snapshot()["target_audio_monitor"] == {"enabled": enabled}
    assert console.settings is before
    assert "target_audio_monitor" not in console.values()
    preset = tmp_path / "preset.toml"
    preset.write_text("[voice.speaker]\nvoice_match = 0.65\n")
    TomlSettingsStore(preset).save(console.values())
    assert "target_audio_monitor" not in preset.read_text()
    for invalid in (0, 1, "true", None):
        with pytest.raises(ValueError, match="ON or OFF"):
            console.tune("target_audio_monitor", invalid)


@pytest.mark.anyio
async def test_slow_monitor_control_does_not_block_the_event_loop():
    class SlowMonitor(Monitor):
        def set_enabled(self, value):
            time.sleep(0.2)
            super().set_enabled(value)

    bridge = _bridge_for(_console(target_audio_monitor=SlowMonitor()))

    async def send(payload):
        pass

    task = asyncio.create_task(
        bridge._console_command(
            SimpleNamespace(send=send),
            {"action": "set", "key": "target_audio_monitor", "value": True},
            "stream",
        )
    )
    await asyncio.sleep(0.03)
    assert not task.done(), "Device control blocked the event loop"
    await task


@pytest.mark.parametrize(
    "names", [("target_audio_monitor",), ("approach_threshold_m",) * 2]
)
def test_console_refuses_a_reserved_or_repeated_host_key(names):
    keys = tuple(
        LiveKey(name, (0.1, 6.0), lambda: 1.0, lambda v: None) for name in names
    )
    with pytest.raises(ValueError):
        _console(live_keys=keys)


def test_store_refuses_another_table_for_a_speaker_key(tmp_path):
    with pytest.raises(ValueError, match="voice_match"):
        TomlSettingsStore(
            tmp_path / "preset.toml", key_tables={"voice_match": ("kiosk",)}
        )


@pytest.mark.anyio
async def test_bridge_save_command_writes_through_the_console_store():
    store = Store()
    console = _console(store=store)
    bridge = VisionAudioBridge("ws://vision", "session", FaceTrackBuffer())
    bridge.console = console
    bridge._stream_id = "stream"
    sent = []

    async def send(payload):
        sent.append(json.loads(payload))

    await bridge._console_command(
        SimpleNamespace(send=send),
        {"request_id": "request", "action": "save"},
        "stream",
    )
    assert sent == [
        {
            "cmd": "voice_command_result",
            "stream_id": "stream",
            "request_id": "request",
            "ok": True,
        }
    ]
    assert store.saved == [console.values()]
