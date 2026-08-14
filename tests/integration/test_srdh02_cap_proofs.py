from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
DOMAIN_DIRS = [
    ROOT / "app" / "contracts",
    ROOT / "app" / "processing",
    ROOT / "app" / "platform",
    ROOT / "app" / "ingest" / "registry",
]

RUN_MODE_RE = ("run_mode", "source_type")


class TestCAP1StaticScan:
    _ALLOWLIST_FILES = {"app/processing/replay_clock.py"}

    def test_domain_no_run_mode_source_type_branching(self) -> None:
        hits: list[str] = []
        for d in DOMAIN_DIRS:
            if not d.exists():
                continue
            for py in sorted(d.rglob("*.py")):
                rel = py.relative_to(ROOT).as_posix()
                if rel in self._ALLOWLIST_FILES:
                    continue
                try:
                    txt = py.read_text(encoding="utf-8")
                    tree = ast.parse(txt, filename=str(py))
                except Exception:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.If | ast.IfExp):
                        if isinstance(node, ast.IfExp):
                            checks = [node.test]
                        else:
                            checks = [node.test] + [
                                other.test
                                for other in getattr(node, "orelse", [])
                                if isinstance(other, ast.If)
                            ]
                        for test_node in checks:
                            src = ast.unparse(test_node)
                            if any(p in src for p in RUN_MODE_RE):
                                if "tests" not in str(py.relative_to(ROOT)).lower():
                                    hits.append(f"{rel}: {src}")
        assert not hits, f"CAP-1: run_mode/source_type branching found in domain: {hits[:20]}"


class TestCAP2SevenFlagsPresent:
    def test_seven_flags_in_quality_flags_dataclass(self) -> None:
        from app.contracts.canonical import QualityFlags
        fields = QualityFlags.__dataclass_fields__
        # seven boolean fields
        seven = {"stale", "missing", "duplicate", "out_of_order", "invalid", "quarantined", "degraded"}
        assert seven.issubset(set(fields.keys())), seven - set(fields.keys())
        for f in seven:
            assert fields[f].type in ("bool", bool, "<class 'bool'>") or "bool" in str(fields[f].type)
