from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any

from app.contracts import (
    CONTRACT_VERSION,
    Candle,
    ClockRef,
    ContractSchemaError,
    MarketTick,
    OrderBookSnapshot,
    PaperFill,
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    QualityFlags,
    RunMode,
    SourceType,
    format_instant,
    schema_sha256,
    to_sorted_dict,
    validate_instant,
)
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    SchemaRef,
)
from app.contracts.types import Instant, Symbol, ULID
from app.platform.event_bus import InMemoryTypedEventBus
from app.simulation.fill_config import (
    FILL_MODEL_VERSION,
    FillAssumptionsConfig,
    PaperFillRejectReason,
    PaperFillResult,
)


_QUANTIZE_8DP = Decimal("0.00000001")
_BPS_DENOM = Decimal("10000")
_SPREAD_BPS_SAFETY_CAP = 10_000.0
_SLIPPAGE_BPS_SAFETY_CAP = 10_000.0


@dataclass
class PipelineReferenceData:
    tick: MarketTick | None = None
    orderbook: OrderBookSnapshot | None = None
    candle: Candle | None = None
    symbol: Symbol | None = None
    clock_ref: ClockRef | None = None


def build_pipeline_reference_data(
    *,
    tick: MarketTick | None = None,
    orderbook: OrderBookSnapshot | None = None,
    candle: Candle | None = None,
    symbol: Symbol | None = None,
    clock_ref: ClockRef | None = None,
) -> PipelineReferenceData:
    return PipelineReferenceData(
        tick=tick,
        orderbook=orderbook,
        candle=candle,
        symbol=symbol,
        clock_ref=clock_ref,
    )


def _parse_instant_to_dt(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _format_dt_to_instant(dt: datetime) -> str:
    dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    ms = int(dt_utc.microsecond / 1000)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}Z"


def _instant_plus_ms(instant_str: str, ms: int) -> str:
    dt = _parse_instant_to_dt(instant_str)
    new_dt = dt + timedelta(milliseconds=ms)
    return _format_dt_to_instant(new_dt)


def _deterministic_hash_int(*seeds: Any, max_val: int) -> int:
    payload = "|".join(str(s) for s in seeds)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest, 16) % max(1, max_val + 1)


def deterministic_latency_ms(
    *,
    config: FillAssumptionsConfig,
    correlation_id: str,
    reference_market_ts: str,
    order_id: str,
) -> int:
    base = max(0, int(config.base_latency_ms))
    max_cap = max(0, int(config.max_latency_ms))
    if base > max_cap:
        raise ValueError(
            f"{PaperFillRejectReason.P3_LATENCY_EXCEEDS_MAX.value}: "
            f"base_latency_ms={base} > max_latency_ms={max_cap}"
        )
    jitter_max = max(0, int(config.latency_jitter_ms))
    if jitter_max > 0:
        jitter = _deterministic_hash_int(
            "lat", correlation_id, reference_market_ts, order_id, max_val=jitter_max
        )
    else:
        jitter = 0
    latency = base + jitter
    if latency < 0:
        raise ValueError(f"{PaperFillRejectReason.P3_LATENCY_NEGATIVE.value}: latency_ms={latency}")
    if latency > max_cap:
        latency = max_cap
    return int(latency)


def _orderbook_best_bid_ask(ob: OrderBookSnapshot) -> tuple[Decimal | None, Decimal | None]:
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    if ob.bids and len(ob.bids) > 0 and len(ob.bids[0]) >= 1:
        maybe_bid = ob.bids[0][0]
        if isinstance(maybe_bid, Decimal) and maybe_bid > 0:
            best_bid = maybe_bid
    if ob.asks and len(ob.asks) > 0 and len(ob.asks[0]) >= 1:
        maybe_ask = ob.asks[0][0]
        if isinstance(maybe_ask, Decimal) and maybe_ask > 0:
            best_ask = maybe_ask
    return best_bid, best_ask


def _fallback_mid_price(ref: PipelineReferenceData) -> Decimal | None:
    if ref.tick is not None:
        if isinstance(ref.tick.price, Decimal) and ref.tick.price > 0:
            return ref.tick.price
    if ref.candle is not None and getattr(ref.candle, "closed", False):
        if isinstance(ref.candle.close, Decimal) and ref.candle.close > 0:
            return ref.candle.close
    return None


