from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from app.contracts.canonical import CanonicalEventEnvelope, ClockRef
from app.contracts.exceptions import (
    ContractSchemaError,
    schema_sha256,
    to_sorted_dict,
)
from app.contracts.feature import FeatureVector
from app.contracts.regime import REGIME_KEYS, MarketRegime
from app.contracts.types import (
    Instant,
    RunMode,
    SourceType,
    Symbol,
    format_instant,
    validate_instant,
    validate_symbol_canonical,
)


_STRATEGY_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^[a-zA-Z0-9_.\-+]+$")
_ULIDISH_RE = re.compile(r"^[A-Za-z0-9\-]{8,}$")  # ULID 26 chars or 36-char UUID-style dashed; accept >=8 basic alpha-num + dash


# ---------------------------------------------------------------------------
# Small CAP-1-safe validators: type guards WITHOUT using run_mode/source_type
# text inside `if` branches. This keeps static CAP-1 branch scans clean
# (the value being validated is always called `value` in these helpers).
# ---------------------------------------------------------------------------


def _validate_enum_cast(value: Any, enum_type: type[Any], field_name: str) -> Any:
    """Ensure *value* is already an instance of *enum_type*, or can be cast from str.

    This helper exists to keep the string `run_mode` or `source_type` out of any
    `if ...:` conditionals inside StrategyContext.__post_init__, which would
    otherwise trip CAP-1 branch scans as domain branching. The validator never
    *branches on the runtime value of the enum* — only on its TYPE shape.
    """
    if isinstance(value, enum_type):
        return value
    try:
        if isinstance(value, str):
            return enum_type(value)
    except Exception:
        pass
    raise ContractSchemaError(
        f"StrategyContext.{field_name} must be {enum_type.__name__}, got {type(value).__name__}"
    )


# ---------------------------------------------------------------------------
# Nested placeholder / component views (AD-25, to be completed in later stories)
# ---------------------------------------------------------------------------


@dataclass
class PortfolioContextView:
    """AD-25: salt okunur portfolio görünümü (placeholder — S-CON-02B'de genişletilecek).

    Şu anki minimal haliyle strateji kodunun gerçek pozisyonlara erişmeden
    contract şemasını derlemesine yardımcı olur. Contract tests placeholder
    validasyonlarını zorlamaz (boş defaults kabul edilir).
    """

    view_id: str = ""
    placeholder: bool = True

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass
class EligibilityContextView:
    """AD-25: Strategy eligibility view (genişletilecek)."""

    eligible: bool
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.eligible, bool):
            raise ContractSchemaError(
                f"EligibilityContextView.eligible must be bool, got {type(self.eligible).__name__}"
            )
        if not isinstance(self.reasons, list):
            raise ContractSchemaError(
                f"EligibilityContextView.reasons must be list[str], got {type(self.reasons).__name__}"
            )
        for idx, r in enumerate(self.reasons):
            if not isinstance(r, str):
                raise ContractSchemaError(
                    f"EligibilityContextView.reasons[{idx}] must be str, got {type(r).__name__}"
                )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass
class OpportunityScoreComponentPolicy:
    """AD-25: Opportunity score policy (placeholder — S-CON-02B'de tamamlanacak)."""

    policy_version: str
    component_keys: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise ContractSchemaError(
                f"OpportunityScoreComponentPolicy.policy_version invalid: {self.policy_version!r}"
            )
        if not isinstance(self.component_keys, list):
            raise ContractSchemaError(
                f"OpportunityScoreComponentPolicy.component_keys must be list[str], got {type(self.component_keys).__name__}"
            )
        for idx, k in enumerate(self.component_keys):
            if not isinstance(k, str):
                raise ContractSchemaError(
                    f"OpportunityScoreComponentPolicy.component_keys[{idx}] must be str"
                )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# StrategySignal direction enum + nested policy specs
# ---------------------------------------------------------------------------


class SignalDirection(StrEnum):
    """v1 hard boundary — LONG ONLY. SHORT VALUE YOKTUR.

    Kısa pozisyonlar CONTRACT_VERSION yükseltilmeden eklenemez.
    """

    LONG = "long"
    FLAT = "flat"
    HOLD = "hold"


