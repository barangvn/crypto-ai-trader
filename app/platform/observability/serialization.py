from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.platform.observability.schema import CanonicalLogLine


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def deterministic_dumps(obj: Any) -> str:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def compute_log_id(
    ts_utc: str,
    level: str,
    module: str,
    msg: str,
    correlation_id: str,
    causation_id: str,
) -> str:
    seed = "|".join(
        [
            ts_utc or "",
            level or "",
            module or "",
            msg or "",
            correlation_id or "",
            causation_id or "",
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def serialize_line(line: CanonicalLogLine) -> str:
    return deterministic_dumps(line.as_dict())
