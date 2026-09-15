from __future__ import annotations

import pytest

from app.rollback.builder import _dedup_sort_reasons, ROLLBACK_COMMAND_NAME_LITERAL
from app.rollback import (
    ERR_ROLLBACK_CURRENT_NOT_CHAMPION,
    ERR_ROLLBACK_MISSING_ROLLBACK_TARGET,
    ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING,
    ERR_ROLLBACK_STALE_DEGRADATION_WINDOW,
)


def test_reasons_empty_when_all_pass():
    out = _dedup_sort_reasons([[], [], []])
    assert out == []


def test_reasons_ascending_sorted():
    r = _dedup_sort_reasons([
        [ERR_ROLLBACK_STALE_DEGRADATION_WINDOW, ERR_ROLLBACK_CURRENT_NOT_CHAMPION],
        [ERR_ROLLBACK_MISSING_ROLLBACK_TARGET],
    ])
    assert r == sorted(r)
    assert len(r) == 3


def test_reasons_dedup_duplicates_removed():
    r = _dedup_sort_reasons([
        [ERR_ROLLBACK_MISSING_ROLLBACK_TARGET, ERR_ROLLBACK_MISSING_ROLLBACK_TARGET],
        [ERR_ROLLBACK_MISSING_ROLLBACK_TARGET],
    ])
    assert len(r) == 1
    assert r[0] == ERR_ROLLBACK_MISSING_ROLLBACK_TARGET


@pytest.mark.parametrize("repeat", [1, 2, 5, 10])
def test_dedup_repeat_call_idempotent(repeat):
    buckets = [
        [ERR_ROLLBACK_CURRENT_NOT_CHAMPION, ERR_ROLLBACK_ROLLBACK_STRATEGY_MISSING],
        [ERR_ROLLBACK_MISSING_ROLLBACK_TARGET, ERR_ROLLBACK_CURRENT_NOT_CHAMPION],
    ]
    first = _dedup_sort_reasons(buckets)
    for _ in range(repeat - 1):
        assert _dedup_sort_reasons(buckets) == first


def test_invalid_stranger_codes_filtered():
    out = _dedup_sort_reasons([
        [ERR_ROLLBACK_MISSING_ROLLBACK_TARGET, "UNSOURCED_FAKE_CODE_XYZ_NOT_IN_CAP13"],
    ])
    assert "UNSOURCED_FAKE_CODE_XYZ_NOT_IN_CAP13" not in out
    assert ERR_ROLLBACK_MISSING_ROLLBACK_TARGET in out


def test_command_name_literal_exact():
    assert ROLLBACK_COMMAND_NAME_LITERAL == "rollback_champion"
