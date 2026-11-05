#!/usr/bin/env python3
"""Start/stop only the processes recorded for this workspace."""

import argparse
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".runtime"
SERVICES = {
    "visual": (
        9877,
        [
            os.environ.get("TREND_AV_PYTHON", str(ROOT / "Visual/.venv/bin/python")),
            "-B",
            "-m",
            "trendcoffee.visual_worker",
        ],
    ),
    "avatar": (
        8010,
        [
            str(ROOT / ".runtime/livetalking-venv/bin/python"),
            "-B",
            str(ROOT / "scripts/livetalking_local.py"),
            "--checkout",
            str(ROOT / ".runtime/LiveTalking"),
            "--model",
            "wav2lip",
            "--avatar_id",
            "wav2lip256_avatar1",
            "--batch_size",
            "4",
            "--listenport",
            "8010",
        ],
    ),
    "api": (
        8080,
        [str(ROOT / ".venv/bin/python"), "-B", "-m", "trendcoffee", "serve", "--port", "8080"],
    ),
}


def identity(pid):
    try:
        process = Path("/proc") / str(pid)
        args = process.joinpath("cmdline").read_bytes().split(b"\0")
        cwd = process.joinpath("cwd").resolve()
        avatar = any(
            str(ROOT / "scripts" / script).encode() in args
            for script in ("livetalking_local.py", "ditto_server.py")
        )
        if cwd != ROOT and not (
            avatar and cwd in (ROOT / ".runtime/LiveTalking", ROOT / ".runtime/Ditto")
        ):
            return None
        if not any(
            arg
            in (
                b"trendcoffee",
                b"trendcoffee.visual_worker",
                str(ROOT / "scripts/livetalking_local.py").encode(),
                str(ROOT / "scripts/ditto_server.py").encode(),
            )
            for arg in args
        ):
            return None
        return process.joinpath("stat").read_text().split()[21]
    except OSError:
        return None


def record(name):
    try:
        data = json.loads((RUNTIME / f"kiosk-{name}.json").read_text())
        return data if identity(data["pid"]) == data["started"] else None
    except (OSError, ValueError, KeyError):
        return None


def listening(port):
    with socket.socket() as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def avatar_command(command, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("engine") == "ditto":
        source = (ROOT / manifest["source"]).resolve()
        if not source.is_file():
            raise ValueError("Ditto source video missing")
        if not (ROOT / "scripts/ditto_server.py").is_file():
            raise ValueError("Ditto WebRTC server is not installed yet")
        result = [
            str(ROOT / ".runtime/livetalking-venv/bin/python"),
            "-B",
            str(ROOT / "scripts/ditto_server.py"),
            "--source",
            str(source),
            "--port",
            "8010",
        ]
        if "gpu_budget" in manifest:
            result.extend(["--gpu-budget", str(manifest["gpu_budget"])])
        if "render_fps" in manifest:
            result.extend(["--render-fps", str(manifest["render_fps"])])
        if "motion_stride_ms" in manifest:
            result.extend(["--motion-stride-ms", str(manifest["motion_stride_ms"])])
        if "renderer_backend" in manifest:
            result.extend(["--renderer-backend", str(manifest["renderer_backend"])])
        if "expression_mode" in manifest:
            result.extend(["--expression-mode", str(manifest["expression_mode"])])
        if "lip_opening_limit" in manifest:
            result.extend(["--lip-opening-limit", str(manifest["lip_opening_limit"])])
        if "presentation_lead_ms" in manifest:
            result.extend(["--presentation-lead-ms", str(manifest["presentation_lead_ms"])])
        if "reference_frame" in manifest:
            result.extend(["--reference-frame", str(manifest["reference_frame"])])
        if "lip_factor" in manifest:
            result.extend(["--lip-factor", str(manifest["lip_factor"])])
        if "lip_width" in manifest:
            result.extend(["--lip-width", str(manifest["lip_width"])])
        if "turn_gain" in manifest:
            result.extend(["--turn-gain", str(manifest["turn_gain"])])
        if manifest.get("wave") is False:
            result.append("--no-wave")
        if manifest.get("whole_head"):
            result.append("--whole-head")
        if manifest.get("closed_source"):
            result.append("--closed-source")
        if "composite" in manifest:
            result.extend(["--composite", str(manifest["composite"])])
        if "rest_source" in manifest:
            rest = (ROOT / manifest["rest_source"]).resolve()
            if not rest.is_file():
                raise ValueError("Ditto rest video missing")
            result.extend(["--rest-source", str(rest)])
        if manifest.get("drive_head"):
            result.append("--drive-head")
        if "head_gain" in manifest:
            result.extend(["--head-gain", str(manifest["head_gain"])])
        return result
    return [*command, "--motion-config", str(manifest_path)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "status", "stop"))
    parser.add_argument("--service", choices=("api", "visual", "avatar", "all"), default="all")
    args = parser.parse_args()
    os.chdir(ROOT)
    RUNTIME.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "TREND_CODEX_VOICE": "1",
        "TREND_AVATAR_URL": os.environ.get("TREND_AVATAR_URL", "http://127.0.0.1:8010"),
        "TREND_MERCHANT_ENABLED": os.environ.get("TREND_MERCHANT_ENABLED", "1"),
        "TREND_PRINT_QUEUE": os.environ.get("TREND_PRINT_QUEUE", "GP-C180I"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(ROOT / "Audio/src") + os.pathsep + str(ROOT),
        "HF_HOME": str(RUNTIME / "huggingface"),
        "TORCH_HOME": str(RUNTIME / "torch"),
        "NEMO_CACHE_DIR": str(RUNTIME / "torch/NeMo"),
        "TORCHINDUCTOR_COMPILE_THREADS": "4",
    }
    for name, (port, command) in SERVICES.items():
        if args.service not in ("all", name):
            continue
        info = record(name)
        if args.action == "stop":
            if info:
                pid = info["pid"]
                if os.getpgid(pid) == pid:
                    os.killpg(pid, signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGTERM)
                print(f"{name}: stopping owned pid {pid}")
                for _ in range(100):
                    if identity(pid) is None:
                        break
                    time.sleep(0.1)
            continue
        if args.action == "start" and not info:
            if name == "avatar" and (RUNTIME / "trend-avatar.json").exists():
                command = avatar_command(command, RUNTIME / "trend-avatar.json")
            if listening(port):
                raise SystemExit(
                    f"{name}: port {port} is already in use; no unrelated process was stopped"
                )
            with (RUNTIME / f"kiosk-{name}.log").open("ab") as log:
                child = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            time.sleep(0.15)
            started = identity(child.pid)
            if started is None:
                raise SystemExit(f"{name}: startup failed; see .runtime/kiosk-{name}.log")
            info = {"pid": child.pid, "started": started}
            (RUNTIME / f"kiosk-{name}.json").write_text(json.dumps(info))
        print(
            f"{name}: {'running pid ' + str(info['pid']) if info else 'not managed'}; port {port} {'listening' if listening(port) else 'not ready'}"
        )
    if args.action == "start":
        print("Open http://127.0.0.1:8080 — model warm-up continues in the background.")


if __name__ == "__main__":
    main()
