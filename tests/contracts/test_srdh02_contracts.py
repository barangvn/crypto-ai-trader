from __future__ import annotations

from pathlib import Path
import typing

import pytest

from app.ingest.adapters.base import PublicExchangeAdapter, RawFrame
from app.ingest.adapters.replay_bundle_adapter import ReplayBundleAdapter
from app.ingest.registry import ReplayBundleRegistry
from app.ingest.registry.merge_iterator import merge_iterators


FIXTURES = Path("tests_fixtures")


def _has_protocol_methods(obj) -> bool:
    required = {"stream_market_events"}
    return all(hasattr(obj, a) and callable(getattr(obj, a, None)) for a in required)


@pytest.mark.contract
class TestSRDH02Contracts:
    def test_get_adapter_returns_public_exchange_adapter(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        bid = "small_3sym_1h_1m_candles"
        adapter = reg.get_adapter(bid)
        assert isinstance(adapter, ReplayBundleAdapter)
        if typing.get_origin(PublicExchangeAdapter) is not None or hasattr(PublicExchangeAdapter, "__protocol_attrs__") or (
            hasattr(PublicExchangeAdapter, "_is_protocol") and getattr(PublicExchangeAdapter, "_is_runtime_checkable", False)
        ):
            try:
                assert isinstance(adapter, PublicExchangeAdapter)
            except TypeError:
                # Protocol isn't @runtime_checkable — fall back to structural check
                pass
        assert _has_protocol_methods(adapter), "Adapter lacks PublicExchangeAdapter protocol methods"
        it = adapter.stream_market_events()
        first = next(iter(it))
        assert isinstance(first, dict)


    def test_merge_iterator_stream_multiple_respects_protocol(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        for frame in reg.stream_multiple(["small_3sym_1h_1m_candles", "edge_stale"]):
            # RawFrame typing (dict subtype)
            assert isinstance(frame, dict)
            break

    def test_adapter_stream_is_iterator_of_rawframes(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        adapter = reg.get_adapter("edge_stale")
        count = 0
        for f in adapter.stream_market_events():
            assert isinstance(f, dict)
            assert "raw_symbol" in f
            count += 1
        assert count > 0
