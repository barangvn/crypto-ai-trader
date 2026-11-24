"""Stable, deterministic JSON summary for the Paper Trading MVP.

Renders a readable JSON document with a fixed schema, sorted keys and
deterministic numeric/string serialization. Contains no credentials, no API
keys, no secrets and no environment-dependent (wall-clock) fields.

Stdlib-only. No network, no import side effects.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.backtest.runner import BacktestRunResult, compute_result_sha256


SUMMARY_SCHEMA_VERSION: str = "paper_mvp_summary_v1"


def build_summary(
    result: BacktestRunResult,
    *,
    bundle: Any,
    config: Any,
    paper_only: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the stable summary document for a completed backtest run.

    Every value is derived from deterministic inputs (fixture data, static
    configuration and the deterministic run result). Wall-clock timestamps,
    credentials and API keys are intentionally excluded.
    """
    metadata = result.metadata
    return {
        "artifact_schema_version": SUMMARY_SCHEMA_VERSION,
        "bundle": {
            "bundle_id": bundle.bundle_id,
            "bundle_sha256": bundle.compute_sha256(),
            "bundle_version": bundle.bundle_version,
            "symbol_count": len(bundle.symbols),
            "symbols": list(bundle.symbols),
            "timeframe": bundle.timeframe,
        },
        "config": {
            "env_name": config.env_name,
            "run_mode_default": config.run_mode_default,
        },
        "counts": result.counts.to_sorted_dict(),
        "engine_versions": dict(sorted(result.engine_versions.items())),
        "failure_reason_codes": list(result.failure_reason_codes),
        "paper_only": dict(paper_only),
        "performance": result.performance_v2.to_sorted_dict(),
        "provenance": result.provenance,
        "result_sha256": compute_result_sha256(result),
        "run": {
            "end_instant": metadata.end_instant,
            "event_count": metadata.event_count,
            "fill_count": metadata.fill_count,
            "portfolio_snapshot_count": metadata.portfolio_snapshot_count,
            "run_id": metadata.run_id,
            "run_mode": metadata.run_mode,
            "source_type": metadata.source_type,
            "start_instant": metadata.start_instant,
            "timeframe": metadata.timeframe,
            "walk_forward_mode": metadata.walk_forward_mode,
        },
    }


def render_summary_json(summary: dict[str, Any], *, indent: int = 2) -> str:
    """Render the summary as deterministic, key-sorted JSON."""
    return json.dumps(
        summary,
        sort_keys=True,
        indent=indent,
        separators=(",", ": "),
        default=str,
    )


def compute_summary_sha256(summary: dict[str, Any]) -> str:
    """Stable sha256 over the rendered summary document."""
    payload = json.dumps(
        summary,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
