from __future__ import annotations

import configparser
import hashlib
import json
from pathlib import Path
from typing import Any, Optional


def ini_write(sections: dict[str, dict[str, Any]], dest_path: Path) -> Path:
    cp = configparser.ConfigParser(interpolation=None, default_section=None, strict=True)
    for s, kv in sections.items():
        if not cp.has_section(s):
            cp.add_section(s)
        for k, v in kv.items():
            cp.set(s, str(k), "" if v is None else str(v))
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as fh:
        cp.write(fh, space_around_delimiters=True)
    return dest_path


def sha_json(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def count_imports(module_name: str) -> dict[str, int]:
    import ast
    import importlib.util

    spec = importlib.util.find_spec(module_name)
    counts: dict[str, int] = {}
    if spec is None or spec.origin is None:
        return counts
    src = Path(spec.origin).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                counts[name] = counts.get(name, 0) + 1
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                name = node.module.split(".")[0]
                counts[name] = counts.get(name, 0) + 1
    return counts


ALLOWED_STDLIB_CONFIG = {
    "configparser",
    "copy",
    "dataclasses",
    "decimal",
    "hashlib",
    "json",
    "os",
    "pathlib",
    "sys",
    "typing",
}


def scan_3rd_party_imports(module_name: str) -> list[str]:
    counts = count_imports(module_name)
    found: list[str] = []
    for name in counts:
        if name in ALLOWED_STDLIB_CONFIG:
            continue
        found.append(name)
    return found
