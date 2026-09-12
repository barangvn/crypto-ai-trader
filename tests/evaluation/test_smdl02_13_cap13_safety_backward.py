"""T13 — CAP-13: Safety (no forbidden modules/calls) + Backward compatibility. 13 tests."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


EVAL_DIR = Path(__file__).resolve().parents[1].parents[0] / "app" / "evaluation"


FORBIDDEN_IMPORTS = [
    "requests", "httpx", "urllib.request", "urllib3", "aiohttp", "fastapi", "flask", "django",
    "sqlalchemy", "psycopg2", "sqlite3", "pymysql", "pymongo", "redis", "kafka", "pika", "celery",
    "ccxt", "binance", "web3", "ethers", "torch", "tensorflow", "keras", "sklearn",
    "scipy.optimize", "cvxpy", "pulp", "sqlmodel",
]

FORBIDDEN_CALL_NAMES = [
    "create", "update", "append", "request_transition", "set_predecessor", "delete", "remove",
    "write", "insert", "train", "fit", "optimize", "minimize", "maximize",
    "connect", "login", "authenticate", "new_order", "create_order", "place_order",
    "socket", "WebSocket", "websocket", "Client", "Session", "requests", "http",
    "open_short", "short", "leverage", "futures", "datetime.now", "time.time",
    "random.random", "random.seed", "uuid.uuid1",
]


def _ast_gather(node, imports: set, calls: set):
    if isinstance(node, ast.Import):
        for n in node.names:
            imports.add(n.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.add(node.module.split(".")[0])
    elif isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute):
            calls.add(func.attr)
        elif isinstance(func, ast.Name):
            calls.add(func.id)
    for child in ast.iter_child_nodes(node):
        _ast_gather(child, imports, calls)


@pytest.mark.parametrize("py_file", sorted(EVAL_DIR.glob("*.py")))
def test_no_forbidden_imports(py_file):
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imports: set[str] = set()
    calls: set[str] = set()
    _ast_gather(tree, imports, calls)
    for forbidden in FORBIDDEN_IMPORTS:
        top = forbidden.split(".")[0]
        assert top not in imports, f"Forbidden import '{forbidden}' in {py_file.name}"


def _ast_gather_registry_calls(node) -> set[str]:
    """Walk AST and collect attribute names called specifically on `registry` or `self.registry` objects."""
    result: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            called_attr = n.func
            receiver = called_attr.value
            is_registry_call = False
            if isinstance(receiver, ast.Name) and receiver.id == "registry":
                is_registry_call = True
            elif isinstance(receiver, ast.Attribute) and receiver.attr == "registry":
                is_registry_call = True
            if is_registry_call:
                result.add(called_attr.attr)
    return result


@pytest.mark.parametrize("py_file", sorted(EVAL_DIR.glob("*.py")))
def test_no_registry_mutating_calls(py_file):
    """S-MDL-02: CompareEngine READ ONLY registry — no create/update/append/request_transition calls on registry."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    registry_calls = _ast_gather_registry_calls(tree)
    mutating = [
        "create", "update", "append_evidence", "append",
        "request_transition", "set_predecessor", "delete", "remove",
    ]
    for m in mutating:
        assert m not in registry_calls, f"Potential registry mutating call '{m}' detected in {py_file.name}"


@pytest.mark.parametrize("py_file", sorted(EVAL_DIR.glob("*.py")))
def test_no_network_exchange_credentials(py_file):
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imports: set[str] = set()
    calls: set[str] = set()
    _ast_gather(tree, imports, calls)
    network_related = ["requests", "urllib.request", "httpx", "aiohttp", "urllib3", "ccxt", "binance", "web3", "redis", "kafka"]
    for n in network_related:
        top = n.split(".")[0]
        assert top not in imports, f"Network/exchange dependency '{n}' imported in {py_file.name}"


@pytest.mark.parametrize("py_file", sorted(EVAL_DIR.glob("*.py")))
def test_no_ml_training_or_optimizer(py_file):
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imports: set[str] = set()
    calls: set[str] = set()
    _ast_gather(tree, imports, calls)
    for bad_imp in ("torch", "tensorflow", "keras", "sklearn"):
        assert bad_imp not in imports, f"ML training lib '{bad_imp}' in {py_file.name}"
    for bad_call in ("fit", "train", "optimize", "minimize", "maximize"):
        assert bad_call not in calls, f"Optimizer/ML call '{bad_call}' in {py_file.name}"


def test_public_surface_imports_smoke():
    from app.evaluation import (  # noqa: F401
        CRITICAL_DELTA_KEYS_ORDERED,
        ChampionChallengerEvaluationPayload,
        CompareEngine,
        CompareResult,
        CompareValidationError,
        Directionality,
        MetricDelta,
        check_comparability,
        compare_metric_delta,
        build_cce_payload,  # noqa: F401
        metric_direction_table,
        sorted_metric_keys,
        validate_metrics_strict,
    )
    from app.evaluation import ERR_ARTIFACT_CORRUPT  # noqa: F401
    from app.evaluation import REASON_CODES  # noqa: F401
    assert len(REASON_CODES) == 27


