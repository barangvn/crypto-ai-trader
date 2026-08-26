from __future__ import annotations

import math

import pytest

from app.contracts.exceptions import ContractSchemaError
from app.contracts.feature import FEATURE_SCHEMA_REGISTRY
from app.contracts.regime import REGIME_KEYS
from app.contracts.strategy import SignalDirection, StrategySignal
from app.strategies import MomentumStrategy, StrategyQualityHint, TrendFollowingStrategy

from tests.strategies.conftest import (
    FIXED_CAUS_ID,
    FIXED_CAUS_ID_V2,
    FIXED_CORR_ID,
    FIXED_CORR_ID_V2,
    make_strategy_context,
)


class TestSignalDirectionEnum:
    def test_direction_has_three_values_total(self):
        vals = list(SignalDirection)
        assert len(vals) == 3

    def test_direction_long_exists(self):
        assert SignalDirection.LONG.value == "long"

    def test_direction_flat_exists(self):
        assert SignalDirection.FLAT.value == "flat"

    def test_direction_hold_exists(self):
        assert SignalDirection.HOLD.value == "hold"

    def test_direction_short_does_not_exist(self):
        assert hasattr(SignalDirection, "short") is False


class TestStrategySignalConstruction:
    def test_construct_signal_with_direction_short_raises(self):
        with pytest.raises(ContractSchemaError):
            StrategySignal(
                strategy_id="trend_following",
                strategy_version="str_01_v1",
                direction="short",
                signal_strength=0.5,
                correlation_id=FIXED_CORR_ID,
                causation_id=FIXED_CAUS_ID,
            )

    def test_signal_strength_neg_01_raises(self):
        with pytest.raises(ContractSchemaError):
            StrategySignal(
                strategy_id="trend_following",
                strategy_version="str_01_v1",
                direction=SignalDirection.LONG,
                signal_strength=-0.1,
                correlation_id=FIXED_CORR_ID,
                causation_id=FIXED_CAUS_ID,
            )

    def test_signal_strength_11_raises(self):
        with pytest.raises(ContractSchemaError):
            StrategySignal(
                strategy_id="momentum",
                strategy_version="str_01_v1",
                direction=SignalDirection.LONG,
                signal_strength=1.1,
                correlation_id=FIXED_CORR_ID,
                causation_id=FIXED_CAUS_ID,
            )

    def test_confidence_neg_001_raises(self):
        with pytest.raises(ContractSchemaError):
            StrategySignal(
                strategy_id="trend_following",
                strategy_version="str_01_v1",
                direction=SignalDirection.LONG,
                signal_strength=0.5,
                confidence=-0.01,
                correlation_id=FIXED_CORR_ID,
                causation_id=FIXED_CAUS_ID,
            )

    def test_confidence_101_raises(self):
        with pytest.raises(ContractSchemaError):
            StrategySignal(
                strategy_id="momentum",
                strategy_version="str_01_v1",
                direction=SignalDirection.LONG,
                signal_strength=0.5,
                confidence=1.01,
                correlation_id=FIXED_CORR_ID,
                causation_id=FIXED_CAUS_ID,
            )


