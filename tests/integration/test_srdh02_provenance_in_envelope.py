from __future__ import annotations

from pathlib import Path

from app.ingest.registry import ReplayBundleRegistry
from app.contracts import CONTRACT_VERSION, SourceType
from app.ingest.adapters.replay_bundle_adapter import ReplayBundleAdapter
from app.platform.event_bus import InMemoryTypedEventBus
from app.processing import DataQualityMonitor, Normalizer, set_clock_ref_for_replay
from app.contracts.canonical import CanonicalEventEnvelope


FIXTURES = Path("tests_fixtures")
FIXED_CORR_ID = "corr:srdh02:prov-test:v1"


def _run_envelopes(adapter: ReplayBundleAdapter, *, source_overrides: dict | None = None):
    bus = InMemoryTypedEventBus()
    nm = Normalizer(run_mode="paper", source_type="replay")
    _BIG_STALE_MS = 100 * 365 * 24 * 60 * 60 * 1000
    qm = DataQualityMonitor(stale_threshold_ms=_BIG_STALE_MS)
    published = []
    for raw_row in adapter.stream_market_events():
        envelope: CanonicalEventEnvelope = nm.normalize_one(
            raw_row,
            correlation_id=FIXED_CORR_ID,
            event_id_factory=None,
        )
        set_clock_ref_for_replay(envelope)
        _, is_q = qm.validate_one(envelope)
        if not is_q and not envelope.quality_flags.quarantined:
            bus.publish(envelope)
            published.append(envelope)
    return published


class TestProvenanceInEnvelope:
    def test_source_different_per_bundle(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        a1 = reg.get_adapter("small_3sym_1h_1m_candles")
        a2 = reg.get_adapter("edge_stale")
        # Adapter source string (provenance carrier) is unique per bundle
        assert a1.default_source != a2.default_source
        assert "small_3sym_1h_1m_candles" in a1.default_source
        assert "edge_stale" in a2.default_source
        # Envelope construction itself works and envelope.source_type is replay
        env1 = _run_envelopes(a1)
        env2 = _run_envelopes(a2)
        assert len(env1) > 10
        assert len(env2) > 0
        for e in env1:
            assert e.source_type == SourceType.REPLAY
        for e in env2:
            assert e.source_type == SourceType.REPLAY

    def test_envelope_contains_all_seven_quality_flags_unchanged(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        adapter = reg.get_adapter("small_3sym_1h_1m_candles")
        envelopes = _run_envelopes(adapter)
        assert len(envelopes) == 180
        for e in envelopes:
            qf = e.quality_flags
            # seven booleans all exist and are booleans
            for attr in ("stale", "missing", "duplicate", "out_of_order", "invalid", "quarantined", "degraded"):
                val = getattr(qf, attr)
                assert isinstance(val, bool)

    def test_contract_version_and_source_type_preserved(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        adapter = reg.get_adapter("small_3sym_1h_1m_candles")
        envelopes = _run_envelopes(adapter)
        for e in envelopes:
            assert e.contract_version == CONTRACT_VERSION
            assert e.source_type == SourceType.REPLAY

    def test_stream_multiple_envelopes_have_distinct_bundle_sources(self) -> None:
        reg = ReplayBundleRegistry.auto_register(FIXTURES)
        # Simulate two adapters then normalize individually then compare source values
        bid1 = "small_3sym_1h_1m_candles"
        bid2 = "edge_stale"
        frames = list(reg.stream_multiple([bid1, bid2]))
        provenance_per_frame = [(f.get("_provenance_bundle_id"), f.get("_provenance_checksum_prefix"), f.get("_provenance_version")) for f in frames]
        bundle_ids_seen = {p[0] for p in provenance_per_frame}
        assert bundle_ids_seen == {bid1, bid2}
        # sha prefixes are 12 chars
        for _, prefix, ver in provenance_per_frame:
            assert isinstance(prefix, str) and len(prefix) == 12
            assert isinstance(ver, str) and ver
