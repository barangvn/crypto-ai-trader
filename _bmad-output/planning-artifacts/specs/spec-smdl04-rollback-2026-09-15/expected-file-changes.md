# S-MDL-04 Expected File Changes (allowlist only; 0 existing file modify; HARD-RED 20 scopes 0 diff)

## BU HİKÂYE (SPEC STORY — SADECE SPEC YAZILDI; implementation KOD YOK)

Şu an **SADECE SPEC artifactları** yazıldı (aşağıdaki 10 md + SPEC.md = 11 dosya, BU KLASÖR).

**Hiçbir production / test kodu yazılmadı.** Git add/commit/push YAPILMADI.

---
## FUTURE Implementation Story — S-MDL-04 Production Code (NEW 6 files under app/rollback/)

1. `app/rollback/__init__.py` — public exports: RollbackEngine, RollbackValidationError, RollbackEligibilityDecision, build_rollback_decision, evaluate_rollback_eligibility
2. `app/rollback/exceptions.py` — RollbackValidationError + 17 ERR_ROLLBACK_* reason code constants (CAP-13 list — FIX-02: 18→17 PREDECESSOR_COMPATIBILITY_MISMATCH unsourced removed)
3. `app/rollback/thresholds.py` — load/validate rollback degradation thresholds config (max_window_days / min_approvals / min_evidence_count / thresholds_version / eligible_status_set / trigger enum check)
4. `app/rollback/evidence.py` — validate 6 EV1-EV6 evidence rules, 11 delta_metrics required keys set match ModelEvaluation, integrity_sha256 verify, staleness age calc
5. `app/rollback/builder.py` — build_rollback_eligibility_decision: E1-E5 eligibility, trigger enum validate, evidence validate, approval min READ, missing target reasons ASC, dedup+sort reasons, audit payload 12 fields, 8-tuple deterministic
6. `app/rollback/engine.py` — RollbackEngine dataclass READONLY; only 3 registry GET method calls; 0 write; 0 PromotionGate; 0 eventbus; determinism seed inject

---
## FUTURE Implementation Story — S-MDL-04 Tests (NEW 19 files under tests/rollback/)

7. `tests/rollback/conftest.py` — fixtures: happy, missing, stale, thresholds, pred_model, delta_metrics, tmp_registry_path, cce_payload_3variant, approval_param, trigger_param
8–25. T01..T18 18 family per test-plan.md:
   8. rollback_01_eligibility_e1e5_rules.py
   9. rollback_02_trigger_enum_3value.py
   10. rollback_03_evidence_ev1ev6_minimum.py
   11. rollback_04_approval_min_readonly.py
   12. rollback_05_staleness_integrity_guard.py
   13. rollback_06_missing_target_5reasons.py
   14. rollback_07_target_selection_1to1.py
   15. rollback_08_reasons_sort_dedup.py
   16. rollback_09_determinism_10x.py
   17. rollback_10_audit_payload_12field.py
   18. rollback_11_registry_readonly_boundary.py
   19. rollback_12_smdl03_border_strict.py
   20. rollback_13_17_failclosed_reasons.py
   21. rollback_14_corr_caus_chain.py
   22. rollback_15_safety_ast_forbidden.py
   23. rollback_16_f5_champion_challenger_bypass.py
   24. rollback_17_thresholds_version_mismatch.py
   25. rollback_18_smoke_backward_regression.py

---
## SPEC ARTIFACTS — BU KLASÖR (NEW 11 dosya BU SPEC story)

26. `SPEC.md` (ana kernel: Why, 20 Source-back Headers, 13 CAP, Constraints, NG, Success)
27. `acceptance-criteria.md` (272 AC G1-G18 — FIX-01 actual enum 25 G9 + FIX-02 remove 1 reason = 272 canonical)
28. `dod.md` (30 DoD)
29. `test-plan.md` (T01-T18 18 family, 272 scenario, ≥242 PASS target, conftest fixtures — 272-30 skip=242 arithmetic)
30. `hard-red.md` (20 scope 14 inherit + 6 rollback new)
31. `open-decisions.md` (8 ADN)
32. `expected-file-changes.md` (BU DOSYA)
33. `reuse-map.md` (reuse / reimplement)
34. `thresholds.md` (rollback degradation ADN defaults reference table)
35. `weights.md` (weighted score NOT USED by rollback — explicit N/A for S-MDL-04, boundary to S-MDL-03)

---
## FORBIDDEN Zero-Touch Hard-Red 20 scope

app/contracts/*, app/registry/*, tests/registry/*, app/backtest/*, tests/backtest/*, app/risk/*, app/simulation/*, app/replay/*, app/platform/*, app/features/*, app/regime/*, app/strategies/*, app/opportunity/*, pyproject.toml, + HRC15-20 rollback module specific AST 0 literal/call.

**0 existing file ANY change allowed outside allowlist NEW files.**
