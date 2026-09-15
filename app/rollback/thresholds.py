from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.contracts.model import ModelLifecycleStatus

from app.rollback.exceptions import (
    ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH,
    ROLLBACK_REASON_CODES,
)


THRESHOLDS_CONFIG_VERSION_V1 = "1.0.0"


_ADN_TAG_OD02 = "ADN-NOT-BINDING OD-02 degradation window default"
_ADN_TAG_OD03 = "ADN-NOT-BINDING OD-03 approval minimum default"
_ADN_TAG_OD04 = "ADN-NOT-BINDING OD-04 evidence minimum default"
_ADN_TAG_OD05 = "ADN-NOT-BINDING OD-05 eligible status set default"


def _adn_default_max_degradation_window_days() -> int:
    return 30


def _adn_default_min_rollback_approval_count() -> int:
    return 1


def _adn_default_min_degradation_evidence_count() -> int:
    return 2


def _adn_default_eligible_status_values() -> list[str]:
    return [
        ModelLifecycleStatus.RETIRED.value,
        ModelLifecycleStatus.PAPER.value,
        ModelLifecycleStatus.CHALLENGER.value,
    ]


def _adn_default_thresholds_dict() -> dict[str, Any]:
    return {
        "max_degradation_window_days": _adn_default_max_degradation_window_days(),
        "min_rollback_approval_count": _adn_default_min_rollback_approval_count(),
        "min_degradation_evidence_count": _adn_default_min_degradation_evidence_count(),
        "eligible_status_values": _adn_default_eligible_status_values(),
        "thresholds_config_version": THRESHOLDS_CONFIG_VERSION_V1,
    }


@dataclass
class ThresholdsConfig:
    max_degradation_window_days: int = field(default_factory=_adn_default_max_degradation_window_days)
    min_rollback_approval_count: int = field(default_factory=_adn_default_min_rollback_approval_count)
    min_degradation_evidence_count: int = field(default_factory=_adn_default_min_degradation_evidence_count)
    eligible_status_values: list[str] = field(default_factory=_adn_default_eligible_status_values)
    thresholds_config_version: str = THRESHOLDS_CONFIG_VERSION_V1

    adn_tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.adn_tags = {
            "max_degradation_window_days": _ADN_TAG_OD02,
            "min_rollback_approval_count": _ADN_TAG_OD03,
            "min_degradation_evidence_count": _ADN_TAG_OD04,
            "eligible_status_values": _ADN_TAG_OD05,
        }
        if not isinstance(self.max_degradation_window_days, int) or self.max_degradation_window_days < 1:
            raise ValueError("max_degradation_window_days must be int >= 1")
        if not isinstance(self.min_rollback_approval_count, int) or self.min_rollback_approval_count < 0:
            raise ValueError("min_rollback_approval_count must be int >= 0")
        if not isinstance(self.min_degradation_evidence_count, int) or self.min_degradation_evidence_count < 1:
            raise ValueError("min_degradation_evidence_count must be int >= 1")
        if not isinstance(self.eligible_status_values, list) or not self.eligible_status_values:
            raise ValueError("eligible_status_values must be non-empty list of str")
        for v in self.eligible_status_values:
            if not isinstance(v, str) or not v:
                raise ValueError("eligible_status_values items must be non-empty str")
        if not isinstance(self.thresholds_config_version, str) or not self.thresholds_config_version:
            raise ValueError("thresholds_config_version must be non-empty str")

    @classmethod
    def defaults_adn_v1(cls) -> "ThresholdsConfig":
        return cls(**_adn_default_thresholds_dict())

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "ThresholdsConfig":
        if d is None:
            return cls.defaults_adn_v1()
        if not isinstance(d, dict):
            raise ValueError("ThresholdsConfig.from_dict requires dict or None")
        merged = dict(_adn_default_thresholds_dict())
        for k, v in d.items():
            if k in merged:
                merged[k] = v
        return cls(**merged)

    def eligible_status_set(self) -> set[str]:
        return set(str(v) for v in self.eligible_status_values)


def check_thresholds_version(
    cfg: ThresholdsConfig,
    expected_version: str | None,
) -> list[str]:
    reasons: list[str] = []
    if expected_version is None:
        return reasons
    if not isinstance(expected_version, str) or not expected_version:
        reasons.append(ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH)
        return reasons
    if cfg.thresholds_config_version != expected_version:
        reasons.append(ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH)
    return reasons
