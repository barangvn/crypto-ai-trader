import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts, make_quality_flags, attach_quality
from app.simulation.portfolio import build_rolling_24h, INFO_INVALID_SAMPLES_EXCLUDED, INFO_STALE_SAMPLES_INCLUDED, INFO_EMPTY_WINDOW


class TestSPTF03Q11Quality:
    def test_invalid_excluded_adn02(self):
        s_valid = make_snapshot(minutes_delta=-10, equity=Decimal("100"))
        s_invalid = make_snapshot(minutes_delta=-10, snapshot_id="INV_001")
        attach_quality(s_invalid, make_quality_flags(invalid=True))
        res = build_rolling_24h(snapshot_samples=[s_valid, s_invalid], end_ts=make_ts(0))
        assert res.window_samples_count == 1
        assert INFO_INVALID_SAMPLES_EXCLUDED in res.info_codes

    def test_quarantined_excluded_adn02(self):
        s_ok = make_snapshot(minutes_delta=-10)
        s_q = make_snapshot(minutes_delta=-10, snapshot_id="Q_001")
        attach_quality(s_q, make_quality_flags(quarantined=True))
        res = build_rolling_24h(snapshot_samples=[s_ok, s_q], end_ts=make_ts(0))
        assert res.window_samples_count == 1

    def test_missing_excluded_adn02(self):
        s_ok = make_snapshot(minutes_delta=-10)
        s_m = make_snapshot(minutes_delta=-10, snapshot_id="MISS_001")
        attach_quality(s_m, make_quality_flags(missing=True))
        res = build_rolling_24h(snapshot_samples=[s_ok, s_m], end_ts=make_ts(0))
        assert res.window_samples_count == 1

    def test_all_three_bad_excluded(self):
        s_ok = make_snapshot(minutes_delta=-10)
        s1 = make_snapshot(minutes_delta=-10, snapshot_id="S1")
        s2 = make_snapshot(minutes_delta=-10, snapshot_id="S2")
        s3 = make_snapshot(minutes_delta=-10, snapshot_id="S3")
        attach_quality(s1, make_quality_flags(invalid=True))
        attach_quality(s2, make_quality_flags(quarantined=True))
        attach_quality(s3, make_quality_flags(missing=True))
        res = build_rolling_24h(snapshot_samples=[s_ok, s1, s2, s3], end_ts=make_ts(0))
        assert res.window_samples_count == 1

    def test_stale_included_adn02(self):
        s_ok = make_snapshot(minutes_delta=-10, realized=Decimal("100"))
        s_stale = make_snapshot(minutes_delta=-20, realized=Decimal("50"), snapshot_id="ST_001")
        attach_quality(s_stale, make_quality_flags(stale=True))
        res = build_rolling_24h(snapshot_samples=[s_stale, s_ok], end_ts=make_ts(0))
        assert res.window_samples_count == 2
        assert INFO_STALE_SAMPLES_INCLUDED in res.info_codes
        assert res.rolling_realized_pnl_quote_24h == Decimal("50")

    def test_degraded_included_adn02(self):
        s1 = make_snapshot(minutes_delta=-10, realized=Decimal("100"))
        s_d = make_snapshot(minutes_delta=-20, realized=Decimal("50"), snapshot_id="DEG_001_QLTY")
        attach_quality(s_d, make_quality_flags(degraded=True))
        res = build_rolling_24h(snapshot_samples=[s_d, s1], end_ts=make_ts(0))
        assert res.window_samples_count == 2

    def test_duplicate_flag_included_adn02(self):
        s1 = make_snapshot(minutes_delta=-10, realized=Decimal("100"))
        s_d = make_snapshot(minutes_delta=-20, realized=Decimal("50"), snapshot_id="DFLAG_001")
        attach_quality(s_d, make_quality_flags(duplicate=True))
        res = build_rolling_24h(snapshot_samples=[s_d, s1], end_ts=make_ts(0))
        assert res.window_samples_count == 2

    def test_out_of_order_flag_included_adn02(self):
        s1 = make_snapshot(minutes_delta=-10, realized=Decimal("100"))
        s_o = make_snapshot(minutes_delta=-20, realized=Decimal("50"), snapshot_id="OOFLAG_01")
        attach_quality(s_o, make_quality_flags(out_of_order=True))
        res = build_rolling_24h(snapshot_samples=[s_o, s1], end_ts=make_ts(0))
        assert res.window_samples_count == 2

    def test_qualityflags_immutable_readonly_ad_cap2(self):
        """QualityFlags (S-CON-02A §2.3 frozen=False; Read-Only: tüm fieldlar okunabilir)"""
        qf = make_quality_flags()
        # Read-only — field değerleri okunabilir
        assert qf.invalid is False
        assert qf.quarantined is False
        assert qf.missing is False
        assert qf.stale is False
        assert qf.degraded is False
        assert qf.duplicate is False
        assert qf.out_of_order is False
        # S-PTF-03 kodunda QualityFlags mutate YOK (CAP-2 AST taraması ile test edilir — test_sptf03_cap14)

    @pytest.mark.parametrize("inv,quar,miss,expected_count", [
        (False, False, False, 2),
        (True, False, False, 1),
        (False, True, False, 1),
        (False, False, True, 1),
        (True, True, False, 1),
        (True, False, True, 1),
        (False, True, True, 1),
        (True, True, True, 1),
    ])
    def test_excluded_flags_orthogonal_2x3_matrix(self, inv, quar, miss, expected_count):
        s_ok = make_snapshot(minutes_delta=-10, snapshot_id=f"OK_{inv}{quar}{miss}_")
        s_bad = make_snapshot(minutes_delta=-15, snapshot_id=f"BAD_{inv}{quar}{miss}_")
        attach_quality(s_bad, make_quality_flags(invalid=inv, quarantined=quar, missing=miss))
        res = build_rolling_24h(snapshot_samples=[s_ok, s_bad], end_ts=make_ts(0))
        assert res.window_samples_count == expected_count, f"inv={inv} quar={quar} miss={miss} cnt={res.window_samples_count}"
        if expected_count == 1:
            assert INFO_INVALID_SAMPLES_EXCLUDED in res.info_codes

    @pytest.mark.parametrize("flag_name", ["stale", "degraded", "duplicate", "out_of_order"])
    def test_included_flags_each_one_separate(self, flag_name):
        s_ok = make_snapshot(minutes_delta=-10, realized=Decimal("80"))
        s_flag = make_snapshot(minutes_delta=-20, realized=Decimal("30"), snapshot_id=f"{flag_name.upper()}_INC_")
        kwargs = {flag_name: True}
        attach_quality(s_flag, make_quality_flags(**kwargs))
        res = build_rolling_24h(snapshot_samples=[s_flag, s_ok], end_ts=make_ts(0))
        assert res.window_samples_count == 2

    @pytest.mark.parametrize("combo", [
        {"stale": True, "degraded": True},
        {"stale": True, "duplicate": True},
        {"stale": True, "out_of_order": True},
        {"degraded": True, "duplicate": True},
        {"degraded": True, "out_of_order": True},
        {"duplicate": True, "out_of_order": True},
    ])
    def test_included_flags_pairwise_combinations(self, combo):
        s1 = make_snapshot(minutes_delta=-5, realized=Decimal("200"))
        s2 = make_snapshot(minutes_delta=-120, realized=Decimal("100"), snapshot_id=f"PAIR_{id(combo)}_")
        attach_quality(s2, make_quality_flags(**combo))
        res = build_rolling_24h(snapshot_samples=[s2, s1], end_ts=make_ts(0))
        assert res.window_samples_count == 2
        assert res.rolling_realized_pnl_quote_24h == Decimal("100")

    def test_all_excluded_then_empty_window_fallback(self):
        s_i = make_snapshot(minutes_delta=-5, snapshot_id="AI")
        s_q = make_snapshot(minutes_delta=-10, snapshot_id="AQ")
        s_m = make_snapshot(minutes_delta=-15, snapshot_id="AM")
        attach_quality(s_i, make_quality_flags(invalid=True))
        attach_quality(s_q, make_quality_flags(quarantined=True))
        attach_quality(s_m, make_quality_flags(missing=True))
        res = build_rolling_24h(snapshot_samples=[s_i, s_q, s_m], end_ts=make_ts(0))
        assert res.window_samples_count == 0
        assert INFO_EMPTY_WINDOW in res.info_codes
        # ADN-PTF03-04: input dolu, ama window boş → en yeni input sample corr/caus fallback
        assert res.rolling_realized_pnl_quote_24h == Decimal("0")

    def test_mixed_valid_invalid_50_50_ratio(self):
        snaps = []
        for i in range(20):
            s = make_snapshot(minutes_delta=-(i * 30), snapshot_id=f"MIX_{i:03d}_", equity=Decimal(str(100 + i)))
            if i % 2 == 1:
                attach_quality(s, make_quality_flags(invalid=True))
            snaps.append(s)
        res = build_rolling_24h(snapshot_samples=snaps, end_ts=make_ts(0))
        assert res.window_samples_count == 10  # 0,2,4,...,18 dahil
        assert INFO_INVALID_SAMPLES_EXCLUDED in res.info_codes