def select_reference_price(
    *,
    side: PaperOrderSide,
    ref: PipelineReferenceData,
    config: FillAssumptionsConfig,
) -> tuple[Decimal, str, float | None]:
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None

    if ref.orderbook is not None:
        best_bid, best_ask = _orderbook_best_bid_ask(ref.orderbook)

    if best_bid is not None and best_ask is not None:
        if best_bid >= best_ask:
            raise ValueError(
                f"{PaperFillRejectReason.P4_BID_ASK_CROSS.value}: bid={best_bid} ask={best_ask}"
            )

    source_tag = ""
    spread_bps_actual: float | None = None

    if side == PaperOrderSide.BUY:
        if best_ask is not None:
            source_tag = "OB_ASK"
            price = best_ask
            if best_bid is not None and best_bid > 0:
                mid = (best_bid + best_ask) / Decimal("2")
                if mid > 0:
                    spread = float((best_ask - best_bid) / mid * Decimal("10000"))
                    spread_bps_actual = float(spread)
            return price, source_tag, spread_bps_actual
        if ref.tick is not None and isinstance(ref.tick.ask_price, Decimal) and ref.tick.ask_price > 0:
            source_tag = "TICK_ASK"
            price = ref.tick.ask_price
            if isinstance(ref.tick.bid_price, Decimal) and ref.tick.bid_price > 0:
                mid = (ref.tick.bid_price + ref.tick.ask_price) / Decimal("2")
                if mid > 0:
                    spread = float((ref.tick.ask_price - ref.tick.bid_price) / mid * Decimal("10000"))
                    spread_bps_actual = float(spread)
            return price, source_tag, spread_bps_actual
        if isinstance(ref.tick, MarketTick) and isinstance(ref.tick.price, Decimal) and ref.tick.price > 0:
            source_tag = "TICK_PRICE"
            return ref.tick.price, source_tag, getattr(ref.tick, "spread_bps", None)
        if isinstance(ref.candle, Candle) and ref.candle.closed and isinstance(ref.candle.close, Decimal) and ref.candle.close > 0:
            source_tag = "CANDLE_CLOSE"
            return ref.candle.close, source_tag, None
        fallback = _fallback_mid_price(ref)
        if fallback is not None:
            source_tag = "FALLBACK_MID"
            return fallback, source_tag, None
        raise ValueError(f"{PaperFillRejectReason.P4_NO_MARKET_REFERENCE.value}: no market data")

    elif side == PaperOrderSide.SELL:
        if best_bid is not None:
            source_tag = "OB_BID"
            price = best_bid
            if best_ask is not None and best_ask > 0:
                mid = (best_bid + best_ask) / Decimal("2")
                if mid > 0:
                    spread = float((best_ask - best_bid) / mid * Decimal("10000"))
                    spread_bps_actual = float(spread)
            return price, source_tag, spread_bps_actual
        if ref.tick is not None and isinstance(ref.tick.bid_price, Decimal) and ref.tick.bid_price > 0:
            source_tag = "TICK_BID"
            price = ref.tick.bid_price
            if isinstance(ref.tick.ask_price, Decimal) and ref.tick.ask_price > 0:
                mid = (ref.tick.bid_price + ref.tick.ask_price) / Decimal("2")
                if mid > 0:
                    spread = float((ref.tick.ask_price - ref.tick.bid_price) / mid * Decimal("10000"))
                    spread_bps_actual = float(spread)
            return price, source_tag, spread_bps_actual
        if isinstance(ref.tick, MarketTick) and isinstance(ref.tick.price, Decimal) and ref.tick.price > 0:
            source_tag = "TICK_PRICE"
            return ref.tick.price, source_tag, getattr(ref.tick, "spread_bps", None)
        if isinstance(ref.candle, Candle) and ref.candle.closed and isinstance(ref.candle.close, Decimal) and ref.candle.close > 0:
            source_tag = "CANDLE_CLOSE"
            return ref.candle.close, source_tag, None
        fallback = _fallback_mid_price(ref)
        if fallback is not None:
            source_tag = "FALLBACK_MID"
            return fallback, source_tag, None
        raise ValueError(f"{PaperFillRejectReason.P4_NO_MARKET_REFERENCE.value}: no market data")
    else:
        raise ValueError(f"{PaperFillRejectReason.P1_SIDE_INVALID.value}: side={side}")


