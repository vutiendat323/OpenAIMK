"""Move top-level definitions between modules, with the comments above them.

usage: split_symbols.py SOURCE TARGET NAME [NAME ...]

Appends each named class, function or assignment of SOURCE to TARGET, in
SOURCE order, together with the comment lines directly above it, and removes
them from SOURCE. Code moves byte for byte; imports are fixed afterwards.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def defined_name(node: ast.stmt) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        return target.id if isinstance(target, ast.Name) else None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def main() -> None:
    source, target, *names = sys.argv[1:]
    src = Path(source)
    lines = src.read_text().splitlines()
    spans = {}
    for node in ast.parse("\n".join(lines)).body:
        name = defined_name(node)
        if name in names:
            decorators = getattr(node, "decorator_list", [])
            start = min([node.lineno] + [d.lineno for d in decorators])
            while start > 1 and lines[start - 2].startswith("#"):
                start -= 1
            spans[name] = (start, node.end_lineno)
    missing = sorted(set(names) - set(spans))
    if missing:
        raise SystemExit(f"{source}: not found {missing}")
    ordered = sorted(spans.values())
    blocks = ["\n".join(lines[start - 1 : end]) for start, end in ordered]
    drop = {i for start, end in ordered for i in range(start, end + 1)}
    kept = [line for i, line in enumerate(lines, 1) if i not in drop]
    src.write_text("\n".join(kept) + "\n")
    with Path(target).open("a") as out:
        out.write("\n\n" + "\n\n\n".join(blocks) + "\n")
    print(f"{source} -> {target}: {', '.join(names)}")


if __name__ == "__main__":
    main()
