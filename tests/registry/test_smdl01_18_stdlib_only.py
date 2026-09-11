from __future__ import annotations

import ast
import pathlib
import sys

import pytest


REGISTRY_ROOT = pathlib.Path("app/registry")

FORBIDDEN_NETWORK = [
    "urllib",
    "httpx",
    "requests",
    "websocket",
    "websockets",
]

FORBIDDEN_STORAGE = [
    "sqlalchemy",
    "asyncpg",
    "sqlite3",
    "redis",
]

ALL_FORBIDDEN = FORBIDDEN_NETWORK + FORBIDDEN_STORAGE


class _ImportCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: list[tuple[str, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, f"Import@{node.lineno}"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if mod:
            self.imports.append((mod, f"ImportFrom@{node.lineno}"))
        for alias in node.names:
            qualified = f"{mod}.{alias.name}" if mod else alias.name
            self.imports.append((qualified, f"ImportFrom.name@{node.lineno}"))
        self.generic_visit(node)


def _registry_files() -> list[pathlib.Path]:
    return sorted(p for p in REGISTRY_ROOT.rglob("*.py") if p.is_file())


def test_smdl01_18_ast_no_network_or_storage_imports_zero_matches():
    col = _ImportCollector()
    for f in _registry_files():
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        col.visit(tree)

    hits: list[tuple[str, str, str]] = []
    for imp_name, location in col.imports:
        imp_lower = imp_name.lower()
        for forbidden in ALL_FORBIDDEN:
            if forbidden in imp_lower:
                hits.append((forbidden, imp_name, location))
    assert hits == []


def test_smdl01_18_import_modelregistry_success():
    from app.registry import ModelRegistry  # noqa: F401

    assert ModelRegistry is not None


def test_smdl01_18_sys_modules_no_network_from_registry_chain():
    already_loaded = set(sys.modules.keys())

    registry_snapshot = {
        k: v for k, v in sys.modules.items() if k.startswith("app.registry")
    }
    try:
        import importlib  # noqa: F401

        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("app.registry"):
                del sys.modules[mod_name]
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("app.registry"):
                del sys.modules[mod_name]

        from app.registry import ModelRegistry  # noqa: F401

        registry_related = {
            k for k in sys.modules.keys()
            if k.startswith("app.registry")
            or (k not in already_loaded and "registry" in k.lower())
        }

        forbidden_hits: list[tuple[str, str]] = []
        for mod_key in registry_related:
            mod_lower = mod_key.lower()
            for forb in ALL_FORBIDDEN:
                if forb in mod_lower:
                    forbidden_hits.append((mod_key, forb))

        assert forbidden_hits == []
    finally:
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("app.registry"):
                del sys.modules[mod_name]
        sys.modules.update(registry_snapshot)
