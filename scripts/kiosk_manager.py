"""Kiosk Manager logic: state of the services, safe actions, settings and the watchdog.

The window itself is `kiosk_manager_gui.py`. This module has no window code, so it runs
(and is tested) without a screen. It never starts a service itself: it calls the launcher
`scripts/kiosk.py`, which only stops the processes it recorded for this workspace.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

try:  # run as `scripts.kiosk_manager` (tests) or as a script from this folder (the window)
    from scripts import kiosk
except ImportError:  # pragma: no cover
    import kiosk

ROOT = kiosk.ROOT
RUNTIME = kiosk.RUNTIME
LAUNCHER = ROOT / "scripts" / "kiosk.py"
SETTINGS_PATH = RUNTIME / "kiosk-manager.json"
API_PORT = kiosk.SERVICES["api"][0]
SERVICE_NAMES = ("api", "visual", "avatar")
LABELS = {
    "api": "Trend (giọng nói và gọi món)",
    "visual": "Thị giác (camera)",
    "avatar": "Nhân vật",
}
ACTION_TIMEOUT = 150  # seconds; the API and the avatar load models when they start


def service_state(name):
    """running | starting | stopped | other (the port belongs to a program we do not own)."""
    owned = kiosk.record(name) is not None
    ready = kiosk.listening(kiosk.SERVICES[name][0])
    if owned:
        return "running" if ready else "starting"
    return "other" if ready else "stopped"


def fetch_kiosk(port=API_PORT, timeout=1.5):
    """The API's kiosk status, or None when it cannot be reached."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/kiosk/status", timeout=timeout
        ) as r:
            data = json.load(r)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def kiosk_banner(status):
    """(kind, text) for the top of the window: unknown, free or busy."""
    if status is None:
        return "unknown", "Chưa kết nối được với Trend"
    if status.get("session_active"):
        return "busy", "Đang phục vụ khách"
    return "free", "Kiosk đang rảnh"


def guest_would_be_cut(action, status):
    """True when stopping or restarting now would interrupt a guest."""
    return action in ("stop", "restart") and bool(status and status.get("session_active"))


def run_launcher(action, service, staff_token=""):
    """Run `kiosk.py` for one service or all. Returns (ok, message). restart = stop, start."""
    env = dict(os.environ)
    if staff_token:
        env["TREND_STAFF_TOKEN"] = staff_token
    steps = ("stop", "start") if action == "restart" else (action,)
    output = []
    for step in steps:
        try:
            done = subprocess.run(
                [sys.executable, str(LAUNCHER), "--service", service, step],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=ACTION_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return False, "Quá thời gian chờ. Xem nhật ký để biết thêm."
        text = (done.stdout + done.stderr).strip()
        if done.returncode != 0:
            return False, text or f"Lỗi khi {step}."
        output.append(text)
    return True, output[-1] if output else ""


def load_settings(path=SETTINGS_PATH, use_env=True):
    settings = {"staff_token": "", "auto_restart": False}
    try:
        data = json.loads(Path(path).read_text())
        if isinstance(data, dict):
            if isinstance(data.get("staff_token"), str):
                settings["staff_token"] = data["staff_token"]
            settings["auto_restart"] = data.get("auto_restart") is True
    except (OSError, ValueError):
        pass
    if use_env and os.environ.get("TREND_STAFF_TOKEN"):
        settings["staff_token"] = os.environ["TREND_STAFF_TOKEN"]
    return settings


def save_settings(settings, path=SETTINGS_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(
            {
                "staff_token": settings.get("staff_token", ""),
                "auto_restart": bool(settings.get("auto_restart")),
            },
            handle,
        )
    os.chmod(path, 0o600)


class Watchdog:
    """Decides when a service that stopped by itself is started again, with limits."""

    def __init__(self, cooldown=30.0, max_restarts=3, window=600.0):
        self.cooldown, self.max_restarts, self.window = cooldown, max_restarts, window
        self.history = {}

    def should_restart(self, name, state, wanted, now):
        if not wanted or state != "stopped":
            return False
        recent = [t for t in self.history.get(name, []) if now - t < self.window]
        if recent and now - recent[-1] < self.cooldown:
            return False
        if len(recent) >= self.max_restarts:
            return False
        self.history[name] = [*recent, now]
        return True


class IdleWait:
    """An action chosen to wait for the guest fires after the kiosk stays free a while."""

    def __init__(self, readings=15):
        self.readings, self.count = readings, 0

    def ready(self, status):
        if status is None or status.get("session_active") is not False:
            self.count = 0
            return False
        self.count += 1
        return self.count >= self.readings


def tail_log(path, lines=200, size=65536):
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            end = handle.tell()
            handle.seek(max(0, end - size))
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        return "Chưa có nhật ký cho dịch vụ này."
    return "\n".join(text.splitlines()[-lines:])


def log_path(name):
    return RUNTIME / f"kiosk-{name}.log"


def desktop_entry(python, gui, workdir):
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Trend Kiosk Manager\n"
        "Comment=Bật, tắt và khởi động lại các dịch vụ của kiosk Trend\n"
        f"Exec={python} {gui}\n"
        f"Path={workdir}\n"
        "Icon=applications-system\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
    )
