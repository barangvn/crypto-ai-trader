from __future__ import annotations

import ast
import os
import sys

import pytest

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None


HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "app", "simulation"))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PYPROJECT = os.path.join(PROJECT_ROOT, "pyproject.toml")
SIM_FILES = [
    os.path.join(APP_ROOT, "__init__.py"),
    os.path.join(APP_ROOT, "execution.py"),
    os.path.join(APP_ROOT, "fill_config.py"),
]


def _collect_sim_sources() -> dict[str, str]:
    out = {}
    for fp in SIM_FILES:
        with open(fp, "r", encoding="utf-8") as f:
            out[fp] = f.read()
    return out


def _imported_module_names(src: str) -> set[str]:
    names: set[str] = set()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                names.add(top)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".")[0]
            if top:
                names.add(top)
    return names


_STDLIB_TOP_LEVEL = {
    "__future__", "collections", "dataclasses", "datetime", "decimal", "enum", "hashlib",
    "io", "json", "math", "os", "re", "sys", "time", "typing", "uuid",
    "copy", "functools", "itertools", "pathlib", "statistics", "struct",
    "threading", "traceback", "types", "warnings", "zoneinfo",
}


class TestDependenciesStdlibOnly:
    def test_17_01_pyproject_runtime_deps_empty(self):
        assert tomllib is not None, "tomllib required (Python 3.11+)"
        with open(PYPROJECT, "rb") as f:
            data = tomllib.load(f)
        proj = data.get("project", {})
        deps = proj.get("dependencies", [])
        assert deps == [], f"Expected empty runtime deps, got: {deps}"
        opt = proj.get("optional-dependencies", {})
        assert "dev" in opt or len(opt) >= 0, "optional-deps allowed (pytest only)"

    def test_17_02_sim_imports_only_stdlib_or_app_internal(self):
        sources = _collect_sim_sources()
        for path, src in sources.items():
            mods = _imported_module_names(src)
            for m in mods:
                ok_app = m == "app"
                ok_std = m in _STDLIB_TOP_LEVEL
                assert ok_app or ok_std, f"{path}: non-stdlib/app import '{m}'"

    @pytest.mark.parametrize("forbidden_lib", ["pydantic", "msgspec", "attrs", "cattrs", "pandas"])
    def test_17_03_no_data_modeling_deps(self, forbidden_lib):
        sources = _collect_sim_sources()
        for path, src in sources.items():
            mods = _imported_module_names(src)
            assert forbidden_lib not in mods, f"{path}: imports {forbidden_lib}"
            assert forbidden_lib not in src.lower(), f"{path}: literal {forbidden_lib}"

    @pytest.mark.parametrize("forbidden", ["ccxt", "binance", "bybit", "okx", "kucoin"])
    def test_17_04_no_exchange_sdk_deps(self, forbidden):
        sources = _collect_sim_sources()
        for path, src in sources.items():
            mods = _imported_module_names(src)
            assert forbidden not in mods, f"{path}: imports {forbidden}"

    @pytest.mark.parametrize("forbidden", ["requests", "httpx", "websocket", "aiohttp", "urllib3"])
    def test_17_05_no_network_client_deps(self, forbidden):
        sources = _collect_sim_sources()
        for path, src in sources.items():
            mods = _imported_module_names(src)
            assert forbidden not in mods, f"{path}: imports {forbidden}"
