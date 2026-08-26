from __future__ import annotations

import re

import pytest

from app.strategies import MomentumStrategy, TrendFollowingStrategy

from tests.strategies.conftest import (
    FIXED_CAUS_ID,
    FIXED_CAUS_ID_V2,
    FIXED_CORR_ID,
    FIXED_CORR_ID_V2,
    make_strategy_context,
)


ULIDISH_RE = re.compile(r"^[A-Za-z0-9_\-]{8,}$")
TEN_RUNS = 10


class TestTrendCorrelationPreserved:
    @pytest.mark.parametrize("variant", ["bull", "hv", "sideways", "lv"])
    def test_trend_correlation_same_as_ctx_four_variants(
        self, trend_strategy: TrendFollowingStrategy, variant: str
    ):
        ctx = make_strategy_context(variant, correlation_id=FIXED_CORR_ID)
        sig = trend_strategy.evaluate(ctx)
        assert sig.correlation_id == FIXED_CORR_ID


class TestTrendCausationPreserved:
    @pytest.mark.parametrize("variant", ["bull", "hv", "sideways", "lv"])
    def test_trend_causation_same_as_ctx_four_variants(
        self, trend_strategy: TrendFollowingStrategy, variant: str
    ):
        ctx = make_strategy_context(variant, causation_id=FIXED_CAUS_ID)
        sig = trend_strategy.evaluate(ctx)
        assert sig.causation_id == FIXED_CAUS_ID


class TestMomentumCorrelationPreserved:
    @pytest.mark.parametrize("variant", ["bull", "hv", "sideways", "lv"])
    def test_momentum_correlation_same_as_ctx_four_variants(
        self, momentum_strategy: MomentumStrategy, variant: str
    ):
        ctx = make_strategy_context(variant, correlation_id=FIXED_CORR_ID)
        sig = momentum_strategy.evaluate(ctx)
        assert sig.correlation_id == FIXED_CORR_ID


class TestMomentumCausationPreserved:
    @pytest.mark.parametrize("variant", ["bull", "hv", "sideways", "lv"])
    def test_momentum_causation_same_as_ctx_four_variants(
        self, momentum_strategy: MomentumStrategy, variant: str
    ):
        ctx = make_strategy_context(variant, causation_id=FIXED_CAUS_ID)
        sig = momentum_strategy.evaluate(ctx)
        assert sig.causation_id == FIXED_CAUS_ID


class TestRunsConsistentSameCtx:
    def test_trend_10x_runs_same_ctx_corr_consistent(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull", correlation_id=FIXED_CORR_ID, causation_id=FIXED_CAUS_ID)
        corrs = set()
        causs = set()
        for _ in range(TEN_RUNS):
            sig = trend_strategy.evaluate(ctx)
            corrs.add(sig.correlation_id)
            causs.add(sig.causation_id)
        assert len(corrs) == 1
        assert len(causs) == 1
        assert next(iter(corrs)) == FIXED_CORR_ID
        assert next(iter(causs)) == FIXED_CAUS_ID

    def test_momentum_10x_runs_same_ctx_corr_consistent(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull", correlation_id=FIXED_CORR_ID, causation_id=FIXED_CAUS_ID)
        corrs = set()
        causs = set()
        for _ in range(TEN_RUNS):
            sig = momentum_strategy.evaluate(ctx)
            corrs.add(sig.correlation_id)
            causs.add(sig.causation_id)
        assert len(corrs) == 1
        assert len(causs) == 1
        assert next(iter(corrs)) == FIXED_CORR_ID
        assert next(iter(causs)) == FIXED_CAUS_ID


class TestCtxChangeReflectedInSignal:
    def test_change_correlation_id_signal_correlation_changes_not_stale(
        self, trend_strategy: TrendFollowingStrategy, momentum_strategy: MomentumStrategy
    ):
        ctx1 = make_strategy_context("bull", correlation_id=FIXED_CORR_ID)
        sig1_trend = trend_strategy.evaluate(ctx1)
        sig1_mom = momentum_strategy.evaluate(ctx1)
        assert sig1_trend.correlation_id == FIXED_CORR_ID
        assert sig1_mom.correlation_id == FIXED_CORR_ID

        ctx2 = make_strategy_context("bull", correlation_id=FIXED_CORR_ID_V2)
        sig2_trend = trend_strategy.evaluate(ctx2)
        sig2_mom = momentum_strategy.evaluate(ctx2)
        assert sig2_trend.correlation_id == FIXED_CORR_ID_V2
        assert sig2_mom.correlation_id == FIXED_CORR_ID_V2
        assert sig1_trend.correlation_id != sig2_trend.correlation_id
        assert sig1_mom.correlation_id != sig2_mom.correlation_id


class TestULIDISHFormat:
    @pytest.mark.parametrize("variant", ["bull", "lv"])
    def test_trend_correlation_ulidish_format_length_8_and_regex(
        self, trend_strategy: TrendFollowingStrategy, variant: str
    ):
        ctx = make_strategy_context(variant)
        sig = trend_strategy.evaluate(ctx)
        assert isinstance(sig.correlation_id, str)
        assert len(sig.correlation_id) >= 8
        assert ULIDISH_RE.match(sig.correlation_id) is not None

    @pytest.mark.parametrize("variant", ["bull", "lv"])
    def test_trend_causation_ulidish_format_length_8_and_regex(
        self, trend_strategy: TrendFollowingStrategy, variant: str
    ):
        ctx = make_strategy_context(variant)
        sig = trend_strategy.evaluate(ctx)
        assert isinstance(sig.causation_id, str)
        assert len(sig.causation_id) >= 8
        assert ULIDISH_RE.match(sig.causation_id) is not None

    @pytest.mark.parametrize("variant", ["bull", "lv"])
    def test_momentum_correlation_ulidish_format_length_8_and_regex(
        self, momentum_strategy: MomentumStrategy, variant: str
    ):
        ctx = make_strategy_context(variant)
        sig = momentum_strategy.evaluate(ctx)
        assert isinstance(sig.correlation_id, str)
        assert len(sig.correlation_id) >= 8
        assert ULIDISH_RE.match(sig.correlation_id) is not None

    @pytest.mark.parametrize("variant", ["bull", "lv"])
    def test_momentum_causation_ulidish_format_length_8_and_regex(
        self, momentum_strategy: MomentumStrategy, variant: str
    ):
        ctx = make_strategy_context(variant)
        sig = momentum_strategy.evaluate(ctx)
        assert isinstance(sig.causation_id, str)
        assert len(sig.causation_id) >= 8
        assert ULIDISH_RE.match(sig.causation_id) is not None
