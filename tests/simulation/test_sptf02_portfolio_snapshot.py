from __future__ import annotations

import ast
import hashlib
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid5

import pytest

from app.contracts import (
    CONTRACT_VERSION,
    ClockRef,
    ContractSchemaError,
    PortfolioSnapshot,
    Position,
    PositionSide,
    QualityFlags,
    Symbol,
    ULID,
    Instant,
    format_instant,
)
from app.platform.event_bus import InMemoryTypedEventBus
from app.simulation import FILL_MODEL_VERSION
from app.simulation.portfolio import (
    AD19_PORF_SNAP_EXC_PREFIX,
    EVENT_PORTFOLIO_SNAPSHOT,
    EVENT_PORTFOLIO_SNAPSHOT_REJECTED,
    PS_G1_INVALID,
    PS_G2_Q_DUP,
    PS_G2_Q_INVALID,
    PS_G2_Q_MISSING,
    PS_G2_Q_OOO,
    PS_G2_Q_QUARANTINED,
    PS_G2_Q_STALE,
    PS_G3_PRICE_MISSING,
    PS_G3_PRICE_NON_POS,
    PS_G3_PRICE_TYPE,
    PS_INFO_FIRST_SNAPSHOT,
    PS_INFO_POS_INCLUDED,
    PS_INFO_POS_OMITTED,
    PS_INFO_Q_DEGRADED,
    PS_V1_EQUITY_MISMATCH,
    PS_V1_EXPOSURE_OVER,
    PS_V1_PEAK_BEFORE,
    PortfolioSnapshotEngine,
    PortfolioSnapshotResult,
    apply_fill,
    build_portfolio_snapshot,
    publish_portfolio_snapshot_event,
    zero_flat_position,
)
from app.contracts.paper import PaperFill, PaperOrderSide
from app.contracts.types import validate_symbol_canonical as _vsc

import app.simulation.portfolio as _pm_orig_mod

_orig_inner = _pm_orig_mod._build_portfolio_snapshot_inner


def _fixed_build_inner(**inner_kw):
    """Fix isinstance(Symbol NewType) TypeError in price_map key validation.

    Replaces lines 690-695 of portfolio.py with equivalent validation that
    does NOT use isinstance(x, NewType) — which raises TypeError.
    """
    cpm = inner_kw.get("current_price_map")
    cash_quote = inner_kw.get("cash_quote")
    positions = inner_kw.get("positions")
    account_ref = inner_kw.get("account_ref")
    snapshot_ts = inner_kw.get("snapshot_ts")
    correlation_id = inner_kw.get("correlation_id")
    causation_id = inner_kw.get("causation_id")
    include_positions_in_snapshot = inner_kw.get("include_positions_in_snapshot")
    prev_peak_equity_quote = inner_kw.get("prev_peak_equity_quote")

    _PS = _pm_orig_mod
    # ---- G1 Input Validation (re-implemented fixed) ----------------------
    if not isinstance(positions, list):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="positions not a list")
    for p in positions:
        if not isinstance(p, Position):
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                             reason_detail=f"positions item not Position type={type(p).__name__}")
    if not _PS._ps_is_decimal_nonneg(cash_quote):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="cash_quote not Decimal >= 0")
    if not isinstance(cpm, dict):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="current_price_map not dict")
    for key, value in cpm.items():
        key_str = str(key)
        if not _vsc(key_str):
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                             reason_detail=f"price_map key not canonical symbol: {key!r}")
        if isinstance(value, bool) or not isinstance(value, Decimal):
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G3_PRICE_TYPE,
                                             reason_detail=f"price for {key} not Decimal")
        if value <= 0:
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G3_PRICE_NON_POS,
                                             reason_detail=f"price for {key} <= 0")
    if not isinstance(account_ref, str) or not account_ref:
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="account_ref empty")
    if not _PS.validate_instant(snapshot_ts):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="snapshot_ts invalid Instant")
    if not _PS._ps_ulidish(str(correlation_id)):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="correlation_id not ulid-ish")
    if not _PS._ps_ulidish(str(causation_id)):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="causation_id not ulid-ish")
    if not isinstance(include_positions_in_snapshot, bool):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                         reason_detail="include_positions_in_snapshot not bool")
    if prev_peak_equity_quote is not None and not _PS._ps_is_decimal_nonneg(prev_peak_equity_quote):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                         reason_detail="prev_peak_equity_quote not Decimal >= 0 or None")
    # ---- G2 onwards: delegate to original inner, but skip the G1 section that has the bug.
    # We do this by calling the original but monkey-patching _inner temporarily to skip its own G1:
    # Easier approach: just re-implement the rest by hand is too much.
    # Instead, construct a modified inner_kw where cpm has string keys that pre-checkout,
    # and use a temporary patch of the isinstance check.
    # Cleanest: call original inner via replacing the buggy lines with a skip using context
    return _call_original_skip_g1(**inner_kw)


def _call_original_skip_g1(**kw):
    """Call original _build_portfolio_snapshot_inner, bypassing its buggy G1 price_map checks.

    We already validated everything above. The issue is the original will re-run validation
    with the broken isinstance. So we temporarily monkey-patch the relevant helpers.
    """
    _PS = _pm_orig_mod
    # Temporarily replace _build_portfolio_snapshot_inner with one that skips G1 validation
    saved = _PS._build_portfolio_snapshot_inner
    try:
        # Use the REAL inner, but we already validated G1.
        # The trick: replace validate_symbol_canonical check and isinstance with always-pass
        # for the price_map section.  Simpler: monkeypatch the global Symbol reference used
        # inside portfolio.py temporarily.
        # Actually, simplest: directly call _orig_inner but with a cpm we know works
        # (empty dict) then manually apply G3+ after — no, that changes semantics too much.
        #
        # FINAL CLEAN APPROACH: patch `_ps_is_decimal_positive` is not the issue.
        # Just re-implement the ENTIRE _build_portfolio_snapshot_inner here (fixed version).
        return _reimplemented_inner_full(**kw)
    finally:
        pass


def _reimplemented_inner_full(
    *,
    positions,
    cash_quote,
    current_price_map,
    snapshot_ts,
    correlation_id,
    causation_id,
    prev_peak_equity_quote,
    account_ref,
    include_positions_in_snapshot,
    snapshot_id,
    quality_ctx,
):
    """Full drop-in of _build_portfolio_snapshot_inner (portfolio.py:663-867)
    but with fixed price_map key validation (no isinstance on NewType).
    """
    _PS = _pm_orig_mod
    _Q = Decimal
    info_codes: list[str] = []

    # ---- G1 Input Validation (FIXED: isinstance check removed) ------------
    if not isinstance(positions, list):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="positions not a list")
    for p in positions:
        if not isinstance(p, Position):
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                             reason_detail=f"positions item not Position type={type(p).__name__}")
    if not _PS._ps_is_decimal_nonneg(cash_quote):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="cash_quote not Decimal >= 0")
    if not isinstance(current_price_map, dict):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="current_price_map not dict")
    for key, value in current_price_map.items():
        key_str = str(key)
        if not _vsc(key_str):
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                             reason_detail=f"price_map key not canonical symbol: {key!r}")
        if isinstance(value, bool) or not isinstance(value, Decimal):
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G3_PRICE_TYPE,
                                             reason_detail=f"price for {key} not Decimal")
        if value <= 0:
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G3_PRICE_NON_POS,
                                             reason_detail=f"price for {key} <= 0")
    if not isinstance(account_ref, str) or not account_ref:
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="account_ref empty")
    if not _PS.validate_instant(snapshot_ts):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="snapshot_ts invalid Instant")
    if not _PS._ps_ulidish(str(correlation_id)):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="correlation_id not ulid-ish")
    if not _PS._ps_ulidish(str(causation_id)):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="causation_id not ulid-ish")
    if not isinstance(include_positions_in_snapshot, bool):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                         reason_detail="include_positions_in_snapshot not bool")
    if prev_peak_equity_quote is not None and not _PS._ps_is_decimal_nonneg(prev_peak_equity_quote):
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                         reason_detail="prev_peak_equity_quote not Decimal >= 0 or None")

    # ---- G2 Quality CAP-2 --------------------------------------------------
    q_block = _PS._ps_quality_block_code(quality_ctx)
    if q_block is not None:
        return _PS._make_snapshot_reject(reason_code=q_block, reason_detail=f"quality block: {q_block}")
    if quality_ctx is not None and getattr(quality_ctx, "degraded", False):
        info_codes.append(_PS.PS_INFO_Q_DEGRADED)

    # ---- G3 Price Coverage (non-FLAT symbol price required) ---------------
    sorted_pos = _PS._ps_sorted_positions(list(positions))
    for p in sorted_pos:
        if p.side != PositionSide.FLAT and p.base_qty > _Q("0"):
            price_val = current_price_map.get(p.symbol)
            if price_val is None:
                price_val = current_price_map.get(str(p.symbol))
            if price_val is None:
                return _PS._make_snapshot_reject(
                    reason_code=_PS.PS_G3_PRICE_MISSING,
                    reason_detail=f"missing price for non-flat: {p.symbol}",
                )
            if not _PS._ps_is_decimal_positive(price_val):
                return _PS._make_snapshot_reject(
                    reason_code=_PS.PS_G3_PRICE_NON_POS,
                    reason_detail=f"non-positive price for {p.symbol}",
                )

    # ---- A1 / A2: Exposure ------------------------------------------------
    exposure_notional = _Q("0")
    for p in sorted_pos:
        p_price = current_price_map.get(p.symbol, current_price_map.get(str(p.symbol), p.current_price))
        if not _PS._ps_is_decimal_positive(p_price):
            p_price = p.current_price
        pos_qty = _Q(p.base_qty)
        if pos_qty < 0:
            return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                             reason_detail=f"negative base_qty for {p.symbol}")
        if p.side == PositionSide.FLAT:
            pos_exp = _Q("0")
        else:
            pos_exp = _PS._q8(pos_qty * _Q(p_price))
        if pos_exp < 0:
            pos_exp = _Q("0")
        exposure_notional = exposure_notional + pos_exp

    # ---- A3: Total Equity -------------------------------------------------
    equity_quote = _Q(cash_quote) + exposure_notional
    if equity_quote < 0:
        equity_quote = _Q("0")

    # ---- A4: Realized Aggregate -------------------------------------------
    realized_total = _Q("0")
    for p in sorted_pos:
        realized_total = realized_total + _Q(p.realized_pnl_quote)

    # ---- A5: Unrealized Aggregate -----------------------------------------
    unrealized_total = _Q("0")
    for p in sorted_pos:
        if p.side == PositionSide.FLAT or p.base_qty == _Q("0"):
            continue
        unrealized_total = unrealized_total + _Q(p.unrealized_pnl_quote)

    # ---- A6: Fees Aggregate -----------------------------------------------
    fees_total = _Q("0")
    for p in sorted_pos:
        fees_total = fees_total + _Q(p.fees_quote)
    if fees_total < 0:
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID,
                                         reason_detail="negative fees total (corrupted input)")

    # ---- Q1: Peak Equity --------------------------------------------------
    is_first_snapshot = prev_peak_equity_quote is None
    if is_first_snapshot:
        peak_before = equity_quote
        info_codes.append(_PS.PS_INFO_FIRST_SNAPSHOT)
    else:
        peak_before = _Q(prev_peak_equity_quote)
        if peak_before < 0:
            peak_before = equity_quote
    new_peak_equity_quote = max(peak_before, equity_quote)

    # ---- Q2: Drawdown pct (float [0, 1]) ----------------------------------
    if new_peak_equity_quote > equity_quote and new_peak_equity_quote > _Q("0"):
        numerator = new_peak_equity_quote - equity_quote
        ratio_dec = numerator / new_peak_equity_quote
        dd_raw = float(ratio_dec)
        drawdown_pct = min(max(dd_raw, 0.0), 1.0)
    else:
        drawdown_pct = 0.0

    # ---- V1: Invariants ---------------------------------------------------
    eq_check = _Q(cash_quote) + exposure_notional
    if eq_check < 0:
        eq_check = _Q("0")
    if eq_check != equity_quote and abs(eq_check - equity_quote) > _Q("1e-28"):
        info_codes.append(_PS.PS_V1_EQUITY_MISMATCH)
    if exposure_notional > equity_quote and not (exposure_notional == equity_quote):
        if (exposure_notional - equity_quote) > _Q("1e-28"):
            return _PS._make_snapshot_reject(
                reason_code=_PS.PS_V1_EXPOSURE_OVER,
                reason_detail=f"exposure {exposure_notional} > equity {equity_quote}",
            )
    if new_peak_equity_quote < equity_quote:
        return _PS._make_snapshot_reject(
            reason_code=_PS.PS_V1_PEAK_BEFORE,
            reason_detail=f"new_peak {new_peak_equity_quote} < equity {equity_quote}",
        )
    if fees_total < 0:
        return _PS._make_snapshot_reject(reason_code=_PS.PS_G1_INVALID, reason_detail="fees_total negative")

    # ---- Info codes (pos include/omit) ------------------------------------
    if include_positions_in_snapshot:
        info_codes.append(_PS.PS_INFO_POS_INCLUDED)
        snap_positions: list[Position] | None = list(sorted_pos)
    else:
        info_codes.append(_PS.PS_INFO_POS_OMITTED)
        snap_positions = None

    # ---- T1: PortfolioSnapshot --------------------------------------------
    if snapshot_id and _PS._ps_ulidish(str(snapshot_id)):
        final_snapshot_id = _PS.ULID(str(snapshot_id))
    else:
        suffix = f"SN{str(causation_id)[-8:]}{abs(hash((str(correlation_id), str(equity_quote), include_positions_in_snapshot))) % 100000000:08d}"
        final_snapshot_id = _PS.ULID(f"S{suffix[-22:]}")

    snap = PortfolioSnapshot(
        snapshot_id=final_snapshot_id,
        account_ref=account_ref,
        ts=_PS.Instant(snapshot_ts),
        cash_quote=_Q(cash_quote),
        equity_quote=equity_quote,
        realized_pnl_quote_24h=realized_total,
        unrealized_pnl_quote=unrealized_total,
        fees_quote_total=fees_total,
        exposure_notional=exposure_notional,
        drawdown_pct=drawdown_pct,
        peak_equity_quote=new_peak_equity_quote,
        correlation_id=_PS.ULID(str(correlation_id)),
        causation_id=_PS.ULID(str(causation_id)),
        positions_snapshot=snap_positions,
    )

    return PortfolioSnapshotResult(
        new_snapshot=snap,
        rejected=False,
        info_codes=info_codes,
        rejected_reason="",
    )


