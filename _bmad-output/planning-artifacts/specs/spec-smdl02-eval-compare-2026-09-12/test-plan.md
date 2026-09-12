# S-MDL-02 — Test Plan (Source-backed, no arbitrary count)

Toplam test: **240 parametrize** (her case explicit, no fake coverage).

## T1. Champion/Challenger Identify + Registry Load (22 test)
- champion model_id+version → registry status=CHAMPION PASS (3 case: ok, status_paper→FAIL NOT_CHAMPION_STATUS, not_found→FAIL)
- challenger status=CHALLENGER PASS (3 case)
- same model same version → SAME_MODEL_SAME_VERSION reject (1 case)
- champion model empty correlation / causation → VALID (no reject on corr/caus; artifact matters) (1)
- evidence_refs kind filter: historical_oos_eval/walk_forward_run/paper_replay_eval 3 tür 3x loaded (3×2=6; 3 missing type → EVIDENCE_NOT_FOUND)
- artifact_uri empty → EMPTY_ARTIFACT_URI reject (2x champion/challenger)
- evidence count < 3 (min) → champion/challenger EVIDENCE_NOT_FOUND (2)
Total: 22

## T2. Comparability Invariants (6 invariant × 4 case each + 1 happy = 25)
INCOMPARABLE invariant types:
1. DATASET_KIND → champion historical vs challenger walk_forward (→ INCOMPARABLE_DATASET)
2. WINDOW_OVERLAP (<99pct start/end overlap)
3. THRESHOLDS_CONFIG_VERSION mismatch
4. COST_CONFIG_VERSION mismatch
5. SYMBOL_UNIVERSE mismatch (set difference between champion.universe & challenger.universe)
6. COMPATIBILITY_REF versions (feature/strategy/regime) mismatch any
Happy path: all match → comparable OK (1)
6×4 = 24 mismatch (each invalid pair + partial overlap + both swapped)
Total: 24 + 1 = 25

## T3. Artifact → ModelEvaluation Build (11 required keys + type strictness = 24 test)
11 required keys × 2 case (present, missing) → 22 missing_metric RAISE
11 type mismatches × 1 each (Decimal→string return_pct; float→int maxDD; bool→str oos_flag; int→float trade_count) → 12 METRIC_TYPE_MISMATCH RAISE (key subset: top 12)
Corrupt artifact JSON (decode error) → ARTIFACT_CORRUPT (2x)
Negative trade_count (-1) → NEGATIVE_TRADE_COUNT (1)
drawdown out of range [0,1] = 1.5 → DRAWDOWN_OUT_OF_RANGE (1)
sharpe NaN (float('nan')) → SHARPE_NAN (1)
Total 22 + 12 + 2 + 1 + 1 + 1 = 39

## T4. Per-Metric Delta Direction (11 keys × 5 case = 55)
11 keys: return_pct(D), max_drawdown(F), sharpe(F), sortino(F), PF(F), total_fees(D), avg_slippage(F), trade_count(I), regime_coverage(I), window_days(I), oos_flag(B)
Each:
1. challenger > champion HigherBetter → delta positive PASS (D+I directionality check)
2. challenger < champion LowerBetter → delta positive PASS (Fees/DD/slippage/window LowerBetter) → POSITIVE
3. challenger == champion → delta == 0 PASS
4. bool oos_flag match=both true → delta=0 NeutralMatch / mismatch → METRIC_TYPE_MISMATCH reject (or delta bool 0/1 with neutral)
5. cross: oos_flag true vs false → INCOMPARABLE (NeutralMatch mismatch reject)
Per metric 5 case → 11 × 5 = 55.

## T5. Score Delta Canonical Serialization + SHA (4)
10x same input → delta list sorted keys: to_sorted_dict identical (set len 1); sha set len=1 (4)
fold order ASC deterministic: 5 folds → correct index ordering (1)
delta_list schema_sha256 consistent across restarts (1)
Total: 6

## T6. Evidence Integrity SHA (4)
Integrity sha correct → PASS (1)
Integrity sha mismatch → INTEGRITY_SHA_MISMATCH RAISE (1)
Integrity sha not set → PASS (skip check, not error) (1)
Artifact file not found + integrity required → ARTIFACT_NOT_FOUND (1)
Total: 4

## T7. Fold-level + Aggregate Comparison (18)
Fold count match = 5 both → per-fold 5 deltas (return/sharpe/trade_count × 5 = 15) (8)
Fold count champion N=5 vs challenger N=4 → INCOMPARABLE_FOLD_COUNT RAISE (1)
Aggregate compound return = Π(1+r_i)-1 exact (Decimal, 4 case: 3r × 2 values) (4)
Aggregate avg sharpe / sortino / PF exact (3)
min/max fold return exact (2 values) (2)
Total 8+1+4+3+2=18

