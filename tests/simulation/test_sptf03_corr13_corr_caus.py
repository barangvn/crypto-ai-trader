import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts
from app.simulation.portfolio import build_rolling_24h, CORR_UNKNOWN_ROLLING, CAUS_UNKNOWN_ROLLING, INFO_EMPTY_WINDOW


class TestSPTF03CORR13CorrelationCausation:
    def test_input_empty_const_corr_caus_adn04(self):
        res = build_rolling_24h(snapshot_samples=[], end_ts=make_ts(0))
        assert res.correlation_id == CORR_UNKNOWN_ROLLING
        assert res.causation_id == CAUS_UNKNOWN_ROLLING

    def test_input_full_but_all_outside_window_latest_input_fallback_adn04(self):
        # Input dolu ama window dışı → latest input sample corr/caus
        s1 = make_snapshot(minutes_delta=-60*49, corr="CORR_BTC_LATEST_XYZ_123", caus="CAUS_BTC_LATEST_XYZ_123")
        s2 = make_snapshot(minutes_delta=-60*50, corr="CORR_EARLIER_AAAAAA", caus="CAUS_EARLIER_BBBBB")
        res = build_rolling_24h(snapshot_samples=[s2, s1], end_ts=make_ts(0))
        assert INFO_EMPTY_WINDOW in res.info_codes
        assert res.correlation_id == "CORR_BTC_LATEST_XYZ_123"  # en yeni input (latest by ts)
        assert res.causation_id == "CAUS_BTC_LATEST_XYZ_123"

    def test_in_window_latest_sample_corr_caus_used(self):
        s_old = make_snapshot(minutes_delta=-600, corr="CORR_OLD_11111111", caus="CAUS_OLD_11111111")
        s_last = make_snapshot(minutes_delta=0, corr="CORR_LAST_24H_AAAA", caus="CAUS_LAST_24H_BBBB")
        res = build_rolling_24h(snapshot_samples=[s_old, s_last], end_ts=make_ts(0))
        assert res.correlation_id == "CORR_LAST_24H_AAAA"
        assert res.causation_id == "CAUS_LAST_24H_BBBB"

    def test_corr_caus_none_not_mutated(self):
        s = make_snapshot(minutes_delta=0, corr="C1_ABCDEFGH", caus="U1_UVWXYZ1234")
        orig_corr = s.correlation_id
        orig_caus = s.causation_id
        res = build_rolling_24h(snapshot_samples=[s], end_ts=make_ts(0))
        assert s.correlation_id == orig_corr
        assert s.causation_id == orig_caus

    def test_dedup_after_dup_first_corr_kept(self):
        sid = "DUP_CORR_SPTF03_00001"
        s1 = make_snapshot(minutes_delta=-60, snapshot_id=sid, corr="CORR_KEEP_FIRST_XXX", caus="CAUS_KEEP_FIRST_YYY")
        s2 = make_snapshot(minutes_delta=-60, snapshot_id=sid, corr="CORR_DROP_THIS_ZZZZZ", caus="CAUS_DROP_THIS_WWWW")
        sl = make_snapshot(minutes_delta=0, corr="CORR_END_SPTF03_AAAAA", caus="CAUS_END_SPTF03_BBBBB")
        res = build_rolling_24h(snapshot_samples=[s1, s2, sl], end_ts=make_ts(0))
        # window sonu end → corr/caus en son (end) kullanılmalı
        assert res.correlation_id == "CORR_END_SPTF03_AAAAA"
        assert res.causation_id == "CAUS_END_SPTF03_BBBBB"

    @pytest.mark.parametrize("corr_id,caus_id", [
        ("CORR_A_001_SPTF", "CAUS_U_001_SPTF"),
        ("CORR_XYZ_999_SPTF", "CAUS_XYZ_999_SPTF"),
        ("C_______8LEN", "U_______8LEN"),
        ("C" * 64, "U" * 64),
    ])
    def test_corr_caus_exact_pass_through(self, corr_id, caus_id):
        s1 = make_snapshot(minutes_delta=-10, corr="ANY_OLD_SPTF03_OLD", caus="ANY_UOLD_SPTF03_OLD")
        s2 = make_snapshot(minutes_delta=0, corr=corr_id, caus=caus_id)
        res = build_rolling_24h(snapshot_samples=[s1, s2], end_ts=make_ts(0))
        assert res.correlation_id == corr_id
        assert res.causation_id == caus_id
