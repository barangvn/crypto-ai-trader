from __future__ import annotations

import pytest

from app.rollback import (
    RollbackEngine,
    ThresholdsConfig,
    RollbackEligibilityDecision,
)


TUPLE_ITEMS = (
    "decision_id",
    "eligible",
    "target_model_id",
    "target_version",
    "reasons",
    "thresholds_version",
    "decision_sha256",
    "approval_count",
)


def _tuple_items(d: RollbackEligibilityDecision) -> tuple:
    return tuple(getattr(d, k) for k in TUPLE_ITEMS)


def _many_runs(engine, kw, n=10):
    outs = []
    for _ in range(n):
        d, _ = engine.evaluate(**kw)
        outs.append(_tuple_items(d))
    return outs


@pytest.mark.parametrize("seed", [0, 1, 3, 7, 42, 100, 555, 2024, 1337, 999, 500001])
def test_same_input_10_runs_same_tuple_each_item(seed, dummy_storage_happy, common_evaluate_kwargs):
    cfg = ThresholdsConfig.defaults_adn_v1()
    engine = RollbackEngine(
        storage=dummy_storage_happy,
        thresholds_cfg=cfg,
        expected_thresholds_version="1.0.0",
        explicit_seed=seed,
    )
    runs = _many_runs(engine, common_evaluate_kwargs, n=10)
    for i, name in enumerate(TUPLE_ITEMS):
        column = [r[i] for r in runs]
        if name == "reasons":
            column = [tuple(x) for x in column]
        assert len(set(column)) == 1, f"determinism fail: {name} not same across 10 runs (seed={seed})"


@pytest.mark.parametrize("seed", [1, 42, 1337])
def test_cross_2_engine_instances_same_output(seed, dummy_storage_happy, common_evaluate_kwargs):
    cfg_a = ThresholdsConfig.defaults_adn_v1()
    cfg_b = ThresholdsConfig.defaults_adn_v1()
    eng_a = RollbackEngine(storage=dummy_storage_happy, thresholds_cfg=cfg_a, explicit_seed=seed)
    eng_b = RollbackEngine(storage=dummy_storage_happy, thresholds_cfg=cfg_b, explicit_seed=seed)
    d_a, _ = eng_a.evaluate(**common_evaluate_kwargs)
    d_b, _ = eng_b.evaluate(**common_evaluate_kwargs)
    assert _tuple_items(d_a) == _tuple_items(d_b)


def test_fail_path_determinism_10(dummy_storage_missing_pointer, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_missing_pointer, explicit_seed=777)
    runs = _many_runs(engine, common_evaluate_kwargs, n=10)
    for i, name in enumerate(TUPLE_ITEMS):
        col = [tuple(r[i]) if isinstance(r[i], list) else r[i] for r in runs]
        assert len(set(col)) == 1, name
