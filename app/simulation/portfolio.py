from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from app.contracts import (
    CONTRACT_VERSION,
    ClockRef,
    ContractSchemaError,
    PaperFill,
    PaperOrderSide,
    PortfolioSnapshot,
    Position,
    PositionSide,
    QualityFlags,
    RunMode,
    SourceType,
    Symbol,
    ULID,
    format_instant,
)
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    SchemaRef,
)
from app.contracts.types import Instant, Symbol, ULID, validate_instant, validate_symbol_canonical
from app.platform.event_bus import InMemoryTypedEventBus


_QUANTIZE_8DP = Decimal("0.00000001")
_ONE = Decimal("1")


# ---------------------------------------------------------------------------
# Info / reject codes
# ---------------------------------------------------------------------------

G1_INPUT_INVALID = "G1_INPUT_INVALID"
G2_SYMBOL_MISMATCH = "G2_SYMBOL_MISMATCH"
G2_PREVIOUS_CORRUPTED = "G2_PREVIOUS_CORRUPTED"
G3_Q_STALE = "G3_Q_STALE"
G3_Q_INVALID = "G3_Q_INVALID"
G3_Q_QUARANTINED = "G3_Q_QUARANTINED"
G3_Q_DUP = "G3_Q_DUP"
G3_Q_OOO = "G3_Q_OOO"
G3_Q_MISSING = "G3_Q_MISSING"
G4_NO_POSITION = "G4_NO_POSITION"
G4_INVALID_SIDE = "G4_INVALID_SIDE"
Q1_SELL_EXCESS_IGNORED = "Q1_SELL_EXCESS_IGNORED"
AD19_POS_TRANSITION_EXC_PREFIX = "AD19_POS_TRANSITION_EXC:"
AD19_PORF_SNAP_EXC_PREFIX = "AD19_PORF_SNAP_EXC:"
PS_G1_INVALID = "PS_G1_INVALID"
PS_G2_Q_STALE = "PS_G2_Q_STALE"
PS_G2_Q_INVALID = "PS_G2_Q_INVALID"
PS_G2_Q_QUARANTINED = "PS_G2_Q_QUARANTINED"
PS_G2_Q_DUP = "PS_G2_Q_DUP"
PS_G2_Q_OOO = "PS_G2_Q_OOO"
PS_G2_Q_MISSING = "PS_G2_Q_MISSING"
PS_G3_PRICE_MISSING = "PS_G3_PRICE_MISSING"
PS_G3_PRICE_NON_POS = "PS_G3_PRICE_NON_POS"
PS_G3_PRICE_TYPE = "PS_G3_PRICE_TYPE"
PS_V1_EQUITY_MISMATCH = "PS_V1_EQUITY_MISMATCH"
PS_V1_EXPOSURE_OVER = "PS_V1_EXPOSURE_OVER"
PS_V1_PEAK_BEFORE = "PS_V1_PEAK_BEFORE"
PS_INFO_Q_DEGRADED = "PS_INFO_Q_DEGRADED"
PS_INFO_POS_INCLUDED = "PS_INFO_POS_INCLUDED"
PS_INFO_POS_OMITTED = "PS_INFO_POS_OMITTED"
PS_INFO_FIRST_SNAPSHOT = "PS_INFO_FIRST_SNAPSHOT"


# ---------------------------------------------------------------------------
# Public typed event names
# ---------------------------------------------------------------------------

EVENT_POSITION_UPDATED = "position_updated.v1"
EVENT_POSITION_TRANSITION_REJECTED = "position_transition_rejected.v1"
EVENT_PORTFOLIO_SNAPSHOT = "portfolio_snapshot.v1"
EVENT_PORTFOLIO_SNAPSHOT_REJECTED = "portfolio_snapshot_rejected.v1"


# ---------------------------------------------------------------------------
# Apply fill result
# ---------------------------------------------------------------------------

@dataclass
class PositionEngineResult:
    """Deterministic apply_fill çıktısı. Transition NO ise new_position == previous (None ise None)."""

    previous_position: Position | None
    new_position: Position | None
    rejected: bool
    info_codes: list[str] = field(default_factory=list)
    transition_type: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_decimal_positive(v: object) -> bool:
    return isinstance(v, Decimal) and not isinstance(v, bool) and v > 0


def _is_decimal_nonneg(v: object) -> bool:
    return isinstance(v, Decimal) and not isinstance(v, bool) and v >= 0


def _q8(v: Decimal) -> Decimal:
    return v.quantize(_QUANTIZE_8DP, rounding=ROUND_HALF_EVEN)


def _symbol_from_fill(pf: PaperFill) -> Symbol | None:
    """PaperFill.da symbol alanı yok; symbol'ü çağırıcı (apply_fill symbol kw) veya previous positiondan çıkar."""
    return None


def _make_corrupted_state_result(
    prev: Position | None,
    code: str,
) -> PositionEngineResult:
    return PositionEngineResult(
        previous_position=prev,
        new_position=prev,
        rejected=True,
        info_codes=[code],
        transition_type="reject",
    )


