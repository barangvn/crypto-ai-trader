from __future__ import annotations

from uuid import UUID, uuid5


FIXED_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _make_event_id_factory():
    counter = {"n": 0}

    def factory() -> str:
        counter["n"] += 1
        return str(uuid5(FIXED_NAMESPACE, f"evt-{counter['n']}"))

    return factory


def test_10_runs_same_event_ids_and_flags(
    run_pipeline, small_fixture_path, corr_id_fixed
):
    results = []
    for _ in range(10):
        published, quarantined, _ = run_pipeline(
            small_fixture_path,
            corr_id=corr_id_fixed,
            event_id_factory=_make_event_id_factory(),
        )
        results.append({
            "count": len(published),
            "q_count": len(quarantined),
            "event_ids": [e.event_id for e in published],
            "symbols": [e.symbol for e in published],
            "timestamps": [e.timestamp for e in published],
            "flags": [
                (
                    e.quality_flags.stale,
                    e.quality_flags.missing,
                    e.quality_flags.duplicate,
                    e.quality_flags.out_of_order,
                    e.quality_flags.invalid,
                    e.quality_flags.quarantined,
                    e.quality_flags.degraded,
                )
                for e in published
            ],
        })
    first = results[0]
    for r in results[1:]:
        assert r["count"] == first["count"]
        assert r["q_count"] == first["q_count"]
        assert r["event_ids"] == first["event_ids"]
        assert r["symbols"] == first["symbols"]
        assert r["timestamps"] == first["timestamps"]
        assert r["flags"] == first["flags"]
    assert first["count"] == 180
    assert first["q_count"] == 0


def test_deterministic_event_id_sequence(
    run_pipeline, small_fixture_path, corr_id_fixed
):
    pub1, _, _ = run_pipeline(
        small_fixture_path, corr_id=corr_id_fixed, event_id_factory=_make_event_id_factory()
    )
    pub2, _, _ = run_pipeline(
        small_fixture_path, corr_id=corr_id_fixed, event_id_factory=_make_event_id_factory()
    )
    ids1 = [e.event_id for e in pub1]
    ids2 = [e.event_id for e in pub2]
    assert ids1 == ids2
    assert len(set(ids1)) == len(ids1)
