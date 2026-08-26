from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.contracts.strategy import SignalDirection
from app.strategies import MomentumStrategy, StrategyQualityHint, TrendFollowingStrategy

from tests.strategies.conftest import make_strategy_context


APP_STRATEGIES_DIR = Path(__file__).resolve().parents[2] / "app" / "strategies"


class TestQualityHintFrozen:
    def test_strategyqualityhint_frozen_true_assign_raises(self):
        q = StrategyQualityHint()
        with pytest.raises(FrozenInstanceError):
            q.stale = True

    def test_strategyqualityhint_frozen_duplicate_raises(self):
        q = StrategyQualityHint()
        with pytest.raises(FrozenInstanceError):
            q.duplicate = True

    def test_strategyqualityhint_frozen_invalid_raises(self):
        q = StrategyQualityHint()
        with pytest.raises(FrozenInstanceError):
            q.invalid = True


class TestNoQualityValidatorImportInStrategies:
    def test_ast_walk_base_py_no_qualityvalidator_import(self):
        path = APP_STRATEGIES_DIR / "base.py"
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        found = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if "QualityValidator" in module:
                        found += 1
                    for alias in node.names:
                        if "QualityValidator" in alias.name or "QualityValidator" in (alias.asname or ""):
                            found += 1
                else:
                    for alias in node.names:
                        if "QualityValidator" in alias.name:
                            found += 1
        assert found == 0

    def test_ast_walk_init_py_no_qualityvalidator_import(self):
        path = APP_STRATEGIES_DIR / "__init__.py"
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        found = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if "QualityValidator" in alias.name or "QualityValidator" in (alias.asname or ""):
                            found += 1
                else:
                    for alias in node.names:
                        if "QualityValidator" in alias.name:
                            found += 1
        assert found == 0


class TestQualityHintDefaults:
    def test_eight_flags_default_false_stale(self):
        q = StrategyQualityHint()
        assert q.stale is False

    def test_eight_flags_default_false_invalid(self):
        q = StrategyQualityHint()
        assert q.invalid is False

    def test_eight_flags_default_false_quarantined(self):
        q = StrategyQualityHint()
        assert q.quarantined is False

    def test_eight_flags_default_false_degraded(self):
        q = StrategyQualityHint()
        assert q.degraded is False

    def test_eight_flags_default_false_duplicate(self):
        q = StrategyQualityHint()
        assert q.duplicate is False

    def test_eight_flags_default_false_out_of_order(self):
        q = StrategyQualityHint()
        assert q.out_of_order is False

    def test_eight_flags_default_false_missing(self):
        q = StrategyQualityHint()
        assert q.missing is False

    def test_eight_flags_default_false_abnormal_spread(self):
        q = StrategyQualityHint()
        assert q.abnormal_spread is False


class TestTrendQualityPenalties:
    def test_trend_stale_confidence_0_60x_vs_clean(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        clean = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        stale = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(stale=True))
        ratio = stale.confidence / max(clean.confidence, 1e-9)
        assert 0.30 <= ratio <= 0.65
        assert stale.confidence < clean.confidence

    def test_trend_degraded_confidence_0_60x(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        clean = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        degraded = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(degraded=True))
        ratio = degraded.confidence / max(clean.confidence, 1e-9)
        assert 0.30 <= ratio <= 0.65
        assert degraded.confidence < clean.confidence

    def test_trend_invalid_force_flat(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(invalid=True))
        assert sig.direction == SignalDirection.FLAT

    def test_trend_quarantined_force_flat(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(quarantined=True))
        assert sig.direction == SignalDirection.FLAT

    def test_trend_duplicate_0_85x(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        clean = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        dup = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(duplicate=True))
        ratio = dup.confidence / max(clean.confidence, 1e-9)
        assert 0.60 <= ratio <= 0.90
        assert dup.confidence < clean.confidence

    def test_trend_missing_0_85x(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        clean = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(missing=True))
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.60 <= ratio <= 0.90
        assert sig.confidence < clean.confidence

    def test_trend_out_of_order_0_85x(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        clean = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(out_of_order=True))
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.60 <= ratio <= 0.90
        assert sig.confidence < clean.confidence

    def test_trend_abnormal_spread_0_80x(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        clean = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(abnormal_spread=True))
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.50 <= ratio <= 0.85
        assert sig.confidence < clean.confidence

    def test_trend_stale_plus_duplicate_multi_worst_wins_0_60x(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        clean = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        multi = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(stale=True, duplicate=True))
        ratio = multi.confidence / max(clean.confidence, 1e-9)
        assert 0.30 <= ratio <= 0.65
        assert multi.confidence <= clean.confidence * 0.85


