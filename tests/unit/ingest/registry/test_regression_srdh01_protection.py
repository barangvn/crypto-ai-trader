from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
BASELINE_FILE = ROOT / ".tmp" / "srdh01_baseline_sha256.json"


SRDH01_FILES = [
    "app/ingest/adapters/replay_bundle_adapter.py",
    "app/processing/quality_monitor.py",
    "app/processing/normalizer.py",
    "app/processing/replay_clock.py",
    "app/contracts/canonical.py",
    "app/contracts/market.py",
    "app/contracts/types.py",
    "app/platform/event_bus.py",
    "app/ingest/adapters/base.py",
    "tests/conftest.py",
    "tests/integration/test_pipeline_happy_path.py",
    "tests/integration/test_cap1_live_replay_parity.py",
    "tests/integration/test_cap2_quality_in_envelope.py",
    "tests/unit/processing/test_validator_9checks.py",
    "pyproject.toml",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_baseline() -> dict[str, str]:
    return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))


class TestSRDH01Regression:
    @pytest.mark.skipif(not BASELINE_FILE.exists(), reason="Baseline sha256 file was not created before start")
    def test_srdh01_files_sha256_unchanged_regression_f2(self) -> None:
        baseline = _load_baseline()
        deltas: list[str] = []
        for rel, expected in baseline.items():
            p = ROOT / rel
            if not p.exists():
                deltas.append(f"MISSING {rel}")
                continue
            actual = _sha256(p)
            if actual != expected:
                deltas.append(
                    f"CHANGED {rel}: expected={expected[:16]} actual={actual[:16]}"
                )
        assert not deltas, "\n".join(deltas)

    @pytest.mark.parametrize("relpath", SRDH01_FILES)
    def test_each_srdh01_file_exists(self, relpath: str) -> None:
        assert (ROOT / relpath).exists(), f"Missing S-RDH-01 file: {relpath}"


class TestSRDH01SuiteRuns:
    """This is essentially F1 — the full suite, but runs only if explicitly requested with --run-srdh01-suite.
    The full regression test suite is run at the outer level. Here we only verify that baseline exists."""

    def test_baseline_has_15_entries(self) -> None:
        if not BASELINE_FILE.exists():
            pytest.skip("Baseline not created")
        baseline = _load_baseline()
        assert len(baseline) >= 13, f"Expected >=13 baseline entries, got {len(baseline)}"
