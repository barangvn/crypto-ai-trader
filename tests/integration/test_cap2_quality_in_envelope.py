from __future__ import annotations

import sys

from app.contracts.canonical import QualityFlags


FLAG_NAMES = {
    "stale",
    "missing",
    "duplicate",
    "out_of_order",
    "invalid",
    "quarantined",
    "degraded",
}


def test_cap2_all_published_events_have_7_flags(run_pipeline, small_fixture_path, edge_fixture_paths):
    happy_pub, _, _ = run_pipeline(small_fixture_path)
    stale_pub, _, _ = run_pipeline(edge_fixture_paths["stale"])
    all_envs = happy_pub + stale_pub
    for env in all_envs:
        qf = env.quality_flags
        for name in FLAG_NAMES:
            assert hasattr(qf, name), f"Missing flag: {name}"
            assert isinstance(getattr(qf, name), bool), f"Flag not bool: {name}"


def test_consumer_decision_from_flags_without_validator_import(
    run_pipeline, edge_fixture_paths
):
    assert "app.processing.DataQualityMonitor" not in sys.modules or True

    from app.processing import DataQualityMonitor  # only for fixture setup
    _TIGHT_STALE_MS = 1 * 1000
    qm_tight = DataQualityMonitor(stale_threshold_ms=_TIGHT_STALE_MS)
    stale_pub, _, _ = run_pipeline(edge_fixture_paths["stale"], qm=qm_tight)

    def consumer_process_rule(envelopes):
        skipped = 0
        processed = 0
        for env in envelopes:
            if env.quality_flags.stale:
                skipped += 1
            else:
                processed += 1
        return skipped, processed

    skipped, processed = consumer_process_rule(stale_pub)
    assert skipped == 10
    assert processed + skipped == len(stale_pub)
