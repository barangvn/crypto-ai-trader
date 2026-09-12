# S-MDL-02 Definition of Done (28/28 Source-backed)

DoD-01: CompareEngine modulu `app/evaluation/engine.py` içinde; imports sadece stdlib + typed contracts imported from app.contracts (no 3rd-party)
DoD-02: `CompareValidationError` exception: `.reason_code ∈` 25-enum (string values listed in CAP-10); `.details` dict non-empty on raise
DoD-03: `MetricDelta` dataclass local: {metric_key, champion_value, challenger_value, delta, directionality ∈ HIGHER_BETTER/LOWER_BETTER/NEUTRAL_MATCH, metric_version, rounding_precision}
DoD-04: ChampionChallengerEvaluationPayload field list S-CON-02C ChampionChallengerEvaluation fields ile isim/type uyumlu 1-1 (comparison_metrics flat dict 11 delta required + extras allowed)
DoD-05: `pyproject.toml dependencies=[]` unchanged (no new package)
DoD-06: HARD-RED files listesi unchanged — HARD-RED 0 diff git diff 7604262 audit (hard-red.md doğrulama)
DoD-07: S-MDL-01 registry.py / storage.py / events.py / exceptions.py / __init__.py — 0 MODIFY (UNTOUCHED)
DoD-08: app/contracts/model.py + opportunity.py + diğer — 0 değişiklik (no add/delete/edit, contract_version preserved 1.0.0)
DoD-09: SBKT 01/02/03 run 10x → PASS unchanged (0 regression 222 SBKT01, 332 SBKT03 at least; SBKT02 run timeout ise HARD-RED 0 diff verified)
DoD-10: Registry 162/162 PASS unchanged
DoD-11: FULL tests `FAIL=0 / SKIP ≤ 5`
DoD-12: Test klasör `tests/evaluation/` yeni; her test assertion var; 0 assertionless
DoD-13: `python -m pytest tests/evaluation/ -q --no-header` ≥ 240 PASS / 0 FAIL / 0 SKIP
DoD-14: Determinism 10x için 3 sha set len=1 (MEval / DeltaList / Winner)
DoD-15: 6 comparability invariant tek tek FAILS 6/6 reject
DoD-16: 25 fail-closed category 25/25 reject with correct reason_code
DoD-17: Artifact SHA integrity — 1 match PASS, 1 mismatch INTEGRITY_SHA_MISMATCH reject
DoD-18: Fold 5/5 match produce per-fold delta; fold 5 vs 4 → INCOMPARABLE_FOLD_COUNT reject
DoD-19: Regime decomposition 6/6 deltas produce; 6 vs 5 → INCOMPARABLE_REGIME_GROUPS reject
DoD-20: Decimal/float/int/bool type strict enforcement — 12 type mismatch 12/12 METRIC_TYPE_MISMATCH reject
DoD-21: Per-metric direction correctness: HigherBetter 6× positive delta when challenger>champion; LowerBetter 4× positive when challenger<champion (10/10 PASS)
DoD-22: Winner Hint: 6 critical all pro → challenger_promoted; all pro champion → champion_keeps; mixed → inconclusive (3/3)
DoD-23: Engine NEVER sets `promotion_gate_result.passed` (S-MDL-03 boundary)
DoD-24: Engine NEVER executes registry write (create_model_version / update_metadata / request_transition) — single writer korunur (AST scan 0 hit)
DoD-25: Engine YENİ PnL/maxDD/sharpe/sortino/fee/slippage/trade/cost HESAPLAMAZ — ONLY reads artifacts produced by SBKT/PTF/PTR pipeline (manual diff proof: no new calculation function)
DoD-26: Engine output payload `ChampionChallengerEvaluation(**payload_from_engine)` 0 ContractSchemaError (contract accepts)
DoD-27: AST Forbidden-pattern safety 24 scan → 24/24 0 HIT
DoD-28: 288 AC 288/288 PASS (her AC'nin implementation evidence + test evidence mevcut — audit doğrulanabilir)
