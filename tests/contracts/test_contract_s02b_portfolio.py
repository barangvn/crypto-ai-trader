"""S-CON-02B Position + PortfolioSnapshot — 16+ contract tests.

Story coverage: C-25 .. C-34 Acceptance Criteria.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts import (
    ContractSchemaError,
    PortfolioSnapshot,
    Position,
    PositionSide,
    format_instant,
)


# ---------------------------------------------------------------------------
# Test helpers — valid Position + PortfolioSnapshot factories with overrides
# ---------------------------------------------------------------------------


def _make_valid_position(**overrides) -> Position:
    now = format_instant()
    fields: dict = dict(
        position_id="01J5POSID1234567890ABCDEF1",
        symbol="BTC_USDT",
        side=PositionSide.LONG,
        base_qty=Decimal("0.5"),
        avg_entry_price=Decimal("48000"),
        current_price=Decimal("50000"),
        unrealized_pnl_quote=Decimal("1000"),
        realized_pnl_quote=Decimal("0"),
        fees_quote=Decimal("24"),
        opened_ts=now,
        last_updated_ts=now,
        open_refs=["01J5OPENREF1234567890ABCDEF"],
        correlation_id="01J5CORREL0000000000000001",
        causation_id="01J5CORREL0000000000000001",
        stop_loss_ref=None,
        take_profit_ref=None,
    )
    fields.update(overrides)
    return Position(**fields)


def _make_valid_snapshot(**overrides) -> PortfolioSnapshot:
    now = format_instant()
    fields: dict = dict(
        snapshot_id="01J5SNAPID1234567890ABCDEF1",
        account_ref="paper_main",
        ts=now,
        cash_quote=Decimal("50000"),
        equity_quote=Decimal("100000"),
        realized_pnl_quote_24h=Decimal("500"),
        unrealized_pnl_quote=Decimal("1000"),
        fees_quote_total=Decimal("124"),
        exposure_notional=Decimal("50000"),
        drawdown_pct=0.05,
        peak_equity_quote=Decimal("105263.15789"),
        correlation_id="01J5CORREL0000000000000001",
        causation_id="01J5CORREL0000000000000001",
        positions_snapshot=[_make_valid_position()],
    )
    fields.update(overrides)
    return PortfolioSnapshot(**fields)


# ===========================================================================
# POSITION TESTS (C-25 .. C-29 + determinism + open_refs)
# ===========================================================================


@pytest.mark.contract
def test_c25_position_side_short_string_raises_contract_schema_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_position(side="short")
    assert "short" in str(exc_info.value).lower()
    assert not isinstance(exc_info.value, ValueError) or type(exc_info.value) is ContractSchemaError


@pytest.mark.contract
def test_c26_position_flat_side_with_nonzero_base_qty_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_position(
            side=PositionSide.FLAT,
            base_qty=Decimal("1.5"),
        )
    assert "flat" in str(exc_info.value).lower()
    assert "0" in str(exc_info.value)


@pytest.mark.contract
def test_c26b_position_flat_side_with_zero_base_qty_ok() -> None:
    p = _make_valid_position(
        side=PositionSide.FLAT,
        base_qty=Decimal("0"),
        unrealized_pnl_quote=Decimal("0"),
        avg_entry_price=Decimal("0"),
    )
    assert p.side == PositionSide.FLAT
    assert p.base_qty == Decimal("0")


@pytest.mark.contract
def test_c27_position_negative_base_qty_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_position(base_qty=Decimal("-0.001"))
    assert "base_qty" in str(exc_info.value)
    assert ">= 0" in str(exc_info.value) or "negative" in str(exc_info.value).lower()


@pytest.mark.contract
def test_c28_position_negative_fees_quote_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_position(fees_quote=Decimal("-1"))
    assert "fees_quote" in str(exc_info.value)
    assert ">= 0" in str(exc_info.value)


@pytest.mark.contract
def test_c29_position_symbol_missing_or_empty_raises_error() -> None:
    with pytest.raises((TypeError, ContractSchemaError)):
        Position(
            position_id="01J5POSID1234567890ABCDEF1",
            side=PositionSide.LONG,
            base_qty=Decimal("0.5"),
            avg_entry_price=Decimal("48000"),
            current_price=Decimal("50000"),
            unrealized_pnl_quote=Decimal("1000"),
            realized_pnl_quote=Decimal("0"),
            fees_quote=Decimal("24"),
            opened_ts=format_instant(),
            last_updated_ts=format_instant(),
            open_refs=["01J5OPENREF1234567890ABCDEF"],
            correlation_id="01J5CORREL0000000000000001",
            causation_id="01J5CORREL0000000000000001",
        )

    with pytest.raises(ContractSchemaError):
        _make_valid_position(symbol="")


@pytest.mark.contract
def test_position_10x_schema_sha256_determinism() -> None:
    fixed_ts = "2026-08-15T12:00:00.000Z"
    p = Position(
        position_id="01J5POSID1234567890ABCDEF1",
        symbol="BTC_USDT",
        side=PositionSide.LONG,
        base_qty=Decimal("0.5"),
        avg_entry_price=Decimal("48000"),
        current_price=Decimal("50000"),
        unrealized_pnl_quote=Decimal("1000"),
        realized_pnl_quote=Decimal("0"),
        fees_quote=Decimal("24"),
        opened_ts=fixed_ts,
        last_updated_ts=fixed_ts,
        open_refs=["01J5OPENREF1234567890ABCDEF"],
        correlation_id="01J5CORREL0000000000000001",
        causation_id="01J5CORREL0000000000000001",
        stop_loss_ref=None,
        take_profit_ref=None,
    )
    digests = [p.schema_sha256() for _ in range(10)]
    first = digests[0]
    assert all(d == first for d in digests)
    assert len(first) == 64


@pytest.mark.contract
def test_position_open_refs_none_raises_error_empty_list_ok() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_position(open_refs=None)
    assert "open_refs" in str(exc_info.value)
    assert "None" in str(exc_info.value) or "list" in str(exc_info.value).lower()

    p_empty = _make_valid_position(open_refs=[])
    assert p_empty.open_refs == []


# ===========================================================================
# PORTFOLIO SNAPSHOT TESTS (C-30 .. C-34 + determinism + peak<equity)
# ===========================================================================


@pytest.mark.contract
def test_c30_snapshot_drawdown_pct_above_1_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_snapshot(drawdown_pct=1.5)
    assert "drawdown_pct" in str(exc_info.value)
    assert "[0, 1]" in str(exc_info.value) or "range" in str(exc_info.value).lower()


@pytest.mark.contract
def test_c30b_snapshot_drawdown_pct_boundary_checks() -> None:
    with pytest.raises(ContractSchemaError):
        _make_valid_snapshot(drawdown_pct=-0.01)

    s0 = _make_valid_snapshot(drawdown_pct=0.0)
    assert s0.drawdown_pct == 0.0

    s1 = _make_valid_snapshot(drawdown_pct=1.0)
    assert s1.drawdown_pct == 1.0


@pytest.mark.contract
def test_c31_snapshot_negative_exposure_notional_raises_error() -> None:
    with pytest.raises(ContractSchemaError) as exc_info:
        _make_valid_snapshot(exposure_notional=Decimal("-100"))
    assert "exposure_notional" in str(exc_info.value)
    assert ">= 0" in str(exc_info.value)


@pytest.mark.contract
def test_c32_snapshot_missing_equity_quote_raises_type_error() -> None:
    with pytest.raises(TypeError):
        PortfolioSnapshot(
            snapshot_id="01J5SNAPID1234567890ABCDEF1",
            account_ref="paper_main",
            ts=format_instant(),
            cash_quote=Decimal("50000"),
            realized_pnl_quote_24h=Decimal("500"),
            unrealized_pnl_quote=Decimal("1000"),
            fees_quote_total=Decimal("124"),
            exposure_notional=Decimal("50000"),
            drawdown_pct=0.05,
            peak_equity_quote=Decimal("105263.15789"),
            correlation_id="01J5CORREL0000000000000001",
            causation_id="01J5CORREL0000000000000001",
            positions_snapshot=None,
        )


@pytest.mark.contract
def test_c33_snapshot_peak_less_than_equity_no_contract_error_math_assert() -> None:
    peak = Decimal("80000")
    equity = Decimal("100000")
    s = _make_valid_snapshot(
        peak_equity_quote=peak,
        equity_quote=equity,
        drawdown_pct=0.0,
    )
    assert s.peak_equity_quote == peak
    assert s.equity_quote == equity

    if peak > Decimal("0"):
        implied_drawdown = float((peak - equity) / peak)
        if implied_drawdown >= 0:
            assert s.drawdown_pct >= 0.0
            assert s.drawdown_pct <= 1.0


@pytest.mark.contract
def test_c34_snapshot_three_positions_to_sorted_dict_sorted_keys_nested() -> None:
    p1 = _make_valid_position(position_id="01J5POSA1234567890ABCDEF1", symbol="BTC_USDT")
    p2 = _make_valid_position(position_id="01J5POSB1234567890ABCDEF2", symbol="ETH_USDT")
    p3 = _make_valid_position(position_id="01J5POSC1234567890ABCDEF3", symbol="SOL_USDT")
    s = _make_valid_snapshot(positions_snapshot=[p1, p2, p3])

    d = s.to_sorted_dict()
    top_keys = list(d.keys())
    assert top_keys == sorted(top_keys)

    pos_list = d["positions_snapshot"]
    assert isinstance(pos_list, list)
    assert len(pos_list) == 3

    for pos_dict in pos_list:
        inner_keys = list(pos_dict.keys())
        assert inner_keys == sorted(inner_keys)


@pytest.mark.contract
def test_portfolio_snapshot_10x_schema_sha256_determinism() -> None:
    fixed_ts = "2026-08-15T12:00:00.000Z"
    p = Position(
        position_id="01J5POSID1234567890ABCDEF1",
        symbol="BTC_USDT",
        side=PositionSide.LONG,
        base_qty=Decimal("0.5"),
        avg_entry_price=Decimal("48000"),
        current_price=Decimal("50000"),
        unrealized_pnl_quote=Decimal("1000"),
        realized_pnl_quote=Decimal("0"),
        fees_quote=Decimal("24"),
        opened_ts=fixed_ts,
        last_updated_ts=fixed_ts,
        open_refs=["01J5OPENREF1234567890ABCDEF"],
        correlation_id="01J5CORREL0000000000000001",
        causation_id="01J5CORREL0000000000000001",
        stop_loss_ref=None,
        take_profit_ref=None,
    )
    s = PortfolioSnapshot(
        snapshot_id="01J5SNAPID1234567890ABCDEF1",
        account_ref="paper_main",
        ts=fixed_ts,
        cash_quote=Decimal("50000"),
        equity_quote=Decimal("100000"),
        realized_pnl_quote_24h=Decimal("500"),
        unrealized_pnl_quote=Decimal("1000"),
        fees_quote_total=Decimal("124"),
        exposure_notional=Decimal("50000"),
        drawdown_pct=0.05,
        peak_equity_quote=Decimal("105263.15789"),
        correlation_id="01J5CORREL0000000000000001",
        causation_id="01J5CORREL0000000000000001",
        positions_snapshot=[p],
    )
    digests = [s.schema_sha256() for _ in range(10)]
    first = digests[0]
    assert all(d == first for d in digests)
    assert len(first) == 64


@pytest.mark.contract
def test_snapshot_peak_less_than_equity_no_schema_raise() -> None:
    s = _make_valid_snapshot(
        peak_equity_quote=Decimal("1000"),
        equity_quote=Decimal("1500"),
        drawdown_pct=0.0,
    )
    assert s.peak_equity_quote == Decimal("1000")
    assert s.equity_quote == Decimal("1500")
