"""Mission Control rendering, session ownership, freshness and saved settings."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from Visual.application.state import SharedState
from Visual.presentation.console_settings import save_live_values
from Visual.presentation.ws_server import VisionWSServer


def _server(path=None):
    cfg = SimpleNamespace(face_ipd_m=0.063, distance_threshold=1.0,
                          asd_audio_offset_secs=0.0,
                          camera_id=0, camera_width=640, camera_height=480)
    return VisionWSServer(SharedState(), cfg=cfg, config_path=str(path) if path else None)


def test_console_renders_modular_templates_and_hides_template_sources():
    server = _server()
    conn = MagicMock()
    conn.respond.side_effect = lambda status, text: Response(
        status, "OK", Headers(), text.encode())
    for route in ("/", "/console", "/console/", "/index.html"):
        response = server._process_request(conn, Request(route, Headers()))
        assert response.status_code == 200
        assert b"Mission Control" in response.body
        assert b"{%" not in response.body and b"{{" not in response.body
        for identifier in (b'"feed"', b'"waveform"', b'"verdict"', b'"tuning-drawer"',
                           b'"target-audio-toggle"'):
            assert identifier in response.body
        assert response.headers["Cache-Control"] == "no-store"
    for route in ("/templates/base.html", "/templates/dashboard.html", "/js/../../ws_server.py"):
        assert server._process_request(conn, Request(route, Headers())).status_code == 404


def test_only_stream_owner_can_publish_and_stale_observations_are_removed(monkeypatch):
    server = _server()
    owner, intruder = object(), object()
    start = {"stream_id": "stream", "session_id": "session"}
    assert server._start_voice_monitor(owner, start)["status"] == "ready"
    assert server._start_voice_monitor(intruder, start)["status"] == "busy"
    packet = {"stream_id": "stream", "data": {"verdict": "ACCEPT"}}
    server._voice_telemetry(intruder, packet)
    assert server._voice_data is None
    server._voice_telemetry(owner, {**packet, "stream_id": "wrong"})
    assert server._voice_data is None
    server._voice_telemetry(owner, packet)
    assert server._voice_event()["status"] == "live"
    now = server._voice_received_at
    monkeypatch.setattr("Visual.presentation.ws_server.time.monotonic", lambda: now + 2)
    assert server._voice_event() == {"status": "stale", "session_id": "session", "data": None}
    server._release_voice_monitor(intruder)
    assert server._voice_owner is owner
    server._release_voice_monitor(owner)
    assert server._voice_event()["status"] == "idle"


def test_nonfinite_telemetry_never_reaches_console_clients():
    server, owner = _server(), object()
    server._start_voice_monitor(owner, {"stream_id": "s", "session_id": "session"})
    server._voice_telemetry(owner, {"stream_id": "s", "data": {"score": float("nan")}})
    assert server._voice_data is None


def test_audio_video_offset_is_live_and_range_checked():
    server = _server()
    assert server._apply_set({"key": "asd_audio_offset_secs", "value": -0.12})["ok"]
    assert server._cfg.asd_audio_offset_secs == -0.12
    assert not server._apply_set({"key": "asd_audio_offset_secs", "value": 2})["ok"]


def test_save_preserves_other_yaml_keys_comments_and_file_permissions(tmp_path):
    path = tmp_path / "vision.yml"
    path.write_text('# operator config\nface_ipd_m: 0.063 # personal IPD\n'
                    'camera_id: 1\nmodel_path: /weights/model.onnx\n')
    path.chmod(0o640)
    save_live_values(str(path), {"face_ipd_m": 0.066, "asd_audio_offset_secs": -0.12})
    source = path.read_text()
    assert "# operator config" in source and "# personal IPD" in source
    assert "camera_id: 1" in source and "model_path: /weights/model.onnx" in source
    assert "face_ipd_m: 0.066" in source and "asd_audio_offset_secs: -0.12" in source
    assert path.stat().st_mode & 0o777 == 0o640


@pytest.mark.asyncio
async def test_voice_control_round_trip_requires_owner_and_matching_stream():
    server = _server()

    async def send(payload):
        command = json.loads(payload)
        reply = {"stream_id": "s", "request_id": command["request_id"],
                 "ok": True, "key": "voice_match", "value": 0.75}
        server._voice_command_result(object(), reply)
        assert not server._voice_pending[command["request_id"]].done()
        server._voice_command_result(owner, {**reply, "stream_id": "old"})
        assert not server._voice_pending[command["request_id"]].done()
        server._voice_command_result(owner, reply)

    owner = SimpleNamespace(send=send)
    server._start_voice_monitor(owner, {"stream_id": "s", "session_id": "session"})
    result = await server._voice_command("set", key="voice_match", value=0.75)
    assert result["ok"] and result["value"] == 0.75
    assert not server._voice_pending


@pytest.mark.asyncio
async def test_console_monitor_toggle_forwards_control_only_and_confirms_boolean():
    server = _server()
    commands, replies = [], []

    async def send_command(payload):
        command = json.loads(payload)
        commands.append(command)
        server._voice_command_result(owner, {
            "stream_id": "s", "request_id": command["request_id"],
            "ok": True, "key": command["key"], "value": command["value"],
        })

    async def send_reply(payload):
        replies.append(json.loads(payload))

    owner = SimpleNamespace(send=send_command)
    console = MagicMock(send=send_reply)
    server._monitors.add(console)
    server._start_voice_monitor(owner, {"stream_id": "s", "session_id": "session"})
    for enabled in (True, False):
        await server._on_message(console, json.dumps({
            "cmd": "voice_set", "key": "target_audio_monitor", "value": enabled,
        }))
        assert commands[-1]["action"] == "set"
        assert commands[-1]["value"] is enabled
        assert set(commands[-1]) == {
            "event", "stream_id", "request_id", "action", "key", "value",
        }
        assert replies[-1]["ok"] and replies[-1]["value"] is enabled


@pytest.mark.asyncio
async def test_disconnect_resolves_pending_controls_without_a_success_claim():
    server, owner = _server(), object()
    server._start_voice_monitor(owner, {"stream_id": "s", "session_id": "session"})
    future = asyncio.get_running_loop().create_future()
    server._voice_pending["request"] = future
    server._release_voice_monitor(owner)
    assert (await future)["ok"] is False


@pytest.mark.asyncio
async def test_save_without_voice_reports_vision_only_and_uses_active_file(tmp_path):
    path = tmp_path / "active.yml"
    path.write_text("camera_id: 0\n")
    server = _server(path)
    result = await server._save_settings()
    assert result["ok"] and result["vision"]["ok"] and result["voice"]["skipped"]
    assert "face_ipd_m: 0.063" in path.read_text()


@pytest.mark.asyncio
async def test_invalid_yaml_save_reports_failure_and_keeps_the_file(tmp_path):
    path = tmp_path / "active.yml"
    source = "camera_id: [\n"
    path.write_text(source)
    result = await _server(path)._save_settings()
    assert not result["ok"] and "invalid YAML" in result["vision"]["error"]
    assert path.read_text() == source
