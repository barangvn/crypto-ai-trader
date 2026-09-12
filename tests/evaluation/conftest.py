"""Shared fixtures for tests/evaluation (S-MDL-02).

Provides:
  - sample_champion_mv / sample_challenger_mv → ModelVersion dataclass fixtures
  - sample_sbkt_artifact_maker → callable returning (model_id, version, metrics) → dict (artifact JSON)
  - fresh_registry → in-memory registry (LocalFS tmp_path or pure in-memory ModelRegistry) with evidence refs + predecessor
  - fresh_engine → CompareEngine with tmp_path artifact loader
  - helper make_engine_with_artifacts(tmp_path, champ_metrics, chall_metrics, **cfg) → engine + registry + tmp_path
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.contracts.canonical import QualityFlags  # noqa: E402
from app.contracts.model import (  # noqa: E402
    DatasetKindEnum,
    ModelCompatibilityRef,
    ModelLifecycleStatus,
    ModelPurposeEnum,
    ModelVersion,
    TrainingDataRange,
    _REQUIRED_METRIC_KEYS,
)
from app.evaluation import (  # noqa: E402
    CompareEngine,
    CompareValidationError,
    ERR_INCOMPARABLE_WINDOW,
    metric_direction_table,
    round_metric_value,
    validate_metrics_strict,
)
from app.registry import (  # noqa: E402
    EvidenceKind,
    EvidenceRef,
    LocalFSRegistryStorage,
    ModelRegistry,
)


DEFAULT_EVAL_TS = "2026-09-12T10:00:00.000Z"
DEFAULT_CREATED_TS = "2026-09-01T00:00:00.000Z"
DEFAULT_CORRELATION = "CORR000001"
DEFAULT_CAUSATION = "CAUS000001"
DEFAULT_THRESHOLDS_VERSION = "thresholds-v1.0"
DEFAULT_COST_VERSION = "cost-v1.0"
DEFAULT_COMPAT = ModelCompatibilityRef(
    feature_version="feature-v2.0",
    strategy_version="strategy-v0.1",
    regime_version="regime-v1.0",
)
DEFAULT_WINDOW = TrainingDataRange(start="2025-01-01T00:00:00.000Z", end="2026-01-01T00:00:00.000Z")
DEFAULT_WINDOW_DAYS = 365
DEFAULT_UNIVERSE = ["BTC_USDT", "ETH_USDT"]


def metrics_window_days() -> int:
    return DEFAULT_WINDOW_DAYS


def _base_metrics_template(
    *,
    return_pct: Decimal | None = None,
    max_drawdown_pct: float | None = None,
    sharpe_ratio: float | None = None,
    sortino_ratio: float | None = None,
    profit_factor: float | None = None,
    total_fees_quote: Decimal | None = None,
    avg_slippage_bps: float | None = None,
    trade_count: int | None = None,
    regime_coverage_count: int | None = None,
    window_days: int | None = DEFAULT_WINDOW_DAYS,
    oos_flag: bool | None = True,
    stability: float | None = None,
) -> dict[str, Any]:
    m: dict[str, Any] = {
        "return_pct": Decimal("0.12000000") if return_pct is None else return_pct,
        "max_drawdown_pct": 0.08 if max_drawdown_pct is None else max_drawdown_pct,
        "sharpe_ratio": 1.6 if sharpe_ratio is None else sharpe_ratio,
        "sortino_ratio": 2.1 if sortino_ratio is None else sortino_ratio,
        "profit_factor": 1.45 if profit_factor is None else profit_factor,
        "total_fees_quote": Decimal("250.00000000") if total_fees_quote is None else total_fees_quote,
        "avg_slippage_bps": 3.0 if avg_slippage_bps is None else avg_slippage_bps,
        "trade_count": 240 if trade_count is None else trade_count,
        "regime_coverage_count": 6 if regime_coverage_count is None else regime_coverage_count,
        "window_days": window_days,
        "oos_flag": True if oos_flag is None else oos_flag,
    }
    if stability is not None:
        m["stability"] = float(stability)
    # Round values deterministically
    for k in list(m.keys()):
        m[k] = round_metric_value(m[k], k)
    validate_metrics_strict(m, "fixture_base")
    return m


def champion_metrics() -> dict[str, Any]:
    """Base champion: 12% return / 8% DD / Sharpe 1.6 / PF 1.45 / fees 250 / trades 240 / coverage 6 / OOS true."""
    return _base_metrics_template(
        return_pct=Decimal("0.12000000"),
        max_drawdown_pct=0.08,
        sharpe_ratio=1.6,
        sortino_ratio=2.1,
        profit_factor=1.45,
        total_fees_quote=Decimal("250.00000000"),
        avg_slippage_bps=3.0,
        trade_count=240,
        regime_coverage_count=6,
        stability=0.78,
    )


def challenger_better_metrics() -> dict[str, Any]:
    """Challenger strictly better: higher return/sharpe/PF, lower DD/fees/slippage, more trades, higher coverage, same OOS true."""
    return _base_metrics_template(
        return_pct=Decimal("0.14500000"),
        max_drawdown_pct=0.06,
        sharpe_ratio=1.95,
        sortino_ratio=2.5,
        profit_factor=1.65,
        total_fees_quote=Decimal("210.00000000"),
        avg_slippage_bps=2.2,
        trade_count=260,
        regime_coverage_count=6,
        stability=0.86,
    )


def challenger_mixed_metrics() -> dict[str, Any]:
    """Challenger mixed: return higher, fees higher → mixed."""
    return _base_metrics_template(
        return_pct=Decimal("0.13000000"),
        max_drawdown_pct=0.08,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        profit_factor=1.45,
        total_fees_quote=Decimal("290.00000000"),
        avg_slippage_bps=3.0,
        trade_count=240,
        regime_coverage_count=6,
    )


def champion_challenger_equal_metrics() -> tuple[dict[str, Any], dict[str, Any]]:
    c = _base_metrics_template()
    t = json.loads(json.dumps(c, default=str))
    # Convert back decimal-like strings to Decimal after json roundtrip (decimal serialized to str via json; restore)
    for k in ("return_pct", "total_fees_quote"):
        t[k] = Decimal(str(t[k]))
    # numeric types
    for k in ("max_drawdown_pct", "sharpe_ratio", "sortino_ratio", "profit_factor", "avg_slippage_bps"):
        if k in t and isinstance(t[k], (int, float, str)):
            t[k] = float(t[k])
    for k in ("trade_count", "regime_coverage_count", "window_days"):
        t[k] = int(t[k])
    t["oos_flag"] = bool(t["oos_flag"])
    return c, t


def build_artifact_json_bytes(
    model_id: str,
    version: str,
    metrics: dict[str, Any],
    *,
    dataset_kind: DatasetKindEnum = DatasetKindEnum.OUT_OF_SAMPLE,
    evaluation_ts: str = DEFAULT_EVAL_TS,
    thresholds_config_version: str = DEFAULT_THRESHOLDS_VERSION,
    cost_config_version: str = DEFAULT_COST_VERSION,
    per_fold_metrics: list[dict[str, Any]] | None = None,
    regime_matrix: list[dict[str, Any]] | None = None,
    paper_flag: bool = False,
    eval_id: str = "EVAL000001",
    correlation_id: str = DEFAULT_CORRELATION,
    causation_id: str = DEFAULT_CAUSATION,
    notes: str | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, bytes]:
    """Return (sha256, bytes) with artifact dict JSON + optional fold/regime metadata."""
    payload: dict[str, Any] = {
        "eval_id": eval_id,
        "model_id": model_id,
        "model_version": version,
        "dataset_kind": dataset_kind.value,
        "metrics": metrics,
        "evaluation_ts": evaluation_ts,
        "thresholds_config_version": thresholds_config_version,
        "paper_flag": paper_flag,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "cost_config_version": cost_config_version,
        "evaluation_window_days": int(metrics.get("window_days", DEFAULT_WINDOW_DAYS)),
        "oos_flag": bool(metrics.get("oos_flag", True)),
    }
    if per_fold_metrics is not None:
        payload["per_fold_metrics"] = per_fold_metrics
        payload["fold_count"] = len(per_fold_metrics)
    if regime_matrix is not None:
        payload["regime_matrix"] = regime_matrix
    if notes is not None:
        payload["notes"] = notes
    if extra:
        for k, v in extra.items():
            if k not in payload:
                payload[k] = v
    content = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(content).hexdigest(), content


def make_sample_mv(
    *,
    model_id: str,
    version: str,
    status: ModelLifecycleStatus,
    window: TrainingDataRange = DEFAULT_WINDOW,
    universe: list[str] | None = None,
    thresholds_config_version: str = DEFAULT_THRESHOLDS_VERSION,
    cost_config_version: str = DEFAULT_COST_VERSION,
    compat: ModelCompatibilityRef = DEFAULT_COMPAT,
    dataset_kind: DatasetKindEnum = DatasetKindEnum.OUT_OF_SAMPLE,
    purpose: ModelPurposeEnum = ModelPurposeEnum.DIRECTIONAL,
    walk_forward_run_ids: list[str] | None = None,
    author_ref: str = "AUTH-0001",
    extra_metadata: dict[str, Any] | None = None,
) -> ModelVersion:
    md: dict[str, Any] = {
        "thresholds_config_version": thresholds_config_version,
        "cost_config_version": cost_config_version,
        "author_ref": author_ref,
        "thresholds_config": {"min_return_pct": "0.05", "max_drawdown_pct": 0.20},
        "cost_metadata": {"version": cost_config_version},
        "dataset_kind_override": dataset_kind.value,
        "symbol_universe_size": len(list(universe) if universe is not None else DEFAULT_UNIVERSE),
        "symbol_universe": list(universe) if universe is not None else list(DEFAULT_UNIVERSE),
    }
    if walk_forward_run_ids is not None:
        md["walk_forward_run_ids"] = list(walk_forward_run_ids)
    if extra_metadata:
        md.update(extra_metadata)
    return ModelVersion(
        model_id=model_id,
        version=version,
        purpose=purpose,
        training_data_range=window,
        feature_version=compat.feature_version,
        compatibility_ref=compat,
        hyperparams={"learning_rate": "0.001", "window": int(metrics_window_days())},
        artifact_uri=f"file://artifacts/{model_id}-{version}.json",
        status=status,
        created_ts=DEFAULT_CREATED_TS,
        correlation_id="CORR_MV01_" + model_id.replace("_", "").replace(".", "").ljust(10, "0"),
        causation_id="CAUS_MV01_" + version.replace("_", "").replace(".", "").ljust(10, "0"),
        quality_flags=QualityFlags(),  # clean default
        metadata=md,
    )


def write_tmp_artifact(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / "artifacts"
    p.mkdir(parents=True, exist_ok=True)
    fp = p / name
    fp.write_bytes(content)
    return fp


def build_registry_with_models(
    tmp_path: Path,
    champion_mv: ModelVersion,
    challenger_mv: ModelVersion,
    *,
    champion_artifact_bytes: dict[str, bytes] | None = None,
    challenger_artifact_bytes: dict[str, bytes] | None = None,
    champion_predecessor: dict[str, str] | None = None,
    walk_forward_run_ids: list[str] | None = None,
) -> tuple[ModelRegistry, dict[str, dict[EvidenceKind, Path]]]:
    """Build registry (tmp_path LocalFS storage) + write artifacts + append evidence refs with integrity sha.

    champion_artifact_bytes: {kind: bytes} — defaults to create minimal artifact via build_artifact_json_bytes
    """
    models_dir = tmp_path / "registry"
    storage = LocalFSRegistryStorage(root=models_dir)
    registry = ModelRegistry(storage=storage)
    registry.create(champion_mv)
    registry.create(challenger_mv)
    if champion_predecessor is not None:
        registry.set_predecessor(champion_mv.model_id, champion_mv.version, champion_predecessor["model_id"], champion_predecessor["version"])
    artifact_paths: dict[str, dict[EvidenceKind, Path]] = {"champion": {}, "challenger": {}}
    for side, mv in (("champion", champion_mv), ("challenger", challenger_mv)):
        if walk_forward_run_ids:
            # already in mv metadata for paper/challenger or champion
            pass
        for kind in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL):
            side_bytes = champion_artifact_bytes if side == "champion" else challenger_artifact_bytes
            if side_bytes and kind in side_bytes:
                data = side_bytes[kind]
                integrity = hashlib.sha256(data).hexdigest()
            else:
                integrity = None
                # fallback minimal artifact (never actually used if caller provides primary artifacts; needed because evidence integrity checks may skip)
                data = b'{"metrics":{"return_pct":"0.00000000","max_drawdown_pct":0.0,"sharpe_ratio":0.0,"sortino_ratio":0.0,"profit_factor":0.0,"total_fees_quote":"0.00000000","avg_slippage_bps":0.0,"trade_count":0,"regime_coverage_count":0,"window_days":0,"oos_flag":true},"model_id":"%s","model_version":"%s","dataset_kind":"out_of_sample","evaluation_ts":"%s","thresholds_config_version":"%s","paper_flag":false,"correlation_id":"FALLBACK00001","causation_id":"FALLBACK00001","cost_config_version":"%s","evaluation_window_days":0,"oos_flag":true}' % (
                    mv.model_id.encode().decode(),
                    mv.version,
                    DEFAULT_EVAL_TS,
                    DEFAULT_THRESHOLDS_VERSION,
                    DEFAULT_COST_VERSION,
                ).encode("utf-8")
            fname = f"{side}-{kind.value}-{mv.model_id}-{mv.version}.json"
            p = write_tmp_artifact(tmp_path, fname, data)
            artifact_paths[side][kind] = p
            ref = EvidenceRef(
                kind=kind,
                ref_id=f"REF-{side[:3]}-{kind.value[:4]}-{mv.model_id[:6]}-{mv.version}-{abs(hash(fname))%100000:05d}",
                artifact_uri=str(p.resolve()),
                source_created_ts=DEFAULT_EVAL_TS,
                correlation_id=DEFAULT_CORRELATION,
                integrity_sha256=hashlib.sha256(data).hexdigest(),
                metadata={"side": side, "kind": kind.value},
            )
            registry.append_evidence(mv.model_id, mv.version, ref)
    return registry, artifact_paths


def make_engine_with_fixtures(
    tmp_path: Path,
    champ_metrics: dict[str, Any],
    chall_metrics: dict[str, Any],
    *,
    champion_model_id: str = "champion_btc_v1",
    champion_version: str = "1.0.0",
    challenger_model_id: str = "challenger_btc_v2",
    challenger_version: str = "1.2.0",
    window: TrainingDataRange = DEFAULT_WINDOW,
    challenger_window: TrainingDataRange | None = None,
    universe: list[str] = DEFAULT_UNIVERSE,
    challenger_universe: list[str] | None = None,
    thresholds: str = DEFAULT_THRESHOLDS_VERSION,
    challenger_thresholds: str | None = None,
    cost: str = DEFAULT_COST_VERSION,
    challenger_cost: str | None = None,
    compat: ModelCompatibilityRef = DEFAULT_COMPAT,
    challenger_compat: ModelCompatibilityRef | None = None,
    dataset_kind: DatasetKindEnum = DatasetKindEnum.OUT_OF_SAMPLE,
    challenger_dataset_kind: DatasetKindEnum | None = None,
    per_fold: list[dict[str, Any]] | None = None,
    challenger_per_fold: list[dict[str, Any]] | None = None,
    regime: list[dict[str, Any]] | None = None,
    challenger_regime: list[dict[str, Any]] | None = None,
    champion_predecessor: dict[str, str] | None = None,
    integrity_mismatch_champion_historical: bool = False,
    challenger_status: ModelLifecycleStatus = ModelLifecycleStatus.CHALLENGER,
) -> dict[str, Any]:
    """Helper used by all happy-path tests. Returns dict with engine, registry, artifact_paths, champ_mv, chall_mv."""
    ch_mv = make_sample_mv(
        model_id=champion_model_id, version=champion_version, status=ModelLifecycleStatus.CHAMPION,
        window=window, universe=universe, thresholds_config_version=thresholds, cost_config_version=cost,
        compat=compat, dataset_kind=dataset_kind,
    )
    ct_mv = make_sample_mv(
        model_id=challenger_model_id, version=challenger_version, status=challenger_status,
        window=challenger_window if challenger_window is not None else window,
        universe=challenger_universe if challenger_universe is not None else universe,
        thresholds_config_version=challenger_thresholds if challenger_thresholds is not None else thresholds,
        cost_config_version=challenger_cost if challenger_cost is not None else cost,
        compat=challenger_compat if challenger_compat is not None else compat,
        dataset_kind=challenger_dataset_kind if challenger_dataset_kind is not None else dataset_kind,
    )
    _ch_sha, ch_hist = build_artifact_json_bytes(ch_mv.model_id, ch_mv.version, champ_metrics, dataset_kind=dataset_kind, thresholds_config_version=thresholds, cost_config_version=cost, per_fold_metrics=per_fold, regime_matrix=regime, eval_id=f"EVAL-C-{champion_model_id}")
    _ct_sha, ct_hist = build_artifact_json_bytes(ct_mv.model_id, ct_mv.version, chall_metrics, dataset_kind=challenger_dataset_kind or dataset_kind, thresholds_config_version=challenger_thresholds or thresholds, cost_config_version=challenger_cost or cost, per_fold_metrics=challenger_per_fold, regime_matrix=challenger_regime, eval_id=f"EVAL-T-{challenger_model_id}")
    champion_bytes = {
        EvidenceKind.HISTORICAL_OOS_EVAL: ch_hist,
        EvidenceKind.WALK_FORWARD_RUN: ch_hist,  # same content (ok, minimal)
        EvidenceKind.PAPER_REPLAY_EVAL: ch_hist,
    }
    challenger_bytes = {
        EvidenceKind.HISTORICAL_OOS_EVAL: ct_hist,
        EvidenceKind.WALK_FORWARD_RUN: ct_hist,
        EvidenceKind.PAPER_REPLAY_EVAL: ct_hist,
    }
    registry, artifact_paths = build_registry_with_models(
        tmp_path, ch_mv, ct_mv,
        champion_artifact_bytes=champion_bytes,
        challenger_artifact_bytes=challenger_bytes,
        champion_predecessor=champion_predecessor,
    )
    if integrity_mismatch_champion_historical:
        # AFTER evidence ref SHA recorded in registry, tamper champion historical file BYTES.
        # Registry evidence_sha still = original SHA, file bytes = tampered → SHA mismatch.
        hist_path = artifact_paths["champion"][EvidenceKind.HISTORICAL_OOS_EVAL]
        original = hist_path.read_bytes()
        tampered = original[:-1] + (b"!" if not original.endswith(b"!") else b"?")
        hist_path.write_bytes(tampered)
        ch_hist = tampered
    engine = CompareEngine(registry=registry)
    return {
        "engine": engine,
        "registry": registry,
        "artifact_paths": artifact_paths,
        "champion_mv": ch_mv,
        "challenger_mv": ct_mv,
        "champion_historical_sha256_actual": hashlib.sha256(ch_hist).hexdigest(),
        "challenger_historical_sha256_actual": hashlib.sha256(ct_hist).hexdigest(),
    }


@pytest.fixture
def base_champion_metrics() -> dict[str, Any]:
    return champion_metrics()


@pytest.fixture
def base_challenger_better() -> dict[str, Any]:
    return challenger_better_metrics()


@pytest.fixture
def base_challenger_mixed() -> dict[str, Any]:
    return challenger_mixed_metrics()
