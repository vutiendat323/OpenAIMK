"""Point test imports at the layered modules, one statement at a time.

usage: rewrite_imports.py FILE [FILE ...]
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict
from pathlib import Path

HOMES = {
    "audio.domain.verdict": ["Verdict", "turn_verdict"],
    "audio.domain.settings": [
        "SpeakerSettings",
        "SEGMENT_MAX_SECS",
        "SPEAKER_LIVE_KEYS",
        "settings_from_mapping",
    ],
    "audio.domain.evidence": ["VISION_WINDOW_SECS", "FaceTrackBuffer", "AudioSpan"],
    "audio.domain.gate": ["OverlapDetector", "AudioOnlyGate", "SpeakerTracker"],
    "audio.domain.identity": [
        "unit",
        "cosine",
        "Voiceprint",
        "SlotTrackBinder",
        "Label",
        "LockState",
        "EmbeddingJob",
        "SlotIdentity",
        "LockEvent",
        "TargetLock",
        "BotVoiceprint",
    ],
    "audio.domain.fusion": ["FusionGate"],
    "audio.domain.signal": ["SAMPLE_RATE", "resample_to_16k", "audio_levels"],
    "audio.application.ports": [
        "Diarizer",
        "Separator",
        "SpeakerEmbedder",
        "AsdBridge",
        "LiveKey",
        "TelemetrySink",
        "ConsoleSource",
        "SettingsStore",
    ],
    "audio.application.stream": [
        "AudioChunk",
        "SpeakerVerdict",
        "SttAudio",
        "SpeakerStream",
    ],
    "audio.application.embedding": [
        "EMBEDDING_EXECUTOR",
        "EmbeddingWorker",
        "bot_audio_sink",
    ],
    "audio.application.console": ["SpeakerConsole"],
    "audio.infrastructure.nemo.sortformer": ["SortformerDiarizer"],
    "audio.infrastructure.nemo.titanet": ["TitaNetEmbedder"],
    "audio.infrastructure.tse.bsrnn": ["TseSeparator"],
    "audio.infrastructure.vision.asd_bridge": ["VisionAudioBridge", "RECONNECT_DELAYS"],
    "audio.infrastructure.config.toml_store": [
        "load_speaker_settings",
        "TomlSettingsStore",
    ],
}
MOVES = {name: module for module, names in HOMES.items() for name in names}
FLAT = {
    "audio.speaker",
    "audio.speaker_identity",
    "audio.speaker_embedding",
    "audio.speaker_models",
    "audio.speaker_vision",
    "audio.speaker_console",
    "audio.speaker_stream",
}
TEXT = {
    '"audio.speaker_vision.': '"audio.infrastructure.vision.asd_bridge.',
    "from audio import speaker_vision": "from audio.infrastructure.vision import asd_bridge as speaker_vision",
}


def rewrite(path: Path) -> None:
    text = path.read_text()
    for old, new in TEXT.items():
        text = text.replace(old, new)
    lines = text.splitlines()
    nodes = [
        node
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.ImportFrom) and node.module in FLAT
    ]
    for node in sorted(nodes, key=lambda n: n.lineno, reverse=True):
        groups = defaultdict(list)
        for alias in node.names:
            if alias.name not in MOVES:
                raise SystemExit(f"{path}:{node.lineno}: no home for {alias.name}")
            spelled = (
                alias.name
                if alias.asname is None
                else (f"{alias.name} as {alias.asname}")
            )
            groups[MOVES[alias.name]].append(spelled)
        indent = " " * node.col_offset
        suffix = "  # noqa: E402" if "noqa: E402" in lines[node.lineno - 1] else ""
        lines[node.lineno - 1 : node.end_lineno] = [
            f"{indent}from {module} import {', '.join(names)}{suffix}"
            for module, names in groups.items()
        ]
    path.write_text("\n".join(lines) + "\n")
    print(f"rewrote {path}")


if __name__ == "__main__":
    for name in sys.argv[1:]:
        rewrite(Path(name))
