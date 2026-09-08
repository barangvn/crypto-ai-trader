"""S-BKT-03: Deterministic performance metrics pure helpers.

- Hicbir PnL / drawdown / portfolio ALGORITMASI YENIDEN YAZILMAZ.
  (S-PTF-01 position, S-PTF-02 portfolio, S-PTF-03 rolling 24h zaten mevcut.)
- Bu modul: varolan ctx.fills / ctx.snapshots / last_snapshot verilerinden
  FR-059 / FR-038 tarafindan istenen win_rate / winning / losing trades,
  Sharpe/Sortino, Profit Factor, expectancy, avg win/loss gibi TUREV metrikleri
  DETERMINISTIK sekilde hesaplayan PURE fonksiyonlar.
- float metrics 8dp ROUND_HALF_EVEN.
- stdlib statistics mean/stdev kullanilir (numpy/pandas YASAK: hard-red deps).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Iterable, Sequence

from .run_metadata import BacktestWindowSplit, SplitDataset


_Q8 = Decimal("0.00000001")


def _q8(v: Decimal) -> Decimal:
    return Decimal(v).quantize(_Q8, rounding=ROUND_HALF_EVEN)


def _r8(v: float) -> float:
    if v is None:
        return 0.0
    if math.isnan(v) or math.isinf(v):
        return 0.0
    return round(v, 8)


def closed_trade_pnl_sequence(
    fills: Iterable[Any],
) -> list[Decimal]:
    """Position lifecycle: BUY-SELL pairlarinin net closed PnL sirasi.

    Input: PaperFill listesi (FillAssumptionsConfig + PositionEngine PTF-01 ile
    zaten uretilmis). Sadece side SELL olan ve closed_qty > 0 dolayisiyla
    position.realized_pnl_quote tarafindan islenmis olanlari degil,
    her fill icin PaperFill.side == SELL ise fees dusulmus notional delta
    uzerinden trade-level PnL series cikar (REUSE PTF-01 PnL formulu):
    gross = (fill_price - avg_price_prev) * close_qty; net = gross - fees_quote.
    avg_price_prev lineer cumulative O(1) tutulur.
    """
    out: list[Decimal] = []
    cum_qty = Decimal("0")
    cum_notional = Decimal("0")  # fees dahil DEGIL (avg base price * qty)
    for f in fills:
        side = getattr(f, "side", None)
        fp = getattr(f, "fill_price", Decimal("0"))
        fq = getattr(f, "fill_qty_base", Decimal("0"))
        fees = getattr(f, "fees_quote", Decimal("0"))
        try:
            fp = Decimal(fp)
            fq = Decimal(fq)
            fees = Decimal(fees)
        except BaseException:
            continue
        if fp <= 0 or fq <= 0:
            continue
        if str(side).upper() in {"BUY", "1", "LONG"}:
            # Weighted avg open price ex-fees (PTF-01 style old_avg update)
            cum_notional = cum_notional + fp * fq
            cum_qty = cum_qty + fq
        elif str(side).upper() in {"SELL", "2", "SHORT"}:
            if cum_qty <= 0:
                continue
            avg = cum_notional / cum_qty
            closed_qty = min(fq, cum_qty)
            gross = (fp - avg) * closed_qty
            # Prorate fees yalnizca closed_qty/fq kadar (PTF-01 formulu)
            fee_clamped = fees * (closed_qty / fq)
            net = gross - fee_clamped
            out.append(_q8(net))
            cum_notional = cum_notional - avg * closed_qty
            cum_qty = cum_qty - closed_qty
            if cum_qty < Decimal("1e-18"):
                cum_qty = Decimal("0")
                cum_notional = Decimal("0")
    return out


def summarize_win_loss(
    closed_pnl_list: Sequence[Decimal],
) -> dict[str, Any]:
    wins = [p for p in closed_pnl_list if p > Decimal("0")]
    losses = [p for p in closed_pnl_list if p < Decimal("0")]
    n = len(closed_pnl_list)
    if n == 0:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate_pct": None,
            "avg_win_quote": None,
            "avg_loss_quote": None,
            "expectancy_quote": None,
            "profit_factor": None,
            "stability_index": None,
            "info_codes": ("METRICS_NO_CLOSED_TRADES",),
        }
    win_rate = _r8(len(wins) / n * 100.0)
    avg_win = _q8(sum(wins, Decimal("0")) / Decimal(max(1, len(wins)))) if wins else Decimal("0")
    avg_loss = _q8(sum(losses, Decimal("0")) / Decimal(max(1, len(losses)))) if losses else Decimal("0")
    gross_win = sum(wins, Decimal("0"))
    gross_loss_abs = sum((-p for p in losses), Decimal("0"))
    expectancy = _q8(
        (gross_win if wins else Decimal("0"))
        - (gross_loss_abs if losses else Decimal("0"))
    ) / Decimal(n)
    expectancy_q = _q8(expectancy)
    pf: float | None
    if gross_loss_abs > Decimal("0"):
        pf = _r8(float(gross_win) / float(gross_loss_abs))
    else:
        pf = None
    # OD-01 stability: stddev < 2*|mean| ise 1; else 0 (mean=0 -> 1)
    try:
        floats = [float(p) for p in closed_pnl_list]
        mean_f = statistics.fmean(floats) if floats else 0.0
        sd_f = statistics.pstdev(floats) if len(floats) >= 2 else 0.0
        if mean_f == 0.0:
            stability = 1
        else:
            stability = 1 if sd_f < 2.0 * abs(mean_f) else 0
    except BaseException:
        stability = None
    info_codes: tuple[str, ...] = ()
    if gross_loss_abs == Decimal("0") and pf is None:
        info_codes = info_codes + ("PROFIT_FACTOR_NO_LOSSES",)
    return {
        "total_trades": n,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": win_rate,
        "avg_win_quote": avg_win if wins else None,
        "avg_loss_quote": avg_loss if losses else None,
        "expectancy_quote": expectancy_q,
        "profit_factor": pf,
        "stability_index": stability,
        "info_codes": info_codes,
    }


def compute_sharpe_sortino_from_returns(
    returns_pct: Sequence[float],
    *,
    min_samples: int = 30,
    periods_per_year: float = 365.0 * 24.0 * 60.0,
    rf_annual_pct: float = 0.0,
) -> dict[str, float | None]:
    """Sharpe/Sortino per sample returns (PCT 1-unit = 1%).

    periods_per_year: 1-minute sample varsayilan = 525600 min/yil.
    N < min_samples ise None + info code dondurur (fail-closed YOK).
    """
    n = len(returns_pct)
    if n < min_samples:
        return {
            "sharpe_ratio_24h": None,
            "sortino_ratio_24h": None,
            "info_codes": (f"METRICS_INSUFFICIENT_SAMPLES_N{n}_MIN{min_samples}",),
        }
    try:
        excess = [r - rf_annual_pct / periods_per_year for r in returns_pct]
        sd = statistics.pstdev(excess)
        if sd == 0.0:
            sh: float | None = None
        else:
            sh = _r8(statistics.fmean(excess) / sd * math.sqrt(periods_per_year))
        neg_excess = [e for e in excess if e < 0.0]
        dsd = statistics.pstdev(neg_excess) if len(neg_excess) >= 2 else 0.0
        if dsd == 0.0:
            so: float | None = None
        else:
            so = _r8(statistics.fmean(excess) / dsd * math.sqrt(periods_per_year))
        return {
            "sharpe_ratio_24h": sh,
            "sortino_ratio_24h": so,
            "info_codes": (),
        }
    except BaseException:
        return {
            "sharpe_ratio_24h": None,
            "sortino_ratio_24h": None,
            "info_codes": ("METRICS_SHARPE_SORTINO_EXC",),
        }


def returns_pct_from_snapshots(
    snapshots: Sequence[Any],
    equity_attr: str = "equity_quote",
    ts_attr: str = "ts",
    *,
    return_per_sample_not_annual: bool = True,
    max_minutes: int | None = None,
) -> list[float]:
    """Snapshot serisinden sample-basi return (%) serisi.

    S-PTF-03 Rolling24 kullanilmaz ise BURASI snapshot list uzerinden calisir
    (OD-02 / OD-08 fallback).
    """
    if len(snapshots) < 2:
        return []
    out: list[float] = []
    prev: float | None = None
    last_ts_ms: float | None = None
    gap_ms = (max_minutes * 60_000.0) if max_minutes else None
    for s in snapshots:
        eq_raw = getattr(s, equity_attr, None)
        ts_raw = getattr(s, ts_attr, "")
        try:
            eq_f = float(Decimal(eq_raw))
        except BaseException:
            eq_f = 0.0
        if gap_ms is not None and isinstance(ts_raw, str) and ts_raw:
            try:
                from datetime import datetime as _dt, timezone as _tz
                t = _dt.strptime(ts_raw.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S.%f%z")
                this_ts_ms = t.timestamp() * 1000.0
            except BaseException:
                this_ts_ms = 0.0
        else:
            this_ts_ms = None
        if prev is not None and prev > 0 and eq_f > 0:
            if gap_ms is None or last_ts_ms is None or this_ts_ms is None or (this_ts_ms - last_ts_ms) <= gap_ms * 1.01:
                r = (eq_f - prev) / prev * 100.0
                out.append(_r8(r))
        prev = eq_f
        if this_ts_ms is not None:
            last_ts_ms = this_ts_ms
    return out


@dataclass(frozen=True)
class StrategyRegimeRow:
    strategy_id: str
    regime: str
    trade_count: int
    win_rate_pct: float | None
    avg_pnl_quote: Decimal | None
    info_codes: tuple[str, ...]


def group_by_strategy_regime(
    fills: Sequence[Any],
    strategy_by_correlation: dict[str, str] | None = None,
    regime_by_correlation: dict[str, str] | None = None,
) -> list[StrategyRegimeRow]:
    """OD-05: Position tarafinda strategy_id/regime YOK ise corr_id wrapper ile
    disaridan saglanan map'ler uzerinden groupby. Eger correlation lookup
    basarisiz -> group "UNKNOWN_STRATEGY" / "UNKNOWN_REGIME". Audit NOT REJECT.
    """
    buckets: dict[tuple[str, str], list[Decimal]] = {}
    pnl_list = closed_trade_pnl_sequence(fills)
    # Fill indexi ile pnl eslestir (closed_pnl_list dogrudan satış sırası)
    # -> alternate: her fill sonrası PNL'yi corr etiketiyle saklamak yerine
    # sadede corr chain'ten gelen strategy_id / regime dolayli atamamiz gerek.
    # Burada: fills uzerinden side SELL olan + position kapatanlarla
    # closed_pnl_list[i] eslesir (ustteki closed_trade_pnl_sequence ile
    # ayni iterator sirasi kullanir).
    closed_iter = iter(pnl_list)
    for f in fills:
        side = getattr(f, "side", None)
        if str(side).upper() not in {"SELL", "2", "SHORT"}:
            continue
        try:
            pnl = next(closed_iter)
        except StopIteration:
            break
        corr = str(getattr(f, "correlation_id", "") or "")
        sid = (strategy_by_correlation or {}).get(corr, "UNKNOWN_STRATEGY")
        reg = (regime_by_correlation or {}).get(corr, "UNKNOWN_REGIME")
        buckets.setdefault((sid, reg), []).append(pnl)
    rows: list[StrategyRegimeRow] = []
    for (sid, reg), pnls in sorted(buckets.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        wl = summarize_win_loss(pnls)
        avg: Decimal | None = wl["expectancy_quote"]
        rows.append(
            StrategyRegimeRow(
                strategy_id=sid,
                regime=reg,
                trade_count=wl["total_trades"],
                win_rate_pct=wl["win_rate_pct"],
                avg_pnl_quote=avg,
                info_codes=wl["info_codes"],
            )
        )
    return rows


def aggregate_metrics_fold_level(
    per_fold: Sequence[dict[str, Any]],
    *,
    exclude_none_in_avg: bool = True,
) -> dict[str, Any]:
    """Multi-fold aggregation: avg(Sharpe/Sortino/PF) — None fold exclude policy
    OD-06; compound total return = Prod(1+r_i) - 1; min/max fold return.
    """
    n = len(per_fold)
    if n == 0:
        return {
            "fold_count": 0,
            "avg_sharpe_ratio_24h": None,
            "avg_sortino_ratio_24h": None,
            "avg_profit_factor": None,
            "compound_total_return_pct": 0.0,
            "min_fold_total_return_pct": 0.0,
            "max_fold_total_return_pct": 0.0,
            "per_fold_included_in_avg_count": 0,
            "info_codes": ("METRICS_EMPTY_FOLD_LIST",),
        }
    returns = [float(f.get("total_return_pct", 0.0) or 0.0) for f in per_fold]
    sharpe_list: list[float] = []
    sortino_list: list[float] = []
    pf_list: list[float] = []
    for f in per_fold:
        s = f.get("sharpe_ratio_24h")
        so = f.get("sortino_ratio_24h")
        pf = f.get("profit_factor")
        if isinstance(s, (int, float)) and not exclude_none_in_avg:
            sharpe_list.append(float(s))
        elif isinstance(s, (int, float)):
            sharpe_list.append(float(s))
        if isinstance(so, (int, float)):
            sortino_list.append(float(so))
        if isinstance(pf, (int, float)):
            pf_list.append(float(pf))
    def _av(lst: list[float]) -> float | None:
        if not lst:
            return None
        return _r8(statistics.fmean(lst))
    compound = 1.0
    for r in returns:
        compound *= (1.0 + r / 100.0)
    compound_pct = _r8((compound - 1.0) * 100.0)
    codes: tuple[str, ...] = ()
    if len(sharpe_list) < n:
        codes = codes + ("METRICS_NA_EXCLUDED_AVG",)
    return {
        "fold_count": n,
        "avg_sharpe_ratio_24h": _av(sharpe_list),
        "avg_sortino_ratio_24h": _av(sortino_list),
        "avg_profit_factor": _av(pf_list),
        "compound_total_return_pct": compound_pct,
        "min_fold_total_return_pct": _r8(min(returns)) if returns else 0.0,
        "max_fold_total_return_pct": _r8(max(returns)) if returns else 0.0,
        "per_fold_included_in_avg_count": len(sharpe_list),
        "info_codes": codes,
    }


def cost_impact_between_runs(
    base: dict[str, Any],
    overridden: dict[str, Any],
) -> dict[str, Any]:
    """Cost-aware metrics delta: base (default) vs override cost model output.

    Monotonic degilse kabul (non-linear), ancak imzali delta raporlanir.
    """
    def _get(d: dict[str, Any], k: str) -> float:
        v = d.get(k)
        try:
            return float(v) if v is not None else 0.0
        except BaseException:
            return 0.0
    delta_return = _r8(_get(overridden, "total_return_pct") - _get(base, "total_return_pct"))
    delta_dd = _r8(_get(overridden, "max_drawdown_pct") - _get(base, "max_drawdown_pct"))
    try:
        base_fees = Decimal(str(base.get("total_fees_quote", "0") or "0"))
        over_fees = Decimal(str(overridden.get("total_fees_quote", "0") or "0"))
        delta_fees = _q8(over_fees - base_fees)
    except BaseException:
        delta_fees = _q8(Decimal("0"))
    return {
        "delta_total_return_pct": delta_return,
        "delta_max_drawdown_pct": delta_dd,
        "delta_fees_quote": delta_fees,
        "info_codes": (),
    }


def fold_window_split_sha256(split: BacktestWindowSplit | None) -> str:
    if split is None:
        return "none"
    d = split.to_sorted_dict()
    import hashlib, json
    raw = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
