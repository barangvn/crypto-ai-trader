from __future__ import annotations

"""AC-26 / CAP-1: Bus source code içinde run_mode veya source_type branch YOKTUR."""

import ast
import os


ALLOWLIST_BUS_FILES = {
    "app/processing/replay_clock.py",
}


def _find_bus_related_py_files(root: str) -> list[str]:
    """app/platform/*.py ve app/contracts içinde bus ile ilgili importlar
    (ancak doğrudan bus.py ve tüm app/platform + event_bus ile ilgili test dosyaları)."""
    results: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            # Include: event_bus.py, app/platform/, ve bus ile ilgili tüm test dosyaları
            if (
                rel == "app/platform/event_bus.py"
                or rel.startswith("app/platform/")
                or "event_bus" in fn
                or "bus_" in fn
                or "pln01" in fn
            ):
                results.append(rel)
    return sorted(results)


def test_AC26_cap1_bus_no_runmode_source_type_branch_allowlist_respected():
    """CAP-1: allowlist dışında bus ile ilgili kaynak kodunda
    `if run_mode ==` veya `if source_type ==` static scan ile 0 match."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    files = _find_bus_related_py_files(root)
    assert len(files) >= 5, f"Expected >=5 bus related files, got {files}"

    violations: list[tuple[str, int, str]] = []
    patterns_any_case = [
        "run_mode",
        "source_type",
    ]

    for rel in files:
        if rel in ALLOWLIST_BUS_FILES:
            continue
        path = os.path.join(root, rel)
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While)):
                snippet = ast.get_source_segment(source, node) or ""
                snippet_lower = snippet.lower()
                for pat in patterns_any_case:
                    if pat in snippet_lower:
                        violations.append((rel, node.lineno, snippet[:120]))

    if violations:
        lines = "\n".join(
            f"  - {v[0]}:L{v[1]} {v[2]!r}" for v in violations[:20]
        )
        raise AssertionError(
            f"CAP-1 violations in bus layer ({len(violations)}):\n{lines}"
        )


def test_bus_source_imports_only_contracts_and_stdlib():
    """AD-7: event_bus.py sadece contracts + stdlib import eder; başka domain yok."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bus_path = os.path.join(root, "app", "platform", "event_bus.py")
    with open(bus_path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=bus_path)
    forbidden_prefixes = (
        "app.ingest",
        "app.processing.normalizer",
        "app.processing.quality_monitor",
        "app.strategy",
        "app.risk",
        "app.feature",
        "app.regime",
        "app.paper",
        "feature_engineering",
        "exchange",
    )
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if any(name.startswith(p) for p in forbidden_prefixes):
                    bad.append(f"import {name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod.startswith(p) for p in forbidden_prefixes):
                bad.append(f"from {mod} import ...")
    assert bad == [], f"Forbidden domain imports in event_bus.py: {bad}"
