"""CompareEngine orchestration (CAP-1..CAP-12).

Responsibilities:
  - Load champion/challenger from registry (READ-ONLY — NO create/update/append/transition)
  - Resolve 3 required evidence kinds: HISTORICAL_OOS_EVAL + WALK_FORWARD_RUN + PAPER_REPLAY_EVAL (optional ARTIFACT_PACKAGE)
  - Read/parse artifact JSON via artifact_loader callable (default: file: local path)
  - Build typed ModelEvaluation per side (11 required keys strict)
  - Run 6 comparability invariants → raise ERR_INCOMPARABLE_* on mismatch (fail-closed)
  - Compute 11-key + optional extras MetricDelta list (direction-based)
  - Build CCE payload (ChampionChallengerEvaluationPayload)
  - Deterministic canonical output/schema_sha256 10x identical
  - NO promotion_gate_result.passed (S-MDL-03 boundary)
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from app.contracts.model import (
    CCWinnerEnum,
    DatasetKindEnum,
    ModelEvaluation,
    ModelLifecycleStatus,
    ModelRef,
    ModelVersion,
    _REQUIRED_METRIC_KEYS,
)
from app.registry.registry import (
    EvidenceKind,
    EvidenceRef,
    ModelRegistry,
)

from app.evaluation.comparability import (
    ComparabilityResult,
    check_comparability,
)
from app.evaluation.contract_payload import (
    ChampionChallengerEvaluationPayload,
    build_cce_payload,
)
from app.evaluation.delta import (
    CRITICAL_DELTA_KEYS_ORDERED,
    MetricDelta,
    compare_metric_delta,
    metric_direction_table,
    sorted_metric_keys,
    validate_metrics_strict,
)
from app.evaluation.exceptions import (
    CompareValidationError,
    ERR_ARTIFACT_CORRUPT,
    ERR_ARTIFACT_NOT_FOUND,
    ERR_EMPTY_ARTIFACT_URI,
    ERR_EMPTY_CHALLENGER_MODEL,
    ERR_EMPTY_CHAMPION_MODEL,
    ERR_INCOMPATIBLE_STATUS_TRANSITION,
    ERR_INTEGRITY_SHA_MISMATCH,
    ERR_METRIC_TYPE_MISMATCH,
    ERR_MODEL_NOT_FOUND,
    ERR_NOT_CHALLENGER_STATUS,
    ERR_NOT_CHAMPION_STATUS,
    ERR_SAME_MODEL_SAME_VERSION,
    ERR_VERSION_MISMATCH,
)


REQUIRED_EVIDENCE_KINDS: tuple[EvidenceKind, ...] = (
    EvidenceKind.HISTORICAL_OOS_EVAL,
    EvidenceKind.WALK_FORWARD_RUN,
    EvidenceKind.PAPER_REPLAY_EVAL,
)

_ULIDISH_RE = re.compile(r"^[A-Za-z0-9_\-]{8,}$")


def _ulidish(v: str) -> bool:
    return isinstance(v, str) and bool(_ULIDISH_RE.match(v))


@dataclass
class CompareResult:
    """Result object returned by CompareEngine.compare().

    Typed, canonical-sorted, schema_sha256 deterministic.
    """

    champion_model: ModelVersion
    challenger_model: ModelVersion
    champion_eval: ModelEvaluation
    challenger_eval: ModelEvaluation
    comparability_result: ComparabilityResult
    metric_deltas: list[MetricDelta]
    payload: ChampionChallengerEvaluationPayload
    extra: dict[str, Any] = field(default_factory=dict)

    def schema_sha256(self) -> str:
        return self.payload.schema_sha256()


def _load_artifact_bytes(uri: str) -> bytes:
    """Fail-closed artifact bytes loader. Empty URI / missing file → deterministic ERR."""
    if not isinstance(uri, str) or not uri:
        raise CompareValidationError(ERR_EMPTY_ARTIFACT_URI, "empty artifact_uri", {"uri": uri})
    path_str = uri
    if uri.startswith("file://"):
        path_str = uri[len("file://"):]
    path = Path(path_str)
    if not path.exists() or not path.is_file():
        raise CompareValidationError(ERR_ARTIFACT_NOT_FOUND, "artifact file not found", {"uri": uri, "resolved_path": str(path.resolve())})
    try:
        data = path.read_bytes()
    except Exception as exc:
        raise CompareValidationError(ERR_ARTIFACT_NOT_FOUND, f"artifact read failed: {exc!r}", {"uri": uri}) from exc
    if len(data) == 0:
        raise CompareValidationError(ERR_ARTIFACT_CORRUPT, "artifact zero bytes", {"uri": uri})
    return data


def _parse_artifact_bytes(data: bytes, uri: str) -> dict[str, Any]:
    """Parse bytes -> JSON dict. Fail closed non-dict / corrupt JSON."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CompareValidationError(ERR_ARTIFACT_CORRUPT, f"artifact corrupt JSON: {exc!r}", {"uri": uri}) from exc
    if not isinstance(payload, dict):
        raise CompareValidationError(ERR_ARTIFACT_CORRUPT, "artifact JSON root must be object/dict", {"type": type(payload).__name__})
    return payload


