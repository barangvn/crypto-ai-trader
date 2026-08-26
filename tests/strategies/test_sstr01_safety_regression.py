from __future__ import annotations

from pathlib import Path

import pytest


APP_STRATEGIES_DIR = Path(__file__).resolve().parents[2] / "app" / "strategies"
PROJECT_ROOT = Path(__file__).resolve().parents[3] if (Path(__file__).resolve().parents[3] / "pyproject.toml").exists() else Path(__file__).resolve().parents[2]


def _chr_join(chars: list[str]) -> str:
    return "".join(chr(ord(c)) for c in chars)


FORBIDDEN_CREDENTIAL_SUBSTRINGS = [
    _chr_join(["B", "I", "N", "A", "N", "C", "E"]),
    _chr_join(["A", "K", "I", "A"]),
    _chr_join(["s", "k", "-"]),
    _chr_join(["x", "o", "x", "b", "-"]),
    _chr_join(["P", "R", "I", "V", "A", "T", "E", "_", "K", "E", "Y"]),
    _chr_join(["S", "E", "C", "R", "E", "T", "_", "K", "E", "Y"]),
    _chr_join(["L", "E", "V", "E", "R", "A", "G", "E"]),
    _chr_join(["F", "U", "T", "U", "R", "E", "S"]),
]

FORBIDDEN_IMPORT_LIBS = [
    "requests",
    "httpx",
    "websockets",
    "asyncpg",
    "psycopg2",
    "sqlalchemy",
    "pydantic",
    "pandas",
    "numpy",
    "talib",
    "ta",
    "ccxt",
    "kafka",
    "redis",
    "aiohttp",
    "boto3",
    "django",
    "flask",
    "fastapi",
    "torch",
    "tensorflow",
    "catboost",
]


class TestCredentialSubstringsZeroInStrategiesBase:
    @pytest.mark.parametrize("forbidden", FORBIDDEN_CREDENTIAL_SUBSTRINGS)
    def test_base_py_no_forbidden_credential_substrings(self, forbidden: str):
        path = APP_STRATEGIES_DIR / "base.py"
        src = path.read_text(encoding="utf-8")
        assert forbidden not in src, f"Found forbidden credential substring {forbidden!r} in base.py"


class TestCredentialSubstringsZeroInStrategiesInit:
    @pytest.mark.parametrize("forbidden", FORBIDDEN_CREDENTIAL_SUBSTRINGS)
    def test_init_py_no_forbidden_credential_substrings(self, forbidden: str):
        path = APP_STRATEGIES_DIR / "__init__.py"
        src = path.read_text(encoding="utf-8")
        assert forbidden not in src, f"Found forbidden credential substring {forbidden!r} in __init__.py"


class TestForbiddenImportsInStrategiesBase:
    @pytest.mark.parametrize("lib", FORBIDDEN_IMPORT_LIBS)
    def test_base_py_no_forbidden_imports(self, lib: str):
        path = APP_STRATEGIES_DIR / "base.py"
        src = path.read_text(encoding="utf-8")
        hit_import = f"import {lib}" in src
        hit_from_import = f"from {lib} import" in src
        hit_from_dot = f"from {lib}." in src
        assert not (hit_import or hit_from_import or hit_from_dot), (
            f"Found forbidden import of {lib!r} in strategies/base.py"
        )


class TestForbiddenImportsInStrategiesInit:
    @pytest.mark.parametrize("lib", FORBIDDEN_IMPORT_LIBS)
    def test_init_py_no_forbidden_imports(self, lib: str):
        path = APP_STRATEGIES_DIR / "__init__.py"
        src = path.read_text(encoding="utf-8")
        hit_import = f"import {lib}" in src
        hit_from_import = f"from {lib} import" in src
        hit_from_dot = f"from {lib}." in src
        assert not (hit_import or hit_from_import or hit_from_dot), (
            f"Found forbidden import of {lib!r} in strategies/__init__.py"
        )