class TestStrategyEvaluateSupportingKeys:
    def test_trend_supporting_feature_keys_in_registry(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        allowed = FEATURE_SCHEMA_REGISTRY["fea_01_v1"].allowed_keys
        for k in sig.supporting_feature_keys:
            assert isinstance(k, str)
            assert k in allowed

    def test_momentum_supporting_feature_keys_in_registry(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx)
        allowed = FEATURE_SCHEMA_REGISTRY["fea_01_v1"].allowed_keys
        for k in sig.supporting_feature_keys:
            assert isinstance(k, str)
            assert k in allowed

    def test_trend_supporting_regime_keys_subset_values_in_range(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        keys = set(sig.supporting_regime_evidence.keys())
        assert keys.issubset(set(REGIME_KEYS))
        for v in sig.supporting_regime_evidence.values():
            assert isinstance(v, float)
            assert 0.0 <= v <= 1.0

    def test_momentum_supporting_regime_keys_subset_values_in_range(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx)
        keys = set(sig.supporting_regime_evidence.keys())
        assert keys.issubset(set(REGIME_KEYS))
        for v in sig.supporting_regime_evidence.values():
            assert isinstance(v, float)
            assert 0.0 <= v <= 1.0


class TestSerialization:
    def test_trend_schema_sha256_returns_64_char_hex(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        h = sig.schema_sha256()
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_momentum_schema_sha256_returns_64_char_hex(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx)
        h = sig.schema_sha256()
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_trend_to_sorted_dict_keys_sorted(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        d = sig.to_sorted_dict()
        assert isinstance(d, dict)
        assert sorted(d.keys()) == list(d.keys())

    def test_momentum_to_sorted_dict_keys_sorted(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx)
        d = sig.to_sorted_dict()
        assert isinstance(d, dict)
        assert sorted(d.keys()) == list(d.keys())


class TestClamping:
    @pytest.mark.parametrize("variant", ["bull", "lv", "hv", "sideways", "tu", "insufficient"])
    def test_trend_signal_strength_always_clamped_0_1(self, trend_strategy: TrendFollowingStrategy, variant: str):
        ctx = make_strategy_context(variant)
        sig = trend_strategy.evaluate(ctx)
        assert 0.0 <= sig.signal_strength <= 1.0

    @pytest.mark.parametrize("variant", ["bull", "lv", "hv", "sideways", "tu", "insufficient"])
    def test_momentum_signal_strength_always_clamped_0_1(self, momentum_strategy: MomentumStrategy, variant: str):
        ctx = make_strategy_context(variant)
        sig = momentum_strategy.evaluate(ctx)
        assert 0.0 <= sig.signal_strength <= 1.0

    @pytest.mark.parametrize("variant", ["bull", "lv", "hv", "sideways", "tu", "insufficient"])
    def test_trend_confidence_always_clamped_0_1(self, trend_strategy: TrendFollowingStrategy, variant: str):
        ctx = make_strategy_context(variant)
        sig = trend_strategy.evaluate(ctx)
        assert sig.confidence is not None
        assert 0.0 <= sig.confidence <= 1.0

    @pytest.mark.parametrize("variant", ["bull", "lv", "hv", "sideways", "tu", "insufficient"])
    def test_momentum_confidence_always_clamped_0_1(self, momentum_strategy: MomentumStrategy, variant: str):
        ctx = make_strategy_context(variant)
        sig = momentum_strategy.evaluate(ctx)
        assert sig.confidence is not None
        assert 0.0 <= sig.confidence <= 1.0


class TestDirectionType:
    def test_trend_direction_always_enum_instance_not_raw_str(self, trend_strategy: TrendFollowingStrategy):
        for v in ["bull", "hv", "sideways", "tu", "insufficient", "lv"]:
            ctx = make_strategy_context(v)
            sig = trend_strategy.evaluate(ctx)
            assert isinstance(sig.direction, SignalDirection)

    def test_momentum_direction_always_enum_instance_not_raw_str(self, momentum_strategy: MomentumStrategy):
        for v in ["bull", "hv", "sideways", "tu", "insufficient", "lv"]:
            ctx = make_strategy_context(v)
            sig = momentum_strategy.evaluate(ctx)
            assert isinstance(sig.direction, SignalDirection)


class TestStrategyIdentity:
    def test_trend_strategy_id_trend_following(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        assert sig.strategy_id == "trend_following"

    def test_momentum_strategy_id_momentum(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx)
        assert sig.strategy_id == "momentum"

    def test_trend_strategy_version_str_01_v1(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        assert sig.strategy_version == "str_01_v1"

    def test_momentum_strategy_version_str_01_v1(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx)
        assert sig.strategy_version == "str_01_v1"


class TestCorrelationCausationOutputPreserved:
    def test_trend_correlation_preserved_v1(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull", correlation_id=FIXED_CORR_ID)
        sig = trend_strategy.evaluate(ctx)
        assert sig.correlation_id == FIXED_CORR_ID

    def test_trend_correlation_preserved_v2(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull", correlation_id=FIXED_CORR_ID_V2)
        sig = trend_strategy.evaluate(ctx)
        assert sig.correlation_id == FIXED_CORR_ID_V2

    def test_momentum_correlation_preserved_v1(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull", correlation_id=FIXED_CORR_ID)
        sig = momentum_strategy.evaluate(ctx)
        assert sig.correlation_id == FIXED_CORR_ID

    def test_momentum_correlation_preserved_v2(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull", correlation_id=FIXED_CORR_ID_V2)
        sig = momentum_strategy.evaluate(ctx)
        assert sig.correlation_id == FIXED_CORR_ID_V2

    def test_trend_causation_preserved_v1(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull", causation_id=FIXED_CAUS_ID)
        sig = trend_strategy.evaluate(ctx)
        assert sig.causation_id == FIXED_CAUS_ID

    def test_trend_causation_preserved_v2(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull", causation_id=FIXED_CAUS_ID_V2)
        sig = trend_strategy.evaluate(ctx)
        assert sig.causation_id == FIXED_CAUS_ID_V2

    def test_momentum_causation_preserved_v1(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull", causation_id=FIXED_CAUS_ID)
        sig = momentum_strategy.evaluate(ctx)
        assert sig.causation_id == FIXED_CAUS_ID

    def test_momentum_causation_preserved_v2(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull", causation_id=FIXED_CAUS_ID_V2)
        sig = momentum_strategy.evaluate(ctx)
        assert sig.causation_id == FIXED_CAUS_ID_V2


class TestPolicyFieldsNone:
    def test_trend_stop_policy_none(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        assert sig.stop_policy is None

    def test_momentum_stop_policy_none(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx)
        assert sig.stop_policy is None

    def test_trend_take_profit_policy_none(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        assert sig.take_profit_policy is None

    def test_momentum_take_profit_policy_none(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx)
        assert sig.take_profit_policy is None

    def test_trend_expected_edge_bps_none(self, trend_strategy: TrendFollowingStrategy):
        for v in ["bull", "hv", "sideways"]:
            ctx = make_strategy_context(v)
            sig = trend_strategy.evaluate(ctx)
            assert sig.expected_edge_bps is None

    def test_momentum_expected_edge_bps_none(self, momentum_strategy: MomentumStrategy):
        for v in ["bull", "hv", "sideways"]:
            ctx = make_strategy_context(v)
            sig = momentum_strategy.evaluate(ctx)
            assert sig.expected_edge_bps is None
