"""The dependency rule, enforced: application → domain ← infrastructure.

Reads the imports of every module in a layer and fails on one that crosses the
rule. A layer's rule is switched on (ENFORCED) once that layer has moved in.
"""

import ast
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "audio"

# What a module in each layer may import from inside the package (audio.<x>).
ALLOWED = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "infrastructure": {"domain", "infrastructure"},
}
# Outside the package the domain takes only the standard library and these.
DOMAIN_THIRD_PARTY = {"numpy", "scipy"}
FORBIDDEN = {"openjarvis", "pipecat", "loguru"}

ENFORCED: set[str] = {"domain", "application", "infrastructure"}


def imported_modules(source: str) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "use absolute audio.* imports"
            names.add(node.module)
    return names


@pytest.mark.parametrize("layer", sorted(ALLOWED))
def test_layer_imports_follow_the_dependency_rule(layer):
    if layer not in ENFORCED:
        pytest.skip(f"{layer} has not moved in yet")
    for path in sorted((PACKAGE / layer).rglob("*.py")):
        for name in imported_modules(path.read_text()):
            parts = name.split(".")
            if parts[0] == "audio":
                inner = parts[1] if len(parts) > 1 else ""
                assert inner in ALLOWED[layer], f"{path.name} imports {name}"
            elif layer == "domain":
                assert (
                    parts[0] in sys.stdlib_module_names
                    or parts[0] in DOMAIN_THIRD_PARTY
                ), f"{path.name} imports {name}"


def test_no_module_depends_on_openjarvis_pipecat_or_loguru():
    for path in sorted(PACKAGE.rglob("*.py")):
        tops = {name.split(".")[0] for name in imported_modules(path.read_text())}
        assert not tops & FORBIDDEN, (
            f"{path.relative_to(PACKAGE)} imports {tops & FORBIDDEN}"
        )


def test_every_module_belongs_to_a_layer():
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE)
        assert relative == Path("__init__.py") or relative.parts[0] in ALLOWED, relative
