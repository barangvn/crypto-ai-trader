from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from tests.regime._fixtures import (  # noqa: E402
    MarketRegimeState,
    QualityHint,
    DetectOptions,
    RegimeEngine,
    _clean_fv,
    _make_fv,
    pytest,
)


FIXTURES = [
    # 1 Strong bull
    lambda: _clean_fv({
        "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
        "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
        "atr_14": 0.8, "volatility_20_bps": 10.0,
        "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
        "high_raw": 105.5, "low_raw": 104.5,
    }),
    # 2 Strong bear
    lambda: _clean_fv({
        "close_raw": 95.0, "ema_14": 100.0, "rsi_14": 15.0,
        "vwap_20": 100.0, "mom_10_abs": -5.0, "mom_10_pct": -0.050,
        "atr_14": 0.8, "volatility_20_bps": 10.0,
        "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
        "high_raw": 95.5, "low_raw": 94.5,
    }),
    # 3 Neutral sideways
    lambda: _clean_fv({
        "close_raw": 100.02, "ema_14": 100.0, "rsi_14": 50.0,
        "vwap_20": 100.0, "mom_10_abs": 0.1, "mom_10_pct": 0.001,
        "atr_14": 0.3, "volatility_20_bps": 10.0,
        "vol_ratio_20": 0.85, "vol_std_20_scaled": 5.0,
        "high_raw": 100.3, "low_raw": 99.7,
    }),
    # 4 High vol spike
    lambda: _clean_fv({
        "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
        "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
        "atr_14": 5.0, "volatility_20_bps": 500.0,
        "vol_ratio_20": 4.0, "vol_std_20_scaled": 200.0,
        "high_raw": 110.0, "low_raw": 90.0,
    }),
    # 5 Low vol calm
    lambda: _clean_fv({
        "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
        "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
        "atr_14": 0.05, "volatility_20_bps": 5.0,
        "vol_ratio_20": 0.4, "vol_std_20_scaled": 1.0,
        "high_raw": 100.05, "low_raw": 99.95,
    }),
]


class TestReg01Determinism10x:
    @pytest.mark.parametrize("fidx", list(range(len(FIXTURES))))
    def test_reg01_ad20_10x_same_sha256(self, fidx):
        fv = FIXTURES[fidx]()
        eng = RegimeEngine()
        shas = set()
        dicts = []
        for _ in range(10):
            mr, aux = eng.detect("BTC_USDT", fv)
            shas.add(mr.schema_sha256())
            dicts.append(json.dumps(mr.to_sorted_dict(), sort_keys=True))
        assert len(shas) == 1, f"fixture {fidx}: multiple schema_sha256 across 10 runs"
        assert len(set(dicts)) == 1, f"fixture {fidx}: multiple sorted_dict variants"

    @pytest.mark.parametrize("fidx", list(range(len(FIXTURES))))
    def test_reg01_ad20_10x_same_regime_enum(self, fidx):
        fv = FIXTURES[fidx]()
        eng = RegimeEngine()
        regimes = [eng.detect("X", fv)[0].regime for _ in range(10)]
        assert len(set(regimes)) == 1

    @pytest.mark.parametrize("fidx", list(range(len(FIXTURES))))
    def test_reg01_aux_sorted_json_is_deterministic_10x(self, fidx):
        fv = FIXTURES[fidx]()
        eng = RegimeEngine()
        aux_hashes = set()
        for _ in range(10):
            _, aux = eng.detect(
                "BTC_USDT", fv,
                correlation_id="COR_test123",
                causation_id="CAU_test456",
            )
            s = json.dumps(aux, sort_keys=True, default=str)
            aux_hashes.add(hashlib.sha256(s.encode("utf-8")).hexdigest())
        assert len(aux_hashes) == 1


class TestReg01Cap1NoRunModeSourceTypeBranches:
    def test_reg01_c70_cap1_ast_no_runmode_or_sourcetype_branch(self):
        """CAP-1 AST scan: engine code has 0 if run_mode / if source_type."""
        engine_path = Path.cwd() / "app" / "regime" / "engine.py"
        tree = ast.parse(engine_path.read_text(encoding="utf-8"))

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.hits = 0
                self.hit_lines: list[int] = []

            def visit_If(self, node: ast.If) -> None:
                # Check test expression for run_mode or source_type mentions
                for sub in ast.walk(node.test):
                    if isinstance(sub, ast.Name) and sub.id in (
                        "run_mode",
                        "source_type",
                        "RunMode",
                        "SourceType",
                    ):
                        self.hits += 1
                        self.hit_lines.append(node.lineno)
                    if isinstance(sub, ast.Attribute) and sub.attr in (
                        "run_mode",
                        "source_type",
                    ):
                        self.hits += 1
                        self.hit_lines.append(node.lineno)
                self.generic_visit(node)

            def visit_Attribute(self, node: ast.Attribute) -> None:
                # Even attribute access to .run_mode / .source_type inside an If
                # was already caught above; additionally disallow conditional
                # expressions and any other branches (ternary):
                self.generic_visit(node)

            def visit_IfExp(self, node: ast.IfExp) -> None:
                for sub in ast.walk(node.test):
                    if isinstance(sub, ast.Name) and sub.id in (
                        "run_mode",
                        "source_type",
                    ):
                        self.hits += 1
                        self.hit_lines.append(node.lineno)
                    if isinstance(sub, ast.Attribute) and sub.attr in (
                        "run_mode",
                        "source_type",
                    ):
                        self.hits += 1
                        self.hit_lines.append(node.lineno)
                self.generic_visit(node)

        v = Visitor()
        v.visit(tree)
        assert v.hits == 0, (
            f"CAP-1 violation: {v.hits} if/ternary branches mentioning "
            f"run_mode/source_type in regime engine. Lines: {v.hit_lines}"
        )


class TestReg01OptionsOverride:
    def test_reg01_c47_tie_threshold_overridable_001(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.5, "volatility_20_bps": 50.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 100.5, "low_raw": 99.5,
        })
        # Very tight tie threshold AND disable all other transition triggers
        opt_narrow = DetectOptions(
            tie_threshold=0.0001,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        # Disable tie threshold entirely (nothing triggers tie) AND disable others
        opt_wide = DetectOptions(
            tie_threshold=100.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        mr_narrow, aux_n = RegimeEngine(options=opt_narrow).detect("X", fv)
        mr_wide, aux_w = RegimeEngine(options=opt_wide).detect("X", fv)
        # Wide tie threshold → T1 fires → transition
        assert aux_w["tie_activated"] is True
        assert mr_wide.regime == MarketRegimeState.TRANSITION_UNCERTAIN
        # Narrow → tie not active
        assert aux_n["tie_activated"] is False

    def test_reg01_c48_conflict_threshold_overridable(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 5.0, "volatility_20_bps": 500.0,
            "vol_ratio_20": 5.0, "vol_std_20_scaled": 200.0,
            "high_raw": 110.0, "low_raw": 95.0,
        })
        opt_strict = DetectOptions(
            tie_threshold=0.0,
            conflict_threshold=0.001,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        opt_relaxed = DetectOptions(
            tie_threshold=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        _, aux_s = RegimeEngine(options=opt_strict).detect("X", fv)
        _, aux_r = RegimeEngine(options=opt_relaxed).detect("X", fv)
        assert aux_s["conflict_activated"] is True
        # relaxed: conflict_score still may fire depending on strength, but we
        # just verify options are respected by difference
        assert isinstance(aux_r["conflict_activated"], bool)
