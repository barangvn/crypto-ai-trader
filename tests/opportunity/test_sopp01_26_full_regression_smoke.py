import ast
import pathlib
import re
import tomllib


PYPROJECT = pathlib.Path("pyproject.toml")
APP_ROOT = pathlib.Path("app")
TEST_ROOT = pathlib.Path("tests")

FORBIDDEN_RUNTIME_LIBS = [
    "requests", "httpx", "websockets", "asyncpg", "psycopg2", "sqlalchemy",
    "pydantic", "pandas", "numpy", "talib", "ta", "ccxt", "kafka", "redis",
    "aiohttp", "boto3", "django", "flask", "fastapi", "torch", "tensorflow",
    "catboost", "sklearn", "xgboost",
]


class TestRegressionSmoke:
    def test_pyproject_runtime_deps_empty(self):
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        project = data.get("project", {})
        deps = project.get("dependencies", [])
        assert deps == []

    def test_no_forbidden_libs_in_app_opportunity(self):
        col = ast.NodeVisitor()
        all_imports = []

        class Col(ast.NodeVisitor):
            def visit_Import(self, node):
                for a in node.names:
                    all_imports.append(a.name)
                self.generic_visit(node)

            def visit_ImportFrom(self, node):
                mod = node.module or ""
                all_imports.append(mod)
                for a in node.names:
                    all_imports.append(f"{mod}.{a.name}" if mod else a.name)
                self.generic_visit(node)

        visitor = Col()
        for p in pathlib.Path("app/opportunity").rglob("*.py"):
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            visitor.visit(tree)
        for forbidden in FORBIDDEN_RUNTIME_LIBS:
            for imp in all_imports:
                assert not imp.startswith(forbidden), f"forbidden import {imp}"

    def test_contract_version_semver(self):
        from app.contracts import CONTRACT_VERSION
        assert re.match(r"^\d+\.\d+\.\d+(?:[-+][\w.]+)?$", CONTRACT_VERSION)

    def test_import_all_contract_modules(self):
        from app.contracts import canonical  # noqa: F401
        from app.contracts import feature  # noqa: F401
        from app.contracts import regime  # noqa: F401
        from app.contracts import strategy  # noqa: F401
        from app.contracts import opportunity  # noqa: F401
        from app.contracts import types  # noqa: F401

    def test_import_strategy_and_platform(self):
        from app.strategies import base  # noqa: F401
        from app.platform import event_bus  # noqa: F401
