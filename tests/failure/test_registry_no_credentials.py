from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app" / "ingest" / "registry"
TEST_DIRS = [
    ROOT / "tests" / "unit" / "ingest" / "registry",
    ROOT / "tests" / "integration",
    ROOT / "tests" / "replay",
    ROOT / "tests" / "failure",
    ROOT / "tests" / "contracts",
]


_S_API = "api"
_S_AP = _S_API + "_"
_S_SEC = "sec" + "ret"
_S_BIN = "bin" + "ance"
_S_OKX = "okx"
_S_REAL = "real"
_S_XCHG = "exch" + "ange"
_S_LIVE = "live"
_S_SUB = "sub" + "mit"
_S_PLACE = "place"
_S_ORDER = "order"
_S_KEY = "key"
_S_EXEC = "exec" + "ution"
_S_TO = "to"

_CREDS_TERMS: list[str] = [
    _S_AP + _S_KEY,
    _S_API + _S_KEY,
    _S_AP + _S_SEC,
    _S_SEC + "_" + _S_KEY,
    _S_BIN + "_" + _S_API + "_" + _S_KEY,
    _S_OKX + "_" + _S_KEY,
]
_LIVE_TERMS: list[str] = [
    "send" + "_" + _S_REAL + "_" + _S_ORDER,
    _S_PLACE + "_" + _S_XCHG + "_" + _S_ORDER,
    _S_LIVE + "_" + _S_EXEC,
    _S_SUB + "_" + _S_ORDER + "_" + _S_TO + "_" + _S_XCHG,
    _S_PLACE + "_" + _S_REAL + "_" + _S_ORDER,
]
del _S_API, _S_AP, _S_SEC, _S_BIN, _S_OKX, _S_REAL, _S_XCHG, _S_LIVE, _S_SUB, _S_PLACE, _S_ORDER, _S_KEY, _S_EXEC, _S_TO


def _build_pattern(terms: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)


CREDS_PATTERN: re.Pattern[str] = _build_pattern(_CREDS_TERMS)
LIVE_FN_PATTERN: re.Pattern[str] = _build_pattern(_LIVE_TERMS)
del _build_pattern, _CREDS_TERMS, _LIVE_TERMS


def _iter_py_files(dirs: list[Path]) -> list[Path]:
    out: list[Path] = []
    exclude_names = {
        "test_registry_no_credentials.py",
        "test_no_credentials.py",
    }
    for d in dirs:
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            if p.name in exclude_names:
                continue
            out.append(p)
    return out


@pytest.mark.failure_injection
class TestRegistryNoCredentials:
    def test_registry_module_has_no_credentials_strings(self) -> None:
        files = _iter_py_files([APP_DIR, *TEST_DIRS])
        hits: list[str] = []
        for f in files:
            try:
                txt = f.read_text(encoding="utf-8")
            except Exception:
                continue
            for m in CREDS_PATTERN.findall(txt):
                hits.append(f"{f}:{m}")
        assert not hits, f"Credential-like strings found: {hits[:20]}"

    def test_registry_no_live_execution_functions(self) -> None:
        files = _iter_py_files([APP_DIR, *TEST_DIRS])
        hits: list[str] = []
        for f in files:
            try:
                txt = f.read_text(encoding="utf-8")
                tree = ast.parse(txt, filename=str(f))
            except Exception:
                continue
            names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}
            for n in names:
                if LIVE_FN_PATTERN.search(n):
                    hits.append(f"{f}:{n}")
            for m in LIVE_FN_PATTERN.findall(txt):
                hits.append(f"{f}:{m}")
        assert not hits, f"Live execution function patterns found: {hits[:20]}"
