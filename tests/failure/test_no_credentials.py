from __future__ import annotations

import os
import re


APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SUSPICIOUS_STRINGS = [
    "api_key",
    "secret",
    "BINANCE_API_KEY",
    "OKX_KEY",
]
STRING_RE = re.compile(
    "|".join(re.escape(s) for s in SUSPICIOUS_STRINGS),
    re.IGNORECASE,
)

FORBIDDEN_FN_RE = re.compile(
    r"def\s+(send_real_order|place_exchange_order|live_execution)\b",
)


def _iter_py_files(root_dir: str):
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if not f.endswith(".py"):
                continue
            if f in {
                "test_no_credentials.py",
                "test_registry_no_credentials.py",
                "test_bus_no_credentials.py",
                "test_sopp01_21_credential_safety.py",
                "test_sopp01_24_safety_boundary.py",
                "test_srsk02_13_safety_regression_ast.py",
                "test_sptf03_cap14_cap1_cap2_safety8.py",
            }:
                continue
            yield os.path.join(root, f)


def test_static_no_api_key_strings():
    total_matches = 0
    scan_dirs = [
        os.path.join(APP_ROOT, "app"),
        os.path.join(APP_ROOT, "tests"),
    ]
    for d in scan_dirs:
        if not os.path.isdir(d):
            continue
        for fp in _iter_py_files(d):
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            matches = STRING_RE.findall(content)
            total_matches += len(matches)
    assert total_matches == 0, (
        f"Found {total_matches} suspicious credential-like strings in source"
    )


def test_static_no_real_order_function_names():
    total_matches = 0
    app_dir = os.path.join(APP_ROOT, "app")
    if os.path.isdir(app_dir):
        for fp in _iter_py_files(app_dir):
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            matches = FORBIDDEN_FN_RE.findall(content)
            total_matches += len(matches)
    assert total_matches == 0, (
        f"Found {total_matches} forbidden live-execution function definitions"
    )
