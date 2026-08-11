from __future__ import annotations

from app.contracts import CONTRACT_VERSION, SourceType


def test_happy_path_180_candles_published(run_pipeline, small_fixture_path):
    published, quarantined, bus = run_pipeline(small_fixture_path)
    assert len(published) == 180


def test_happy_path_zero_quarantined(run_pipeline, small_fixture_path):
    published, quarantined, bus = run_pipeline(small_fixture_path)
    assert len(quarantined) == 0


def test_happy_path_all_flags_fresh(run_pipeline, small_fixture_path):
    published, quarantined, bus = run_pipeline(small_fixture_path)
    for env in published:
        qf = env.quality_flags
        assert qf.stale is False
        assert qf.missing is False
        assert qf.duplicate is False
        assert qf.out_of_order is False
        assert qf.invalid is False
        assert qf.quarantined is False
        assert qf.degraded is False


def test_happy_path_all_source_type_replay(run_pipeline, small_fixture_path):
    published, quarantined, bus = run_pipeline(small_fixture_path)
    for env in published:
        assert env.source_type == SourceType.REPLAY


def test_happy_path_all_event_type_candle_v1(run_pipeline, small_fixture_path):
    published, quarantined, bus = run_pipeline(small_fixture_path)
    for env in published:
        assert env.event_type == "candle.v1"


def test_happy_path_contract_version_all_1_0_0(run_pipeline, small_fixture_path):
    published, quarantined, bus = run_pipeline(small_fixture_path)
    for env in published:
        assert env.contract_version == CONTRACT_VERSION
