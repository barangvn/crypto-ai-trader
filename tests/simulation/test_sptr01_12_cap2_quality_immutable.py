from __future__ import annotations

import ast
import os

import pytest

from app.contracts import QualityFlags
from app.simulation import PaperExecutionSimulator


HERE = os.path.dirname(os.path.abspath(__file__))
EXECUTION_PY = os.path.abspath(os.path.join(HERE, "..", "..", "app", "simulation", "execution.py"))


# G13: 8 tests — CAP-2 QualityFlags Immutable + Validator No Call
class TestCAP2QualityImmutable:
    def _read_execution_source(self) -> str:
        with open(EXECUTION_PY, "r", encoding="utf-8") as f:
            return f.read()

    def test_no_quality_setattr_assign(self):
        src = self._read_execution_source()
        tree = ast.parse(src)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Attribute):
                        if isinstance(tgt.value, ast.Name) and tgt.value.id in ("qf", "quality_ctx", "quality_flags"):
                            bad.append(ast.unparse(tgt))
                    elif isinstance(tgt, ast.Subscript):
                        pass
            if isinstance(node, ast.AugAssign):
                tgt = node.target
                if isinstance(tgt, ast.Attribute):
                    if isinstance(tgt.value, ast.Name) and tgt.value.id in ("qf", "quality_ctx", "quality_flags"):
                        bad.append("aug:" + ast.unparse(tgt))
        assert len(bad) == 0, f"QualityFlags mutation: {bad}"

    def test_no_reasons_append(self):
        tree = ast.parse(self._read_execution_source())
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "append":
                    obj = func.value
                    if isinstance(obj, ast.Name) and obj.id in ("qf", "quality_ctx", "quality_flags"):
                        bad.append(ast.unparse(node))
        assert len(bad) == 0, f"QualityFlags.reasons append: {bad}"

    def test_no_validator_module_import(self):
        src = self._read_execution_source()
        tree = ast.parse(src)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    nm = alias.name
                    if "validator" in nm.lower() or "quality_monitor" in nm.lower():
                        bad.append(nm)
            if isinstance(node, ast.ImportFrom):
                if node.module and ("validator" in node.module.lower() or "quality_monitor" in node.module.lower()):
                    bad.append(node.module)
        assert len(bad) == 0, f"Validator import: {bad}"

    def test_no_validator_function_calls(self):
        src = self._read_execution_source()
        tree = ast.parse(src)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    nm = func.id
                    if (nm.startswith("validate_quality") or nm.startswith("validator")
                            or nm.startswith("validate_market") or nm.startswith("validate_fill")):
                        bad.append(nm)
                if isinstance(func, ast.Attribute):
                    nm = func.attr
                    if (nm.startswith("validate_quality") or nm.startswith("validator")):
                        bad.append(nm)
        assert len(bad) == 0, f"Validator calls: {bad}"

    def test_read_only_quality_flags_stale(self, sptr01_order_buy, sptr01_ref_tick, sptr01_bus):
        qf = QualityFlags(stale=True)
        qf_dict_before = {k: v for k, v in qf.__dict__.items() if k != "reasons"}
        sim2 = PaperExecutionSimulator(event_bus=sptr01_bus)
        _ = sim2.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=qf)
        qf_dict_after = {k: v for k, v in qf.__dict__.items() if k != "reasons"}
        assert qf_dict_before == qf_dict_after

    def test_read_only_invalid(self, sptr01_order_buy, sptr01_ref_tick, sptr01_bus):
        qf = QualityFlags(invalid=True)
        before_stale = qf.stale
        before_inv = qf.invalid
        before_q = qf.quarantined
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        _ = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=qf)
        assert qf.stale == before_stale and qf.invalid == before_inv and qf.quarantined == before_q

    def test_degraded_not_blocked(self, sptr01_order_buy, sptr01_ref_tick, sptr01_bus):
        qf = QualityFlags(degraded=True)
        sim = PaperExecutionSimulator(event_bus=sptr01_bus)
        res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=qf)
        assert res.rejected is False
        assert res.fill is not None

    def test_fill_config_import_no_validator(self):
        path = os.path.abspath(os.path.join(HERE, "..", "..", "app", "simulation", "fill_config.py"))
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", None) or ""
                names = [a.name for a in getattr(node, "names", [])]
                combined = [module] + names
                for n in combined:
                    assert "validator" not in n.lower() if isinstance(n, str) else True
                    assert "quality_monitor" not in n.lower() if isinstance(n, str) else True
