from __future__ import annotations

import sys
from typing import Any

import pytest

from app.platform.observability import correlation as corr_mod
from app.platform.observability.correlation import CorrelationContext, set_correlation_provider
from app.platform.observability.factory import (
    StructuredLogger,
    get_logger,
    get_metrics_facade,
    reset_globals_for_test,
)
from app.platform.observability.sinks_log import InMemoryCaptureSink


FIXED_TS = "2026-09-21T12:00:00Z"
FIXED_CORR = "DETERM-CORR-0000000000000000000001"
FIXED_CAUSE_ROOT = "ROOT"


@pytest.fixture(autouse=True)
def _reset_test_state():
    reset_globals_for_test()
    set_correlation_provider(lambda: FIXED_CORR)
    yield
    reset_globals_for_test()


@pytest.fixture
def frozen_ts_logger(monkeypatch):
    import app.platform.observability.serialization as ser_mod

    monkeypatch.setattr(ser_mod, "utc_now_iso", lambda: FIXED_TS)
    sink = InMemoryCaptureSink(level="DEBUG")
    lg = get_logger(module="app.platform.observability.fixture", env="test", sink=sink)
    return lg, sink


@pytest.fixture
def fixed_correlation_root():
    return CorrelationContext(correlation_id=FIXED_CORR, causation_id=FIXED_CAUSE_ROOT)


@pytest.fixture
def fake_env_config():
    class Env:
        def __init__(self, env: str = "test", run_mode: str = "replay"):
            self.env = env
            self.run_mode = run_mode

    return Env
