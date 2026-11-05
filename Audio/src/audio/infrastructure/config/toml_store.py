"""Speaker settings in TOML: loading a table, saving tuned values atomically."""

from __future__ import annotations

import os
import tempfile
import tomllib
from collections.abc import Mapping
from pathlib import Path

from audio.domain.settings import (
    SPEAKER_LIVE_KEYS,
    SpeakerSettings,
    settings_from_mapping,
)


def load_speaker_settings(
    path: str | Path | None, table: tuple[str, ...] = ("voice", "speaker")
) -> SpeakerSettings:
    """Load optional speaker settings from *table* of the TOML file at *path*.

    None, a blank path or a missing file gives the defaults, as an unset or
    empty preset did.
    """
    if path is None or not str(path).strip():
        return SpeakerSettings()
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return SpeakerSettings()
    with config_path.open("rb") as config_file:
        section = tomllib.load(config_file)

    for name in table[:-1]:
        section = section.get(name, {})
        if not isinstance(section, Mapping):
            raise ValueError("voice_config_must_be_a_table")
    section = section.get(table[-1], {})
    if not isinstance(section, Mapping):
        raise ValueError("voice_speaker_config_must_be_a_table")
    return settings_from_mapping(section)


def _table(document, names: tuple[str, ...]):
    import tomlkit

    node = document
    for name in names:
        node = node.setdefault(name, tomlkit.table())
    return node


class TomlSettingsStore:
    """Writes tuned values into a TOML file atomically, keeping its comments."""

    def __init__(
        self,
        path: str | Path,
        table: tuple[str, ...] = ("voice", "speaker"),
        key_tables: Mapping[str, tuple[str, ...]] | None = None,
    ) -> None:
        moved = sorted(set(key_tables or {}) & set(SPEAKER_LIVE_KEYS))
        if moved:
            # load_speaker_settings reads them from *table* only.
            raise ValueError(f"Speaker settings must stay in {table}: {moved}")
        self._path = Path(path)
        self._table = table
        self._key_tables = dict(key_tables or {})

    def save(self, values: Mapping[str, float]) -> None:
        import tomlkit

        path = self._path.expanduser().resolve(strict=True)
        document = tomlkit.parse(path.read_text())
        section = _table(document, self._table)
        for key, value in values.items():
            if key in self._key_tables:
                _table(document, self._key_tables[key])[key] = value
            elif key in SPEAKER_LIVE_KEYS:
                section[key] = value
            else:
                raise ValueError("Unsupported speaker setting")
        descriptor, temporary = tempfile.mkstemp(prefix=".console-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w") as output:
                output.write(tomlkit.dumps(document))
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, path.stat().st_mode & 0o777)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
