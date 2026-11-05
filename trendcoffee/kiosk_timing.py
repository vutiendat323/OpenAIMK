"""Staff-tuned kiosk session boundaries, kept on the server and applied from the next guest.

Session start: how close a guest must stand and for how long before a session opens.
Session end: how long the guest may be away or in one session, and the warning before
that limit. `idle_seconds` no longer ends a session (2026-11-05): after that much quiet,
Trend asks the guest a question that fits where they are. Values are bounded so a typo
cannot lock the kiosk open or shut.
"""

import json
import logging
import math
import os
import tempfile
import threading
from pathlib import Path

from .service import ServiceError

# name: (default, minimum, maximum)
FIELDS = {
    "presence_distance_m": (0.6, 0.3, 2.0),
    "enter_seconds": (2.0, 0.5, 10.0),
    "leave_seconds": (3.0, 1.0, 30.0),
    "idle_seconds": (120.0, 30.0, 600.0),
    "session_limit_seconds": (600.0, 120.0, 3600.0),
    "warning_seconds": (60.0, 0.0, 300.0),
}


def defaults():
    return {name: default for name, (default, _, _) in FIELDS.items()}


def validate(values):
    """Complete, bounded values; raises ServiceError('invalid_kiosk_timing') otherwise."""
    if not isinstance(values, dict) or set(values) != set(FIELDS):
        raise ServiceError("invalid_kiosk_timing")
    result = {}
    for name, (_, low, high) in FIELDS.items():
        value = values[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or not low <= value <= high
        ):
            raise ServiceError("invalid_kiosk_timing")
        result[name] = float(value)
    if result["warning_seconds"] >= result["session_limit_seconds"]:
        raise ServiceError("invalid_kiosk_timing")
    return result


class KioskTiming:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        self.values = defaults()
        if self.path and self.path.exists():
            try:
                stored = json.loads(self.path.read_text())
                if not isinstance(stored, dict):
                    raise ValueError("not an object")
                # Fields added later keep their defaults; unknown or bad values reject the file.
                self.values = validate({**defaults(), **stored})
            except (OSError, ValueError, ServiceError):
                logging.getLogger(__name__).warning(
                    "Ignoring unreadable kiosk timing file %s; using defaults", self.path
                )

    def describe(self):
        return {
            "values": dict(self.values),
            "defaults": defaults(),
            "limits": {name: {"min": low, "max": high} for name, (_, low, high) in FIELDS.items()},
        }

    def update(self, changes):
        if not isinstance(changes, dict) or not changes or set(changes) - set(FIELDS):
            raise ServiceError("invalid_kiosk_timing")
        with self.lock:
            values = validate({**self.values, **changes})
            if self.path:
                self._write(values)
            self.values = values
        return self.describe()

    def _write(self, values):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".kiosk-timing-")
        try:
            with os.fdopen(handle, "w") as file:
                json.dump(values, file, indent=2)
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
