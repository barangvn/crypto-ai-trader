from __future__ import annotations

import pytest

from tests.foundation_sfnd03._helpers import (
    F2PRIME_MANDATORY_KEYS,
    PatternScanFinding,
    _f2prime_credentials,
)

_AK = "api" + "_" + "key"
_AK2 = "api" + "-" + "key"
_SK = "sec" + "ret"
_SKK = _SK + "_" + "key"
_PW = "pass" + "word"
_AT = "ac" + "cess" + "_" + "tok" + "en"
_RT = "ref" + "resh" + "_" + "tok" + "en"
_CR = "creden" + "tial"
_CRS = _CR + "s"
_PK = "priv" + "ate" + "_" + "key"
_BK = "BINANCE" + "_" + "API" + "_" + "KEY"
_BK2 = "BINANCE" + "-" + "API" + "-" + "KEY"
_OK = "OKX" + "_" + "KEY"
_OK2 = "OKX" + "_" + "API" + "_" + "KEY"


def _line(var: str, val: str) -> str:
    return f"{var} = {val}"


_KEY_RHS: list[tuple[str]] = [
    (_line(_AK, '"sk_live_abcdef1234567890"'),),
    (_line(_AK.upper(), "'abc'"),),
    (_line(_AK2, "'xyz'"),),
    (_line(_SK, "'hushhush1234'"),),
    (_line(_SKK.upper(), "'topconfidential'"),),
    (_line(_PW, "'hunter2'"),),
    (_line(_AT, "'tk_abc123'"),),
    (_line(_RT, "'rf_deadbeef'"),),
    (_line(_CR, "'plaincred'"),),
    (_line(_CRS, "'list'"),),
    (_line(_PK, "'RSA PRIVATE'"),),
    (_line(_PK.upper(), "'BEGIN'"),),
    (_line(_BK, "'bi_abc'"),),
    (_line(_BK2, "'bi2'"),),
    (_line(_OK, "'okx_abcd1234'"),),
    (_line(_OK2, "'okx2'"),),
]


class TestF2PrimeEightMandatoryKeys:
    @pytest.mark.parametrize(
        "key_rhs",
        _KEY_RHS,
        ids=lambda t: t[0][:40],
    )
    def test_literal_triggers_blocker(self, key_rhs: tuple[str, str], tmp_path) -> None:
        line = key_rhs[0]
        p = tmp_path / "bad_creds.py"
        p.write_text(line + "\n", encoding="utf-8")
        findings = _f2prime_credentials(p, p.read_text(encoding="utf-8"))
        assert any(
            f.rule_id == "F2P-CRED-LITERAL" and f.severity == "BLOCKER" for f in findings
        ), f"cred literal not detected in: {line!r}, findings={findings}"

    def test_os_environ_reference_not_flagged(self, tmp_path) -> None:
        p = tmp_path / "good_env.py"
        p.write_text(f'{_AK} = os.environ["{_AK.upper()}"]\n', encoding="utf-8")
        findings = _f2prime_credentials(p, p.read_text(encoding="utf-8"))
        literals = [f for f in findings if f.rule_id == "F2P-CRED-LITERAL"]
        assert literals == []

    def test_os_getenv_reference_not_flagged(self, tmp_path) -> None:
        p = tmp_path / "good_env2.py"
        p.write_text(f"{_SK} = os.getenv('{_SK.upper()}')\n", encoding="utf-8")
        findings = _f2prime_credentials(p, p.read_text(encoding="utf-8"))
        assert [f for f in findings if f.rule_id == "F2P-CRED-LITERAL"] == []

    def test_concat_split_pattern_not_false_positive(self, tmp_path) -> None:
        """S-FND-02 concat-split avoidance: ensure grep+dual mode does NOT flag dynamic build."""
        _AP = '"ap" + "i" + "_" + "ke" + "y"'
        _AN = '"".join(["se", "cr", "et"])'
        _CMT = f"# Commented: {_AK} = 'actual_should_flag_only_in_code'\n"
        p = tmp_path / "concat_pattern.py"
        p.write_text(
            f'KEY_NAME = {_AP}\nANOTHER = {_AN}\n{_CMT}',
            encoding="utf-8",
        )
        findings = _f2prime_credentials(p, p.read_text(encoding="utf-8"))
        blocker_literals = [
            f for f in findings
            if f.rule_id == "F2P-CRED-LITERAL" and f.severity == "BLOCKER"
        ]
        assert blocker_literals == [], f"false positive on concat-split: {blocker_literals}"

    def test_fixtures_path_skipped_for_credential_scan(self, tmp_path, monkeypatch) -> None:
        import tests.foundation_sfnd03._helpers as h

        good = tmp_path / "tests_fixtures" / "mock_keys.py"
        good.parent.mkdir(exist_ok=True, parents=True)
        good.write_text(f"{_AK} = 'fixture-only-mock'\n", encoding="utf-8")
        rel_old = h._rel  # noqa: SLF001
        try:
            h._rel = lambda p: f"tests_fixtures/{p.name}"  # type: ignore[method-assign]
            findings = _f2prime_credentials(good, good.read_text(encoding="utf-8"))
            assert findings == []
        finally:
            h._rel = rel_old  # type: ignore[method-assign]

    def test_full_report_has_no_credential_blockers(self, sfnd03_gate_report) -> None:
        blockers = [
            f for f in sfnd03_gate_report.findings
            if f.rule_id == "F2P-CRED-LITERAL" and f.severity == "BLOCKER"
        ]
        for f in blockers:
            assert "config.test.ini" in f.file or "config.stg.ini" in f.file or "tests_fixtures" in f.file, (
                f"Unexpected cred blocker outside allowlist paths: {f}"
            )

    def test_eight_mandatory_key_regex_count(self) -> None:
        """Count validation: exactly 8 regex rules (HR HARD-RED mandatory 8)."""
        assert len(F2PRIME_MANDATORY_KEYS) == 8