def _exposure_calc(qty: Decimal, price: Decimal) -> Decimal:
    if not _is_decimal_positive(price):
        return Decimal("0")
    if not _is_decimal_nonneg(qty):
        return Decimal("0")
    return _q8(qty * price)


# ---------------------------------------------------------------------------
# Flat / zero initial state
# ---------------------------------------------------------------------------

def zero_flat_position(
    *,
    symbol: Symbol,
    position_id: str,
    ts: Instant,
    correlation_id: str,
    causation_id: str,
    current_price: Decimal,
    realized_pnl_quote: Decimal = Decimal("0"),
    fees_quote: Decimal = Decimal("0"),
) -> Position:
    if not validate_symbol_canonical(symbol):
        raise ContractSchemaError(f"zero_flat_position: symbol not canonical {symbol!r}")
    if not _is_decimal_positive(current_price):
        raise ContractSchemaError("zero_flat_position: current_price must be > 0 Decimal")
    return Position(
        position_id=ULID(position_id),
        symbol=Symbol(symbol),
        side=PositionSide.FLAT,
        base_qty=Decimal("0"),
        avg_entry_price=Decimal("0"),
        current_price=current_price,
        unrealized_pnl_quote=Decimal("0"),
        realized_pnl_quote=realized_pnl_quote,
        fees_quote=fees_quote,
        opened_ts=Instant(ts),
        last_updated_ts=Instant(ts),
        open_refs=[],
        correlation_id=ULID(correlation_id),
        causation_id=ULID(causation_id),
    )


# ---------------------------------------------------------------------------
# Core pure transition (AD-20 deterministic)
# ---------------------------------------------------------------------------

def _quality_block_code(qf: QualityFlags | None) -> str | None:
    if qf is None:
        return None
    if getattr(qf, "stale", False):
        return G3_Q_STALE
    if getattr(qf, "invalid", False):
        return G3_Q_INVALID
    if getattr(qf, "quarantined", False):
        return G3_Q_QUARANTINED
    if getattr(qf, "duplicate", False):
        return G3_Q_DUP
    if getattr(qf, "out_of_order", False):
        return G3_Q_OOO
    if getattr(qf, "missing", False):
        return G3_Q_MISSING
    return None


def apply_fill(
    prev_position: Position | None,
    paper_fill: PaperFill,
    *,
    symbol: Symbol,
    current_price: Decimal,
    quality_ctx: QualityFlags | None = None,
    clock_ref: ClockRef | None = None,
    position_id_new: str | None = None,
) -> PositionEngineResult:
    """Deterministic transition: PaperFill + previous Position (or None) → new Position (or same if rejected).

    AD-19 fail-closed: her exception → döner previous unchanged + AD19_* info code.
    """
    try:
        return _apply_fill_inner(
            prev_position,
            paper_fill,
            symbol=symbol,
            current_price=current_price,
            quality_ctx=quality_ctx,
            clock_ref=clock_ref,
            position_id_new=position_id_new,
        )
    except BaseException as exc:  # noqa: BLE001 - AD-19 outer fail-closed
        code = f"{AD19_POS_TRANSITION_EXC_PREFIX}{type(exc).__name__}"
        return _make_corrupted_state_result(prev_position, code)


