from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.contracts.canonical import QualityFlags
from app.contracts.exceptions import (
    ContractSchemaError,
    schema_sha256,
    to_sorted_dict,
)
from app.contracts.types import (
    Instant,
    ULID,
    validate_instant,
)


_ULIDISH_RE = re.compile(r"^[A-Za-z0-9_\-]{8,}$")
_VERSION_RE = re.compile(r"^[a-zA-Z0-9_.\-+]+$")
_MODEL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ARTIFACT_URI_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\+\.\-]+://[^\s]+$")


def _validate_ulidish(value: Any, field_name: str, contract: str = "Model") -> None:
    if not isinstance(value, str):
        raise ContractSchemaError(
            f"{contract}.{field_name} must be str (ULID-like), got {type(value).__name__}"
        )
    if not _ULIDISH_RE.match(value):
        raise ContractSchemaError(
            f"{contract}.{field_name} invalid format: {value!r}"
        )


# ---------------------------------------------------------------------------
# 4 Enum setleri (tam sayılar EXACT — yeni değerler ancak CONTRACT_VERSION bump'ı ile)
# ---------------------------------------------------------------------------


class ModelLifecycleStatus(StrEnum):
    """AD-14 Governed Learning Lifecycle 6-State FSM — EXACT 6 değer.

    Forbidden transitions: see _FSM_ALLOWED below. Anything not in allowed raises.
    """

    CANDIDATE = "candidate"
    TESTED = "tested"
    PAPER = "paper"
    CHALLENGER = "challenger"
    CHAMPION = "champion"
    RETIRED = "retired"


class ModelPurposeEnum(StrEnum):
    """5-purpose model taxonomy — EXACT 5 değer."""

    DIRECTIONAL = "directional"
    REGIME_DETECTOR = "regime_detector"
    FEATURE_ENGINEERING = "feature_engineering"
    EXECUTION_POLICY = "execution_policy"
    COST_MODEL = "cost_model"


class DatasetKindEnum(StrEnum):
    """4-dataset evaluation taxonomy — EXACT 4 değer."""

    IN_SAMPLE = "in_sample"
    WALK_FORWARD = "walk_forward"
    OUT_OF_SAMPLE = "out_of_sample"
    PAPER_TRADING = "paper_trading"


class CCWinnerEnum(StrEnum):
    """3-way Champion/Challenger result — EXACT 3 değer."""

    CHAMPION_KEEPS = "champion_keeps"
    CHALLENGER_PROMOTED = "challenger_promoted"
    INCONCLUSIVE_RERUN = "inconclusive_rerun"


# ---------------------------------------------------------------------------
# 9 İzinli + 7 Yasaklı geçiş tanımı (LIFECYCLE.md authoritative)
# from → set(allowed_to)
# ---------------------------------------------------------------------------


_FSM_ALLOWED: dict[str, set[str]] = {
    ModelLifecycleStatus.CANDIDATE.value: {
        ModelLifecycleStatus.TESTED.value,
        ModelLifecycleStatus.RETIRED.value,  # admin retire (emergency)
    },
    ModelLifecycleStatus.TESTED.value: {
        ModelLifecycleStatus.PAPER.value,
        ModelLifecycleStatus.RETIRED.value,  # admin retire
    },
    ModelLifecycleStatus.PAPER.value: {
        ModelLifecycleStatus.CHALLENGER.value,
        ModelLifecycleStatus.RETIRED.value,  # admin retire
    },
    ModelLifecycleStatus.CHALLENGER.value: {
        ModelLifecycleStatus.CHAMPION.value,
        ModelLifecycleStatus.RETIRED.value,  # admin retire
    },
    ModelLifecycleStatus.CHAMPION.value: {
        ModelLifecycleStatus.RETIRED.value,
    },
    ModelLifecycleStatus.RETIRED.value: set(),  # NO outbound — hard frozen
}


