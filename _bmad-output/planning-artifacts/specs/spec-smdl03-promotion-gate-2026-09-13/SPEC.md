---
story_id: S-MDL-03
title: S-MDL-03 Promotion Gate (Weighted Score + Thresholds + gate.passed)
status: spec
version: 1.0.0
baseline_commit: 9325236
created: 2026-09-13
epic: E-MDL Epic13
companions:
  - open-decisions.md
  - weights.md
  - thresholds.md
  - test-plan.md
  - hard-red.md
  - acceptance-criteria.md
  - dod.md
  - expected-file-changes.md
  - reuse-map.md
sources:
  - EPICS
  - S-CON-02C
  - PRD FR-038/039
  - S-MDL-02 SPEC + 10 OD
  - S-MDL-01 registry SPEC
  - LIFECYCLE T3/T4
  - S-BKT03 aggregate
  - app/contracts/model.py
---

# SPEC — S-MDL-03 Promotion Gate (Weighted Score + Thresholds + gate.passed)

## Why

PRD FR-038: Promotion SHALL require a documented gate with explicit thresholds across 10+ metrics (return, maxDD, Sharpe, Sortino, profit factor, stability, trade count, fees, slippage, regime performance). FR-039: High return with elevated drawdown / insufficient trades / unstable regime / degraded cost / weak OOS SHALL reject. AC-07: Challenger CANNOT replace Champion without approval record and explicit gate.passed. LIFECYCLE.md T3 Paper→Challenger PRECONDITION: winner=challenger_wins AND promotion_gate_result.pass=true. T4 Challenger→Champion PRECONDITION: min approval count + rollback prepared. S-MDL-02 produced metric deltas + non-binding winner hint but intentionally left weighted score/gate decision OPEN. This story closes those open decisions (source-backed) to produce binding PromotionGateResult and validates invariant winner=challenger_promoted ↔ gate.passed=True against S-CON-02C.

## Capabilities (13 CAP)

