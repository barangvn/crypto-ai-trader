from __future__ import annotations


def test_determinism_same_fixture_two_runs(run_pipeline, small_fixture_path, corr_id_fixed):
    published1, _, _ = run_pipeline(small_fixture_path, corr_id=corr_id_fixed)
    published2, _, _ = run_pipeline(small_fixture_path, corr_id=corr_id_fixed)
    assert len(published1) == len(published2)
    for e1, e2 in zip(published1, published2):
        assert e1.symbol == e2.symbol
        assert e1.timestamp == e2.timestamp
        assert e1.quality_flags.stale == e2.quality_flags.stale
        assert e1.quality_flags.missing == e2.quality_flags.missing
        assert e1.quality_flags.duplicate == e2.quality_flags.duplicate
        assert e1.quality_flags.out_of_order == e2.quality_flags.out_of_order
        assert e1.quality_flags.invalid == e2.quality_flags.invalid
        assert e1.quality_flags.quarantined == e2.quality_flags.quarantined
        assert e1.quality_flags.degraded == e2.quality_flags.degraded


def test_publish_order_fifo_across_runs(run_pipeline, small_fixture_path, corr_id_fixed):
    published1, _, _ = run_pipeline(small_fixture_path, corr_id=corr_id_fixed)
    published2, _, _ = run_pipeline(small_fixture_path, corr_id=corr_id_fixed)
    symbols1 = [e.symbol for e in published1]
    symbols2 = [e.symbol for e in published2]
    assert symbols1 == symbols2


def test_10_runs_consistency(run_pipeline, small_fixture_path, corr_id_fixed):
    counts = []
    for _ in range(10):
        published, quarantined, _ = run_pipeline(small_fixture_path, corr_id=corr_id_fixed)
        counts.append((len(published), len(quarantined)))
    for c in counts:
        assert c == (180, 0)
