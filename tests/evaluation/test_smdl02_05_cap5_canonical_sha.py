"""T05 — CAP-5: canonical ordering + schema_sha256 determinism. 6 tests."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)


def test_schema_sha_length_64_hex(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    sha = r.payload.schema_sha256()
    assert isinstance(sha, str) and len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)


def test_to_sorted_dict_is_sorted(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    import json

    d = r.payload.to_sorted_dict()
    raw = json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)
    raw2 = json.dumps(json.loads(json.dumps(d, default=str)), sort_keys=True, separators=(",", ":"), default=str)
    assert raw == raw2


def test_canonical_independent_of_fixture_call_order(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r1 = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    r2 = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r1.schema_sha256() == r2.schema_sha256()


def test_canonical_compare_result_matches_payload_sha(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.schema_sha256() == r.payload.schema_sha256()


def test_metric_order_in_payload_deterministic(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r1 = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    r2 = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    keys1 = [m.metric_key for m in r1.payload.metric_deltas]
    keys2 = [m.metric_key for m in r2.payload.metric_deltas]
    assert keys1 == keys2


def test_schema_sha_change_when_metrics_change(tmp_path):
    fix_a = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r_a = fix_a["engine"].compare(fix_a["champion_mv"].model_id, fix_a["champion_mv"].version, fix_a["challenger_mv"].model_id, fix_a["challenger_mv"].version)
    # Build fixture with modified metrics
    import tempfile
    from tests.evaluation.conftest import make_engine_with_fixtures as mewf

    with tempfile.TemporaryDirectory() as d:
        p2 = Path(d)
        worse_ct = dict(challenger_better_metrics())
        worse_ct["return_pct"] = Decimal("0.08000000")
        fix_b = mewf(p2, champion_metrics(), worse_ct)
        r_b = fix_b["engine"].compare(fix_b["champion_mv"].model_id, fix_b["champion_mv"].version, fix_b["challenger_mv"].model_id, fix_b["challenger_mv"].version)
        assert r_a.schema_sha256() != r_b.schema_sha256()
