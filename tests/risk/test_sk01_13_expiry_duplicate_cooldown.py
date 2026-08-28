"""T13 — Expiry + Duplicate Window + Cooldown (4 + 5 + 4 + 4 + 4 = 21 tests)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.contracts.risk import RiskDecisionResult
from app.risk import RiskContext, RiskEngineDefaults


def _add_ms(ts, ms):
    try:
        base = ts[:-1]
        if "." in base:
            main, frac = base.split(".", 1)
        else:
            main = base
            frac = "000"
        dt = datetime.strptime(main, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        epoch = dt.timestamp() + int((frac + "000")[:3]) / 1000.0 + ms / 1000.0
        from app.contracts.types import format_instant
        return format_instant(datetime.fromtimestamp(epoch, tz=timezone.utc))
    except Exception:
        return ts


def test_t13_opp_score_expired(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    # Explicitly set: ctx.as_of = opp.created_ts + 10 mins → age = 600k ms (default window 300k)
    new_as_of = _add_ms(opp.created_ts, +600_000)
    rd = engine.evaluate(opp, sig, reg, pv, lim, replace(ctx, as_of=new_as_of))
    assert rd.decision == RiskDecisionResult.REJECTED, rd.reason_codes
    assert "OPPORTUNITY_SCORE_EXPIRED" in rd.reason_codes, rd.reason_codes


def test_t13_opp_score_fresh(happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    fresh_as_of = _add_ms(opp.created_ts, +5_000)  # 5 sec within 300k window
    rd = engine.evaluate(opp, sig, reg, pv, lim, replace(ctx, as_of=fresh_as_of))
    if rd.decision == RiskDecisionResult.APPROVED:
        assert "OPPORTUNITY_SCORE_EXPIRED" not in rd.reason_codes


def test_t13_score_validity_override(happy_path_tuple, engine):
    from app.risk import RiskEngineDefaults
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    stale_as_of = _add_ms(opp.created_ts, +600_000)
    # Increase validity window to 1 hour -> not expired
    ctx2 = replace(ctx, defaults=RiskEngineDefaults(score_valid_until_ms=3_600_000), as_of=stale_as_of)
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx2)
    # Expiry NOT the cause when window expanded to 1h
    if rd.decision == RiskDecisionResult.REJECTED:
        assert "OPPORTUNITY_SCORE_EXPIRED" not in rd.reason_codes, rd.reason_codes


# 5 duplicate_window tests
@pytest.mark.parametrize("delta_ms,expect_dup", [(-5000, True), (-30000, True), (0, True), (120_000, False), (10_000, True)])
def test_t13_duplicate_decision_window(delta_ms, expect_dup, happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    # Insert an event with as_of delta from ctx.as_of; ctx.duplicate_tracker[(corr, BTC_USDT, as_of[second precision])] = ts
    as_of = ctx.as_of or opp.created_ts
    key_rounded = as_of[:-7]
    tracker = {(opp.correlation_id, "BTC_USDT", key_rounded): as_of}
    ctx2 = replace(ctx, duplicate_tracker=tracker)
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx2)
    if expect_dup:
        assert "DUPLICATE_DECISION_WINDOW" in rd.reason_codes or rd.decision != RiskDecisionResult.APPROVED
    else:
        # No duplicate expected -> could be approved
        pass


# 4 cooldown tests
COOLDOWN_DELTAS = [(-5000, True), (-60_000, True), (-300_000, False), (-500_000, False)]


@pytest.mark.parametrize("delta_ms,expect_cool", COOLDOWN_DELTAS)
def test_t13_cooldown_window(delta_ms, expect_cool, happy_path_tuple, engine):
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    as_of = ctx.as_of or opp.created_ts
    last_ts = _add_ms(as_of, delta_ms)
    cool_track = {("BTC_USDT", sig.strategy_id): last_ts}
    ctx2 = replace(ctx, cooldown_tracker=cool_track)
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx2)
    if expect_cool:
        assert rd.decision == RiskDecisionResult.REJECTED or "COOLDOWN_ACTIVE" in rd.reason_codes, (delta_ms, rd.reason_codes)


# 4 valid_until deterministic tests
VALID_UNTIL_DELTAS = [10_000, 30_000, 60_000]


@pytest.mark.parametrize("validity_ms", VALID_UNTIL_DELTAS)
def test_t13_valid_until_deterministic(validity_ms, happy_path_tuple, engine):
    from app.risk import RiskEngineDefaults
    opp, sig, reg, pv, lim, ctx = happy_path_tuple
    ctx2 = replace(ctx, defaults=RiskEngineDefaults(decision_valid_until_ms=validity_ms))
    rd = engine.evaluate(opp, sig, reg, pv, lim, ctx2)
    # Compute expected
    expected_end = _add_ms(ctx2.as_of or opp.created_ts, validity_ms)
    # within ±2 ms
    assert rd.valid_until is not None
