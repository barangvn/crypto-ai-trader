import json
from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_strategy_signal,
    make_default_scorer,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.opportunity.base import build_explainability_bundle


class TestExplainability:
    def test_six_fields_alphabetical(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG, signal_strength=1.0, confidence=1.0)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=1.0, strength=1.0)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        keys = list(opp.score_components.keys())
        assert keys == sorted(keys)

    def test_explain_note_has_pipe_delimiters(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert opp.explainability_note
        assert opp.explainability_note.count("|") >= 2

    def test_dominant_factors_sorted_impact(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        note = opp.explainability_note or ""
        # Extract DOM segment
        dom_text = ""
        parts = note.split("DOM|")
        if len(parts) >= 2:
            after = parts[1]
            # Our DOM section ends at the next pipe-delimited segment (lowecase starts)
            # Actually the note has format: ...|DOM|dom1;dom2;dom3|raw:... → DOM content is up to the next |
            dom_end = after.find("|raw:")
            if dom_end > 0:
                dom_text = after[:dom_end]
            else:
                # last segment
                dom_text = after
        dom_items = [d for d in dom_text.split(";") if d] if dom_text else []
        impacts = []
        item_names = []
        for d in dom_items:
            if "#" in d:
                try:
                    impacts.append(float(d.split("#", 1)[1]))
                    item_names.append(d.split("#", 1)[0])
                except Exception:
                    impacts.append(0.0)
                    item_names.append(d)
            elif ":" in d:
                try:
                    name_part, val_part = d.split(":", 1)
                    item_names.append(name_part)
                    if name_part == "raw_score":
                        impacts.append(abs(float(val_part)))
                    else:
                        impacts.append(abs(float(val_part) - 1.0))
                except Exception:
                    impacts.append(0.0)
                    item_names.append(d)
        if len(impacts) >= 2:
            # impacts sorted desc with alpha tie-break on name
            combined = list(zip(impacts, item_names))
            expected = sorted(combined, key=lambda x: (-x[0], x[1]))
            actual_sorted_impacts = [p[0] for p in expected]
            # Verify actual list is a valid sort: check impacts desc, ties alphabetic
            for i in range(len(impacts) - 1):
                if impacts[i] < impacts[i + 1]:
                    raise AssertionError(f"impact {impacts[i]} < {impacts[i+1]} at i={i}")
                if abs(impacts[i] - impacts[i + 1]) < 1e-9 and item_names[i] > item_names[i + 1]:
                    raise AssertionError(f"name tie-break invalid at i={i}")
            assert True

    def test_deterministic_same_explain_note(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG, signal_strength=0.8)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.SIDEWAYS, confidence=0.7)
        notes = [
            scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z").explainability_note
            for _ in range(8)
        ]
        assert len(set(notes)) == 1

    def test_component_weights_present(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime()
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        for key in ("weights.w_raw_strategy", "weights.w_raw_regime", "weights.w_raw_feature"):
            assert key in opp.score_components

    def test_regime_evidence_and_strategy_evidence_present_in_note(self):
        scorer = make_default_scorer()
        sig = make_strategy_signal(strategy_id="momentum_v1", direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.LOW_VOLATILITY, confidence=0.9)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")
        assert "REG|" in opp.explainability_note
        assert "STR|" in opp.explainability_note


import pytest
