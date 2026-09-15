# S-MDL-03 Thresholds (version gate-thresholds-default-v1; source-backed PRD FR-038/039/LIFECYCLE T3-T4)

Split: A) CAP-3 Hard independent block, B) soft per-metric, C) meta global gate.

## A. Hard independent blocks (any fail → gate=False regardless weighted_total)

| Constraint | Threshold | Direction | Fail code | Source |
|---|---|---|---|---|
| return_delta (challenger − champion) | > 0 | min | HARD_RETURN_NOT_POSITIVE | FR-039 |
| max_drawdown_delta (worse challenger) | < 0 (worsened) | min | HARD_DRAWDOWN_WORSENED | FR-039 |
| challenger sharpe | ≥ 0.0 | min | HARD_SHARPE_NEGATIVE | PRD §5.6 |
| challenger profit_factor | ≥ 1.0 | min | HARD_PROFIT_FACTOR_SUBUNITY | FR-039 |
| challenger trade_count | ≥ 30 default | min | HARD_TRADE_COUNT_INSUFFICIENT | AC-06 min sample |
| challenger oos_flag | exact True | exact | HARD_OOS_FLAG_FALSE | AC-06 mandatory OOS |

## B. Per-metric soft thresholds (fail → reason THRESHOLD_<KEY>_FAIL)

| metric_key | norm bounds (lo, hi) | pass threshold | source |
|---|---|---|---|
| return_pct | -0.05 → +0.50 | ≥ 0.01 (1%) | FR-038 |
| max_drawdown_pct | 0 → 0.50 | ≤ 0.25 (25%) | FR-039 |
| sharpe_ratio | 0 → 5 | ≥ 1.0 | FR-038 |
| sortino_ratio | 0 → 5 | ≥ 1.2 | FR-038 |
| profit_factor | 0 → 5 | ≥ 1.2 | FR-038 |
| total_fees_quote | 0 → 2*champion_fees | ≤ champion × 1.10 | OD-08 default abs |
| avg_slippage_bps | 0 → 50 | ≤ 15 | FR-038 |
| trade_count | 0 → 1000 | ≥ 30 | AC-06 |
| regime_coverage_count | 0 → 10 | ≥ 3 | FR-038 |
| window_days | 0 → 730 | ≥ 90 | FR-035 |
| oos_flag | (exact) | exact True | AC-06 |

## C. Meta global gate

| condition | default | fail code | source |
|---|---|---|---|
| weighted_total_score | ≥ 0.65 (65%) | GATE_MIN_TOTAL_SCORE_UNMET | default policy |
| max_eval_age_days | 30 | EVAL_STALE | LIFECYCLE §T3 fresh eval |
| min_approval_count | 1 | GATE_MIN_APPROVALS_FAIL | LIFECYCLE §T4 min human |
| thresholds_version match | match embedded | THRESHOLDS_VERSION_MISMATCH | determinism AD-20 |
| weights_version match | match embedded | WEIGHTS_VERSION_MISMATCH | determinism |
| eval.comparable (S-MDL-02) | True | EVAL_INCOMPARABLE | LIFECYCLE §T3 |
| eval evidence SHA integrity | OK | EVIDENCE_INTEGRITY_FAIL | CAP-6 AD-5 |
| winner_hint | ≠ inconclusive_rerun | WINNER_HINT_INCONCLUSIVE_RERUN | OD-05 tie |
