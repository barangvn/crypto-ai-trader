from __future__ import annotations

import pytest

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
    build_explainability_bundle,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection


REGIMES_FOR_QUALITY = list(MarketRegimeState)
QUALITY_FLAGS_SINGLE = [
    ("stale", True),
    ("missing", True),
    ("duplicate", True),
    ("out_of_order", True),
    ("invalid", True),
    ("quarantined", True),
    ("degraded", True),
]


@pytest.mark.parametrize("flag,_val", QUALITY_FLAGS_SINGLE, ids=[f[0] for f in QUALITY_FLAGS_SINGLE])
def test_single_quality_flag_immutable_and_scoring(flag, _val):
    q = make_quality_clean()
    q_snapshot_id = id(q)
    q_before = {f: getattr(q, f, None) for f in ("stale", "missing", "duplicate", "out_of_order", "invalid", "quarantined", "degraded")}
    q_flagged = make_quality(**{flag: True})
    scorer = make_default_scorer()
    sig = make_strategy_signal()
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL)
    opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, q_flagged, FIXED_AS_OF)
    assert id(q) == q_snapshot_id, "clean quality id changed"
    for f in q_before:
        assert getattr(q, f, None) == q_before[f], f"clean quality mutated at {f}"
    assert 0.0 <= opp.score_total <= 1.0, f"score out of range with flag {flag}: {opp.score_total}"
    if flag in ("invalid", "quarantined"):
        assert opp.actionable is False, f"flag {flag} must make actionable False"
        assert opp.score_total <= 0.20 + 1e-9, f"flag {flag} expected ceiling behavior, got {opp.score_total}"
        assert len(opp.reject_reasons) >= 1


PAIRWISE_FLAGS = [
    ("stale", "missing"),
    ("stale", "degraded"),
    ("missing", "out_of_order"),
    ("duplicate", "out_of_order"),
    ("stale", "duplicate"),
]


@pytest.mark.parametrize("a,b", PAIRWISE_FLAGS, ids=[f"{a}+{b}" for a, b in PAIRWISE_FLAGS])
def test_pairwise_quality_flags_combined_score_bounded(a, b):
    q = make_quality(**{a: True, b: True})
    scorer = make_default_scorer()
    sig = make_strategy_signal(signal_strength=0.8)
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL, confidence=0.9, strength=0.9)
    opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, q, FIXED_AS_OF)
    assert 0.0 <= opp.score_total <= 1.0
    opp_clean = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, None, FIXED_AS_OF)
    assert opp.score_total <= opp_clean.score_total + 1e-9, "flagged quality should not outperform clean"


EXPLAIN_MATRIX = [
    (MarketRegimeState.BULL, SignalDirection.LONG, None),
    (MarketRegimeState.BEAR, SignalDirection.LONG, None),
    (MarketRegimeState.HIGH_VOLATILITY, SignalDirection.FLAT, make_quality(stale=True)),
    (MarketRegimeState.LOW_VOLATILITY, SignalDirection.LONG, make_quality(missing=True)),
    (MarketRegimeState.SIDEWAYS, SignalDirection.HOLD, make_quality(duplicate=True)),
    (MarketRegimeState.TRANSITION_UNCERTAIN, SignalDirection.LONG, make_quality(invalid=True)),
]


@pytest.mark.parametrize("state,dir,q", EXPLAIN_MATRIX, ids=[f"{s.value}_{d.value}_{'clean' if q is None else 'flagged'}" for s, d, q in EXPLAIN_MATRIX])
def test_explainability_bundle_returns_tuple_and_components_consistent(state, dir, q):
    sig = make_strategy_signal(direction=dir)
    fv = make_feature_vector("bull")
    regime = make_market_regime(state)
    scorer = make_default_scorer()
    opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, q, FIXED_AS_OF)
    costs_dict = {
        "fee_bps": opp.score_components.get("costs.fee_bps", 0.0),
        "slippage_bps": opp.score_components.get("costs.slippage_bps", 0.0),
        "spread_bps": opp.score_components.get("costs.spread_bps", 0.0),
        "latency_bps": opp.score_components.get("costs.latency_bps", 0.0),
        "gross_edge_bps": opp.score_components.get("costs.gross_edge_bps", 0.0),
        "net_edge_bps": opp.score_components.get("costs.net_edge_bps", 0.0),
        "total_cost_bps": opp.score_components.get("costs.total_cost_bps", 0.0),
    }
    result = build_explainability_bundle(
        sig, fv, regime,
        opp.score_components,
        costs_dict,
        opp.score_components.get("raw_score", 0.0),
        opp.score_components.get("regime.adjustment", 0.5),
        opp.score_components.get("strategy.adjustment", 0.5),
        opp.score_components.get("cost_multiplier", 1.0),
        opp.score_components.get("quality_multiplier", 1.0),
    )
    assert isinstance(result, tuple) and len(result) == 2, f"explain bundle should be (dict,str), got {type(result)}"
    bundle, note_str = result
    assert isinstance(bundle, dict)
    assert isinstance(note_str, str)
    assert "REG|" in note_str, f"note missing REG|, got {note_str}"
    assert "STR|" in note_str, f"note missing STR|, got {note_str}"
    assert "DOM|" in note_str, f"note missing DOM|, got {note_str}"
    gross = costs_dict["gross_edge_bps"]
    costs_sum = costs_dict["fee_bps"] + costs_dict["slippage_bps"] + costs_dict["spread_bps"] + costs_dict["latency_bps"]
    expected_net = gross - costs_sum
    assert abs(opp.expected_edge_bps - expected_net) < 1e-6, (
        f"expected_edge mismatch: opp.net={opp.expected_edge_bps}, gross={gross}, costs_sum={costs_sum}, net_from_comp={expected_net}"
    )
    for k in ("costs.fee_bps", "costs.net_edge_bps", "costs.spread_bps", "confidence", "cost_multiplier", "quality_multiplier", "final_score", "raw_score"):
        assert k in bundle, f"bundle missing expected key {k}"
    keys_sorted = list(bundle.keys())
    assert keys_sorted == sorted(keys_sorted), "bundle keys not alphabetically sorted"
    assert opp.to_sorted_dict() == opp.to_sorted_dict()


def test_explainability_deterministic_ten_runs():
    notes = set()
    shas = set()
    scorer = make_default_scorer()
    sig = make_strategy_signal(signal_strength=0.85)
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL, confidence=0.9)
    q = make_quality(missing=True, duplicate=True)
    for _ in range(10):
        opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, q, FIXED_AS_OF)
        notes.add(opp.explainability_note or "")
        shas.add(opp.schema_sha256())
    assert len(notes) == 1, f"explain notes set={len(notes)}"
    assert len(shas) == 1, f"sha set={len(shas)}"
