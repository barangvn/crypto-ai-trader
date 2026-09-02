from __future__ import annotations

import pytest

from app.backtest.ordering import (
    DETERMINISTIC_EVENT_STAGE_ORDER,
    DeterministicEventOrderViolation,
    LookAheadLeakageError,
    ReplayClock,
    assert_no_look_ahead,
    deterministic_event_sort_key,
    deterministic_sort_events,
    stage_for_event,
    verify_event_ordering_strict,
)


class TestEventStageOrder:
    def test_eleven_stages(self):
        assert len(DETERMINISTIC_EVENT_STAGE_ORDER) == 11

    def test_expected_ordering(self):
        expected = [
            "MARKET", "FEATURE", "REGIME", "STRATEGY", "OPPORTUNITY",
            "RISK", "GATE", "FILL", "POSITION", "PORTFOLIO", "PERFORMANCE",
        ]
        assert tuple(expected) == DETERMINISTIC_EVENT_STAGE_ORDER

    @pytest.mark.parametrize("stage,rank", [
        ("MARKET", 0),
        ("FEATURE", 1),
        ("REGIME", 2),
        ("STRATEGY", 3),
        ("OPPORTUNITY", 4),
        ("RISK", 5),
        ("GATE", 6),
        ("FILL", 7),
        ("POSITION", 8),
        ("PORTFOLIO", 9),
        ("PERFORMANCE", 10),
    ])
    def test_rank(self, stage, rank):
        idx = list(DETERMINISTIC_EVENT_STAGE_ORDER).index(stage)
        assert idx == rank


class TestStageForEvent:
    def test_stage_for_candle(self, sbkt_small_bundle):
        for c in sbkt_small_bundle.iter_events():
            assert stage_for_event(c) == "MARKET"
            break

    def test_stage_for_markettick(self):
        from tests.backtest.conftest import _make_qflags
        from app.contracts import MarketTick
        from decimal import Decimal
        tick = MarketTick(
            price=Decimal("1"),
            market_ts="2025-01-01T00:00:00.000Z",
        )
        tick.tick_id = "T-001"
        tick.event_ts = "2025-01-01T00:00:00.000Z"
        tick.symbol = "BTC_USDT"
        tick.last_size = Decimal("1")
        tick.quality_flags = _make_qflags(valid=True)
        assert stage_for_event(tick) == "MARKET"

    def test_stage_for_feature_vector(self):
        from app.contracts.feature import FeatureVector, LookbackWindowSpec
        fv = FeatureVector(
            feature_version="feat_v1.0.0",
            timeframe="1m",
            features={},
            lookback_window=LookbackWindowSpec(count=20, timeframe="1m"),
            input_refs=[],
        )
        fv.feature_id = "F-001"
        fv.event_ts = "2025-01-01T00:00:00.000Z"
        fv.symbol = "BTC_USDT"
        assert stage_for_event(fv) == "FEATURE"

    def test_stage_for_strategy_signal(self):
        from app.contracts import StrategySignal, SignalDirection
        ss = StrategySignal(
            strategy_id="str_tf_v1",
            strategy_version="1.0.0",
            direction=SignalDirection.FLAT,
            signal_strength=0.0,
            correlation_id="U" + "a" * 20,
            causation_id="U" + "b" * 20,
        )
        ss.signal_id = "S-001"
        ss.event_ts = "2025-01-01T00:00:00.000Z"
        ss.symbol = "BTC_USDT"
        assert stage_for_event(ss) == "STRATEGY"

    def test_stage_for_risk_decision(self):
        from app.contracts.risk import (
            RiskDecision,
            RiskDecisionResult,
            PositionSizingSpec,
            LimitsSnapshot,
            KillSwitchStateSpec,
        )
        from decimal import Decimal
        rd = RiskDecision(
            decision_id="U" + "c" * 20,
            decision=RiskDecisionResult.APPROVED,
            reason_codes=[],
            position_sizing=PositionSizingSpec(
                base_qty=Decimal("0.1"),
                quote_qty=Decimal("4200"),
                notional=Decimal("4200"),
                method="notional",
            ),
            limits_snapshot=LimitsSnapshot(
                max_position_notional_per_symbol=Decimal("1000000"),
                max_exposure_notional_total=Decimal("1000000"),
                max_daily_loss_notional=Decimal("100000"),
                max_drawdown_pct=0.10,
                max_consecutive_losses=100,
                max_leverage_allowed=1,
                current_exposure_notional=Decimal("0"),
                current_daily_pnl=Decimal("0"),
                current_drawdown_pct=0.0,
                current_consecutive_losses=0,
            ),
            kill_switch_state=KillSwitchStateSpec(
                global_kill=False,
            ),
            valid_until="2099-01-01T00:00:00.000Z",
            correlation_id="U" + "d" * 20,
            causation_id="U" + "e" * 20,
        )
        rd.event_ts = "2025-01-01T00:00:00.000Z"
        rd.symbol = "BTC_USDT"
        assert stage_for_event(rd) == "RISK"

    def test_stage_for_position(self):
        from app.contracts import Position, PositionSide, ULID
        from decimal import Decimal
        p = Position(
            position_id=ULID("U" + "f" * 20),
            symbol="BTC_USDT",
            side=PositionSide.LONG,
            base_qty=Decimal("0.1"),
            avg_entry_price=Decimal("42000"),
            current_price=Decimal("42100"),
            unrealized_pnl_quote=Decimal("10"),
            realized_pnl_quote=Decimal("0"),
            fees_quote=Decimal("4.2"),
            opened_ts="2025-01-01T00:00:00.000Z",
            last_updated_ts="2025-01-01T00:00:00.000Z",
            open_refs=[],
            correlation_id=ULID("U" + "g" * 20),
            causation_id=ULID("U" + "h" * 20),
        )
        p.event_ts = "2025-01-01T00:00:00.000Z"
        assert stage_for_event(p) == "POSITION"

    def test_stage_for_portfolio_snapshot(self):
        from app.contracts import PortfolioSnapshot, ULID
        from decimal import Decimal
        ps = PortfolioSnapshot(
            snapshot_id=ULID("U" + "i" * 20),
            account_ref="paper-main",
            ts="2025-01-01T00:00:00.000Z",
            cash_quote=Decimal("0"),
            equity_quote=Decimal("0"),
            realized_pnl_quote_24h=Decimal("0"),
            unrealized_pnl_quote=Decimal("0"),
            fees_quote_total=Decimal("0"),
            exposure_notional=Decimal("0"),
            drawdown_pct=0.0,
            peak_equity_quote=Decimal("0"),
            correlation_id=ULID("U" + "j" * 20),
            causation_id=ULID("U" + "k" * 20),
        )
        ps.event_ts = "2025-01-01T00:00:00.000Z"
        assert stage_for_event(ps) == "PORTFOLIO"


