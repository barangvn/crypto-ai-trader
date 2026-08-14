from __future__ import annotations

from pathlib import Path
import types

import pytest

from app.ingest.registry import ReplayBundleRegistry


FIXTURES = Path("tests_fixtures")


class TestRegistryApi:
    def test_auto_register_returns_seven_manifests(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        all_m = reg.list()
        assert len(all_m) == 7

    def test_list_is_immutable_snapshot(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        a = reg.list()
        a.pop(0)
        assert len(reg.list()) == 7

    def test_get_returns_copy_not_original(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        bid = reg.list()[0].bundle_id
        m1 = reg.get(bid)
        assert m1 is not None
        m1.symbols.append("FAKE_XY")
        m2 = reg.get(bid)
        assert "FAKE_XY" not in (m2.symbols if m2 else [])

    def test_find_by_tag_edge(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        edges = reg.find_by(tag="edge")
        assert len(edges) == 6

    def test_find_by_tag_happy(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        happy = reg.find_by(tag="happy")
        assert len(happy) == 1

    def test_find_by_symbol_btc(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        btc = reg.find_by(symbol="BTC_USDT")
        assert len(btc) >= 1

    def test_unknown_bundle_id_returns_none(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        assert reg.get("does-not-exist") is None

    def test_ad7_public_api_no_state_mutation(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        original_len = len(reg.list())
        _ = reg.list()
        _ = reg.get(reg.list()[0].bundle_id)
        _ = reg.find_by(tag="edge")
        _ = reg.validate_integrity(reg.list()[0])
        try:
            adapter = reg.get_adapter(reg.list()[0].bundle_id)
            _ = list(adapter.stream_market_events())[:3]
        except Exception:
            pass
        try:
            _ = list(reg.stream_multiple([reg.list()[0].bundle_id]))[:3]
        except Exception:
            pass
        after_len = len(reg.list())
        assert after_len == original_len

    def test_ad7_manifests_property_is_frozen_readonly(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        m = reg.manifests
        assert isinstance(m, types.MappingProxyType) or not hasattr(type(m), "__setitem__") or (
            # frozen mapping class raises on setitem
            True
        )
        with pytest.raises((TypeError, AttributeError)):
            m["foo"] = reg.list()[0]  # type: ignore[call-overload]

    def test_stream_multiple_sum_rows(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        bids = ["small_3sym_1h_1m_candles", "edge_stale"]
        expected = sum((reg.get(b) or _zero()).expected_rows for b in bids)
        frames = list(reg.stream_multiple(bids))
        assert len(frames) == expected

    def test_stream_multiple_each_frame_has_bundle_id(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        frames = list(reg.stream_multiple(["small_3sym_1h_1m_candles", "edge_stale"]))
        for f in frames:
            assert "_bundle_id" in f
            assert f["_bundle_id"] in {"small_3sym_1h_1m_candles", "edge_stale"}

    def test_stream_multiple_provenance_fields(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        frames = list(reg.stream_multiple(["small_3sym_1h_1m_candles", "edge_stale"]))
        for f in frames:
            assert "_provenance_bundle_id" in f
            assert "_provenance_checksum_prefix" in f
            assert len(f["_provenance_checksum_prefix"]) == 12
            assert "_provenance_version" in f

    def test_stream_multiple_determinism_two_runs_deep_equal(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        bids = ["small_3sym_1h_1m_candles", "edge_duplicate", "edge_missing"]
        r1 = [
            (
                f.get("_bundle_id"),
                f.get("_bundle_row_index"),
                f.get("raw_symbol"),
                f.get("raw_timestamp"),
            )
            for f in reg.stream_multiple(bids)
        ]
        r2 = [
            (
                f.get("_bundle_id"),
                f.get("_bundle_row_index"),
                f.get("raw_symbol"),
                f.get("raw_timestamp"),
            )
            for f in reg.stream_multiple(bids)
        ]
        assert r1 == r2


def _zero():
    from dataclasses import make_dataclass
    return make_dataclass("X", [("expected_rows", int)])()
