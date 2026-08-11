from __future__ import annotations

from app.contracts.canonical import QualityFlags


EXPECTED_FLAG_NAMES = {
    "stale",
    "missing",
    "duplicate",
    "out_of_order",
    "invalid",
    "quarantined",
    "degraded",
}


def test_quality_flags_7_boolean_fields_present():
    flags = QualityFlags()
    for name in EXPECTED_FLAG_NAMES:
        assert hasattr(flags, name), f"Missing flag: {name}"
        assert isinstance(getattr(flags, name), bool), f"Flag not bool: {name}"


def test_degraded_invariant_auto_true_if_any_other_flag():
    flags_stale = QualityFlags(stale=True)
    assert flags_stale.degraded is True

    flags_missing = QualityFlags(missing=True)
    assert flags_missing.degraded is True

    flags_dup = QualityFlags(duplicate=True)
    assert flags_dup.degraded is True

    flags_ooo = QualityFlags(out_of_order=True)
    assert flags_ooo.degraded is True

    flags_invalid = QualityFlags(invalid=True)
    assert flags_invalid.degraded is True

    flags_quar = QualityFlags(quarantined=True)
    assert flags_quar.degraded is True

    flags_multi = QualityFlags(stale=True, missing=True)
    assert flags_multi.degraded is True


def test_default_flags_all_false_and_degraded_false():
    flags = QualityFlags()
    for name in EXPECTED_FLAG_NAMES:
        assert getattr(flags, name) is False, f"Flag not False: {name}"


def test_reasons_appended_correctly():
    flags = QualityFlags()
    assert len(flags.reasons) == 0
    flags.reasons.append({"code": "STALE_DATA", "message": "timestamp too old"})
    assert len(flags.reasons) == 1
    assert flags.reasons[0]["code"] == "STALE_DATA"


def test_all_7_flags_names_exactly_match_contract():
    flags = QualityFlags()
    actual = {name for name in EXPECTED_FLAG_NAMES if hasattr(flags, name)}
    assert actual == EXPECTED_FLAG_NAMES
