from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.strategies import MomentumStrategy, TrendFollowingStrategy

from tests.strategies.conftest import make_strategy_context


APP_STRATEGIES_DIR = Path(__file__).resolve().parents[2] / "app" / "strategies"


TREND_FIXTURES = ["bull", "hv", "sideways", "insufficient"]
MOM_FIXTURES = ["bull", "hv", "sideways", "insufficient"]
ALL_RUNS = 10


class TestTrendDeterminism:
    @pytest.mark.parametrize("variant", TREND_FIXTURES)
    def test_trend_10_runs_sha256_unique_set_size_1(self, trend_strategy: TrendFollowingStrategy, variant: str):
        ctx = make_strategy_context(variant)
        hashes = set()
        for _ in range(ALL_RUNS):
            sig = trend_strategy.evaluate(ctx)
            hashes.add(sig.schema_sha256())
        assert len(hashes) == 1


class TestMomentumDeterminism:
    @pytest.mark.parametrize("variant", MOM_FIXTURES)
    def test_momentum_10_runs_sha256_unique_set_size_1(self, momentum_strategy: MomentumStrategy, variant: str):
        ctx = make_strategy_context(variant)
        hashes = set()
        for _ in range(ALL_RUNS):
            sig = momentum_strategy.evaluate(ctx)
            hashes.add(sig.schema_sha256())
        assert len(hashes) == 1


