from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


def sha_json(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


ALLOWED_STDLIB_CONTRACTS: set[str] = {
    "__future__",
    "copy",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "hashlib",
    "json",
    "pathlib",
    "re",
    "sys",
    "typing",
}

INTERNAL_ROOT_PREFIXES: set[str] = {
    "app",
}


def count_imports_file(src_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    src = src_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name in INTERNAL_ROOT_PREFIXES:
                    continue
                counts[name] = counts.get(name, 0) + 1
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue
            if node.module:
                name = node.module.split(".")[0]
                if name in INTERNAL_ROOT_PREFIXES:
                    continue
                counts[name] = counts.get(name, 0) + 1
    return counts


def scan_3rd_party_contracts() -> list[tuple[str, list[str]]]:
    app_root = Path(__file__).resolve().parents[2] / "app" / "contracts"
    found: list[tuple[str, list[str]]] = []
    for py in sorted(app_root.glob("*.py")):
        counts = count_imports_file(py)
        extra: list[str] = []
        for name in counts:
            if name in ALLOWED_STDLIB_CONTRACTS:
                continue
            extra.append(name)
        if extra:
            found.append((str(py), extra))
    return found