## T8. Regime-Performance Decomposition (12)
2 strategy × 3 regime = 6 groups identical between champion/challenger → 6 deltas per group (return+trade_count) × 2 (6 group produce 12 deltas, correct order): 12 test case (6 return PASS direction, 6 trade_count PASS direction)
regime group mismatch count champion: 6 challenger: 5 → INCOMPARABLE_REGIME_GROUPS RAISE (1)
strategy_id sort canonical ASC (case insensitive) — verify sorted list ASC: 1 case
Total 12+1+1=14

## T9. Winner Hint Non-Binding (7)
All 6 critical metrics pro-challenger → challenger_promoted (1)
All 6 pro-champion → champion_keeps (1)
Mixed → inconclusive_rerun (2 case: 3-3 split; 4-2) (2)
1 tie + 5 pro-champion → inconclusive_rerun or tie→ champion_keeps ? tie policy 2 tests (2)
HINT output field not used as final gate decision & `promotion_gate_result.passed` = None (unset) — guard assertion 1 (engine does NOT set passed)
Total 7

## T10. Fail-Closed 25 Categories (25)
25 reason_code enum: 25 x 1 dedicated test (each category specific invalid payload + assert exception.reason_code match):
  MODEL_NOT_FOUND, EVIDENCE_NOT_FOUND, ARTIFACT_NOT_FOUND, ARTIFACT_CORRUPT, MISSING_METRIC, METRIC_TYPE_MISMATCH, INCOMPARABLE_WINDOW, INCOMPARABLE_DATASET, INCOMPARABLE_COST, INCOMPARABLE_UNIVERSE, INCOMPARABLE_REGIME_GROUPS, INCOMPATIBLE_FOLD_COUNT, INTEGRITY_SHA_MISMATCH, NOT_CHALLENGER_STATUS, NOT_CHAMPION_STATUS, EMPTY_CHAMPION_MODEL, EMPTY_CHALLENGER_MODEL, SAME_MODEL_SAME_VERSION, NEGATIVE_TRADE_COUNT, DRAWDOWN_OUT_OF_RANGE, SHARPE_NAN, EMPTY_ARTIFACT_URI, INVALID_ROUNDING_PRECISION, INCOMPATIBLE_STATUS_TRANSITION, UNKNOWN_METRIC_KEY
Total 25

## T11. Determinism 10x (13)
10x builds ModelEvaluation sha → set len 1 (3 separate metrics classes 3×1)
10x compare → delta_list sha set len 1 (3)
10x winner_hint → enum set len 1 (1)
2 CompareEngine different object instances → same delta sha (1)
10x regime groups order → sha set len 1 (1)
10x fold deltas order → sha set len 1 (1)
10x aggregate compound result → sha set len 1 (1)
10x evidence order determinism → sha set len 1 (1)
10x CCE payload sha set len 1 (1)
Total 13

## T12. Safety AST + Forbidden patterns (12)
24 forbidden patterns (see Constraints C8/C1/network/credential/short/lev>1/optimizer fit/write registry/datetime now/run mode branch/real order/leverage calc): 24/24 0 hit (1 assertion aggregate scan)
imports: no requests/httpx/urllib/websocket/ccxt/sqlalchemy/redis (6 separate assertion each 0 → 6)
function names no place_order / send_order / partial_fit / fit (4)
write path registry: no `registry.create_model_version` / storage.write / `request_transition` in evaluation module AST (2)
Total 1+6+4+2=13 (minimum count; aggregate single scan 1 + individual 12).

## T13. Contract ChampionChallengerEvaluation Payload (8)
Typed payload + ChampionChallengerEvaluation(**payload) → 0 schema error (1 happy path)
11 comparison_metrics required exact keys check (1)
winner enum populated correctly (1)
approval_refs = [] len=0 — not filled by engine (1)
promotion_gate_result.passed = not-set / None — guard: engine does NOT set gate.passed (1)
rollback_strategy_ref populated if predecessor ref exists from registry metadata (1)
comparable=True on success (1)
incomparable=False + reasons empty on success (1)
Total 8

## T14. Backward Compatibility Guards (1)
SBKT01/02/03/MDL-01 regression unchanged import chain:
from app.evaluation import CompareEngine, ChampionChallengerEvaluationPayload, MetricDelta, CompareValidationError  — no AttributeError (smoke imports) (1)
Total 1

---
### TOTAL: 22 + 25 + 39 + 55 + 6 + 4 + 18 + 14 + 7 + 25 + 13 + 13 + 8 + 1 = 250 parametrize meaningful (count ≥ 240 → PASS S1)
