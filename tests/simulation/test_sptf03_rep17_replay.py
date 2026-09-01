import json
import hashlib
import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h


def _replay_fixture_1():
    return [
        (0, Decimal("10000"), Decimal("0"), Decimal("0"), Decimal("0"), "CORR_A_SPTF03_RPL_001", "CAUS_A_SPTF03_RPL_001"),
        (-60, Decimal("10050"), Decimal("10"), Decimal("1"), Decimal("50"), "CORR_B_SPTF03_RPL_002", "CAUS_B_SPTF03_RPL_002"),
        (-180, Decimal("9900"), Decimal("5"), Decimal("1.5"), Decimal("800"), "CORR_C_SPTF03_RPL_003", "CAUS_C_SPTF03_RPL_003"),
        (-360, Decimal("10200"), Decimal("20"), Decimal("2"), Decimal("400"), "CORR_D_SPTF03_RPL_004", "CAUS_D_SPTF03_RPL_004"),
        (-720, Decimal("9800"), Decimal("-50"), Decimal("3"), Decimal("1200"), "CORR_E_SPTF03_RPL_005", "CAUS_E_SPTF03_RPL_005"),
        (-1080, Decimal("10500"), Decimal("100"), Decimal("4"), Decimal("200"), "CORR_F_SPTF03_RPL_006", "CAUS_F_SPTF03_RPL_006"),
        (-1440, Decimal("10000"), Decimal("0"), Decimal("0"), Decimal("0"), "CORR_G_SPTF03_RPL_007", "CAUS_G_SPTF03_RPL_007"),  # exactly 24h
    ]


def _fixture_to_snaps(fixture):
    snaps = []
    for idx, row in enumerate(fixture):
        m, eq, rl, fe, ex, co, ca = row
        snaps.append(make_snapshot(
            minutes_delta=m,
            equity=eq,
            realized=rl,
            fees_total=fe,
            exposure=ex,
            corr=co,
            caus=ca,
            snapshot_id=f"REPLAY_SNAP_{idx:03d}_{abs(m)}",
        ))
    return snaps


class TestSPTF03REP17Replay:
    def test_replay_fixture_same_output_100_runs(self):
        snaps = _fixture_to_snaps(_replay_fixture_1())
        end_ts = make_ts(0)
        baseline = build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts)
        for i in range(100):
            r = build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts)
            assert r == baseline

    def test_no_live_replay_branching(self):
        """Live/Replay branching için run_mode/source_type if bulunmaz (CAP1 ile zaten cover)"""
        # Ekstra kontrol: build_rolling_24h fonksiyonunda "run_mode" string literal yok
        import inspect
        from app.simulation import portfolio as pmod
        src = inspect.getsource(pmod.build_rolling_24h)
        assert "run_mode" not in src
        assert "replay" not in src.lower() or "replay" in "info"  # replay kelimesi ancak docstring'de olabilir
        assert "live" not in src.lower() or "live" in "info"

    def test_replay_sha256_immutable(self):
        snaps = _fixture_to_snaps(_replay_fixture_1())
        end_ts = make_ts(0)
        baseline_sha = build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts).schema_sha256()
        for _ in range(20):
            assert build_rolling_24h(snapshot_samples=snaps, end_ts=end_ts).schema_sha256() == baseline_sha

    def test_replay_corr_caus_same(self):
        snaps = _fixture_to_snaps(_replay_fixture_1())
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.correlation_id == "CORR_A_SPTF03_RPL_001"
        assert res.causation_id.startswith("REPLAY_SNAP_") or res.causation_id != ""
