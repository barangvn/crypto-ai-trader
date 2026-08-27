import ast
import pathlib
import re


APP_OPPORTUNITY = pathlib.Path("app/opportunity")
FORBIDDEN_CLASSES = [
    "RiskDecision",
    "PaperOrder",
    "PaperFill",
    "Position",
    "Portfolio",
    "BrokerAdapter",
    "ExchangeAdapter",
    "Executor",
]


class _ImportCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.append(alias.name)
            if alias.asname:
                self.names.append(alias.asname)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        self.names.append(mod)
        for alias in node.names:
            self.names.append(alias.name)
            if alias.asname:
                self.names.append(alias.asname)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self.names.append(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.names.append(node.attr)
        self.generic_visit(node)


class TestNoExecutionAuthority:
    def _files(self):
        return sorted(str(p) for p in APP_OPPORTUNITY.rglob("*.py"))

    def test_no_downstream_exec_types_in_ast(self):
        col = _ImportCollector()
        for f in self._files():
            tree = ast.parse(open(f, "r", encoding="utf-8").read(), filename=f)
            col.visit(tree)
        hits = []
        for forbidden in FORBIDDEN_CLASSES:
            if forbidden in col.names:
                hits.append(forbidden)
        assert hits == []

    def test_no_downstream_exec_types_in_text(self):
        pattern = re.compile(r"\b(" + "|".join(FORBIDDEN_CLASSES) + r")\b")
        matches = []
        for f in self._files():
            for i, line in enumerate(open(f, "r", encoding="utf-8"), 1):
                clean = re.sub(r"(['\"]).*?\1", "", line, flags=re.S)
                if pattern.search(clean):
                    matches.append((f, i, line.strip()))
        assert matches == []

    def test_scorer_returns_only_opportunity_score(self):
        from tests.opportunity.conftest import make_default_scorer, make_strategy_signal, make_feature_vector, make_market_regime
        scorer = make_default_scorer()
        from app.contracts.opportunity import OpportunityScore
        opp = scorer.evaluate_with_symbol(make_strategy_signal(), make_feature_vector(), make_market_regime(), "BTC_USDT")
        assert isinstance(opp, OpportunityScore)