def _validate_fsm_transition(from_s: str, to_s: str) -> None:
    """AD-14/23 + CAP-5: SADECE registry command pattern ile geçiş. Yasaklı HARD FAIL.

    Yasaklı 7 geçiş (hata mesajlarında C-23..28 testlerine gönderme yapılır):
      F1. candidate → champion
      F2. paper → champion (direkt — challenger aşaması atlanıyor)
      F3. tested → champion
      F4. retired → *  (RETIRED'tan GERİ DÖNÜŞ YOKTUR)
      F5. champion → challenger  (champion downgrade YOKTUR)
      F6. challenger → paper (default downgrade YOKTUR)
      F7. tested → candidate (geri dönüş YOKTUR)
    + same-status no-op YASAK (C-29)
    """
    if from_s == to_s:
        raise ContractSchemaError(
            f"ModelLifecycleTransition FSM: from_status == to_status ({from_s!r}) no-op YASAK (C-29)"
        )
    if from_s not in _FSM_ALLOWED:
        raise ContractSchemaError(
            f"ModelLifecycleTransition FSM: unknown from_status {from_s!r}; "
            f"allowed={sorted(ModelLifecycleStatus.__members__.values())}"
        )
    allowed = _FSM_ALLOWED[from_s]
    if to_s not in allowed:
        raise ContractSchemaError(
            f"ModelLifecycleTransition FSM FORBIDDEN: {from_s!r} → {to_s!r}. "
            f"Allowed from {from_s!r}: {sorted(allowed) if allowed else '[] (TERMINAL)'}"
        )


# ---------------------------------------------------------------------------
# 11 Zorunlu Metrik Key — ModelEvaluation.metrics + C/C comparison_metrics İKİSİ de
# ---------------------------------------------------------------------------


_REQUIRED_METRIC_KEYS: tuple[str, ...] = (
    "return_pct",          # Decimal   — parasal return (kesin)
    "max_drawdown_pct",    # float     — [0,1]
    "sharpe_ratio",        # float
    "sortino_ratio",       # float
    "profit_factor",       # float     — 0.0..inf
    "total_fees_quote",    # Decimal   — parasal fee toplamı
    "avg_slippage_bps",    # float     — bps, non-monetary score
    "trade_count",         # int       — non-neg
    "regime_coverage_count",  # int   — non-neg
    "window_days",         # int       — non-neg
    "oos_flag",            # bool      — out-of-sample flag
)


def _validate_metrics_11keys(metrics: Any, field_name: str, contract: str) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        raise ContractSchemaError(
            f"{contract}.{field_name} must be dict with 11 required keys, got {type(metrics).__name__}"
        )
    present = set(metrics.keys())
    required = set(_REQUIRED_METRIC_KEYS)
    missing = required - present
    extra = present - required
    if missing:
        raise ContractSchemaError(
            f"{contract}.{field_name} missing required keys: {sorted(missing)}; required={sorted(required)}"
        )
    # --- type check: Decimal vs Float vs Int vs Bool (Decimal/Float strict ayrımı DoD-15) ---
    m = metrics
    # Parasal: Decimal
    for key_parasal in ("return_pct", "total_fees_quote"):
        v = m[key_parasal]
        if isinstance(v, bool) or not isinstance(v, Decimal):
            raise ContractSchemaError(
                f"{contract}.{field_name}[{key_parasal!r}] must be Decimal (monetary rule, float forbidden), got {type(v).__name__}"
            )
    # Float: drawdown, sharpe, sortino, profit_factor, slippage
    for key_float in (
        "max_drawdown_pct",
        "sharpe_ratio",
        "sortino_ratio",
        "profit_factor",
        "avg_slippage_bps",
    ):
        v = m[key_float]
        if isinstance(v, bool) or not isinstance(v, float):
            raise ContractSchemaError(
                f"{contract}.{field_name}[{key_float!r}] must be float, got {type(v).__name__}"
            )
    # max_drawdown_pct [0, 1] aralığı zorunlu
    dd = m["max_drawdown_pct"]
    if dd < 0.0 or dd > 1.0:
        raise ContractSchemaError(
            f"{contract}.{field_name}.max_drawdown_pct out of [0, 1]: {dd!r}"
        )
    # Int
    for key_int in ("trade_count", "regime_coverage_count", "window_days"):
        v = m[key_int]
        if isinstance(v, bool) or not isinstance(v, int):
            raise ContractSchemaError(
                f"{contract}.{field_name}[{key_int!r}] must be int, got {type(v).__name__}"
            )
        if v < 0:
            raise ContractSchemaError(
                f"{contract}.{field_name}[{key_int!r}] must be >= 0, got {v!r}"
            )
    # Bool
    if not isinstance(m["oos_flag"], bool):
        raise ContractSchemaError(
            f"{contract}.{field_name}[oos_flag] must be bool, got {type(m['oos_flag']).__name__}"
        )
    # Ekstra keys allow edilir (ileriye yönelik extension) ama required ZORUNLU (yukarıda kontrol edildi)
    return dict(metrics)


