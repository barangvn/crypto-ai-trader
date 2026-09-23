from __future__ import annotations

import pytest

from tests.foundation_sfnd03._helpers import MarkerCatalog


class TestMarkerCatalog:
    def test_exact_three_markers_in_order(self) -> None:
        got = tuple(m.value for m in MarkerCatalog.ordered())
        assert got == ("contract", "replay", "failure_injection")

    def test_enum_values_match_member_names(self) -> None:
        assert MarkerCatalog.contract.value == "contract"
        assert MarkerCatalog.replay.value == "replay"
        assert MarkerCatalog.failure_injection.value == "failure_injection"

    def test_catalog_length_exactly_three(self) -> None:
        assert len(list(MarkerCatalog)) == 3

    def test_no_fourth_marker_added_od01_default_fail_closed(self) -> None:
        values = {m.value for m in MarkerCatalog}
        assert "performance" not in values
        assert "chaos" not in values
        assert "smoke" not in values


class TestIniMarkersRegistered:
    def test_pytest_ini_has_three_contract_replay_failure_injection(self, sfnd03_ini_markers) -> None:
        for name in ("contract", "replay", "failure_injection"):
            assert name in sfnd03_ini_markers, f"missing marker {name}"

    def test_cli_registered_markers_contains_catalog(self, sfnd03_cli_registered_markers) -> None:
        for name in ("contract", "replay", "failure_injection"):
            assert name in sfnd03_cli_registered_markers, f"marker {name} not in pytest --markers"

    def test_sfnd01_markers_preserved(self, sfnd03_ini_markers) -> None:
        for name in ("F1", "F2", "F3", "F4"):
            assert name in sfnd03_ini_markers, f"S-FND-01 marker {name} missing from pytest.ini"

    def test_wrong_marker_name_strict_mode_fails(self, tmp_path) -> None:
        import subprocess
        from tests.foundation_sfnd03._helpers import REPO_ROOT

        bad = tmp_path / "test_bad_marker.py"
        bad.write_text(
            "\n".join(
                [
                    "import pytest",
                    "@pytest.mark.contractz",
                    "def test_x():",
                    "    pass",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["python", "-m", "pytest", "--strict-markers", str(bad)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
            check=False,
        )
        assert proc.returncode != 0, f"strict markers did not fail:\n{proc.stdout}\n{proc.stderr}"
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        assert "contractz" in combined


class TestDecoratorAttach:
    @pytest.mark.contract
    def test_marker_contract_attached(self, request) -> None:  # noqa: PT004
        m = request.node.get_closest_marker("contract")
        assert m is not None

    @pytest.mark.replay
    def test_marker_replay_attached(self, request) -> None:  # noqa: PT004
        m = request.node.get_closest_marker("replay")
        assert m is not None

    @pytest.mark.failure_injection
    def test_marker_failure_injection_attached(self, request) -> None:  # noqa: PT004
        m = request.node.get_closest_marker("failure_injection")
        assert m is not None

    def test_parametrize_contract_marker(self, request) -> None:  # noqa: PT004
        @pytest.mark.contract
        def _f():
            pass

        assert any(m.name == "contract" for m in _f.pytestmark)  # type: ignore[attr-defined]
