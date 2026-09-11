from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.contracts import (
    CONTRACT_VERSION,
    CanonicalEventEnvelope,
    ClockRef,
    ContractSchemaError,
    ContractVersion,
    Instant,
    ModelCompatibilityRef,
    ModelLifecycleStatus,
    ModelLifecycleTransition,
    ModelPurposeEnum,
    ModelVersion,
    QualityFlags,
    RunMode,
    SchemaRef,
    SourceType,
    Symbol,
    TrainingDataRange,
    ULID,
    deep_copy,
    format_instant,
    now_instant,
    schema_sha256,
    to_sorted_dict,
    validate_instant,
)
from app.platform.event_bus import InMemoryTypedEventBus

from app.registry.events import build_status_transition_event
from app.registry.exceptions import *
from app.registry.storage import LocalFSRegistryStorage, sha_from_payload


# ---------------------------------------------------------------------------
# EvidenceRef typed (S-MDL-01 level, contract fieldlari degil — registry helper)
# 7 desteklenen tur: 4 required + 3 opsiyonel
# ---------------------------------------------------------------------------


class EvidenceKind(StrEnum):
    HISTORICAL_OOS_EVAL = "historical_oos_eval"
    WALK_FORWARD_RUN = "walk_forward_run"
    PAPER_REPLAY_EVAL = "paper_replay_eval"
    ARTIFACT_PACKAGE = "artifact_package"
    FEATURESET_REF = "featureset_ref"
    HYPERPARAMS_SNAPSHOT = "hyperparams_snapshot"
    COST_INJECTION_CONFIG = "cost_injection_config"


_EVIDENCE_KINDS_REQUIRED: set[str] = {
    EvidenceKind.HISTORICAL_OOS_EVAL.value,
    EvidenceKind.WALK_FORWARD_RUN.value,
    EvidenceKind.PAPER_REPLAY_EVAL.value,
    EvidenceKind.ARTIFACT_PACKAGE.value,
}


def _ulidish(v: Any) -> bool:
    return isinstance(v, str) and len(v) >= 8 and bool(
        re.match(r"^[A-Za-z0-9_\-]{8,}$", v)
    )


def _validate_instant_field(name: str, v: Any) -> None:
    if v is not None and not validate_instant(v):
        raise RegistryError(
            ERR_FIELD_VALIDATION,
            f"Field {name} invalid Instant: {v!r}",
            {"field": name},
        )


