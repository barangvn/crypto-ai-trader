from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.contracts.model import ModelLifecycleStatus, ModelVersion

from app.rollback import (
    THRESHOLDS_CONFIG_VERSION_V1,
    ThresholdsConfig,
)


FIXED_TS_EVIDENCE = "2026-09-15T10:00:00Z"
FIXED_TS_WINDOW_END = "2026-09-15T12:00:00Z"
FIXED_TS_STALE_EVIDENCE = "2026-07-01T10:00:00Z"
FIXED_CORR = "corr-rollback-spec-sm04-0001"
FIXED_CAUS = "caus-eval-upstream-sm02-9988"
FIXED_SEED = 1337
CHAMPION_MID = "champ_trend_v3"
CHAMPION_VER = "3.1.0"
PRED_MID = "champ_trend_v2"
PRED_VER = "2.4.1"
ROLLBACK_STRATEGY_REF = "rb-default-v1"
EMPTY_STRATEGY_REF = ""
NONE_STRATEGY_REF = None


def happy_delta_11keys() -> dict[str, Any]:
    return {
        "return_pct": -0.03,
        "max_drawdown_pct": 0.18,
        "sharpe_ratio": 0.95,
        "sortino_ratio": 1.20,
        "profit_factor": 1.05,
        "total_fees_quote": 125.4,
        "avg_slippage_bps": 3.2,
        "trade_count": 142,
        "regime_coverage_count": 5,
        "window_days": 90,
        "oos_flag": True,
    }


def _sample_mv(
    model_id: str,
    version: str,
    status: ModelLifecycleStatus,
    artifact_uri: str = "file:///artifacts/pkg.zip",
) -> ModelVersion:
    return object.__new__(ModelVersion)


def _fill_mv(mv: ModelVersion, **kwargs: Any) -> ModelVersion:
    for k, v in kwargs.items():
        try:
            setattr(mv, k, v)
        except Exception:
            pass
    return mv


def make_champion_mv(
    model_id: str = CHAMPION_MID,
    version: str = CHAMPION_VER,
    status: ModelLifecycleStatus = ModelLifecycleStatus.CHAMPION,
    approval_refs: list | None = None,
) -> ModelVersion:
    mv = _sample_mv(model_id, version, status)
    return _fill_mv(
        mv,
        model_id=model_id,
        version=version,
        status=status,
        artifact_uri=f"file:///artifacts/{model_id}/{version}/pkg.zip",
        approval_refs=approval_refs if approval_refs is not None else ["appr-001"],
    )


def make_predecessor_mv(
    model_id: str = PRED_MID,
    version: str = PRED_VER,
    status: ModelLifecycleStatus = ModelLifecycleStatus.RETIRED,
    artifact_ok: bool = True,
) -> ModelVersion:
    mv = _sample_mv(model_id, version, status)
    uri = (
        f"file:///artifacts/{model_id}/{version}/pkg.zip"
        if artifact_ok
        else ""
    )
    return _fill_mv(
        mv,
        model_id=model_id,
        version=version,
        status=status,
        artifact_uri=uri,
    )


@dataclass
class DummyRegistryStorage:
    _champion: Any = None
    _predecessor: Any = None
    _predecessor_pointer: dict[str, str] | None = None
    _raise_on_get_champion: bool = False
    _raise_on_get_predecessor: bool = False

    def set_champion(self, mv: Any) -> None:
        self._champion = mv

    def set_predecessor(self, mv: Any) -> None:
        self._predecessor = mv

    def set_predecessor_pointer(self, mid: str, ver: str) -> None:
        self._predecessor_pointer = {"model_id": mid, "version": ver}

    def clear_predecessor_pointer(self) -> None:
        self._predecessor_pointer = None

    def get(self, model_id: str, version: str) -> tuple[Any, str]:
        if self._champion is not None:
            cm = self._champion
            c_mid = getattr(cm, "model_id", None)
            c_ver = getattr(cm, "version", None)
            if c_mid == model_id and c_ver == version:
                if self._raise_on_get_champion:
                    raise KeyError("not found")
                return cm, "sha-champion"
        if self._predecessor is not None:
            pm = self._predecessor
            p_mid = getattr(pm, "model_id", None)
            p_ver = getattr(pm, "version", None)
            if p_mid == model_id and p_ver == version:
                if self._raise_on_get_predecessor:
                    raise KeyError("not found pred")
                return pm, "sha-predecessor"
        raise KeyError(f"model {model_id}/{version} not in dummy storage")

    def get_predecessor(self, model_id: str, version: str) -> dict[str, str] | None:
        return self._predecessor_pointer


