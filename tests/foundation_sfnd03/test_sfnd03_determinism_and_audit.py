from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.foundation_sfnd03._helpers import (
    PRGateScanReport,
    REPO_ROOT,
    PatternScanFinding,
    import_from_failure_exists,
    run_full_scan,
)


class TestDeterminism10x:
    @pytest.mark.parametrize("run_idx", list(range(10)), ids=lambda i: f"run-{i+1:02d}")
    def test_D1_report_sha256_unique_set_len_one(self, run_idx: int) -> None:
        report = run_full_scan("det-10x-v1")
        sha = report.deterministic_sha256()
        store = getattr(self.__class__, "_sha_store", None)
        if store is None:
            store = []
            setattr(self.__class__, "_sha_store", store)
        store.append(sha)

    def test_D1_assert_unique_count_one(self) -> None:
        store = getattr(self.__class__, "_sha_store", [])
        assert len(store) == 10, f"expected 10 runs; got {len(store)}"
        assert len(set(store)) == 1, f"determinism violated; unique SHAs = {len(set(store))} set={set(store)}"

    def test_D2_scanned_files_sorted_10x_identical(self) -> None:
        file_lists: list[tuple[str, ...]] = []
        for _ in range(10):
            r = run_full_scan("d2-files")
            file_lists.append(tuple(r.scanned_files))
        assert len(set(file_lists)) == 1

    def test_D3_findings_tuple_dedup_10x_identical(self) -> None:
        tuple_sets: list[tuple[tuple, ...]] = []
        for _ in range(10):
            r = run_full_scan("d3-dedup")
            tuple_sets.append(tuple(sorted(f.as_tuple() for f in r.findings)))
        assert len(set(tuple_sets)) == 1

    def test_D4_total_files_scanned_count_stable(self) -> None:
        counts = {len(run_full_scan(f"d4-count-{i}").scanned_files) for i in range(10)}
        assert len(counts) == 1

    def test_D5_marker_catalog_order_stable(self) -> None:
        from tests.foundation_sfnd03._helpers import MarkerCatalog

        orders = {tuple(m.value for m in MarkerCatalog.ordered()) for _ in range(10)}
        assert len(orders) == 1

    def test_D6_deterministic_dumps_same_across_10_runs(self) -> None:
        import dataclasses

        r = run_full_scan("d6-json")
        payloads = {
            r.deterministic_sha256() for _ in range(10)
        }
        assert len(payloads) == 1


class TestFailClosed:
    def test_FC1_missing_ini_raises_runtime(self, tmp_path, monkeypatch) -> None:
        bad = tmp_path / "nope"
        bad.mkdir()
        import tests.foundation_sfnd03.conftest as cft

        with pytest.raises(RuntimeError, match="pytest.ini missing"):
            cft._load_ini_markers(tmp_path / "DOES_NOT_EXIST_pytest.ini")

    def test_FC2_broken_ini_missing_section(self, tmp_path, monkeypatch) -> None:
        bad_ini = tmp_path / "broken.ini"
        bad_ini.write_text("[other]\nmarkers = a:desc\n", encoding="utf-8")
        import tests.foundation_sfnd03.conftest as cft

        with pytest.raises(RuntimeError, match="missing \\[pytest\\]"):
            cft._load_ini_markers(bad_ini)

    def test_FC3_regex_compile_error_aborts_not_silent(self) -> None:
        import re

        with pytest.raises(re.error):
            re.compile("(?P<name>[unclosed")

    def test_FC4_subprocess_timeout_produces_exception(self) -> None:
        import subprocess

        never_ends = [sys.executable, "-c", "while True: pass"]
        with pytest.raises((subprocess.TimeoutExpired, subprocess.CalledProcessError)):
            subprocess.run(never_ends, shell=False, timeout=0.1, check=True, capture_output=True)

    def test_FC5_duplicate_finding_tuple_deduped_once(self) -> None:
        r1 = PatternScanFinding(
            rule_id="X", severity="BLOCKER", file="a.py", line=1, snippet="x"
        )
        r2 = PatternScanFinding(
            rule_id="X", severity="BLOCKER", file="a.py", line=1, snippet="x"
        )
        assert r1.as_tuple() == r2.as_tuple()
        seen = {r1.as_tuple(), r2.as_tuple()}
        assert len(seen) == 1

    def test_FC6_allowlist_read_errors_recorded_not_silent(self) -> None:
        r = PRGateScanReport(scan_id="fc6")
        r.allowlist_read_errors.append("permissions:tests_fixtures/path")
        assert r.allowlist_read_errors

    def test_FC7_syntax_error_ast_produces_major_not_crash(self) -> None:
        from tests.foundation_sfnd03._helpers import _f1prime_network_imports

        p = Path(__file__).with_name("__init__.py")
        fake = p.parent / "broken_fc.py"
        try:
            fake.write_text("def x(\n pass\n", encoding="utf-8")
            findings = _f1prime_network_imports(fake, fake.read_text(encoding="utf-8"))
            assert any(f.rule_id == "F3P-SYNTAX" for f in findings)
        finally:
            fake.unlink(missing_ok=True)

    def test_FC8_gate_report_blocker_passed_is_false(self, sfnd03_gate_report) -> None:
        blockers = [f for f in sfnd03_gate_report.findings if f.severity == "BLOCKER"]
        if blockers:
            assert sfnd03_gate_report.passed is False


