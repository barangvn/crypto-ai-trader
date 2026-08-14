from __future__ import annotations

from pathlib import Path
import tempfile
import shutil
import hashlib
import os

import pytest

from app.ingest.registry import (
    ReplayBundleManifest,
    ReplayBundleRegistry,
    RegistryIntegrityError,
    build_manifest,
)


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path("tests_fixtures")


class TestIntegrityChecks:
    def test_i1_file_missing(self, fixtures_dir: Path) -> None:
        reg = ReplayBundleRegistry()
        good = build_manifest(fixtures_dir / "small_3sym_1h_1m_candles.csv")
        bad = ReplayBundleManifest.from_dict({
            **good.to_dict(),
            "fixture_path": str(fixtures_dir / "definitely_nope_xyz123.csv"),
        })
        res = reg.validate_integrity(bad)
        assert res.passed is False
        assert res.degraded is True
        assert any(r.code == "I1_FILE_MISSING" for r in res.reasons)

    def test_i2_rowcount_mismatch(self, fixtures_dir: Path) -> None:
        reg = ReplayBundleRegistry()
        good = build_manifest(fixtures_dir / "small_3sym_1h_1m_candles.csv")
        bad = ReplayBundleManifest.from_dict({**good.to_dict(), "expected_rows": 999999})
        res = reg.validate_integrity(bad)
        assert res.passed is False
        assert any(r.code == "I2_ROWCOUNT_MISMATCH" for r in res.reasons)

    def test_i3_checksum_mismatch(self, fixtures_dir: Path) -> None:
        reg = ReplayBundleRegistry()
        good = build_manifest(fixtures_dir / "edge_stale.csv")
        bad = ReplayBundleManifest.from_dict({**good.to_dict(), "checksum_sha256": "0" * 64})
        res = reg.validate_integrity(bad)
        assert res.passed is False
        assert any(r.code == "I3_CHECKSUM_MISMATCH" for r in res.reasons)

    def test_i3_checksum_hard_fail_get_adapter_raises(self, fixtures_dir: Path) -> None:
        good = build_manifest(fixtures_dir / "edge_stale.csv")
        bad = ReplayBundleManifest.from_dict({**good.to_dict(), "checksum_sha256": "0" * 64})
        reg = ReplayBundleRegistry(manifests=[bad])
        with pytest.raises(RegistryIntegrityError):
            reg.get_adapter(bad.bundle_id)

    def test_i4_header_mismatch(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "edge_stale.csv"
        txt = src.read_text(encoding="utf-8")
        lines = txt.splitlines()
        header = ",".join(col for col in lines[0].split(",") if col != "raw_timestamp")
        new_csv = tmp_path / "no_raw_ts.csv"
        new_csv.write_text(header + "\n" + "\n".join(lines[1:]) + "\n", encoding="utf-8")
        m = build_manifest(new_csv)
        m.event_type = "candle"
        reg = ReplayBundleRegistry()
        res = reg.validate_integrity(m)
        assert any(r.code == "I4_HEADER_MISMATCH" for r in res.reasons), [r.code for r in res.reasons]
        assert res.degraded is True

    def test_i5_symbol_coverage_weak_degrade_only(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "edge_stale.csv"
        new_csv = tmp_path / "weak_syms.csv"
        txt = src.read_text(encoding="utf-8").replace("BTC/USDT", "ETH/USDT")
        new_csv.write_text(txt, encoding="utf-8")
        m = build_manifest(new_csv)
        m.symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
        reg = ReplayBundleRegistry()
        res = reg.validate_integrity(m)
        codes = {r.code for r in res.reasons}
        assert "I5_SYMBOL_COVERAGE_WEAK" in codes
        assert res.passed is True
        assert res.degraded is True

    def test_adapter_for_good_manifest_is_replay_bundle_adapter(self, fixtures_dir: Path) -> None:
        from app.ingest.adapters.replay_bundle_adapter import ReplayBundleAdapter
        reg = ReplayBundleRegistry.auto_register(fixtures_dir)
        bid = [m.bundle_id for m in reg.list() if "small" in m.bundle_id][0]
        adapter = reg.get_adapter(bid)
        assert type(adapter).__name__ == "ReplayBundleAdapter"
        assert isinstance(adapter, ReplayBundleAdapter)

    def test_adapter_source_contains_bundle_id_and_version(self, fixtures_dir: Path) -> None:
        reg = ReplayBundleRegistry.auto_register(fixtures_dir)
        bid = "small_3sym_1h_1m_candles"
        m = reg.get(bid)
        assert m is not None
        adapter = reg.get_adapter(bid)
        src = adapter.default_source
        assert bid in src
        assert m.bundle_version in src
        assert "@sha256:" in src
