from __future__ import annotations

from pathlib import Path

import pytest

from app.ingest.registry import ReplayBundleRegistry


FIXTURES = Path("tests_fixtures")


@pytest.mark.failure_injection
class TestRegistryNetworkSafety:
    def test_registry_works_with_network_blocked(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        manifests = reg.list()
        assert len(manifests) == 7
        for m in manifests:
            assert reg.validate_integrity(m).passed is True

    def test_stream_multiple_with_network_blocked(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        frames = list(reg.stream_multiple(["small_3sym_1h_1m_candles", "edge_stale"]))
        assert len(frames) > 150