def _has_any_spread_source(ref: PipelineReferenceData) -> bool:
    if ref.orderbook is not None:
        bid, ask = _orderbook_best_bid_ask(ref.orderbook)
        if bid is not None and ask is not None:
            return True
    if ref.tick is not None:
        both_ok = isinstance(ref.tick.bid_price, Decimal) and isinstance(ref.tick.ask_price, Decimal)
        if both_ok and ref.tick.bid_price > 0 and ref.tick.ask_price > 0:
            return True
    return False


def apply_spread_cost(
    *,
    side: PaperOrderSide,
    reference_price: Decimal,
    ref: PipelineReferenceData,
    config: FillAssumptionsConfig,
    actual_spread_bps: float | None,
) -> tuple[Decimal, float, str]:
    if actual_spread_bps is not None:
        if actual_spread_bps < 0:
            raise ValueError(f"{PaperFillRejectReason.P5_SPREAD_NEGATIVE.value}: spread_bps={actual_spread_bps}")
        if actual_spread_bps > _SPREAD_BPS_SAFETY_CAP:
            raise ValueError(
                f"{PaperFillRejectReason.P5_SPREAD_TOO_LARGE.value}: spread_bps={actual_spread_bps}"
            )
        bps = float(actual_spread_bps)
        source = "ACTUAL_BID_ASK" if _has_any_spread_source(ref) else "ACTUAL_EXPLICIT"
    else:
        default_bps = float(config.default_spread_bps)
        if default_bps < 0:
            raise ValueError(f"{PaperFillRejectReason.P5_SPREAD_NEGATIVE.value}: spread_bps={default_bps}")
        if default_bps > _SPREAD_BPS_SAFETY_CAP:
            raise ValueError(
                f"{PaperFillRejectReason.P5_SPREAD_TOO_LARGE.value}: spread_bps={default_bps}"
            )
        bps = float(default_bps)
        source = "DEFAULT_ASSUMPTION"

    spread_half_bps_decimal = Decimal(str(bps / 2.0)) / _BPS_DENOM
    spread_amount = reference_price * spread_half_bps_decimal
    if side == PaperOrderSide.BUY:
        final_price = reference_price + spread_amount
    else:
        final_price = reference_price - spread_amount
    if final_price <= 0:
        raise ValueError(f"{PaperFillRejectReason.P5_SPREAD_NEGATIVE.value}: resulting price non-positive")
    return final_price, bps, source


def apply_slippage_directional(
    *,
    side: PaperOrderSide,
    price_after_spread: Decimal,
    config: FillAssumptionsConfig,
) -> tuple[Decimal, float]:
    slippage_bps = float(config.base_slippage_bps)
    max_cap = min(float(config.max_slippage_bps), _SLIPPAGE_BPS_SAFETY_CAP)
    if slippage_bps < 0:
        raise ValueError(f"{PaperFillRejectReason.P6_SLIPPAGE_NEGATIVE.value}: slippage_bps={slippage_bps}")
    if slippage_bps > max_cap:
        raise ValueError(
            f"{PaperFillRejectReason.P6_SLIPPAGE_EXCEEDS_MAX.value}: slippage_bps={slippage_bps}"
        )
    if slippage_bps == 0.0:
        return price_after_spread, 0.0
    slip_decimal = Decimal(str(slippage_bps)) / _BPS_DENOM
    slip_amount = price_after_spread * slip_decimal
    if side == PaperOrderSide.BUY:
        final_price = price_after_spread + slip_amount
    else:
        final_price = price_after_spread - slip_amount
    if final_price <= 0:
        raise ValueError(
            f"{PaperFillRejectReason.P6_SLIPPAGE_EXCEEDS_MAX.value}: resulting price non-positive"
        )
    return final_price, slippage_bps


