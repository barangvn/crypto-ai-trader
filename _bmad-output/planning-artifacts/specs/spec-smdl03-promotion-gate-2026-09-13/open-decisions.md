# S-MDL-03 Open Decisions (from S-MDL-02 10 ODs — resolved/open per source)

| # | Decision | Status | Source-backed rationale |
|---|---|---|---|
| OD-01 | Weighted composite total score | **RESOLVED** | weighted_total = Σ w_i × normalize(metric_i) 11 required keys; optional extras renorm present weights to 1.0; versioned weights.thresholds_weights_version. |
| OD-02 | Cross-metric scale normalization | **RESOLVED** | Min-max per metric using explicit bounds in thresholds_config.metric_bounds[key]={lo,hi}. Direction from S-MDL-02 table; clamp [0,1] with threshold flag OOB. |
| OD-03 | Missing metric fail behavior | **RESOLVED inherited + amplified** | Inherited ERR_MISSING_METRIC → gate reason NORM_METRIC_MISSING → gate.passed=False. |
| OD-04 | Incomparable eval output mode | **RESOLVED inherited + amplified** | S-MDL-02 raises CompareValidationError → gate catches → reason EVAL_INCOMPARABLE; gate=False. |
| OD-05 | Ties default winner hint | **RESOLVED** | 6 critical deltas tie or winner_hint=inconclusive_rerun → WINNER_HINT_INCONCLUSIVE_RERUN reason; gate=False; winner=inconclusive_rerun; champion keeps. |
| OD-06 | Numeric rounding precision | **RESOLVED inherited** | Decimal 1e-8 ROUND_HALF_EVEN, Float 8dp, int/bool exact (S-BKT-03 C6). |
| OD-07 | Stability metric inclusion/weight | **RESOLVED (optional presence)** | Present → extra weight w_stability=0.015 default; renorm. Absent → SKIP (not missing; no fail). Direction HigherBetter. |
| OD-08 | Cost normalization abs vs rel | **RESOLVED defaults + optional** | Required total_fees_quote LowerBetter w=0.10 (absolute default). Optional extra fees_per_trade when artifact present w=0.005 LowerBetter; ignored when missing. |
| OD-09 | Fold weighting inside aggregates | **REMAINS OPEN (upstream used as-is)** | Continue consume S-BKT03 pre-computed compound Π(1+r_i)-1 and 1/N mean Sharpe/Sortino/PF. No new fold algorithm in S-MDL-03. |
| OD-10 | Symbol universe multi-symbol weighting | **REMAINS OPEN (upstream used as-is)** | Consume upstream pre-weighted aggregates only. S-MDL-03 NEVER symbol-re-weights. |

RESOLVED: 8 (OD-01/02/03/04/05/06/07/08)
REMAINS OPEN: 2 (OD-09, OD-10)
