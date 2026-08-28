"""T08 — Correlation / Causation (3 corr × 3 caus + chain length checks = 10 tests)."""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.contracts.risk import RiskDecisionResult


def test_t08_correlation_id_preserved(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
    assert rd.correlation_id == opp.correlation_id


def test_t08_causation_id_is_opp_score_id(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
    assert rd.causation_id == opp.score_id


def test_t08_different_corr_different_rd(happy_path_tuple, engine):
    opp1, sig, reg, pv, lim, ctx = happy_path_tuple
    opp2 = replace(opp1, correlation_id="CORR_02_" + "a"*16, score_id="OPP_02_" + "a"*16)
    rd1 = engine.evaluate(opp1, sig, reg, pv, lim, ctx)
    rd2 = engine.evaluate(opp2, sig, reg, pv, lim, ctx)
    assert rd1.correlation_id != rd2.correlation_id
    assert rd1.causation_id != rd2.causation_id


def test_t08_chain_sig_to_opp_to_risk(happy_path_tuple, engine):
    """Zincir: StrategySignal.causation_id != RiskDecision.causation_id; parent = OpportunityScore.score_id."""
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx)
    # sig.causation_id might be same or different; RD's causation MUST equal opp.score_id
    assert rd.causation_id == opp.score_id
    # correlation stays same throughout: sig.correlation_id == opp.correlation_id == rd.correlation_id
    assert opp.correlation_id == sig.correlation_id  # conftest sets this
    assert rd.correlation_id == opp.correlation_id


def test_t08_corr_caus_with_rejected(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    from app.contracts.canonical import QualityFlags
    rd = engine.evaluate(replace(opp, quality_flags=QualityFlags(invalid=True)), sig, reg, pv, lim, ctx)
    assert rd.correlation_id == opp.correlation_id
    assert rd.causation_id == opp.score_id


@pytest.mark.parametrize("corr_id", ["CRR_A_" + "x"*16, "CRR_B_" + "y"*16, "CRR_C_" + "z"*16])
def test_t08_3corr_matrix(corr_id, happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    sig2 = replace(sig, correlation_id=corr_id)
    opp2 = replace(opp, correlation_id=corr_id, causation_id=sig.causation_id)
    rd = engine.evaluate(opp2, sig2, reg, pv, lim, ctx)
    assert rd.correlation_id == corr_id


@pytest.mark.parametrize("opp_id", ["OPP_X_" + "x"*16, "OPP_Y_" + "y"*16, "OPP_Z_" + "z"*16])
def test_t08_3causation_matrix(opp_id, happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    opp2 = replace(opp, score_id=opp_id)
    rd = engine.evaluate(opp2, sig, reg, pv, lim, ctx)
    assert rd.causation_id == opp_id
