from __future__ import annotations

import pytest

from app.simulation.fill_config import PaperFillRejectReason


# G3: 10 tests — P2 Quality Hard Gate CAP-2
class TestPipelineP2QualityGate:
    def test_healthy_allow(self, sptr01_order_buy, sptr01_sim_default, sptr01_ref_tick, sptr01_quality_healthy):
        res = sptr01_sim_default.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
        assert res.rejected is False
        assert res.fill is not None

    def test_degraded_allow_with_info(self, sptr01_order_buy, sptr01_sim_default, sptr01_ref_tick):
        from app.contracts import QualityFlags
        qf = QualityFlags(degraded=True, reasons=[{"k": "d"}])
        res = sptr01_sim_default.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=qf)
        assert res.rejected is False
        assert res.fill is not None
        assert any("DEGRADED" in c for c in res.info_codes)

    @pytest.mark.parametrize("idx", range(6))
    def test_6_blocking_flags(self, sptr01_order_buy, sptr01_sim_default, sptr01_ref_tick, sptr01_quality_blocked, idx):
        flag_name, qf = sptr01_quality_blocked
        res = sptr01_sim_default.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=qf)
        assert res.rejected is True, f"Expected block for {flag_name}"
        assert len(res.reject_reasons) >= 1

    def test_combo_stale_invalid(self, sptr01_order_buy, sptr01_sim_default, sptr01_ref_tick):
        from app.contracts import QualityFlags
        qf = QualityFlags(stale=True, invalid=True)
        res = sptr01_sim_default.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=qf)
        assert res.rejected is True
        assert PaperFillRejectReason.P2_QUALITY_STALE.value in res.reject_reasons
        assert PaperFillRejectReason.P2_QUALITY_INVALID.value in res.reject_reasons

    def test_combo_dup_quarantine(self, sptr01_order_buy, sptr01_sim_default, sptr01_ref_tick):
        from app.contracts import QualityFlags
        qf = QualityFlags(duplicate=True, quarantined=True, out_of_order=True)
        res = sptr01_sim_default.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=qf)
        assert res.rejected is True
        assert len([r for r in res.reject_reasons if r.startswith("P2_QUALITY_")]) >= 3