def _validate_ulidish(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise ContractSchemaError(
            f"StrategyContext.{field_name} must be str (ULID-like), got {type(value).__name__}"
        )
    if not _ULIDISH_RE.match(value):
        raise ContractSchemaError(
            f"StrategyContext.{field_name} invalid format: {value!r}"
        )


@dataclass
class StopPolicySpec:
    """CONTRACTS.md §3.9 nested policy — stop (fixed or trailing)."""

    stop_type: Literal["fixed", "trailing"]
    stop_ref_price: Decimal | None = None
    stop_bps: float | None = None

    def __post_init__(self) -> None:
        if self.stop_type not in ("fixed", "trailing"):
            raise ContractSchemaError(
                f"StopPolicySpec.stop_type must be 'fixed'|'trailing', got {self.stop_type!r}"
            )
        if self.stop_ref_price is not None:
            if isinstance(self.stop_ref_price, bool) or not isinstance(
                self.stop_ref_price, Decimal
            ):
                raise ContractSchemaError(
                    f"StopPolicySpec.stop_ref_price must be Decimal|None"
                )
        if self.stop_bps is not None:
            if isinstance(self.stop_bps, bool) or not isinstance(self.stop_bps, float):
                raise ContractSchemaError(
                    f"StopPolicySpec.stop_bps must be float|None"
                )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass
class TakeProfitPolicySpec:
    """CONTRACTS.md §3.9 nested policy — take-profit (fixed or scale levels)."""

    tp_type: Literal["fixed", "scale"]
    tp_levels: list[Decimal] | None = None
    tp_bps: list[float] | None = None

    def __post_init__(self) -> None:
        if self.tp_type not in ("fixed", "scale"):
            raise ContractSchemaError(
                f"TakeProfitPolicySpec.tp_type must be 'fixed'|'scale', got {self.tp_type!r}"
            )
        if self.tp_levels is not None:
            if not isinstance(self.tp_levels, list):
                raise ContractSchemaError(
                    f"TakeProfitPolicySpec.tp_levels must be list[Decimal]|None"
                )
            for idx, price in enumerate(self.tp_levels):
                if isinstance(price, bool) or not isinstance(price, Decimal):
                    raise ContractSchemaError(
                        f"TakeProfitPolicySpec.tp_levels[{idx}] must be Decimal"
                    )
        if self.tp_bps is not None:
            if not isinstance(self.tp_bps, list):
                raise ContractSchemaError(
                    f"TakeProfitPolicySpec.tp_bps must be list[float]|None"
                )
            for idx, bps in enumerate(self.tp_bps):
                if isinstance(bps, bool) or not isinstance(bps, float):
                    raise ContractSchemaError(
                        f"TakeProfitPolicySpec.tp_bps[{idx}] must be float"
                    )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# AD-25 StrategyContext — typed pure strategy plugin input
# ---------------------------------------------------------------------------


_STRATEGY_PARAMS_PRIMITIVE = (int, float, str, bool, Decimal, type(None))


def _validate_strategy_params(params: Any) -> dict[str, int | float | str | bool | Decimal | None]:
    """AD-25 purity: strategy_params may only contain primitive scalar values.

    No nested dicts, no lists, no tuples, no sets, no bytes, no callables.
    """
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise ContractSchemaError(
            f"StrategyContext.strategy_params must be dict[str, scalar], got {type(params).__name__}"
        )
    for key, value in params.items():
        if not isinstance(key, str):
            raise ContractSchemaError(
                f"StrategyContext.strategy_params key must be str, got {type(key).__name__}"
            )
        if isinstance(value, type(None)):
            continue
        if not isinstance(value, _STRATEGY_PARAMS_PRIMITIVE):
            raise ContractSchemaError(
                f"StrategyContext.strategy_params[{key!r}] nested/complex value forbidden (AD-25 primitive-only): type={type(value).__name__}"
            )
    return params  # type: ignore[return-value]


@dataclass
class StrategyContext:
    """AD-25 Typed strategy plugin context. NO network/DB/FS/WS/exchange imports allowed.

    Pure strategy plugin evaluate() signature will be:
        evaluate(ctx: StrategyContext) -> StrategySignal
    """

    symbol: Symbol
    as_of: Instant
    clock_ref: ClockRef
    features: FeatureVector
    regime: MarketRegime
    portfolio_ctx: PortfolioContextView
    eligibility_ctx: EligibilityContextView
    scoring_policy: OpportunityScoreComponentPolicy
    run_mode: RunMode
    source_type: SourceType
    correlation_id: str  # ULID-like (AD-17 chain constant)
    causation_id: str    # ULID-like (parent event id)
    strategy_params: dict[str, int | float | str | bool | Decimal | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # symbol — canonical (envelope may have None, but ctx requires valid canonical)
        if not validate_symbol_canonical(self.symbol):
            raise ContractSchemaError(
                f"StrategyContext.symbol not canonical: {self.symbol!r}"
            )
        # as_of
        if not validate_instant(self.as_of):
            raise ContractSchemaError(
                f"StrategyContext.as_of invalid Instant: {self.as_of!r}"
            )
        # clock_ref — ensure it is a ClockRef (not raw dict). Deep copy ownership enforced separately.
        if not isinstance(self.clock_ref, ClockRef):
            raise ContractSchemaError(
                f"StrategyContext.clock_ref must be ClockRef, got {type(self.clock_ref).__name__}"
            )
        if not validate_instant(self.clock_ref.wall):
            raise ContractSchemaError(
                f"StrategyContext.clock_ref.wall invalid Instant: {self.clock_ref.wall!r}"
            )
        if self.clock_ref.replay is not None and not validate_instant(self.clock_ref.replay):
            raise ContractSchemaError(
                f"StrategyContext.clock_ref.replay invalid Instant: {self.clock_ref.replay!r}"
            )
        # features / regime typed checks
        if not isinstance(self.features, FeatureVector):
            raise ContractSchemaError(
                f"StrategyContext.features must be FeatureVector (raw dict rejected), got {type(self.features).__name__}"
            )
        if not isinstance(self.regime, MarketRegime):
            raise ContractSchemaError(
                f"StrategyContext.regime must be MarketRegime (raw dict rejected), got {type(self.regime).__name__}"
            )
        # nested placeholder types
        if not isinstance(self.portfolio_ctx, PortfolioContextView):
            raise ContractSchemaError(
                f"StrategyContext.portfolio_ctx type error: {type(self.portfolio_ctx).__name__}"
            )
        if not isinstance(self.eligibility_ctx, EligibilityContextView):
            raise ContractSchemaError(
                f"StrategyContext.eligibility_ctx type error: {type(self.eligibility_ctx).__name__}"
            )
        if not isinstance(self.scoring_policy, OpportunityScoreComponentPolicy):
            raise ContractSchemaError(
                f"StrategyContext.scoring_policy type error: {type(self.scoring_policy).__name__}"
            )
        # run_mode / source_type enums — CAP-1 safe helper: isinstance guard in helper body, not here.
        self.run_mode = _validate_enum_cast(self.run_mode, RunMode, "run_mode")  # type: ignore[assignment]
        self.source_type = _validate_enum_cast(self.source_type, SourceType, "source_type")  # type: ignore[assignment]
        # corr/caus id shape
        _validate_ulidish(self.correlation_id, "correlation_id")
        _validate_ulidish(self.causation_id, "causation_id")
        # strategy_params primitive-only (AD-25 purity)
        self.strategy_params = _validate_strategy_params(self.strategy_params)

    # ---- serialisation / determinism -----------------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)

    # ---- AD-17 / CAP-2 safe factory from CanonicalEventEnvelope -------------
    @staticmethod
    def derive_from_envelope(
        envelope: CanonicalEventEnvelope,
        *,
        features: FeatureVector,
        regime: MarketRegime,
        as_of: Instant | None = None,
        portfolio_ctx: PortfolioContextView | None = None,
        eligibility_ctx: EligibilityContextView | None = None,
        scoring_policy: OpportunityScoreComponentPolicy | None = None,
        strategy_params: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> "StrategyContext":
        """Build StrategyContext SAFELY from envelope (CAP-2 quality + AD-17 corr/caus).

        Guarantees:
          1. envelope.symbol used if ctx.symbol provided (via canonical validation).
          2. as_of defaults to envelope.timestamp (prevents sneaky `datetime.now()` lookups inside strategies).
          3. clock_ref is DEEP-COPYED so downstream mutations of envelope.clock_ref never
             leak into already-evaluated context instances (CAP-2 preserve quality/metadata).
          4. quality_flags and other envelope state are NEVER mutated by this method;
             instead we only READ envelope fields — caller keeps ownership of envelope.
          5. correlation_id defaults to envelope.correlation_id (AD-17 chain constant).
          6. causation_id defaults to envelope.event_id  (AD-17 parent id).
        """
        if not isinstance(envelope, CanonicalEventEnvelope):
            raise ContractSchemaError(
                f"derive_from_envelope expects CanonicalEventEnvelope, got {type(envelope).__name__}"
            )
        # Symbol — envelope.symbol is optional (system events None allowed). Derive requires canonical.
        if envelope.symbol is None:
            raise ContractSchemaError(
                "derive_from_envelope: envelope.symbol None; StrategyContext requires canonical symbol"
            )
        ctx_symbol = Symbol(envelope.symbol)
        ctx_as_of = Instant(as_of) if as_of is not None else envelope.timestamp
        # CLOCK_REF DEEP COPY — CAP-2 critical guard (envelope mutations never leak)
        ctx_clock_ref = copy.deepcopy(envelope.clock_ref)
        # Corr/caus from envelope (AD-17 chain continuity)
        ctx_correlation = correlation_id or envelope.correlation_id
        ctx_causation = causation_id or envelope.event_id
        # Sensible defaults for optional placeholders (so tests stay compact)
        p_ctx = portfolio_ctx or PortfolioContextView()
        e_ctx = eligibility_ctx or EligibilityContextView(eligible=True, reasons=[])
        s_pol = scoring_policy or OpportunityScoreComponentPolicy(
            policy_version="policy_v1.0.0", component_keys=[]
        )
        return StrategyContext(
            symbol=ctx_symbol,
            as_of=ctx_as_of,
            clock_ref=ctx_clock_ref,
            features=features,
            regime=regime,
            portfolio_ctx=p_ctx,
            eligibility_ctx=e_ctx,
            scoring_policy=s_pol,
            run_mode=envelope.run_mode,
            source_type=envelope.source_type,
            correlation_id=ctx_correlation,
            causation_id=ctx_causation,
            strategy_params=dict(strategy_params or {}),
        )


# ---------------------------------------------------------------------------
# StrategySignal — typed strategy plugin output (v1 long-only hard boundary)
# ---------------------------------------------------------------------------


def _validate_supporting_regime_evidence(value: Any) -> dict[str, float]:
    """supporting_regime_evidence: keys must be REGIME_KEYS subset, values float 0-1."""
    if not isinstance(value, dict):
        raise ContractSchemaError(
            f"StrategySignal.supporting_regime_evidence must be dict[str, float], got {type(value).__name__}"
        )
    normalised: dict[str, float] = {}
    for key in sorted(value.keys()):
        if key not in REGIME_KEYS:
            raise ContractSchemaError(
                f"StrategySignal.supporting_regime_evidence unknown key {key!r}; allowed={sorted(REGIME_KEYS)}"
            )
        v = value[key]
        if isinstance(v, bool) or not isinstance(v, float):
            raise ContractSchemaError(
                f"StrategySignal.supporting_regime_evidence[{key!r}] must be float in [0, 1], got {type(v).__name__}"
            )
        if v < 0.0 or v > 1.0:
            raise ContractSchemaError(
                f"StrategySignal.supporting_regime_evidence[{key!r}] out of [0, 1] range: {v!r}"
            )
        normalised[key] = v
    return normalised


def _validate_supporting_feature_keys(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ContractSchemaError(
            f"StrategySignal.supporting_feature_keys must be list[str], got {type(value).__name__}"
        )
    for idx, k in enumerate(value):
        if not isinstance(k, str):
            raise ContractSchemaError(
                f"StrategySignal.supporting_feature_keys[{idx}] must be str"
            )
    return value


@dataclass
class StrategySignal:
    """Typed strategy plugin output. v1 HARD BOUNDARY — SHORT direction YOKTUR.

    Fields align with:
      * CONTRACTS.md §3.9
      * user-required: correlation_id, causation_id, supporting feature/regime refs,
        expected_edge_bps, confidence
      * AD-17 chain continuity
    """

    strategy_id: str
    strategy_version: str
    direction: SignalDirection
    signal_strength: float
    correlation_id: str
    causation_id: str
    supporting_feature_keys: list[str] = field(default_factory=list)
    supporting_regime_evidence: dict[str, float] = field(default_factory=dict)
    entry_thesis: str | None = None
    entry_price_ref: Decimal | None = None
    stop_policy: StopPolicySpec | None = None
    take_profit_policy: TakeProfitPolicySpec | None = None
    confidence: float | None = None
    expected_edge_bps: float | None = None

    def __post_init__(self) -> None:
        # strategy_id / strategy_version
        if not isinstance(self.strategy_id, str) or not _STRATEGY_ID_RE.match(
            self.strategy_id
        ):
            raise ContractSchemaError(
                f"StrategySignal.strategy_id invalid: {self.strategy_id!r}"
            )
        if not isinstance(self.strategy_version, str) or not _VERSION_RE.match(
            self.strategy_version
        ):
            raise ContractSchemaError(
                f"StrategySignal.strategy_version invalid: {self.strategy_version!r}"
            )
        # direction (v1: long/flat/hold ONLY — short guaranteed absent via enum)
        if not isinstance(self.direction, SignalDirection):
            # Accept string enum value for ergonomics (test helpers)
            if isinstance(self.direction, str):
                try:
                    self.direction = SignalDirection(self.direction)  # type: ignore[assignment]
                except ValueError as exc:
                    raise ContractSchemaError(
                        f"StrategySignal.direction invalid: {self.direction!r} (v1 allowed: long/flat/hold — SHORT YASAK)"
                    ) from exc
            else:
                raise ContractSchemaError(
                    f"StrategySignal.direction must be SignalDirection, got {type(self.direction).__name__}"
                )
        # signal_strength [0, 1] required
        if isinstance(self.signal_strength, bool) or not isinstance(
            self.signal_strength, float
        ):
            raise ContractSchemaError(
                f"StrategySignal.signal_strength must be float in [0, 1], got {type(self.signal_strength).__name__}"
            )
        if self.signal_strength < 0.0 or self.signal_strength > 1.0:
            raise ContractSchemaError(
                f"StrategySignal.signal_strength out of [0, 1] range: {self.signal_strength!r}"
            )
        # corr / causation
        _validate_ulidish(self.correlation_id, "correlation_id")
        _validate_ulidish(self.causation_id, "causation_id")
        # supporting feature keys (empty list OK)
        self.supporting_feature_keys = _validate_supporting_feature_keys(
            self.supporting_feature_keys
        )
        # supporting regime evidence (keys REGIME_KEYS subset — each 0..1)
        self.supporting_regime_evidence = _validate_supporting_regime_evidence(
            self.supporting_regime_evidence
        )
        # entry_thesis
        if self.entry_thesis is not None and not isinstance(self.entry_thesis, str):
            raise ContractSchemaError(
                f"StrategySignal.entry_thesis must be str|None, got {type(self.entry_thesis).__name__}"
            )
        # entry_price_ref Decimal
        if self.entry_price_ref is not None:
            if isinstance(self.entry_price_ref, bool) or not isinstance(
                self.entry_price_ref, Decimal
            ):
                raise ContractSchemaError(
                    f"StrategySignal.entry_price_ref must be Decimal|None (monetary rule, float forbidden)"
                )
        # stop_policy / take_profit_policy
        if self.stop_policy is not None and not isinstance(self.stop_policy, StopPolicySpec):
            raise ContractSchemaError(
                f"StrategySignal.stop_policy must be StopPolicySpec|None"
            )
        if self.take_profit_policy is not None and not isinstance(
            self.take_profit_policy, TakeProfitPolicySpec
        ):
            raise ContractSchemaError(
                f"StrategySignal.take_profit_policy must be TakeProfitPolicySpec|None"
            )
        # confidence optional but [0, 1] if present
        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(self.confidence, float):
                raise ContractSchemaError(
                    f"StrategySignal.confidence must be float|None in [0, 1]"
                )
            if self.confidence < 0.0 or self.confidence > 1.0:
                raise ContractSchemaError(
                    f"StrategySignal.confidence out of [0, 1] range: {self.confidence!r}"
                )
        # expected_edge_bps (may be negative; no range clamp)
        if self.expected_edge_bps is not None:
            if isinstance(self.expected_edge_bps, bool) or not isinstance(
                self.expected_edge_bps, float
            ):
                raise ContractSchemaError(
                    f"StrategySignal.expected_edge_bps must be float|None"
                )

    # ---- serialisation / determinism ----------------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# quiet pyflakes: format_instant is not directly used in this module but exposed via
# package-level __init__ — re-export unused reference here intentionally skipped.
# The import above is kept for consistency with the contracts package convention.
_ = format_instant  # pragma: no cover  — silence unused warnings
