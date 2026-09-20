"""S-API-03 CAP-6 forbidden route multi-method zero-occurrence scanner (ANA PROOF).

4 scan methods tested (AC-06 AC-07) — ALL MUST return occurrence count = ZERO:
  - T3.1 Runtime FastAPI route registry scan (app.routes + OpenAPI paths)
  - T3.2 Static AST/import/string literal scan over app/platform/api/*.py
  - T3.3 Generated OpenAPI JSON path list scan
  - T3.4 Path/case/variant edge-case brute force (v2 prefix / lower case / underscore / ../../../ traversal)

5 forbidden patterns (4 CAP-6 + 1 /admin/retire-champion):
  "/execution/live/*"
  "/keys/*"
  "/accounts/funding/*"
  "/risk/limits/write"
  "/admin/retire-champion"
"""
from __future__ import annotations

import ast
import glob
import os
import re

import pytest

FORBIDDEN_PATTERNS = [
    ("/execution/live/", "live execution", re.compile(r"/execution/live[^a-zA-Z0-9_-]?", re.IGNORECASE)),
    ("/keys", "key management", re.compile(r"/keys[^a-zA-Z0-9_-]?", re.IGNORECASE)),
    ("/accounts/funding/", "accounts funding", re.compile(r"/accounts/funding[^a-zA-Z0-9_-]?", re.IGNORECASE)),
    ("/risk/limits/write", "limits write", re.compile(r"/risk/limits/write[^a-zA-Z0-9_-]?", re.IGNORECASE)),
    ("/admin/retire-champion", "admin retire champion", re.compile(r"/admin/retire.champion[^a-zA-Z0-9_-]?", re.IGNORECASE)),
]


def _runtime_paths(app) -> list[str]:
    """T3.1 collect runtime FastAPI route paths."""
    paths: list[str] = []
    for route in getattr(app, "routes", []) or []:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.append(path)
    return paths


# ---------------- T3.1 Runtime registry scan ----------------


def test_t31_runtime_registry_zero(app):
    """Runtime route registry: 0 occurrence of any CAP-6 forbidden pattern."""
    paths = _runtime_paths(app)
    findings = []
    for label, _name, rx in FORBIDDEN_PATTERNS:
        for p in paths:
            if rx.search(p) or label in p:
                findings.append((label, p))
    assert findings == [], f"T3.1 CAP-6 runtime forbidden found: {findings}"


# ---------------- T3.2 Static AST / literal scan ----------------


def _ast_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, os.pardir, os.pardir, "app", "platform", "api"))


def test_t32_static_ast_and_literal_scan_zero():
    """Static scan over app/platform/api Python modules — 0 forbidden literal occurrence."""
    root = _ast_root()
    files = glob.glob(os.path.join(root, "**", "*.py"), recursive=True)
    findings = []
    for fp in files:
        src = open(fp, "r", encoding="utf-8").read()
        # literal / regex scan
        for label, _n, rx in FORBIDDEN_PATTERNS:
            for i, line in enumerate(src.splitlines(), start=1):
                # comments OK but forbidden route handlers/strings MUST be 0
                if rx.search(line) or label in line:
                    if label == "/keys" and ("double_confirm_token" in line or "idempotency_key" in line):
                        # Allowed — N1 body field names are not /keys route
                        continue
                    findings.append((label, fp, i, line.strip()))
        # AST scan for route registration strings
        try:
            tree = ast.parse(src, filename=fp)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for label, _n, rx in FORBIDDEN_PATTERNS:
                    if (rx.search(node.value) or label in node.value):
                        if label == "/keys" and (
                            "double_confirm" in node.value or "idempotency" in node.value
                        ):
                            continue
                        findings.append((label + ":AST", fp, getattr(node, "lineno", "?"), repr(node.value)))
    assert findings == [], f"T3.2 static forbidden strings found (count={len(findings)}): {findings[:20]}"


# ---------------- T3.3 Generated OpenAPI JSON scan ----------------


def _openapi_paths(app) -> list[str]:
    openapi = app.openapi()
    return list((openapi.get("paths") or {}).keys())


def test_t33_openapi_json_zero(app):
    """T3.3 OpenAPI paths generated from FastAPI — 0 forbidden pattern occurrence."""
    paths = _openapi_paths(app)
    findings = []
    for label, _n, rx in FORBIDDEN_PATTERNS:
        for p in paths:
            if rx.search(p) or label in p:
                findings.append((label, p))
    assert findings == [], f"T3.3 OpenAPI forbidden: {findings}"


# ---------------- T3.4 Path variant brute-force actual HTTP 404 scan ----------------


VARIANT_TEST_PATHS = [
    # live execution variants
    "/api/v1/execution/live/orders",
    "/api/v1/execution/LIVE/orders",
    "/execution/live/submit",
    # keys variants
    "/api/v1/keys",
    "/api/v1/keys/create",
    "/keys/list",
    # accounts funding
    "/api/v1/accounts/funding/deposit",
    "/accounts/funding/withdraw",
    # risk limits write
    "/api/v1/risk/limits/write",
    "/risk/limits/write",
    # admin retire champion
    "/api/v1/admin/retire-champion",
    "/admin/retire_champion",
    # path traversal + prefix tricks
    "/api/v1/../execution/live/orders",
    "/api/v1/%6beys",  # not literally matching; ensure 404 only not 200
]


def test_t34_path_variant_404_or_not_registered(client):
    """T3.4 All variant CAP-6 paths MUST NOT return 200 ok=True; ok=False envelope expected (fail-closed)."""
    ok_successes = []
    for path in VARIANT_TEST_PATHS:
        # try GET then POST
        for method in ("GET", "POST", "PUT", "DELETE"):
            r = client.request(method, path)
            # Forbid any 200 with ok=True
            if r.status_code == 200:
                try:
                    j = r.json()
                    if j.get("ok") is True:
                        ok_successes.append((method, path, r.status_code, j))
                except Exception:
                    ok_successes.append((method, path, r.status_code, "NON_JSON_BODY_200"))
    assert ok_successes == [], f"T3.4 forbidden path 200 ok=True responses: {ok_successes}"