@pytest.fixture
def thresholds_adn_v1() -> ThresholdsConfig:
    return ThresholdsConfig.defaults_adn_v1()


@pytest.fixture
def thresholds_version_v1_str() -> str:
    return THRESHOLDS_CONFIG_VERSION_V1


@pytest.fixture
def happy_delta_metrics() -> dict[str, Any]:
    return happy_delta_11keys()


@pytest.fixture
def champion_mv_retired() -> ModelVersion:
    return make_champion_mv(status=ModelLifecycleStatus.RETIRED)


@pytest.fixture
def champion_mv_candidate() -> ModelVersion:
    return make_champion_mv(status=ModelLifecycleStatus.CANDIDATE)


@pytest.fixture
def predecessor_mv_retired() -> ModelVersion:
    return make_predecessor_mv(status=ModelLifecycleStatus.RETIRED)


@pytest.fixture
def predecessor_mv_paper() -> ModelVersion:
    return make_predecessor_mv(status=ModelLifecycleStatus.PAPER)


@pytest.fixture
def predecessor_mv_challenger() -> ModelVersion:
    return make_predecessor_mv(status=ModelLifecycleStatus.CHALLENGER)


@pytest.fixture
def predecessor_mv_candidate_ineligible() -> ModelVersion:
    return make_predecessor_mv(status=ModelLifecycleStatus.CANDIDATE)


@pytest.fixture
def predecessor_mv_tested_ineligible() -> ModelVersion:
    return make_predecessor_mv(status=ModelLifecycleStatus.TESTED)


@pytest.fixture
def predecessor_mv_corrupt_artifact() -> ModelVersion:
    return make_predecessor_mv(artifact_ok=False)


@pytest.fixture
def dummy_storage_happy(
    predecessor_mv_retired: ModelVersion,
) -> DummyRegistryStorage:
    s = DummyRegistryStorage()
    s.set_champion(make_champion_mv())
    s.set_predecessor(predecessor_mv_retired)
    s.set_predecessor_pointer(PRED_MID, PRED_VER)
    return s


@pytest.fixture
def dummy_storage_missing_pointer() -> DummyRegistryStorage:
    s = DummyRegistryStorage()
    s.set_champion(make_champion_mv())
    s.clear_predecessor_pointer()
    return s


@pytest.fixture
def dummy_storage_ineligible_candidate_status(
    predecessor_mv_candidate_ineligible: ModelVersion,
) -> DummyRegistryStorage:
    s = DummyRegistryStorage()
    s.set_champion(make_champion_mv())
    s.set_predecessor(predecessor_mv_candidate_ineligible)
    s.set_predecessor_pointer(PRED_MID, PRED_VER)
    return s


@pytest.fixture
def dummy_storage_artifact_corrupt(
    predecessor_mv_corrupt_artifact: ModelVersion,
) -> DummyRegistryStorage:
    s = DummyRegistryStorage()
    s.set_champion(make_champion_mv())
    s.set_predecessor(predecessor_mv_corrupt_artifact)
    s.set_predecessor_pointer(PRED_MID, PRED_VER)
    return s


@pytest.fixture
def dummy_storage_current_not_champion(
    champion_mv_retired: ModelVersion,
) -> DummyRegistryStorage:
    s = DummyRegistryStorage()
    s.set_champion(champion_mv_retired)
    return s


@pytest.fixture
def common_evaluate_kwargs(
    happy_delta_metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "champion_model_id": CHAMPION_MID,
        "champion_version": CHAMPION_VER,
        "trigger_type": "degradation_breach",
        "rollback_strategy_ref_from_cce": ROLLBACK_STRATEGY_REF,
        "promotion_gate_passed_bool_from_cce": True,
        "delta_metrics": happy_delta_metrics,
        "approver_identity": "governor-01",
        "rationale_text": "Degradation observed in live compare, rollback per policy.",
        "prior_state_snapshot_ref": "snap-champ-v3-promoted-001",
        "degradation_evidence_count": 3,
        "evidence_ts": FIXED_TS_EVIDENCE,
        "comparison_window_end_ts": FIXED_TS_WINDOW_END,
        "evidence_integrity_ok_flag": True,
        "evidence_integrity_sha": "",
        "strategy_ref_artifact_exists_flag": True,
        "approval_refs": ["appr-001"],
        "explicit_approval_count_extra": 0,
        "correlation_id": FIXED_CORR,
        "causation_id": FIXED_CAUS,
        "target_mode": "restore_prior_champion",
    }
