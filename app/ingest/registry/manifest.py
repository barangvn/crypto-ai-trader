from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
import json


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass
class IntegrityReason:
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IntegrityResult:
    passed: bool
    degraded: bool
    reasons: list[IntegrityReason] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "degraded": self.degraded,
            "reasons": [r.to_dict() for r in self.reasons],
        }


@dataclass
class ReplayBundleManifest:
    bundle_id: str
    bundle_version: str
    display_name: str
    fixture_path: str
    event_type: str
    symbols: list[str]
    timeframes: list[str]
    expected_rows: int
    expected_first_ts: str
    expected_last_ts: str
    checksum_sha256: str
    tags: list[str] = field(default_factory=list)
    registered_at: str = field(default_factory=_utc_now_iso)
    notes: str | None = None
    manifest_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReplayBundleManifest":
        return cls(
            bundle_id=str(data["bundle_id"]),
            bundle_version=str(data["bundle_version"]),
            display_name=str(data["display_name"]),
            fixture_path=str(data["fixture_path"]),
            event_type=str(data["event_type"]),
            symbols=list(data["symbols"]),
            timeframes=list(data["timeframes"]),
            expected_rows=int(data["expected_rows"]),
            expected_first_ts=str(data["expected_first_ts"]),
            expected_last_ts=str(data["expected_last_ts"]),
            checksum_sha256=str(data["checksum_sha256"]),
            tags=list(data.get("tags", [])),
            registered_at=str(data.get("registered_at") or _utc_now_iso()),
            notes=data.get("notes"),
            manifest_path=data.get("manifest_path"),
        )

    def save(self, out_path: str | Path) -> Path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        as_d = self.to_dict()
        as_d["manifest_path"] = str(p)
        p.write_text(json.dumps(as_d, indent=2, sort_keys=True), encoding="utf-8")
        return p
