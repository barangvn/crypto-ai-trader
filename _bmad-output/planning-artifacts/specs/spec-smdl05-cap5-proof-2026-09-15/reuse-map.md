# Reuse Map S-MDL-05 CAP-5 — Upstream Artifacts / Ownership

> Map: S-MDL-05 imports & EXERCISES upstream artifacts; NEVER REIMPLEMENTS. NG1-NG3 explicit no reimplement.

## Reuse: Contract / Implementation Layer (100% reused — 0 new implementation contract logic)

| Reused Artifact | Producer Story | Reused by S-MDL-05 as (CONSUME ROLE) | Modify / Reimplement |
|---|---|---|---|
| ModelVersion (contract dataclass) | S-CON-02C §2.1 | input payload; NO modify contract fields | ❌ NEVER |
| ModelLifecycleTransition (with `__post_init__` CAP-5 FSM contract raise 9/7 + noop rules) | S-CON-02C §3.4 | DIRECTLY EXERCISE raise for F1-F7 / noop scenarios; NO duplicate validation logic — S-MDL-01 L225 reuse pattern | ❌ NEVER duplicate. ONLY import and verify raise |
| ChampionChallengerEvaluation contract + 11 required keys + schema_sha | S-MDL-02 / S-CON-02C | Evidence ID reference only; never recompute Sharpe/PF/DD | ❌ NEVER recompute metric |
| PromotionGateResult.pass + winner=challenger invariant binding CAP-5 (S-MDL-03 CAP-5 binding invariant) | S-MDL-03 CAP-4 / CAP-5 | audit gate_decision_id links valid; never recompute weighted score Σ = sum(Wm*Sm) logic S-MDL-03 H51 | ❌ NEVER recalc Σ or change Wm |
| RollbackEligibilityDecision + 17 fail-closed reasons + command_NAME ref rollback_champion (NOT EXECUTE call) | S-MDL-04 (NG1: actual execute call deferred to S-MDL-05 registry side via request_transition literal T10) | audit eligibility decision id + predecessor pointer; never duplicate compute_eligibility() logic in proof harness (HRC20: grep duplicate 0) | ❌ NEVER duplicate rollback algorithm |
| ModelRegistry class (registry.py — S-MDL-01) | S-MDL-01 | EXERCISE request_transition() T1–T10 via tests; NO modify existing create / update / list / read methods. S-MDL-05 NEVER writes directly to storage. request_transition is the ONLY entry point. | ❌ NEVER modify existing registry methods except via NEW test that call existing imported registry. |
| ModelStorage ADN-10 local fs tmp→rename pattern (app/registry/storage.py) | S-MDL-01 L118-L136 + ADN-10 default local fs | FAULT INJECT atomic write 3 scenarios via monkeypatch storage write failures; then verify partial artifacts = zero. | NEVER add new storage class. Only import |
| 12-Category RegistryError fail matrix S-MDL-01 L179-L192 | S-MDL-01 L179-L192 + AD-19 default-safe block | CAP5A-H extend families map to error categories. | NO new error class. Existing RegistryError with CAP5_* reason_code subreason field. |
| EventBus model_version_status_transitioned.v1 event envelope | S-MDL-01 L138-L167 publish rules | valid transition → publish_count++ only; invalid → delta=0. | ❌ NEVER schema change, new event type |
| correlation_id / causation_id AD-17 + occurred_ts timestamp fields (deterministic from inputs NOT time.time internal) | SPEC-CRYPTO CAP-1 parity + NFR-007 / AD-20 | audit corr/caus equal parent/transition/event envelope. | NEVER new datetime.now() call inside proof harness code. |

## 14 Non-Owner Domain Scopes — READ-ONLY consumers (0 modify; HRC1-HRC14)

S-MDL-05 inherits from S-MDL-03 (HRC14) S-MDL-04 (HRC1-14 20 scope 0 diff list) 14 scopes; they are READONLY consumers CAP-5 audits non-owner writes zero by AST.

- app/backtest
- app/risk
- app/simulation
- app/replay
- app/platform
- app/features
- app/regime
- app/strategies
- app/opportunity
- app/gate
- app/evaluation
- app/rollback
- tests/backtest/tests/registry/tests/gate/tests/evaluation/tests/rollback

## Produced Artifacts by S-MDL-05 (CAP-5 PROOF STORY ONLY; new scoring/rollback)

1. 13 SPEC companion markdown (this folder SPEC + 12 companions).
2. Static AST scan script (app/proof/ new proof harness — STANDALONE; NEVER calls write_operations on registry; only runs ast.walk())
3. Fail matrix report generators JSON/CSV/md under _proof-reports/cap5/ (gitignore generated)
4. 24 tests under tests/cap5/ conftest + 23 test files.
5. 1 line pyproject.toml pattern add cap5_*.py