class TestSortedDictEquality:
    def test_trend_strong_bull_10_runs_sorted_dict_equality(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        dicts = []
        for _ in range(ALL_RUNS):
            sig = trend_strategy.evaluate(ctx)
            dicts.append(sig.to_sorted_dict())
        first = dicts[0]
        for d in dicts[1:]:
            assert d == first

    def test_momentum_strong_bull_10_runs_sorted_dict_equality(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        dicts = []
        for _ in range(ALL_RUNS):
            sig = momentum_strategy.evaluate(ctx)
            dicts.append(sig.to_sorted_dict())
        first = dicts[0]
        for d in dicts[1:]:
            assert d == first


class TestLVDeterminism:
    def test_trend_lv_10_runs_sha256_set_1(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("lv")
        hashes = set()
        for _ in range(ALL_RUNS):
            sig = trend_strategy.evaluate(ctx)
            hashes.add(sig.schema_sha256())
        assert len(hashes) == 1

    def test_momentum_lv_10_runs_sha256_set_1(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("lv")
        hashes = set()
        for _ in range(ALL_RUNS):
            sig = momentum_strategy.evaluate(ctx)
            hashes.add(sig.schema_sha256())
        assert len(hashes) == 1


class TestTUDeterminism:
    def test_trend_tu_10_runs_sha256_set_1(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("tu")
        hashes = set()
        for _ in range(ALL_RUNS):
            sig = trend_strategy.evaluate(ctx)
            hashes.add(sig.schema_sha256())
        assert len(hashes) == 1

    def test_momentum_tu_10_runs_sha256_set_1(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("tu")
        hashes = set()
        for _ in range(ALL_RUNS):
            sig = momentum_strategy.evaluate(ctx)
            hashes.add(sig.schema_sha256())
        assert len(hashes) == 1


def _check_ast_cap1_runmode_sourcetype_in_ifs(tree: ast.AST, filename: str) -> int:
    findings = 0
    TARGET_NAMES = {"run_mode", "source_type"}
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test_node = node.test
            checks: list[ast.AST] = []
            if isinstance(test_node, ast.Compare):
                checks = [test_node.left]
                for comp in test_node.comparators:
                    checks.append(comp)
            elif isinstance(test_node, ast.BoolOp):
                for v in test_node.values:
                    checks.append(v)
            elif isinstance(test_node, ast.UnaryOp):
                checks = [test_node.operand]
            elif isinstance(test_node, ast.Call):
                pass
            else:
                checks = [test_node]
            for c in checks:
                if isinstance(c, ast.Name) and c.id in TARGET_NAMES:
                    findings += 1
                elif isinstance(c, ast.Attribute) and c.attr in TARGET_NAMES:
                    findings += 1
                elif isinstance(c, ast.Compare):
                    sub_left = c.left
                    if isinstance(sub_left, ast.Name) and sub_left.id in TARGET_NAMES:
                        findings += 1
                    elif isinstance(sub_left, ast.Attribute) and sub_left.attr in TARGET_NAMES:
                        findings += 1
                    for comp in c.comparators:
                        if isinstance(comp, ast.Name) and comp.id in TARGET_NAMES:
                            findings += 1
                        elif isinstance(comp, ast.Attribute) and comp.attr in TARGET_NAMES:
                            findings += 1
    return findings


class TestCAP1AstScan:
    def test_cap1_ast_scan_base_py_zero_runmode_sourcetype_ifs(self):
        path = APP_STRATEGIES_DIR / "base.py"
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        findings = _check_ast_cap1_runmode_sourcetype_in_ifs(tree, "base.py")
        assert findings == 0

    def test_cap1_ast_scan_init_py_zero_runmode_sourcetype_ifs(self):
        path = APP_STRATEGIES_DIR / "__init__.py"
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        findings = _check_ast_cap1_runmode_sourcetype_in_ifs(tree, "__init__.py")
        assert findings == 0


class TestCAP1StringGrep:
    def test_cap1_string_grep_base_py_zero_runmode_if(self):
        path = APP_STRATEGIES_DIR / "base.py"
        src = path.read_text(encoding="utf-8")
        count = 0
        for line in src.splitlines():
            stripped = line
            if "#" in stripped:
                stripped = stripped[: stripped.index("#")]
            if "if run_mode" in stripped:
                count += 1
            if "if source_type" in stripped:
                count += 1
        assert count == 0

    def test_cap1_string_grep_init_py_zero_runmode_if(self):
        path = APP_STRATEGIES_DIR / "__init__.py"
        src = path.read_text(encoding="utf-8")
        count = 0
        for line in src.splitlines():
            stripped = line
            if "#" in stripped:
                stripped = stripped[: stripped.index("#")]
            if "if run_mode" in stripped:
                count += 1
            if "if source_type" in stripped:
                count += 1
        assert count == 0


class TestStrategyPuritySideEffects:
    def test_trend_evaluate_as_of_unchanged(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        original_as_of = ctx.as_of
        _ = trend_strategy.evaluate(ctx)
        assert ctx.as_of == original_as_of

    def test_momentum_evaluate_as_of_unchanged(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        original_as_of = ctx.as_of
        _ = momentum_strategy.evaluate(ctx)
        assert ctx.as_of == original_as_of

    def test_trend_evaluate_side_effect_free_clock_ref_unchanged(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        orig_clock_sha = ctx.clock_ref.wall
        orig_replay = ctx.clock_ref.replay
        _ = trend_strategy.evaluate(ctx)
        assert ctx.clock_ref.wall == orig_clock_sha
        assert ctx.clock_ref.replay == orig_replay

    def test_momentum_evaluate_side_effect_free_clock_ref_unchanged(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("bull")
        orig_clock_sha = ctx.clock_ref.wall
        orig_replay = ctx.clock_ref.replay
        _ = momentum_strategy.evaluate(ctx)
        assert ctx.clock_ref.wall == orig_clock_sha
        assert ctx.clock_ref.replay == orig_replay

    def test_trend_evaluate_correlation_not_mutated(self, trend_strategy: TrendFollowingStrategy):
        from tests.strategies.conftest import FIXED_CORR_ID, FIXED_CAUS_ID

        ctx = make_strategy_context("bull")
        orig_corr = ctx.correlation_id
        orig_caus = ctx.causation_id
        _ = trend_strategy.evaluate(ctx)
        assert ctx.correlation_id == orig_corr
        assert ctx.causation_id == orig_caus
        assert ctx.correlation_id == FIXED_CORR_ID
        assert ctx.causation_id == FIXED_CAUS_ID

    def test_momentum_evaluate_correlation_not_mutated(self, momentum_strategy: MomentumStrategy):
        from tests.strategies.conftest import FIXED_CORR_ID, FIXED_CAUS_ID

        ctx = make_strategy_context("bull")
        orig_corr = ctx.correlation_id
        orig_caus = ctx.causation_id
        _ = momentum_strategy.evaluate(ctx)
        assert ctx.correlation_id == orig_corr
        assert ctx.causation_id == orig_caus
        assert ctx.correlation_id == FIXED_CORR_ID
        assert ctx.causation_id == FIXED_CAUS_ID