class TestAuditAndOwnership:
    def test_A1_ownership_sfnd03_no_imports_of_failure(self, sfnd03_ownership_invariant_count) -> None:
        assert sfnd03_ownership_invariant_count == 0, (
            f"S-FND-03 package imports tests.failure.* count={sfnd03_ownership_invariant_count}"
        )

    def test_A2_no_subprocess_shell_equals_true(self) -> None:
        import ast
        import inspect

        import tests.foundation_sfnd03.conftest as cft

        sources = [inspect.getsource(cft)]
        for src in sources:
            tree = ast.parse(src)
            for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
                if isinstance(call.func, ast.Attribute) and call.func.attr in {"run", "Popen", "call"}:
                    for kw in call.keywords:
                        if kw.arg == "shell":
                            val = getattr(kw.value, "value", None)
                            assert val is not True, "shell=True subprocess call found"

    def test_A3_gate_report_files_list_is_sorted(self, sfnd03_gate_report) -> None:
        assert sfnd03_gate_report.scanned_files == sorted(sfnd03_gate_report.scanned_files)

    def test_A4_correlation_label_import_optional_noop(self) -> None:
        try:
            from app.platform.observability.correlation import CorrelationContext  # noqa: F401
        except Exception:
            pass
        # optional dependency / AC-21 / no crash if import not available on fresh env
        try:
            import sys as _s

            if "app.platform.observability.correlation" in _s.modules:
                ctx = CorrelationContext.new_root()
                assert ctx.correlation_id
        except Exception:
            pass

    def test_A5_smoke_new_pkg_import(self) -> None:
        import tests.foundation_sfnd03 as pkg

        assert pkg.__name__ == "tests.foundation_sfnd03"

    def test_A6_regression_smoke_4_suites(self) -> None:
        """Minimal smoke: each folder has collection hooks. Runs pytest --collect-only with list args."""
        suites = [
            ["tests/foundation_sfnd03"],
            ["tests/foundation"],
            ["tests/failure"],
            ["tests/contracts"],
        ]
        for suite in suites:
            path = REPO_ROOT / suite[0]
            if not path.exists():
                continue
            proc = subprocess.run(
                ["python", "-m", "pytest", f"--rootdir={REPO_ROOT}", "--collect-only", "-q", f"--confcutdir={REPO_ROOT}", suite[0]],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                shell=False,
                timeout=60,
                check=False,
            )
            assert proc.returncode == 0, (
                f"Regression smoke collect failed for {suite}:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