@dataclass
class EvidenceRef:
    """Registry-level Evidence reference — 7 typed kind supported.

    Deterministic canonical order (by kind ASC then ref_id ASC).
    APPEND-only default policy — OD-02.
    Duplicate (kind,ref_id) RAISE (ERR_EVIDENCE_REF_DUPLICATE).
    integrity_sha256 provided ise content doğrulaması external.
    """

    kind: EvidenceKind
    ref_id: str
    artifact_uri: str
    source_created_ts: Instant
    correlation_id: str
    integrity_sha256: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceKind):
            try:
                self.kind = EvidenceKind(self.kind)  # type: ignore[assignment]
            except ValueError as exc:
                raise RegistryError(
                    ERR_EVIDENCE_TYPE_INVALID,
                    f"Evidence kind invalid: {self.kind!r}",
                    {"kind": self.kind, "allowed": [e.value for e in EvidenceKind]},
                ) from exc
        if not isinstance(self.ref_id, str) or not self.ref_id:
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                "EvidenceRef.ref_id must be non-empty str",
                {"kind": self.kind.value},
            )
        if not isinstance(self.artifact_uri, str) or not self.artifact_uri:
            raise RegistryError(
                ERR_ARTIFACT_REQUIRED,
                "EvidenceRef.artifact_uri non-empty required",
                {"kind": self.kind.value, "ref_id": self.ref_id},
            )
        if not validate_instant(self.source_created_ts):
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                "EvidenceRef.source_created_ts invalid Instant",
                {"kind": self.kind.value},
            )
        if not _ulidish(self.correlation_id):
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                "EvidenceRef.correlation_id invalid ULID-like (>=8 chars)",
                {"kind": self.kind.value},
            )
        if self.integrity_sha256 is not None and not (
            isinstance(self.integrity_sha256, str)
            and len(self.integrity_sha256) == 64
            and all(c in "0123456789abcdef" for c in self.integrity_sha256)
        ):
            raise RegistryError(
                ERR_EVIDENCE_INTEGRITY,
                "integrity_sha256 must be None or 64-char lowercase hex",
                {"kind": self.kind.value, "ref_id": self.ref_id},
            )
        if not isinstance(self.metadata, dict):
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                "EvidenceRef.metadata must be dict[str,Any]",
                {"kind": self.kind.value},
            )

    def canonical_key(self) -> tuple[str, str]:
        return (self.kind.value, self.ref_id)

    def to_sorted_dict(self) -> dict[str, Any]:
        raw = {
            "artifact_uri": self.artifact_uri,
            "correlation_id": self.correlation_id,
            "integrity_sha256": self.integrity_sha256,
            "kind": self.kind.value,
            "metadata": to_sorted_dict(self.metadata)
            if is_dataclass(self.metadata)
            else dict(sorted(self.metadata.items(), key=lambda kv: kv[0])),
            "ref_id": self.ref_id,
            "source_created_ts": self.source_created_ts,
        }
        return dict(sorted(raw.items(), key=lambda kv: kv[0]))

    def schema_sha256(self) -> str:
        payload = json.dumps(self.to_sorted_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Helpers — immutable field list and ULID seeding
# ---------------------------------------------------------------------------


MV_IMMUTABLE_FIELDS: frozenset[str] = frozenset(
    {
        "model_id",
        "version",
        "purpose",
        "training_data_range",
        "feature_version",
        "compatibility_ref",
        "hyperparams",
        "status",  # CAP-5 — yalnız request_transition ile değişir
        "created_ts",
        "correlation_id",
        "causation_id",
    }
)

MV_APPEND_ONLY_FIELDS: frozenset[str] = frozenset(
    {
        "walk_forward_run_ids",  # metadata icinde, list append-only
        "evidence_refs",  # registry-level, append-only
        "approval_refs",  # ChampionChallenger icindekinden farkli — mv.metadata icinde
    }
)

MV_MUTABLE_FIELDS: frozenset[str] = frozenset(
    {
        "artifact_uri",
        "quality_flags",
        "metadata",
        "promoted_at",
        "retired_at",
    }
) | MV_APPEND_ONLY_FIELDS


MAX_WALK_FORWARD_RUNS: int = 250  # OD-08


def _deterministic_ulid(seed: str, nonce: int = 0) -> str:
    """sha256 seeded ULID benzeri 26+ karakter — 10× idem (AD-20)."""
    if nonce:
        base = f"{seed}|{nonce}"
    else:
        base = seed
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    # 26 karakter ULID görünümü (0123456789ABCDEFGHJKMNPQRSTVWXYZ) Crockford benzeri
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    chars: list[str] = []
    for i in range(26):
        slice_val = digest[i * 2 : i * 2 + 2]
        idx = int(slice_val, 16) % len(alphabet)
        chars.append(alphabet[idx])
    return "".join(chars)


# ---------------------------------------------------------------------------
# List filters (source-backed 4) — status, model_id, created_after, purpose
# ---------------------------------------------------------------------------


@dataclass
class RegistryListFilter:
    status: ModelLifecycleStatus | None = None
    model_id: str | None = None
    created_after: Instant | None = None
    purpose: ModelPurposeEnum | None = None

    def __post_init__(self) -> None:
        if self.status is not None and not isinstance(self.status, ModelLifecycleStatus):
            try:
                self.status = ModelLifecycleStatus(self.status)  # type: ignore[assignment]
            except ValueError as exc:
                raise RegistryError(
                    ERR_FILTER_INVALID,
                    f"Filter.status invalid: {self.status!r}",
                    {"filter": "status"},
                ) from exc
        if self.model_id is not None and (
            not isinstance(self.model_id, str)
            or not self.model_id
            or not re.match(r"^[a-z][a-z0-9_]*$", self.model_id)
        ):
            raise RegistryError(
                ERR_FILTER_INVALID,
                f"Filter.model_id invalid: {self.model_id!r}",
                {"filter": "model_id"},
            )
        if self.created_after is not None and not validate_instant(self.created_after):
            raise RegistryError(
                ERR_FILTER_INVALID,
                f"Filter.created_after invalid: {self.created_after!r}",
                {"filter": "created_after"},
            )
        if self.purpose is not None and not isinstance(self.purpose, ModelPurposeEnum):
            try:
                self.purpose = ModelPurposeEnum(self.purpose)  # type: ignore[assignment]
            except ValueError as exc:
                raise RegistryError(
                    ERR_FILTER_INVALID,
                    f"Filter.purpose invalid: {self.purpose!r}",
                    {"filter": "purpose"},
                ) from exc


def _canonical_sort_key(
    item: tuple[ModelVersion, str, Any],
) -> tuple[str, tuple[int, int, int, str], tuple[int, ...]]:
    mv, _sha, _p = item
    # version: semver tuple (major, minor, patch, pre); baseline 0.0.0-' kalan
    v = mv.version
    numeric = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", v)
    if numeric:
        major, minor, patch, rest = numeric.groups()
        ver_tuple = (int(major), int(minor), int(patch), rest or "")
    else:
        ver_tuple = (0, 0, 0, v)
    # created_ts DESC — epoch negatif
    try:
        created_epoch = int(
            _dt.datetime.fromisoformat(mv.created_ts.replace("Z", "+00:00"))
            .timestamp()
            * 1_000_000
        )
    except Exception:
        created_epoch = 0
    return (mv.model_id.lower(), ver_tuple, (-created_epoch,))


# ---------------------------------------------------------------------------
# Audit log (OD-07 publish exception — DLQ disinda audit log append)
# ---------------------------------------------------------------------------


def _append_audit_log(root: Path, line: str) -> None:
    try:
        logs_dir = root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stamp = now_instant()[:10].replace("-", "")
        path = logs_dir / f"audit-{stamp}.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(
                f"[{now_instant()}] {line.rstrip()}\n",
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ModelRegistry — FOUNDATION (S-MDL-01)
# ---------------------------------------------------------------------------


class ModelRegistry:
    """Model Lifecycle Registry Foundation (S-MDL-01).

    Kapsam:
      • ModelVersion CRUD (Create / Read / Update / List)
      • CAP-5 request_transition FSM enforcement + direct mutation forbid
      • EvidenceRefs APPEND-only + 7 typed kind
      • Approval_refs metadata + Predecessor pointer
      • List/filter (4 tür) + Canonical deterministic sort
      • Event `model_version_status_transitioned.v1` publish
      • Fail-closed, AD-20 Determinism, ADN-10 LocalFS Storage
    """

    def __init__(
        self,
        storage: Optional[LocalFSRegistryStorage] = None,
        event_bus: Optional[InMemoryTypedEventBus] = None,
        root: Optional[Path] = None,
    ) -> None:
        self._storage = storage or LocalFSRegistryStorage(root=root)
        self._bus: Any = event_bus  # None ise publish skip edilir, DLQ no-op
        self._root = self._storage.root
        # evidence_refs: (model_id, version) -> list[EvidenceRef]
        self._evidence: dict[tuple[str, str], list[EvidenceRef]] = {}
        # predecessor: (model_id, version) -> {model_id, version}
        self._predecessor: dict[tuple[str, str], dict[str, str]] = {}
        # od decision log (implementation only, not persisted to storage)
        self._od_decisions: dict[str, str] = {
            "OD-01": "Predecessor cardinality: SINGLE (1 champion -> 1 eski champion); multi-chain OOS S-MDL-04",
            "OD-02": "Evidence / walk_forward / approval_refs = APPEND-ONLY policy",
            "OD-03": "Hard delete: NO DELETE / tombstone ADN-13 Single Writer OOS",
            "OD-04": "Concurrent write: tmp+rename atomic; duplicate -> VERSION_ALREADY_EXISTS; NO LOCK",
            "OD-05": "T4 promote_champion -> approval_refs (mv.metadata['approval_refs']) MIN 1",
            "OD-06": "metrics_on_promotion (mv.metadata) overwrite allowed on UPDATE",
            "OD-07": "Event publish exception: NO retry; bus DLQ + audit log append; storage state commit korunur",
            "OD-08": "walk_forward_run_ids max 250; overflow -> APPEND_ONLY + WARNING log, NO RAISE (reject 251+) RAISE",
            "OD-09": "Duplicate version: HARD fail; force/admin overwrite OOS",
            "OD-10": "oos_range / author_ref (mv.metadata): UPDATE allowed (not in immutable list)",
        }

    # ------------------------------------------------------------------
    # Public: OD decisions (tests için görünür)
    # ------------------------------------------------------------------

    def od_decision(self, code: str) -> str | None:
        return self._od_decisions.get(code)

    def od_decisions_all(self) -> dict[str, str]:
        return dict(self._od_decisions)

    # ------------------------------------------------------------------
    # Public: Evidence helpers (append, list)
    # ------------------------------------------------------------------

    def append_evidence(
        self, model_id: str, version: str, evidence: EvidenceRef
    ) -> list[EvidenceRef]:
        """Append-only (OD-02). Duplicate (kind, ref_id) -> RegistryError."""
        if not isinstance(evidence, EvidenceRef):
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                "append_evidence requires EvidenceRef instance",
            )
        key = (model_id.lower(), version)
        existing = self._evidence.setdefault(key, [])
        dup_key = evidence.canonical_key()
        for e in existing:
            if e.canonical_key() == dup_key:
                raise RegistryError(
                    ERR_EVIDENCE_REF_DUPLICATE,
                    f"Evidence duplicate (kind,ref_id): {dup_key}",
                    {
                        "model_id": model_id,
                        "version": version,
                        "kind": evidence.kind.value,
                        "ref_id": evidence.ref_id,
                    },
                )
        existing.append(evidence)
        # Deterministic canonical order
        self._evidence[key] = sorted(
            existing,
            key=lambda e: (e.kind.value, e.ref_id),
        )
        return list(self._evidence[key])

    def list_evidence(self, model_id: str, version: str) -> list[EvidenceRef]:
        key = (model_id.lower(), version)
        return list(self._evidence.get(key, []))

    # ------------------------------------------------------------------
    # Public: predecessor pointer (S-MDL-01 foundation only)
    # ------------------------------------------------------------------

    def set_predecessor(
        self, model_id: str, version: str, prev_model_id: str, prev_version: str
    ) -> None:
        if not re.match(r"^[a-z][a-z0-9_]*$", prev_model_id):
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                "Predecessor model_id invalid (lowercase snake case required)",
                {"prev_model_id": prev_model_id},
            )
        if not isinstance(prev_version, str) or not prev_version:
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                "Predecessor version required",
            )
        key = (model_id.lower(), version)
        self._predecessor[key] = {"model_id": prev_model_id, "version": prev_version}

    def get_predecessor(
        self, model_id: str, version: str
    ) -> dict[str, str] | None:
        key = (model_id.lower(), version)
        return self._predecessor.get(key)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create(self, mv: ModelVersion) -> tuple[ModelVersion, str]:
        if not isinstance(mv, ModelVersion):
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                "create() requires ModelVersion dataclass instance",
                {"got_type": type(mv).__name__},
            )
        # 1) CREATE sonrası status field doğrudan değiştirilemeyecek — storage sayesinde
        #    koruma altına alınıyor (write sonrası read ile dönen kopya).
        sha = self._storage.write_model_version(mv, check_duplicate=True)
        # walk_forward_run_ids 250 kontrol (OD-08)
        wf_ids = mv.metadata.get("walk_forward_run_ids")
        if isinstance(wf_ids, list) and len(wf_ids) > MAX_WALK_FORWARD_RUNS:
            # Create sonrası 251+ varsa — reject et, dosyayı yazdık ama RAISE
            # Strict fail-closed AD-19: 251+ create RAISE
            raise RegistryError(
                ERR_WALK_FORWARD_MAX,
                (
                    f"walk_forward_run_ids create-time overflow {len(wf_ids)}"
                    f" > MAX={MAX_WALK_FORWARD_RUNS}"
                ),
                {"model_id": mv.model_id, "version": mv.version},
            )
        return mv, sha

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get(
        self, model_id: str, version: str
    ) -> tuple[ModelVersion, str]:
        """Read ModelVersion + sha. Fail-closed on missing/corrupt."""
        mv, sha = self._storage.read_model_version(model_id, version)
        # Deep copy — dolaylı döndürerek dışarıdaki mutationların storage'i
        # etkilemesini engelliyoruz (CAP-5 direct mutation engeli takviye).
        return deep_copy(mv), sha

    # ------------------------------------------------------------------
    # UPDATE — allowed mutable, immutable RAISE, append-only append policy
    # ------------------------------------------------------------------

    def update(
        self,
        model_id: str,
        version: str,
        patch: dict[str, Any],
    ) -> tuple[ModelVersion, str]:
        cur_mv, cur_sha = self._storage.read_model_version(model_id, version)

        patch_keys = set(patch.keys())
        if not patch_keys:
            raise RegistryError(
                ERR_FIELD_MISSING,
                "update() requires non-empty patch dict",
            )

        # 1) CAP-5 guard: status doğrudan patch ile SET -> HARD RAISE
        if "status" in patch_keys:
            raise RegistryError(
                ERR_CAP5_DIRECT_MUTATION,
                (
                    "ModelVersion.status cannot be mutated directly. "
                    "Use request_transition(...) instead (CAP-5 AD-14/23)."
                ),
                {"patch_keys": sorted(patch_keys)},
            )

        # 2) Immutable set — hyperparams/compat/...
        immutable_hit = patch_keys & MV_IMMUTABLE_FIELDS
        if immutable_hit:
            raise RegistryError(
                ERR_FIELD_IMMUTABLE,
                f"Cannot update immutable ModelVersion fields: {sorted(immutable_hit)}",
                {"immutable_fields": sorted(immutable_hit)},
            )

        # 3) Mutable olmayan / bilinmeyen key -> REJECT (fail closed AD-19)
        unknown = patch_keys - MV_MUTABLE_FIELDS
        if unknown:
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                f"Unknown/unpatchable keys: {sorted(unknown)}",
                {"mutable_fields": sorted(MV_MUTABLE_FIELDS)},
            )

        # 4) Append-only checks (OD-02)
        #    walk_forward_run_ids: yeni listedeki eski list olmayan entryler EKLENMELİ,
        #    ama listeden silmeye çalışılırsa RAISE
        wf_cur: list[Any] = list(cur_mv.metadata.get("walk_forward_run_ids") or [])
        if "walk_forward_run_ids" in patch:
            new_wf = patch["walk_forward_run_ids"]
            if not isinstance(new_wf, list):
                raise RegistryError(
                    ERR_APPEND_ONLY,
                    "walk_forward_run_ids patch must be list[str]",
                    {"model_id": model_id, "version": version},
                )
            # eski subset olmalı: her eski item yenide olmalı
            missing_old = [x for x in wf_cur if x not in new_wf]
            if missing_old:
                raise RegistryError(
                    ERR_APPEND_ONLY,
                    (
                        "walk_forward_run_ids is APPEND-ONLY (OD-02); "
                        "cannot remove existing items. Missing after patch: "
                        f"{missing_old[:5]}"
                    ),
                    {"model_id": model_id, "version": version},
                )
            if len(new_wf) > MAX_WALK_FORWARD_RUNS:  # OD-08
                raise RegistryError(
                    ERR_WALK_FORWARD_MAX,
                    (
                        f"walk_forward_run_ids overflow {len(new_wf)} > "
                        f"MAX={MAX_WALK_FORWARD_RUNS}"
                    ),
                    {"model_id": model_id, "version": version},
                )

        # approval_refs append-only (mv.metadata icindeki list)
        appr_cur: list[Any] = list(cur_mv.metadata.get("approval_refs") or [])
        if "approval_refs" in patch:
            new_appr = patch["approval_refs"]
            if not isinstance(new_appr, list):
                raise RegistryError(
                    ERR_APPEND_ONLY,
                    "approval_refs patch must be list[str]",
                )
            missing_old = [x for x in appr_cur if x not in new_appr]
            if missing_old:
                raise RegistryError(
                    ERR_APPEND_ONLY,
                    (
                        "approval_refs is APPEND-ONLY; cannot remove: "
                        f"{missing_old[:5]}"
                    ),
                )

        # evidence_refs append-only (registry-level liste üstünden)
        if "evidence_refs" in patch:
            # patch ile setleme DENEME -> raise (kullanıcı append_evidence kullanmalı)
            raise RegistryError(
                ERR_APPEND_ONLY,
                (
                    "evidence_refs is APPEND-ONLY; DO NOT patch evidence_refs. "
                    "Use registry.append_evidence(...)."
                ),
            )

        # 5) Build new ModelVersion — promoted_at / retired_at / artifact_uri /
        #    quality_flags / metadata patch doğrula
        new_metadata: dict[str, Any] = deep_copy(cur_mv.metadata)
        for k, v in patch.items():
            if k in MV_APPEND_ONLY_FIELDS and k in ("walk_forward_run_ids",):
                new_metadata["walk_forward_run_ids"] = list(patch["walk_forward_run_ids"])
            elif k == "approval_refs":
                new_metadata["approval_refs"] = list(patch["approval_refs"])
            elif k == "metadata":
                if not isinstance(v, dict):
                    raise RegistryError(
                        ERR_FIELD_VALIDATION,
                        "metadata patch value must be dict",
                    )
                # nested doğrudan overwrite etme — update keys sadece (ancak DELETE olmamalı)
                for mk, mv2 in v.items():
                    new_metadata[mk] = mv2
            else:
                # promoted_at / retired_at / artifact_uri / quality_flags -> doğrudan
                setattr(cur_mv, k, v)  # type: ignore[misc]

        # Final promoted_at/retired_at validation (Instant veya None)
        _validate_instant_field("promoted_at", cur_mv.promoted_at)
        _validate_instant_field("retired_at", cur_mv.retired_at)

        try:
            new_mv = replace(  # immutable kopya oluştur
                cur_mv,
                metadata=new_metadata,
            )
        except Exception as exc:
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                f"Update replace() failed: {exc}",
                {"exc_type": type(exc).__name__},
            ) from exc

        # 6) Write (overwrite allowed, audit files preserved)
        new_sha = self._storage.write_model_version(
            new_mv, check_duplicate=False
        )
        return deep_copy(new_mv), new_sha

    # ------------------------------------------------------------------
    # LIST + FILTERS + deterministic canonical sort
    # ------------------------------------------------------------------

    def list(
        self,
        filters: RegistryListFilter | None = None,
    ) -> list[tuple[ModelVersion, str]]:
        raw = self._storage.list_model_versions()
        filt = filters or RegistryListFilter()

        def _pass(mv: ModelVersion) -> bool:
            if filt.status is not None and mv.status != filt.status:
                return False
            if filt.model_id is not None and mv.model_id != filt.model_id:
                return False
            if filt.created_after is not None:
                if mv.created_ts < filt.created_after:
                    return False
            if filt.purpose is not None and mv.purpose != filt.purpose:
                return False
            return True

        filtered = [item for item in raw if _pass(item[0])]
        # Deterministic canonical order (AD-20)
        sorted_items = sorted(filtered, key=_canonical_sort_key)
        return [(deep_copy(mv), sha) for (mv, sha, _p) in sorted_items]

    # ------------------------------------------------------------------
    # REQUEST TRANSITION (CAP-5 + FSM + Event publish)
    # ------------------------------------------------------------------

    def request_transition(
        self,
        *,
        model_id: str,
        version: str,
        to_status: ModelLifecycleStatus | str,
        transition_command: str,
        evidence_ref_ids: list[str] | None = None,
        requested_by: str = "system",
        approved_by: str = "system",
        transition_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        requested_ts: Instant | None = None,
        metadata: dict[str, Any] | None = None,
        envelope_event_id: str | None = None,
    ) -> tuple[ModelVersion, str, ModelLifecycleTransition, Any | None]:
        """CAP-5 AD-14/23: SADECE bu metot ile status değişir.

        Döner: (new_mv, new_sha, tx, published_event_envelope or None)

        Fail-closed (geçersiz herhangi şey -> RAISE; hiçbir şey yazılmaz).
        Invalid transition -> EVENT PUBLISH YOK (S-CON-02C L262-264 + spec).
        """
        if not transition_command or not isinstance(transition_command, str):
            raise RegistryError(
                ERR_CAP5_COMMAND_EMPTY,
                "transition_command non-empty required (CAP-5)",
            )
        if not isinstance(requested_by, str) or not requested_by:
            raise RegistryError(ERR_FIELD_MISSING, "requested_by required")
        if not isinstance(approved_by, str) or not approved_by:
            raise RegistryError(ERR_FIELD_MISSING, "approved_by required")

        # Normalize to_status
        try:
            to_enum = (
                to_status
                if isinstance(to_status, ModelLifecycleStatus)
                else ModelLifecycleStatus(to_status)
            )
        except ValueError as exc:
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                f"to_status invalid: {to_status!r}",
                {"allowed": [s.value for s in ModelLifecycleStatus]},
            ) from exc

        # 1) Read Mevcut MV
        try:
            cur_mv, cur_sha = self._storage.read_model_version(model_id, version)
        except StorageError as exc:
            if exc.reason_code == "MODEL_VERSION_NOT_FOUND":
                raise RegistryError(
                    ERR_UPDATE_NOT_FOUND,
                    f"Transition target not found: {model_id}@{version}",
                ) from exc
            raise

        from_enum = cur_mv.status

        # 2) T4 promote_champion için OD-05 min 1 onay zorunlu
        if to_enum == ModelLifecycleStatus.CHAMPION:
            appr_list = cur_mv.metadata.get("approval_refs")
            if not isinstance(appr_list, list) or len(appr_list) < 1:
                raise RegistryError(
                    ERR_PROMOTE_MIN_APPROVAL,
                    (
                        "Promote to champion (T4) requires at least 1 entry in "
                        f"mv.metadata['approval_refs']. Found: {appr_list!r}"
                    ),
                    {
                        "model_id": model_id,
                        "version": version,
                        "approval_refs": appr_list,
                    },
                )

        # 3) Deterministic ULIDs (AD-20 idem)
        seed_base = f"{cur_mv.model_id}|{cur_mv.version}|{from_enum.value}|{to_enum.value}|{transition_command}"
        tx_seed = f"tx|{seed_base}|{cur_sha}"
        corr = correlation_id or cur_mv.correlation_id
        caus = causation_id or _deterministic_ulid(f"caus|{tx_seed}", 1)
        tx_id = transition_id or _deterministic_ulid(tx_seed, 2)
        rts = requested_ts or now_instant()
        meta = dict(metadata or {})
        er_list = list(evidence_ref_ids or [])
        for idx, e in enumerate(er_list):
            if not isinstance(e, str) or not e:
                raise RegistryError(
                    ERR_FIELD_VALIDATION,
                    f"evidence_ref_ids[{idx}] must be non-empty str",
                )

        # 4) ModelLifecycleTransition construct (CON-02C §4.2 HARD VALIDATE)
        #    Geçersiz FSM edge ise ContractSchemaError -> catch, RegistryError çevir
        try:
            tx = ModelLifecycleTransition(
                transition_id=tx_id,
                model_id=cur_mv.model_id,
                model_version=cur_mv.version,
                from_status=from_enum,
                to_status=to_enum,
                reason=transition_command,
                evidence_refs=er_list,
                requested_by=requested_by,
                approved_by=approved_by,
                requested_ts=rts,
                correlation_id=ULID(corr),
                causation_id=ULID(caus),
                metadata=meta,
            )
        except ContractSchemaError as exc:
            msg = str(exc)
            if "from_status == to_status" in msg or "no-op" in msg:
                raise RegistryError(
                    ERR_CAP5_FSM_NOOP,
                    msg,
                    {
                        "from": from_enum.value,
                        "to": to_enum.value,
                        "model_id": model_id,
                        "version": version,
                    },
                ) from exc
            raise RegistryError(
                ERR_CAP5_FSM_FORBIDDEN,
                msg,
                {
                    "from": from_enum.value,
                    "to": to_enum.value,
                    "model_id": model_id,
                    "version": version,
                },
            ) from exc

        # 5) Predecessor (T4 promote_champion zamanı predecessor = eski champion
        #    user dışarıdan set_predecessor çağırmalı — S-MDL-01 set etmiyoruz,
        #    sadece pointer'ı koruyoruz.)
        # promoted_at / retired_at timestamp set et:
        patch_meta: dict[str, Any] = {}
        patch_attrs: dict[str, Any] = {}
        if to_enum == ModelLifecycleStatus.CHAMPION:
            patch_attrs["promoted_at"] = rts
        if to_enum == ModelLifecycleStatus.RETIRED:
            patch_attrs["retired_at"] = rts

        # 6) Build new MV with UPDATED status (via replace, CAP-5 writer tek yer)
        try:
            new_mv = replace(
                cur_mv,
                status=to_enum,
                metadata={**cur_mv.metadata, **patch_meta},
                **patch_attrs,
            )
        except Exception as exc:
            raise RegistryError(
                ERR_FIELD_VALIDATION,
                f"Transition replace failed: {exc}",
                {"exc_type": type(exc).__name__},
            ) from exc

        # 7) Yaz storage sırası: ÖNCE mv (overwrite allowed, check_dup=False), SONRA transition
        new_sha = self._storage.write_model_version(
            new_mv, check_duplicate=False
        )
        self._storage.write_transition(tx)

        # 8) Event publish SADECE valid transition SONRASI (storage write OK)
        published_envelope: Any = None
        if self._bus is not None:
            try:
                eid = envelope_event_id or _deterministic_ulid(
                    f"evt|{tx_id}", 3
                )
                envelope = build_status_transition_event(
                    envelope_event_id=eid,
                    mv=new_mv,
                    tx=tx,
                    previous_mv_sha=cur_sha,
                    new_mv_sha=new_sha,
                    symbol=None,
                )
                # DLQ mekanizması bus._dispatch_typed_subscribers içinde çalışıyor (AD-19)
                self._bus.publish(envelope)  # type: ignore[attr-defined]
                published_envelope = envelope
            except Exception as exc:
                # OD-07: bus exception -> NO retry; audit log + state korunur
                _append_audit_log(
                    self._root,
                    (
                        f"EVENT_PUBLISH_FAIL model={model_id}@"
                        f"{version} tx_id={tx_id} exc="
                        f"{type(exc).__name__}:{exc}"
                    ),
                )
                # state SAKLANIR — rollback YOK (transition + new_mv dosyada var)
                published_envelope = None

        return deep_copy(new_mv), new_sha, tx, published_envelope

    # ------------------------------------------------------------------
    # Public: transition history (audit için)
    # ------------------------------------------------------------------

    def transition_history(
        self, model_id: str, version: str
    ) -> list[ModelLifecycleTransition]:
        """Deterministic order: written order (st_mtime ASC by storage)."""
        return list(self._storage.read_transitions(model_id, version))