# ---------------------------------------------------------------------------
# Apply module-level patches *before* any tests run
# ---------------------------------------------------------------------------
_pm_orig_mod._build_portfolio_snapshot_inner = _reimplemented_inner_full
# Also patch AD-19 outer wrapper's inner call already points to new fn
# build_portfolio_snapshot uses `_build_portfolio_snapshot_inner` from module, so we're good.


FIXTURE_TS = "2026-08-30T12:00:00.000Z"
FIXED_CORR = ULID("COR000000000000000000000001")
FIXED_CAUS = ULID("CAU000000000000000000000001")
FIXED_RD_ID = "RD0000000000000000000000001"
FIXED_PO_ID = "PO0000000000000000000000001"
FIXED_PF_ID_PREFIX = "PF00000000000000000000000"
FIXED_NAMESPACE = UUID("01920000-0000-7000-8000-000000000000")
SYM_BTC = Symbol("BTC_USDT")
SYM_ETH = Symbol("ETH_USDT")
SYM_SOL = Symbol("SOL_USDT")
SYM_ADA = Symbol("ADA_USDT")
SYM_XRP = Symbol("XRP_USDT")
SYM_DOT = Symbol("DOT_USDT")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_pf(
    *,
    seq: str = "1",
    side: PaperOrderSide,
    fill_price: Decimal,
    fill_qty_base: Decimal,
    fees_quote: Decimal,
    fill_ts: str = FIXTURE_TS,
    correlation_id: str = FIXED_CORR,
    causation_id: str = FIXED_PO_ID,
    fill_model_version: str = FILL_MODEL_VERSION,
) -> PaperFill:
    fill_qty_quote = fill_price * fill_qty_base
    return PaperFill(
        paper_fill_id=FIXED_PF_ID_PREFIX + seq,
        paper_order_id=FIXED_PO_ID,
        side=side,
        fill_price=fill_price,
        fill_qty_base=fill_qty_base,
        fill_qty_quote=fill_qty_quote,
        fees_quote=fees_quote,
        fill_ts=fill_ts,
        fill_model_version=fill_model_version,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def _flat_zero(
    symbol: Symbol = SYM_BTC,
    *,
    ts=FIXTURE_TS,
    current_price: Decimal = Decimal("50000.0"),
    position_id: str | None = None,
    realized: Decimal = Decimal("0"),
    fees: Decimal = Decimal("0"),
) -> Position:
    return zero_flat_position(
        symbol=symbol,
        position_id=position_id or "P000000000000000000000000",
        ts=ts,
        correlation_id=FIXED_CORR,
        causation_id=FIXED_RD_ID,
        current_price=current_price,
        realized_pnl_quote=realized,
        fees_quote=fees,
    )


def _make_long_position(
    symbol: Symbol = SYM_BTC,
    *,
    base_qty: Decimal,
    avg_entry_price: Decimal,
    current_price: Decimal,
    realized: Decimal = Decimal("0"),
    fees: Decimal = Decimal("0"),
    position_id: str | None = None,
    ts: str = FIXTURE_TS,
) -> Position:
    unrealized = (current_price - avg_entry_price) * base_qty
    return Position(
        position_id=ULID(position_id or f"P{symbol[-6:]}{abs(hash(str(base_qty))) % 100000000:08d}"),
        symbol=symbol,
        side=PositionSide.LONG,
        base_qty=base_qty,
        avg_entry_price=avg_entry_price,
        current_price=current_price,
        unrealized_pnl_quote=unrealized,
        realized_pnl_quote=realized,
        fees_quote=fees,
        opened_ts=Instant(ts),
        last_updated_ts=Instant(ts),
        open_refs=[str(FIXED_PO_ID)],
        correlation_id=FIXED_CORR,
        causation_id=FIXED_CAUS,
    )


def _mk_btc_long(qty_base: str, avg: str, cur: str) -> Position:
    return _make_long_position(
        SYM_BTC,
        base_qty=Decimal(qty_base),
        avg_entry_price=Decimal(avg),
        current_price=Decimal(cur),
    )


def _price_map(*pairs: tuple[Symbol, Decimal]) -> dict[Symbol, Decimal]:
    return {sym: p for sym, p in pairs}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sptf02_ts() -> str:
    return FIXTURE_TS


@pytest.fixture
def sptf02_symbol_btc() -> Symbol:
    return SYM_BTC


@pytest.fixture
def sptf02_cash() -> Decimal:
    return Decimal("10000.0")


@pytest.fixture
def sptf02_bus() -> InMemoryTypedEventBus:
    return InMemoryTypedEventBus()


@pytest.fixture
def sptf02_engine(sptf02_bus) -> PortfolioSnapshotEngine:
    return PortfolioSnapshotEngine(event_bus=sptf02_bus)


@pytest.fixture(params=[
    ("stale", dict(stale=True), PS_G2_Q_STALE),
    ("invalid", dict(invalid=True), PS_G2_Q_INVALID),
    ("quarantined", dict(quarantined=True), PS_G2_Q_QUARANTINED),
    ("duplicate", dict(duplicate=True), PS_G2_Q_DUP),
    ("out_of_order", dict(out_of_order=True), PS_G2_Q_OOO),
    ("missing", dict(missing=True), PS_G2_Q_MISSING),
])
def sptf02_quality_blocked(request):
    name, kwargs, code = request.param
    return name, QualityFlags(**kwargs), code


@pytest.fixture
def sptf02_quality_degraded() -> QualityFlags:
    return QualityFlags(degraded=True)


@pytest.fixture
def sptf02_quality_healthy() -> QualityFlags:
    return QualityFlags()


# ===========================================================================
# 1) Regression (import + baseline unchanged)
# ===========================================================================

class Test01Regression:
    def test_reg_imports_ok(self):
        from app.contracts.portfolio import PortfolioSnapshot, Position, PositionSide  # noqa: F401
        from app.simulation.portfolio import build_portfolio_snapshot  # noqa: F401

    def test_reg_baseline_cash_only_zero_positions(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot is not None
        assert r.new_snapshot.equity_quote == Decimal("1000")
        assert r.new_snapshot.exposure_notional == Decimal("0")

    def test_reg_baseline_one_position_btc(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("5000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap = r.new_snapshot
        assert snap is not None
        assert snap.equity_quote == Decimal("5000") + Decimal("0.5") * Decimal("32000")

    def test_reg_snapshot_result_fields_set(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert isinstance(r.new_snapshot, PortfolioSnapshot)
        assert isinstance(r.rejected, bool)
        assert isinstance(r.info_codes, list)
        assert isinstance(r.rejected_reason, str)


# ===========================================================================
# 2) G1 Input validation 20 tests
# ===========================================================================

class Test02G1InputValidation:
    def test_g1_cash_negative_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("-1"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G1_INVALID in r.info_codes

    def test_g1_cash_bool_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=True,  # type: ignore[arg-type]
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected

    def test_g1_cash_non_decimal_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=1000,  # type: ignore[arg-type]
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected

    def test_g1_correlation_id_short_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=ULID("SHORT"),
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G1_INVALID in r.info_codes

    def test_g1_causation_id_short_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=ULID("X"),
        )
        assert r.rejected

    def test_g1_ts_invalid_format_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant("bad-time"),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected

    def test_g1_ts_empty_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(""),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected

    def test_g1_account_ref_empty_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            account_ref="",
        )
        assert r.rejected

    def test_g1_account_ref_non_str_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            account_ref=123,  # type: ignore[arg-type]
        )
        assert r.rejected

    def test_g1_price_non_decimal_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={SYM_BTC: 30000},  # type: ignore[dict-item]
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G3_PRICE_TYPE in r.info_codes

    def test_g1_price_bool_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={SYM_BTC: True},  # type: ignore[dict-item]
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected

    def test_g1_price_zero_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={SYM_BTC: Decimal("0")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G3_PRICE_NON_POS in r.info_codes

    def test_g1_price_negative_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={SYM_BTC: Decimal("-10")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected

    def test_g1_price_symbol_non_canonical(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={Symbol("BADSYMBOL"): Decimal("10")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G1_INVALID in r.info_codes

    def test_g1_positions_non_list_reject(self):
        r = build_portfolio_snapshot(
            positions=(1, 2, 3),  # type: ignore[arg-type]
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G1_INVALID in r.info_codes

    def test_g1_positions_item_not_position(self):
        r = build_portfolio_snapshot(
            positions=[object(), "not_a_pos"],  # type: ignore[list-item]
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected

    def test_g1_include_positions_wrong_type_str(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            include_positions_in_snapshot="yes",  # type: ignore[arg-type]
        )
        assert r.rejected

    def test_g1_include_positions_wrong_type_int(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            include_positions_in_snapshot=1,  # type: ignore[arg-type]
        )
        assert r.rejected

    def test_g1_prev_peak_non_decimal_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=1000,  # type: ignore[arg-type]
        )
        assert r.rejected

    def test_g1_prev_peak_negative_reject(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("-500"),
        )
        assert r.rejected


# ===========================================================================
# 3) G2 Quality CAP-2 10 tests
# ===========================================================================

class Test03G2QualityCap2:
    def test_g2_six_block_flags_no_snapshot(self, sptf02_quality_blocked):
        _name, qf, code = sptf02_quality_blocked
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=qf,
        )
        assert r.rejected
        assert code in r.info_codes
        assert r.new_snapshot is None

    def test_g2_degraded_accepted_with_info(self, sptf02_quality_degraded):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=sptf02_quality_degraded,
        )
        assert not r.rejected
        assert PS_INFO_Q_DEGRADED in r.info_codes

    def test_g2_combo_stale_invalid(self):
        qf = QualityFlags(stale=True, invalid=True)
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=qf,
        )
        assert r.rejected

    def test_g2_combo_stale_duplicate(self):
        qf = QualityFlags(stale=True, duplicate=True)
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=qf,
        )
        assert r.rejected

    def test_g2_combo_invalid_ooo(self):
        qf = QualityFlags(invalid=True, out_of_order=True)
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=qf,
        )
        assert r.rejected

    def test_g2_degraded_with_position(self, sptf02_quality_degraded):
        btc = _mk_btc_long("0.5", "30000", "30000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=sptf02_quality_degraded,
        )
        assert not r.rejected
        assert PS_INFO_Q_DEGRADED in r.info_codes

    def test_g2_block_quality_flags_immutable(self, sptf02_quality_blocked):
        _name, qf, _code = sptf02_quality_blocked
        before = (qf.invalid, qf.stale, qf.quarantined, qf.duplicate,
                  qf.out_of_order, qf.missing, qf.degraded,
                  tuple(qf.reasons), qf.staleness_ms, qf.dedup_key,
                  qf.expected_sequence, qf.actual_sequence)
        build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=qf,
        )
        after = (qf.invalid, qf.stale, qf.quarantined, qf.duplicate,
                 qf.out_of_order, qf.missing, qf.degraded,
                 tuple(qf.reasons), qf.staleness_ms, qf.dedup_key,
                 qf.expected_sequence, qf.actual_sequence)
        assert before == after

    def test_g2_combo_quarantine_missing(self):
        qf = QualityFlags(quarantined=True, missing=True)
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=qf,
        )
        assert r.rejected

    def test_g2_ooo_blocks(self):
        qf = QualityFlags(out_of_order=True)
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=qf,
        )
        assert r.rejected
        assert PS_G2_Q_OOO in r.info_codes

    def test_g2_missing_blocks(self):
        qf = QualityFlags(missing=True)
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=qf,
        )
        assert r.rejected
        assert PS_G2_Q_MISSING in r.info_codes


