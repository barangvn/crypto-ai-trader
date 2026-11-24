"""Paper Trading MVP — end-to-end pipeline acceptance tests.

Covers AC-01 (single-command execution), AC-03 (network/credential isolation),
AC-04 (paper-only enforcement) and AC-05 (stable summary).

All in-process tests run under the repository session-level
``offline_network_blocker`` conftest fixture, so any attempted outbound network
access fails the test.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from app.backtest.pipeline import _make_limits_snapshot
from app.paper.__main__ import (
    PaperOnlyViolation,
    build_paper_summary,
    enforce_paper_only,
    main,
)
from app.paper.fixture_bundle import FixtureBundle, FixtureBundleError
from app.paper.summary import SUMMARY_SCHEMA_VERSION, render_summary_json
from app.platform.config import AppConfig, ConfigFactory, EnvSafetyLocks, PlatformContractSection


REPO_ROOT: Path = Path(__file__).resolve().parents[2]
FIXTURE_PATH: Path = REPO_ROOT / "tests_fixtures" / "small_3sym_1h_1m_candles.csv"

EXPECTED_ROWS = 180
EXPECTED_SYMBOLS = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]


# --------------------------------------------------------------------------- AC-01
class TestAC01SingleCommandExecution:
    def test_ac01_subprocess_python_m_app_paper(self) -> None:
        env = dict(os.environ)
        env["CRYPTO_AI_ENV"] = "test"
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        proc = subprocess.run(
            [sys.executable, "-m", "app.paper"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
        )

        assert proc.returncode == 0, proc.stderr
        summary = json.loads(proc.stdout)
        assert summary["artifact_schema_version"] == SUMMARY_SCHEMA_VERSION
        assert len(summary["result_sha256"]) == 64
        assert summary["counts"]["market_events"] == EXPECTED_ROWS
        assert summary["failure_reason_codes"] == []

    def test_ac01_in_process_entrypoint(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["--env", "test", "--fixture", str(FIXTURE_PATH)])
        out = capsys.readouterr().out
        assert rc == 0
        summary = json.loads(out)
        assert summary["artifact_schema_version"] == SUMMARY_SCHEMA_VERSION
        assert summary["bundle"]["symbols"] == EXPECTED_SYMBOLS
        assert summary["bundle"]["timeframe"] == "1m"


# --------------------------------------------------------------------------- AC-03
class TestAC03NetworkAndCredentialIsolation:
    def test_ac03_offline_network_blocker_is_active(self) -> None:
        with pytest.raises(RuntimeError):
            socket.create_connection(("example.com", 80), timeout=1)

    def test_ac03_run_succeeds_without_credentials(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # No API key / exchange credential is configured or required.
        config = ConfigFactory.read_env("test")
        assert config.safety.allow_api_keys is False
        rc = main(["--env", "test"])
        capsys.readouterr()
        assert rc == 0


# --------------------------------------------------------------------------- AC-04
class TestAC04PaperOnly:
    def test_ac04_runtime_config_is_paper_only(self) -> None:
        config = ConfigFactory.read_env("test")
        assert config.safety.max_leverage_allowed == 1
        assert config.safety.allow_short is False
        assert config.safety.allow_api_keys is False
        assert config.run_mode_default in ("replay", "paper")
        # enforce_paper_only must not raise for the real configuration.
        block = enforce_paper_only(config)
        assert block["max_leverage"] == "1"
        assert block["allow_short"] is False
        assert block["allow_futures"] is False

    def test_ac04_execution_path_limits_are_paper_only(self) -> None:
        limits = _make_limits_snapshot()
        # LimitsSnapshot encodes the v1 paper-only boundary as max_leverage_allowed == 1
        # (no leverage / no futures / no short); it has no allow_short/allow_futures fields.
        assert limits.max_leverage_allowed == 1
        assert isinstance(limits.max_leverage_allowed, int)
        block = enforce_paper_only(ConfigFactory.read_env("test"))
        assert block["max_leverage"] == "1"
        assert block["allow_futures"] is False

    def test_ac04_no_live_execution_path_in_summary(self) -> None:
        summary = build_paper_summary(env="test", fixture_path=FIXTURE_PATH)
        assert summary["run"]["source_type"] == "replay"
        assert summary["paper_only"]["allow_futures"] is False
        assert summary["paper_only"]["max_leverage"] == "1"

    def test_ac04_fail_closed_on_violating_config(self) -> None:
        bad = AppConfig(
            env_name="test",
            db_namespace="bad",
            artifact_path="bad",
            run_mode_default="replay",
            safety=EnvSafetyLocks(
                allow_short=True,
                allow_api_keys=True,
                max_leverage_allowed=3,
            ),
            observability=None,
            platform_contract=PlatformContractSection(),
        )
        with pytest.raises(PaperOnlyViolation):
            enforce_paper_only(bad)


# --------------------------------------------------------------------------- AC-05
class TestAC05StableSummary:
    def test_ac05_keys_sorted_recursively(self) -> None:
        summary = build_paper_summary(env="test", fixture_path=FIXTURE_PATH)
        parsed = json.loads(render_summary_json(summary))
        assert list(parsed.keys()) == sorted(parsed.keys())
        assert list(parsed["run"].keys()) == sorted(parsed["run"].keys())
        assert list(parsed["bundle"].keys()) == sorted(parsed["bundle"].keys())
        assert list(parsed["config"].keys()) == sorted(parsed["config"].keys())
        assert list(parsed["paper_only"].keys()) == sorted(parsed["paper_only"].keys())

    def test_ac05_no_secret_values_in_output(self) -> None:
        summary = build_paper_summary(env="test", fixture_path=FIXTURE_PATH)
        rendered = render_summary_json(summary)
        # ``allow_api_keys`` is the boolean safety-lock *flag* (AC-04 evidence), not a
        # credential value. It is the sole permitted occurrence of the "api_key"
        # substring; neutralise exactly that one key token before scanning so any
        # other occurrence (key or value) still fails the assertion below.
        assert rendered.count("allow_api_keys") == 1
        lowered = rendered.replace("allow_api_keys", "SAFETY_LOCK_FLAG").lower()
        for needle in (
            "api_key",
            "apikey",
            "secret",
            "password",
            "passphrase",
            "private_key",
            "mnemonic",
        ):
            assert needle not in lowered

    def test_ac05_identical_input_gives_identical_summary(self) -> None:
        first = build_paper_summary(env="test", fixture_path=FIXTURE_PATH)
        second = build_paper_summary(env="test", fixture_path=FIXTURE_PATH)
        assert render_summary_json(first) == render_summary_json(second)


# ----------------------------------------------------------- fixture bundle contract
class TestFixtureBundleContract:
    def test_bundle_contract_surface(self) -> None:
        bundle = FixtureBundle(FIXTURE_PATH)
        assert bundle.bundle_id == "small_3sym_1h_1m_candles"
        assert bundle.bundle_version == "1.0.0"
        assert bundle.timeframe == "1m"
        assert list(bundle.symbols) == EXPECTED_SYMBOLS
        assert len(bundle.compute_sha256()) == 64

    def test_iter_events_yields_candles_with_runner_attributes(self) -> None:
        from app.contracts import Candle

        bundle = FixtureBundle(FIXTURE_PATH)
        events = list(bundle.iter_events())
        assert len(events) == EXPECTED_ROWS
        for event in events:
            assert isinstance(event, Candle)
            assert event.symbol in EXPECTED_SYMBOLS
            assert event.event_ts
            assert event.candle_id
            assert event.closed is True
            assert event.close > 0

    def test_event_order_is_stable(self) -> None:
        first = [(e.event_ts, e.symbol, e.candle_id) for e in FixtureBundle(FIXTURE_PATH).iter_events()]
        second = [(e.event_ts, e.symbol, e.candle_id) for e in FixtureBundle(FIXTURE_PATH).iter_events()]
        assert first == second
        assert first == sorted(first)

    def test_rejects_unsupported_event_type(self, tmp_path: Path) -> None:
        bad = tmp_path / "unsupported.csv"
        bad.write_text(
            "raw_symbol,raw_timestamp,open,high,low,close,volume,event_type,timeframe\n"
            "BTCUSDT,2026-08-10 10:00:00,1,2,1,2,1,trade,1m\n",
            encoding="utf-8",
        )
        with pytest.raises(FixtureBundleError):
            FixtureBundle(bad)

    def test_rejects_malformed_numeric_row(self, tmp_path: Path) -> None:
        bad = tmp_path / "malformed.csv"
        bad.write_text(
            "raw_symbol,raw_timestamp,open,high,low,close,volume,event_type,timeframe\n"
            "BTCUSDT,2026-08-10 10:00:00,not-a-number,2,1,2,1,candle,1m\n",
            encoding="utf-8",
        )
        with pytest.raises(FixtureBundleError):
            FixtureBundle(bad)
