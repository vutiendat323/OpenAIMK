"""The dependency rule, enforced: presentation → application → domain ← infrastructure.

Reads the imports of every module in a layer and fails on one that crosses
the rule.  A layer's rule is switched on (ENFORCED) once that layer has been
moved in; main.py, the composition root, may import every layer, and tools/
sit outside the layers.
"""

import ast
import sys
from pathlib import Path

import pytest

VISION = Path(__file__).resolve().parents[1]

# What a module in each layer may import from inside the service (vision.<x>).
ALLOWED = {
    "domain": {"domain"},
    "application": {"domain", "application", "config"},
    "infrastructure": {"domain", "infrastructure"},
    "presentation": {"domain", "application", "presentation", "config"},
    "config": set(),
}
# Outside the service the domain takes only the standard library and these
# (OpenCV as mathematics: solvePnP, projectPoints -- a convention, not testable).
DOMAIN_THIRD_PARTY = {"numpy", "cv2"}

ENFORCED: set[str] = {"domain", "application", "infrastructure", "presentation", "config"}


def imported_modules(source: str) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "use absolute vision.* imports"
            names.add(node.module)
    return names


def violations(layer: str, names: set[str]) -> list[str]:
    bad = []
    for name in names:
        top, _, rest = name.partition(".")
        if top == "Visual":
            if rest.split(".")[0] not in ALLOWED[layer]:
                bad.append(name)
        elif layer == "domain" and top not in sys.stdlib_module_names | DOMAIN_THIRD_PARTY:
            bad.append(name)
    return sorted(bad)


def layer_modules() -> list[tuple[str, Path]]:
    found = []
    for layer in sorted(ENFORCED):
        root = VISION / layer
        paths = sorted(root.rglob("*.py")) if root.is_dir() else [VISION / f"{layer}.py"]
        found += [(layer, p) for p in paths]
    return found


def test_checker_flags_what_crosses_the_rule():
    assert violations("domain", {"os", "numpy", "cv2", "torch", "Visual.domain.scene",
                                 "Visual.application.state"}) == [
        "Visual.application.state", "torch"]  # sorted: capital V before t
    assert violations("application", {"torch", "Visual.domain.scene", "Visual.config",
                                      "Visual.infrastructure.faces.scrfd"}) == [
        "Visual.infrastructure.faces.scrfd"]
    assert violations("infrastructure", {"onnxruntime", "Visual.domain.faces",
                                         "Visual.config", "Visual.application.ports"}) == [
        "Visual.application.ports", "Visual.config"]
    assert violations("presentation", {"Visual.application.state",
                                       "Visual.infrastructure.camera"}) == [
        "Visual.infrastructure.camera"]


@pytest.mark.parametrize("layer,path", layer_modules(),
                         ids=lambda v: str(v.relative_to(VISION)) if isinstance(v, Path) else v)
def test_module_respects_the_dependency_rule(layer, path):
    assert violations(layer, imported_modules(path.read_text())) == []