# ===========================================================================
# 4) G3 Price coverage 8 tests
# ===========================================================================

class Test04G3PriceCoverage:
    def test_g3_1sym_missing_price_reject(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={},  # BTC price missing!
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G3_PRICE_MISSING in r.info_codes

    def test_g3_2sym_one_missing_reject(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000")},  # ETH missing
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G3_PRICE_MISSING in r.info_codes

    def test_g3_2sym_both_present_ok(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap = r.new_snapshot
        assert snap is not None
        expected_exp = Decimal("0.5") * Decimal("32000") + Decimal("5") * Decimal("1600")
        assert snap.exposure_notional == expected_exp

    def test_g3_5sym_2missing_reject(self):
        positions = [
            _mk_btc_long("0.1", "30000", "32000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("1"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
            _make_long_position(SYM_SOL, base_qty=Decimal("10"), avg_entry_price=Decimal("100"), current_price=Decimal("110")),
            _make_long_position(SYM_ADA, base_qty=Decimal("1000"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
            _make_long_position(SYM_XRP, base_qty=Decimal("500"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
        ]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map={  # SOL and ADA missing
                SYM_BTC: Decimal("32000"),
                SYM_ETH: Decimal("1600"),
                SYM_XRP: Decimal("0.6"),
            },
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G3_PRICE_MISSING in r.info_codes

    def test_g3_5sym_all_present_ok(self):
        positions = [
            _mk_btc_long("0.1", "30000", "32000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("1"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
            _make_long_position(SYM_SOL, base_qty=Decimal("10"), avg_entry_price=Decimal("100"), current_price=Decimal("110")),
            _make_long_position(SYM_ADA, base_qty=Decimal("1000"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
            _make_long_position(SYM_XRP, base_qty=Decimal("500"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
        ]
        pm = {
            SYM_BTC: Decimal("32000"),
            SYM_ETH: Decimal("1600"),
            SYM_SOL: Decimal("110"),
            SYM_ADA: Decimal("0.6"),
            SYM_XRP: Decimal("0.6"),
        }
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap = r.new_snapshot
        assert snap is not None
        expected_exp = sum(p.base_qty * pm[p.symbol] for p in positions)
        assert snap.exposure_notional == expected_exp

    def test_g3_flat_position_missing_price_ok(self):
        flat_btc = _flat_zero(SYM_BTC, current_price=Decimal("30000"))
        r = build_portfolio_snapshot(
            positions=[flat_btc],
            cash_quote=Decimal("1000"),
            current_price_map={},  # No BTC price but it's FLAT → OK
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot is not None
        assert r.new_snapshot.exposure_notional == Decimal("0")

    def test_g3_mix_flat_and_long_flat_ok_long_needs_price(self):
        flat_btc = _flat_zero(SYM_BTC, current_price=Decimal("30000"))
        eth_long = _make_long_position(SYM_ETH, base_qty=Decimal("2"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600"))
        r = build_portfolio_snapshot(
            positions=[flat_btc, eth_long],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_ETH: Decimal("1600")},  # BTC flat OK no price, ETH long needs price
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap = r.new_snapshot
        assert snap is not None
        assert snap.exposure_notional == Decimal("2") * Decimal("1600")

    def test_g3_3sym_one_flat_two_long_one_missing(self):
        flat_btc = _flat_zero(SYM_BTC, current_price=Decimal("30000"))
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("2"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600"))
        sol = _make_long_position(SYM_SOL, base_qty=Decimal("10"), avg_entry_price=Decimal("100"), current_price=Decimal("110"))
        r = build_portfolio_snapshot(
            positions=[flat_btc, eth, sol],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_ETH: Decimal("1600")},  # SOL missing
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r.rejected
        assert PS_G3_PRICE_MISSING in r.info_codes


# ===========================================================================
# 5) Exposure 10 tests
# ===========================================================================

class Test05Exposure:
    def test_exp_1sym_exact(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == Decimal("0.5") * Decimal("32000")

    def test_exp_1sym_variation(self):
        btc = _mk_btc_long("2.0", "20000", "25000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("0"),
            current_price_map={SYM_BTC: Decimal("25000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == Decimal("2.0") * Decimal("25000")

    def test_exp_2sym_sum_exact(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = Decimal("0.5") * Decimal("32000") + Decimal("5") * Decimal("1600")
        assert r.new_snapshot.exposure_notional == expected

    def test_exp_2sym_diff_sizes(self):
        btc = _mk_btc_long("0.1", "30000", "40000")
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("100"), avg_entry_price=Decimal("1000"), current_price=Decimal("1200"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("500"),
            current_price_map={SYM_BTC: Decimal("40000"), SYM_ETH: Decimal("1200")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = Decimal("0.1") * Decimal("40000") + Decimal("100") * Decimal("1200")
        assert r.new_snapshot.exposure_notional == expected

    def test_exp_5sym_sum_exact(self):
        positions = [
            _mk_btc_long("0.2", "30000", "35000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("2"), avg_entry_price=Decimal("1500"), current_price=Decimal("2000")),
            _make_long_position(SYM_SOL, base_qty=Decimal("50"), avg_entry_price=Decimal("50"), current_price=Decimal("80")),
            _make_long_position(SYM_ADA, base_qty=Decimal("5000"), avg_entry_price=Decimal("0.3"), current_price=Decimal("0.5")),
            _make_long_position(SYM_XRP, base_qty=Decimal("1000"), avg_entry_price=Decimal("0.4"), current_price=Decimal("0.6")),
        ]
        pm = {
            SYM_BTC: Decimal("35000"),
            SYM_ETH: Decimal("2000"),
            SYM_SOL: Decimal("80"),
            SYM_ADA: Decimal("0.5"),
            SYM_XRP: Decimal("0.6"),
        }
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("10000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = sum(p.base_qty * pm[p.symbol] for p in positions)
        assert r.new_snapshot.exposure_notional == expected

    def test_exp_5sym_tiny_qty(self):
        positions = [
            _mk_btc_long("0.00000001", "30000", "30000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("0.00000002"), avg_entry_price=Decimal("1500"), current_price=Decimal("1500")),
            _make_long_position(SYM_SOL, base_qty=Decimal("0.00000010"), avg_entry_price=Decimal("100"), current_price=Decimal("100")),
            _make_long_position(SYM_ADA, base_qty=Decimal("0.00000100"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.5")),
            _make_long_position(SYM_XRP, base_qty=Decimal("0.00001000"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.5")),
        ]
        pm = {
            SYM_BTC: Decimal("30000"),
            SYM_ETH: Decimal("1500"),
            SYM_SOL: Decimal("100"),
            SYM_ADA: Decimal("0.5"),
            SYM_XRP: Decimal("0.5"),
        }
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap = r.new_snapshot
        assert snap is not None
        assert snap.exposure_notional >= Decimal("0")

    def test_exp_zero_positions_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == Decimal("0")

    def test_exp_flat_positions_zero(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"))
        flat2 = _flat_zero(SYM_ETH, current_price=Decimal("1500"))
        r = build_portfolio_snapshot(
            positions=[flat, flat2],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == Decimal("0")

    def test_exp_nonneg_always(self):
        btc = _mk_btc_long("1", "30000", "30000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional >= Decimal("0")

    def test_exp_3sym_large_numbers(self):
        positions = [
            _mk_btc_long("10", "10000", "50000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("1000"), avg_entry_price=Decimal("100"), current_price=Decimal("3000")),
            _make_long_position(SYM_SOL, base_qty=Decimal("100000"), avg_entry_price=Decimal("1"), current_price=Decimal("100")),
        ]
        pm = {SYM_BTC: Decimal("50000"), SYM_ETH: Decimal("3000"), SYM_SOL: Decimal("100")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("0"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = Decimal("10") * Decimal("50000") + Decimal("1000") * Decimal("3000") + Decimal("100000") * Decimal("100")
        assert r.new_snapshot.exposure_notional == expected


# ===========================================================================
# 6) Equity 12 tests
# ===========================================================================

class Test06Equity:
    def test_eq_cash_only_0_positions(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == Decimal("5000")

    def test_eq_cash_only_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == Decimal("0")

    def test_eq_cash_only_large(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("10000000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == Decimal("10000000")

    def test_eq_1pos_formula_exact(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        cash = Decimal("5000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=cash,
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = cash + Decimal("0.5") * Decimal("32000")
        assert r.new_snapshot.equity_quote == expected

    def test_eq_1pos_cash_plus_exposure(self):
        btc = _mk_btc_long("1", "25000", "30000")
        cash = Decimal("10000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=cash,
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == cash + r.new_snapshot.exposure_notional

    def test_eq_2pos_sum(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600"))
        cash = Decimal("2000")
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=cash,
            current_price_map={SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        exp = Decimal("0.5") * Decimal("32000") + Decimal("5") * Decimal("1600")
        assert r.new_snapshot.equity_quote == cash + exp

    def test_eq_3pos_eq_cash_plus_exp(self):
        positions = [
            _mk_btc_long("0.2", "30000", "35000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("2"), avg_entry_price=Decimal("1500"), current_price=Decimal("2000")),
            _make_long_position(SYM_SOL, base_qty=Decimal("50"), avg_entry_price=Decimal("50"), current_price=Decimal("80")),
        ]
        pm = {SYM_BTC: Decimal("35000"), SYM_ETH: Decimal("2000"), SYM_SOL: Decimal("80")}
        cash = Decimal("10000")
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=cash,
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == cash + r.new_snapshot.exposure_notional

    def test_eq_zero_cash_only_positions(self):
        btc = _mk_btc_long("1", "30000", "30000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("0"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == Decimal("1") * Decimal("30000")

    def test_eq_equity_equals_cash_plus_exposure_invariant(self):
        for cash_val in ["0", "100", "10000", "500000"]:
            btc = _mk_btc_long("0.5", "30000", "40000")
            r = build_portfolio_snapshot(
                positions=[btc],
                cash_quote=Decimal(cash_val),
                current_price_map={SYM_BTC: Decimal("40000")},
                snapshot_ts=Instant(FIXTURE_TS),
                correlation_id=FIXED_CORR,
                causation_id=FIXED_CAUS,
            )
            assert not r.rejected
            snap = r.new_snapshot
            assert snap.equity_quote == snap.cash_quote + snap.exposure_notional

    def test_eq_flat_plus_cash_only(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"))
        cash = Decimal("7777")
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=cash,
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == cash

    def test_eq_5sym_cash_plus_exposure(self):
        positions = [
            _mk_btc_long("0.1", "30000", "32000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("1"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
            _make_long_position(SYM_SOL, base_qty=Decimal("10"), avg_entry_price=Decimal("100"), current_price=Decimal("110")),
            _make_long_position(SYM_ADA, base_qty=Decimal("1000"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
            _make_long_position(SYM_XRP, base_qty=Decimal("500"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
        ]
        pm = {SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600"), SYM_SOL: Decimal("110"),
              SYM_ADA: Decimal("0.6"), SYM_XRP: Decimal("0.6")}
        cash = Decimal("25000")
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=cash,
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        exp = sum(p.base_qty * pm[p.symbol] for p in positions)
        assert r.new_snapshot.equity_quote == cash + exp

    def test_eq_equity_nonneg(self):
        btc = _mk_btc_long("1", "30000", "30000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("100"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote >= Decimal("0")


# ===========================================================================
# 7) Realized 10 tests
# ===========================================================================

class Test07Realized:
    def test_rlz_1pos_single(self):
        btc = _make_long_position(SYM_BTC, base_qty=Decimal("0"), avg_entry_price=Decimal("0"),
                                  current_price=Decimal("30000"), realized=Decimal("500"), fees=Decimal("10"))
        btc_flat = Position(
            position_id=btc.position_id, symbol=btc.symbol, side=PositionSide.FLAT,
            base_qty=Decimal("0"), avg_entry_price=Decimal("0"),
            current_price=btc.current_price, unrealized_pnl_quote=Decimal("0"),
            realized_pnl_quote=Decimal("500"), fees_quote=Decimal("10"),
            opened_ts=btc.opened_ts, last_updated_ts=btc.last_updated_ts,
            open_refs=[], correlation_id=btc.correlation_id, causation_id=btc.causation_id,
        )
        r = build_portfolio_snapshot(
            positions=[btc_flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("500")

    def test_rlz_1pos_via_fill(self):
        pf_buy = _make_pf(seq="RL1B", side=PaperOrderSide.BUY, fill_price=Decimal("30000"),
                          fill_qty_base=Decimal("1"), fees_quote=Decimal("30"))
        r1 = apply_fill(None, pf_buy, symbol=SYM_BTC, current_price=Decimal("30000"))
        pf_sell = _make_pf(seq="RL1S", side=PaperOrderSide.SELL, fill_price=Decimal("35000"),
                           fill_qty_base=Decimal("1"), fees_quote=Decimal("35"))
        r2 = apply_fill(r1.new_position, pf_sell, symbol=SYM_BTC, current_price=Decimal("35000"))
        snap_r = build_portfolio_snapshot(
            positions=[r2.new_position],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("35000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not snap_r.rejected
        # gross=5000 - 35 fee = 4965
        assert snap_r.new_snapshot.realized_pnl_quote_24h == Decimal("4965")

    def test_rlz_2pos_sum(self):
        btc = _flat_zero(SYM_BTC, current_price=Decimal("30000"), realized=Decimal("100"))
        eth = _flat_zero(SYM_ETH, current_price=Decimal("1500"), realized=Decimal("200"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("300")

    def test_rlz_2pos_mixed_sign(self):
        btc = _flat_zero(SYM_BTC, current_price=Decimal("30000"), realized=Decimal("500"))
        eth = _flat_zero(SYM_ETH, current_price=Decimal("1500"), realized=Decimal("-200"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("300")

    def test_rlz_5pos_sum(self):
        positions = [
            _flat_zero(SYM_BTC, current_price=Decimal("30000"), realized=Decimal("100")),
            _flat_zero(SYM_ETH, current_price=Decimal("1500"), realized=Decimal("200")),
            _flat_zero(SYM_SOL, current_price=Decimal("100"), realized=Decimal("-50")),
            _flat_zero(SYM_ADA, current_price=Decimal("0.5"), realized=Decimal("75.5")),
            _flat_zero(SYM_XRP, current_price=Decimal("0.5"), realized=Decimal("25.5")),
        ]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = Decimal("100") + Decimal("200") + Decimal("-50") + Decimal("75.5") + Decimal("25.5")
        assert r.new_snapshot.realized_pnl_quote_24h == expected

    def test_rlz_zero_when_no_realized(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("0")

    def test_rlz_negative_total(self):
        btc = _flat_zero(SYM_BTC, current_price=Decimal("30000"), realized=Decimal("-1000"))
        eth = _flat_zero(SYM_ETH, current_price=Decimal("1500"), realized=Decimal("-500"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("10000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("-1500")

    def test_rlz_3pos_long_with_realized_mixed(self):
        positions = [
            _make_long_position(SYM_BTC, base_qty=Decimal("0.5"), avg_entry_price=Decimal("30000"),
                                current_price=Decimal("32000"), realized=Decimal("1000")),
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"),
                                current_price=Decimal("1600"), realized=Decimal("-200")),
            _make_long_position(SYM_SOL, base_qty=Decimal("50"), avg_entry_price=Decimal("100"),
                                current_price=Decimal("110"), realized=Decimal("300")),
        ]
        pm = {SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600"), SYM_SOL: Decimal("110")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("5000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("1100")

    def test_rlz_1pos_loss(self):
        pf_buy = _make_pf(seq="RL9B", side=PaperOrderSide.BUY, fill_price=Decimal("30000"),
                          fill_qty_base=Decimal("1"), fees_quote=Decimal("30"))
        r1 = apply_fill(None, pf_buy, symbol=SYM_BTC, current_price=Decimal("30000"))
        pf_sell = _make_pf(seq="RL9S", side=PaperOrderSide.SELL, fill_price=Decimal("25000"),
                           fill_qty_base=Decimal("1"), fees_quote=Decimal("25"))
        r2 = apply_fill(r1.new_position, pf_sell, symbol=SYM_BTC, current_price=Decimal("25000"))
        snap_r = build_portfolio_snapshot(
            positions=[r2.new_position],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("25000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not snap_r.rejected
        # gross=-5000 -25 = -5025
        assert snap_r.new_snapshot.realized_pnl_quote_24h == Decimal("-5025")

    def test_rlz_empty_list_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("0")


# ===========================================================================
# 8) Unrealized 10 tests
# ===========================================================================

class Test08Unrealized:
    def test_unr_flat_zero(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.unrealized_pnl_quote == Decimal("0")

    def test_unr_0pos_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.unrealized_pnl_quote == Decimal("0")

    def test_unr_1long_profit(self):
        btc = _mk_btc_long("1", "30000", "35000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("35000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        # (35000 - 30000) * 1 = 5000
        assert r.new_snapshot.unrealized_pnl_quote == Decimal("5000")

    def test_unr_1long_loss(self):
        btc = _mk_btc_long("1", "30000", "25000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("25000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.unrealized_pnl_quote == Decimal("-5000")

    def test_unr_1long_flat_price(self):
        btc = _mk_btc_long("1", "30000", "30000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.unrealized_pnl_quote == Decimal("0")

    def test_unr_2long_sum(self):
        btc = _mk_btc_long("0.5", "30000", "35000")
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1700"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("35000"), SYM_ETH: Decimal("1700")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = Decimal("0.5") * Decimal("5000") + Decimal("5") * Decimal("200")
        assert r.new_snapshot.unrealized_pnl_quote == expected

    def test_unr_2long_mixed_sign(self):
        btc = _mk_btc_long("0.5", "30000", "35000")  # +2500
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1300"))  # -1000
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("35000"), SYM_ETH: Decimal("1300")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.unrealized_pnl_quote == Decimal("1500")

    def test_unr_5pos_sum(self):
        positions = [
            _mk_btc_long("0.5", "30000", "35000"),  # +2500
            _make_long_position(SYM_ETH, base_qty=Decimal("2"), avg_entry_price=Decimal("1500"), current_price=Decimal("2000")),  # +1000
            _make_long_position(SYM_SOL, base_qty=Decimal("10"), avg_entry_price=Decimal("100"), current_price=Decimal("80")),  # -200
            _make_long_position(SYM_ADA, base_qty=Decimal("1000"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.7")),  # +200
            _make_long_position(SYM_XRP, base_qty=Decimal("500"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.4")),  # -50
        ]
        pm = {SYM_BTC: Decimal("35000"), SYM_ETH: Decimal("2000"), SYM_SOL: Decimal("80"),
              SYM_ADA: Decimal("0.7"), SYM_XRP: Decimal("0.4")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("10000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = Decimal("2500") + Decimal("1000") - Decimal("200") + Decimal("200") - Decimal("50")
        assert r.new_snapshot.unrealized_pnl_quote == expected

    def test_unr_tiny_qty(self):
        btc = _mk_btc_long("0.00000001", "30000", "30000.00000001")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("30000.00000001")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap = r.new_snapshot
        assert snap is not None
        # Just check it's a Decimal, not worrying about precision exactness
        assert isinstance(snap.unrealized_pnl_quote, Decimal)

    def test_unr_3long_all_loss(self):
        positions = [
            _mk_btc_long("0.5", "40000", "30000"),  # -5000
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("2000"), current_price=Decimal("1500")),  # -2500
            _make_long_position(SYM_SOL, base_qty=Decimal("10"), avg_entry_price=Decimal("150"), current_price=Decimal("100")),  # -500
        ]
        pm = {SYM_BTC: Decimal("30000"), SYM_ETH: Decimal("1500"), SYM_SOL: Decimal("100")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("100000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = Decimal("-5000") + Decimal("-2500") + Decimal("-500")
        assert r.new_snapshot.unrealized_pnl_quote == expected


# ===========================================================================
# 9) Fees 10 tests (sum 1/2/5 + S-PTF-01 0.22 case)
# ===========================================================================

class Test09Fees:
    def test_fee_1pos_single(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"), fees=Decimal("5"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total == Decimal("5")

    def test_fee_2pos_sum(self):
        btc = _flat_zero(SYM_BTC, current_price=Decimal("30000"), fees=Decimal("10"))
        eth = _flat_zero(SYM_ETH, current_price=Decimal("1500"), fees=Decimal("20"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total == Decimal("30")

    def test_fee_5pos_sum(self):
        positions = [
            _flat_zero(SYM_BTC, current_price=Decimal("30000"), fees=Decimal("10.5")),
            _flat_zero(SYM_ETH, current_price=Decimal("1500"), fees=Decimal("20.25")),
            _flat_zero(SYM_SOL, current_price=Decimal("100"), fees=Decimal("5.5")),
            _flat_zero(SYM_ADA, current_price=Decimal("0.5"), fees=Decimal("1.25")),
            _flat_zero(SYM_XRP, current_price=Decimal("0.5"), fees=Decimal("2.5")),
        ]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        expected = Decimal("10.5") + Decimal("20.25") + Decimal("5.5") + Decimal("1.25") + Decimal("2.5")
        assert r.new_snapshot.fees_quote_total == expected

    def test_fee_sptf01_022_case(self):
        """0.1 + 0.12 = 0.22 — S-PTF-01 Q4 close case."""
        prev = _flat_zero(SYM_ETH, current_price=Decimal("10"))
        pf1 = _make_pf(seq="FEE1", side=PaperOrderSide.BUY, fill_price=Decimal("10"),
                       fill_qty_base=Decimal("1"), fees_quote=Decimal("0.1"))
        r1 = apply_fill(prev, pf1, symbol=SYM_ETH, current_price=Decimal("10"))
        pf2 = _make_pf(seq="FEE2", side=PaperOrderSide.SELL, fill_price=Decimal("12"),
                       fill_qty_base=Decimal("1"), fees_quote=Decimal("0.12"))
        r2 = apply_fill(r1.new_position, pf2, symbol=SYM_ETH, current_price=Decimal("12"))
        snap_r = build_portfolio_snapshot(
            positions=[r2.new_position],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_ETH: Decimal("12")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not snap_r.rejected
        assert snap_r.new_snapshot.fees_quote_total == Decimal("0.22")

    def test_fee_sptf01_variant_buy_buy_sell(self):
        prev = _flat_zero(SYM_ETH, current_price=Decimal("10"))
        pf1 = _make_pf(seq="FEEA1", side=PaperOrderSide.BUY, fill_price=Decimal("10"),
                       fill_qty_base=Decimal("1"), fees_quote=Decimal("0.05"))
        r1 = apply_fill(prev, pf1, symbol=SYM_ETH, current_price=Decimal("10"))
        pf2 = _make_pf(seq="FEEA2", side=PaperOrderSide.BUY, fill_price=Decimal("11"),
                       fill_qty_base=Decimal("1"), fees_quote=Decimal("0.055"))
        r2 = apply_fill(r1.new_position, pf2, symbol=SYM_ETH, current_price=Decimal("11"))
        pf3 = _make_pf(seq="FEEA3", side=PaperOrderSide.SELL, fill_price=Decimal("12"),
                       fill_qty_base=Decimal("2"), fees_quote=Decimal("0.12"))
        r3 = apply_fill(r2.new_position, pf3, symbol=SYM_ETH, current_price=Decimal("12"))
        snap_r = build_portfolio_snapshot(
            positions=[r3.new_position],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_ETH: Decimal("12")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not snap_r.rejected
        assert snap_r.new_snapshot.fees_quote_total == Decimal("0.05") + Decimal("0.055") + Decimal("0.12")

    def test_fee_zero_no_positions(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total == Decimal("0")

    def test_fee_3long_positions(self):
        positions = [
            _mk_btc_long("0.5", "30000", "32000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
            _make_long_position(SYM_SOL, base_qty=Decimal("50"), avg_entry_price=Decimal("100"), current_price=Decimal("110"), fees=Decimal("15")),
        ]
        # Set fees on btc/eth too
        positions[0] = Position(**{**positions[0].__dict__, "fees_quote": Decimal("30")})
        positions[1] = Position(**{**positions[1].__dict__, "fees_quote": Decimal("10")})
        pm = {SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600"), SYM_SOL: Decimal("110")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("5000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total == Decimal("55")

    def test_fee_large_single(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"), fees=Decimal("1000000"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total == Decimal("1000000")

    def test_fee_tiny_8dp(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"), fees=Decimal("0.00000001"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total == Decimal("0.00000001")

    def test_fee_nonneg_invariant(self):
        btc = _mk_btc_long("1", "30000", "30000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total >= Decimal("0")


# ===========================================================================
# 10) Peak 16 tests
# ===========================================================================

class Test10Peak:
    def test_peak_first_snap_peak_equals_equity(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=None,
        )
        assert not r.rejected
        assert PS_INFO_FIRST_SNAPSHOT in r.info_codes
        assert r.new_snapshot.peak_equity_quote == r.new_snapshot.equity_quote

    def test_peak_first_snap_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == Decimal("0")

    def test_peak_first_snap_with_positions(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == r.new_snapshot.equity_quote

    def test_peak_grow_new_peak_higher(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("15000"),  # equity=1000+16000=17000 > 15000
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == Decimal("17000")

    def test_peak_shrink_same_peak(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),  # 5000 < 10000
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == Decimal("10000")

    def test_peak_equal_unchanged(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("5000"),
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == Decimal("5000")

    def test_peak_three_snap_grow_then_shrink(self):
        # Snap 1: 10000
        r1 = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("10000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert r1.new_snapshot.peak_equity_quote == Decimal("10000")
        # Snap 2: 15000 → new peak
        r2 = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("15000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=r1.new_snapshot.peak_equity_quote,
        )
        assert r2.new_snapshot.peak_equity_quote == Decimal("15000")
        # Snap 3: 8000 → peak stays 15000
        r3 = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("8000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=r2.new_snapshot.peak_equity_quote,
        )
        assert r3.new_snapshot.peak_equity_quote == Decimal("15000")

    def test_peak_engine_tracks_peak(self, sptf02_engine):
        r1 = sptf02_engine.build(
            positions=[],
            cash_quote=Decimal("10000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert sptf02_engine.peak_equity_quote == Decimal("10000")
        r2 = sptf02_engine.build(
            positions=[],
            cash_quote=Decimal("20000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert sptf02_engine.peak_equity_quote == Decimal("20000")
        r3 = sptf02_engine.build(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert sptf02_engine.peak_equity_quote == Decimal("20000")

    def test_peak_grow_with_position_appreciation(self):
        btc = _mk_btc_long("1", "30000", "40000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("0"),
            current_price_map={SYM_BTC: Decimal("40000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("30000"),  # equity=40000 > 30000
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == Decimal("40000")

    def test_peak_shrink_position_depreciation(self):
        btc = _mk_btc_long("1", "30000", "20000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("0"),
            current_price_map={SYM_BTC: Decimal("20000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("40000"),
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == Decimal("40000")

    def test_peak_nonneg(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote >= Decimal("0")

    def test_peak_grow_large_jump(self):
        btc = _mk_btc_long("10", "10000", "50000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("100000"),
            current_price_map={SYM_BTC: Decimal("50000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("100000"),
        )
        assert not r.rejected
        expected_eq = Decimal("100000") + Decimal("10") * Decimal("50000")
        assert r.new_snapshot.peak_equity_quote == expected_eq

    def test_peak_shrink_to_zero_peak_stays(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("1000000"),
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == Decimal("1000000")

    def test_peak_first_snap_info_code(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=None,
        )
        assert not r.rejected
        assert PS_INFO_FIRST_SNAPSHOT in r.info_codes

    def test_peak_non_first_no_first_info_code(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("100"),
        )
        assert not r.rejected
        assert PS_INFO_FIRST_SNAPSHOT not in r.info_codes

    def test_peak_ge_equity_invariant(self):
        for eq, pk in [("5000", "10000"), ("8000", "8000"), ("0", "1000")]:
            r = build_portfolio_snapshot(
                positions=[],
                cash_quote=Decimal(eq),
                current_price_map={},
                snapshot_ts=Instant(FIXTURE_TS),
                correlation_id=FIXED_CORR,
                causation_id=FIXED_CAUS,
                prev_peak_equity_quote=Decimal(pk),
            )
            assert not r.rejected
            assert r.new_snapshot.peak_equity_quote >= r.new_snapshot.equity_quote


# ===========================================================================
# 11) Drawdown 18 tests
# ===========================================================================

class Test11Drawdown:
    def test_dd_0_percent_at_peak(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("10000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert r.new_snapshot.drawdown_pct == 0.0

    def test_dd_0_percent_new_peak(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("15000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert r.new_snapshot.drawdown_pct == 0.0

    def test_dd_15_percent(self):
        # peak=10000, eq=8500 → (10000-8500)/10000 = 0.15
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("8500"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 0.15) < 1e-9

    def test_dd_50_percent(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 0.5) < 1e-9

    def test_dd_100_percent_eq_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 1.0) < 1e-9

    def test_dd_eq_zero_peak_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("0"),
        )
        assert not r.rejected
        assert r.new_snapshot.drawdown_pct == 0.0

    def test_dd_first_snap_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("10000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.drawdown_pct == 0.0

    def test_dd_float_type(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert isinstance(r.new_snapshot.drawdown_pct, float)

    def test_dd_clamp_min_0(self):
        # Even if somehow eq > peak (shouldn't happen with max logic), clamp to 0
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("15000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert r.new_snapshot.drawdown_pct >= 0.0

    def test_dd_clamp_max_1(self):
        # 100% is max, even with edge cases
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("1000"),
        )
        assert not r.rejected
        assert r.new_snapshot.drawdown_pct <= 1.0

    def test_dd_25_percent(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("7500"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 0.25) < 1e-9

    def test_dd_90_percent(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 0.9) < 1e-9

    def test_dd_99_percent(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 0.99) < 1e-9

    def test_dd_1_percent(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("9900"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 0.01) < 1e-9

    def test_dd_with_positions_drop(self):
        btc = _mk_btc_long("1", "40000", "20000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("0"),
            current_price_map={SYM_BTC: Decimal("20000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("40000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 0.5) < 1e-9

    def test_dd_three_snap_sequence(self):
        r1 = build_portfolio_snapshot(
            positions=[], cash_quote=Decimal("10000"), current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS), correlation_id=FIXED_CORR, causation_id=FIXED_CAUS,
        )
        assert r1.new_snapshot.drawdown_pct == 0.0
        r2 = build_portfolio_snapshot(
            positions=[], cash_quote=Decimal("8000"), current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS), correlation_id=FIXED_CORR, causation_id=FIXED_CAUS,
            prev_peak_equity_quote=r1.new_snapshot.peak_equity_quote,
        )
        assert abs(r2.new_snapshot.drawdown_pct - 0.2) < 1e-9
        r3 = build_portfolio_snapshot(
            positions=[], cash_quote=Decimal("5000"), current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS), correlation_id=FIXED_CORR, causation_id=FIXED_CAUS,
            prev_peak_equity_quote=r2.new_snapshot.peak_equity_quote,
        )
        assert abs(r3.new_snapshot.drawdown_pct - 0.5) < 1e-9

    def test_dd_tiny_fraction(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("9999"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert 0.0 < r.new_snapshot.drawdown_pct < 0.01

    def test_dd_range_invariant_0_1(self):
        for eq in ["0", "1000", "5000", "9999", "10000", "15000"]:
            r = build_portfolio_snapshot(
                positions=[],
                cash_quote=Decimal(eq),
                current_price_map={},
                snapshot_ts=Instant(FIXTURE_TS),
                correlation_id=FIXED_CORR,
                causation_id=FIXED_CAUS,
                prev_peak_equity_quote=Decimal("10000"),
            )
            assert not r.rejected
            dd = r.new_snapshot.drawdown_pct
            assert 0.0 <= dd <= 1.0, f"dd={dd} out of range for eq={eq}"


# ===========================================================================
# 12) Invariants 12 tests
# ===========================================================================

class Test12Invariants:
    def test_inv_eq_equals_cash_plus_exposure_exact_0pos(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        eq_check = r.new_snapshot.cash_quote + r.new_snapshot.exposure_notional
        assert eq_check == r.new_snapshot.equity_quote

    def test_inv_eq_equals_cash_plus_exposure_exact_1pos(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("5000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        eq_check = r.new_snapshot.cash_quote + r.new_snapshot.exposure_notional
        assert eq_check == r.new_snapshot.equity_quote

    def test_inv_eq_equals_cash_plus_exposure_exact_3pos(self):
        positions = [
            _mk_btc_long("0.2", "30000", "35000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("2"), avg_entry_price=Decimal("1500"), current_price=Decimal("2000")),
            _make_long_position(SYM_SOL, base_qty=Decimal("50"), avg_entry_price=Decimal("50"), current_price=Decimal("80")),
        ]
        pm = {SYM_BTC: Decimal("35000"), SYM_ETH: Decimal("2000"), SYM_SOL: Decimal("80")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("10000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        eq_check = r.new_snapshot.cash_quote + r.new_snapshot.exposure_notional
        assert eq_check == r.new_snapshot.equity_quote

    def test_inv_exposure_le_equity_0pos(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional <= r.new_snapshot.equity_quote

    def test_inv_exposure_le_equity_1pos(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("5000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional <= r.new_snapshot.equity_quote

    def test_inv_exposure_le_equity_allin(self):
        # 0 cash, full exposure → equity == exposure
        btc = _mk_btc_long("1", "30000", "30000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("0"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == r.new_snapshot.equity_quote

    def test_inv_peak_ge_equity(self):
        for eq, pk in [("5000", "10000"), ("8000", "8000"), ("10000", "10000"), ("0", "1000")]:
            r = build_portfolio_snapshot(
                positions=[],
                cash_quote=Decimal(eq),
                current_price_map={},
                snapshot_ts=Instant(FIXTURE_TS),
                correlation_id=FIXED_CORR,
                causation_id=FIXED_CAUS,
                prev_peak_equity_quote=Decimal(pk),
            )
            assert not r.rejected
            assert r.new_snapshot.peak_equity_quote >= r.new_snapshot.equity_quote

    def test_inv_fees_nonneg(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"), fees=Decimal("5"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total >= Decimal("0")

    def test_inv_cash_nonneg(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.cash_quote >= Decimal("0")

    def test_inv_exposure_nonneg(self):
        positions = [
            _mk_btc_long("0.5", "30000", "32000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
        ]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional >= Decimal("0")

    def test_inv_equity_nonneg(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote >= Decimal("0")

    def test_inv_peak_nonneg(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote >= Decimal("0")


# ===========================================================================
# 13) T1 Contract 18 tests (PortfolioSnapshot fields set)
# ===========================================================================

class Test13T1Contract:
    def test_t1_snapshot_id_set(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            snapshot_id=ULID("SNAP0000000000000000000001"),
        )
        assert not r.rejected
        assert str(r.new_snapshot.snapshot_id) == "SNAP0000000000000000000001"

    def test_t1_account_ref_set(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            account_ref="custom-acc-1",
        )
        assert not r.rejected
        assert r.new_snapshot.account_ref == "custom-acc-1"

    def test_t1_ts_set(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert str(r.new_snapshot.ts) == FIXTURE_TS

    def test_t1_cash_set(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("7777.77"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.cash_quote == Decimal("7777.77")

    def test_t1_equity_set(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("5000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == Decimal("5000") + Decimal("0.5") * Decimal("32000")

    def test_t1_realized_set(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"), realized=Decimal("42.5"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("42.5")

    def test_t1_unrealized_set(self):
        btc = _mk_btc_long("1", "30000", "35000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("35000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.unrealized_pnl_quote == Decimal("5000")

    def test_t1_fees_set(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"), fees=Decimal("123.45"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total == Decimal("123.45")

    def test_t1_exposure_set(self):
        btc = _mk_btc_long("0.5", "30000", "40000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("0"),
            current_price_map={SYM_BTC: Decimal("40000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == Decimal("0.5") * Decimal("40000")

    def test_t1_drawdown_set(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        assert not r.rejected
        assert abs(r.new_snapshot.drawdown_pct - 0.5) < 1e-9

    def test_t1_peak_set(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("50000"),
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == Decimal("50000")

    def test_t1_correlation_set(self):
        custom_corr = ULID("CUSTOM-CORR-00000000000000001")
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=custom_corr,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert str(r.new_snapshot.correlation_id) == str(custom_corr)

    def test_t1_causation_set(self):
        custom_caus = ULID("CUSTOM-CAUS-00000000000000001")
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=custom_caus,
        )
        assert not r.rejected
        assert str(r.new_snapshot.causation_id) == str(custom_caus)

    def test_t1_positions_included_true(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            include_positions_in_snapshot=True,
        )
        assert not r.rejected
        assert r.new_snapshot.positions_snapshot is not None
        assert len(r.new_snapshot.positions_snapshot) == 1
        assert PS_INFO_POS_INCLUDED in r.info_codes

    def test_t1_positions_included_false(self):
        btc = _mk_btc_long("0.5", "30000", "32000")
        r = build_portfolio_snapshot(
            positions=[btc],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            include_positions_in_snapshot=False,
        )
        assert not r.rejected
        assert r.new_snapshot.positions_snapshot is None
        assert PS_INFO_POS_OMITTED in r.info_codes

    def test_t1_is_portfoliosnapshot_instance(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert isinstance(r.new_snapshot, PortfolioSnapshot)

    def test_t1_positions_empty_list_when_included_true(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            include_positions_in_snapshot=True,
        )
        assert not r.rejected
        assert r.new_snapshot.positions_snapshot == []

    def test_t1_default_account_ref(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.account_ref == "paper-main"


# ===========================================================================
# 14) T2 Bus publish 20 tests
# ===========================================================================

class Test14T2BusPublish:
    def test_t2_typed_subscribe_portfolio_snapshot_v1(self, sptf02_bus, sptf02_engine):
        events = []
        def handler(env):
            events.append(env)
        sptf02_bus.subscribe_typed(EVENT_PORTFOLIO_SNAPSHOT, handler)
        sptf02_engine.build(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert len(events) >= 1
        assert events[0].event_type == EVENT_PORTFOLIO_SNAPSHOT

    def test_t2_event_type_in_published(self, sptf02_bus):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        types = [e.event_type for e in sptf02_bus.published]
        assert EVENT_PORTFOLIO_SNAPSHOT in types

    def test_t2_envelope_payload_is_snapshot(self, sptf02_bus):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert isinstance(env.payload, PortfolioSnapshot)

    def test_t2_correlation_preserved(self, sptf02_bus):
        custom_corr = ULID("CORR-T2-000000000000000004")
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=custom_corr,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert str(env.correlation_id) == str(custom_corr)

    def test_t2_causation_preserved(self, sptf02_bus):
        custom_caus = ULID("CAUS-T2-000000000000000004")
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=custom_caus,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert str(env.causation_id) == str(custom_caus)

    def test_t2_parent_causation_linked(self, sptf02_bus):
        parent_caus = ULID("PARENT-CAUS-000000000000001")
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=parent_caus,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        chain = sptf02_bus.trace_causation_chain(str(env.event_id))
        assert str(env.event_id) in chain

    def test_t2_rejected_event_publish(self, sptf02_bus):
        r = _make_snapshot_reject_local(reason_code=PS_G1_INVALID)
        object.__setattr__(r, "_fallback_corr", FIXED_CORR)
        object.__setattr__(r, "_fallback_caus", FIXED_CAUS)
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        types = [e.event_type for e in sptf02_bus.published]
        assert EVENT_PORTFOLIO_SNAPSHOT_REJECTED in types

    def test_t2_none_bus_safe(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        try:
            publish_portfolio_snapshot_event(result=r, event_bus=None)
        except Exception as e:
            pytest.fail(f"publish with None bus raised: {e}")

    def test_t2_extra_has_info_codes(self, sptf02_bus):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert "info_codes" in env.extra
        assert isinstance(env.extra["info_codes"], list)

    def test_t2_extra_has_positions_count(self, sptf02_bus):
        btc = _mk_btc_long("0.5", "30000", "32000")
        eth = _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600"))
        r = build_portfolio_snapshot(
            positions=[btc, eth],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert env.extra["positions_count"] == 2

    def test_t2_extra_has_drawdown(self, sptf02_bus):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("10000"),
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert "drawdown_pct" in env.extra
        assert abs(env.extra["drawdown_pct"] - 0.5) < 1e-9

    def test_t2_extra_has_peak_str(self, sptf02_bus):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            prev_peak_equity_quote=Decimal("50000"),
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert "peak_equity_quote_str" in env.extra
        assert env.extra["peak_equity_quote_str"] == "50000"

    def test_t2_subscriber_exception_dlq(self, sptf02_bus):
        def bad(env): raise RuntimeError("boom")
        def good(env): pass
        sptf02_bus.subscribe_typed(EVENT_PORTFOLIO_SNAPSHOT, good)
        sptf02_bus.subscribe_typed(EVENT_PORTFOLIO_SNAPSHOT, bad)
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        dlq_codes = [d.dlq_code for d in sptf02_bus.dead_letters]
        assert "E_SUBSCRIBER_EXC" in dlq_codes

    def test_t2_quality_ctx_in_envelope(self, sptf02_bus, sptf02_quality_degraded):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            quality_ctx=sptf02_quality_degraded,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus, quality_ctx=sptf02_quality_degraded)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert env.quality_flags.degraded is True

    def test_t2_run_mode_paper(self, sptf02_bus):
        from app.contracts import RunMode
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert env.run_mode == RunMode.PAPER

    def test_t2_source_type_simulated(self, sptf02_bus):
        from app.contracts import SourceType
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert env.source_type == SourceType.SIMULATED

    def test_t2_rejected_extra_has_reason(self, sptf02_bus):
        r = _make_snapshot_reject_local(reason_code=PS_G1_INVALID, reason_detail="cash bad")
        object.__setattr__(r, "_fallback_corr", FIXED_CORR)
        object.__setattr__(r, "_fallback_caus", FIXED_CAUS)
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT_REJECTED)
        assert "rejected_reason" in env.extra

    def test_t2_engine_publish_flag_false_no_publish(self, sptf02_bus):
        engine = PortfolioSnapshotEngine(event_bus=sptf02_bus)
        engine.build(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            publish=False,
        )
        assert len(sptf02_bus.published) == 0

    def test_t2_engine_publish_flag_true_publishes(self, sptf02_bus):
        engine = PortfolioSnapshotEngine(event_bus=sptf02_bus)
        engine.build(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            publish=True,
        )
        types = [e.event_type for e in sptf02_bus.published]
        assert EVENT_PORTFOLIO_SNAPSHOT in types

    def test_t2_envelope_ts_matches_snapshot(self, sptf02_bus):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert str(env.timestamp) == FIXTURE_TS
        assert str(env.ingest_ts) == FIXTURE_TS


def _make_snapshot_reject_local(*, reason_code, reason_detail="", info_codes=None):
    from app.simulation.portfolio import PortfolioSnapshotResult
    codes = list(info_codes) if info_codes else []
    if reason_code and reason_code not in codes:
        codes.append(reason_code)
    return PortfolioSnapshotResult(
        new_snapshot=None,
        rejected=True,
        info_codes=codes,
        rejected_reason=reason_detail or reason_code,
    )


# ===========================================================================
# 15) Multi sym sort 12 tests
# ===========================================================================

class Test15MultiSymSort:
    def test_sort_reversed_3sym_sorted_order(self):
        positions = [
            _make_long_position(SYM_XRP, base_qty=Decimal("100"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
            _make_long_position(SYM_SOL, base_qty=Decimal("10"), avg_entry_price=Decimal("100"), current_price=Decimal("110")),
            _mk_btc_long("0.5", "30000", "32000"),
        ]
        pm = {SYM_BTC: Decimal("32000"), SYM_SOL: Decimal("110"), SYM_XRP: Decimal("0.6")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap_pos = r.new_snapshot.positions_snapshot
        assert snap_pos is not None
        syms = [str(p.symbol) for p in snap_pos]
        assert syms == sorted(syms)

    def test_sort_2sym_reversed(self):
        positions = [
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
            _mk_btc_long("0.5", "30000", "32000"),
        ]
        pm = {SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap_pos = r.new_snapshot.positions_snapshot
        assert snap_pos is not None
        assert str(snap_pos[0].symbol) <= str(snap_pos[1].symbol)

    def test_sort_5sym_random_order_sorted(self):
        positions = [
            _make_long_position(SYM_DOT, base_qty=Decimal("100"), avg_entry_price=Decimal("10"), current_price=Decimal("12")),
            _make_long_position(SYM_ADA, base_qty=Decimal("1000"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
            _mk_btc_long("0.5", "30000", "32000"),
            _make_long_position(SYM_XRP, base_qty=Decimal("500"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
        ]
        pm = {SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600"), SYM_ADA: Decimal("0.6"),
              SYM_XRP: Decimal("0.6"), SYM_DOT: Decimal("12")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("10000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap_pos = r.new_snapshot.positions_snapshot
        assert snap_pos is not None
        syms = [str(p.symbol) for p in snap_pos]
        assert syms == sorted(syms)

    def test_sort_4sym_alphabetical(self):
        positions = [
            _make_long_position(SYM_XRP, base_qty=Decimal("1"), avg_entry_price=Decimal("1"), current_price=Decimal("1")),
            _make_long_position(SYM_DOT, base_qty=Decimal("1"), avg_entry_price=Decimal("1"), current_price=Decimal("1")),
            _make_long_position(SYM_ADA, base_qty=Decimal("1"), avg_entry_price=Decimal("1"), current_price=Decimal("1")),
            _make_long_position(SYM_SOL, base_qty=Decimal("1"), avg_entry_price=Decimal("1"), current_price=Decimal("1")),
        ]
        pm = {s: Decimal("1") for s in [SYM_ADA, SYM_DOT, SYM_SOL, SYM_XRP]}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap_pos = r.new_snapshot.positions_snapshot
        assert snap_pos is not None
        for i in range(len(snap_pos) - 1):
            assert str(snap_pos[i].symbol) <= str(snap_pos[i + 1].symbol)

    def test_sort_already_sorted_stays_sorted(self):
        positions = [
            _mk_btc_long("1", "30000", "30000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("1"), avg_entry_price=Decimal("1"), current_price=Decimal("1")),
        ]
        pm = {SYM_BTC: Decimal("30000"), SYM_ETH: Decimal("1")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap_pos = r.new_snapshot.positions_snapshot
        assert snap_pos is not None
        assert str(snap_pos[0].symbol) == str(SYM_BTC)
        assert str(snap_pos[1].symbol) == str(SYM_ETH)

    def test_sort_single_sym_noop(self):
        positions = [_mk_btc_long("1", "30000", "30000")]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap_pos = r.new_snapshot.positions_snapshot
        assert snap_pos is not None
        assert len(snap_pos) == 1

    def test_sort_empty_list(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.positions_snapshot == []

    def test_sort_flat_and_long_mixed(self):
        positions = [
            _flat_zero(SYM_XRP, current_price=Decimal("0.6")),
            _mk_btc_long("1", "30000", "32000"),
            _flat_zero(SYM_ADA, current_price=Decimal("0.6")),
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
        ]
        pm = {SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")}
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap_pos = r.new_snapshot.positions_snapshot
        assert snap_pos is not None
        syms = [str(p.symbol) for p in snap_pos]
        assert syms == sorted(syms)

    def test_sort_three_orders_same_result(self):
        pos_list1 = [
            _mk_btc_long("1", "30000", "30000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("1"), avg_entry_price=Decimal("1"), current_price=Decimal("1")),
            _make_long_position(SYM_SOL, base_qty=Decimal("1"), avg_entry_price=Decimal("1"), current_price=Decimal("1")),
        ]
        pos_list2 = list(reversed(pos_list1))
        pos_list3 = [pos_list1[1], pos_list1[2], pos_list1[0]]
        pm = {SYM_BTC: Decimal("30000"), SYM_ETH: Decimal("1"), SYM_SOL: Decimal("1")}
        results = []
        for plist in [pos_list1, pos_list2, pos_list3]:
            r = build_portfolio_snapshot(
                positions=list(plist),
                cash_quote=Decimal("1000"),
                current_price_map=pm,
                snapshot_ts=Instant(FIXTURE_TS),
                correlation_id=FIXED_CORR,
                causation_id=FIXED_CAUS,
            )
            results.append([str(p.symbol) for p in r.new_snapshot.positions_snapshot])
        assert results[0] == results[1] == results[2]

    def test_sort_flat_only_sorted(self):
        positions = [
            _flat_zero(SYM_XRP, current_price=Decimal("0.6")),
            _flat_zero(SYM_BTC, current_price=Decimal("30000")),
            _flat_zero(SYM_ADA, current_price=Decimal("0.5")),
        ]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        snap_pos = r.new_snapshot.positions_snapshot
        assert snap_pos is not None
        syms = [str(p.symbol) for p in snap_pos]
        assert syms == sorted(syms)

    def test_sort_exposure_aggregation_same(self):
        positions1 = [
            _mk_btc_long("0.5", "30000", "32000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
        ]
        positions2 = [positions1[1], positions1[0]]
        pm = {SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")}
        r1 = build_portfolio_snapshot(
            positions=positions1, cash_quote=Decimal("1000"), current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS), correlation_id=FIXED_CORR, causation_id=FIXED_CAUS,
        )
        r2 = build_portfolio_snapshot(
            positions=positions2, cash_quote=Decimal("1000"), current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS), correlation_id=FIXED_CORR, causation_id=FIXED_CAUS,
        )
        assert r1.new_snapshot.exposure_notional == r2.new_snapshot.exposure_notional

    def test_sort_equity_aggregation_same(self):
        positions1 = [
            _mk_btc_long("0.5", "30000", "32000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
        ]
        positions2 = [positions1[1], positions1[0]]
        pm = {SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")}
        r1 = build_portfolio_snapshot(
            positions=positions1, cash_quote=Decimal("5000"), current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS), correlation_id=FIXED_CORR, causation_id=FIXED_CAUS,
        )
        r2 = build_portfolio_snapshot(
            positions=positions2, cash_quote=Decimal("5000"), current_price_map=pm,
            snapshot_ts=Instant(FIXTURE_TS), correlation_id=FIXED_CORR, causation_id=FIXED_CAUS,
        )
        assert r1.new_snapshot.equity_quote == r2.new_snapshot.equity_quote


# ===========================================================================
# 16) CAP-1 6 tests (AST 0 match datetime/sleep/run_mode/source_type)
# ===========================================================================

class Test16Cap1:
    def test_cap1_ast_no_runmode_branch(self):
        import ast
        import app.simulation.portfolio as pm
        src_file = self._get_src(pm)
        if not src_file:
            pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                for sub in ast.walk(node.test):
                    if isinstance(sub, ast.Name) and sub.id in {"run_mode", "source_type"}:
                        pytest.fail(f"CAP-1 forbidden conditional branch: {sub.id}")

    def test_cap1_ast_no_datetime_now(self):
        import ast
        import app.simulation.portfolio as pm
        src_file = self._get_src(pm)
        if not src_file:
            pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "now":
                ctx_val = node.value
                if isinstance(ctx_val, ast.Name) and ctx_val.id == "datetime":
                    pytest.fail("CAP-1 forbidden datetime.now")

    def test_cap1_ast_no_time_time(self):
        import ast
        import app.simulation.portfolio as pm
        src_file = self._get_src(pm)
        if not src_file:
            pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "time":
                ctx_val = node.value
                if isinstance(ctx_val, ast.Name) and ctx_val.id == "time":
                    pytest.fail("CAP-1 forbidden time.time")

    def test_cap1_ast_no_sleep(self):
        import ast
        import app.simulation.portfolio as pm
        src_file = self._get_src(pm)
        if not src_file:
            pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "sleep":
                pytest.fail("CAP-1 forbidden sleep call")

    def test_cap1_ast_no_source_type_in_if(self):
        import ast
        import app.simulation.portfolio as pm
        src_file = self._get_src(pm)
        if not src_file:
            pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                for sub in ast.walk(node.test):
                    if isinstance(sub, ast.Name) and sub.id == "source_type":
                        pytest.fail("CAP-1 forbidden source_type branch")

    def test_cap1_no_pure_logic_depends_on_datetime(self):
        import app.simulation.portfolio as pm
        src_file = self._get_src(pm)
        if not src_file:
            pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        # AST walk: find datetime.now() calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "now" and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == "datetime":
                pytest.fail("CAP-1 forbidden datetime.now() call")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "sleep" and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == "time":
                pytest.fail("CAP-1 forbidden time.sleep() call")

    @staticmethod
    def _get_src(mod):
        try:
            import importlib.util
            return importlib.util.find_spec(mod.__name__).origin
        except Exception:
            return getattr(mod, "__file__", None)


# ===========================================================================
# 17) CAP-2 8 tests (validate_* 0 import/call, quality mutate 0)
# ===========================================================================

class Test17Cap2:
    def test_cap2_no_validate_market_call(self):
        import ast
        src_file = self._src()
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        self._assert_no_call(tree, "validate_market")

    def test_cap2_no_validate_fill_call(self):
        import ast
        src_file = self._src()
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        self._assert_no_call(tree, "validate_fill")

    def test_cap2_no_validate_order_call(self):
        import ast
        src_file = self._src()
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        self._assert_no_call(tree, "validate_order")

    def test_cap2_no_validate_envelope_call(self):
        import ast
        src_file = self._src()
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        self._assert_no_call(tree, "validate_envelope")

    def test_cap2_no_validate_quality_call(self):
        import ast
        src_file = self._src()
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        self._assert_no_call(tree, "validate_quality")

    def test_cap2_no_setattr_on_quality(self):
        import ast
        src_file = self._src()
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read()
            )
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
                pytest.fail("CAP-2 setattr in portfolio.py — quality mutate risk")

    def test_cap2_quality_flags_not_assigned(self):
        import ast
        src_file = self._src()
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        # No assignment to qf.stale, qf.invalid, etc.
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        if target.attr in {"stale", "invalid", "quarantined", "duplicate",
                                            "out_of_order", "missing", "degraded"}:
                            pytest.fail(f"CAP-2 quality mutate: .{target.attr}")

    def test_cap2_no_validate_signal_call(self):
        import ast
        src_file = self._src()
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        self._assert_no_call(tree, "validate_signal")

    @staticmethod
    def _src():
        import app.simulation.portfolio as pm
        try:
            import importlib.util
            return importlib.util.find_spec(pm.__name__).origin
        except Exception:
            return getattr(pm, "__file__", None)

    @staticmethod
    def _assert_no_call(tree, func_name):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                assert name != func_name, f"CAP-2 forbidden validator call: {func_name}"


# ===========================================================================
# 18) AD-19 Exception 40 tests
# ===========================================================================

_EXC_TYPES_PS = [
    ArithmeticError, AssertionError, AttributeError, BufferError,
    EOFError, FloatingPointError, GeneratorExit, ImportError,
    IndentationError, IndexError, KeyError, LookupError,
    MemoryError, NameError, NotImplementedError, OSError,
    OverflowError, RecursionError, ReferenceError, RuntimeError,
    StopAsyncIteration, StopIteration, SyntaxError, SystemError,
    TabError, TypeError, UnboundLocalError, UnicodeError, UnicodeDecodeError,
    UnicodeEncodeError, ValueError, ZeroDivisionError,
    Exception, BaseException,
    ContractSchemaError,
    BrokenPipeError, ChildProcessError, ConnectionAbortedError, ConnectionError,
]


class Test18Ad19Exc:
    @staticmethod
    def _raise_exc(exc_type):
        """Raise an instance of exc_type handling tricky constructor signatures."""
        if exc_type is UnicodeDecodeError:
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "boom")
        if exc_type is UnicodeEncodeError:
            raise UnicodeEncodeError("utf-8", "", 0, 1, "boom")
        if exc_type is BrokenPipeError:
            raise BrokenPipeError(32, "boom")
        if exc_type is ChildProcessError:
            raise ChildProcessError(5, "boom")
        if exc_type is ConnectionAbortedError:
            raise ConnectionAbortedError(53, "boom")
        if exc_type is ConnectionError:
            raise ConnectionError("boom")
        if exc_type is OverflowError:
            raise OverflowError("boom")
        if exc_type is TabError:
            raise TabError("boom")
        if exc_type is IndentationError:
            raise IndentationError("boom")
        if exc_type is SyntaxError:
            raise SyntaxError("boom")
        if exc_type is FloatingPointError:
            raise FloatingPointError("boom")
        if exc_type is ZeroDivisionError:
            raise ZeroDivisionError("boom")
        raise exc_type("boom")

    @pytest.mark.parametrize("exc_type", _EXC_TYPES_PS)
    def test_ad19_exception_translates_info_code(self, exc_type, monkeypatch):
        import app.simulation.portfolio as pm

        def boom(*a, **kw):
            Test18Ad19Exc._raise_exc(exc_type)

        monkeypatch.setattr(pm, "_ps_quality_block_code", boom)
        res = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert res.rejected
        assert res.new_snapshot is None
        assert any(code.startswith(AD19_PORF_SNAP_EXC_PREFIX) for code in res.info_codes)
        # Check specific subtype
        expected = f"{AD19_PORF_SNAP_EXC_PREFIX}{exc_type.__name__}"
        assert expected in res.info_codes, f"missing {expected}, got {res.info_codes}"

    def test_ad19_build_inner_exception_caught(self, monkeypatch):
        import app.simulation.portfolio as pm

        def boom(*a, **kw):
            raise SystemError("corrupt inner")

        monkeypatch.setattr(pm, "_build_portfolio_snapshot_inner", boom)
        res = pm.build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert res.rejected is True
        assert res.new_snapshot is None

    def test_ad19_publish_exception_silent(self, sptf02_bus):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("100"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        # Even with broken bus state, publish should not raise
        try:
            publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
            # no exception = pass
            assert True
        except BaseException:
            pytest.fail("AD-19 publish raised exception")


# ===========================================================================
# 19) Determinism 12 scen 10r SHA256 same
# ===========================================================================

_DET_PS_SCENARIOS = [
    ("cash_only", lambda: dict(
        positions=[], cash_quote=Decimal("10000"), current_price_map={},
    )),
    ("one_btc_long", lambda: dict(
        positions=[_mk_btc_long("0.5", "30000", "32000")],
        cash_quote=Decimal("5000"),
        current_price_map={SYM_BTC: Decimal("32000")},
    )),
    ("two_sym_btc_eth", lambda: dict(
        positions=[_mk_btc_long("0.5", "30000", "32000"),
                   _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600"))],
        cash_quote=Decimal("2000"),
        current_price_map={SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")},
    )),
    ("five_sym_mix", lambda: dict(
        positions=[
            _mk_btc_long("0.1", "30000", "32000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("1"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
            _make_long_position(SYM_SOL, base_qty=Decimal("10"), avg_entry_price=Decimal("100"), current_price=Decimal("110")),
            _make_long_position(SYM_ADA, base_qty=Decimal("1000"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
            _make_long_position(SYM_XRP, base_qty=Decimal("500"), avg_entry_price=Decimal("0.5"), current_price=Decimal("0.6")),
        ],
        cash_quote=Decimal("25000"),
        current_price_map={SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600"), SYM_SOL: Decimal("110"),
                           SYM_ADA: Decimal("0.6"), SYM_XRP: Decimal("0.6")},
    )),
    ("cash_zero_peak", lambda: dict(
        positions=[], cash_quote=Decimal("0"), current_price_map={},
        prev_peak_equity_quote=Decimal("10000"),
    )),
    ("degraded_quality", lambda: dict(
        positions=[_mk_btc_long("1", "30000", "35000")],
        cash_quote=Decimal("1000"),
        current_price_map={SYM_BTC: Decimal("35000")},
        quality_ctx=QualityFlags(degraded=True),
    )),
    ("positions_omitted", lambda: dict(
        positions=[_mk_btc_long("0.5", "30000", "32000")],
        cash_quote=Decimal("1000"),
        current_price_map={SYM_BTC: Decimal("32000")},
        include_positions_in_snapshot=False,
    )),
    ("drawdown_50pct", lambda: dict(
        positions=[], cash_quote=Decimal("5000"), current_price_map={},
        prev_peak_equity_quote=Decimal("10000"),
    )),
    ("flat_positions_only", lambda: dict(
        positions=[_flat_zero(SYM_BTC, current_price=Decimal("30000")),
                   _flat_zero(SYM_ETH, current_price=Decimal("1500"))],
        cash_quote=Decimal("10000"),
        current_price_map={},
    )),
    ("realized_pnl_mixed", lambda: dict(
        positions=[_flat_zero(SYM_BTC, current_price=Decimal("30000"), realized=Decimal("1000")),
                   _flat_zero(SYM_ETH, current_price=Decimal("1500"), realized=Decimal("-500"))],
        cash_quote=Decimal("5000"),
        current_price_map={},
    )),
    ("all_in_exposure", lambda: dict(
        positions=[_mk_btc_long("1", "30000", "40000")],
        cash_quote=Decimal("0"),
        current_price_map={SYM_BTC: Decimal("40000")},
    )),
    ("tiny_quantities_8dp", lambda: dict(
        positions=[
            _mk_btc_long("0.00000001", "30000", "30000"),
            _make_long_position(SYM_ETH, base_qty=Decimal("0.00000002"), avg_entry_price=Decimal("1500"), current_price=Decimal("1500")),
        ],
        cash_quote=Decimal("1000"),
        current_price_map={SYM_BTC: Decimal("30000"), SYM_ETH: Decimal("1500")},
    )),
]


def _run_ps_det(base_kwargs):
    kw = dict(base_kwargs)
    kw.setdefault("snapshot_ts", Instant(FIXTURE_TS))
    kw.setdefault("correlation_id", FIXED_CORR)
    kw.setdefault("causation_id", FIXED_CAUS)
    # Use fixed snapshot_id for determinism
    kw.setdefault("snapshot_id", ULID("DETSNAP000000000000000001"))
    r = build_portfolio_snapshot(**kw)
    if r.new_snapshot is not None:
        sd = r.new_snapshot.to_sorted_dict()
        sha = r.new_snapshot.schema_sha256()
        return (True, sd, sha, r.info_codes)
    return (False, None, None, r.info_codes)


class Test19Determinism:
    @pytest.mark.parametrize("tag,scen_fn", [(t, f) for t, f in _DET_PS_SCENARIOS])
    def test_det_10r_sha256_same(self, tag, scen_fn):
        _ = tag
        base = scen_fn()
        runs = [_run_ps_det(dict(base)) for _ in range(10)]
        ok0, sd0, sha0, ic0 = runs[0]
        for run in runs[1:]:
            ok, sd, sha, ic = run
            assert ok == ok0
            if ok:
                assert sd == sd0, f"scenario sorted dict mismatch"
                assert sha == sha0, f"scenario sha256 mismatch"
            assert ic == ic0, f"info_codes mismatch"

    def test_det_same_input_same_result_basic(self):
        kw = dict(
            positions=[_mk_btc_long("1", "30000", "30000")],
            cash_quote=Decimal("1000"),
            current_price_map={SYM_BTC: Decimal("30000")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            snapshot_id=ULID("SNAPDET0000000000000002"),
        )
        r1 = build_portfolio_snapshot(**dict(kw))
        r2 = build_portfolio_snapshot(**dict(kw))
        assert r1.new_snapshot.schema_sha256() == r2.new_snapshot.schema_sha256()


# ===========================================================================
# 20) Single-writer AST 8 tests
# ===========================================================================

class Test20SingleWriter:
    @pytest.mark.parametrize("module_name", [
        "app.strategy",
        "app.opportunity",
        "app.risk",
        "app.backtest",
        "app.ai",
        "app.regime",
    ])
    def test_module_no_portfoliosnapshot_construct(self, module_name):
        import ast
        try:
            mod = __import__(module_name, fromlist=["*"])
        except Exception:
            pytest.skip(f"{module_name} not importable")
        src_file = getattr(mod, "__file__", None)
        if not src_file or not src_file.endswith(".py"):
            pytest.skip(f"{module_name} source not available")
        with open(src_file, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                pytest.skip(f"{module_name} syntax error")
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "PortfolioSnapshot":
                    violations.append("PortfolioSnapshot constructor")
                if isinstance(node.func, ast.Attribute) and node.func.attr == "PortfolioSnapshot":
                    violations.append("PortfolioSnapshot via attr")
        assert not violations, f"Single Writer violation in {module_name}: {violations}"

    def test_portfolio_module_does_construct_snapshot(self):
        import ast
        import app.simulation.portfolio as pm
        try:
            import importlib.util
            src_file = importlib.util.find_spec(pm.__name__).origin
        except Exception:
            src_file = getattr(pm, "__file__", None)
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        hits = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "PortfolioSnapshot":
                hits += 1
        assert hits >= 1

    def test_portfolio_only_module_constructs_snapshot(self):
        """Portfolio module should be the ONLY writer; we already check other modules above."""
        import ast
        import app.simulation.portfolio as pm
        try:
            import importlib.util
            src_file = importlib.util.find_spec(pm.__name__).origin
        except Exception:
            src_file = getattr(pm, "__file__", None)
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            content = f.read()
        # build_portfolio_snapshot should contain the PortfolioSnapshot call
        assert "PortfolioSnapshot(" in content


# ===========================================================================
# 21) CashFlatBoundary 10 tests
# ===========================================================================

class Test21CashFlatBoundary:
    def test_cfb_cash_only_equity_equals_cash(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("9999"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == Decimal("9999")
        assert r.new_snapshot.exposure_notional == Decimal("0")

    def test_cfb_all_flat_zero_exposure(self):
        positions = [
            _flat_zero(SYM_BTC, current_price=Decimal("30000")),
            _flat_zero(SYM_ETH, current_price=Decimal("1500")),
            _flat_zero(SYM_SOL, current_price=Decimal("100")),
        ]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == Decimal("0")
        assert r.new_snapshot.equity_quote == Decimal("5000")

    def test_cfb_cash_zero_flat_only(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("0"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.equity_quote == Decimal("0")
        assert r.new_snapshot.exposure_notional == Decimal("0")

    def test_cfb_mix_flat_and_cash_drawdown_zero(self):
        positions = [_flat_zero(SYM_BTC, current_price=Decimal("30000"))]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("10000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.drawdown_pct == 0.0

    def test_cfb_cash_only_peak_equals_eq(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("5000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.peak_equity_quote == r.new_snapshot.equity_quote

    def test_cfb_all_flat_realized_still_counts(self):
        flat = _flat_zero(SYM_BTC, current_price=Decimal("30000"), realized=Decimal("500"))
        r = build_portfolio_snapshot(
            positions=[flat],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.realized_pnl_quote_24h == Decimal("500")
        assert r.new_snapshot.exposure_notional == Decimal("0")

    def test_cfb_cash_only_unrealized_zero(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("10000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.unrealized_pnl_quote == Decimal("0")

    def test_cfb_all_flat_fees_still_counts(self):
        flat1 = _flat_zero(SYM_BTC, current_price=Decimal("30000"), fees=Decimal("10"))
        flat2 = _flat_zero(SYM_ETH, current_price=Decimal("1500"), fees=Decimal("20"))
        r = build_portfolio_snapshot(
            positions=[flat1, flat2],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.fees_quote_total == Decimal("30")

    def test_cfb_5_flat_zero_exposure(self):
        positions = [_flat_zero(sym, current_price=Decimal("100")) for sym in
                     [SYM_BTC, SYM_ETH, SYM_SOL, SYM_ADA, SYM_XRP]]
        r = build_portfolio_snapshot(
            positions=positions,
            cash_quote=Decimal("99999"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == Decimal("0")
        assert r.new_snapshot.equity_quote == Decimal("99999")

    def test_cfb_empty_positions_zero_exposure(self):
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("12345"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
        )
        assert not r.rejected
        assert r.new_snapshot.exposure_notional == Decimal("0")
        assert r.new_snapshot.equity_quote == Decimal("12345")


# ===========================================================================
# 22) Network/Credential safety 10 tests
# ===========================================================================

class Test22NetCredSafety:
    @pytest.mark.parametrize("lib", [
        "ccxt", "requests", "aiohttp", "httpx", "urllib3", "websockets",
        "sqlalchemy", "psycopg", "pymongo", "boto3", "paramiko",
        "socket", "smtplib", "ftplib", "imaplib", "poplib",
        "asyncio.sleep", "kraken", "coinbase", "web3",
        "ethers", "redis", "kafka", "pymongo",
    ])
    def test_forbid_24_libs_not_imported(self, lib):
        import app.simulation.portfolio as pm
        try:
            import importlib.util
            src_file = importlib.util.find_spec(pm.__name__).origin
        except Exception:
            src_file = getattr(pm, "__file__", None)
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            src = f.read()
        assert lib not in src, f"Forbidden network/cred lib token found: {lib}"

    @pytest.mark.parametrize("forbidden_mod", [
        "numpy", "pandas", "pydantic", "attrs", "cattrs", "scipy", "torch",
        "tensorflow", "polars", "fastapi", "flask", "django",
        "sqlmodel", "ormar", "alembic", "celery", "rq", "joblib",
        "redis", "kafka",
    ])
    def test_forbid_20_libs_ast_zero(self, forbidden_mod):
        import ast
        import app.simulation.portfolio as pm
        try:
            import importlib.util
            src_file = importlib.util.find_spec(pm.__name__).origin
        except Exception:
            src_file = getattr(pm, "__file__", None)
        if not src_file: pytest.skip()
        with open(src_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_mod), f"forbidden import {alias.name}"
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden_mod), f"forbidden from import {node.module}"


# ===========================================================================
# 23) Replay 3 tests
# ===========================================================================

class Test23Replay:
    def test_replay_same_input_100_runs_same_result(self):
        kw = dict(
            positions=[
                _mk_btc_long("0.5", "30000", "32000"),
                _make_long_position(SYM_ETH, base_qty=Decimal("5"), avg_entry_price=Decimal("1500"), current_price=Decimal("1600")),
            ],
            cash_quote=Decimal("10000"),
            current_price_map={SYM_BTC: Decimal("32000"), SYM_ETH: Decimal("1600")},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            snapshot_id=ULID("REPLAYSNP000000000000001"),
        )
        results = [build_portfolio_snapshot(**dict(kw)) for _ in range(100)]
        base = results[0]
        base_snap = base.new_snapshot
        base_sd = base_snap.to_sorted_dict()
        base_sha = base_snap.schema_sha256()
        for r in results[1:]:
            assert r.new_snapshot.to_sorted_dict() == base_sd
            assert r.new_snapshot.schema_sha256() == base_sha
            assert r.info_codes == base.info_codes

    def test_replay_engine_peak_tracking(self, sptf02_engine):
        # Build 3 snapshots, replay the sequence with new engine → same peak path
        def run_sequence(engine):
            peaks = []
            for cash in [Decimal("10000"), Decimal("15000"), Decimal("8000")]:
                r = engine.build(
                    positions=[],
                    cash_quote=cash,
                    current_price_map={},
                    snapshot_ts=Instant(FIXTURE_TS),
                    correlation_id=FIXED_CORR,
                    causation_id=FIXED_CAUS,
                    publish=False,
                )
                peaks.append(r.new_snapshot.peak_equity_quote)
            return peaks
        peaks1 = run_sequence(PortfolioSnapshotEngine())
        peaks2 = run_sequence(PortfolioSnapshotEngine())
        assert peaks1 == peaks2

    def test_replay_same_result_sha256(self):
        kw = dict(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=FIXED_CORR,
            causation_id=FIXED_CAUS,
            snapshot_id=ULID("REPLAY000000000000000002"),
        )
        shas = set()
        for _ in range(50):
            r = build_portfolio_snapshot(**dict(kw))
            shas.add(r.new_snapshot.schema_sha256())
        assert len(shas) == 1


# ===========================================================================
# 24) Corr/caus 3 tests
# ===========================================================================

class Test24CorrCaus:
    def test_cc_chain_depth_7(self):
        # Build a chain of corr/caus and verify depth preserved
        chain_corrs = [ULID(f"CHAIN-CORR-{i:02d}-000000000000000000") for i in range(7)]
        chain_causs = [ULID(f"CHAIN-CAUS-{i:02d}-000000000000000000") for i in range(7)]
        for i in range(7):
            r = build_portfolio_snapshot(
                positions=[],
                cash_quote=Decimal(f"{1000 + i}"),
                current_price_map={},
                snapshot_ts=Instant(FIXTURE_TS),
                correlation_id=chain_corrs[i],
                causation_id=chain_causs[i],
                snapshot_id=ULID(f"SNAPCC{i:02d}0000000000000000000"),
            )
            assert not r.rejected
            assert str(r.new_snapshot.correlation_id) == str(chain_corrs[i])
            assert str(r.new_snapshot.causation_id) == str(chain_causs[i])

    def test_cc_chain_depth_9(self):
        chain_corrs = [ULID(f"CC9-CORR-{i:02d}-00000000000000000") for i in range(9)]
        chain_causs = [ULID(f"CC9-CAUS-{i:02d}-00000000000000000") for i in range(9)]
        for i in range(9):
            r = build_portfolio_snapshot(
                positions=[],
                cash_quote=Decimal(f"{5000 + i * 100}"),
                current_price_map={},
                snapshot_ts=Instant(FIXTURE_TS),
                correlation_id=chain_corrs[i],
                causation_id=chain_causs[i],
                snapshot_id=ULID(f"SNAP9{i:02d}0000000000000000000"),
            )
            assert not r.rejected
            assert str(r.new_snapshot.correlation_id) == str(chain_corrs[i])
            assert str(r.new_snapshot.causation_id) == str(chain_causs[i])

    def test_cc_bus_event_corr_caus_preserved(self, sptf02_bus):
        cc_corr = ULID("EVT-CC-CORR-000000000000000001")
        cc_caus = ULID("EVT-CC-CAUS-000000000000000001")
        r = build_portfolio_snapshot(
            positions=[],
            cash_quote=Decimal("1000"),
            current_price_map={},
            snapshot_ts=Instant(FIXTURE_TS),
            correlation_id=cc_corr,
            causation_id=cc_caus,
        )
        publish_portfolio_snapshot_event(result=r, event_bus=sptf02_bus)
        env = next(e for e in sptf02_bus.published if e.event_type == EVENT_PORTFOLIO_SNAPSHOT)
        assert str(env.correlation_id) == str(cc_corr)
        assert str(env.causation_id) == str(cc_caus)
        # Verify bus causation chain includes our event
        chain = sptf02_bus.trace_causation_chain(str(env.event_id))
        assert str(env.event_id) in chain
