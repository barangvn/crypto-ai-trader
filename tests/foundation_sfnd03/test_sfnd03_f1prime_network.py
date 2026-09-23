from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.foundation_sfnd03._helpers import (
    F1PRIME_ALLOW_SUBDIRS,
    PatternScanFinding,
    REPO_ROOT,
    _f1prime_network_imports,
    _norm_path,
)


class TestF1PrimeNetworkBlockedOutsideAdapters:
    def test_requests_import_in_nonadapter_is_blocker(self, tmp_path) -> None:
        p = tmp_path / "bad_network.py"
        p.write_text("import requests\n", encoding="utf-8")
        findings = _f1prime_network_imports(p, p.read_text(encoding="utf-8"))
        assert any(f.severity == "BLOCKER" for f in findings)
        rule_ids = {f.rule_id for f in findings}
        assert "F1P-NET-IMPORT" in rule_ids

    def test_httpx_from_import_nonadapter_is_blocker(self, tmp_path) -> None:
        p = tmp_path / "bad_httpx.py"
        p.write_text("from httpx import Client\n", encoding="utf-8")
        findings = _f1prime_network_imports(p, p.read_text(encoding="utf-8"))
        assert any(f.rule_id == "F1P-NET-IMPORT" and f.severity == "BLOCKER" for f in findings)

    def test_aiohttp_import_blocked(self, tmp_path) -> None:
        p = tmp_path / "bad_aio.py"
        p.write_text("import aiohttp\n", encoding="utf-8")
        findings = _f1prime_network_imports(p, p.read_text(encoding="utf-8"))
        assert any(f.rule_id == "F1P-NET-IMPORT" for f in findings)

    def test_websockets_import_blocked(self, tmp_path) -> None:
        p = tmp_path / "bad_ws.py"
        p.write_text("import websockets\n", encoding="utf-8")
        findings = _f1prime_network_imports(p, p.read_text(encoding="utf-8"))
        assert any(f.rule_id == "F1P-NET-IMPORT" for f in findings)

    def test_adapter_folder_allows_requests(self) -> None:
        adapters_dir = REPO_ROOT / "app" / "ingest" / "adapters"
        if not adapters_dir.exists():
            pytest.skip("no adapters dir present in baseline")
        candidate = adapters_dir / "__allow_f1prime_check.py"
        try:
            candidate.write_text("import requests\n", encoding="utf-8")
            findings = _f1prime_network_imports(candidate, candidate.read_text(encoding="utf-8"))
            assert findings == []
        finally:
            candidate.unlink(missing_ok=True)

    def test_urllib_nonadapter_blocked(self, tmp_path) -> None:
        p = tmp_path / "bad_url.py"
        p.write_text("import urllib.request\n", encoding="utf-8")
        findings = _f1prime_network_imports(p, p.read_text(encoding="utf-8"))
        assert any(f.rule_id == "F1P-NET-IMPORT" for f in findings)

    def test_syntax_error_produces_major_not_crash(self, tmp_path) -> None:
        p = tmp_path / "bad_syntax.py"
        p.write_text("def foo(:\n  pass\n", encoding="utf-8")
        findings = _f1prime_network_imports(p, p.read_text(encoding="utf-8"))
        rule_ids = {f.rule_id for f in findings}
        assert "F3P-SYNTAX" in rule_ids
        assert all(f.severity in {"MAJOR", "MINOR"} for f in findings)

    def test_full_gate_report_no_network_import_blockers_in_repo_app(
        self, sfnd03_gate_report
    ) -> None:
        blockers = [
            f for f in sfnd03_gate_report.findings
            if f.rule_id == "F1P-NET-IMPORT" and f.severity == "BLOCKER"
        ]
        for f in blockers:
            assert any(
                _norm_path(f.file).startswith(prefix) for prefix in F1PRIME_ALLOW_SUBDIRS
            ), f"F1' BLOCKER outside allowlist: {f}"
