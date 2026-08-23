from __future__ import annotations

import pytest
from decimal import Decimal
from app.contracts.exceptions import ContractSchemaError
from app.contracts import (
    OpportunityScore,
    schema_sha256,
    to_sorted_dict,
    QualityFlags,
)


# ---------------------------------------------------------------------------
# Base valid fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_os_args() -> dict:
    return dict(
        score_id="SCORE_OS_0001_26AUG",
        score_total=0.82,
        confidence=0.78,
        actionable=True,
        reject_reasons=[],
        score_components={
            "trend_component": 0.65,
            "momentum_component": 0.74,
            "regime_component": 0.88,
        },
        expected_edge_bps=14.5,
        expected_cost_bps=4.2,
        symbol_ref="BTC_USDT",
        regime_ref="trending_up_low_vol",
        strategy_ref="dual_momentum_v1",
        policy_version="opportunity-policy/v2.1.0",
        correlation_id="COR_001_S2C_FULLCHAIN",
        causation_id="SS_SIG_0001_PARENT",
        created_ts="2026-08-22T14:00:00.000Z",
        model_version_ref=None,
        quality_flags=None,
        expected_hold_bars=24,
        explainability_note="Trend + momentum strong; cost=4.2bps within envelope",
    )


# ---------------------------------------------------------------------------
# C-05: score_total [0, 1] range
# ---------------------------------------------------------------------------


def test_C05_score_total_below_0_raises(base_os_args):
    base_os_args["score_total"] = -0.01
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


def test_C05_score_total_above_1_raises(base_os_args):
    base_os_args["score_total"] = 1.01
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


def test_C05_score_total_0_and_1_valid(base_os_args):
    for v in (0.0, 1.0):
        base_os_args["score_total"] = float(v)
        os = OpportunityScore(**base_os_args)
        assert os.score_total == float(v)


# ---------------------------------------------------------------------------
# C-06: confidence [0, 1] REQUIRED (None raises)
# ---------------------------------------------------------------------------


def test_C06_confidence_above_1_raises(base_os_args):
    base_os_args["confidence"] = 1.5
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


def test_C06_confidence_none_raises_required(base_os_args):
    base_os_args["confidence"] = None  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


# ---------------------------------------------------------------------------
# C-07: actionable=false + reject_reasons=[]  PASS (None raises)
# ---------------------------------------------------------------------------


def test_C07_actionable_false_empty_reasons_pass(base_os_args):
    base_os_args["actionable"] = False
    base_os_args["reject_reasons"] = []
    os = OpportunityScore(**base_os_args)
    assert os.actionable is False
    assert os.reject_reasons == []


def test_C07_reject_reasons_none_raises(base_os_args):
    base_os_args["actionable"] = False
    base_os_args["reject_reasons"] = None  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


# ---------------------------------------------------------------------------
# C-08: corr_id / causation_id ULID-like
# ---------------------------------------------------------------------------


def test_C08_corr_id_empty_raises(base_os_args):
    base_os_args["correlation_id"] = ""
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


def test_C08_caus_id_short_raises(base_os_args):
    base_os_args["causation_id"] = "abc"
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


# ---------------------------------------------------------------------------
# C-09: created_ts non-UTC format RAISE
# ---------------------------------------------------------------------------


def test_C09_created_ts_no_z_raises(base_os_args):
    base_os_args["created_ts"] = "2026-08-22T14:00:00.000+03:00"
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


def test_C09_created_ts_bad_format_raises(base_os_args):
    base_os_args["created_ts"] = "2026/08/22 14:00"
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


# ---------------------------------------------------------------------------
# C-10: score_components values must be float (string value RAISE)
# ---------------------------------------------------------------------------


def test_C10_score_components_string_value_raises(base_os_args):
    base_os_args["score_components"]["trend_component"] = "0.8"  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


def test_C10_score_components_bool_value_raises(base_os_args):
    base_os_args["score_components"]["trend_component"] = True  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


# ---------------------------------------------------------------------------
# C-11: policy_version empty / None RAISE
# ---------------------------------------------------------------------------


def test_C11_policy_version_empty_raises(base_os_args):
    base_os_args["policy_version"] = ""
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


def test_C11_policy_version_none_raises(base_os_args):
    base_os_args["policy_version"] = None  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


# ---------------------------------------------------------------------------
# C-12: symbol_ref canonical
# ---------------------------------------------------------------------------


def test_C12_symbol_ref_lowercase_raises(base_os_args):
    base_os_args["symbol_ref"] = "btcusdt"  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        OpportunityScore(**base_os_args)


def test_C12_symbol_ref_canonical_pass(base_os_args):
    for sym in ("BTC_USDT", "ETH_BUSD", "SOL_USDC"):
        base_os_args["symbol_ref"] = sym  # type: ignore[assignment]
        os = OpportunityScore(**base_os_args)
        assert os.symbol_ref == sym


# ---------------------------------------------------------------------------
# C-13: 10x determinism schema_sha256 — AYNI digest
# ---------------------------------------------------------------------------


def test_C13_10x_determinism(base_os_args):
    os_inst = OpportunityScore(**base_os_args)
    digests = [os_inst.schema_sha256() for _ in range(10)]
    assert len(set(digests)) == 1
    digests2 = [schema_sha256(os_inst) for _ in range(10)]
    assert len(set(digests2)) == 1
    assert digests[0] == digests2[0]
    # to_sorted_dict 10x eşit (dictler doğrudan karşılaştırılır)
    ds = [to_sorted_dict(os_inst) for _ in range(10)]
    assert all(d == ds[0] for d in ds)


# ---------------------------------------------------------------------------
# Ek validasyon: explainable fields mevcut, cost-aware field'lar doğru typed
# ---------------------------------------------------------------------------


def test_explainable_note_optional_valid(base_os_args):
    # None geçer
    base_os_args["explainability_note"] = None
    # string olarak da geçer
    os1 = OpportunityScore(**base_os_args)
    base_os_args["explainability_note"] = "Yüksek momentum"
    os2 = OpportunityScore(**base_os_args)
    assert os1.explainability_note is None
    assert os2.explainability_note == "Yüksek momentum"


def test_quality_flags_none_or_typed(base_os_args):
    # None geçer
    os1 = OpportunityScore(**base_os_args)
    assert os1.quality_flags is None
    # QualityFlags instance geçer
    base_os_args["quality_flags"] = QualityFlags()
    os2 = OpportunityScore(**base_os_args)
    assert os2.quality_flags is not None