# ---------------------------------------------------------------------------
# 3 Nested Typed (TrainingDataRange / ModelCompatibilityRef / PromotionGateResult)
# ---------------------------------------------------------------------------


@dataclass
class TrainingDataRange:
    """ModelVersion.training_data_range — başlangıç/bitiş Instant; end >= start zorunlu."""

    start: Instant
    end: Instant

    def __post_init__(self) -> None:
        if not validate_instant(self.start):
            raise ContractSchemaError(
                f"TrainingDataRange.start invalid Instant: {self.start!r}"
            )
        if not validate_instant(self.end):
            raise ContractSchemaError(
                f"TrainingDataRange.end invalid Instant: {self.end!r}"
            )
        if self.end < self.start:
            raise ContractSchemaError(
                f"TrainingDataRange invariant: end ({self.end!r}) < start ({self.start!r})"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass
class ModelCompatibilityRef:
    """ModelVersion.compatibility_ref — feature/strategy/regime version triple;
    her biri non-empty zorunlu."""

    feature_version: str
    strategy_version: str
    regime_version: str

    def __post_init__(self) -> None:
        for fname in ("feature_version", "strategy_version", "regime_version"):
            val = getattr(self, fname)
            if not isinstance(val, str) or not val:
                raise ContractSchemaError(
                    f"ModelCompatibilityRef.{fname} must be non-empty str, got {val!r}"
                )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass
class PromotionGateResult:
    """ChampionChallengerEvaluation.promotion_gate_result — geçti /
    sebepler / hangi thresholds sürümü kullanıldı."""

    passed: bool
    reasons: list[str]
    thresholds_used_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.passed, bool):
            raise ContractSchemaError(
                "PromotionGateResult.passed must be bool"
            )
        if self.reasons is None or not isinstance(self.reasons, list):
            raise ContractSchemaError(
                "PromotionGateResult.reasons must be list[str] (None forbidden)"
            )
        for idx, r in enumerate(self.reasons):
            if not isinstance(r, str):
                raise ContractSchemaError(
                    f"PromotionGateResult.reasons[{idx}] must be str"
                )
        if not isinstance(self.thresholds_used_version, str) or not self.thresholds_used_version:
            raise ContractSchemaError(
                f"PromotionGateResult.thresholds_used_version invalid: {self.thresholds_used_version!r}"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# Yardımcı: hyperparams FLAT DICT kuralı (AD-22 ile aynı — nested dict RAISE)
# ---------------------------------------------------------------------------


_HYPERPARAM_VALUE = (int, float, str, bool, Decimal, type(None))


def _validate_flat_hyperparams(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ContractSchemaError(
            "ModelVersion.hyperparams must be flat dict[str, scalar] (no nested dict/list)"
        )
    for k, v in value.items():
        if not isinstance(k, str) or not k:
            raise ContractSchemaError(
                "ModelVersion.hyperparams keys must be non-empty str"
            )
        if isinstance(v, type(None)):
            continue
        if isinstance(v, (dict, list, tuple, set, bytes)):
            raise ContractSchemaError(
                f"ModelVersion.hyperparams[{k!r}] nested/complex value forbidden (FLAT rule); type={type(v).__name__}"
            )
        if not isinstance(v, _HYPERPARAM_VALUE):
            raise ContractSchemaError(
                f"ModelVersion.hyperparams[{k!r}] unsupported scalar type: {type(v).__name__}"
            )
    return value


# ---------------------------------------------------------------------------
# ModelVersion — 14 alan, 6-enum status, AD-23/CAP-5: status SADECE FSM transition ile değişir
# ---------------------------------------------------------------------------


@dataclass
class ModelVersion:
    """CONTRACTS.md §3.16 ModelVersion — eğitilmiş model artifact ref +
    compatibility + lifecycle metadata.
    """

    model_id: str
    version: str
    purpose: ModelPurposeEnum
    training_data_range: TrainingDataRange
    feature_version: str
    compatibility_ref: ModelCompatibilityRef
    hyperparams: dict[str, Any]
    artifact_uri: str
    status: ModelLifecycleStatus
    created_ts: Instant
    correlation_id: ULID
    causation_id: ULID
    quality_flags: QualityFlags | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    promoted_at: Instant | None = None
    retired_at: Instant | None = None

    def __post_init__(self) -> None:
        # model_id
        if not isinstance(self.model_id, str) or not _MODEL_ID_RE.match(self.model_id):
            raise ContractSchemaError(
                f"ModelVersion.model_id invalid: {self.model_id!r}"
            )
        # version
        if not isinstance(self.version, str) or not _VERSION_RE.match(self.version):
            raise ContractSchemaError(
                f"ModelVersion.version invalid: {self.version!r}"
            )
        # purpose enum
        if not isinstance(self.purpose, ModelPurposeEnum):
            if isinstance(self.purpose, str):
                try:
                    self.purpose = ModelPurposeEnum(self.purpose)  # type: ignore[assignment]
                except ValueError as exc:
                    raise ContractSchemaError(
                        f"ModelVersion.purpose invalid: {self.purpose!r} "
                        f"(allowed 5={sorted(e.value for e in ModelPurposeEnum)})"
                    ) from exc
            else:
                raise ContractSchemaError(
                    f"ModelVersion.purpose must be ModelPurposeEnum, got {type(self.purpose).__name__}"
                )
        # training_data_range nested typed
        if not isinstance(self.training_data_range, TrainingDataRange):
            raise ContractSchemaError(
                "ModelVersion.training_data_range must be TrainingDataRange (raw dict rejected)"
            )
        # feature_version non-empty
        if not isinstance(self.feature_version, str) or not self.feature_version:
            raise ContractSchemaError(
                "ModelVersion.feature_version must be non-empty str"
            )
        # compatibility_ref
        if not isinstance(self.compatibility_ref, ModelCompatibilityRef):
            raise ContractSchemaError(
                "ModelVersion.compatibility_ref must be ModelCompatibilityRef"
            )
        # hyperparams FLAT
        self.hyperparams = _validate_flat_hyperparams(self.hyperparams)
        # artifact_uri
        if not isinstance(self.artifact_uri, str) or not self.artifact_uri:
            raise ContractSchemaError(
                "ModelVersion.artifact_uri must be non-empty str"
            )
        # status enum
        if not isinstance(self.status, ModelLifecycleStatus):
            if isinstance(self.status, str):
                try:
                    self.status = ModelLifecycleStatus(self.status)  # type: ignore[assignment]
                except ValueError as exc:
                    raise ContractSchemaError(
                        f"ModelVersion.status invalid: {self.status!r} "
                        f"(allowed 6={sorted(e.value for e in ModelLifecycleStatus)})"
                    ) from exc
            else:
                raise ContractSchemaError(
                    f"ModelVersion.status must be ModelLifecycleStatus, got {type(self.status).__name__}"
                )
        # created_ts
        if not validate_instant(self.created_ts):
            raise ContractSchemaError(
                f"ModelVersion.created_ts invalid Instant format: {self.created_ts!r}"
            )
        # corr / caus
        _validate_ulidish(self.correlation_id, "correlation_id", "ModelVersion")
        _validate_ulidish(self.causation_id, "causation_id", "ModelVersion")
        # quality_flags
        if self.quality_flags is not None and not isinstance(self.quality_flags, QualityFlags):
            raise ContractSchemaError(
                "ModelVersion.quality_flags must be QualityFlags|None"
            )
        # metadata (flat — nested kabul etmiyoruz ama key str değer herhangi primitive)
        if not isinstance(self.metadata, dict):
            raise ContractSchemaError(
                "ModelVersion.metadata must be dict[str, Any]"
            )
        for k in self.metadata.keys():
            if not isinstance(k, str):
                raise ContractSchemaError(
                    "ModelVersion.metadata keys must be str"
                )
        # promoted_at / retired_at optional Instant
        for fname in ("promoted_at", "retired_at"):
            val = getattr(self, fname)
            if val is not None and not validate_instant(val):
                raise ContractSchemaError(
                    f"ModelVersion.{fname} invalid Instant|None: {val!r}"
                )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# ModelEvaluation — 12 alan, metrics 11 zorunlu key (yukarıda)
# ---------------------------------------------------------------------------


@dataclass
class ModelEvaluation:
    """CONTRACTS.md §3.17 ModelEvaluation — 11 zorunlu metrik + dataset + threshold version."""

    eval_id: ULID
    model_id: str
    model_version: str
    dataset_kind: DatasetKindEnum
    metrics: dict[str, Any]
    evaluation_ts: Instant
    thresholds_config_version: str
    evaluation_window_days: int
    oos_flag: bool
    paper_flag: bool
    correlation_id: ULID
    causation_id: ULID
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_ulidish(self.eval_id, "eval_id", "ModelEvaluation")
        if not isinstance(self.model_id, str) or not _MODEL_ID_RE.match(self.model_id):
            raise ContractSchemaError(
                f"ModelEvaluation.model_id invalid: {self.model_id!r}"
            )
        if not isinstance(self.model_version, str) or not _VERSION_RE.match(self.model_version):
            raise ContractSchemaError(
                f"ModelEvaluation.model_version invalid: {self.model_version!r}"
            )
        # dataset_kind enum
        if not isinstance(self.dataset_kind, DatasetKindEnum):
            if isinstance(self.dataset_kind, str):
                try:
                    self.dataset_kind = DatasetKindEnum(self.dataset_kind)  # type: ignore[assignment]
                except ValueError as exc:
                    raise ContractSchemaError(
                        f"ModelEvaluation.dataset_kind invalid: {self.dataset_kind!r}; "
                        f"allowed={sorted(e.value for e in DatasetKindEnum)}"
                    ) from exc
            else:
                raise ContractSchemaError(
                    f"ModelEvaluation.dataset_kind must be DatasetKindEnum"
                )
        # metrics 11 key + type check
        self.metrics = _validate_metrics_11keys(self.metrics, "metrics", "ModelEvaluation")
        # evaluation_ts
        if not validate_instant(self.evaluation_ts):
            raise ContractSchemaError(
                f"ModelEvaluation.evaluation_ts invalid Instant: {self.evaluation_ts!r}"
            )
        # thresholds_config_version
        if not isinstance(self.thresholds_config_version, str) or not self.thresholds_config_version:
            raise ContractSchemaError(
                f"ModelEvaluation.thresholds_config_version invalid: {self.thresholds_config_version!r}"
            )
        # evaluation_window_days int >=0
        if isinstance(self.evaluation_window_days, bool) or not isinstance(self.evaluation_window_days, int):
            raise ContractSchemaError(
                "ModelEvaluation.evaluation_window_days must be int >= 0"
            )
        if self.evaluation_window_days < 0:
            raise ContractSchemaError(
                f"ModelEvaluation.evaluation_window_days < 0: {self.evaluation_window_days!r}"
            )
        # oos_flag / paper_flag bool
        if not isinstance(self.oos_flag, bool):
            raise ContractSchemaError("ModelEvaluation.oos_flag must be bool")
        if not isinstance(self.paper_flag, bool):
            raise ContractSchemaError("ModelEvaluation.paper_flag must be bool")
        # corr / caus
        _validate_ulidish(self.correlation_id, "correlation_id", "ModelEvaluation")
        _validate_ulidish(self.causation_id, "causation_id", "ModelEvaluation")
        # notes
        if self.notes is not None and not isinstance(self.notes, str):
            raise ContractSchemaError("ModelEvaluation.notes must be str|None")
        # metrics içindeki oos_flag ile contract.oos_flag UYUMLU olmalı (aynıysa OK, değilse RAISE)
        if bool(self.metrics["oos_flag"]) != self.oos_flag:
            raise ContractSchemaError(
                "ModelEvaluation invariant: metrics.oos_flag != contract.oos_flag "
                f"({self.metrics['oos_flag']!r} vs {self.oos_flag!r})"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# ModelLifecycleTransition — FSM ENFORCEMENT (AD-14/23 + CAP-5)
# ---------------------------------------------------------------------------


@dataclass
class ModelLifecycleTransition:
    """CONTRACTS.md §3.18 ModelLifecycleTransition — FSM graph HARD ENFORCE.

    AD-23 (CAP-5): SADECE bu transition event vasıtasıyla ModelVersion.status
    değişebilir; direct assignment contract seviyesinde YOKTUR (doğrulama
    AST single-writer testleri ile yapılır — C-42 / DoD-11).
    """

    transition_id: ULID
    model_id: str
    model_version: str
    from_status: ModelLifecycleStatus
    to_status: ModelLifecycleStatus
    reason: str
    evidence_refs: list[str]
    requested_by: str
    approved_by: str
    requested_ts: Instant
    correlation_id: ULID
    causation_id: ULID
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_ulidish(self.transition_id, "transition_id", "ModelLifecycleTransition")
        if not isinstance(self.model_id, str) or not _MODEL_ID_RE.match(self.model_id):
            raise ContractSchemaError(
                f"ModelLifecycleTransition.model_id invalid: {self.model_id!r}"
            )
        if not isinstance(self.model_version, str) or not _VERSION_RE.match(self.model_version):
            raise ContractSchemaError(
                f"ModelLifecycleTransition.model_version invalid: {self.model_version!r}"
            )
        # from_status enum
        if not isinstance(self.from_status, ModelLifecycleStatus):
            if isinstance(self.from_status, str):
                self.from_status = ModelLifecycleStatus(self.from_status)  # type: ignore[assignment]
            else:
                raise ContractSchemaError(
                    "ModelLifecycleTransition.from_status must be ModelLifecycleStatus"
                )
        # to_status enum
        if not isinstance(self.to_status, ModelLifecycleStatus):
            if isinstance(self.to_status, str):
                self.to_status = ModelLifecycleStatus(self.to_status)  # type: ignore[assignment]
            else:
                raise ContractSchemaError(
                    "ModelLifecycleTransition.to_status must be ModelLifecycleStatus"
                )
        # ===== FSM HARD VALIDATION — AD-14 / CAP-5 =====
        _validate_fsm_transition(self.from_status.value, self.to_status.value)
        # reason non-empty
        if not isinstance(self.reason, str) or not self.reason:
            raise ContractSchemaError(
                "ModelLifecycleTransition.reason must be non-empty str"
            )
        # evidence_refs list[str]
        if not isinstance(self.evidence_refs, list):
            raise ContractSchemaError(
                "ModelLifecycleTransition.evidence_refs must be list[str]"
            )
        for idx, ref in enumerate(self.evidence_refs):
            if not isinstance(ref, str) or not ref:
                raise ContractSchemaError(
                    f"ModelLifecycleTransition.evidence_refs[{idx}] must be non-empty str"
                )
        # requested_by / approved_by non-empty
        for fname in ("requested_by", "approved_by"):
            val = getattr(self, fname)
            if not isinstance(val, str) or not val:
                raise ContractSchemaError(
                    f"ModelLifecycleTransition.{fname} must be non-empty str"
                )
        # requested_ts
        if not validate_instant(self.requested_ts):
            raise ContractSchemaError(
                f"ModelLifecycleTransition.requested_ts invalid Instant: {self.requested_ts!r}"
            )
        # corr / caus
        _validate_ulidish(self.correlation_id, "correlation_id", "ModelLifecycleTransition")
        _validate_ulidish(self.causation_id, "causation_id", "ModelLifecycleTransition")
        # metadata dict
        if not isinstance(self.metadata, dict):
            raise ContractSchemaError(
                "ModelLifecycleTransition.metadata must be dict[str, Any]"
            )
        for k in self.metadata.keys():
            if not isinstance(k, str):
                raise ContractSchemaError(
                    "ModelLifecycleTransition.metadata keys must be str"
                )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


# ---------------------------------------------------------------------------
# ChampionChallengerEvaluation — 13 alan, 11 karşılaştırma metriği + winner 3 enum
# ---------------------------------------------------------------------------


@dataclass
class ModelRef:
    """ChampionChallengerEvaluation.{champion,challenger}_ref nested typed."""

    model_id: str
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.model_id, str) or not _MODEL_ID_RE.match(self.model_id):
            raise ContractSchemaError(
                f"ModelRef.model_id invalid: {self.model_id!r}"
            )
        if not isinstance(self.version, str) or not _VERSION_RE.match(self.version):
            raise ContractSchemaError(
                f"ModelRef.version invalid: {self.version!r}"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass
class ChampionChallengerEvaluation:
    """CONTRACTS.md §3.18 ChampionChallengerEvaluation — promotion gate evidence,
    rollback planı ve approval metadata."""

    cc_id: ULID
    champion_ref: ModelRef
    challenger_ref: ModelRef
    winner: CCWinnerEnum
    comparison_metrics: dict[str, Any]  # 11 zorunlu key (aynı _REQUIRED_METRIC_KEYS)
    evaluation_period_days: int
    promotion_gate_result: PromotionGateResult
    rollback_strategy_ref: str | None
    approval_refs: list[str]
    evaluation_ts: Instant
    correlation_id: ULID
    causation_id: ULID
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_ulidish(self.cc_id, "cc_id", "ChampionChallengerEvaluation")
        # nested typed refs
        if not isinstance(self.champion_ref, ModelRef):
            raise ContractSchemaError(
                "ChampionChallengerEvaluation.champion_ref must be ModelRef"
            )
        if not isinstance(self.challenger_ref, ModelRef):
            raise ContractSchemaError(
                "ChampionChallengerEvaluation.challenger_ref must be ModelRef"
            )
        # winner enum
        if not isinstance(self.winner, CCWinnerEnum):
            if isinstance(self.winner, str):
                try:
                    self.winner = CCWinnerEnum(self.winner)  # type: ignore[assignment]
                except ValueError as exc:
                    raise ContractSchemaError(
                        f"ChampionChallengerEvaluation.winner invalid: {self.winner!r}; "
                        f"allowed 3={sorted(e.value for e in CCWinnerEnum)}"
                    ) from exc
            else:
                raise ContractSchemaError(
                    "ChampionChallengerEvaluation.winner must be CCWinnerEnum"
                )
        # comparison_metrics 11 key
        self.comparison_metrics = _validate_metrics_11keys(
            self.comparison_metrics, "comparison_metrics", "ChampionChallengerEvaluation"
        )
        # evaluation_period_days int >=0
        if isinstance(self.evaluation_period_days, bool) or not isinstance(self.evaluation_period_days, int):
            raise ContractSchemaError(
                "ChampionChallengerEvaluation.evaluation_period_days must be int >= 0"
            )
        if self.evaluation_period_days < 0:
            raise ContractSchemaError(
                f"ChampionChallengerEvaluation.evaluation_period_days < 0: {self.evaluation_period_days!r}"
            )
        # promotion_gate_result nested
        if not isinstance(self.promotion_gate_result, PromotionGateResult):
            raise ContractSchemaError(
                "ChampionChallengerEvaluation.promotion_gate_result must be PromotionGateResult"
            )
        # rollback_strategy_ref optional non-empty
        if self.rollback_strategy_ref is not None:
            if not isinstance(self.rollback_strategy_ref, str) or not self.rollback_strategy_ref:
                raise ContractSchemaError(
                    "ChampionChallengerEvaluation.rollback_strategy_ref must be non-empty str|None"
                )
        # approval_refs list[str]
        if not isinstance(self.approval_refs, list):
            raise ContractSchemaError(
                "ChampionChallengerEvaluation.approval_refs must be list[str]"
            )
        for idx, ref in enumerate(self.approval_refs):
            if not isinstance(ref, str) or not ref:
                raise ContractSchemaError(
                    f"ChampionChallengerEvaluation.approval_refs[{idx}] must be non-empty str"
                )
        # evaluation_ts
        if not validate_instant(self.evaluation_ts):
            raise ContractSchemaError(
                f"ChampionChallengerEvaluation.evaluation_ts invalid Instant: {self.evaluation_ts!r}"
            )
        # corr / caus
        _validate_ulidish(self.correlation_id, "correlation_id", "ChampionChallengerEvaluation")
        _validate_ulidish(self.causation_id, "causation_id", "ChampionChallengerEvaluation")
        # notes
        if self.notes is not None and not isinstance(self.notes, str):
            raise ContractSchemaError(
                "ChampionChallengerEvaluation.notes must be str|None"
            )
        # WINNER / PROMOTION GATE UYUMLULUĞU invariant
        # Eğer winner=challenger_promoted → gate.passed=True OLMALI
        if self.winner == CCWinnerEnum.CHALLENGER_PROMOTED and not self.promotion_gate_result.passed:
            raise ContractSchemaError(
                "C/C invariant: winner=challenger_promoted iken promotion_gate_result.passed=True OLMALIDIR"
            )
        # Eğer gate.passed=True → winner IN {challenger_promoted, inconclusive_rerun} OLAMAZ champion_keeps ise; yani
        # gate.passed=True ve winner=champion_keeps → YANI RAISE (aynı thresholdda geçtiyse demek ki challenger kazanmalı)
        # Yukarıdaki daha net. İkinci invariant: winner=champion_keeps & gate.passed=True → contradiction?
        # Hayır — gate geçti demek challenger daha iyi demek; champion_keeps OLAMAZ.
        if self.promotion_gate_result.passed and self.winner == CCWinnerEnum.CHAMPION_KEEPS:
            raise ContractSchemaError(
                "C/C invariant: promotion_gate_result.passed=True iken winner='champion_keeps' OLAMAZ"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)