def calculate_fee_quote(
    *,
    fill_qty_quote: Decimal,
    config: FillAssumptionsConfig,
) -> tuple[Decimal, Decimal]:
    if config.default_fee_type == "maker":
        fee_bps = config.maker_fee_bps
    else:
        fee_bps = config.taker_fee_bps
    if not isinstance(fee_bps, Decimal):
        fee_bps = Decimal(str(fee_bps))
    if fee_bps < 0:
        raise ValueError(f"{PaperFillRejectReason.P7_FEE_NEGATIVE.value}: fee_bps={fee_bps}")
    if fee_bps > config.max_fee_bps:
        raise ValueError(
            f"{PaperFillRejectReason.P7_FEE_EXCEEDS_SAFETY.value}: fee_bps={fee_bps}"
        )
    raw_fee = (fill_qty_quote * fee_bps) / _BPS_DENOM
    quantized_fee = raw_fee.quantize(_QUANTIZE_8DP, rounding=ROUND_DOWN)
    if quantized_fee <= 0:
        quantized_fee = config.min_fee_quote_floor.quantize(_QUANTIZE_8DP, rounding=ROUND_DOWN)
        if quantized_fee <= 0:
            quantized_fee = Decimal("0.00000001")
    if quantized_fee < 0:
        raise ValueError(f"{PaperFillRejectReason.P7_FEE_NEGATIVE.value}: fee_quote={quantized_fee}")
    return quantized_fee, fee_bps


def calculate_fill_quantities(
    *,
    requested_qty_base: Decimal,
    fill_price: Decimal,
    config: FillAssumptionsConfig,
) -> tuple[Decimal, Decimal, Decimal]:
    ratio = config.fill_ratio
    if not isinstance(ratio, Decimal):
        ratio = Decimal(str(ratio))
    if ratio <= 0:
        raise ValueError(f"{PaperFillRejectReason.P8_FILL_RATIO_ZERO.value}: ratio={ratio}")
    if ratio > Decimal("1.0"):
        raise ValueError(f"{PaperFillRejectReason.P8_FILL_RATIO_GT_ONE.value}: ratio={ratio}")
    raw_qty_base = requested_qty_base * ratio
    qty_base = raw_qty_base.quantize(_QUANTIZE_8DP, rounding=ROUND_DOWN)
    if qty_base <= 0:
        raise ValueError(
            f"{PaperFillRejectReason.P8_FILL_QTY_NOT_POSITIVE.value}: qty_base={qty_base}"
        )
    if qty_base > requested_qty_base:
        raise ValueError(
            f"{PaperFillRejectReason.P8_FILL_QTY_EXCEEDS_REQUESTED.value}: "
            f"qty_base={qty_base} requested={requested_qty_base}"
        )
    qty_quote_exact = fill_price * qty_base
    qty_quote = qty_quote_exact
    if qty_quote <= 0:
        raise ValueError(
            f"{PaperFillRejectReason.P9_QUOTE_AMOUNT_MISMATCH.value}: qty_quote non-positive"
        )
    return qty_base, qty_quote, ratio


def _validate_order_fillable(order: PaperOrder) -> list[str]:
    reasons: list[str] = []
    fillable_statuses = {
        PaperOrderStatus.CREATED,
        PaperOrderStatus.SIMULATING,
        PaperOrderStatus.PARTIALLY_FILLED,
    }
    if order.status not in fillable_statuses:
        reasons.append(PaperFillRejectReason.P1_ORDER_STATUS_NOT_FILLABLE.value)
    if not (isinstance(order.requested_qty_base, Decimal) and order.requested_qty_base > 0):
        reasons.append(PaperFillRejectReason.P1_QTY_NOT_POSITIVE.value)
    rdid = getattr(getattr(order, "policy_refs", None), "risk_decision_id", None)
    if rdid is None or len(str(rdid)) < 8:
        reasons.append(PaperFillRejectReason.P1_RISK_DECISION_ID_MISSING.value)
    if not isinstance(order.side, PaperOrderSide):
        reasons.append(PaperFillRejectReason.P1_SIDE_INVALID.value)
    return reasons


def _check_quality_flags(qf: QualityFlags | None) -> list[str]:
    reasons: list[str] = []
    if qf is None:
        return reasons
    if qf.stale:
        reasons.append(PaperFillRejectReason.P2_QUALITY_STALE.value)
    if qf.invalid:
        reasons.append(PaperFillRejectReason.P2_QUALITY_INVALID.value)
    if qf.quarantined:
        reasons.append(PaperFillRejectReason.P2_QUALITY_QUARANTINED.value)
    if qf.duplicate:
        reasons.append(PaperFillRejectReason.P2_QUALITY_DUPLICATE.value)
    if qf.out_of_order:
        reasons.append(PaperFillRejectReason.P2_QUALITY_OUT_OF_ORDER.value)
    if qf.missing:
        reasons.append(PaperFillRejectReason.P2_QUALITY_MISSING.value)
    return reasons