def _apply_fill_inner(
    prev_position: Position | None,
    paper_fill: PaperFill,
    *,
    symbol: Symbol,
    current_price: Decimal,
    quality_ctx: QualityFlags | None,
    clock_ref: ClockRef | None,
    position_id_new: str | None,
) -> PositionEngineResult:
    ts_now = paper_fill.fill_ts

    # ---- G1 Input Validation -------------------------------------------------
    if not isinstance(paper_fill, PaperFill):
        return _make_corrupted_state_result(prev_position, G1_INPUT_INVALID)
    if not (
        _is_decimal_positive(paper_fill.fill_price)
        and _is_decimal_positive(paper_fill.fill_qty_base)
        and _is_decimal_positive(paper_fill.fees_quote)
    ):
        return _make_corrupted_state_result(prev_position, G1_INPUT_INVALID)
    if paper_fill.side not in (PaperOrderSide.BUY, PaperOrderSide.SELL):
        return _make_corrupted_state_result(prev_position, G1_INPUT_INVALID)
    if not _is_decimal_positive(current_price):
        return _make_corrupted_state_result(prev_position, G1_INPUT_INVALID)
    if not validate_symbol_canonical(symbol):
        return _make_corrupted_state_result(prev_position, G1_INPUT_INVALID)

    # ---- G2 Previous Position Init (or Zero-State) --------------------------
    effective_prev: Position | None
    if prev_position is None:
        try:
            effective_prev = zero_flat_position(
                symbol=symbol,
                position_id=ULID(position_id_new) if position_id_new else ULID(f"P{paper_fill.paper_fill_id}"),
                ts=Instant(ts_now),
                correlation_id=str(paper_fill.correlation_id),
                causation_id=str(paper_fill.paper_fill_id),
                current_price=Decimal(current_price),
            )
        except BaseException:
            return _make_corrupted_state_result(prev_position, G2_PREVIOUS_CORRUPTED)
    else:
        if not isinstance(prev_position, Position):
            return _make_corrupted_state_result(prev_position, G2_PREVIOUS_CORRUPTED)
        if str(prev_position.symbol) != str(symbol):
            return _make_corrupted_state_result(prev_position, G2_SYMBOL_MISMATCH)
        effective_prev = prev_position

    # ---- G3 Quality Gate (CAP-2 fail-safe) ----------------------------------
    q_block = _quality_block_code(quality_ctx)
    info_codes: list[str] = []
    if q_block is not None:
        return PositionEngineResult(
            previous_position=prev_position,
            new_position=prev_position,
            rejected=True,
            info_codes=[q_block],
            transition_type="reject",
        )
    if quality_ctx is not None and getattr(quality_ctx, "degraded", False):
        info_codes.append("INFO_Q_DEGRADED_ACCEPTED")

    # ---- G4 Directional Safety ----------------------------------------------
    side = paper_fill.side
    prev_qty = Decimal(effective_prev.base_qty)
    if side == PaperOrderSide.SELL and prev_qty == Decimal("0"):
        return PositionEngineResult(
            previous_position=prev_position,
            new_position=prev_position,
            rejected=True,
            info_codes=[G4_NO_POSITION],
            transition_type="reject",
        )
    if side not in (PaperOrderSide.BUY, PaperOrderSide.SELL):
        return PositionEngineResult(
            previous_position=prev_position,
            new_position=prev_position,
            rejected=True,
            info_codes=[G4_INVALID_SIDE],
            transition_type="reject",
        )

    # ---- Q1 Closed Qty / Lifecycle routing ----------------------------------
    fill_qty = Decimal(paper_fill.fill_qty_base)
    transition_type: str
    if side == PaperOrderSide.BUY:
        added_qty = fill_qty
        closed_qty = Decimal("0")
        remaining_qty = prev_qty + added_qty
        transition_type = "buy_add" if prev_qty > 0 else "open_new_buy"
    else:  # SELL
        added_qty = Decimal("0")
        closed_qty = min(fill_qty, prev_qty)
        remaining_qty = prev_qty - closed_qty
        if closed_qty != fill_qty:
            info_codes.append(Q1_SELL_EXCESS_IGNORED)
        if remaining_qty == Decimal("0"):
            transition_type = "full_close_sell"
        else:
            transition_type = "reduce_sell"

    # ---- Q2 Weighted Avg Price (BUY yönü) -----------------------------------
    old_avg = Decimal(effective_prev.avg_entry_price)
    if side == PaperOrderSide.BUY:
        if prev_qty == Decimal("0"):
            new_avg = Decimal(paper_fill.fill_price)
        else:
            num = prev_qty * old_avg + added_qty * Decimal(paper_fill.fill_price)
            den = prev_qty + added_qty
            new_avg = _q8(num / den)
    else:  # SELL → avg unchanged, FLAT reset to 0
        if remaining_qty == Decimal("0"):
            new_avg = Decimal("0")
        else:
            new_avg = old_avg

    # ---- Q3 Realized PnL (SELL yönü) ----------------------------------------
    new_realized = Decimal(effective_prev.realized_pnl_quote)
    if side == PaperOrderSide.SELL and closed_qty > Decimal("0"):
        gross_realized = (Decimal(paper_fill.fill_price) - old_avg) * closed_qty
        net_realized = gross_realized - Decimal(paper_fill.fees_quote)
        new_realized = new_realized + net_realized

    # ---- Q4 Fee Accumulation ------------------------------------------------
    new_fees = Decimal(effective_prev.fees_quote) + Decimal(paper_fill.fees_quote)

    # ---- Side decision ------------------------------------------------------
    new_side = PositionSide.LONG if remaining_qty > Decimal("0") else PositionSide.FLAT

    # ---- Exposure (extra için hesapla — Position alanı YOK, envelope extra'ya yazılır)
    exposure_notional = _exposure_calc(remaining_qty, Decimal(current_price))

    # ---- Q5 Unrealized PnL --------------------------------------------------
    if remaining_qty == Decimal("0") or new_avg == Decimal("0"):
        new_unrealized = Decimal("0")
    else:
        new_unrealized = (Decimal(current_price) - new_avg) * remaining_qty

    # ---- open_refs -----------------------------------------------------------
    if transition_type == "full_close_sell":
        new_open_refs: list[str] = []
    else:
        new_open_refs = list(effective_prev.open_refs)
        new_open_refs.append(str(paper_fill.paper_fill_id))

    # ---- T1 Position Contract Finalize --------------------------------------
    if new_side == PositionSide.FLAT:
        final_avg = Decimal("0")
        final_qty = Decimal("0")
    else:
        final_avg = _q8(new_avg)
        final_qty = remaining_qty

    # Invariant: FLAT ↔ base_qty=0 (Position.__post_init__ tekrar kontrol eder)
    opened_ts = Instant(effective_prev.opened_ts)
    if effective_prev.side == PositionSide.FLAT and (transition_type == "open_new_buy"):
        opened_ts = Instant(ts_now)

    new_position = Position(
        position_id=ULID(position_id_new) if position_id_new else effective_prev.position_id,
        symbol=Symbol(symbol),
        side=new_side,
        base_qty=final_qty,
        avg_entry_price=final_avg,
        current_price=Decimal(current_price),
        unrealized_pnl_quote=new_unrealized,
        realized_pnl_quote=new_realized,
        fees_quote=new_fees,
        opened_ts=opened_ts,
        last_updated_ts=Instant(ts_now),
        open_refs=new_open_refs,
        correlation_id=ULID(str(paper_fill.correlation_id)),
        causation_id=ULID(str(paper_fill.paper_fill_id)),
    )

    # Extra'larda exposure + info kodları publish için dönülebilir
    result = PositionEngineResult(
        previous_position=prev_position,
        new_position=new_position,
        rejected=False,
        info_codes=info_codes,
        transition_type=transition_type,
    )
    # exposure (hesaplandı ama caller publish_position_event kullanmak zorunda)
    object.__setattr__(result, "_exposure_notional", exposure_notional)
    return result


