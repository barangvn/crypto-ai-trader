from __future__ import annotations

"""AC-28: hassas kelimeler (api_key, secret, BINANCE_API_KEY, OKX_KEY, send_real_order,
place_exchange_order, live_execution) taraması → bus kodunda + yeni test dosyalarında 0 match.

Kendini taramamak için concat pattern + exclude_names kullan."""

import ast
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
APP_BUS_DIR = ROOT / "app" / "platform"
TEST_DIRS = [
    ROOT / "tests" / "unit" / "platform",
    ROOT / "tests" / "integration",
    ROOT / "tests" / "replay",
    ROOT / "tests" / "failure",
    ROOT / "tests" / "contracts",
]


# Hassas kelimeleri concat ile parçala — regex taraması kendini bulmasın
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
del (
    _S_API, _S_AP, _S_SEC, _S_BIN, _S_OKX, _S_REAL, _S_XCHG, _S_LIVE,
    _S_SUB, _S_PLACE, _S_ORDER, _S_KEY, _S_EXEC, _S_TO,
)


def _build_pattern(terms: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)


CREDS_PATTERN: re.Pattern[str] = _build_pattern(_CREDS_TERMS)
LIVE_FN_PATTERN: re.Pattern[str] = _build_pattern(_LIVE_TERMS)
del _build_pattern, _CREDS_TERMS, _LIVE_TERMS


def _iter_py_files(dirs: list[Path]) -> list[Path]:
    out: list[Path] = []
    # Kendini ve diğer credential tarayıcıları exclude et (concat pattern kullansınlar diye)
    exclude_names = {
        "test_bus_no_credentials.py",
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
    # Ayrıca app/platform/*.py ekle (event_bus.py ve platform __init__)
    for p in APP_BUS_DIR.rglob("*.py"):
        if p.name not in exclude_names:
            out.append(p)
    return sorted(set(out))


@pytest.mark.failure_injection
class TestBusNoCredentials:
    def test_event_bus_source_no_credentials_or_live_order_patterns(self) -> None:
        files = _iter_py_files(TEST_DIRS)
        violations: list[tuple[str, int, str, str]] = []
        for p in files:
            src = p.read_text(encoding="utf-8")
            for lineno, line in enumerate(src.splitlines(), start=1):
                for pat_name, pat in (
                    ("CREDS", CREDS_PATTERN),
                    ("LIVE_FN", LIVE_FN_PATTERN),
                ):
                    m = pat.search(line)
                    if m:
                        violations.append(
                            (str(p.relative_to(ROOT)), lineno, pat_name, line.strip()[:100])
                        )
        if violations:
            lines = "\n".join(
                f"  - {v[0]}:L{v[1]} [{v[2]}] {v[3]!r}" for v in violations[:30]
            )
            raise AssertionError(
                f"Credential/live-order pattern violations ({len(violations)}):\n{lines}"
            )

    def test_event_bus_ast_no_prohibited_literals(self) -> None:
        """AST string literal taraması — string concat kullanıldığında bu test de 0 match vermeli,
        çünkü hassas kelimeleri parçalıyoruz."""
        files = _iter_py_files(TEST_DIRS)
        # Hassas kelimeleri tekrar (bu kez doğrudan string olarak AST literal arıyoruz)
        _ALL_TERMS = [
            "api_key", "apikey", "secret", "secret_key",
            "binance_api_key", "okx_key",
            "send_real_order", "place_exchange_order",
            "live_execution", "submit_order_to_exchange",
            "place_real_order",
        ]
        literal_re = re.compile(
            "|".join(re.escape(t) for t in _ALL_TERMS),
            re.IGNORECASE,
        )
        violations: list[tuple[str, int, str]] = []
        for p in files:
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if literal_re.search(node.value):
                        violations.append(
                            (
                                str(p.relative_to(ROOT)),
                                getattr(node, "lineno", 0),
                                node.value[:80],
                            )
                        )
        if violations:
            lines = "\n".join(
                f"  - {v[0]}:L{v[1]} literal={v[2]!r}" for v in violations[:30]
            )
            raise AssertionError(
                f"Prohibited string literal violations ({len(violations)}):\n{lines}"
            )