def _new_fill_id(corr: str, order_id: str, suffix: str = "f1") -> str:
    seed = f"pfill|{corr}|{order_id}|{suffix}"
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return h[:26].upper()


def _reference_data_timestamp(ref: PipelineReferenceData) -> str:
    if ref.orderbook is not None and validate_instant(str(ref.orderbook.book_ts)):
        return str(ref.orderbook.book_ts)
    if ref.tick is not None and validate_instant(str(ref.tick.market_ts)):
        return str(ref.tick.market_ts)
    if ref.candle is not None and validate_instant(str(ref.candle.close_time)):
        return str(ref.candle.close_time)
    return "NO_TS"


class PaperExecutionSimulator:
    def __init__(
        self,
        *,
        config: FillAssumptionsConfig | None = None,
        event_bus: InMemoryTypedEventBus | None = None,
    ) -> None:
        self.config: FillAssumptionsConfig = config or FillAssumptionsConfig()
        self.event_bus: InMemoryTypedEventBus | None = event_bus
        self.last_reject_reasons: list[str] = []
        self.last_info_codes: list[str] = []

    # ========= 10-step deterministic pipeline =========

    def simulate(
        self,
        *,
        order: PaperOrder,
        reference: PipelineReferenceData,
        quality_ctx: QualityFlags | None = None,
        clock_ref: ClockRef | None = None,
        publish_to_bus: bool = True,
    ) -> PaperFillResult:
        result = PaperFillResult()
        effective_cr = clock_ref if clock_ref is not None else reference.clock_ref

        try:
            # ---- P1 Validation ----
            p1_reasons = _validate_order_fillable(order)
            if p1_reasons:
                result.rejected = True
                result.reject_reasons.extend(p1_reasons)
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            # ---- P2 Quality Gate ----
            p2_reasons = _check_quality_flags(quality_ctx)
            if p2_reasons:
                result.rejected = True
                result.reject_reasons.extend(p2_reasons)
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            if quality_ctx is not None and quality_ctx.degraded and not result.rejected:
                result.info_codes.append("P2_INFO_QUALITY_DEGRADED_ACCEPTED")

            # ---- P3 Latency (NO SLEEP — pure Instant math) ----
            ref_ts = _reference_data_timestamp(reference)
            try:
                latency = deterministic_latency_ms(
                    config=self.config,
                    correlation_id=str(order.correlation_id),
                    reference_market_ts=ref_ts,
                    order_id=str(order.paper_order_id),
                )
            except ValueError as e:
                msg = str(e)
                if msg.startswith(PaperFillRejectReason.P3_LATENCY_NEGATIVE.value):
                    result.reject_reasons.append(PaperFillRejectReason.P3_LATENCY_NEGATIVE.value)
                elif msg.startswith(PaperFillRejectReason.P3_LATENCY_EXCEEDS_MAX.value):
                    result.reject_reasons.append(PaperFillRejectReason.P3_LATENCY_EXCEEDS_MAX.value)
                else:
                    result.reject_reasons.append(PaperFillRejectReason.AD19_SIM_EXCEPTION.value + ":P3")
                result.rejected = True
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            fill_ts_str = _instant_plus_ms(str(order.created_at), latency)
            result.fill_ts = fill_ts_str
            result.latency_ms_applied = latency

            # ---- P4 Reference Price ----
            try:
                if reference.candle is not None and not getattr(reference.candle, "closed", True):
                    raise ValueError(PaperFillRejectReason.P4_CANDLE_NOT_CLOSED.value)
                ref_price, source_tag, spread_bps_actual = select_reference_price(
                    side=order.side,
                    ref=reference,
                    config=self.config,
                )
                result.reference_price_used = ref_price
                result.info_codes.append(f"P4_SOURCE={source_tag}")
            except ValueError as e:
                msg = str(e)
                for cand in (
                    PaperFillRejectReason.P4_NO_MARKET_REFERENCE.value,
                    PaperFillRejectReason.P4_CANDLE_NOT_CLOSED.value,
                    PaperFillRejectReason.P4_BID_ASK_CROSS.value,
                ):
                    if msg.startswith(cand):
                        result.reject_reasons.append(cand)
                        break
                else:
                    result.reject_reasons.append(PaperFillRejectReason.AD19_SIM_EXCEPTION.value + ":P4")
                result.rejected = True
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            # ---- P5 Spread Cost ----
            try:
                post_spread_price, spread_bps_applied, spread_src = apply_spread_cost(
                    side=order.side,
                    reference_price=ref_price,
                    ref=reference,
                    config=self.config,
                    actual_spread_bps=spread_bps_actual,
                )
                result.spread_cost_applied_bps = float(spread_bps_applied)
                result.info_codes.append(f"P5_SOURCE={spread_src}")
            except ValueError as e:
                msg = str(e)
                for cand in (
                    PaperFillRejectReason.P5_SPREAD_NEGATIVE.value,
                    PaperFillRejectReason.P5_SPREAD_TOO_LARGE.value,
                ):
                    if msg.startswith(cand):
                        result.reject_reasons.append(cand)
                        break
                else:
                    result.reject_reasons.append(PaperFillRejectReason.AD19_SIM_EXCEPTION.value + ":P5")
                result.rejected = True
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            # ---- P6 Slippage ----
            try:
                post_slip_price, slip_bps = apply_slippage_directional(
                    side=order.side,
                    price_after_spread=post_spread_price,
                    config=self.config,
                )
                result.slippage_applied_bps = float(slip_bps)
            except ValueError as e:
                msg = str(e)
                for cand in (
                    PaperFillRejectReason.P6_SLIPPAGE_NEGATIVE.value,
                    PaperFillRejectReason.P6_SLIPPAGE_EXCEEDS_MAX.value,
                ):
                    if msg.startswith(cand):
                        result.reject_reasons.append(cand)
                        break
                else:
                    result.reject_reasons.append(PaperFillRejectReason.AD19_SIM_EXCEPTION.value + ":P6")
                result.rejected = True
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            fill_price_final = post_slip_price

            # ---- P8 Fill Qty (Fee before fee needs qty_quote, so P8 before P7) ----
            try:
                qty_base, qty_quote, ratio_applied = calculate_fill_quantities(
                    requested_qty_base=order.requested_qty_base,
                    fill_price=fill_price_final,
                    config=self.config,
                )
                result.fill_ratio_applied = ratio_applied
            except ValueError as e:
                msg = str(e)
                for cand in (
                    PaperFillRejectReason.P8_FILL_RATIO_ZERO.value,
                    PaperFillRejectReason.P8_FILL_RATIO_GT_ONE.value,
                    PaperFillRejectReason.P8_FILL_QTY_NOT_POSITIVE.value,
                    PaperFillRejectReason.P8_FILL_QTY_EXCEEDS_REQUESTED.value,
                    PaperFillRejectReason.P9_QUOTE_AMOUNT_MISMATCH.value,
                ):
                    if msg.startswith(cand):
                        result.reject_reasons.append(cand)
                        break
                else:
                    result.reject_reasons.append(PaperFillRejectReason.AD19_SIM_EXCEPTION.value + ":P8")
                result.rejected = True
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            # ---- P7 Fee ----
            try:
                fees_quote, fee_bps_applied = calculate_fee_quote(
                    fill_qty_quote=qty_quote,
                    config=self.config,
                )
                if fees_quote <= 0:
                    raise ValueError(PaperFillRejectReason.P10_FEE_NOT_POSITIVE.value)
                result.fee_bps_applied = fee_bps_applied
            except ValueError as e:
                msg = str(e)
                for cand in (
                    PaperFillRejectReason.P7_FEE_NEGATIVE.value,
                    PaperFillRejectReason.P7_FEE_EXCEEDS_SAFETY.value,
                    PaperFillRejectReason.P10_FEE_NOT_POSITIVE.value,
                ):
                    if msg.startswith(cand):
                        result.reject_reasons.append(cand)
                        break
                else:
                    result.reject_reasons.append(PaperFillRejectReason.AD19_SIM_EXCEPTION.value + ":P7")
                result.rejected = True
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            # ---- P10 PaperFill Contract Build ----
            try:
                fill_id = _new_fill_id(str(order.correlation_id), str(order.paper_order_id))
                fill = PaperFill(
                    paper_fill_id=ULID(fill_id),
                    paper_order_id=ULID(str(order.paper_order_id)),
                    side=order.side,
                    fill_price=fill_price_final,
                    fill_qty_base=qty_base,
                    fill_qty_quote=qty_quote,
                    fees_quote=fees_quote,
                    fill_ts=Instant(fill_ts_str),
                    fill_model_version=FILL_MODEL_VERSION,
                    correlation_id=ULID(str(order.correlation_id)),
                    causation_id=ULID(str(order.paper_order_id)),
                    slippage_bps=float(result.slippage_applied_bps) if result.slippage_applied_bps is not None else None,
                    latency_ms=int(latency) if latency is not None else None,
                )
            except (ContractSchemaError, ValueError) as e:
                result.reject_reasons.append(
                    f"{PaperFillRejectReason.AD19_SIM_EXCEPTION.value}:P10:{type(e).__name__}"
                )
                result.rejected = True
                self.last_reject_reasons = list(result.reject_reasons)
                return result

            result.fill = fill

            # ---- Publish to Typed Event Bus (optional) ----
            if publish_to_bus and self.event_bus is not None:
                try:
                    sym = reference.symbol if reference.symbol else Symbol("")
                    ts_now = fill.fill_ts
                    cr = effective_cr or ClockRef(wall=Instant(ts_now))
                    qf = quality_ctx or QualityFlags()
                    envelope = CanonicalEventEnvelope(
                        event_id=ULID(fill.paper_fill_id),
                        event_type="paper_fill_created.v1",
                        contract_version=CONTRACT_VERSION,
                        symbol=sym if sym else None,
                        source="s.paper.exec.sim",
                        timestamp=Instant(ts_now),
                        ingest_ts=Instant(ts_now),
                        correlation_id=ULID(str(order.correlation_id)),
                        causation_id=ULID(str(order.paper_order_id)),
                        run_mode=RunMode.PAPER,
                        source_type=SourceType.SIMULATED,
                        clock_ref=cr,
                        quality_flags=qf,
                        schema_ref=SchemaRef(),
                        extra={
                            "spread_bps": result.spread_cost_applied_bps,
                            "slippage_bps": result.slippage_applied_bps,
                            "latency_ms": result.latency_ms_applied,
                            "ref_price": str(result.reference_price_used),
                            "fill_ratio": str(result.fill_ratio_applied),
                            "info_codes": list(result.info_codes),
                        },
                        payload=fill,
                    )
                    self.event_bus.publish_with_causation(
                        envelope,
                        parent_event_id=str(order.paper_order_id),
                    )
                except BaseException as exc:  # noqa: BLE001
                    result.info_codes.append(
                        f"P10_INFO_BUS_EXC:{type(exc).__name__}"
                    )
                    pass

            self.last_reject_reasons = []
            self.last_info_codes = list(result.info_codes)
            return result

        except BaseException as exc:  # noqa: BLE001  # AD-19 fail-closed
            result.rejected = True
            tag = f"{PaperFillRejectReason.AD19_SIM_EXCEPTION.value}:{type(exc).__name__}"
            result.reject_reasons.append(tag)
            self.last_reject_reasons = list(result.reject_reasons)
            return result

    # ===== Convenience: publish rejected explicitly on bus (optional) =====
    def publish_rejection(
        self,
        *,
        order: PaperOrder,
        result: PaperFillResult,
        reference: PipelineReferenceData,
        quality_ctx: QualityFlags | None = None,
    ) -> None:
        if not result.rejected or self.event_bus is None:
            return
        try:
            sym = reference.symbol if reference.symbol else Symbol("")
            ts = result.fill_ts or str(order.updated_at)
            cr = reference.clock_ref or ClockRef(wall=Instant(ts))
            qf = quality_ctx or QualityFlags()
            event_id = _new_fill_id(
                str(order.correlation_id), str(order.paper_order_id), suffix="rej"
            )
            envelope = CanonicalEventEnvelope(
                event_id=ULID(event_id),
                event_type="paper_fill_rejected.v1",
                contract_version=CONTRACT_VERSION,
                symbol=sym if sym else None,
                source="s.paper.exec.sim",
                timestamp=Instant(ts),
                ingest_ts=Instant(ts),
                correlation_id=ULID(str(order.correlation_id)),
                causation_id=ULID(str(order.paper_order_id)),
                run_mode=RunMode.PAPER,
                source_type=SourceType.SIMULATED,
                clock_ref=cr,
                quality_flags=qf,
                schema_ref=SchemaRef(),
                extra={
                    "reject_reasons": list(result.reject_reasons),
                    "info_codes": list(result.info_codes),
                },
                payload=None,
            )
            self.event_bus.publish_with_causation(
                envelope,
                parent_event_id=str(order.paper_order_id),
            )
        except BaseException:  # noqa: BLE001
            pass