class TestMomentumQualityPenalties:
    def test_momentum_stale_0_60x(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        clean = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        stale = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(stale=True))
        ratio = stale.confidence / max(clean.confidence, 1e-9)
        assert 0.35 <= ratio <= 0.65
        assert stale.confidence < clean.confidence

    def test_momentum_degraded_0_60x(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        clean = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(degraded=True))
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.35 <= ratio <= 0.65
        assert sig.confidence < clean.confidence

    def test_momentum_invalid_force_flat(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(invalid=True))
        assert sig.direction == SignalDirection.FLAT

    def test_momentum_quarantined_force_flat(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        sig = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(quarantined=True))
        assert sig.direction == SignalDirection.FLAT

    def test_momentum_duplicate_0_85x(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        clean = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(duplicate=True))
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.65 <= ratio <= 0.90
        assert sig.confidence < clean.confidence

    def test_momentum_missing_0_85x(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        clean = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(missing=True))
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.65 <= ratio <= 0.90
        assert sig.confidence < clean.confidence

    def test_momentum_out_of_order_0_85x(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        clean = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(out_of_order=True))
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.65 <= ratio <= 0.90
        assert sig.confidence < clean.confidence

    def test_momentum_abnormal_spread_0_80x(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        clean = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(abnormal_spread=True))
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.55 <= ratio <= 0.85
        assert sig.confidence < clean.confidence

    def test_momentum_invalid_plus_stale_flat_priority_invalid(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        clean = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        sig = momentum_strategy.evaluate(ctx, quality_hint=StrategyQualityHint(invalid=True, stale=True))
        assert sig.direction == SignalDirection.FLAT
        assert sig.confidence < clean.confidence

    def test_all_eight_flags_true_force_flat_worst_0_15(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        clean = trend_strategy.evaluate(ctx, quality_hint=StrategyQualityHint())
        all_true = StrategyQualityHint(
            stale=True,
            invalid=True,
            quarantined=True,
            degraded=True,
            duplicate=True,
            out_of_order=True,
            missing=True,
            abnormal_spread=True,
        )
        sig = trend_strategy.evaluate(ctx, quality_hint=all_true)
        assert sig.direction == SignalDirection.FLAT
        ratio = sig.confidence / max(clean.confidence, 1e-9)
        assert 0.01 <= ratio <= 0.20


class TestQualityInvalidVsVersionCheck:
    def test_trend_invalid_force_flat_version_mismatch_mode_flat_hold(self, trend_strategy: TrendFollowingStrategy):
        from app.strategies.base import TrendStrategyOptions

        ctx = make_strategy_context("bull")
        opts = TrendStrategyOptions(
            feature_version="WRONG_VERSION_XYZ",
            unexpected_version_mode="flat_hold",
        )
        sig = trend_strategy.evaluate(
            ctx,
            quality_hint=StrategyQualityHint(invalid=True),
            options=opts,
        )
        assert sig.direction == SignalDirection.FLAT


class TestValidatorWordAstScan:
    def test_strategies_sources_validator_word_count_zero_except_comments(self):
        total = 0
        for fname in ("base.py", "__init__.py"):
            path = APP_STRATEGIES_DIR / fname
            src = path.read_text(encoding="utf-8")
            lines = src.splitlines()
            for raw_line in lines:
                stripped = raw_line.strip()
                code_part = stripped.split("#", 1)[0] if "#" in stripped else stripped
                if "validator" in code_part.lower() and not code_part.lstrip().startswith("#"):
                    total += 1
        assert total == 0
