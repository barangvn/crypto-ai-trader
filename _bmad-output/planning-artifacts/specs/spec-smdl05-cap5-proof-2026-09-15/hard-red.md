# HARD-RED S-MDL-05 CAP-5 Proof (21 HRC)

> ihlal = FAIL, teslim edilmiş sayılmaz; herhangi bir öğenin ihlali = commit BLOCK.
> 14 HRC = inheritance from S-MDL-03/04 hard-red 14 domain scope; HRC15–HRC21 = CAP-5 DEDICATED 7 new.

## Inherited 14 Scope Hard-Red (0 byte diff — no change allowed)

| HRC | Scope (0 byte diff; any byte-change → FAIL HRC#) | Why |
|---|---|---|
| HRC1 | app/backtest/* | v1 Backtest engine READONLY consumer, never writes registry. AD-13 AD-33. |
| HRC2 | app/risk/* | Risk engine READONLY consumer CAP-1 parity NFR-015; no mutation. |
| HRC3 | app/simulation/* | Simulation READONLY; no CAP-5 lifecycle. |
| HRC4 | app/replay/* | Replay READONLY; no registry mutation. |
| HRC5 | app/platform/* | Platform READONLY. |
| HRC6 | app/features/* | Features READONLY. |
| HRC7 | app/regime/* | Regime READONLY. |
| HRC8 | app/strategies/* | Strategies READONLY. |
| HRC9 | app/opportunity/* | Opportunity READONLY. |
| HRC10 | app/gate/* | Promotion gate READONLY consumer (S-MDL-03 NG1 defer S-MDL-05). |
| HRC11 | app/evaluation/* | Evaluation READONLY (S-MDL-02 NG3 defer S-MDL-05). |
| HRC12 | app/rollback/* | Rollback READONLY; command NAME only NO execute call (S-MDL-04 NG1). |
| HRC13 | tests/backtest/* | Backtest tests 0 diff. |
| HRC14 | tests/registry/*, tests/gate/*, tests/evaluation/*, tests/rollback/* | Upstream test suites 0 diff inside themselves (except structural wrapper allowlist only if 0 assertion modify). |

## 7 DEDICATED CAP-5 Specific (HRC15–HRC21)

| HRC | Rule — ANY violation detected → FAIL | Detection Method |
|---|---|---|
| HRC15 | `request_transition(` CALL count under {app/gate,app/evaluation,app/rollback,app/backtest,app/risk,app/simulation,app/replay,app/platform,app/features,app/regime,app/strategies,app/opportunity,app/contracts[non import],app/registry_non} = 0 (14 scopes). | AST scan ast.Call func id literal; 0 hit. |
| HRC16 | ModelVersion.status DIRECT assignment (mv.status = X / mv.__setattr__("status", _) / update dict includes "status" outside request_transition) — 0 AST hits outside app/registry/ ONLY. | AST ast.Assign, ast.AugAssign, ast.Call __setattr__ + "status" attr / dict update "status" key node visitor. |
| HRC17 | FSM contract bypass: direct DB-like `ModelVersion(status=champion, ...)` construct outside registry storage.read / registry.storage.create_model_version ONLY allowed if through canonical storage.create_model_version; NEW ModelVersion constructor call directly set status bypass = CAP5 AST flag. | ast.Call "ModelVersion" constructor + "status" keyword arg present inside non storage subclass = flag. |
| HRC18 | 4 Write primitives under `.registry-artifacts/` storage root origin scope NOT equal app/registry.storage: 0. open wb/ab, Path.write_text/bytes, mkdir+write, rename_overwrite = only allowed in storage. | AST walk origin filepath NOT startswith app/registry/ → flag. |
| HRC19 | No weighted Σ score recalculation in cap5 proof code (S-MDL-03 owner): 0 usage of "Σ", "weighted_score", "compute_weighted_score" symbol inside proof harness. | grep symbol count 0 inside new module app/proof/. |
| HRC20 | No rollback eligibility reimplement duplicate in proof harness: 0 "compute_rollback_eligibility" / "RollbackEligibilityBuilder" / 17 reason duplicate inside proof (S-MDL-04 owns). | grep duplicate class / function names 0 inside proof. |
| HRC21 | Direct status assignment in NEW test cap5 files NEVER succeeds: test attempts MUST trigger CAP5_* raise only; no test writes status without registry path. Tests assert raise only. No positive direct write test pass allowed. | pytest AST + test assertion names: "status_write_success" pattern literal count 0 in tests/cap5/. |

## Stdlib / v1 Hard Boundary (Inherit S-MDL-01 — No Change)

- 0 pydantic/numpy/pandas/ccxt/requests/websockets imports allowed in cap5 new code
- 0 live / credentials / short / leverage / futures anywhere (v1 safety)
- 0 datetime.now() / time.time() inside proof harness code (CAP-1 parity; occurred_ts from input)
- 0 DB/sqlalchemy (ADN-10 local fs)
