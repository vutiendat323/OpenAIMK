"""Copy an OpenJarvis speaker test into Audio, changing only what the port needs.

usage: port_tests.py SOURCE DEST [--drop TEST_NAME ...]

* module paths: openjarvis.server.voice.speaker* -> audio.speaker*
  (speaker_audio -> speaker_models);
* settings: ``monkeypatch.setenv("OPENJARVIS_CONFIG", str(X))`` followed by
  ``load_speaker_settings()`` becomes ``load_speaker_settings(X)``; ``delenv``
  becomes ``load_speaker_settings(None)``;
* --drop removes whole test functions that need OpenJarvis (kiosk, Pipecat).
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

MODULES = [
    (
        r"from openjarvis\.server\.voice import speaker_vision\b",
        "from audio import speaker_vision",
    ),
    (r"openjarvis\.server\.voice\.speaker_audio\b", "audio.speaker_models"),
    (
        r"openjarvis\.server\.voice\.speaker_(identity|embedding|vision|console)\b",
        r"audio.speaker_\1",
    ),
    (r"openjarvis\.server\.voice\.speaker\b", "audio.speaker"),
]
SETENV = re.compile(r'^\s*monkeypatch\.setenv\("OPENJARVIS_CONFIG", str\((\w+)\)\)\s*$')
DELENV = re.compile(
    r'^\s*monkeypatch\.delenv\("OPENJARVIS_CONFIG", raising=False\)\s*$'
)
DEF = re.compile(r"^(async )?def ")


def drop_tests(text: str, names: list[str]) -> str:
    tree = ast.parse(text)
    defs = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(names) - set(defs))
    if missing:
        raise SystemExit(f"tests not found: {missing}")
    lines = text.splitlines()
    spans = []
    for name in names:
        node = defs[name]
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        spans.append((start, node.end_lineno))
    for start, end in sorted(spans, reverse=True):
        del lines[start - 1 : end]
    return "\n".join(lines) + "\n"


def explicit_settings_path(text: str) -> str:
    out, pending = [], None
    for line in text.splitlines():
        if DEF.match(line) and pending is not None:
            raise SystemExit("OPENJARVIS_CONFIG set without a following load")
        if match := SETENV.match(line):
            pending = match.group(1)
            continue
        if DELENV.match(line):
            pending = "None"
            continue
        if pending is not None and "load_speaker_settings()" in line:
            line = line.replace(
                "load_speaker_settings()", f"load_speaker_settings({pending})", 1
            )
            pending = None
        out.append(line)
    if pending is not None:
        raise SystemExit("OPENJARVIS_CONFIG set without a following load")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("--drop", nargs="*", default=[])
    args = parser.parse_args()
    text = args.source.read_text()
    if args.drop:
        text = drop_tests(text, args.drop)
    for pattern, replacement in MODULES:
        text = re.sub(pattern, replacement, text)
    text = explicit_settings_path(text)
    leftovers = [
        word
        for word in ("openjarvis.", "OPENJARVIS_CONFIG", "load_speaker_settings()")
        if word in text
    ]
    if leftovers:
        raise SystemExit(f"{args.dest}: still mentions {leftovers}")
    args.dest.write_text(text)
    print(f"{args.source.name} -> {args.dest}")


if __name__ == "__main__":
    main()
