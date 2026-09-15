# S-MDL-04 Test Plan (tests/rollback/ — ≥ 242 PASS / 0 FAIL / 0 SKIP target)

Test families CAP ordered T01..T18 (18 families + conftest = 19 test files). Structural conditional SKIPS allowed ≤ 30; expected ≥242 PASS.

| # | Family File | CAP | Scenarios planned | Assertions planned | Kaynak CAP |
|---|---|---|---|---|---|
| T01 | rollback_01_eligibility_e1e5_rules.py | CAP-1 + G1 25 AC | 25 (5 rule × 2 value + 15 combined) | 50 | CAP-1 |
| T02 | rollback_02_trigger_enum_3value.py | CAP-2 + G2 11 AC | 11 (3 valid + 8 invalid) | 22 | CAP-2 |
| T03 | rollback_03_evidence_ev1ev6_minimum.py | CAP-3 + G3 20 AC | 20 (EV1..EV6 present/missing + delta 11 key count) | 40 | CAP-3 |
| T04 | rollback_04_approval_min_readonly.py | CAP-4 + G4 15 AC | 15 (min count matrix + AST write 0) | 30 | CAP-4 |
| T05 | rollback_05_staleness_integrity_guard.py | CAP-5 + G5 18 AC | 18 (staleness fresh/boundary/stale × 3 default + override + integrity match/mismatch/unset + combos) | 36 | CAP-5 |
| T06 | rollback_06_missing_target_5reasons.py | CAP-6 + G6 15 AC | 15 (5 individual + 5 combo + dedup × 5) | 30 | CAP-6 |
| T07 | rollback_07_target_selection_1to1.py | CAP-7 + G7 10 AC | 10 (pred 1:1 / multi-chain depth1 / observe mode / enum valid) | 20 | CAP-7 |
| T08 | rollback_08_reasons_sort_dedup.py | CAP-8 + G8 15 AC | 15 (asc sort + dedup + eligible→empty list) | 30 | CAP-8 |
| T09 | rollback_09_determinism_10x.py | CAP-9 + G9 25 AC | 25 (3 fixtures ×10 ×8 item + cross instance 1 aggregate) | 25 each set len=1 | CAP-9 |
| T10 | rollback_10_audit_payload_12field.py | CAP-10 + G10 18 AC | 18 (12 fields + corr/caus/ts/command_name/AST publish/transition 0) | 36 | CAP-10 |
| T11 | rollback_11_registry_readonly_boundary.py | CAP-11 + G11 18 AC | 18 (3 GET used + 7 write 0 + 4 write prim 0 + 4 other) | 36 | CAP-11 |
| T12 | rollback_12_smdl03_border_strict.py | CAP-12 + G12 15 AC | 15 (2 read points only + PromotionGate AST 0 + 14 hard-red diff 0) | 30 | CAP-12 |
| T13 | rollback_13_17_failclosed_reasons.py | CAP-13 + G13 19 AC | 19 (17 unique + set unique empty pass) | 38 unique reason exact 1/17 | CAP-13 |
| T14 | rollback_14_corr_caus_chain.py | G14 8 AC | 8 (preserve/not mutate/non-empty; OUT-OF-SCOPE items NOT counted) | 16 corr=caus | Header 10 / AD-17 |
| T15 | rollback_15_safety_ast_forbidden.py | G15 20 AC | 20 (network 6 / cred 3 / db 4 / order 3 / short 1 / lev 1 / futures 1 / datetime.now 1 = 20 AST) | 20 0 HIT | Constraints C9 |
| T16 | rollback_16_f5_champion_challenger_bypass.py | G16 10 AC | 10 (AST literal F5 check) | 20 0 HIT | Constraints C12 NG11 |
| T17 | rollback_17_thresholds_version_mismatch.py | G17 8 AC | 8 (version match/mismatch/semver invalid/empty/mix type) | 16 | CAP-13 code THRESHOLDS_VERSION_MISMATCH |
| T18 | rollback_18_smoke_backward_regression.py | G18 20 AC | 20 (import + S-MDL-01/02/03 + SBKT01/03 unchanged collected counts + deps=[] + contract_version v1.0.0) | 40 backward PASS 0 FAIL | G18 regression |

---
**Scenario toplamı:** 25(T01)+11(T02)+20(T03)+15(T04)+18(T05)+15(T06)+10(T07)+15(T08)+25(T09)+18(T10)+18(T11)+15(T12)+19(T13)+8(T14)+20(T15)+10(T16)+8(T17)+20(T18) = **272 senaryo**.

Structural conditional SKIPS (örn: registry storage fixture unavailable / filesystem permission skip testi) allowed ≤ **30**.

**Coverage target (S1): ≥ 242 PASS / 0 FAIL / 0 SKIP** (272 total - 30 structural skip max = 242 minimum PASS; no fail allowed).

**Structural fixtures (tests/rollback/conftest.py):**
- fixture1: happy_path_full_eligible (E1-E5 True, EV1-EV6 present, approvals=1, fresh window, integrity OK, trigger=manual, strategy_ref OK, predecessor pointer OK)
- fixture2: missing_target_el_not_found (pred not found, pred null, strategy ref null, approvals short count)
- fixture3: stale_degraded + integrity mismatch combined (age=90d, corruption, degradation_evidence_count below min)
- default_thresholds_cfg ADN default (30d window, min approval=1, min evidence_count=N default)
- rollback_engine_default: default new RollbackEngine instance no-op construction
- tmp_registry_artifacts_path: isolated temp .registry-artifacts tmp path with per-test cleanup no pollution
- 3 CCE payload fixtures (rollback_strategy_ref set / null / empty)
- predecessor_model_versions list 2 fixtures (pred Retired eligible + pred Paper eligible)
- delta_metrics_11_keys_full / delta_metrics_5_keys_missing / delta_metrics_0_keys_empty
- trigger types parametrize 3 valid degradation/manual/kill
- approval_refs count parametrize 0/1/2/5
