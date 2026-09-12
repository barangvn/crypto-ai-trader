"""T11 — CAP-11: Determinism 10x identical evaluation payloads/SHA. 13 tests."""

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


def test_10x_same_input_same_schema_sha(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    shas = []
    for _ in range(10):
        r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        shas.append(r.payload.schema_sha256())
    assert len(set(shas)) == 1, f"Multiple unique SHA256 across 10 runs: {len(set(shas))} unique (expected 1)"


def test_10x_same_input_same_metric_order(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    orders = []
    for _ in range(10):
        r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        orders.append(tuple(m.metric_key for m in r.payload.metric_deltas))
    assert len(set(orders)) == 1


def test_10x_same_input_same_winner_hint(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    hints = []
    for _ in range(10):
        r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        hints.append(r.payload.winner_hint.value)
    assert len(set(hints)) == 1


def test_determinism_to_sorted_dict_json(tmp_path):
    import json

    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    dicts_sha = []
    for _ in range(10):
        r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        d = r.payload.to_sorted_dict()
        s = json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)
        import hashlib

        dicts_sha.append(hashlib.sha256(s.encode("utf-8")).hexdigest())
    assert len(set(dicts_sha)) == 1


def test_determinism_two_engine_instances_same_result(tmp_path):
    fix1 = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    # Second engine (fresh compare, same registry)
    from app.evaluation import CompareEngine

    eng2 = CompareEngine(registry=fix1["registry"])
    r1 = fix1["engine"].compare(fix1["champion_mv"].model_id, fix1["champion_mv"].version, fix1["challenger_mv"].model_id, fix1["challenger_mv"].version)
    r2 = eng2.compare(fix1["champion_mv"].model_id, fix1["champion_mv"].version, fix1["challenger_mv"].model_id, fix1["challenger_mv"].version)
    assert r1.schema_sha256() == r2.schema_sha256()


def test_determinism_evidence_order(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    orders = []
    for _ in range(5):
        r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        orders.append(tuple((e.get("kind"), e.get("ref_id")) for e in r.payload.evidence_refs))
    assert len(set(orders)) == 1


# Run 13 tests total (parametrize 7 × 5=35 would overflow; parametrize different metrics for delta stability):
PARAM_FOLD_REGIME_COMBOS = [
    ("no_fold_no_regime", None, None, None, None),
    ("folds_only", [{"return_pct": Decimal("0.01"), "trade_count": 10, "sharpe_ratio": 1.0}], None, None, None),
    ("regimes_only", None, None, [{"strategy_id": "s1", "regime": "r1", "return_pct": Decimal("0.01"), "trade_count": 10, "sharpe_ratio": 1.0}], None),
    ("both", [{"return_pct": Decimal("0.01"), "trade_count": 10, "sharpe_ratio": 1.0}], None, [{"strategy_id": "s1", "regime": "r1", "return_pct": Decimal("0.01"), "trade_count": 10, "sharpe_ratio": 1.0}], None),
    ("stability_present", None, None, None, 0.85),
]


@pytest.mark.parametrize("name,pf,UNUSED,rm,stab", PARAM_FOLD_REGIME_COMBOS)
def test_determinism_variant_configurations_10x(tmp_path, name, pf, UNUSED, rm, stab):
    from tests.evaluation.conftest import _base_metrics_template

    champ = champion_metrics()
    chall = challenger_better_metrics()
    if stab is not None:
        champ["stability"] = float(stab)
        chall["stability"] = float(stab) + 0.02
    pf_ct = pf  # same for challenger
    rm_ct = rm  # same for challenger
    fix = make_engine_with_fixtures(tmp_path, champ, chall, per_fold=pf, challenger_per_fold=pf_ct, regime=rm, challenger_regime=rm_ct)
    shas = []
    for _ in range(10):
        r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        shas.append(r.schema_sha256())
    assert len(set(shas)) == 1, f"variant {name}: unique={len(set(shas))}"


def test_determinism_individual_metric_deltas(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    delta_signatures = []
    for _ in range(10):
        r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        sig = tuple((d.metric_key, d.directionality, str(d.delta), d.winner_hint) for d in r.payload.metric_deltas)
        delta_signatures.append(sig)
    assert len(set(delta_signatures)) == 1
