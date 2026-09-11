from __future__ import annotations

import importlib

import pytest


def test_smdl01_21_contracts_modelversion_preserved():
    import app.contracts as C

    assert hasattr(C, "ModelVersion"), "app.contracts missing ModelVersion attribute"
    assert C.ModelVersion is not None


def test_smdl01_21_contracts_opportunityscore_preserved():
    import app.contracts as C

    assert hasattr(C, "OpportunityScore"), "app.contracts missing OpportunityScore attribute"
    assert C.OpportunityScore is not None


def test_smdl01_21_import_backtest_runner_no_attributeerror():
    try:
        from app.backtest import runner  # noqa: F401
    except AttributeError:
        pytest.fail("app.backtest.runner import raised AttributeError")
    except Exception as exc:
        if isinstance(exc, AttributeError):
            pytest.fail("app.backtest.runner import raised AttributeError")
        pass

    import app.backtest.runner as br
    assert br is not None


def test_smdl01_21_import_risk_base_no_attributeerror():
    try:
        from app.risk import base  # noqa: F401
    except AttributeError:
        pytest.fail("app.risk.base import raised AttributeError")
    except Exception as exc:
        if isinstance(exc, AttributeError):
            pytest.fail("app.risk.base import raised AttributeError")
        pass

    import app.risk.base as rb
    assert rb is not None