class TestPyprojectDependenciesEmpty:
    def test_pyproject_toml_dependencies_empty_list_c10(self):
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        src = pyproject_path.read_text(encoding="utf-8")
        assert "dependencies = []" in src, "C-10: pyproject.toml must have dependencies = []"


class TestContractVersion:
    def test_contract_version_public_import_one_point_zero_zero(self):
        from app.contracts import CONTRACT_VERSION

        assert str(CONTRACT_VERSION) == "1.0.0"


class TestStrategySignalPublicImportsUnchanged:
    def test_public_import_strategysignal_exists(self):
        from app.contracts.strategy import StrategySignal

        assert StrategySignal is not None

    def test_public_import_signaldirection_exists(self):
        from app.contracts.strategy import SignalDirection

        assert SignalDirection is not None

    def test_public_import_strategycontext_exists(self):
        from app.contracts.strategy import StrategyContext

        assert StrategyContext is not None

    def test_public_import_portfoliocontextview_exists(self):
        from app.contracts.strategy import PortfolioContextView

        assert PortfolioContextView is not None

    def test_public_import_eligibilitycontextview_exists(self):
        from app.contracts.strategy import EligibilityContextView

        assert EligibilityContextView is not None

    def test_public_import_opportunityscorecomponentpolicy_exists(self):
        from app.contracts.strategy import OpportunityScoreComponentPolicy

        assert OpportunityScoreComponentPolicy is not None

    def test_public_import_stoppolicyspec_exists(self):
        from app.contracts.strategy import StopPolicySpec

        assert StopPolicySpec is not None

    def test_public_import_takeprofitpolicyspec_exists(self):
        from app.contracts.strategy import TakeProfitPolicySpec

        assert TakeProfitPolicySpec is not None


class TestShortForbidden:
    def test_signal_direction_enum_length_is_three_no_short(self):
        from app.contracts.strategy import SignalDirection

        values = list(SignalDirection)
        assert len(values) == 3
        value_names = {v.name for v in values}
        assert "short" not in value_names
        assert "SHORT" not in value_names


class TestRegressionSmokeImports:
    def test_regime_engine_import_ok(self):
        from app.regime import engine as regime_engine

        assert regime_engine is not None

    def test_features_engine_import_ok(self):
        from app.features import engine as features_engine

        assert features_engine is not None

    def test_contracts_strategy_import_ok(self):
        from app.contracts import strategy as contracts_strategy

        assert contracts_strategy is not None

    def test_contracts_regime_import_ok(self):
        from app.contracts import regime as contracts_regime

        assert contracts_regime is not None

    def test_contracts_feature_import_ok(self):
        from app.contracts import feature as contracts_feature

        assert contracts_feature is not None

    def test_strategies_import_ok(self):
        from app import strategies as strategies_module

        assert strategies_module is not None


class Test12StoryImportSmokes:
    def test_import_canonical_ok(self):
        from app.contracts import canonical

        assert canonical is not None

    def test_import_exceptions_ok(self):
        from app.contracts import exceptions

        assert exceptions is not None

    def test_import_strategy_ok(self):
        from app.contracts import strategy

        assert strategy is not None

    def test_import_regime_ok(self):
        from app.contracts import regime

        assert regime is not None

    def test_import_feature_ok(self):
        from app.contracts import feature

        assert feature is not None

    def test_import_opportunity_ok(self):
        from app.contracts import opportunity

        assert opportunity is not None

    def test_import_paper_ok(self):
        from app.contracts import paper

        assert paper is not None

    def test_import_portfolio_ok(self):
        from app.contracts import portfolio

        assert portfolio is not None

    def test_import_risk_ok(self):
        from app.contracts import risk

        assert risk is not None

    def test_import_types_ok(self):
        from app.contracts import types

        assert types is not None

    def test_import_market_ok(self):
        from app.contracts import market

        assert market is not None

    def test_import_strategies_module_ok(self):
        from app import strategies

        assert strategies is not None
