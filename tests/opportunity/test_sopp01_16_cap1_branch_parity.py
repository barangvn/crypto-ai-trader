import ast
import pathlib
import re


APP_OPPORTUNITY_ROOT = pathlib.Path("app/opportunity")


class _BranchCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.findings = []  # list of (file, line, code_snippet, token)

    def visit_If(self, node: ast.If) -> None:
        self._check(node.test, node)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self._check(node.test, node)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._check(node.test, node)
        self.generic_visit(node)

    def _check(self, test_node: ast.AST, container: ast.AST) -> None:
        for token in ("run_mode", "source_type"):
            hits = [
                n
                for n in ast.walk(test_node)
                if isinstance(n, ast.Name) and n.id == token
            ]
            if hits:
                self.findings.append(
                    (
                        "app/opportunity",
                        getattr(container, "lineno", -1),
                        "ast_if_test_" + token,
                        token,
                    )
                )


class TestCAP1BranchParity:
    def _collect_files(self):
        return sorted(str(p) for p in APP_OPPORTUNITY_ROOT.rglob("*.py"))

    def test_ast_zero_run_mode_branch(self):
        collector = _BranchCollector()
        for path in self._collect_files():
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, filename=path)
            collector.visit(tree)
        run_mode_findings = [f for f in collector.findings if f[3] == "run_mode"]
        assert run_mode_findings == []

    def test_ast_zero_source_type_branch(self):
        collector = _BranchCollector()
        for path in self._collect_files():
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src, filename=path)
            collector.visit(tree)
        src_type_findings = [f for f in collector.findings if f[3] == "source_type"]
        assert src_type_findings == []

    def test_grep_text_no_direct_match(self):
        pattern = re.compile(r"\b(run_mode|source_type)\b")
        matches = []
        for path in self._collect_files():
            for i, line in enumerate(open(path, "r", encoding="utf-8"), 1):
                if pattern.search(line):
                    matches.append((path, i, line.strip()))
        assert matches == []

    def test_public_api_still_importable(self):
        from app.opportunity import DeterministicOpportunityScorer  # noqa: F401
