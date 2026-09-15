from __future__ import annotations

import pytest

from app.rollback import (
    RollbackEngine,
    ThresholdsConfig,
    evaluate_rollback_eligibility,
    RollbackEligibilityDecision,
    RollbackAuditPayload,
)


def test_public_api_module_imported_all_symbols():
    import app.rollback as r
    assert r.RollbackEngine is RollbackEngine
    assert r.ThresholdsConfig is ThresholdsConfig
    assert r.RollbackEligibilityDecision is RollbackEligibilityDecision
    assert r.RollbackAuditPayload is RollbackAuditPayload


def test_public_wrapper_evaluate_returns_same_as_engine(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=777)
    d1, a1 = engine.evaluate(**common_evaluate_kwargs)
    d2, a2 = evaluate_rollback_eligibility(engine=engine, **common_evaluate_kwargs)
    assert d1 == d2
    assert a1.to_sorted_dict() == a2.to_sorted_dict()


def test_happy_path_smoke_multiple_engines(dummy_storage_happy, common_evaluate_kwargs):
    d_list = []
    for seed in [1, 2, 3, 4, 5]:
        engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=seed)
        d, _ = engine.evaluate(**common_evaluate_kwargs)
        d_list.append(d.eligible)
    assert all(d_list)


def test_no_regression_on_happy_idempotency_20(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=9)
    first = None
    for _ in range(20):
        d, _ = engine.evaluate(**common_evaluate_kwargs)
        row = (d.decision_id, d.decision_sha256, tuple(d.reasons))
        if first is None:
            first = row
        else:
            assert row == first


def test_no_existing_test_behavior_change_upstream_modules():
    # sanity only: can import upstream contracts
    from app.contracts.model import ModelLifecycleStatus  # noqa: F401
    from app.registry.registry import ModelRegistry  # noqa: F401
    from app.gate.engine import PromotionGate  # noqa: F401
