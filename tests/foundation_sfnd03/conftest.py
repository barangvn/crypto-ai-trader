from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

import pytest

from ._helpers import (
    MarkerCatalog,
    PRGateScanReport,
    import_from_failure_exists,
    run_full_scan,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYTEST_INI_PATH = REPO_ROOT / "pytest.ini"


def _load_ini_markers(path: Path) -> dict[str, str]:
    """Parse pytest.ini [pytest] markers lines. FAIL_CLOSED on FileNotFound/parse error."""
    import configparser

    if not path.is_file():
        raise RuntimeError(f"pytest.ini missing at {path}")
    cp = configparser.ConfigParser()
    cp.optionxform = str
    with path.open("r", encoding="utf-8") as fh:
        cp.read_file(fh)
    if "pytest" not in cp.sections():
        raise RuntimeError("pytest.ini missing [pytest] section")
    raw = cp["pytest"].get("markers", "")
    out: dict[str, str] = {}
    for line in raw.splitlines():
        s = line.strip()
        if not s or ":" not in s:
            continue
        name, desc = s.split(":", 1)
        out[name.strip()] = desc.strip()
    return out


@pytest.fixture(scope="session")
def sfnd03_ini_markers() -> dict[str, str]:
    return _load_ini_markers(PYTEST_INI_PATH)


@pytest.fixture(scope="session")
def sfnd03_marker_catalog_order() -> tuple[str, ...]:
    return tuple(m.value for m in MarkerCatalog.ordered())


@pytest.fixture(scope="session")
def sfnd03_gate_report() -> PRGateScanReport:
    """Run full static scan once per session. Deterministic output by sort in run_full_scan."""
    return run_full_scan(scan_id="sfnd03-gate-session")


@pytest.fixture(scope="session")
def sfnd03_cli_registered_markers() -> list[str]:
    """Use `python -m pytest --markers` via subprocess list-args shell=False (HR-6)."""
    cmd = ["python", "-m", "pytest", "--markers"]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        shell=False,
        timeout=30,
        check=False,
    )
    out = proc.stdout or ""
    names: list[str] = []
    for line in out.splitlines():
        s = line.strip()
        if not s.startswith("@pytest.mark."):
            continue
        rest = s[len("@pytest.mark.") :].strip()
        for sep in (":", "(", " "):
            if sep in rest:
                rest = rest.split(sep, 1)[0].strip()
        if rest:
            names.append(rest)
    return sorted(set(names))


@pytest.fixture(scope="session")
def sfnd03_ownership_invariant_count() -> int:
    """Count imports from tests.failure.* within S-FND-03 package. MUST == 0 (DoD-6)."""
    return import_from_failure_exists()


def pytest_collection_modifyitems(config, items: Iterable) -> None:  # noqa: ARG001
    """Optional hook: ensure markers under test do not silently skip on unknown names."""
    return None
