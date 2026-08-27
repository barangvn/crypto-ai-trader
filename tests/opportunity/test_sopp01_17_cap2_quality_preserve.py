import ast
import pathlib
import re


APP_OPPORTUNITY_ROOT = pathlib.Path("app/opportunity")


class _ValidatorCallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports = []
        self.calls = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if "validator" in alias.name.lower():
                self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if "validator" in mod.lower():
            self.imports.append(mod)
        for alias in node.names:
            if "validator" in alias.name.lower():
                self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if "validator" in name.lower() or name.startswith("validate_"):
                self.calls.append((name, getattr(node, "lineno", -1)))
        elif isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if "validator" in attr.lower() or attr.startswith("validate_"):
                self.calls.append((attr, getattr(node, "lineno", -1)))
        self.generic_visit(node)


class TestCAP2QualityPreserve:
    def _collect_files(self):
        return sorted(str(p) for p in APP_OPPORTUNITY_ROOT.rglob("*.py"))

    def test_quality_validator_import_zero(self):
        c = _ValidatorCallCollector()
        for path in self._collect_files():
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, filename=path)
            c.visit(tree)
        assert c.imports == []

    def test_quality_validator_call_zero(self):
        c = _ValidatorCallCollector()
        for path in self._collect_files():
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, filename=path)
            c.visit(tree)
        # allow validate_symbol_canonical? not imported explicitly here; check for any validate_quality name
        quality_calls = [x for x in c.calls if "quality" in x[0].lower() or "validator" in x[0].lower()]
        assert quality_calls == []

    def test_grep_quality_flag_constructor_preserves(self):
        from tests.opportunity.conftest import make_quality
        q = make_quality(stale=True)
        before_id = id(q)
        before = (q.stale, q.missing, q.duplicate, q.out_of_order, q.invalid, q.quarantined, q.degraded)
        # scoring functions use accessor only (simulate)
        from app.opportunity.base import _quality_score_multiplier, _quality_reject_reasons

        _ = _quality_score_multiplier(q)
        _ = _quality_reject_reasons(q)
        assert id(q) == before_id
        assert (q.stale, q.missing, q.duplicate, q.out_of_order, q.invalid, q.quarantined, q.degraded) == before
