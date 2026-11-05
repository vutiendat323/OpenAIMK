"""Persist operator-controlled YAML values while retaining unrelated settings."""

import os
import re
import tempfile
from pathlib import Path

import yaml


def save_live_values(config_path: str | None, values: dict) -> None:
    if not config_path:
        raise ValueError("No active Vision configuration file to save")
    path = Path(config_path).resolve(strict=True)
    source = path.read_text()
    try:
        document = yaml.safe_load(source) or {}
    except yaml.YAMLError as exc:
        raise ValueError("Active Vision configuration is invalid YAML") from exc
    if not isinstance(document, dict):
        raise ValueError("Vision configuration must be a YAML mapping")
    for key, value in values.items():
        pattern = re.compile(rf"^{re.escape(key)}:[^\n]*", re.MULTILINE)
        match = pattern.search(source)
        line = f"{key}: {value:g}"
        if match:
            comment = re.search(r"\s+#.*", match.group())
            if comment:
                line += comment.group()
            source = pattern.sub(lambda _match: line, source)
        elif key in document:
            # A quoted YAML key is legal; avoid adding a duplicate spelling.
            document.update(values)
            source = yaml.safe_dump(document, sort_keys=False)
            break
        else:
            source = source.rstrip() + "\n" + line + "\n"
    try:
        parsed = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        raise ValueError("Configuration could not be updated safely") from exc
    if any(parsed.get(key) != value for key, value in values.items()):
        raise ValueError("Configuration could not be updated safely")
    descriptor, temporary = tempfile.mkstemp(prefix=".console-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            output.write(source)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
