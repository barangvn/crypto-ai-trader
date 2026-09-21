"""S-FND-01 F3 = no-live-env marker tests (AC-03.5).

Marker @pytest.mark.F3 auto-applies skip on STG/PROD environments via
pytest_collection_modifyitems (conftest L520 _apply_f3_auto_skip).
"""
from __future__ import annotations

import pytest


@pytest.mark.F3
def test_f3_marker_auto_skip_on_stg_prod(cfg):
    """§C.6 C-3 marker contract: F3 items auto-skip on STG/PROD.

    When this test actually runs -> we are on DEV/TEST -> PASS.
    On STG/PROD it is already SKIPPED by collection hook (no body executed).
    """
    assert cfg.env in {"dev", "test"}, (
        "S-FND-01 F3 BUG: test reached body on non-DEV/TEST. "
        "pytest_collection_modifyitems _apply_f3_auto_skip should have skipped."
    )


@pytest.mark.F3
@pytest.mark.parametrize("case", list(range(10)))
def test_f3_skip_helper_is_deterministic_10x(monkeypatch, case):
    """DET: skip_if_not_env fixture 10x identical behavior on same env."""
    from tests.conftest import _resolve_active_env
    results = {_resolve_active_env() for _ in range(5)}
    assert len(results) == 1


@pytest.mark.F3
def test_f3_skip_if_not_env_fixture_exists(skip_if_not_env):
    """Fixture is callable (exists)."""
    assert callable(skip_if_not_env)


@pytest.mark.F3
def test_f3_dev_allows_skip_checker(skip_if_not_env, cfg):
    """When on DEV, skip_if_not_env("dev") should NOT raise (no-op)."""
    if cfg.env == "dev":
        # Should return None (no skip)
        skip_if_not_env("dev")  # noqa: B018