# ---------------------------------------------------------------------------
# Publish to typed event bus (position_updated.v1)
# ---------------------------------------------------------------------------

def publish_position_event(
    *,
    result: PositionEngineResult,
    paper_fill: PaperFill,
    event_bus: InMemoryTypedEventBus | None,
    symbol: Symbol,
    quality_ctx: QualityFlags | None = None,
    clock_ref: ClockRef | None = None,
) -> None:
    if event_bus is None:
        return
    try:
        ts_now = paper_fill.fill_ts
        qf = quality_ctx or QualityFlags()
        cr = clock_ref or ClockRef(wall=Instant(ts_now))

        if not result.rejected and result.new_position is not None:
            new_pos = result.new_position
            extra: dict[str, Any] = {
                "transition_type": result.transition_type,
                "info_codes": list(result.info_codes),
                "exposure_notional": str(getattr(result, "_exposure_notional", new_pos.base_qty * new_pos.current_price)),
            }
            envelope = CanonicalEventEnvelope(
                event_id=ULID(f"E{new_pos.position_id}"),
                event_type=EVENT_POSITION_UPDATED,
                contract_version=CONTRACT_VERSION,
                symbol=Symbol(symbol) if validate_symbol_canonical(symbol) else None,
                source="s.simulation.portfolio.position_engine",
                timestamp=Instant(ts_now),
                ingest_ts=Instant(ts_now),
                correlation_id=ULID(str(paper_fill.correlation_id)),
                causation_id=ULID(str(paper_fill.paper_fill_id)),
                run_mode=RunMode.PAPER,
                source_type=SourceType.SIMULATED,
                clock_ref=cr,
                quality_flags=qf,
                schema_ref=SchemaRef(),
                extra=extra,
                payload=new_pos,
            )
            event_bus.publish_with_causation(envelope, parent_event_id=str(paper_fill.paper_fill_id))
        else:
            extra = {
                "transition_type": result.transition_type,
                "info_codes": list(result.info_codes),
                "previous_position_id": str(result.previous_position.position_id) if result.previous_position else None,
                "paper_fill_id": str(paper_fill.paper_fill_id),
            }
            envelope = CanonicalEventEnvelope(
                event_id=ULID(f"REJ{paper_fill.paper_fill_id}"),
                event_type=EVENT_POSITION_TRANSITION_REJECTED,
                contract_version=CONTRACT_VERSION,
                symbol=Symbol(symbol) if validate_symbol_canonical(symbol) else None,
                source="s.simulation.portfolio.position_engine",
                timestamp=Instant(ts_now),
                ingest_ts=Instant(ts_now),
                correlation_id=ULID(str(paper_fill.correlation_id)),
                causation_id=ULID(str(paper_fill.paper_fill_id)),
                run_mode=RunMode.PAPER,
                source_type=SourceType.SIMULATED,
                clock_ref=cr,
                quality_flags=qf,
                schema_ref=SchemaRef(),
                extra=extra,
                payload=None,
            )
            event_bus.publish_with_causation(envelope, parent_event_id=str(paper_fill.paper_fill_id))
    except BaseException:
        # AD-19: publish aşaması exception → DLQ bus kendi handler edecek; biz propagate etmiyoruz.
        return


# ---------------------------------------------------------------------------
# PositionEngine (stateful container — next dev story büyürken kullanılır)
# ---------------------------------------------------------------------------

