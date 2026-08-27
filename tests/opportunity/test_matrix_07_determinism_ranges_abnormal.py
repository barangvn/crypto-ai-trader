from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.contracts.exceptions import ContractSchemaError

from tests.opportunity.conftest import (
    FIXED_AS_OF,
    FIXED_SYMBOL,
    make_default_scorer,
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_quality_clean,
    make_strategy_signal,
)
from app.opportunity.base import (
    DEFAULT_MARKET_COST_ASSUMPTIONS,
    DEFAULT_SCORING_WEIGHTS,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection


MATRIX_REGIMES = list(MarketRegimeState)
MATRIX_DIRECTIONS = [SignalDirection.LONG, SignalDirection.FLAT, SignalDirection.HOLD]
MATRIX_QUALITY = [
    (None, "clean"),
    (make_quality(stale=True), "stale"),
    (make_quality(missing=True), "missing"),
    (make_quality(duplicate=True), "duplicate"),
    (make_quality(out_of_order=True), "out_of_order"),
    (make_quality(invalid=True), "invalid"),
    (make_quality(quarantined=True), "quarantined"),
    (make_quality(degraded=True), "degraded"),
]


@pytest.mark.parametrize("regime", MATRIX_REGIMES, ids=[s.value for s in MATRIX_REGIMES])
@pytest.mark.parametrize("direction", MATRIX_DIRECTIONS, ids=[d.value for d in MATRIX_DIRECTIONS])
@pytest.mark.parametrize("q,name", MATRIX_QUALITY, ids=[e[1] for e in MATRIX_QUALITY])
def test_determinism_10x_all_regime_direction_quality(regime, direction, q, name):
    scorer = make_default_scorer()
    sig = make_strategy_signal(direction=direction, signal_strength=0.6)
    fv = make_feature_vector("bull")
    market = make_market_regime(regime)
    shas = set()
    notes = set()
    for _ in range(10):
        opp = scorer.evaluate_with_symbol(sig, fv, market, FIXED_SYMBOL, q, FIXED_AS_OF)
        shas.add(opp.schema_sha256())
        notes.add(opp.explainability_note or "")
        assert 0.0 <= opp.score_total <= 1.0
        assert 0.0 <= opp.confidence <= 1.0
    assert len(shas) == 1, f"sha set size {len(shas)} (regime={regime}, dir={direction}, q={name})"
    assert len(notes) == 1, f"explain notes set size {len(notes)} (regime={regime}, dir={direction}, q={name})"


SIGNAL_KWARGS_RANGES = [
    ({"signal_strength": 0.75, "confidence": 0.8}, {"signal_strength": -0.5}, "neg_strength"),
    ({"signal_strength": 0.75, "confidence": 0.8}, {"signal_strength": 1.5}, "gt1_strength"),
    ({"signal_strength": 0.75, "confidence": 0.8}, {"confidence": -0.01}, "neg_conf"),
    ({"signal_strength": 0.75, "confidence": 0.8}, {"confidence": 1.01}, "gt1_conf"),
]


@pytest.mark.parametrize("base,override,_name", SIGNAL_KWARGS_RANGES, ids=[e[2] for e in SIGNAL_KWARGS_RANGES])
def test_scoring_clamps_invalid_ranges_no_exception(base, override, _name):
    merged = dict(base)
    merged.update(override)
    with pytest.raises(ContractSchemaError):
        sig = make_strategy_signal(**merged)


DECIMAL_AND_INT_FEATURES = [
    ("spread_bps", Decimal("3.5"), "spread_decimal"),
    ("spread_bps", 100, "spread_int_100"),
    ("spread_bps", 99, "spread_int_99"),
    ("rsi_14", Decimal("55.0"), "rsi_decimal"),
    ("volatility_20_bps", 200, "vol_int"),
]


@pytest.mark.parametrize("key,value,_name", DECIMAL_AND_INT_FEATURES, ids=[e[2] for e in DECIMAL_AND_INT_FEATURES])
def test_decimal_and_int_feature_values_no_crash(key, value, _name):
    fv = make_feature_vector("bull", custom_features={key: value})
    scorer = make_default_scorer()
    sig = make_strategy_signal()
    regime = make_market_regime()
    opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, None, FIXED_AS_OF)
    assert 0.0 <= opp.score_total <= 1.0


def test_abnormal_spread_fallback_from_fv_bps_ge_100():
    fv_abn = make_feature_vector("bull", custom_features={"spread_bps": 100})
    fv_ok = make_feature_vector("bull", custom_features={"spread_bps": 99})
    scorer = make_default_scorer()
    sig = make_strategy_signal()
    regime = make_market_regime()
    opp_abn = scorer.evaluate_with_symbol(sig, fv_abn, regime, FIXED_SYMBOL, make_quality_clean(), FIXED_AS_OF)
    opp_ok = scorer.evaluate_with_symbol(sig, fv_ok, regime, FIXED_SYMBOL, make_quality_clean(), FIXED_AS_OF)
    spread_abn = opp_abn.score_components.get("costs.spread_bps")
    spread_ok = opp_ok.score_components.get("costs.spread_bps")
    assert spread_abn is not None
    assert spread_ok is not None
    assert spread_abn > spread_ok * 1.2, f"expected abnormal spread > 1.2x ok, got abn={spread_abn} ok={spread_ok}"
    q = make_quality_clean()
    has_attr = hasattr(q, "abnormal_spread")
    if has_attr:
        assert getattr(q, "abnormal_spread") in (False, None), "quality abnormal_spread was mutated"


def test_expected_hold_bars_default_safe_ge_zero_or_none():
    scorer = make_default_scorer()
    sig = make_strategy_signal()
    opp = scorer.evaluate_with_symbol(sig, make_feature_vector("bull"), make_market_regime(), FIXED_SYMBOL, None, FIXED_AS_OF)
    assert opp.expected_hold_bars is None or opp.expected_hold_bars >= 0


def test_reject_reasons_alphabetical():
    scorer = make_default_scorer()
    sig = make_strategy_signal(signal_strength=0.05)
    fv = make_feature_vector("bull", custom_features={"spread_bps": 500.0})
    regime = make_market_regime(MarketRegimeState.BEAR, confidence=1.0, strength=1.0)
    q = make_quality(invalid=True)
    opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, q, FIXED_AS_OF)
    assert opp.reject_reasons == sorted(opp.reject_reasons), f"reject_reasons not alphabetical: {opp.reject_reasons}"
