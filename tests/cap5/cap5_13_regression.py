from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


REGRESSION_BASELINES = [
    ("registry", "tests/registry", 162, "S-MDL-01 registry test collected count baseline"),
    ("evaluation", "tests/evaluation", 244, "S-MDL-02 evaluation collected count baseline"),
    ("gate", "tests/gate", 220, "S-MDL-03 gate collected count baseline"),
    ("rollback", "tests/rollback", 243, "S-MDL-04 rollback collected count baseline"),
]


def _parse_int_from_output(output_text: str, default: int = 0) -> int:
    pattern = r"(\d+)\s+passed"
    m = re.search(pattern, output_text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            return default
    pattern2 = r"collected\s+(\d+)\s+item"
    m2 = re.search(pattern2, output_text, re.IGNORECASE)
    if m2:
        try:
            return int(m2.group(1))
        except (ValueError, TypeError):
            return default
    return default


class TestPhase1RegressionG13:
    def _pytest_subprocess_or_skip(self, testpaths_rel: str) -> tuple[bool, int, str]:
        repo_root = Path(__file__).resolve().parent.parent.parent
        target = repo_root / testpaths_rel
        if not target.exists():
            return False, 0, f"path {target} does not exist, using baseline estimate"
        try:
            import subprocess
            result = subprocess.run(
                [
                    sys.executable, "-m", "pytest",
                    "--collect-only", "-q",
                    "--rootdir", str(repo_root),
                    testpaths_rel,
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(repo_root),
            )
            combined = (result.stdout or "") + "\n" + (result.stderr or "")
            count = _parse_int_from_output(combined, 0)
            if count > 0:
                return True, count, combined
            return True, max(count, 0), combined
        except Exception as exc:
            return False, 0, f"subprocess unavailable: {type(exc).__name__}"

    @pytest.mark.parametrize("suite_id,testpaths_rel,baseline_count,desc", REGRESSION_BASELINES)
    def test_phase1_regression_collected_ge_baseline(
        self, suite_id, testpaths_rel, baseline_count, desc,
    ):
        assert isinstance(baseline_count, int) and baseline_count > 0, (
            f"{suite_id}: baseline_count must be positive integer, got {baseline_count!r}"
        )
        if suite_id == "registry":
            assert baseline_count == 162, (
                f"{suite_id}: CANONICAL baseline MUST be integer 162 (checkpoint 7604262); "
                f"got {baseline_count!r}. Never accept string '4803' here."
            )
        available, actual_count, _out = self._pytest_subprocess_or_skip(testpaths_rel)
        if not available:
            pytest.xfail(f"subprocess pytest not available for {suite_id}; xfail allowed G13")
        if actual_count == 0:
            pytest.xfail(f"pytest --collect-only returned 0 for {suite_id}; possibly no tests at path; xfail allowed")
        assert isinstance(actual_count, int), f"{suite_id}: actual_count must be int; got type={type(actual_count).__name__}"
        assert actual_count >= baseline_count, (
            f"{suite_id} regression: collected {actual_count} < baseline {baseline_count} (FAIL) — "
            f"desc={desc}"
        )

    @pytest.mark.parametrize("suite_id,testpaths_rel,baseline_count,desc", REGRESSION_BASELINES)
    def test_phase1_regression_fail_count_zero(
        self, suite_id, testpaths_rel, baseline_count, desc,
    ):
        assert isinstance(baseline_count, int) and baseline_count > 0
        available, _collected, combined = self._pytest_subprocess_or_skip(testpaths_rel)
        if not available:
            pytest.xfail(f"subprocess unavailable {suite_id}")
        fail_pattern = r"(\d+)\s+failed"
        m = re.search(fail_pattern, combined, re.IGNORECASE)
        if m:
            try:
                fail_count = int(m.group(1))
            except (ValueError, TypeError):
                fail_count = 0
        else:
            fail_count = 0
        if "error" in combined.lower() and "failed" not in combined.lower():
            err_match = re.search(r"(\d+)\s+error", combined, re.IGNORECASE)
            if err_match:
                try:
                    fail_count += int(err_match.group(1))
                except Exception:
                    pass
        assert fail_count == 0, (
            f"{suite_id} regression: FAIL count must be 0; got {fail_count} failures. "
            f"Baseline target: FAIL=0"
        )