class PositionEngine:
    """Single-writer (AD-7/13/24): Position üretir, doğrular, bus'a publish eder.

    Deterministic. No datetime.now, no run_mode branch, no network.
    """

    def __init__(
        self,
        *,
        event_bus: InMemoryTypedEventBus | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.positions: dict[Symbol, Position] = {}
        self.rejections: list[tuple[PaperFill, PositionEngineResult]] = []

    # ---- Convenience: current price helper — external caller'dan gelir ------
    def apply(
        self,
        paper_fill: PaperFill,
        *,
        symbol: Symbol,
        current_price: Decimal,
        quality_ctx: QualityFlags | None = None,
        clock_ref: ClockRef | None = None,
        publish: bool = True,
    ) -> PositionEngineResult:
        prev = self.positions.get(symbol)
        result = apply_fill(
            prev,
            paper_fill,
            symbol=symbol,
            current_price=current_price,
            quality_ctx=quality_ctx,
            clock_ref=clock_ref,
        )
        if not result.rejected and result.new_position is not None:
            self.positions[Symbol(symbol)] = result.new_position
        else:
            self.rejections.append((paper_fill, result))
        if publish:
            publish_position_event(
                result=result,
                paper_fill=paper_fill,
                event_bus=self.event_bus,
                symbol=symbol,
                quality_ctx=quality_ctx,
                clock_ref=clock_ref,
            )
        return result


# ===========================================================================
# §2: Portfolio Snapshot Engine (S-PTF-02)
# Single Writer PortfolioSnapshot (AD-7/13/24).
# Position state OKUNUR, MUTATE EDİLMEZ.
# ===========================================================================


@dataclass
class PortfolioSnapshotResult:
    """Deterministic build_portfolio_snapshot çıktısı. Reject ise snapshot None."""

    new_snapshot: PortfolioSnapshot | None
    rejected: bool
    info_codes: list[str] = field(default_factory=list)
    rejected_reason: str = ""


# ---------------------------------------------------------------------------
# Helpers (pure)
# ---------------------------------------------------------------------------

def _ps_quality_block_code(qf: QualityFlags | None) -> str | None:
    if qf is None:
        return None
    if getattr(qf, "stale", False):
        return PS_G2_Q_STALE
    if getattr(qf, "invalid", False):
        return PS_G2_Q_INVALID
    if getattr(qf, "quarantined", False):
        return PS_G2_Q_QUARANTINED
    if getattr(qf, "duplicate", False):
        return PS_G2_Q_DUP
    if getattr(qf, "out_of_order", False):
        return PS_G2_Q_OOO
    if getattr(qf, "missing", False):
        return PS_G2_Q_MISSING
    return None


def _ps_sorted_positions(positions: list[Position]) -> list[Position]:
    return sorted(positions, key=lambda p: str(p.symbol))


def _ps_is_decimal_nonneg(v: object) -> bool:
    return isinstance(v, Decimal) and not isinstance(v, bool) and v >= 0


def _ps_is_decimal_positive(v: object) -> bool:
    return isinstance(v, Decimal) and not isinstance(v, bool) and v > 0


def _ps_ulidish(v: object) -> bool:
    return isinstance(v, str) and len(v) >= 8


def _make_snapshot_reject(
    *,
    reason_code: str,
    reason_detail: str = "",
    info_codes: list[str] | None = None,
) -> PortfolioSnapshotResult:
    codes: list[str] = list(info_codes) if info_codes else []
    if reason_code and reason_code not in codes:
        codes.append(reason_code)
    return PortfolioSnapshotResult(
        new_snapshot=None,
        rejected=True,
        info_codes=codes,
        rejected_reason=reason_detail or reason_code,
    )


# ---------------------------------------------------------------------------
# Core pure build (AD-20 deterministic)
# ---------------------------------------------------------------------------

def build_portfolio_snapshot(
    *,
    positions: list[Position],
    cash_quote: Decimal,
    current_price_map: dict[Symbol, Decimal],
    snapshot_ts: Instant,
    correlation_id: ULID,
    causation_id: ULID,
    prev_peak_equity_quote: Decimal | None = None,
    account_ref: str = "paper-main",
    include_positions_in_snapshot: bool = True,
    snapshot_id: ULID | None = None,
    quality_ctx: QualityFlags | None = None,
) -> PortfolioSnapshotResult:
    """Deterministic PortfolioSnapshot üretir. Position state MUTATE YOK.

    Pipeline: G1 → G2(Quality) → G3(Price) → A1..A6(Aggregations)
           → Q1(Peak) → Q2(Drawdown) → V1(Invariants) → T1(Contract)
    Fail-closed: BaseException → AD19_PORF_SNAP_EXC + None snapshot.
    """
    try:
        return _build_portfolio_snapshot_inner(
            positions=positions,
            cash_quote=cash_quote,
            current_price_map=current_price_map,
            snapshot_ts=snapshot_ts,
            correlation_id=correlation_id,
            causation_id=causation_id,
            prev_peak_equity_quote=prev_peak_equity_quote,
            account_ref=account_ref,
            include_positions_in_snapshot=include_positions_in_snapshot,
            snapshot_id=snapshot_id,
            quality_ctx=quality_ctx,
        )
    except BaseException as exc:  # noqa: BLE001 — AD-19 outer fail-closed
        code = f"{AD19_PORF_SNAP_EXC_PREFIX}{type(exc).__name__}"
        return _make_snapshot_reject(reason_code=code, reason_detail=str(exc))


def _build_portfolio_snapshot_inner(
    *,
    positions: list[Position],
    cash_quote: Decimal,
    current_price_map: dict[Symbol, Decimal],
    snapshot_ts: Instant,
    correlation_id: ULID,
    causation_id: ULID,
    prev_peak_equity_quote: Decimal | None,
    account_ref: str,
    include_positions_in_snapshot: bool,
    snapshot_id: ULID | None,
    quality_ctx: QualityFlags | None,
) -> PortfolioSnapshotResult:
    info_codes: list[str] = []

    # ---- G1 Input Validation ----------------------------------------------
    if not isinstance(positions, list):
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="positions not a list")
    for p in positions:
        if not isinstance(p, Position):
            return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail=f"positions item not Position type={type(p).__name__}")
    if not _ps_is_decimal_nonneg(cash_quote):
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="cash_quote not Decimal >= 0")
    if not isinstance(current_price_map, dict):
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="current_price_map not dict")
    for key, value in current_price_map.items():
        try:
            sym = Symbol(key) if not isinstance(key, Symbol) else key
            if not validate_symbol_canonical(sym):
                return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail=f"price_map key not canonical symbol: {key!r}")
        except BaseException:
            return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail=f"price_map key invalid: {key!r}")
        if isinstance(value, bool) or not isinstance(value, Decimal):
            return _make_snapshot_reject(reason_code=PS_G3_PRICE_TYPE, reason_detail=f"price for {key} not Decimal")
        if value <= 0:
            return _make_snapshot_reject(reason_code=PS_G3_PRICE_NON_POS, reason_detail=f"price for {key} <= 0")
    if not isinstance(account_ref, str) or not account_ref:
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="account_ref empty")
    if not validate_instant(snapshot_ts):
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="snapshot_ts invalid Instant")
    if not _ps_ulidish(str(correlation_id)):
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="correlation_id not ulid-ish")
    if not _ps_ulidish(str(causation_id)):
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="causation_id not ulid-ish")
    if isinstance(include_positions_in_snapshot, bool) is False:
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="include_positions_in_snapshot not bool")
    if prev_peak_equity_quote is not None and not _ps_is_decimal_nonneg(prev_peak_equity_quote):
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="prev_peak_equity_quote not Decimal >= 0 or None")

    # ---- G2 Quality CAP-2 (Read-Only / No Validate Call) ------------------
    q_block = _ps_quality_block_code(quality_ctx)
    if q_block is not None:
        return _make_snapshot_reject(reason_code=q_block, reason_detail=f"quality block: {q_block}")
    if quality_ctx is not None and getattr(quality_ctx, "degraded", False):
        info_codes.append(PS_INFO_Q_DEGRADED)

    # ---- G3 Price Coverage (non-FLAT symbol price required) ---------------
    sorted_pos = _ps_sorted_positions(list(positions))
    for p in sorted_pos:
        if p.side != PositionSide.FLAT and p.base_qty > Decimal("0"):
            # Price map'te var mı? (Symbol olarak veya str)
            price_val = current_price_map.get(p.symbol)
            if price_val is None:
                return _make_snapshot_reject(
                    reason_code=PS_G3_PRICE_MISSING,
                    reason_detail=f"missing price for non-flat: {p.symbol}",
                )
            if not _ps_is_decimal_positive(price_val):
                return _make_snapshot_reject(
                    reason_code=PS_G3_PRICE_NON_POS,
                    reason_detail=f"non-positive price for {p.symbol}",
                )

    # ---- A1 / A2: Exposure ------------------------------------------------
    exposure_notional = Decimal("0")
    for p in sorted_pos:
        # Her pos için ya position.current_price kullan (belirtilmemiş) ya da map
        p_price = current_price_map.get(p.symbol, p.current_price)
        if not _ps_is_decimal_positive(p_price):
            p_price = p.current_price
        pos_qty = Decimal(p.base_qty)
        if pos_qty < 0:
            return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail=f"negative base_qty for {p.symbol}")
        if p.side == PositionSide.FLAT:
            pos_exp = Decimal("0")
        else:
            pos_exp = _q8(pos_qty * Decimal(p_price))
        # safety: negatif exposure clamp 0 (long-only, hiç olmamalı ama fail-safe)
        if pos_exp < 0:
            pos_exp = Decimal("0")
        exposure_notional = exposure_notional + pos_exp

    # ---- A3: Total Equity -------------------------------------------------
    equity_quote = Decimal(cash_quote) + exposure_notional
    if equity_quote < 0:
        equity_quote = Decimal("0")  # safety: negatif olamaz (long-only)

    # ---- A4: Realized Aggregate (session cumulative, window OOS) ----------
    realized_total = Decimal("0")
    for p in sorted_pos:
        realized_total = realized_total + Decimal(p.realized_pnl_quote)

    # ---- A5: Unrealized Aggregate (FLAT contribution = 0) -----------------
    unrealized_total = Decimal("0")
    for p in sorted_pos:
        if p.side == PositionSide.FLAT or p.base_qty == Decimal("0"):
            continue
        unrealized_total = unrealized_total + Decimal(p.unrealized_pnl_quote)

    # ---- A6: Fees Aggregate (double-count YOK, sadece sum) ----------------
    fees_total = Decimal("0")
    for p in sorted_pos:
        fees_total = fees_total + Decimal(p.fees_quote)
    if fees_total < 0:
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="negative fees total (corrupted input)")

    # ---- Q1: Peak Equity --------------------------------------------------
    is_first_snapshot = prev_peak_equity_quote is None
    if is_first_snapshot:
        peak_before = equity_quote
        info_codes.append(PS_INFO_FIRST_SNAPSHOT)
    else:
        peak_before = Decimal(prev_peak_equity_quote)
        # Safety: prev_peak < 0 olursa (bozuk) -> kendisiyle aynı (nonneg)
        if peak_before < 0:
            peak_before = equity_quote
    new_peak_equity_quote = max(peak_before, equity_quote)

    # ---- Q2: Drawdown pct (float [0, 1]) ----------------------------------
    if new_peak_equity_quote > equity_quote and new_peak_equity_quote > Decimal("0"):
        numerator = new_peak_equity_quote - equity_quote
        ratio_dec = numerator / new_peak_equity_quote
        dd_raw = float(ratio_dec)
        drawdown_pct = min(max(dd_raw, 0.0), 1.0)
    else:
        drawdown_pct = 0.0
    # Peak == 0 & equity == 0 edge: drawdown 0 (else case zaten)

    # ---- V1: Invariants ---------------------------------------------------
    # (A) equity == cash + exposure (DOĞRULAMA)
    eq_check = Decimal(cash_quote) + exposure_notional
    if eq_check < 0:
        eq_check = Decimal("0")
    if eq_check != equity_quote and abs(eq_check - equity_quote) > Decimal("1e-28"):
        info_codes.append(PS_V1_EQUITY_MISMATCH)
    # (B) exposure <= equity
    if exposure_notional > equity_quote and not (
        exposure_notional == equity_quote
    ):
        # float precision tolerance (Decimal olduğu için zaten exact ama safe)
        if (exposure_notional - equity_quote) > Decimal("1e-28"):
            return _make_snapshot_reject(
                reason_code=PS_V1_EXPOSURE_OVER,
                reason_detail=f"exposure {exposure_notional} > equity {equity_quote}",
            )
    # (C) peak >= equity (new_peak_equity_quote ZORUNLU)
    if new_peak_equity_quote < equity_quote:
        return _make_snapshot_reject(
            reason_code=PS_V1_PEAK_BEFORE,
            reason_detail=f"new_peak {new_peak_equity_quote} < equity {equity_quote}",
        )
    # (D) fees >= 0
    if fees_total < 0:
        return _make_snapshot_reject(reason_code=PS_G1_INVALID, reason_detail="fees_total negative")

    # ---- Info codes (pos include/omit) ------------------------------------
    if include_positions_in_snapshot:
        info_codes.append(PS_INFO_POS_INCLUDED)
        snap_positions: list[Position] | None = list(sorted_pos)
    else:
        info_codes.append(PS_INFO_POS_OMITTED)
        snap_positions = None

    # ---- T1: PortfolioSnapshot (S-CON-02B §3.15) -------------------------
    if snapshot_id and _ps_ulidish(str(snapshot_id)):
        final_snapshot_id = ULID(str(snapshot_id))
    else:
        # Deterministic olmayan ama benzersiz ULID benzeri (corr+caus+peak hash tabanlı değil — sıra dışı benzersiz)
        suffix = f"SN{str(causation_id)[-8:]}{abs(hash((str(correlation_id), str(equity_quote), include_positions_in_snapshot))) % 100000000:08d}"
        final_snapshot_id = ULID(f"S{suffix[-22:]}")

    snap = PortfolioSnapshot(
        snapshot_id=final_snapshot_id,
        account_ref=account_ref,
        ts=Instant(snapshot_ts),
        cash_quote=Decimal(cash_quote),
        equity_quote=equity_quote,
        realized_pnl_quote_24h=realized_total,
        unrealized_pnl_quote=unrealized_total,
        fees_quote_total=fees_total,
        exposure_notional=exposure_notional,
        drawdown_pct=drawdown_pct,
        peak_equity_quote=new_peak_equity_quote,
        correlation_id=ULID(str(correlation_id)),
        causation_id=ULID(str(causation_id)),
        positions_snapshot=snap_positions,
    )

    return PortfolioSnapshotResult(
        new_snapshot=snap,
        rejected=False,
        info_codes=info_codes,
        rejected_reason="",
    )