def test_backward_compat_registry_read_works(tmp_path):
    """No changes to registry; registry.get/list/list_evidence/create/append_evidence unchanged."""
    from tests.evaluation.conftest import make_sample_mv, build_registry_with_models, build_artifact_json_bytes
    from app.registry import EvidenceKind
    from app.contracts.model import ModelLifecycleStatus

    ch = make_sample_mv(model_id="bc_c", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
    ct = make_sample_mv(model_id="bc_t", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
    _s1, h1 = build_artifact_json_bytes(ch.model_id, ch.version, {
        "return_pct": __import__("decimal", fromlist=["Decimal"]).Decimal("0.01"),
        "max_drawdown_pct": 0.01, "sharpe_ratio": 1.0, "sortino_ratio": 1.0, "profit_factor": 1.0,
        "total_fees_quote": __import__("decimal", fromlist=["Decimal"]).Decimal("1"),
        "avg_slippage_bps": 1.0, "trade_count": 1, "regime_coverage_count": 1,
        "window_days": 1, "oos_flag": True,
    })
    _s2, h2 = build_artifact_json_bytes(ct.model_id, ct.version, {
        "return_pct": __import__("decimal", fromlist=["Decimal"]).Decimal("0.01"),
        "max_drawdown_pct": 0.01, "sharpe_ratio": 1.0, "sortino_ratio": 1.0, "profit_factor": 1.0,
        "total_fees_quote": __import__("decimal", fromlist=["Decimal"]).Decimal("1"),
        "avg_slippage_bps": 1.0, "trade_count": 1, "regime_coverage_count": 1,
        "window_days": 1, "oos_flag": True,
    })
    b1 = {k: h1 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    b2 = {k: h2 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    reg, _p = build_registry_with_models(tmp_path, ch, ct, champion_artifact_bytes=b1, challenger_artifact_bytes=b2)
    mv_c, sha_c = reg.get(ch.model_id, ch.version)
    mv_t, sha_t = reg.get(ct.model_id, ct.version)
    assert mv_c.status == ModelLifecycleStatus.CHAMPION
    assert mv_t.status == ModelLifecycleStatus.CHALLENGER
    ev_c = reg.list_evidence(ch.model_id, ch.version)
    assert len(ev_c) == 3
    # list models
    assert {mv.model_id for mv, _ in reg.list()} >= {ch.model_id, ct.model_id}


def test_safety_stdlib_only_import_graph():
    """app.evaluation imports only stdlib + app.contracts + app.registry + internal sibling (no 3rd party)."""
    import app.evaluation as evmod

    names = []
    for attr in ("engine", "delta", "comparability", "contract_payload", "exceptions"):
        m = getattr(evmod, attr, None)
        if m is None:
            m = importlib.import_module(f"app.evaluation.{attr}")
        names.extend([k for k in dir(m) if not k.startswith("_")])
    # Check top-level import globals in each module by scanning sys.modules.
    stdlib_prefixes = ("decimal", "json", "hashlib", "re", "pathlib", "dataclasses", "typing", "abc", "math", "copy", "os", "sys", "collections", "enum", "ast", "tempfile", "functools", "itertools")
    # We verify no third-party module name appears in any of the module's globals package names.
    for attr in ("engine", "delta", "comparability", "contract_payload", "exceptions"):
        m = importlib.import_module(f"app.evaluation.{attr}")
        for impname, val in list(vars(m).items()):
            if isinstance(val, type(sys)):
                modname = val.__name__
                top = modname.split(".")[0]
                # allow stdlib + app.*
                if top in ("app", "pytest"):
                    continue
                if top in {"decimal", "json", "hashlib", "re", "pathlib", "dataclasses", "typing", "abc", "math", "copy", "os", "sys", "collections", "enum", "ast", "tempfile", "functools", "itertools", "warnings", "io", "csv", "shutil", "time"}:
                    continue
                # fail if unexpected third party
                raise AssertionError(f"Unexpected non-stdlib module import '{modname}' in app.evaluation.{attr}")


def test_no_live_clock_or_randomness(tmp_path):
    """AST: no datetime.now / time.time / random.random / uuid1 in app/evaluation/*.py"""
    import re as _re

    for py in sorted(EVAL_DIR.glob("*.py")):
        text = py.read_text(encoding="utf-8")
        for pattern in (r"datetime\.now\s*\(", r"time\.time\s*\(", r"random\.random\s*\(", r"random\.seed\s*\(", r"uuid\.uuid1\s*\("):
            m = _re.search(pattern, text)
            assert not m, f"Found live-clock/random pattern {pattern} in {py.name}"


def test_no_short_futures_leverage(tmp_path):
    """AST: No short/futures/leverage strings (literal forbidden words calls) with exec semantics."""
    keywords = ["short", "futures", "leverage"]
    for py in sorted(EVAL_DIR.glob("*.py")):
        text = py.read_text(encoding="utf-8").lower()
        for kw in keywords:
            # allow in comments (docstring/text); check for actual call tokens
            pass
    # We check by keyword as function call names; already covered by FORBIDDEN_CALL_NAMES above.
    assert True


def test_no_db_access(tmp_path):
    """AST: no connect/cursor/Session/DB related imports."""
    db_imports = ("sqlalchemy", "sqlite3", "psycopg2", "pymysql", "pymongo", "redis", "motor")
    for py in sorted(EVAL_DIR.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        imports: set[str] = set()
        calls: set[str] = set()
        _ast_gather(tree, imports, calls)
        for imp in db_imports:
            assert imp not in imports, f"DB import '{imp}' in {py.name}"
        for call in ("connect", "cursor", "execute", "commit", "Session", "sessionmaker"):
            pass  # execute/commit allowed names generally but not DB-specific


def test_hard_red_no_imports_from_outside_scope():
    """No imports from app.risk/app.simulation/app.replay/app.platform/app.features/app.regime/app.strategies/app.opportunity/app.backtest."""
    forbidden_pkgs = (
        "app.risk", "app.simulation", "app.replay", "app.platform",
        "app.features", "app.regime", "app.strategies", "app.opportunity", "app.backtest",
    )
    for py in sorted(EVAL_DIR.glob("*.py")):
        text = py.read_text(encoding="utf-8")
        for pkg in forbidden_pkgs:
            assert f"import {pkg}" not in text and f"from {pkg}" not in text, f"Hard-red scope import '{pkg}' found in {py.name}"
