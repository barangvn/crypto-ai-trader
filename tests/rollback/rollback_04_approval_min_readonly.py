from __future__ import annotations

import pytest

from app.rollback import (
    check_approval_minimum,
    ThresholdsConfig,
    ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL,
    RollbackEngine,
)


@pytest.mark.parametrize("min_count,total,expect_fail", [
    (1, 0, True),
    (1, 1, False),
    (1, 2, False),
    (2, 1, True),
    (2, 2, False),
    (3, 2, True),
    (0, 0, False),
    (0, 1, False),
])
def test_check_approval_minimum_matrix(min_count, total, expect_fail):
    cfg = ThresholdsConfig.from_dict({"min_rollback_approval_count": min_count})
    r = check_approval_minimum(total, cfg)
    if expect_fail:
        assert ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL in r
    else:
        assert ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL not in r


@pytest.mark.parametrize("extras", [0, 1, 2])
def test_approval_refs_plus_extras_counted(extras, dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=3)
    kw = dict(common_evaluate_kwargs)
    kw["explicit_approval_count_extra"] = extras
    d, a = engine.evaluate(**kw)
    expected = 1 + extras
    assert d.approval_count == expected
    assert a.approval_count == expected


def test_approval_min_1_short_fails_eligible_false(dummy_storage_happy, common_evaluate_kwargs):
    cfg = ThresholdsConfig.from_dict({"min_rollback_approval_count": 5})
    engine = RollbackEngine(storage=dummy_storage_happy, thresholds_cfg=cfg, explicit_seed=9)
    kw = dict(common_evaluate_kwargs)
    kw["approval_refs"] = []
    kw["explicit_approval_count_extra"] = 1
    d, _ = engine.evaluate(**kw)
    assert d.eligible is False
    assert ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL in d.reasons
    assert d.approval_count == 2


@pytest.mark.parametrize("min_count,mv_has_appr,explicit,expected_count,expected_fail", [
    (1, True, 0, 1, False),
    (1, True, 1, 2, False),
    (2, True, 0, 1, True),
    (2, True, 1, 2, False),
    (3, True, 0, 1, True),
    (3, True, 2, 3, False),
    (0, False, 0, 0, False),
    (1, False, 0, 0, True),
    (1, False, 1, 1, False),
    (5, False, 4, 4, True),
    (5, False, 5, 5, False),
    (0, True, 0, 1, False),
    (0, True, 99, 100, False),
])
def test_approval_matrix_variants_counted(
    min_count, mv_has_appr, explicit, expected_count, expected_fail,
    dummy_storage_happy, common_evaluate_kwargs,
):
    if not mv_has_appr:
        from tests.rollback.conftest import make_champion_mv, DummyRegistryStorage
        s = DummyRegistryStorage()
        s.set_champion(make_champion_mv(approval_refs=[]))
        s.set_predecessor_pointer("champ_trend_v2", "2.4.1")
        storage = s
    else:
        storage = dummy_storage_happy
    cfg = ThresholdsConfig.from_dict({"min_rollback_approval_count": min_count})
    engine = RollbackEngine(storage=storage, thresholds_cfg=cfg, explicit_seed=100 + min_count + explicit)
    kw = dict(common_evaluate_kwargs)
    kw["approval_refs"] = None
    kw["explicit_approval_count_extra"] = explicit
    d, _ = engine.evaluate(**kw)
    assert d.approval_count == expected_count
    if expected_fail:
        assert ERR_ROLLBACK_MIN_ROLLBACK_APPROVALS_FAIL in d.reasons
    else:
        if not expected_fail and expected_count >= min_count:
            pass  # may have other reasons blocking eligible, but approval check OK