# ---------------------------------------------------------------------------
# Publish portfolio_snapshot.v1 typed event (S-PLN-01 EventBus)
# ---------------------------------------------------------------------------

def publish_portfolio_snapshot_event(
    *,
    result: PortfolioSnapshotResult,
    event_bus: InMemoryTypedEventBus | None,
    quality_ctx: QualityFlags | None = None,
    clock_ref: ClockRef | None = None,
    source: str = "s.simulation.portfolio.snapshot_engine",
) -> None:
    if event_bus is None:
        return
    try:
        qf = quality_ctx or QualityFlags()
        parent_caus = ""
        corr_id = ""
        ts_iso = ""
        if result.new_snapshot is not None:
            snap = result.new_snapshot
            corr_id = str(snap.correlation_id)
            parent_caus = str(snap.causation_id)
            ts_iso = str(snap.ts)
        else:
            # Rejected: info kodlarından tahmin (corr/caus girildiyse kullanılır yoksa default)
            corr_id = str(getattr(result, "_fallback_corr", "COR000000000000000000000FALL"))
            parent_caus = str(getattr(result, "_fallback_caus", "CAU000000000000000000000FALL"))
            ts_iso = "1970-01-01T00:00:00.000Z"
        cr = clock_ref or ClockRef(wall=Instant(ts_iso))
        if not result.rejected and result.new_snapshot is not None:
            snap = result.new_snapshot
            extra: dict[str, Any] = {
                "info_codes": list(result.info_codes),
                "positions_count": len(snap.positions_snapshot) if snap.positions_snapshot is not None else 0,
                "drawdown_pct": snap.drawdown_pct,
                "peak_equity_quote_str": str(snap.peak_equity_quote),
            }
            envelope = CanonicalEventEnvelope(
                event_id=ULID(f"ES{str(snap.snapshot_id)[-22:]}"),
                event_type=EVENT_PORTFOLIO_SNAPSHOT,
                contract_version=CONTRACT_VERSION,
                symbol=None,
                source=source,
                timestamp=Instant(snap.ts),
                ingest_ts=Instant(snap.ts),
                correlation_id=ULID(corr_id),
                causation_id=ULID(parent_caus),
                run_mode=RunMode.PAPER,
                source_type=SourceType.SIMULATED,
                clock_ref=cr,
                quality_flags=qf,
                schema_ref=SchemaRef(),
                extra=extra,
                payload=snap,
            )
            event_bus.publish_with_causation(envelope, parent_event_id=parent_caus)
        else:
            extra = {
                "rejected_reason": result.rejected_reason,
                "info_codes": list(result.info_codes),
            }
            envelope = CanonicalEventEnvelope(
                event_id=ULID(f"ESR{abs(hash(tuple(result.info_codes))) % 10000000000000000000000:022d}"),
                event_type=EVENT_PORTFOLIO_SNAPSHOT_REJECTED,
                contract_version=CONTRACT_VERSION,
                symbol=None,
                source=source,
                timestamp=Instant(ts_iso),
                ingest_ts=Instant(ts_iso),
                correlation_id=ULID(corr_id),
                causation_id=ULID(parent_caus),
                run_mode=RunMode.PAPER,
                source_type=SourceType.SIMULATED,
                clock_ref=cr,
                quality_flags=qf,
                schema_ref=SchemaRef(),
                extra=extra,
                payload=None,
            )
            try:
                event_bus.publish_with_causation(envelope, parent_event_id=parent_caus)
            except BaseException:
                return
    except BaseException:
        # AD-19: publish aşaması exception → DLQ bus kendi handler eder; biz sessizce devam.
        return


