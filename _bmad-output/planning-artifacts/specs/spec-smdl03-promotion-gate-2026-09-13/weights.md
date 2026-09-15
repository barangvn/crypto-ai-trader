# S-MDL-03 Weights (version promotion-gate-default-v1, sum=1.0)

## 11 Required metrics

| metric_key | direction | default weight | rationale (source) |
|---|---|---|---|
| return_pct | HigherBetter | 0.22 | FR-038 #1 |
| max_drawdown_pct | LowerBetter | 0.20 | FR-039 DD emphasis |
| sharpe_ratio | HigherBetter | 0.15 | FR-038 risk-adjusted |
| sortino_ratio | HigherBetter | 0.12 | FR-038 downside |
| profit_factor | HigherBetter | 0.10 | FR-038 PF |
| total_fees_quote | LowerBetter | 0.10 | FR-020/022 cost aware |
| avg_slippage_bps | LowerBetter | 0.04 | FR-038 execution quality |
| trade_count | HigherBetter | 0.03 | Min sample size |
| regime_coverage_count | HigherBetter | 0.02 | FR-038 regime coverage |
| window_days | NEUTRAL_MATCH (threshold only) | 0.00 | Hard guard min window |
| oos_flag | NEUTRAL_MATCH (exact True) | 0.00 | Exact hard guard OOS |
| Σ 11 | — | **0.98** | Residual for optional extras |

When both optional extras absent: renorm 1/0.98 → Σ = 1.0.

## Optional extras (present in flat dict → consume; absent → skip NO FAIL)

| metric_key | direction | default weight | rule |
|---|---|---|---|
| stability | HigherBetter | 0.015 | OD-07 optional |
| fees_per_trade | LowerBetter | 0.005 | OD-08 optional rel cost |

## Weight validation rules (CAP-9)

1. 11 required keys present → else WEIGHT_MISSING_REQUIRED.
2. 0.0 ≤ w ≤ 1.0 each → WEIGHT_OUT_OF_RANGE.
3. Sum after renorm ∈ [0.99999999, 1.00000001] → WEIGHT_SUM_INVALID otherwise.
4. Unknown key → WEIGHT_UNKNOWN_KEY.
5. Negative weight → WEIGHT_OUT_OF_RANGE immediately.
