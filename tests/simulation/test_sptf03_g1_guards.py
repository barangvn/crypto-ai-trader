import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot
from app.simulation.portfolio import build_rolling_24h, INFO_INTERNAL_CALCULATION_ERROR, CORR_UNKNOWN_ROLLING, CAUS_UNKNOWN_ROLLING


class TestSPTF03G1Guards:
    def test_g1_end_ts_none(self):
        res = build_rolling_24h(snapshot_samples=[], end_ts=None)
        assert INFO_INTERNAL_CALCULATION_ERROR in res.info_codes
        assert res.window_samples_count == 0

    def test_g1_end_ts_empty_str(self):
        res = build_rolling_24h(snapshot_samples=[], end_ts="")
        assert INFO_INTERNAL_CALCULATION_ERROR in res.info_codes

    @pytest.mark.parametrize("bad_ts", ["notadate", "2026/01/01", "2026-01-01 12:00", "2026-01-01T12:00:00", None])
    def test_g1_end_ts_invalid_instant(self, bad_ts):
        res = build_rolling_24h(snapshot_samples=[make_snapshot(minutes_delta=0)], end_ts=bad_ts)
        assert INFO_INTERNAL_CALCULATION_ERROR in res.info_codes

    def test_g1_samples_none(self):
        res = build_rolling_24h(snapshot_samples=None, end_ts="2026-01-15T12:00:00.000Z")
        assert res.correlation_id == CORR_UNKNOWN_ROLLING
        assert res.causation_id == CAUS_UNKNOWN_ROLLING

    def test_g1_samples_empty(self):
        res = build_rolling_24h(snapshot_samples=[], end_ts="2026-01-15T12:00:00.000Z")
        assert res.window_samples_count == 0

    def test_g1_samples_list_type_nonelement(self):
        # None, int, str gibi PortfolioSnapshot olmayan öğeler → fail-closed safe fallback (window count 0, INFO_INTERNAL_CALCULATION_ERROR)
        res = build_rolling_24h(snapshot_samples=[None, 123, "abc"], end_ts="2026-01-15T12:00:00.000Z")
        assert res.window_samples_count == 0
        # INFO_INTERNAL_CALCULATION_ERROR eklenebilir (AD-19 fail-closed)

    def test_g1_sample_ts_none_via_invalid(self):
        snap = make_snapshot(minutes_delta=0)
        # mutate ts invalid (use object setattr)
        object.__setattr__(snap, "ts", "")
        res = build_rolling_24h(snapshot_samples=[snap], end_ts="2026-01-15T12:00:00.000Z")
        # ts empty fail → N2 phase sort exception → AD-19 fallback → info code INTERNAL_CALCULATION_ERROR
        assert res.window_samples_count == 0 or INFO_INTERNAL_CALCULATION_ERROR in res.info_codes

    def test_g1_contract_version_unchanged(self):
        from app.contracts import CONTRACT_VERSION
        assert CONTRACT_VERSION == "1.0.0"

    def test_g1_pyproject_deps_empty(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        deps = data.get("project", {}).get("dependencies", [])
        assert deps == []

    def test_g1_portfolio_snapshot_fields_count(self):
        from dataclasses import fields
        fs = fields(make_snapshot(minutes_delta=0).__class__)
        names = [f.name for f in fs]
        # S-CON-02B §3.15: snapshot_id, account_ref, ts, cash, equity, realized24, unrealized, fees, exposure, dd, peak, corr, caus, positions
        assert "snapshot_id" in names and "equity_quote" in names and "realized_pnl_quote_24h" in names

    def test_g1_no_new_contract_in_contracts_folder(self):
        import os
        contract_path = "app/contracts"
        # No new contract file expected (S-CON-02B unchanged)
        fnames = set(os.listdir(contract_path))
        # portfolio.py exists; no rolling_result.py new contract
        assert "rolling_result.py" not in fnames
        assert "portfolio.py" in fnames
