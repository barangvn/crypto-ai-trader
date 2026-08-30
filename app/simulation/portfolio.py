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
    Position,
    PositionSide,
    QualityFlags,
    RunMode,
    SourceType,
    Symbol,
    format_instant,
)
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    SchemaRef,
)
from app.contracts.types import Instant, ULID, validate_symbol_canonical
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


# ---------------------------------------------------------------------------
# Public typed event names
# ---------------------------------------------------------------------------

EVENT_POSITION_UPDATED = "position_updated.v1"
EVENT_POSITION_TRANSITION_REJECTED = "position_transition_rejected.v1"


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
