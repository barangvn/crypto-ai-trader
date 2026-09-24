from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator

import pytest


@pytest.fixture
def tmp_ini_factory(tmp_path: Path) -> Any:
    from tests.foundation_sfnd04._helpers import ini_write

    def factory(sections: dict[str, dict[str, Any]], filename: str = "config.inject.ini") -> Path:
        dest = tmp_path / filename
        ini_write(sections, dest)
        return dest

    return factory


@pytest.fixture(autouse=False)
def monkeypatch_constants_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.platform.config import loader

    monkeypatch.setattr(loader, "_REPO_ROOT", Path("/nonexistent/invalid/path"))


@pytest.fixture(autouse=False)
def yaml_enabled_override(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from app.platform.config import loader

    original = loader._YAML_ENABLED
    monkeypatch.setattr(loader, "_YAML_ENABLED", True)
    yield
    monkeypatch.setattr(loader, "_YAML_ENABLED", original)


@pytest.fixture(autouse=False)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in list(os.environ.keys()):
        if k.startswith("CRYPTO_AI_"):
            monkeypatch.delenv(k, raising=False)
