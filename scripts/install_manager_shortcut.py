#!/usr/bin/env python3
"""Add "Trend Kiosk Manager" to the application menu of the current user (no root needed)."""

import os
import sys
from pathlib import Path

try:
    from scripts import kiosk_manager as core
except ImportError:  # run as a script from this folder
    import kiosk_manager as core


def main():
    target = Path.home() / ".local/share/applications/trend-kiosk-manager.desktop"
    target.parent.mkdir(parents=True, exist_ok=True)
    gui = core.ROOT / "scripts/kiosk_manager_gui.py"
    target.write_text(core.desktop_entry(Path(sys.executable), gui, core.ROOT))
    os.chmod(target, 0o755)
    print(f"Đã tạo lối tắt: {target}\nMở menu ứng dụng và tìm 'Trend Kiosk Manager'.")


if __name__ == "__main__":
    main()
