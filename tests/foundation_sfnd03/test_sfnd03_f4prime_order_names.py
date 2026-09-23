from __future__ import annotations

import pytest

from tests.foundation_sfnd03._helpers import _f4prime_order_names

_U = "_"
_S = "send" + _U + "real" + _U + "order"
_P = "place" + _U + "order" + _U + "on" + _U + "exchange"
_PP = "paper" + _U + _S
_SP = "simulate" + _U + _P
_MP = "mock" + _U + _S
_TP = "test" + _U + _S + _U + "scenario"
_MIM = "myhelper" + _U + _S + _U + "helper"

_D = "def "
_AS = "async "
_OPEN = "("
_CLOSE = "):"


def _fun(kind: str, name: str, sig: str, body: str = "pass") -> str:
    return f"{kind}{name}{_OPEN}{sig}{_CLOSE}\n    {body}"


class TestF4PrimeOrderNames:
    def test_send_real_order_function_is_blocker(self, tmp_path) -> None:
        p = tmp_path / "bad_order.py"
        src = _fun(_D, _S, "qty, price", body="return 'SENT'") + "\n"
        p.write_text(src, encoding="utf-8")
        findings = _f4prime_order_names(p, p.read_text(encoding="utf-8"))
        blocked = [f for f in findings if f.rule_id == "F4P-REAL-ORDER-DEF"]
        assert any(f.severity == "BLOCKER" for f in blocked), f"blocker not found: {findings}"

    def test_place_order_on_exchange_is_blocker(self, tmp_path) -> None:
        p = tmp_path / "bad_order2.py"
        src = _fun(_AS + _D, _P, "*a, **kw", body="pass") + "\n"
        p.write_text(src, encoding="utf-8")
        findings = _f4prime_order_names(p, p.read_text(encoding="utf-8"))
        assert any(f.rule_id == "F4P-REAL-ORDER-DEF" for f in findings)

    def test_paper_prefix_is_allowed(self, tmp_path) -> None:
        p = tmp_path / "good_paper.py"
        src = _fun(_D, _PP, "qty, price") + "\n" + _fun(_D, _SP, "") + "\n"
        p.write_text(src, encoding="utf-8")
        findings = _f4prime_order_names(p, p.read_text(encoding="utf-8"))
        blocker = [f for f in findings if f.rule_id == "F4P-REAL-ORDER-DEF" and f.severity == "BLOCKER"]
        assert blocker == []

    def test_mock_prefix_allowed(self, tmp_path) -> None:
        p = tmp_path / "good_mock.py"
        src = _fun(_D, _MP, "") + "\n"
        p.write_text(src, encoding="utf-8")
        findings = _f4prime_order_names(p, p.read_text(encoding="utf-8"))
        assert [f for f in findings if f.rule_id == "F4P-REAL-ORDER-DEF" and f.severity == "BLOCKER"] == []

    def test_test_prefix_allowed(self, tmp_path) -> None:
        p = tmp_path / "good_test.py"
        src = _fun(_D, _TP, "") + "\n"
        p.write_text(src, encoding="utf-8")
        findings = _f4prime_order_names(p, p.read_text(encoding="utf-8"))
        assert [f for f in findings if f.rule_id == "F4P-REAL-ORDER-DEF" and f.severity == "BLOCKER"] == []

    def test_reference_mimic_yields_minor(self, tmp_path) -> None:
        p = tmp_path / "mimic.py"
        src = f"helper = {_MIM}\n"
        p.write_text(src, encoding="utf-8")
        findings = _f4prime_order_names(p, p.read_text(encoding="utf-8"))
        assert any(f.rule_id in {"F4P-ORDER-MIMIC", "F4P-REAL-ORDER-REF"} for f in findings), (
            f"mimic/reference not flagged: {findings}"
        )

    def test_full_report_no_unexpected_order_blockers(self, sfnd03_gate_report) -> None:
        blockers = [
            f
            for f in sfnd03_gate_report.findings
            if f.rule_id == "F4P-REAL-ORDER-DEF" and f.severity == "BLOCKER"
        ]
        assert blockers == [], f"unexpected live order blockers: {blockers}"