class TestDeterministicSort:
    def test_sort_key_is_tuple_of_5(self, sbkt_small_bundle):
        evts = list(sbkt_small_bundle.iter_events())
        k = deterministic_event_sort_key(evts[0])
        assert isinstance(k, tuple)
        assert len(k) == 5

    def test_deterministic_sort_events_preserves_length(self, sbkt_small_bundle):
        evts = list(sbkt_small_bundle.iter_events())
        sorted_evts = deterministic_sort_events(evts)
        assert len(sorted_evts) == len(evts)

    def test_deterministic_sort_events_idempotent(self, sbkt_medium_bundle):
        evts = list(sbkt_medium_bundle.iter_events())
        s1 = deterministic_sort_events(evts)
        s2 = deterministic_sort_events(reversed(evts))
        ids_1 = [getattr(e, "candle_id", None) for e in s1]
        ids_2 = [getattr(e, "candle_id", None) for e in s2]
        assert ids_1 == ids_2

    def test_verify_ordering_strict_ok(self, sbkt_small_bundle):
        evts = list(sbkt_small_bundle.iter_events())
        s = deterministic_sort_events(evts)
        verify_event_ordering_strict(s)  # should not raise

    def test_verify_ordering_strict_bad_raises(self, sbkt_small_bundle):
        evts = list(sbkt_small_bundle.iter_events())
        s = deterministic_sort_events(evts)
        if len(s) >= 2:
            s[0], s[-1] = s[-1], s[0]
            with pytest.raises(DeterministicEventOrderViolation):
                verify_event_ordering_strict(s)


class TestReplayClock:
    def test_advance_ok(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:00:00.000Z")
        assert rc.advanced_count == 1
        assert rc.decision_ts == "2025-01-01T00:00:00.000Z"

    def test_advance_twice_monotonic(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:00:00.000Z")
        rc.advance("2025-01-01T00:00:01.000Z")
        assert rc.advanced_count == 2

    def test_advance_nonmonotonic_raises(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:10:00.000Z")
        with pytest.raises(LookAheadLeakageError):
            rc.advance("2025-01-01T00:00:00.000Z")

    def test_freeze_then_advance_raises(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:00:00.000Z")
        rc.frozen = True
        with pytest.raises(LookAheadLeakageError):
            rc.advance("2025-01-01T00:00:01.000Z")

    def test_invalid_instant_format_raises(self):
        rc = ReplayClock()
        with pytest.raises(Exception):
            rc.advance("not-a-date")

    def test_assert_instant_accessible_ok(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:10:00.000Z")
        rc.assert_instant_accessible("2025-01-01T00:10:00.000Z")  # OK equal

    def test_assert_instant_accessible_future_raises(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:10:00.000Z")
        with pytest.raises(LookAheadLeakageError):
            rc.assert_instant_accessible("2025-01-01T00:10:01.000Z")


class TestLookAheadGuards:
    def test_assert_no_look_ahead_equal_ok(self):
        ts = "2025-01-01T00:10:00.000Z"
        assert_no_look_ahead(ts, ts)  # OK equal

    def test_assert_no_look_ahead_past_ok(self):
        assert_no_look_ahead("2025-01-01T00:10:00.000Z", "2025-01-01T00:09:59.999Z")  # OK

    def test_assert_no_look_ahead_future_raises(self):
        with pytest.raises(LookAheadLeakageError):
            assert_no_look_ahead("2025-01-01T00:10:00.000Z", "2025-01-01T00:10:00.001Z")

    def test_assert_no_look_ahead_missing_ts_raises(self):
        with pytest.raises(Exception):
            assert_no_look_ahead(None, "2025-01-01T00:10:00.000Z")

    def test_assert_with_clock_future(self):
        rc = ReplayClock()
        rc.advance("2025-01-01T00:00:00.000Z")
        with pytest.raises(LookAheadLeakageError):
            assert_no_look_ahead("2025-01-01T00:10:00.000Z", "2025-01-01T00:09:00.000Z", clock=rc)
