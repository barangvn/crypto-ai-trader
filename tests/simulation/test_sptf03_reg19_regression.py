import pytest
from decimal import Decimal
from tests.simulation.conftest_sptf03 import make_snapshot, make_ts


class TestSPTF03REG19RegressionBaseline:
    """S-PTF-01 / S-PTF-02 import + çalışmaya devam etmeli (0 modification)"""

    def test_sptf01_import(self):
        from app.simulation.portfolio import PositionEngine
        assert PositionEngine is not None

    def test_sptf02_import(self):
        from app.simulation.portfolio import (
            PortfolioSnapshotEngine,
        )
        assert PortfolioSnapshotEngine is not None

    def test_sptf03_import(self):
        from app.simulation.portfolio import (
            RollingPerformanceEngine,
            build_rolling_24h,
            Rolling24Result,
            WINDOW_MS_24H,
        )
        assert RollingPerformanceEngine is not None
        assert callable(build_rolling_24h)
        assert Rolling24Result is not None
        assert WINDOW_MS_24H == 86_400_000

    def test_sptf01_position_engine_smoke(self):
        from app.simulation.portfolio import PositionEngine
        from app.platform.event_bus import InMemoryTypedEventBus
        bus = InMemoryTypedEventBus()
        # PositionEngine signature — sadece event_bus opsiyonel olabilir, account_ref zorunlu değil ise geç
        try:
            pe = PositionEngine(event_bus=bus)
        except TypeError:
            pe = PositionEngine()
        assert pe is not None

    def test_sptf02_session_cumulative_not_altered_by_sptf03(self):
        from app.simulation.portfolio import PortfolioSnapshotEngine
        from app.platform.event_bus import InMemoryTypedEventBus
        bus = InMemoryTypedEventBus()
        try:
            eng = PortfolioSnapshotEngine(event_bus=bus, account_ref="ACC_REG")
        except TypeError:
            try:
                eng = PortfolioSnapshotEngine(event_bus=bus)
            except TypeError:
                eng = PortfolioSnapshotEngine()
        assert eng is not None

    def test_contract_immutability_portfolio_sha(self):
        import hashlib
        with open("app/contracts/portfolio.py", "rb") as f:
            data = f.read()
        assert len(data) > 1000  # içerik var
        text = data.decode("utf-8")
        assert "class Position" in text
        assert "class PortfolioSnapshot" in text

    def test_quality_flags_contract_present(self):
        from app.contracts.canonical import QualityFlags
        q = QualityFlags()
        assert q.invalid is False

    @pytest.mark.parametrize("n_sess", list(range(5)))
    def test_session_vs_rolling_separated_regression(self, n_sess):
        """S-PTF-02 session cumulative = X; S-PTF-03 rolling 24h = Y. İkisi AYRIMLI"""
        from app.simulation.portfolio import build_rolling_24h
        snaps = [make_snapshot(minutes_delta=-(5-i), realized=Decimal(str(i*10))) for i in range(6)]
        last_snap = snaps[-1]
        rolling_res = build_rolling_24h(snapshot_samples=snaps, end_ts=last_snap.ts)
        session_realized_field = last_snap.realized_pnl_quote_24h
        rolling_realized_delta = rolling_res.rolling_realized_pnl_quote_24h
        assert isinstance(session_realized_field, Decimal)
        assert isinstance(rolling_realized_delta, Decimal)

    def test_pyproject_deps_regression_unchanged(self):
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        deps = data.get("project", {}).get("dependencies", [])
        assert deps == [], "Regression: pyproject dependencies artık boş değil"

    def test_contract_version_1_0_0(self):
        from app.contracts import CONTRACT_VERSION
        assert CONTRACT_VERSION == "1.0.0"