# ---------------------------------------------------------------------------
# PortfolioSnapshotEngine: stateful wrapper for prev_peak (single writer)
# ---------------------------------------------------------------------------

class PortfolioSnapshotEngine:
    """Single Writer PortfolioSnapshot (AD-7/13/24). Peak state kendi içinde tutulur.

    Position state ASLA mutate edilmez. Sadece ve sadece PortfolioSnapshot üretir.
    """

    def __init__(
        self,
        *,
        event_bus: InMemoryTypedEventBus | None = None,
        account_ref: str = "paper-main",
        include_positions_in_snapshot: bool = True,
    ) -> None:
        self.event_bus = event_bus
        self.account_ref = account_ref
        self.include_positions_in_snapshot = include_positions_in_snapshot
        self._peak_equity_quote: Decimal | None = None
        self._snapshots: list[PortfolioSnapshot] = []
        self._rejections: list[PortfolioSnapshotResult] = []

    @property
    def peak_equity_quote(self) -> Decimal | None:
        return self._peak_equity_quote

    @property
    def snapshots(self) -> list[PortfolioSnapshot]:
        return list(self._snapshots)

    @property
    def rejections(self) -> list[PortfolioSnapshotResult]:
        return list(self._rejections)

    def build(
        self,
        *,
        positions: list[Position],
        cash_quote: Decimal,
        current_price_map: dict[Symbol, Decimal],
        snapshot_ts: Instant,
        correlation_id: ULID,
        causation_id: ULID,
        include_positions_in_snapshot: bool | None = None,
        snapshot_id: ULID | None = None,
        quality_ctx: QualityFlags | None = None,
        publish: bool = True,
    ) -> PortfolioSnapshotResult:
        include = (
            include_positions_in_snapshot
            if include_positions_in_snapshot is not None
            else self.include_positions_in_snapshot
        )
        result = build_portfolio_snapshot(
            positions=positions,
            cash_quote=cash_quote,
            current_price_map=current_price_map,
            snapshot_ts=snapshot_ts,
            correlation_id=correlation_id,
            causation_id=causation_id,
            prev_peak_equity_quote=self._peak_equity_quote,
            account_ref=self.account_ref,
            include_positions_in_snapshot=include,
            snapshot_id=snapshot_id,
            quality_ctx=quality_ctx,
        )
        if not result.rejected and result.new_snapshot is not None:
            self._peak_equity_quote = result.new_snapshot.peak_equity_quote
            self._snapshots.append(result.new_snapshot)
        else:
            self._rejections.append(result)
        if publish:
            publish_portfolio_snapshot_event(
                result=result,
                event_bus=self.event_bus,
                quality_ctx=quality_ctx,
                clock_ref=ClockRef(wall=Instant(snapshot_ts)) if snapshot_ts else None,
            )
        return result

