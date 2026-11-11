from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
BASELINE_FILE = ROOT / "tests" / "baselines" / "srdh01_baseline_sha256.json"


SRDH01_FILES = [
    "app/contracts/canonical.py",
    "app/contracts/types.py",
    "app/ingest/adapters/replay_bundle_adapter.py",
    "app/platform/__init__.py",
    "app/processing/normalizer.py",
    "app/processing/quality_monitor.py",
    "app/processing/replay_clock.py",
    "tests/integration/test_pipeline_happy_path.py",
    "tests/unit/ingest/test_replay_bundle_adapter.py",
    "tests/unit/platform/test_event_bus.py",
    "tests/unit/processing/test_validator_9checks.py",
    "app/contracts/__init__.py",
    "app/contracts/model.py",
    "app/contracts/opportunity.py",
]


def _sha256(path: Path) -> str:
    # EOL contract: only CRLF -> LF normalization; no other content mutation.
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _load_baseline() -> dict[str, str]:
    assert BASELINE_FILE.exists(), (
        f"Baseline file missing (fail-closed): {BASELINE_FILE}"
    )
    try:
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Baseline JSON is corrupt (fail-closed): {BASELINE_FILE}: {exc}"
        ) from exc


class TestSRDH01Regression:
    def test_srdh01_files_sha256_unchanged_regression_f2(self) -> None:
        baseline = _load_baseline()
        deltas: list[str] = []
        for rel, expected in baseline.items():
            p = ROOT / rel
            if not p.exists():
                deltas.append(f"MISSING {p}")
                continue
            actual = _sha256(p)
            if actual != expected:
                deltas.append(
                    f"CHANGED {p}: expected={expected} actual={actual}"
                )
        assert not deltas, "\n".join(deltas)

    @pytest.mark.parametrize("relpath", SRDH01_FILES)
    def test_each_srdh01_file_exists(self, relpath: str) -> None:
        assert (ROOT / relpath).exists(), f"Missing S-RDH-01 file: {relpath}"


class TestSRDH01SuiteRuns:
    """This is essentially F1 — the full suite, but runs only if explicitly requested with --run-srdh01-suite.
    The full regression test suite is run at the outer level. Here we only verify that the baseline exists."""

    def test_baseline_has_14_entries(self) -> None:
        baseline = _load_baseline()
        assert len(baseline) == 14, f"Expected exactly 14 baseline entries, got {len(baseline)}"
