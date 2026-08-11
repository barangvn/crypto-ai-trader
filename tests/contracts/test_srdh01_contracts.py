from __future__ import annotations

import re
from decimal import Decimal

import pytest

from app.contracts import SourceType


TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

FLAG_NAMES = {
    "stale",
    "missing",
    "duplicate",
    "out_of_order",
    "invalid",
    "quarantined",
    "degraded",
}


@pytest.mark.contract
def test_c_source_type_replay_and_clock_ref(run_pipeline, small_fixture_path):
    published, _, _ = run_pipeline(small_fixture_path)
    for env in published:
        assert env.source_type == SourceType.REPLAY
        assert env.clock_ref.replay is not None
        assert env.clock_ref.replay == env.timestamp


@pytest.mark.contract
def test_c_quality_flags_7_booleans(run_pipeline, small_fixture_path):
    published, _, _ = run_pipeline(small_fixture_path)
    for env in published:
        qf = env.quality_flags
        for name in FLAG_NAMES:
            assert hasattr(qf, name)
            assert isinstance(getattr(qf, name), bool)


@pytest.mark.contract
def test_c_symbol_base_quote_uppercase(run_pipeline, small_fixture_path):
    published, _, _ = run_pipeline(small_fixture_path)
    for env in published:
        sym = env.symbol
        assert "_" in sym
        base, quote = sym.split("_", 1)
        assert base == base.upper()
        assert quote == quote.upper()
        assert base.isalnum()
        assert quote.isalnum()


@pytest.mark.contract
def test_c_timestamp_iso_z_3digit_regex(run_pipeline, small_fixture_path):
    published, _, _ = run_pipeline(small_fixture_path)
    for env in published:
        assert TS_RE.match(env.timestamp) is not None


@pytest.mark.contract
def test_c_monetary_fields_decimal_type(run_pipeline, small_fixture_path):
    published, _, _ = run_pipeline(small_fixture_path)
    for env in published:
        payload = env.payload
        assert isinstance(payload.open, Decimal)
        assert isinstance(payload.high, Decimal)
        assert isinstance(payload.low, Decimal)
        assert isinstance(payload.close, Decimal)
        assert isinstance(payload.volume, Decimal)
