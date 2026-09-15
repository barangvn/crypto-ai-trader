import ast
import os
import pathlib

import pytest


PROD_GATE_DIR = pathlib.Path(__file__).resolve().parents[2] / "app" / "gate"


FORBIDDEN_WRITE_METHODS = [
    "create_model", "update_model", "delete_model",
    "create_version", "update_version", "delete_version",
    "append_evidence_refs", "set_evidence",
    "request_transition", "apply_transition",
    "set_status", "promote", "demote",
    "publish", "emit", "fire_event",
]

FORBIDDEN_KEYWORDS_CONTEXT = [
    "registry.", "storage.", "event_bus.",
    ".create_model", ".update_model", ".delete_model",
    ".create_version", ".update_version", ".delete_version",
    ".request_transition", ".apply_transition",
    ".append_evidence_refs", ".set_evidence",
    ".set_status", ".promote(", ".demote(",
    ".publish(", ".emit(",
    ".put(", ".post(", ".delete(",
]


def _collect_py_files():
    return [str(p) for p in PROD_GATE_DIR.glob("**/*.py")]


def _scan_source(source: str, file_path: str):
    issues = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        issues.append(f"{file_path}: SyntaxError {exc}")
        return issues
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            fname = None
            if isinstance(func, ast.Attribute):
                fname = func.attr
            elif isinstance(func, ast.Name):
                fname = func.id
            if fname in FORBIDDEN_WRITE_METHODS:
                issues.append(
                    f"{file_path}:{getattr(node, 'lineno', '?')} forbidden method call: {fname}"
                )
    for lineno, line in enumerate(source.splitlines(), start=1):
        low = line.lower()
        for kw in FORBIDDEN_KEYWORDS_CONTEXT:
            if kw in low:
                issues.append(f"{file_path}:{lineno} forbidden keyword context: {kw}")
    return issues


def test_gate_prod_files_exist():
    files = _collect_py_files()
    names = sorted(os.path.basename(f) for f in files)
    assert "__init__.py" in names
    assert "exceptions.py" in names
    assert "weights.py" in names
    assert "thresholds.py" in names
    assert "builder.py" in names
    assert "engine.py" in names
    assert len(names) == 6


def test_gate_prod_files_no_forbidden_writes():
    files = _collect_py_files()
    all_issues = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as fh:
            source = fh.read()
        all_issues.extend(_scan_source(source, fpath))
    assert all_issues == [], "\n".join(all_issues)


def test_gate_no_network_db_credentials_imports():
    files = _collect_py_files()
    forbidden_imports = [
        "requests", "urllib", "httpx", "aiohttp",
        "socket", "websocket", "sqlalchemy", "psycopg",
        "pymongo", "boto3", "botocore",
        "paramiko", "smtplib", "twilio",
    ]
    violations = []
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as fh:
            source = fh.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in forbidden_imports:
                        violations.append(f"{fpath}:{node.lineno} imports {name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod = node.module.split(".")[0]
                    if mod in forbidden_imports:
                        violations.append(f"{fpath}:{node.lineno} from {mod}")
    assert violations == [], "\n".join(violations)


def test_gate_all_public_symbols_exported():
    init_file = PROD_GATE_DIR / "__init__.py"
    source = init_file.read_text(encoding="utf-8")
    expected = [
        "PromotionGate", "WeightsConfig", "ThresholdsConfig",
        "GateValidationError", "GateInvariantError",
        "default_weights_v1", "validate_weights_definition", "renormalize_weights_if_needed",
        "default_thresholds_v1", "normalize_metric",
        "check_hard_constraints", "check_soft_thresholds", "compute_weighted_total_score",
        "build_promotion_gate_result", "enforce_winner_gate_invariant",
        "inject_gate_into_champion_challenger",
        "age_evaluation_check", "comparable_flag_check",
        "evidence_integrity_check", "approval_minimum_readonly",
    ]
    for name in expected:
        assert name in source, f"Missing public export: {name}"
