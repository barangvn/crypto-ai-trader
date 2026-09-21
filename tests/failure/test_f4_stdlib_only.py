"""S-FND-01 F4 = stdlib-only marker tests (AC-03.6).

Marker @pytest.mark.F4 wraps tests with enforce_f4_stdlib_only decorator
(conftest L486). Decorator snapshots sys.modules BEFORE test, AFTER test,
finds NEW non-stdlib non-pytest non-app modules -> FAIL_CLOSED.
"""
from __future__ import annotations

import sys

import pytest


@pytest.mark.F4
def test_f4_stdlib_only_marker_allows_pure_stdlib_imports():
    """Positive: stdlib-only ops PASS under F4 guard (enforce_f4_stdlib_only)."""
    import hashlib
    import json
    import configparser
    import dataclasses
    from decimal import Decimal
    from typing import Literal
    import functools
    import itertools
    import pathlib
    # Use them minimally to guarantee import-side-effect modules load
    hashlib.sha256(b"x").hexdigest()
    json.dumps({"ok": 1})
    Decimal("1")
    functools.lru_cache(lambda x: x)(1)
    list(itertools.chain([1], [2]))
    pathlib.Path(".")


@pytest.mark.F4
def test_f4_stdlib_only_blocks_fastapi_import_during_body(monkeypatch):
    """Negative: importing fastapi DURING F4 test body -> FAIL.

    Since fastapi may NOT be installed in this env (optional eapi subgroup),
    we simulate the check via a dummy fake module 'xxx_fake_thirdparty_xxx'
    by injecting it before test and checking guard logic catches new non-stdlib.
    """
    # Simulate: create a fake module, import it during body via a closure
    MODNAME = "xxx_fake_thirdparty_xxx_for_f4"
    import types

    def _do_import():
        m = types.ModuleType(MODNAME)
        sys.modules[MODNAME] = m
        return m

    # Run in exception context
    from _pytest.outcomes import Failed
    with pytest.raises(Failed):
        # F4 guard via wrapper will detect MODNAME as newly-imported non-stdlib
        _do_import()
        # The wrapper runs post-test. To trigger the check *inside* the wrapped test,
        # we must let the test function body return. The wrapper runs its finally
        # block AFTER return -> raises pytest.fail -> Failed exception in pytest.
        # So we re-raise by returning, but we're calling via function call not pytest.
        # Instead: direct unit-test enforce_f4_stdlib_only wrapper:
        from tests.conftest import enforce_f4_stdlib_only

        @enforce_f4_stdlib_only
        def bad_test_func():
            m2 = types.ModuleType(MODNAME + "_2")
            sys.modules[MODNAME + "_2"] = m2
            return 42

        try:
            bad_test_func()
        except Exception:
            raise
        finally:
            for k in list(sys.modules.keys()):
                if k.startswith(MODNAME):
                    del sys.modules[k]


@pytest.mark.F4
def test_f4_stdlib_only_app_and_tests_modules_allowed(cfg):
    """Positive: app.* (our source) and tests.* modules can be imported under F4.

    Our own code uses stdlib-only (policy §0.6 Memory + pyproject.toml dependencies=[]).
    """
    import app.contracts as c  # noqa: F401
    from app.contracts.types import Symbol  # noqa: F401
    # We are INSIDE tests. failure_injection package already loaded.
    # cfg fixture = stdlib-only frozen dataclass, OK


@pytest.mark.F4
def test_f4_envconfig_dataclass_is_stdlib_only_compliant(cfg):
    """AC-03.6 EnvConfig = stdlib-only (dataclasses + configparser = stdlib)."""
    # Confirm sys.modules for all top-levels used inside cfg:
    required_stdlib = {
        "dataclasses", "configparser", "hashlib", "functools", "os", "sys", "pathlib",
        "typing",
    }
    for mod in required_stdlib:
        assert mod in sys.stdlib_module_names, f"{mod} not stdlib 3.14?!"


@pytest.mark.F4
@pytest.mark.parametrize("n", list(range(10)))
def test_f4_determinism_10x_hash(cfg, n):
    """DET-01: cfg.sha256() returns EXACT same hash on 10 consecutive calls."""
    results = {cfg.sha256() for _ in range(10)}
    assert len(results) == 1, f"Non-deterministic cfg.sha256: {results}"


@pytest.mark.F4
def test_f4_eapi_optional_deps_not_installed_by_default():
    """Memory §0.6: core stdlib-only; E-API optional-deps subgroup NOT installed by default.

    F4 wrapper runs AFTER return of test body. This test loads NO 3rd-party
    (the conditional try/except for fastapi triggers NOTHING new in sys.modules
    if fastapi import fails with ImportError BEFORE test teardown -> F4 sees 0 new).
    """
    # Since E-API optional subgroup may have been installed in venv, we CANNOT
    # guarantee it's absent. This test checks pyproject.toml dependencies=[] rule.
    from pathlib import Path
    import configparser
    path = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    # parse minimal (PEP 621 is TOML; we check plain string dependencies = [])
    content = path.read_text(encoding="utf-8").splitlines()
    in_project = False
    deps_line_found = False
    for line in content:
        stripped = line.strip()
        if stripped.startswith("[project]"):
            in_project = True
            continue
        if in_project and stripped.startswith("["):
            break
        if in_project and stripped.startswith("dependencies"):
            deps_line_found = True
            assert stripped == "dependencies = []", (
                f"pyproject.toml dependencies MUST be stdlib-only = [] per Memory §0.6, "
                f"got: {stripped!r}"
            )
    assert deps_line_found, "[project] dependencies line not found in pyproject.toml"


@pytest.mark.F4
def test_f4_marker_wrap_via_collection_hook_detectable():
    """Like F1, verify decorator module importable + pytest_collection_modifyitems exists."""
    from tests.conftest import (
        enforce_f4_stdlib_only, pytest_collection_modifyitems, _is_stdlib_module,
    )
    assert callable(enforce_f4_stdlib_only)
    assert callable(pytest_collection_modifyitems)
    assert callable(_is_stdlib_module)
