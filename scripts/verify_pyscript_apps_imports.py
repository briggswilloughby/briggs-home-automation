#!/usr/bin/env python3
"""Verify no modules import pyscript.apps package initializer."""
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_PACKAGE = "pyscript.apps"


def _should_skip(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return any(part.startswith(".") for part in relative.parts)


def main() -> int:
    failures: list[str] = []

    for path in ROOT.rglob("*.py"):
        if path == Path(__file__).resolve():
            continue
        if _should_skip(path):
            continue

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:  # pragma: no cover - unexpected parse error
            print(f"Failed to parse {path}: {exc}", file=sys.stderr)
            return 1

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == TARGET_PACKAGE or alias.name.startswith(f"{TARGET_PACKAGE}."):
                        failures.append(
                            f"{path.relative_to(ROOT)}:{node.lineno} -> import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == TARGET_PACKAGE or module.startswith(f"{TARGET_PACKAGE}."):
                    failures.append(
                        f"{path.relative_to(ROOT)}:{node.lineno} -> from {module} import ..."
                    )

    if failures:
        print("Found disallowed imports that rely on the pyscript.apps package initializer:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print("No imports rely on the pyscript.apps package initializer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
