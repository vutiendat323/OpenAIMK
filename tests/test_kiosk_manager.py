"""Kiosk Manager: the logic behind the desktop window that starts and stops the services.

Nothing here starts a real service or opens a window; the launcher and the network are faked.
"""

import json
import os
import stat
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from scripts import kiosk
from scripts import kiosk_manager as manager


def test_a_service_is_running_only_when_owned_and_listening(monkeypatch):
    owned = {"api": True, "visual": True, "avatar": False}
    ports = {8080: True, 9877: False, 8010: True}
    monkeypatch.setattr(kiosk, "record", lambda name: {"pid": 1} if owned[name] else None)
    monkeypatch.setattr(kiosk, "listening", lambda port: ports[port])
    assert manager.service_state("api") == "running"
    assert manager.service_state("visual") == "starting", "owned, port not ready yet"
    assert manager.service_state("avatar") == "other", "port taken by a process we do not own"
    ports[8010] = False
    assert manager.service_state("avatar") == "stopped"


def serve(payload):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_kiosk_activity_is_read_from_the_api_and_unreachable_means_unknown():
    server = serve({"session_active": True})
    try:
        assert manager.fetch_kiosk(port=server.server_port) == {"session_active": True}
    finally:
        server.shutdown()
    assert manager.fetch_kiosk(port=server.server_port) is None


@pytest.mark.parametrize(
    "action,status,warn",
    [
        ("start", {"session_active": True}, False),
        ("stop", {"session_active": True}, True),
        ("restart", {"session_active": True}, True),
        ("restart", {"session_active": False}, False),
        ("stop", None, False),  # the API is down: nobody to protect
    ],
)
def test_stopping_or_restarting_warns_only_while_a_guest_is_served(action, status, warn):
    assert manager.guest_would_be_cut(action, status) is warn


def test_a_command_runs_the_launcher_with_the_staff_code(monkeypatch):
    calls = []

    class Done:
        returncode = 0
        stdout = "api: running pid 5; port 8080 listening\n"
        stderr = ""

    def run(command, **kwargs):
        calls.append((command, kwargs["env"].get("TREND_STAFF_TOKEN")))
        return Done()

    monkeypatch.setattr(manager.subprocess, "run", run)
    ok, message = manager.run_launcher("restart", "api", staff_token="TREND_STAFF")
    assert ok and "running" in message
    assert [c[0][-1] for c in calls] == ["stop", "start"], "restart = stop, then start"
    assert all(c[0][c[0].index("--service") + 1] == "api" for c in calls)
    assert all(token == "TREND_STAFF" for _, token in calls)


def test_a_failed_launcher_reports_its_reason_in_plain_words(monkeypatch):
    class Failed:
        returncode = 1
        stdout = ""
        stderr = "api: port 8080 is already in use; no unrelated process was stopped\n"

    monkeypatch.setattr(manager.subprocess, "run", lambda *a, **k: Failed())
    ok, message = manager.run_launcher("start", "api")
    assert not ok
    assert "port 8080 is already in use" in message


