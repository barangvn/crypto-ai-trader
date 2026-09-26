from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._validation import (
    SCHEMA_REF_CONTRACTS_MD,
    validate_contract_version,
    validate_instant,
)


@dataclass(frozen=True)
class ClockRefT:
    wall: str
    replay: str | None = None

    def __post_init__(self) -> None:
        wall = object.__getattribute__(self, "wall")
        validate_instant(wall, "clock_ref.wall")
        replay = object.__getattribute__(self, "replay")
        if replay is not None:
            validate_instant(replay, "clock_ref.replay")


@dataclass(frozen=True)
class SchemaRefT:
    contracts_md: str = SCHEMA_REF_CONTRACTS_MD
    feature_version: str | None = None
    strategy_version: str | None = None
    model_id: str | None = None

    def __post_init__(self) -> None:
        contracts_md = object.__getattribute__(self, "contracts_md")
        if not isinstance(contracts_md, str) or not contracts_md.startswith("CONTRACTS.md@"):
            from ._validation import ContractValidationError
            raise ContractValidationError(
                "[schema_ref.contracts_md] must match 'CONTRACTS.md@<semver>', e.g. "
                + SCHEMA_REF_CONTRACTS_MD
            )
        tag = contracts_md[len("CONTRACTS.md@"):]
        validate_contract_version(tag, "schema_ref.contracts_md")

        for fn in ("feature_version", "strategy_version", "model_id"):
            val = object.__getattribute__(self, fn)
            if val is None:
                continue
            if not isinstance(val, str) or len(val) == 0 or len(val) > 256:
                from ._validation import ContractValidationError
                raise ContractValidationError(
                    f"[schema_ref.{fn}] must be non-empty str max 256 or None"
                )


__all__ = ["ClockRefT", "SchemaRefT"]
