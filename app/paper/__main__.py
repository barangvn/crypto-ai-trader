"""Entry point for the offline, deterministic Paper Trading MVP.

Usage::

    python -m app.paper [--env test] [--fixture <path>]

Flow: existing test configuration -> deterministic fixture bundle ->
``BacktestRunner.run`` -> stable summary JSON printed to stdout.

Paper-only and fail-closed: the resolved configuration and the execution
limits snapshot must both prove ``max_leverage == 1``, ``allow_short == False``
and ``allow_futures == False``. Otherwise the command exits non-zero without
running the pipeline. No live exchange connectivity, no external services,
no credentials.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from app.backtest import BacktestRunner
from app.backtest.pipeline import _make_limits_snapshot
from app.backtest.run_metadata import BacktestAssumptions
from app.paper.fixture_bundle import FixtureBundle
from app.paper.summary import build_summary, render_summary_json
from app.platform.config import ConfigFactory


DEFAULT_ENV: str = "test"
DEFAULT_FIXTURE_NAME: str = "small_3sym_1h_1m_candles.csv"
FIXTURE_DIR_NAME: str = "tests_fixtures"

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]


class PaperOnlyViolation(RuntimeError):
    """Raised (fail-closed) when paper-only constraints cannot be established."""


def default_fixture_path() -> Path:
    return _REPO_ROOT / FIXTURE_DIR_NAME / DEFAULT_FIXTURE_NAME


def _check(condition: bool, message: str, violations: list[str]) -> None:
    if not condition:
        violations.append(message)


def enforce_paper_only(config: Any) -> dict[str, Any]:
    """Verify configuration and execution limits enforce paper-only trading.

    Raises ``PaperOnlyViolation`` (fail-closed) on any violation.
    """
    safety = config.safety
    limits = _make_limits_snapshot()
    violations: list[str] = []

    _check(
        isinstance(safety.max_leverage_allowed, int)
        and not isinstance(safety.max_leverage_allowed, bool)
        and safety.max_leverage_allowed <= 1,
        f"config max_leverage_allowed={safety.max_leverage_allowed!r} exceeds 1",
        violations,
    )
    _check(safety.allow_short is False, "config allow_short is not False", violations)
    _check(
        safety.allow_api_keys is False,
        "config allow_api_keys is not False",
        violations,
    )
    _check(
        safety.trading_permission_default is False,
        "config trading_permission_default is not False",
        violations,
    )
    _check(
        config.run_mode_default in ("replay", "paper"),
        f"run_mode_default={config.run_mode_default!r} is not replay/paper",
        violations,
    )
    # LimitsSnapshot encodes the v1 hard boundary (no leverage / no futures /
    # no short) as max_leverage_allowed == 1; it has no allow_short /
    # allow_futures fields.
    _check(
        limits.max_leverage_allowed == 1,
        f"execution limits max_leverage_allowed={limits.max_leverage_allowed!r} != 1",
        violations,
    )

    if violations:
        raise PaperOnlyViolation("; ".join(violations))

    no_leverage = limits.max_leverage_allowed == 1
    return {
        "allow_api_keys": safety.allow_api_keys,
        "allow_futures": not no_leverage,
        "allow_short": safety.allow_short or not no_leverage,
        "max_leverage": str(limits.max_leverage_allowed),
        "run_mode_default": config.run_mode_default,
        "trading_permission_default": safety.trading_permission_default,
    }


def build_paper_summary(
    *,
    env: str | None = None,
    fixture_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the deterministic paper pipeline and return the stable summary."""
    env_name = env or os.environ.get("CRYPTO_AI_ENV", DEFAULT_ENV)
    config = ConfigFactory.read_env(env_name)
    paper_only = enforce_paper_only(config)

    path = Path(fixture_path) if fixture_path is not None else default_fixture_path()
    bundle = FixtureBundle(path)
    runner = BacktestRunner(assumptions=BacktestAssumptions())
    result = runner.run(bundle)
    return build_summary(result, bundle=bundle, config=config, paper_only=paper_only)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.paper",
        description="Offline, deterministic, paper-only Paper Trading MVP run.",
    )
    parser.add_argument(
        "--env",
        default=None,
        help=f"configuration environment (default: {DEFAULT_ENV!r} or CRYPTO_AI_ENV)",
    )
    parser.add_argument(
        "--fixture",
        default=None,
        help="path to the CSV fixture (default: repository 1m 3-symbol fixture)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        summary = build_paper_summary(env=args.env, fixture_path=args.fixture)
    except Exception as exc:  # noqa: BLE001 - fail-closed, non-zero exit
        sys.stderr.write(
            f"app.paper FAILED (fail-closed): {type(exc).__name__}: {exc}\n"
        )
        return 1
    sys.stdout.write(render_summary_json(summary) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
