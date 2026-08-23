from __future__ import annotations

from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.exceptions import (
    ContractSchemaError,
    deep_copy,
    schema_sha256,
    to_sorted_dict,
)
from app.contracts.feature import (
    FEATURE_SCHEMA_REGISTRY,
    FeatureSchemaSpec,
    FeatureVector,
    LookbackWindowSpec,
    register_feature_schema,
    validate_feature_vector_features,
)
from app.contracts.market import (
    Candle,
    MarketTick,
    OrderBookSnapshot,
    OrderBookUpdate,
    TradeEvent,
)
from app.contracts.regime import (
    MarketRegime,
    MarketRegimeState,
    REGIME_KEYS,
    TimeRangeSpec,
)
from app.contracts.paper import (
    PaperFill,
    PaperOrder,
    PaperOrderPolicyRefs,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    TimeInForce,
)
from app.contracts.portfolio import (
    PortfolioSnapshot,
    Position,
    PositionSide,
)
from app.contracts.risk import (
    KillSwitchStateSpec,
    LimitsSnapshot,
    PositionSizingSpec,
    RiskDecision,
    RiskDecisionResult,
)
from app.contracts.opportunity import (
    OpportunityScore,
)
from app.contracts.model import (
    CCWinnerEnum,
    ChampionChallengerEvaluation,
    DatasetKindEnum,
    ModelCompatibilityRef,
    ModelEvaluation,
    ModelLifecycleStatus,
    ModelLifecycleTransition,
    ModelPurposeEnum,
    ModelRef,
    ModelVersion,
    PromotionGateResult,
    TrainingDataRange,
)
from app.contracts.strategy import (
    EligibilityContextView,
    OpportunityScoreComponentPolicy,
    PortfolioContextView,
    SignalDirection,
    StopPolicySpec,
    StrategyContext,
    StrategySignal,
    TakeProfitPolicySpec,
)
from app.contracts.types import (
    ContractVersion,
    Instant,
    RunMode,
    SourceType,
    Symbol,
    ULID,
    format_instant,
    normalize_symbol,
    validate_instant,
    validate_symbol_canonical,
)


CONTRACT_VERSION: ContractVersion = ContractVersion("1.0.0")


def now_instant() -> Instant:
    return format_instant()


__all__ = [
    "CONTRACT_VERSION",
    "ContractVersion",
    "Instant",
    "Symbol",
    "ULID",
    "RunMode",
    "SourceType",
    "QualityFlags",
    "ClockRef",
    "SchemaRef",
    "CanonicalEventEnvelope",
    "MarketTick",
    "TradeEvent",
    "OrderBookSnapshot",
    "OrderBookUpdate",
    "Candle",
    "format_instant",
    "validate_instant",
    "normalize_symbol",
    "validate_symbol_canonical",
    "now_instant",
    # ————— S-CON-02A new contracts (appended — existing order preserved) —————
    "ContractSchemaError",
    "deep_copy",
    "FEATURE_SCHEMA_REGISTRY",
    "FeatureSchemaSpec",
    "FeatureVector",
    "LookbackWindowSpec",
    "register_feature_schema",
    "validate_feature_vector_features",
    "MarketRegime",
    "MarketRegimeState",
    "REGIME_KEYS",
    "TimeRangeSpec",
    "PortfolioContextView",
    "EligibilityContextView",
    "OpportunityScoreComponentPolicy",
    "SignalDirection",
    "StopPolicySpec",
    "TakeProfitPolicySpec",
    "StrategyContext",
    "StrategySignal",
    # ————— S-CON-02B: RiskDecision + PaperOrder + PaperFill + Position + PortfolioSnapshot (appended END — preserved prior order) —————
    "RiskDecisionResult",
    "PositionSizingSpec",
    "LimitsSnapshot",
    "KillSwitchStateSpec",
    "RiskDecision",
    "PaperOrderSide",
    "PaperOrderType",
    "TimeInForce",
    "PaperOrderStatus",
    "PaperOrderPolicyRefs",
    "PaperOrder",
    "PaperFill",
    "PositionSide",
    "Position",
    "PortfolioSnapshot",
    "schema_sha256",
    "to_sorted_dict",
    # ————— S-CON-02C: OpportunityScore + Model Lifecycle + Champion/Challenger (appended END — prior order preserved) —————
    "OpportunityScore",
    "ModelLifecycleStatus",
    "ModelPurposeEnum",
    "DatasetKindEnum",
    "CCWinnerEnum",
    "TrainingDataRange",
    "ModelCompatibilityRef",
    "PromotionGateResult",
    "ModelRef",
    "ModelVersion",
    "ModelEvaluation",
    "ModelLifecycleTransition",
    "ChampionChallengerEvaluation",
]