def test_the_staff_code_comes_from_the_environment_then_the_saved_file(monkeypatch, tmp_path):
    path = tmp_path / "manager.json"
    monkeypatch.delenv("TREND_STAFF_TOKEN", raising=False)
    settings = manager.load_settings(path)
    assert settings == {"staff_token": "", "auto_restart": False}
    manager.save_settings({"staff_token": "SECRET", "auto_restart": True}, path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600, "the code is private to the user"
    assert manager.load_settings(path)["staff_token"] == "SECRET"
    monkeypatch.setenv("TREND_STAFF_TOKEN", "FROM_ENV")
    assert manager.load_settings(path)["staff_token"] == "FROM_ENV"
    assert manager.load_settings(path, use_env=False)["staff_token"] == "SECRET"
    path.write_text("not json")
    assert manager.load_settings(path)["auto_restart"] is False, "a damaged file is ignored"


def test_a_service_that_died_by_itself_is_restarted_with_limits():
    watch = manager.Watchdog(cooldown=30, max_restarts=2, window=600)
    assert not watch.should_restart("api", "stopped", wanted=False, now=0)
    assert not watch.should_restart("api", "running", wanted=True, now=0)
    assert watch.should_restart("api", "stopped", wanted=True, now=0)
    assert not watch.should_restart("api", "stopped", wanted=True, now=10), "cooldown"
    assert watch.should_restart("api", "stopped", wanted=True, now=40)
    assert not watch.should_restart("api", "stopped", wanted=True, now=100), "limit reached"
    assert watch.should_restart("api", "stopped", wanted=True, now=700), "window passed"
    assert watch.should_restart("visual", "stopped", wanted=True, now=0), "per service"


def test_a_waiting_action_fires_only_after_the_kiosk_stays_free():
    idle = manager.IdleWait(readings=3)
    assert not idle.ready({"session_active": True})
    assert not idle.ready({"session_active": False})
    assert not idle.ready({"session_active": False})
    assert idle.ready({"session_active": False})
    idle = manager.IdleWait(readings=3)
    assert not idle.ready({"session_active": False})
    assert not idle.ready({"session_active": True}), "a guest arrived: start counting again"
    assert not idle.ready({"session_active": False})
    assert idle.ready({"session_active": None}) is False, "unknown is never free"


def test_the_banner_says_what_the_kiosk_is_doing():
    assert manager.kiosk_banner(None)[0] == "unknown"
    assert manager.kiosk_banner({"session_active": False})[0] == "free"
    assert manager.kiosk_banner({"session_active": True})[0] == "busy"


def test_the_log_view_shows_the_last_lines_and_survives_a_missing_file(tmp_path):
    log = tmp_path / "kiosk-api.log"
    log.write_text("\n".join(f"line {i}" for i in range(500)))
    text = manager.tail_log(log, lines=5)
    assert text.splitlines() == [f"line {i}" for i in range(495, 500)]
    assert "chưa có nhật ký" in manager.tail_log(tmp_path / "missing.log").lower()


def test_the_desktop_entry_launches_the_window_without_a_terminal(tmp_path):
    entry = manager.desktop_entry(tmp_path / "python", tmp_path / "gui.py", tmp_path)
    assert "Terminal=false" in entry
    assert f"Exec={tmp_path / 'python'} {tmp_path / 'gui.py'}" in entry
    assert entry.startswith("[Desktop Entry]")


def test_the_window_shows_each_service_and_blocks_a_second_start(monkeypatch):
    """Builds the real window when a screen is available; otherwise this test is skipped."""
    if not os.environ.get("DISPLAY"):
        pytest.skip("needs a screen")
    import tkinter

    from scripts import kiosk_manager_gui as gui

    try:
        root = tkinter.Tk()
    except tkinter.TclError:
        pytest.skip("no usable screen")
    root.withdraw()
    monkeypatch.setattr(
        manager, "load_settings", lambda *a, **k: {"staff_token": "", "auto_restart": False}
    )
    monkeypatch.setattr(manager, "service_state", lambda name: "stopped")
    monkeypatch.setattr(manager, "fetch_kiosk", lambda *a, **k: None)
    app = gui.ManagerApp(root)
    try:
        app.on_snapshot(
            {"api": "running", "visual": "stopped", "avatar": "starting"}, {"session_active": True}
        )
        assert app.rows["api"]["status"].cget("text") == "Đang chạy"
        assert "disabled" in app.rows["api"]["start"].state()
        assert "disabled" not in app.rows["visual"]["start"].state()
        assert "disabled" in app.rows["visual"]["stop"].state()
        assert app.banner.cget("text") == "Đang phục vụ khách"
        app.busy = True
        app.update_view()
        assert all(
            "disabled" in app.rows[n][a].state()
            for n in manager.SERVICE_NAMES
            for a in ("start", "stop", "restart")
        )
    finally:
        root.destroy()
