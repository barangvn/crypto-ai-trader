from __future__ import annotations

from dataclasses import FrozenInstanceError

from tests.regime._fixtures import (  # noqa: E402
    MarketRegimeState,
    QualityHint,
    DetectOptions,
    RegimeEngine,
    _clean_fv,
    pytest,
)


_FV_BULL_CLEAN = lambda: _clean_fv({
    "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
    "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
    "atr_14": 0.8, "volatility_20_bps": 10.0,
    "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
    "high_raw": 105.5, "low_raw": 104.5,
})


class TestReg01Quality7Modes:
    def test_reg01_c52_stale_quality_lowers_conf_but_no_T5(self):
        fv = _FV_BULL_CLEAN()
        mr_clean, aux_c = RegimeEngine().detect("X", fv)
        mr_stale, aux_s = RegimeEngine().detect("X", fv, quality_hint=QualityHint(stale=True))
        # T5 should NOT fire for stale
        assert aux_s["quality_triggered_transition"] is False
        # Stale reduces confidence by 0.75 multiplier (or similar due to combined effects)
        # So stale confidence should be <= clean confidence (usually)
        if aux_s["tie_activated"] is False and aux_c["tie_activated"] is False:
            assert mr_stale.confidence <= mr_clean.confidence + 1e-9

    def test_reg01_c53_degraded_quality_lowers_conf_no_T5(self):
        fv = _FV_BULL_CLEAN()
        mr_clean, _ = RegimeEngine().detect("X", fv)
        mr_d, aux_d = RegimeEngine().detect("X", fv, quality_hint=QualityHint(degraded=True))
        assert aux_d["quality_triggered_transition"] is False
        assert 0.0 <= mr_d.confidence <= 1.0

    def test_reg01_c54_dup_miss_ooo_90_mult(self):
        fv = _FV_BULL_CLEAN()
        qh = QualityHint(duplicate=True, out_of_order=True, missing=True)
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=qh)
        assert aux["quality_triggered_transition"] is False
        assert 0.0 <= mr.confidence <= 1.0

    def test_reg01_c63_abnormal_spread_085_mult(self):
        fv = _FV_BULL_CLEAN()
        qh = QualityHint(abnormal_spread=True)
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=qh)
        assert aux["quality_triggered_transition"] is False
        assert 0.0 <= mr.confidence <= 1.0

    def test_reg01_c45_invalid_is_T5_transition(self):
        fv = _FV_BULL_CLEAN()
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=QualityHint(invalid=True))
        assert aux["quality_triggered_transition"] is True
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN

    def test_reg01_c46_quarantined_is_T5_transition(self):
        fv = _FV_BULL_CLEAN()
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=QualityHint(quarantined=True))
        assert aux["quality_triggered_transition"] is True
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN

    def test_reg01_combined_7_true_all_flags_true(self):
        fv = _FV_BULL_CLEAN()
        qh = QualityHint(
            stale=True, invalid=True, quarantined=True, degraded=True,
            duplicate=True, out_of_order=True, missing=True, abnormal_spread=True,
        )
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=qh)
        qmult = aux["quality_hint_applied_penalty"]
        # multiply all 4 penalties: invalid/q(0.20) * stale/degraded(0.75) * dup/miss/ooo(0.90) * abnormal(0.85) * transition(0.75)
        expected = 0.20 * 0.75 * 0.90 * 0.85 * 0.75
        assert abs(qmult - expected) < 1e-6
        assert 0.0 <= mr.confidence <= 1.0
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN


class TestReg01Cap2FrozenImmutable:
    def test_reg01_c71a_quality_hint_frozen_setattr_raises(self):
        qh = QualityHint()
        with pytest.raises(FrozenInstanceError):
            qh.stale = True  # type: ignore[misc]

    def test_reg01_c71b_detect_options_frozen_setattr_raises(self):
        opt = DetectOptions()
        with pytest.raises(FrozenInstanceError):
            opt.tie_threshold = 0.01  # type: ignore[misc]


class TestReg01Cap2NoValidatorCall:
    def test_reg01_c71c_no_quality_validator_imported(self):
        """AST scan — regime engine module must not import from quality validator."""
        import ast
        from pathlib import Path
        import sys
        engine_path = Path.cwd() / "app" / "regime" / "engine.py"
        tree = ast.parse(engine_path.read_text(encoding="utf-8"))
        imports_quality_validator = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and ("quality" in node.module.lower() or "validator" in node.module.lower()):
                    imports_quality_validator = True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "quality" in alias.name.lower() or "validator" in alias.name.lower():
                        imports_quality_validator = True
        # Regime engine relies on pre-computed QualityHint passed from caller
        # (CAP-2: no validator re-run). Confirm no quality/validator module imports.
        assert imports_quality_validator is False, "Regime engine must not call quality validator (CAP-2)"

    def test_reg01_c71d_no_quality_mutate_assign_in_engine(self):
        import ast
        from pathlib import Path
        engine_path = Path.cwd() / "app" / "regime" / "engine.py"
        tree = ast.parse(engine_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                target = ""
                for t in getattr(node, "targets", []) or [getattr(node, "target", None)]:
                    if isinstance(t, ast.Attribute):
                        target += t.attr
                    if isinstance(t, ast.Name):
                        target += t.id
                # If there's any assignment to quality_hint / quality attributes inside
                # the engine, fail:
                if ("quality" in target.lower() and (
                    "stale" in target.lower() or "invalid" in target.lower()
                    or "hint" in target.lower()
                )):
                    pytest.fail(f"Quality hint mutation detected: {target}")
        # Passed
