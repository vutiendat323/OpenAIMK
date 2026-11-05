import os
import subprocess
import sys

from scripts.kiosk import identity


def test_ditto_manifest_selects_owned_server_and_source(tmp_path, monkeypatch):
    import json

    from scripts import kiosk

    monkeypatch.setattr(kiosk, "ROOT", tmp_path)
    (tmp_path / "source.mp4").touch()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/ditto_server.py").touch()
    manifest = tmp_path / "avatar.json"
    manifest.write_text(
        json.dumps(
            {
                "engine": "ditto",
                "source": "source.mp4",
                "gpu_budget": 0.8,
                "render_fps": 20,
                "motion_stride_ms": 160,
                "renderer_backend": "tensorrt",
                "expression_mode": "source-relative",
                "lip_opening_limit": 0.035,
                "composite": "full-face",
                "closed_source": True,
                "presentation_lead_ms": 360,
                "reference_frame": 0,
                "lip_factor": 0.5,
                "lip_width": 0.5,
                "whole_head": True,
                "wave": False,
            }
        )
    )
    command = kiosk.avatar_command(["old-server"], manifest)
    assert str(tmp_path / "scripts/ditto_server.py") in command
    assert command[command.index("--source") + 1] == str(tmp_path / "source.mp4")
    assert "old-server" not in command
    assert command[command.index("--gpu-budget") + 1] == "0.8"
    assert command[command.index("--render-fps") + 1] == "20"
    assert command[command.index("--motion-stride-ms") + 1] == "160"
    assert command[command.index("--renderer-backend") + 1] == "tensorrt"
    assert command[command.index("--expression-mode") + 1] == "source-relative"
    assert command[command.index("--lip-opening-limit") + 1] == "0.035"
    assert command[command.index("--composite") + 1] == "full-face"
    assert "--closed-source" in command
    assert command[command.index("--presentation-lead-ms") + 1] == "360"
    assert command[command.index("--reference-frame") + 1] == "0"
    assert command[command.index("--lip-factor") + 1] == "0.5"
    assert command[command.index("--lip-width") + 1] == "0.5"
    assert "--whole-head" in command
    assert "--no-wave" in command


def test_missing_ditto_source_fails_before_start(tmp_path):
    import json

    import pytest

    from scripts import kiosk

    manifest = tmp_path / "avatar.json"
    manifest.write_text(json.dumps({"engine": "ditto", "source": str(tmp_path / "absent.mp4")}))
    with pytest.raises(ValueError, match="source video missing"):
        kiosk.avatar_command([], manifest)


def test_exited_process_is_not_reported_as_running():
    child = subprocess.Popen([sys.executable, "-c", "pass", "trendcoffee"])
    try:
        os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT)
        assert identity(child.pid) is None
    finally:
        child.wait()


def test_stop_waits_for_exit_after_port_has_closed(monkeypatch, tmp_path):
    from scripts import kiosk

    checks = []
    monkeypatch.setattr(kiosk, "RUNTIME", tmp_path)
    monkeypatch.setattr(sys, "argv", ["kiosk.py", "stop", "--service", "api"])
    monkeypatch.setattr(kiosk, "record", lambda name: {"pid": 123456, "started": "test"})
    monkeypatch.setattr(kiosk.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(kiosk.os, "killpg", lambda *args: None)
    monkeypatch.setattr(kiosk.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(kiosk, "listening", lambda port: False)

    def identity(pid):
        checks.append(pid)
        return "still_closing" if len(checks) < 4 else None

    monkeypatch.setattr(kiosk, "identity", identity)
    kiosk.main()
    assert len(checks) == 4


def test_avatar_remains_owned_after_changing_into_checkout(monkeypatch, tmp_path):
    from scripts import kiosk

    monkeypatch.setattr(kiosk, "ROOT", tmp_path)
    checkout = tmp_path / ".runtime/LiveTalking"
    checkout.mkdir(parents=True)

    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; print('ready', flush=True); time.sleep(10)",
            str(tmp_path / "scripts/livetalking_local.py"),
        ],
        cwd=checkout,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        assert identity(child.pid) is not None
    finally:
        child.terminate()
        child.wait()


def test_manifest_passes_the_rest_clip_and_head_drive(tmp_path, monkeypatch):
    import json

    from scripts import kiosk

    monkeypatch.setattr(kiosk, "ROOT", tmp_path)
    for name in ("source.mp4", "rest.mp4"):
        (tmp_path / name).touch()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/ditto_server.py").touch()
    manifest = tmp_path / "avatar.json"
    manifest.write_text(
        json.dumps(
            {
                "engine": "ditto",
                "source": "source.mp4",
                "rest_source": "rest.mp4",
                "drive_head": True,
                "head_gain": 0.4,
                "turn_gain": 0.25,
                "composite": "full-face",
            }
        )
    )
    command = kiosk.avatar_command(["old-server"], manifest)
    assert command[command.index("--turn-gain") + 1] == "0.25"
    assert command[command.index("--rest-source") + 1] == str(tmp_path / "rest.mp4")
    assert "--drive-head" in command
    assert command[command.index("--head-gain") + 1] == "0.4"


def test_missing_rest_clip_fails_before_start(tmp_path, monkeypatch):
    import json

    import pytest

    from scripts import kiosk

    monkeypatch.setattr(kiosk, "ROOT", tmp_path)
    (tmp_path / "source.mp4").touch()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/ditto_server.py").touch()
    manifest = tmp_path / "avatar.json"
    manifest.write_text(
        json.dumps({"engine": "ditto", "source": "source.mp4", "rest_source": "missing.mp4"})
    )
    with pytest.raises(ValueError, match="rest"):
        kiosk.avatar_command(["old-server"], manifest)
