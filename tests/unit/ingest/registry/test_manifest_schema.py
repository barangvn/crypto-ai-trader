from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from app.ingest.registry import ReplayBundleManifest, IntegrityResult, IntegrityReason


REQUIRED_MANIFEST_FIELDS = {
    "bundle_id", "bundle_version", "display_name", "fixture_path",
    "event_type", "symbols", "timeframes", "expected_rows",
    "expected_first_ts", "expected_last_ts", "checksum_sha256",
    "tags", "registered_at", "notes", "manifest_path",
}


class TestManifestSchema:
    def test_required_fields_count_and_names(self) -> None:
        fset = {f.name for f in fields(ReplayBundleManifest)}
        for req in REQUIRED_MANIFEST_FIELDS:
            assert req in fset, f"Missing field {req}"

    def test_required_checksum_field_is_required(self) -> None:
        data = {
            "bundle_id": "x", "bundle_version": "1.0.0", "display_name": "X",
            "fixture_path": "a.csv", "event_type": "candle",
            "symbols": [], "timeframes": [], "expected_rows": 0,
            "expected_first_ts": "", "expected_last_ts": "",
            # no checksum_sha256
            "tags": [],
        }
        with pytest.raises((KeyError, TypeError)):
            ReplayBundleManifest.from_dict(data)

    def test_default_tags_not_none(self) -> None:
        m = ReplayBundleManifest.from_dict({
            "bundle_id": "x", "bundle_version": "1.0.0", "display_name": "X",
            "fixture_path": "a.csv", "event_type": "candle",
            "symbols": [], "timeframes": [], "expected_rows": 0,
            "expected_first_ts": "", "expected_last_ts": "",
            "checksum_sha256": "abc",
        })
        assert isinstance(m.tags, list)

    def test_roundtrip_dict(self) -> None:
        m = ReplayBundleManifest.from_dict({
            "bundle_id": "small", "bundle_version": "1.0.0", "display_name": "S",
            "fixture_path": "tests_fixtures/x.csv", "event_type": "candle",
            "symbols": ["BTC_USDT"], "timeframes": ["1m"], "expected_rows": 5,
            "expected_first_ts": "2024-01-01T00:00:00.000Z",
            "expected_last_ts": "2024-01-01T00:04:00.000Z",
            "checksum_sha256": "a" * 64, "tags": ["happy"],
        })
        d = m.to_dict()
        m2 = ReplayBundleManifest.from_dict(d)
        assert m2.bundle_id == m.bundle_id
        assert m2.symbols == m.symbols

    def test_integrity_result_has_passed_degraded_reasons(self) -> None:
        r = IntegrityResult(passed=False, degraded=True, reasons=[IntegrityReason(code="I1", message="x")])
        assert r.passed is False
        assert r.degraded is True
        assert len(r.reasons) == 1
        assert r.to_dict()["reasons"][0]["code"] == "I1"