def _default_artifact_loader(uri: str) -> tuple[bytes, dict[str, Any]]:
    """file:// URIs + local absolute/relative path support.

    Returns (bytes, parsed_json_dict). Fail-closed on missing/unreadable/corrupt.
    """
    data = _load_artifact_bytes(uri)
    payload = _parse_artifact_bytes(data, uri)
    return data, payload


def _compute_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_evidence_dict(ev: EvidenceRef) -> dict[str, Any]:
    return {
        "artifact_uri": ev.artifact_uri,
        "correlation_id": ev.correlation_id,
        "integrity_sha256": ev.integrity_sha256,
        "kind": ev.kind.value,
        "metadata": {k: ev.metadata[k] for k in sorted(ev.metadata.keys())},
        "ref_id": ev.ref_id,
        "source_created_ts": ev.source_created_ts,
    }


@dataclass
class CompareEngine:
    """Main orchestrator. READ-ONLY registry access; no write methods."""

    registry: ModelRegistry
    artifact_loader: Callable[[str], tuple[bytes, dict[str, Any]]] = field(default_factory=lambda: _default_artifact_loader)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compare(
        self,
        champion_model_id: str,
        champion_version: str,
        challenger_model_id: str,
        challenger_version: str,
        *,
        evaluation_ts_override: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        thresholds_config_version_override: str | None = None,
    ) -> CompareResult:
        """Main: CAP-1..CAP-12 pipeline.

        Steps:
          1. identify + load + validate status (CAP-1)
          2. evidence kinds (3 required) + integrity SHA (CAP-6)
          3. artifact JSON load + parse
          4. build ModelEvaluation (11-key strict) — CAP-3
          5. comparability invariants 6 (CAP-2)
          6. per-metric deltas 11 required + extras (CAP-4/CAP-8/CAP-7)
          7. winner hint (non-binding CAP-9)
          8. build payload (CAP-12)
          9. canonical order + sha (CAP-5 / CAP-11 determinism)
        """
        correlation = correlation_id or f"corr-{champion_model_id}-{challenger_model_id}-{champion_version}-{challenger_version}"
        if len(correlation) < 8:
            correlation = "CORR" + correlation.ljust(10, "_")
        causation = causation_id or f"caus-{correlation}"
        if len(causation) < 8:
            causation = "CAUS" + causation.ljust(10, "_")
        # 1. identity & load: fast fails FIRST (empty input before any registry call)
        if not champion_model_id or not champion_version:
            raise CompareValidationError(ERR_EMPTY_CHAMPION_MODEL, "empty champion model_id or version", {"champion_model_id": champion_model_id, "champion_version": champion_version})
        if not challenger_model_id or not challenger_version:
            raise CompareValidationError(ERR_EMPTY_CHALLENGER_MODEL, "empty challenger model_id or version", {"challenger_model_id": challenger_model_id, "challenger_version": challenger_version})
        if (
            champion_model_id.lower() == challenger_model_id.lower()
            and champion_version == challenger_version
        ):
            raise CompareValidationError(
                ERR_SAME_MODEL_SAME_VERSION,
                "champion and challenger must be different (model_id+version same)",
                {"model_id": champion_model_id, "version": champion_version},
            )
        ch_mv, ch_sha = self._load_model(champion_model_id, champion_version, expected_status=ModelLifecycleStatus.CHAMPION, status_err=ERR_NOT_CHAMPION_STATUS)
        ct_mv, ct_sha = self._load_model(challenger_model_id, challenger_version, expected_status=None, status_err=ERR_NOT_CHALLENGER_STATUS)
        if ct_mv.status not in {ModelLifecycleStatus.CHALLENGER, ModelLifecycleStatus.TESTED}:
            raise CompareValidationError(
                ERR_NOT_CHALLENGER_STATUS,
                "challenger status must be CHALLENGER or TESTED",
                {"model_id": ct_mv.model_id, "version": ct_mv.version, "status": ct_mv.status.value},
            )
        # predecessor ref (champion side)
        predecessor = self.registry.get_predecessor(champion_model_id, champion_version)
        predecessor_ref: str | None = None
        if predecessor:
            predecessor_ref = f"{predecessor['model_id']}@{predecessor['version']}"
        # 2. evidence (3 required kinds)
        ch_ev = self._load_required_evidences(ch_mv.model_id, ch_mv.version)
        ct_ev = self._load_required_evidences(ct_mv.model_id, ct_mv.version)
        # 3. load primary artifact (HISTORICAL_OOS_EVAL) + integrity
        # IMPORTANT: SHA check MUST happen BEFORE JSON parse so a mismatched SHA + corrupt JSON
        # still fires INTEGRITY_SHA_MISMATCH rather than ARTIFACT_CORRUPT.
        ch_hist_ref = ch_ev[EvidenceKind.HISTORICAL_OOS_EVAL]
        ct_hist_ref = ct_ev[EvidenceKind.HISTORICAL_OOS_EVAL]
        # Default loader path: split load / check-integrity / parse explicitly
        _default_loader = (
            self.artifact_loader is _default_artifact_loader
            or (getattr(self.artifact_loader, "__name__", "") == "_default_artifact_loader")
        )
        if _default_loader:
            ch_bytes = _load_artifact_bytes(ch_hist_ref.artifact_uri)
            ct_bytes = _load_artifact_bytes(ct_hist_ref.artifact_uri)
            # Integrity SHA check BEFORE parse
            if ch_hist_ref.integrity_sha256 and ch_hist_ref.integrity_sha256 != _compute_sha256_hex(ch_bytes):
                raise CompareValidationError(
                    ERR_INTEGRITY_SHA_MISMATCH,
                    "champion historical_oos_eval integrity_sha256 mismatch",
                    {"kind": EvidenceKind.HISTORICAL_OOS_EVAL.value, "expected": ch_hist_ref.integrity_sha256, "actual": _compute_sha256_hex(ch_bytes)},
                )
            if ct_hist_ref.integrity_sha256 and ct_hist_ref.integrity_sha256 != _compute_sha256_hex(ct_bytes):
                raise CompareValidationError(
                    ERR_INTEGRITY_SHA_MISMATCH,
                    "challenger historical_oos_eval integrity_sha256 mismatch",
                    {"kind": EvidenceKind.HISTORICAL_OOS_EVAL.value, "expected": ct_hist_ref.integrity_sha256, "actual": _compute_sha256_hex(ct_bytes)},
                )
            ch_artifact = _parse_artifact_bytes(ch_bytes, ch_hist_ref.artifact_uri)
            ct_artifact = _parse_artifact_bytes(ct_bytes, ct_hist_ref.artifact_uri)
        else:
            ch_bytes, ch_artifact = self.artifact_loader(ch_hist_ref.artifact_uri)
            ct_bytes, ct_artifact = self.artifact_loader(ct_hist_ref.artifact_uri)
            if ch_hist_ref.integrity_sha256 and ch_hist_ref.integrity_sha256 != _compute_sha256_hex(ch_bytes):
                raise CompareValidationError(ERR_INTEGRITY_SHA_MISMATCH, "champion integrity mismatch", {"expected": ch_hist_ref.integrity_sha256, "actual": _compute_sha256_hex(ch_bytes)})
            if ct_hist_ref.integrity_sha256 and ct_hist_ref.integrity_sha256 != _compute_sha256_hex(ct_bytes):
                raise CompareValidationError(ERR_INTEGRITY_SHA_MISMATCH, "challenger integrity mismatch", {"expected": ct_hist_ref.integrity_sha256, "actual": _compute_sha256_hex(ct_bytes)})
        # additional evidence integrity check (walk forward & paper replay if set)
        for side_name, ev_map in (("champion", ch_ev), ("challenger", ct_ev)):
            for kind, ref in ev_map.items():
                if kind == EvidenceKind.HISTORICAL_OOS_EVAL:
                    continue
                if ref.integrity_sha256 is None:
                    continue
                if _default_loader:
                    ref_bytes = _load_artifact_bytes(ref.artifact_uri)
                    actual = _compute_sha256_hex(ref_bytes)
                else:
                    ref_bytes, _payload = self.artifact_loader(ref.artifact_uri)
                    actual = _compute_sha256_hex(ref_bytes)
                if actual != ref.integrity_sha256:
                    raise CompareValidationError(
                        ERR_INTEGRITY_SHA_MISMATCH,
                        f"{side_name} evidence integrity_sha256 mismatch",
                        {"side": side_name, "kind": kind.value, "ref_id": ref.ref_id, "expected": ref.integrity_sha256, "actual": actual},
                    )
        # 4. build typed ModelEvaluation
        ch_eval = self._build_model_evaluation(
            mv=ch_mv, artifact=ch_artifact, eval_ref=ch_hist_ref, side="champion",
            evaluation_ts_override=evaluation_ts_override, correlation=correlation, causation=causation,
            thresholds_config_version_override=thresholds_config_version_override,
        )
        ct_eval = self._build_model_evaluation(
            mv=ct_mv, artifact=ct_artifact, eval_ref=ct_hist_ref, side="challenger",
            evaluation_ts_override=evaluation_ts_override, correlation=correlation, causation=causation,
            thresholds_config_version_override=thresholds_config_version_override,
        )
        # cross-check artifact inner model_id/version match
        for side_name, eval_obj, artifact in (("champion", ch_eval, ch_artifact), ("challenger", ct_eval, ct_artifact)):
            a_mid = artifact.get("model_id")
            a_ver = artifact.get("model_version")
            if isinstance(a_mid, str) and a_mid.lower() != eval_obj.model_id.lower():
                raise CompareValidationError(
                    ERR_INCOMPATIBLE_STATUS_TRANSITION,
                    f"{side_name} artifact model_id mismatch registry model",
                    {"side": side_name, "artifact_model_id": a_mid, "registry_model_id": eval_obj.model_id},
                )
            if isinstance(a_ver, str) and a_ver != eval_obj.model_version:
                raise CompareValidationError(
                    ERR_VERSION_MISMATCH,
                    f"{side_name} artifact model_version mismatch registry",
                    {"side": side_name, "artifact_version": a_ver, "registry_version": eval_obj.model_version},
                )
        # artifact summaries (fold_count / regime_matrix / cost_config_version)
        ch_summary = self._build_artifact_summary(ch_artifact)
        ct_summary = self._build_artifact_summary(ct_artifact)
        # 5. comparability invariants
        comp_result = check_comparability(
            ch_mv, ct_mv, ch_eval, ct_eval,
            list(ch_ev.values()), list(ct_ev.values()),
            ch_summary, ct_summary,
        )
        # 6. metric deltas (11 required + extras allowed: stability, fees_per_trade, aggregate_*, fold_*, regime_* per metric groupings)
        metric_deltas: list[MetricDelta] = []
        all_metric_keys = sorted_metric_keys({**ch_eval.metrics, **ct_eval.metrics})
        # 11 required
        for k in _REQUIRED_METRIC_KEYS:
            metric_deltas.append(compare_metric_delta(k, ch_eval.metrics, ct_eval.metrics))
        # optional extras in both
        for k in all_metric_keys:
            if k in _REQUIRED_METRIC_KEYS:
                continue
            if k not in ch_eval.metrics or k not in ct_eval.metrics:
                # absent on either side → SKIP (not required; stability optional)
                continue
            # extras must be stable / numeric known keys
            if k not in metric_direction_table and not k.startswith(("aggregate_", "fold_", "regime_", "per_", "group_")):
                continue  # unknown extras → silently skip (conservative: only direction-table / prefixes allowed)
            try:
                metric_deltas.append(compare_metric_delta(k, ch_eval.metrics, ct_eval.metrics))
            except CompareValidationError:
                # optional extras: direction+type unknown could fail; skip
                continue
        # fold-level deltas: per-fold metrics if both sides have per_fold_metrics[N] list
        fold_deltas = self._build_fold_deltas(ch_summary, ct_summary)
        regime_deltas = self._build_regime_deltas(ch_summary, ct_summary)
        metric_deltas.extend(fold_deltas)
        metric_deltas.extend(regime_deltas)
        # 8. build payload
        champion_ref = ModelRef(ch_mv.model_id, ch_mv.version)
        challenger_ref = ModelRef(ct_mv.model_id, ct_mv.version)
        # canonical evidence list (kind ASC ref_id ASC)
        evidence_combined: list[dict[str, Any]] = []
        for ev in sorted(list(ch_ev.values()), key=lambda e: (e.kind.value, e.ref_id)):
            evidence_combined.append({"side": "champion", **_canonical_evidence_dict(ev)})
        for ev in sorted(list(ct_ev.values()), key=lambda e: (e.kind.value, e.ref_id)):
            evidence_combined.append({"side": "challenger", **_canonical_evidence_dict(ev)})
        evaluation_period_days = int(ch_eval.evaluation_window_days) if int(ch_eval.evaluation_window_days) == int(ct_eval.evaluation_window_days) else min(int(ch_eval.evaluation_window_days), int(ct_eval.evaluation_window_days))
        if evaluation_period_days < 0:
            evaluation_period_days = 0
        payload = build_cce_payload(
            champion_ref=champion_ref,
            challenger_ref=challenger_ref,
            comparable=True,
            metric_deltas=metric_deltas,
            evaluation_period_days=evaluation_period_days,
            rollback_strategy_ref=predecessor_ref,
            evidence_refs=evidence_combined,
            challenger_metrics=ct_eval.metrics,
            champion_metrics=ch_eval.metrics,
            metadata={
                "champion_registry_sha": ch_sha,
                "challenger_registry_sha": ct_sha,
                "champion_dataset_kind": ch_eval.dataset_kind.value,
                "challenger_dataset_kind": ct_eval.dataset_kind.value,
                "champion_eval_id": ch_eval.eval_id,
                "challenger_eval_id": ct_eval.eval_id,
                "correlation_id": correlation,
                "causation_id": causation,
                "critical_delta_keys": list(CRITICAL_DELTA_KEYS_ORDERED),
                "evaluation_ts": ch_eval.evaluation_ts,
                "thresholds_config_version": ch_eval.thresholds_config_version or ct_eval.thresholds_config_version or "1.0.0",
                "cost_config_version": "1.0.0",
                "champion_model_id": ch_mv.model_id,
                "challenger_model_id": ct_mv.model_id,
                "champion_version": ch_mv.version,
                "challenger_version": ct_mv.version,
            },
        )
        extra = {
            "champion_summary": ch_summary,
            "challenger_summary": ct_summary,
        }
        return CompareResult(
            champion_model=ch_mv,
            challenger_model=ct_mv,
            champion_eval=ch_eval,
            challenger_eval=ct_eval,
            comparability_result=comp_result,
            metric_deltas=payload.metric_deltas,
            payload=payload,
            extra=extra,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_model(self, model_id: str, version: str, expected_status: ModelLifecycleStatus | None, status_err: str) -> tuple[ModelVersion, str]:
        if not model_id or not isinstance(model_id, str):
            raise CompareValidationError(
                ERR_EMPTY_CHAMPION_MODEL if expected_status == ModelLifecycleStatus.CHAMPION else ERR_EMPTY_CHALLENGER_MODEL,
                "model_id required non-empty str",
                {"model_id": model_id},
            )
        if not version or not isinstance(version, str):
            raise CompareValidationError(
                ERR_EMPTY_CHAMPION_MODEL if expected_status == ModelLifecycleStatus.CHAMPION else ERR_EMPTY_CHALLENGER_MODEL,
                "model version required non-empty str",
                {"model_id": model_id, "version": version},
            )
        try:
            mv, sha = self.registry.get(model_id, version)
        except Exception as exc:
            # registry raises RegistryError on missing/corrupt
            raise CompareValidationError(
                ERR_MODEL_NOT_FOUND,
                f"registry get failed: {exc!r}",
                {"model_id": model_id, "version": version},
            ) from exc
        if expected_status is not None and mv.status != expected_status:
            raise CompareValidationError(
                status_err,
                f"expected status {expected_status.value}, got {mv.status.value}",
                {"model_id": mv.model_id, "version": mv.version, "expected": expected_status.value, "actual": mv.status.value},
            )
        return mv, sha

    def _load_required_evidences(self, model_id: str, version: str) -> dict[EvidenceKind, EvidenceRef]:
        """Return dict of required kinds; missing any → EVIDENCE_NOT_FOUND via compare.MISSING style error."""
        all_ev = self.registry.list_evidence(model_id, version)
        out: dict[EvidenceKind, EvidenceRef] = {}
        missing: list[str] = []
        for k in REQUIRED_EVIDENCE_KINDS:
            match = [e for e in all_ev if e.kind == k]
            if not match:
                missing.append(k.value)
                continue
            # canonical: pick earliest ref_id ASC (deterministic)
            match_sorted = sorted(match, key=lambda e: e.ref_id)
            out[k] = match_sorted[0]
        if missing:
            # Treat missing required evidence as ARTIFACT_NOT_FOUND equivalent (deterministic error)
            raise CompareValidationError(
                ERR_ARTIFACT_NOT_FOUND,
                f"missing required evidence kinds (need {[k.value for k in REQUIRED_EVIDENCE_KINDS]})",
                {"model_id": model_id, "version": version, "missing": sorted(missing), "present_kinds": sorted([e.kind.value for e in all_ev])},
            )
        return out

    def _build_model_evaluation(
        self,
        *,
        mv: ModelVersion,
        artifact: dict[str, Any],
        eval_ref: EvidenceRef,
        side: str,
        evaluation_ts_override: str | None,
        correlation: str,
        causation: str,
        thresholds_config_version_override: str | None,
    ) -> ModelEvaluation:
        """Build typed ModelEvaluation from artifact 11-metrics dict. Strict fail-closed.

        JSON serialization -> Decimal keys deserialized as str; coerce back to Decimal here.
        Int keys may be deserialized as int OK; bool exact.
        """
        metrics_raw = artifact.get("metrics")
        if not isinstance(metrics_raw, dict):
            raise CompareValidationError(
                ERR_ARTIFACT_CORRUPT,
                f"{side} artifact missing required object field 'metrics' (11 required keys)",
                {"side": side, "artifact_top_keys": sorted(artifact.keys())},
            )
        # --- numeric coercion from JSON-safe primitives back to typed strict ---
        from decimal import Decimal as _Dec
        from app.evaluation.delta import round_metric_value, DECIMAL_KEYS, INT_NONNEG_KEYS, FLOAT_KEYS

        coerced: dict[str, Any] = {}
        for k, v in metrics_raw.items():
            if isinstance(v, bool):
                coerced[k] = bool(v)
                continue
            if k in DECIMAL_KEYS:
                try:
                    if isinstance(v, (int, float, str)):
                        coerced[k] = _Dec(str(v))
                    elif isinstance(v, _Dec):
                        coerced[k] = v
                    else:
                        raise CompareValidationError(
                            ERR_METRIC_TYPE_MISMATCH,
                            f"{side} artifact.metrics[{k!r}] unsupported decimal type={type(v).__name__}",
                            {"metric_key": k, "type": type(v).__name__},
                        )
                except (ValueError, ArithmeticError) as exc:
                    raise CompareValidationError(
                        ERR_METRIC_TYPE_MISMATCH,
                        f"{side} artifact.metrics[{k!r}] invalid decimal literal={v!r}",
                        {"metric_key": k, "raw": str(v)[:120]},
                    ) from exc
            elif k in INT_NONNEG_KEYS:
                if isinstance(v, int):
                    coerced[k] = int(v)
                elif isinstance(v, float) and v.is_integer():
                    coerced[k] = int(v)
                elif isinstance(v, str) and v.lstrip("-").isdigit():
                    coerced[k] = int(v)
                else:
                    raise CompareValidationError(
                        ERR_METRIC_TYPE_MISMATCH,
                        f"{side} artifact.metrics[{k!r}] invalid int literal={v!r}",
                        {"metric_key": k, "raw": str(v)[:120]},
                    )
            elif k in FLOAT_KEYS:
                try:
                    if isinstance(v, (int, float, str, _Dec)):
                        coerced[k] = float(v)
                    else:
                        raise CompareValidationError(
                            ERR_METRIC_TYPE_MISMATCH,
                            f"{side} artifact.metrics[{k!r}] unsupported float type={type(v).__name__}",
                            {"metric_key": k, "type": type(v).__name__},
                        )
                except (ValueError, ArithmeticError) as exc:
                    raise CompareValidationError(
                        ERR_METRIC_TYPE_MISMATCH,
                        f"{side} artifact.metrics[{k!r}] invalid float literal={v!r}",
                        {"metric_key": k, "raw": str(v)[:120]},
                    ) from exc
            else:
                coerced[k] = v
        metrics_validated = validate_metrics_strict(coerced, f"{side} artifact.metrics")
        rounded_metrics: dict[str, Any] = {}
        for k in sorted(list(metrics_validated.keys())):
            try:
                rounded_metrics[k] = round_metric_value(metrics_validated[k], k)
            except CompareValidationError:
                rounded_metrics[k] = metrics_validated[k]
        # evaluate metadata fields
        dataset_kind_raw = artifact.get("dataset_kind") or mv.dataset_kind.value
        if isinstance(dataset_kind_raw, str):
            try:
                dataset_kind = DatasetKindEnum(dataset_kind_raw)
            except ValueError as exc:
                raise CompareValidationError(
                    ERR_METRIC_TYPE_MISMATCH,
                    f"{side} artifact dataset_kind invalid",
                    {"side": side, "dataset_kind": dataset_kind_raw},
                ) from exc
        elif isinstance(dataset_kind_raw, DatasetKindEnum):
            dataset_kind = dataset_kind_raw
        else:
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"{side} artifact dataset_kind invalid type",
                {"side": side, "type": type(dataset_kind_raw).__name__},
            )
        thresholds_cfg: str
        if thresholds_config_version_override:
            thresholds_cfg = str(thresholds_config_version_override)
        else:
            tc = artifact.get("thresholds_config_version") or mv.metadata.get("thresholds_config_version") or "thresholds-v1-default"
            thresholds_cfg = str(tc)
        evaluation_ts: str
        if evaluation_ts_override:
            evaluation_ts = evaluation_ts_override
        else:
            evaluation_ts = str(artifact.get("evaluation_ts") or eval_ref.source_created_ts)
        if not evaluation_ts or not isinstance(evaluation_ts, str):
            raise CompareValidationError(ERR_METRIC_TYPE_MISMATCH, f"{side} evaluation_ts invalid", {"side": side, "evaluation_ts": evaluation_ts})
        eval_id = artifact.get("eval_id") or f"eval-{eval_ref.ref_id}"
        if not _ulidish(eval_id):
            eval_id = f"eval{eval_ref.ref_id[:16].replace('-','_').replace(':','_')}"
            if not _ulidish(eval_id):
                eval_id = "EVAL_DEFAULT_01"
        correlation_id_val = artifact.get("correlation_id") or correlation
        causation_id_val = artifact.get("causation_id") or causation
        if not _ulidish(correlation_id_val):
            correlation_id_val = "CORR_DEFAULT_01"
        if not _ulidish(causation_id_val):
            causation_id_val = "CAUS_DEFAULT_01"
        paper_flag = bool(artifact.get("paper_flag", False))
        oos_flag = bool(rounded_metrics["oos_flag"])
        evaluation_window_days = int(rounded_metrics.get("window_days", 0))
        if isinstance(evaluation_window_days, bool) or not isinstance(evaluation_window_days, int):
            raise CompareValidationError(
                ERR_METRIC_TYPE_MISMATCH,
                f"{side} evaluation_window_days must be int",
                {"type": type(evaluation_window_days).__name__},
            )
        try:
            me = ModelEvaluation(
                eval_id=eval_id,  # type: ignore[arg-type]
                model_id=mv.model_id,
                model_version=mv.version,
                dataset_kind=dataset_kind,
                metrics=rounded_metrics,
                evaluation_ts=evaluation_ts,  # type: ignore[arg-type]
                thresholds_config_version=thresholds_cfg,
                evaluation_window_days=evaluation_window_days,
                oos_flag=oos_flag,
                paper_flag=paper_flag,
                correlation_id=correlation_id_val,  # type: ignore[arg-type]
                causation_id=causation_id_val,  # type: ignore[arg-type]
                notes=artifact.get("notes"),
            )
        except Exception as exc:
            raise CompareValidationError(
                ERR_ARTIFACT_CORRUPT,
                f"{side} artifact → ModelEvaluation constructor failed contract validation: {exc!r}",
                {"side": side},
            ) from exc
        return me

    @staticmethod
    def _build_artifact_summary(artifact: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        # fold count from per_fold_metrics / walk_forward_folds / fold_count
        for k in ("fold_count", "n_folds", "fold_total"):
            v = artifact.get(k)
            if isinstance(v, int):
                summary["fold_count"] = int(v)
                break
        pfm = artifact.get("per_fold_metrics")
        if isinstance(pfm, list) and "fold_count" not in summary:
            summary["fold_count"] = len(pfm)
        summary["per_fold_metrics"] = pfm if isinstance(pfm, list) else None
        rmat = artifact.get("regime_matrix") or artifact.get("regime_performance")
        if isinstance(rmat, list):
            summary["regime_matrix"] = rmat
        cost_cfg = artifact.get("cost_config_version") or artifact.get("cost_metadata", {}).get("version") if isinstance(artifact.get("cost_metadata"), dict) else artifact.get("cost_config_version")
        summary["cost_config_version"] = str(cost_cfg) if cost_cfg is not None else ""
        return summary

    @staticmethod
    def _build_fold_deltas(ch_summary: dict[str, Any], ct_summary: dict[str, Any]) -> list[MetricDelta]:
        c_pf = ch_summary.get("per_fold_metrics")
        t_pf = ct_summary.get("per_fold_metrics")
        if not isinstance(c_pf, list) or not isinstance(t_pf, list):
            return []
        from app.evaluation.exceptions import ERR_INCOMPARABLE_FOLD_COUNT, CompareValidationError

        if len(c_pf) != len(t_pf):
            raise CompareValidationError(
                ERR_INCOMPARABLE_FOLD_COUNT,
                "per_fold_metrics length mismatch between champion and challenger",
                {"champion_folds": len(c_pf), "challenger_folds": len(t_pf)},
            )
        result: list[MetricDelta] = []
        from decimal import Decimal as _DecF
        from app.evaluation.delta import DECIMAL_KEYS, INT_NONNEG_KEYS, FLOAT_KEYS

        def _coerce_f(k: str, v: Any) -> Any:
            if isinstance(v, bool):
                return bool(v)
            if k in DECIMAL_KEYS and isinstance(v, (int, float, str)):
                try:
                    return _DecF(str(v))
                except (ValueError, ArithmeticError):
                    return v
            if k in INT_NONNEG_KEYS:
                if isinstance(v, int):
                    return int(v)
                if isinstance(v, float) and v.is_integer():
                    return int(v)
                if isinstance(v, str) and v.lstrip("-").isdigit():
                    return int(v)
                return v
            if k in FLOAT_KEYS and isinstance(v, (int, str, _DecF)):
                try:
                    return float(v)
                except (ValueError, ArithmeticError):
                    return v
            return v

        for idx, (cf, tf) in enumerate(zip(c_pf, t_pf)):
            if not isinstance(cf, dict) or not isinstance(tf, dict):
                continue
            for inner_key in sorted(set(list(cf.keys())) & set(list(tf.keys()))):
                if inner_key not in metric_direction_table and not inner_key.startswith(("aggregate_",)):
                    continue
                try:
                    c_val = _coerce_f(inner_key, cf[inner_key])
                    t_val = _coerce_f(inner_key, tf[inner_key])
                    direction = metric_direction_table.get(inner_key, None)
                    if direction is None:
                        continue
                    delta = compare_metric_delta(inner_key, {inner_key: c_val}, {inner_key: t_val})
                    delta.metric_key = f"fold_{idx:03d}_{inner_key}"
                    result.append(delta)
                except Exception:
                    continue
        return result

    @staticmethod
    def _build_regime_deltas(ch_summary: dict[str, Any], ct_summary: dict[str, Any]) -> list[MetricDelta]:
        c_mat = ch_summary.get("regime_matrix")
        t_mat = ct_summary.get("regime_matrix")
        if not isinstance(c_mat, list) or not isinstance(t_mat, list):
            return []
        # Build dict keys (strategy_id, regime)
        def _to_indexed(mat: list[Any]) -> dict[tuple[str, str], dict[str, Any]]:
            out: dict[tuple[str, str], dict[str, Any]] = {}
            for row in mat:
                if not isinstance(row, dict):
                    continue
                sid = row.get("strategy_id")
                reg = row.get("regime")
                if isinstance(sid, str) and isinstance(reg, str):
                    out[(sid, reg)] = dict(row)
            return out
        c_idx = _to_indexed(c_mat)
        t_idx = _to_indexed(t_mat)
        if set(c_idx.keys()) != set(t_idx.keys()):
            from app.evaluation.exceptions import ERR_INCOMPARABLE_REGIME_GROUPS, CompareValidationError

            raise CompareValidationError(
                ERR_INCOMPARABLE_REGIME_GROUPS,
                "regime matrix groups mismatch champion vs challenger",
                {"champion_groups": sorted([f"{a}|{b}" for a, b in c_idx.keys()]), "challenger_groups": sorted([f"{a}|{b}" for a, b in t_idx.keys()])},
            )
        result: list[MetricDelta] = []
        from decimal import Decimal as _Dec_R
        from app.evaluation.delta import DECIMAL_KEYS, INT_NONNEG_KEYS, FLOAT_KEYS

        def _coerce(k: str, v: Any) -> Any:
            if isinstance(v, bool):
                return bool(v)
            if k in DECIMAL_KEYS and isinstance(v, (int, float, str)):
                try:
                    return _Dec_R(str(v))
                except (ValueError, ArithmeticError):
                    return v
            if k in INT_NONNEG_KEYS:
                if isinstance(v, int):
                    return int(v)
                if isinstance(v, float) and v.is_integer():
                    return int(v)
                if isinstance(v, str) and v.lstrip("-").isdigit():
                    return int(v)
                return v
            if k in FLOAT_KEYS and isinstance(v, (int, str, _Dec_R)):
                try:
                    return float(v)
                except (ValueError, ArithmeticError):
                    return v
            return v

        for key in sorted(c_idx.keys(), key=lambda t: (t[0], t[1])):
            row_c = c_idx[key]
            row_t = t_idx[key]
            for inner_key in ("return_pct", "trade_count", "profit_factor", "sharpe_ratio", "sortino_ratio", "total_fees_quote", "avg_slippage_bps"):
                if inner_key not in row_c or inner_key not in row_t:
                    continue
                try:
                    cv = _coerce(inner_key, row_c[inner_key])
                    tv = _coerce(inner_key, row_t[inner_key])
                    d = compare_metric_delta(inner_key, {inner_key: cv}, {inner_key: tv})
                    d.metric_key = f"regime_{key[0]}_{key[1]}_{inner_key}"
                    result.append(d)
                except Exception:
                    continue
        return result
