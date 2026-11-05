"""Every module of the vision service imports.

Catches a broken import in a module no behavioural test reaches -- the
Metric3D and YOLO adapters, the spoof model definitions -- the moment a file
moves.  Scripts are imported too: their work sits under ``__main__``.
"""

import importlib
from pathlib import Path

import pytest

VISION = Path(__file__).resolve().parents[1]
SKIP = {"tests", "_shim"}   # _shim is put on sys.path as a top-level mmcv


def service_modules() -> list[str]:
    names = []
    for path in sorted(VISION.rglob("*.py")):
        rel = path.relative_to(VISION)
        if SKIP & set(rel.parts):
            continue
        parts = ["Visual", *rel.with_suffix("").parts]
        if parts[-1] == "__init__":
            parts.pop()
        names.append(".".join(parts))
    return names


@pytest.mark.parametrize("name", service_modules())
def test_module_imports(name):
    importlib.import_module(name)