| ID | Intent (WHAT) | Success signal (testable) |
|---|---|---|
| CAP-1 | Calculate versioned weighted total score = Σ w_i × norm(metric_i) over 11 required metrics (plus optional extras when present). weights_version non-empty; weight sum within ±1e-8 of 1.0 after renorm. | 3 weights × 3 eval payloads × 3 bounds = 27 cases match manual 8dp exact. Bad sum → raises GateValidationError. |
| CAP-2 | Enforce 11 per-metric thresholds (return, maxDD, Sharpe, Sortino, PF, fees, slippage, trade_count, regime coverage, window, OOS flag). | 11 metrics × 2 states pass/fail = 22 scenarios → correct THRESHOLD_<KEY>_FAIL reason code emitted. |
| CAP-3 | Block on 6 independent hard constraints regardless of weighted total score. | 6 hard × 2 values = 12 scenarios: gate.passed=False even when weighted_total > min_total_score. |
| CAP-4 | Produce typed S-CON-02C PromotionGateResult(passed, reasons ASC sorted, thresholds_used_version non-empty). Reuse existing dataclass (no duplicate). | 3 sample runs → PromotionGateResult(**args) 0 error; (passed, reasons, version) 3-tuple all correct. |
| CAP-5 | Bind winner enforcing invariant: winner=challenger_promoted IFF gate.passed=True AND all hard_pass AND all threshold_pass AND weighted_total ≥ min_total_score AND winner_hint != inconclusive_rerun. If gate=False → champion_keeps or inconclusive_rerun. | 100% of test cases: winner=challenger_promoted → gate.passed=True AND inverse hold. 0 invariant violations. |
| CAP-6 | Reason codes list: deterministic ASC order; 1 code per failed threshold + 1 per failed hard constraint + staleness/incomparability; EMPTY list iff gate.passed=True. | 12 failure mixes sorted equals expected sorted. gate=True → len(reasons)=0. |
| CAP-7 | Eval staleness guard: age(eval_ts vs window_end) ≤ thresholds.max_eval_age_days. Stale → gate=False EVAL_STALE. | 2 cases (5d fresh / 90d stale vs 30d) → correct pass/reject. |
| CAP-8 | Comparability consume: eval.comparable == True required. Incomparable → gate=False EVAL_INCOMPARABLE, preserve S-MDL-02 mismatch codes. | 2 cases (OK / mismatch) → correct pass/reject, mismatch codes preserved. |
| CAP-9 | Weight definition validation: 11 required keys present, each w in [0.0, 1.0], sum within ±1e-8 of 1.0, unknown keys reject. Missing/negative/badsum/unknown → 4 reason codes 4/4 raise. | 5 invalid weight files + 1 valid → 4/4 reject + 1 pass OK. |
| CAP-10 | Min-max normalization per metric (HigherBetter: (v-lo)/(hi-lo); LowerBetter: (hi-v)/(hi-lo)), clamp [0,1], OOB flag threshold fail MINIMUM_NOT_MET / MAXIMUM_EXCEEDED. | 11 keys × 3 samples × 2 directions = 66 values manual 8dp match. |
| CAP-11 | Determinism 10x: same (eval_payload, weights_cfg, thresholds_cfg, approval_count) → 10 runs equal scores, reason_codes, gate.passed, SHA. | 3 fixtures × 10 → len(set(scores))=1, len(set(sha))=1. |
| CAP-12 | 22 fail-closed gate reason codes (WEIGHT_SUM_INVALID, WEIGHT_OUT_OF_RANGE, WEIGHT_MISSING_REQUIRED, WEIGHT_UNKNOWN_KEY, NORM_BOUNDS_INVALID, NORM_METRIC_MISSING, THRESHOLD_<KEY>_FAIL×11, HARD_<KEY>_BLOCK×6, HARD_DELTA_SIGN_INSUFFICIENT, EVAL_STALE, EVAL_INCOMPARABLE, EVIDENCE_INTEGRITY_FAIL, EVIDENCE_DELTAS_INSUFFICIENT, WINNER_HINT_INCONCLUSIVE_RERUN, THRESHOLDS_VERSION_MISMATCH, WEIGHTS_VERSION_MISMATCH, GATE_MIN_APPROVALS_FAIL, GATE_MIN_TOTAL_SCORE_UNMET). | 22 scenarios parametrized → each reason produced exact once. |
| CAP-13 | Approval minimum READ: challenger.approval_refs count ≥ thresholds.min_approval_count (default 1 per LIFECYCLE T4). ONLY pointer-read. Short → gate=False GATE_MIN_APPROVALS_FAIL. | 0/1/2 approvals vs min=1 → FAIL/PASS/PASS. |

## Constraints (C1..C10)

C1. Hard-red 0 diff (14 paths). C2. 0 deps stdlib only. C3. Registry READONLY (0 CRUD mutation). C4. PromotionGateResult reuse S-CON-02C; new duplicate class forbidden. C5. S-MDL-02 payload consumed only. No re-evaluation/PnL/DD/cost recalc. C6. Numeric Decimal 1e-8 ROUND_HALF_EVEN (inherit S-BKT-03). C7. to_sorted_dict sort_keys ASC separators (',',':'). C8. Fail-closed on any invalid → gate=False or GateValidationError; NONE silent pass. C9. Safety v1 (0 net/cred/DB/short/lev>1/ML). C10. Invariant winner=challenger_promoted ↔ gate.passed=True enforced POST (GateInvariantError if broken).

## Non-Goals (NG1..11)

NG1 ❌ registry request_transition status mutation (S-MDL-04/05). NG2 ❌ rollback/predecessor restore (S-MDL-04). NG3 ❌ CAP-5 FSM write validation. NG4 ❌ new metric compute. NG5 ❌ new cost/fill models. NG6 ❌ regime/features/strategy/score recalc. NG7 ❌ contract version bump. NG8 ❌ live trading/credentials. NG9 ❌ approval object creation or approval_refs append (READ only). NG10 ❌ EventBus publish. NG11 ❌ any registry/storage write.

## Success Signal

S1: pytest tests/gate/ ≥ 240 PASS / 0 FAIL / 0 SKIP. S2: regression tests/evaluation 244, tests/registry 162, SBKT01 222, SBKT03 332 unchanged, FAIL=0. S3: invariant 100%. S4: 22/22 reason codes exact. S5: 27/27 weighted exact. S6: 3 fixtures×10 SHA len(set)=1. S7: AST 30 forbidden 0 hit. S8: DoD 28/28.
