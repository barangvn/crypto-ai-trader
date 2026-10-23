"""Shared test helpers for the S-FND-06 suite (T03)."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACTS_ROOT = Path(__file__).resolve().parents[2] / "app" / "contracts"
TESTS_ROOT = Path(__file__).resolve().parent

# The exact 6 new production modules of S-FND-06 (allowlist P01..P06).
SFND06_NEW_PROD_FILES: tuple[str, ...] = (
    "sfnd06_serialize.py",
    "_sfnd06_constants.py",
    "_sfnd06_json.py",
    "_sfnd06_fingerprint.py",
    "_sfnd06_builders.py",
    "_sfnd06_helpers.py",
)

# Third-party actor patterns that must never appear as imports in the new modules.
FORBIDDEN_THIRD_PARTY: tuple[str, ...] = (
    "pydantic",
    "msgspec",
    "attrs",
    "orjson",
    "rapidjson",
    "xxhash",
    "dateutil",
    "pytz",
    "numpy",
    "yaml",
    "requests",
    "httpx",
    "aiohttp",
    "websocket",
    "ccxt",
)

# stdlib modules the new production modules are allowed to import.
ALLOWED_STDLIB_SFND06: set[str] = {
    "__future__",
    "dataclasses",
    "datetime",
    "decimal",
    "hashlib",
    "json",
    "re",
    "typing",
}

INTERNAL_ROOT_PREFIXES: set[str] = {"app"}


def sha_sorted_json(obj: Any) -> str:
    """Reference SHA-256 (12 hex) over sorted compact JSON — independent of prod code."""
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def new_prod_paths() -> list[Path]:
    return [CONTRACTS_ROOT / name for name in SFND06_NEW_PROD_FILES]


def count_imports_file(src_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in INTERNAL_ROOT_PREFIXES:
                    continue
                counts[top] = counts.get(top, 0) + 1
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or not node.module:
                continue
            top = node.module.split(".")[0]
            if top in INTERNAL_ROOT_PREFIXES:
                continue
            counts[top] = counts.get(top, 0) + 1
    return counts


def scan_new_prod_3rd_party_imports() -> list[tuple[str, list[str]]]:
    """Return (file, [unexpected top-level imports]) for the 6 new prod modules."""
    found: list[tuple[str, list[str]]] = []
    for path in new_prod_paths():
        counts = count_imports_file(path)
        extra = [name for name in counts if name not in ALLOWED_STDLIB_SFND06]
        if extra:
            found.append((str(path), sorted(extra)))
    return found


def scan_patterns(
    root: Path,
    patterns: tuple[str, ...] | list[str],
    only_files: set[str] | None = None,
    exclude_files: set[str] | None = None,
) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    for py in sorted(root.glob("**/*.py")):
        if exclude_files and py.name in exclude_files:
            continue
        if only_files and py.name not in only_files:
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
            for pat in patterns:
                if pat in line:
                    findings.append((py, i, pat.strip()))
    return findings
