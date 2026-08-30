from __future__ import annotations

import ast
import os

import pytest


HERE = os.path.dirname(os.path.abspath(__file__))
EXECUTION_PY = os.path.abspath(os.path.join(HERE, "..", "..", "app", "simulation", "execution.py"))
FILL_CONFIG_PY = os.path.abspath(os.path.join(HERE, "..", "..", "app", "simulation", "fill_config.py"))


# G14: 6 tests — CAP-1 No Live/Replay Branch
class TestCAP1NoRunmodeBranch:
    def _scan(self, path: str) -> list[str]:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = node.test
                text = ast.unparse(test)
                if any(k in text.lower() for k in ["run_mode", "source_type", "if live", "runmode", "backtest_mode", "is_live", "is_replay", "mode == live", "mode == backtest"]):
                    findings.append(f"L{node.lineno}: if {text}")
                elif isinstance(test, ast.Compare):
                    for comp in test.comparators + [test.left]:
                        if isinstance(comp, ast.Name) and comp.id in ("run_mode", "source_type", "mode"):
                            findings.append(f"L{node.lineno}: compare {ast.unparse(test)}")
        return findings

    def test_execution_py_no_runmode_branch(self):
        bad = self._scan(EXECUTION_PY)
        assert len(bad) == 0, f"CAP-1 violations in execution.py: {bad}"

    def test_fill_config_py_no_runmode_branch(self):
        bad = self._scan(FILL_CONFIG_PY)
        assert len(bad) == 0, f"CAP-1 violations fill_config.py: {bad}"

    def test_init_py_no_runmode_branch(self):
        initp = os.path.abspath(os.path.join(HERE, "..", "..", "app", "simulation", "__init__.py"))
        bad = self._scan(initp)
        assert len(bad) == 0

    def test_simulator_works_paper_mode(self, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
        from app.simulation import PaperExecutionSimulator
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.fill is not None or res.rejected is True

    def test_simulator_no_time_now(self):
        with open(EXECUTION_PY, "r", encoding="utf-8") as f:
            src = f.read()
        assert "datetime.now(" not in src
        assert "time.time()" not in src
        assert "time.sleep(" not in src
        assert "sleep(" not in src

    def test_clock_ref_propagated(self, sptr01_order_buy, sptr01_tick_no_bidask, sptr01_quality_healthy, sptr01_bus, sptr01_clock_ref, sptr01_ts):
        from app.contracts import Symbol
        from app.simulation import PaperExecutionSimulator, build_pipeline_reference_data
        ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask, clock_ref=sptr01_clock_ref, symbol=Symbol("BTC_USDT"))
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        _ = sim.simulate(order=sptr01_order_buy, reference=ref, quality_ctx=sptr01_quality_healthy, clock_ref=sptr01_clock_ref)
        assert len(sptr01_bus.published) >= 1
        env = sptr01_bus.published[-1]
        assert getattr(env, "clock_ref", None) is not None
