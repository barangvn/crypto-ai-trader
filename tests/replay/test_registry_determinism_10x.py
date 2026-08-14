from __future__ import annotations

from pathlib import Path

import pytest

from app.ingest.registry import ReplayBundleRegistry


FIXTURES = Path("tests_fixtures")


BUNDLE_IDS_FOR_DETERMINISM = [
    "small_3sym_1h_1m_candles",
    "edge_duplicate",
    "edge_missing",
]


def _signature(reg: ReplayBundleRegistry, n: int | None = None):
    frames = list(reg.stream_multiple(BUNDLE_IDS_FOR_DETERMINISM))
    if n is not None:
        frames = frames[:n]
    return [
        (
            f.get("_bundle_id"),
            f.get("_bundle_row_index"),
            f.get("raw_symbol"),
            f.get("raw_timestamp"),
            f.get("open"),
        )
        for f in frames
    ]


@pytest.mark.replay
class TestRegistryDeterminismTenRuns:
    def test_auto_register_and_stream_deterministic_ten_runs(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        first = _signature(reg, n=200)
        for _ in range(9):
            reg2 = ReplayBundleRegistry.auto_register(FIXTURES)
            assert _signature(reg2, n=200) == first

    def test_list_order_deterministic_ten_runs(self) -> None:
        ids_list: list[list[str]] = []
        for _ in range(10):
            reg = ReplayBundleRegistry.auto_register(FIXTURES)
            ids_list.append([m.bundle_id for m in reg.list()])
        for other in ids_list[1:]:
            assert other == ids_list[0]
