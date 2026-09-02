from __future__ import annotations

import ast
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
APP_BACKTEST = ROOT / "app" / "backtest"


def _collect_ast_for(module_path: pathlib.Path):
    source = module_path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(module_path))


_DISALLOWED_ATTRS_CAP1 = {
    "now",           # datetime.now
    "today",         # date.today / datetime.today
    "utcnow",        # datetime.utcnow
    "time",          # time.time()
    "sleep",         # time.sleep()
    "random",        # random.random, random.seed etc used standalone
    "choice",        # random.choice
    "randint",       # random.randint
    "randrange",     # random.randrange
}


def _iter_all_calls(tree, module_name: str):
    disallowed = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                name = func.attr
                if name in _DISALLOWED_ATTRS_CAP1:
                    lineno = getattr(node, "lineno", 0)
                    disallowed.append((module_name, lineno, f"{name}() CAP-1 forbidden"))
            # Also check for: datetime.now() → isinstance(func.value, ast.Name) and func.value.id == "datetime"
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                base = func.value.id
                attr = func.attr
                if base == "datetime" and attr in ("now", "today", "utcnow"):
                    lineno = getattr(node, "lineno", 0)
                    disallowed.append((module_name, lineno, f"datetime.{attr}() CAP-1 FORBIDDEN in deterministic path"))
                if base == "time" and attr in ("time", "sleep", "monotonic", "perf_counter"):
                    lineno = getattr(node, "lineno", 0)
                    disallowed.append((module_name, lineno, f"time.{attr}() CAP-1 FORBIDDEN in deterministic path"))
    return disallowed


_WRITER_KEYWORDS_SINGLE_WRITER = (
    "save_position",
    "write_position",
    "persist_position",
    "insert_position",
    "save_portfolio",
    "write_portfolio",
    "persist_portfolio",
    "insert_portfolio",
    "update_position",
    "update_portfolio",
)


def _iter_violations_single_writer(tree, module_name: str):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            name = node.func.attr
            for k in _WRITER_KEYWORDS_SINGLE_WRITER:
                if k in name.lower():
                    out.append((module_name, getattr(node, "lineno", 0), f"single-writer violation: {name}"))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            for k in _WRITER_KEYWORDS_SINGLE_WRITER:
                if k in name.lower():
                    out.append((module_name, getattr(node, "lineno", 0), f"single-writer function: {name}"))
    return out


_CAP2_MUTATE_KEYWORDS = (
    "quality_flags",
)


def _iter_cap2_violations(tree, module_name: str):
    """CAP-2: backtest must NOT mutate quality_flags or call validator."""
    out = []
    for node in ast.walk(tree):
        # look for assignment target whose attr is quality_flags.* or a setattr
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Attribute):
                    chain = []
                    cur = tgt
                    while isinstance(cur, ast.Attribute):
                        chain.append(cur.attr)
                        cur = cur.value
                    if "quality_flags" in chain:
                        out.append((module_name, getattr(tgt, "lineno", 0), f"CAP-2 mutate quality_flags: {'/'.join(reversed(chain))}"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if "validate" in attr.lower() and "quality" in attr.lower():
                out.append((module_name, getattr(node, "lineno", 0), f"CAP-2 validator call: {attr}"))
            if "validator" in attr.lower():
                out.append((module_name, getattr(node, "lineno", 0), f"CAP-2 validator call: {attr}"))
    return out


_SAFETY_FORBIDDEN_MODULES = {
    "requests",
    "httpx",
    "websocket",
    "websockets",
    "urllib",
    "urllib3",
    "aiohttp",
    "psycopg2",
    "sqlalchemy",
    "kafka",
    "redis",
    "pika",
    "ccxt",
    "binance",
}


def _iter_safety_violations(tree, module_name: str):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                names = [node.module or ""]
            for n in names:
                for forbidden in _SAFETY_FORBIDDEN_MODULES:
                    if forbidden.lower() in n.lower():
                        out.append((module_name, getattr(node, "lineno", 0), f"safety forbidden import: {n}"))
    return out


FILES = [
    APP_BACKTEST / "pipeline.py",
    APP_BACKTEST / "runner.py",
    APP_BACKTEST / "ordering.py",
    APP_BACKTEST / "run_metadata.py",
]


class TestCAP1NoWallClock:
    @pytest.mark.parametrize("f", FILES, ids=lambda f: f.name)
    def test_no_datetime_now_time_sleep_random(self, f):
        tree = _collect_ast_for(f)
        bad = _iter_all_calls(tree, f.name)
        assert bad == [], f"CAP-1 violations in {f.name}: {bad[:5]}"

    @pytest.mark.parametrize("f", FILES, ids=lambda f: f.name)
    def test_no_import_of_time_datetime_calls(self, f):
        # this double-check runs ast walk over Call nodes (same as above but more explicit)
        tree = _collect_ast_for(f)
        source = f.read_text(encoding="utf-8")
        if f.name == "pipeline.py":
            # pipeline imports os for urandom is OK, but datetime NOT allowed in calls
            pass
        # ensure no datetime.now / time.time strings even as text
        assert "datetime.now()" not in source, f"CAP-1 datetime.now() literal found in {f.name}"
        assert "time.time()" not in source, f"CAP-1 time.time() literal found in {f.name}"
        assert "time.sleep(" not in source, f"CAP-1 time.sleep( literal found in {f.name}"


class TestSingleWriter:
    @pytest.mark.parametrize("f", FILES, ids=lambda f: f.name)
    def test_no_writer_calls_in_backtest(self, f):
        tree = _collect_ast_for(f)
        bad = _iter_violations_single_writer(tree, f.name)
        assert bad == [], f"Single-writer violations in {f.name}: {bad[:5]}"


class TestCAP2QualityFlags:
    @pytest.mark.parametrize("f", FILES, ids=lambda f: f.name)
    def test_no_quality_mutation_or_validator(self, f):
        tree = _collect_ast_for(f)
        bad = _iter_cap2_violations(tree, f.name)
        assert bad == [], f"CAP-2 violations in {f.name}: {bad[:5]}"

    @pytest.mark.parametrize("f", FILES, ids=lambda f: f.name)
    def test_no_setattr_quality_flags(self, f):
        src = f.read_text(encoding="utf-8")
        assert "quality_flags.valid =" not in src
        assert "quality_flags.quarantined =" not in src


class TestSafetyNoNetwork:
    @pytest.mark.parametrize("f", FILES, ids=lambda f: f.name)
    def test_no_network_imports(self, f):
        tree = _collect_ast_for(f)
        bad = _iter_safety_violations(tree, f.name)
        assert bad == [], f"Safety network imports in {f.name}: {bad[:5]}"


class TestDependencyStdlibOnly:
    def test_backtest_init_only_internal_imports(self):
        src = (APP_BACKTEST / "__init__.py").read_text(encoding="utf-8")
        # import lines should be app.* only
        for line in src.splitlines():
            s = line.strip()
            if s.startswith("import ") and not s.startswith("from "):
                assert "app.backtest" in s or "__future__" in s, s
            if s.startswith("from "):
                mod = s.split()[1]
                # __future__ imports are syntactic markers, exempt
                if mod == "__future__":
                    continue
                assert mod.startswith("app."), f"non-app import found: {s}"
