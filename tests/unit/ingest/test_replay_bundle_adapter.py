from __future__ import annotations

from app.ingest.adapters.replay_bundle_adapter import ReplayBundleAdapter


EXPECTED_KEYS = {
    "raw_symbol",
    "raw_timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "trade_count",
    "event_type",
    "timeframe",
    "raw_trade_id",
    "raw_sequence",
    "spread_bps",
    "_row_index",
}


def test_adapter_reads_180_rows(small_fixture_path):
    adapter = ReplayBundleAdapter(small_fixture_path)
    rows = list(adapter.stream_market_events())
    assert len(rows) == 180


def test_adapter_returns_dicts_with_row_index(small_fixture_path):
    adapter = ReplayBundleAdapter(small_fixture_path)
    rows = list(adapter.stream_market_events())
    for i, row in enumerate(rows):
        assert "_row_index" in row
        assert isinstance(row["_row_index"], int)
        assert row["_row_index"] == i


def test_adapter_csv_columns_as_keys(small_fixture_path):
    adapter = ReplayBundleAdapter(small_fixture_path)
    rows = list(adapter.stream_market_events())
    first = rows[0]
    for key in EXPECTED_KEYS:
        assert key in first, f"Missing key: {key}"


def test_adapter_deterministic_order(small_fixture_path):
    adapter1 = ReplayBundleAdapter(small_fixture_path)
    rows1 = list(adapter1.stream_market_events())
    adapter2 = ReplayBundleAdapter(small_fixture_path)
    rows2 = list(adapter2.stream_market_events())
    assert len(rows1) == len(rows2)
    for r1, r2 in zip(rows1, rows2):
        assert r1["_row_index"] == r2["_row_index"]
        assert r1["raw_symbol"] == r2["raw_symbol"]
        assert r1["raw_timestamp"] == r2["raw_timestamp"]
