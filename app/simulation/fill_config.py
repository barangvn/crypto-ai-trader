from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from app.contracts.paper import PaperFill


FILL_MODEL_VERSION: Literal["1.0.0"] = "1.0.0"


class PaperFillRejectReason(StrEnum):
    P1_ORDER_STATUS_NOT_FILLABLE = "P1_ORDER_STATUS_NOT_FILLABLE"
    P1_QTY_NOT_POSITIVE = "P1_QTY_NOT_POSITIVE"
    P1_RISK_DECISION_ID_MISSING = "P1_RISK_DECISION_ID_MISSING"
    P1_SIDE_INVALID = "P1_SIDE_INVALID"
    P1_ORDER_TYPE_UNSUPPORTED = "P1_ORDER_TYPE_UNSUPPORTED"
    P2_QUALITY_STALE = "P2_QUALITY_STALE_DATA_REJECTED"
    P2_QUALITY_INVALID = "P2_QUALITY_INVALID_DATA_REJECTED"
    P2_QUALITY_QUARANTINED = "P2_QUALITY_QUARANTINED_REJECTED"
    P2_QUALITY_DUPLICATE = "P2_QUALITY_DATA_INTEGRITY_DUPLICATE"
    P2_QUALITY_OUT_OF_ORDER = "P2_QUALITY_DATA_INTEGRITY_OUT_OF_ORDER"
    P2_QUALITY_MISSING = "P2_QUALITY_DATA_INTEGRITY_MISSING"
    P3_LATENCY_NEGATIVE = "P3_LATENCY_NEGATIVE_REJECTED"
    P3_LATENCY_EXCEEDS_MAX = "P3_LATENCY_EXCEEDS_MAX_CAP"
    P4_NO_MARKET_REFERENCE = "P4_NO_MARKET_REFERENCE_AVAILABLE"
    P4_CANDLE_NOT_CLOSED = "P4_CANDLE_NOT_CLOSED_LOOK_AHEAD_RISK"
    P4_BID_ASK_CROSS = "P4_BID_ASK_CROSS_INVALID_MARKET"
    P5_SPREAD_NEGATIVE = "P5_SPREAD_NEGATIVE_INVALID"
    P5_SPREAD_TOO_LARGE = "P5_SPREAD_TOO_LARGE_BEYOND_SAFETY_CAP"
    P6_SLIPPAGE_NEGATIVE = "P6_SLIPPAGE_NEGATIVE_INVALID"
    P6_SLIPPAGE_EXCEEDS_MAX = "P6_SLIPPAGE_EXCEEDS_MAX_SAFETY_CAP"
    P7_FEE_NEGATIVE = "P7_FEE_NEGATIVE_INVALID"
    P7_FEE_EXCEEDS_SAFETY = "P7_FEE_EXCEEDS_SAFETY_CAP"
    P8_FILL_RATIO_ZERO = "P8_FILL_RATIO_ZERO_INVALID"
    P8_FILL_RATIO_GT_ONE = "P8_FILL_RATIO_GREATER_THAN_ONE"
    P8_FILL_QTY_NOT_POSITIVE = "P8_FILL_QTY_NOT_POSITIVE"
    P8_FILL_QTY_EXCEEDS_REQUESTED = "P8_FILL_QTY_EXCEEDS_REQUESTED"
    P9_QUOTE_AMOUNT_MISMATCH = "P9_QUOTE_AMOUNT_INVARIANT_MISMATCH"
    P10_FEE_NOT_POSITIVE = "P10_FEE_MUST_BE_POSITIVE_V1_HARD"
    AD19_SIM_EXCEPTION = "AD19_SIM_EXCEPTION"


@dataclass(frozen=True)
class FillAssumptionsConfig:
    taker_fee_bps: Decimal = Decimal("10")
    maker_fee_bps: Decimal = Decimal("4")
    default_fee_type: Literal["taker", "maker"] = "taker"
    default_spread_bps: float = 5.0
    base_slippage_bps: float = 2.0
    max_slippage_bps: float = 500.0
    base_latency_ms: int = 50
    max_latency_ms: int = 5000
    latency_jitter_ms: int = 10
    fill_ratio: Decimal = Decimal("1.0")
    partial_count_limit: int = 1
    max_spread_bps: float = 1000.0
    max_fee_bps: Decimal = Decimal("100")
    min_fee_quote_floor: Decimal = Decimal("0.00000001")


@dataclass
class PaperFillResult:
    fill: PaperFill | None = None
    rejected: bool = False
    reject_reasons: list[str] = field(default_factory=list)
    info_codes: list[str] = field(default_factory=list)
    fill_ts: str | None = None
    latency_ms_applied: int | None = None
    reference_price_used: Decimal | None = None
    spread_cost_applied_bps: float | None = None
    slippage_applied_bps: float | None = None
    fee_bps_applied: Decimal | None = None
    fill_ratio_applied: Decimal | None = None
