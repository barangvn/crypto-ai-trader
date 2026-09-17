# Proof Boundary S-MDL-05 CAP-5 (IN / OUT explicit — NO SILENT SLIPPAGE)

## IN Scope (Proof What — CAP-5 only)

1. **ModelVersion.status transitions FSM graph — exactly 9 allowed T1-T9 + 1 ADN rollback_champion edge + 7 forbidden F1-F7 + same-status noop** — all from S-CON-02C L176-L265 canonical.
2. **Direct DB/update bypass detection** — AST scan repo-wide detecting direct status mutation (8 pathways), non-registry owner request_transition() call (14 scope), write primitive outside registry storage (4 primitives), FSM contract bypass constructor.
3. **Upstream enforcement layers reuse test-positive** — S-CON-02C ModelLifecycleTransition.\_\_post_init\_\_ FSM validation raises (S-MDL-01 L225 reuse pattern); S-MDL-01 request_transition raises; LIFECYCLE L10/L63 audit rule. NO NEW validation code.
4. **Audit / Event integrity (FR-041)** — approver_refs, audit_note, evidence_refs, occurred_ts, prior_state, corr/caus, publish rules = existing patterns; verify only.
5. **Atomic write proof** — S-MDL-01 storage tmp→rename sequence fault inject = existing implementation only verify.
6. **Determinism / Reproducibility (AD-20 / NFR-007)** — 10 runs identical + replay fixtures = verify only.
7. **Fail-closed AD-19 + CAP5A-H extend 8 families** — existing fail matrix reuse + 8 dedicated CAP-5 verify.
8. **Regression preservation** — S-MDL-01/02/03/04 tests PASS 0 FAIL count preserved.

## OUT Scope (What NOT — NON-GOALS 17; DO NOT TOUCH)

1. ❌ New promotion scoring / weighted Σ algorithm (S-MDL-03 owner — NG1)
2. ❌ New rollback eligibility / 17 reason code duplicate (S-MDL-04 owner — NG2)
3. ❌ New Sharpe / maxDD / Sortino / PF / Return / Cost metric recompute (S-MDL-02 / S-BKT owner — NG3)
4. ❌ New contract class / CONTRACT_VERSION bump 1.0.0 (NG4)
5. ❌ DB / sqlalchemy / timescale adapter; v1 stdlib local fs only (NG5)
6. ❌ ML fit / predict; AI optimizer; grid search (NG6)
7. ❌ Live exchange / credentials / REST real orders / keys (NG7)
8. ❌ MVP API server routes / UI dashboard components (NG8, NG16)
9. ❌ S-MDL-01 registry create_model_version / update_metadata / list / read RE-IMPLEMENTATION (NG9)
10. ❌ EventBus schema change / new event type (NG10)
11. ❌ Approval_refs construct outside governance (NG11)
12. ❌ Direct Champion→Challenger F5 bypass write (NG12)
13. ❌ New object storage SDK / cloud backend (NG13)
14. ❌ Predecessor multi-hop traversal / history restore (NG14)
15. ❌ Policy numeric threshold change (NG15)
16. ❌ S-MDL-01/02/03/04 test assertions modify / weakening (NG17)
17. ❌ Registry mutation inside cap5 proof harness; ONLY imports existing request_transition to test; never new write path.

## Boundary Enforcement

- 14 hard-red scope HRC1-HRC14 0 byte diff.
- HRC15-HRC21 dedicated CAP-5 AST 0-hit.
- Proof code under app/proof/ ONLY; import ast + stdlib only; never writes to .registry-artifacts/; never imports storage create_model_version write path.
