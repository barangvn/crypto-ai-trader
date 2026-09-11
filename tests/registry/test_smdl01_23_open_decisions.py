from __future__ import annotations

import pytest


def test_smdl01_23_od_decision_od01_str_non_empty(fresh_registry):
    reg = fresh_registry[0]
    result = reg.od_decision("OD-01")
    assert isinstance(result, str)
    assert len(result) > 0


def test_smdl01_23_od_decisions_all_len_10(fresh_registry):
    reg = fresh_registry[0]
    all_decisions = reg.od_decisions_all()
    assert isinstance(all_decisions, dict)
    assert len(all_decisions) == 10


def test_smdl01_23_od_decisions_all_keys_od01_through_od10(fresh_registry):
    reg = fresh_registry[0]
    all_decisions = reg.od_decisions_all()
    expected_keys = {f"OD-{i:02d}" for i in range(1, 11)}
    assert set(all_decisions.keys()) == expected_keys


def test_smdl01_23_each_od_decision_has_non_empty_value(fresh_registry):
    reg = fresh_registry[0]
    all_decisions = reg.od_decisions_all()
    for key, value in all_decisions.items():
        assert isinstance(value, str), f"{key} value is not str"
        assert len(value) > 0, f"{key} value is empty"
