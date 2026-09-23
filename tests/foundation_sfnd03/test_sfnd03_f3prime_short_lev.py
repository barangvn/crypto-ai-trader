from __future__ import annotations

import pytest

from tests.foundation_sfnd03._helpers import _f3prime_short_and_leverage


class TestF3PrimeShortAndLeverage:
    def test_short_direction_outside_contracts_is_blocker(self, tmp_path) -> None:
        p = tmp_path / "app_logic.py"
        p.write_text(
            "\n".join(
                [
                    "class Order:",
                    "    def __init__(self):",
                    "        self.direction = 'short'",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        findings = _f3prime_short_and_leverage(p, p.read_text(encoding="utf-8"))
        short_findings = [f for f in findings if f.rule_id == "F3P-SHORT-DIR"]
        assert any(f.severity == "BLOCKER" for f in short_findings), (
            f"short literal not flagged: {findings}"
        )

    def test_leverage_gt_1_outside_is_blocker(self, tmp_path) -> None:
        p = tmp_path / "app_logic2.py"
        p.write_text(
            "\n".join(
                [
                    "leverage = 5",
                    "margin = 1.25",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        findings = _f3prime_short_and_leverage(p, p.read_text(encoding="utf-8"))
        lev = [f for f in findings if f.rule_id in {"F3P-LEV-GT1"}]
        assert any(f.severity == "BLOCKER" for f in lev), f"lev>1 not flagged: {findings}"

    def test_leverage_eq_1_is_safe(self, tmp_path) -> None:
        p = tmp_path / "app_safe.py"
        p.write_text(
            "\n".join(
                [
                    "leverage = 1",
                    "margin = 1",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        findings = _f3prime_short_and_leverage(p, p.read_text(encoding="utf-8"))
        lev = [f for f in findings if f.rule_id in {"F3P-LEV-GT1"}]
        assert lev == []

    def test_short_direction_in_contracts_folder_is_allowed_relpath_hook(
        self, tmp_path, monkeypatch
    ) -> None:
        import tests.foundation_sfnd03._helpers as h

        good = tmp_path / "allowed_short.py"
        good.write_text("direction = 'short'\n", encoding="utf-8")
        old_rel = h._rel  # noqa: SLF001
        try:
            h._rel = lambda p: "app/contracts/orderbook.py"  # type: ignore[method-assign]
            findings = _f3prime_short_and_leverage(good, good.read_text(encoding="utf-8"))
            assert [f for f in findings if f.rule_id == "F3P-SHORT-DIR"] == []
        finally:
            h._rel = old_rel  # type: ignore[method-assign]

    def test_test_func_name_short_substr_not_scanned_field_level(
        self, tmp_path
    ) -> None:
        p = tmp_path / "test_short_name.py"
        p.write_text(
            "\n".join(
                [
                    "def test_short_entry_scenario():",
                    "    return 'ok'",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        findings = _f3prime_short_and_leverage(p, p.read_text(encoding="utf-8"))
        assert [f for f in findings if f.rule_id == "F3P-SHORT-DIR"] == []

    def test_full_report_no_unexpected_short_leverage_blockers(
        self, sfnd03_gate_report
    ) -> None:
        blockers = [
            f
            for f in sfnd03_gate_report.findings
            if f.rule_id in {"F3P-SHORT-DIR", "F3P-LEV-GT1"} and f.severity == "BLOCKER"
        ]
        for f in blockers:
            assert any(
                f.file.startswith(prefix)
                for prefix in (
                    "app/contracts",
                    "app/risk",
                    "app/simulation",
                    "app/strategies",
                    "app/backtest",
                )
            ), f"F3' blocker outside allowlist: {f}"
