import ast
import pathlib
import re


APP_ROOT = pathlib.Path("app/opportunity")
NETWORK_TOKENS = [
    "socket",
    "urllib",
    "http.client",
    "requests",
    "httpx",
    "aiohttp",
    "asyncio.open_connection",
    "ftp",
    "smtp",
    "poplib",
    "imaplib",
    "telnetlib",
    "websocket",
    "websockets",
]


class _ImportCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        self.imports.append(mod)
        for alias in node.names:
            self.imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        self.generic_visit(node)


class TestNetworkSafety:
    def _files(self):
        return sorted(str(p) for p in APP_ROOT.rglob("*.py"))

    def test_ast_no_network_import(self):
        col = _ImportCollector()
        for f in self._files():
            tree = ast.parse(open(f, "r", encoding="utf-8").read(), filename=f)
            col.visit(tree)
        hits = []
        for imp in col.imports:
            for tok in NETWORK_TOKENS:
                if tok in imp.lower():
                    hits.append((imp, tok))
        assert hits == []

    def test_grep_no_network_token(self):
        # Exclude comments/strings? We do plain line grep for the whole file.
        pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in NETWORK_TOKENS if not t.startswith("asyncio")) + r")\b")
        matches = []
        for f in self._files():
            for i, line in enumerate(open(f, "r", encoding="utf-8"), 1):
                # strip string literals (naive)
                clean = re.sub(r"(['\"]).*?\1", "", line, flags=re.S)
                if pattern.search(clean):
                    matches.append((f, i, line.strip()))
        assert matches == []

    def test_scorer_no_network_access(self):
        from app.opportunity import DeterministicOpportunityScorer  # noqa: F401
        # merely import; the AST & grep should confirm no network
