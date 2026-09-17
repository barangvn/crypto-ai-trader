# Evidence & Proof Chain S-MDL-05 CAP-5 Audit

## 9 Canonical Input Evidence Types (Upstream Artifacts ONLY — NO NEW METRIC)

| Chain Step | Evidence Type | Producer (owner upstream) | S-MDL-05 Role (consume only) | Typed field reference in contracts |
|---|---|---|---|---|
| 1 | **ModelVersion.status contract payload + predecessor_ref** | S-MDL-01 ModelRegistry.create_model_version | Proof audit — status is immutable via direct mutation; predecessor set on T4 only | ModelVersion.status, ModelVersion.predecessor_model_ref (app/contracts/model.py) |
| 2 | **ModelLifecycleTransition FSM payload** | S-CON-02C dataclass; validates __post_init__ FSM edge | EXERCISE existing raise pattern (S-MDL-01 L225 reuse) | ModelLifecycleTransition.from_status / to_status / command_name (S-CON-02C §3.4) |
| 3 | **S-CON-02C __post_init__ raise (F1-F7 / noop)** | Contract owner canonical | Proof = verify raises 7 forbidden / noop; never rewrite logic | contract Exception |
| 4 | **S-MDL-01 request_transition(...) return (new MV, transition) or raise RegistryError** | S-MDL-01 registry | POS / NEG test; NOT new impl | RegistryError L179-L192 12 category + CAP5 extend 8 families CAP5A-H |
| 5 | **ChampionChallengerEvaluation (S-MDL-02) winner=challenger + evaluation_refs + integrity_sha** | S-MDL-02 evaluate_compare | audit chain; NO recompute Sharpe/PF/DD; only ref id check present. | ChampionChallengerEvaluation: winner, challenger_ref, eval_id, integrity_sha256 |
| 6 | **PromotionGateResult.pass=True + winner=challenger_promoted invariant T4 (S-MDL-03 CAP-5 binding invariant)** | S-MDL-03 gate engine | Audit that T4 ONLY fires after gate passed; NO new gate scoring | PromotionGateResult.pass, winner, gate_decision_id, rollback_strategy_ref |
| 7 | **RollbackEligibilityDecision.eligible=True + command_name_ref rollback_champion NOT actual execute call (S-MDL-04 NG1)** | S-MDL-04 rollback builder | audit chain; NG1 = actual execute S-MDL-05 registry side via request_transition command literal T10 rollback_champion retired edge; NEVER reimplement 17 reason duplicate in proof harness | RollbackEligibilityDecision: eligible, target_model_id, decision_sha256, command_name_ref (command literal) |
| 8 | **AD-23 transition_command audit strings** | LIFECYCLE canonical + CON 02C commands | audit matching exact literals only T1-T10 allow | transition_command = exact 10 literal strings map to edges |
| 9 | **ADN-08/09/10 defaults** | EPICS Appendix C L503-L506 binding defaults | audit ADN-08 min approval 1 default applied T4 promote; ADN-10 storage root local fs; ADN-09 kill no close pos | default values in test fixtures; audit against non-compliant scenarios |

## 3 LAYER CAP-5 ENFORCEMENT — PROOF CHAIN ORDER (NEG FIRST)

1. **LAYER 1 (S-CON-02C)** = contract-level payload validation; NEG test 7 forbidden + noop (L237-L265 raises).
2. **LAYER 2 (S-MDL-01 Registry.request_transition)** = registry single-writer; NEG test 8 direct mutation paths + 14 non-owner scope request_transition = 0 AST + T4/T10 prereq missing reject; POS test 10 allowed edges PASS.
3. **LAYER 3 (LIFECYCLE.md Audit Rule L10 + L63)** = repo-wide AST bypass scan result 4 pattern = each hit_count 0; produced P1 bypass_audit_report.md; dummy inject positive verify detect works.

## 4 PROOF OUTPUTS TYPES (NOT EVIDENCE, PROOF DELIVERABLES)

| Output | Type | Format |
|---|---|---|
| PROOF-1 Bypass Audit Report (static) | STATIC PROOF | md + csv (file / line / pattern / hit_count) |
| PROOF-2 Fail Closed Negative Matrix | DYNAMIC PROOF (pytest) | json — 8 CAP5A-C families, 80+ individual negative rows → all err_code match |
| PROOF-3 FSM Allowed / Forbidden Matrix | DYNAMIC PROOF | JSON 10 allowed PASS / 13 forbidden fail |
| PROOF-4 Regression Preservation Counts | DYNAMIC PROOF | CSV S-MDL-01/02/03/04 test counts vs baseline delta FAIL = 0 |
| PROOF-5 10x Determinism | DYNAMIC PROOF | CSV 4 sha cols set_size =1 |
| PROOF-6 Replay Reproducibility | DYNAMIC PROOF | JSON fixture input vs output sha equal |
| PROOF-7 Atomic Write Fault Recovery | DYNAMIC PROOF | md 3 faults inject scenarios → recover no partial |
| PROOF-8 Event Publish Rules Audit | DYNAMIC PROOF | CSV 6 valid emit + 6 invalid delta 0 |
| PROOF-9 Prereq T4 Gate Reject | DYNAMIC PROOF | JSON 4 missing fields scenarios → CAP5_GATE_PREREQ_MISSING reject |
| PROOF-10 Prereq Rollback Reject | DYNAMIC PROOF | JSON 4 missing fields → CAP5_ROLLBACK_PREREQ_MISSING |
| PROOF-11 Audit / Evidence Fields Integrity | DYNAMIC PROOF | MD FR-041 audit fields 7 scenario rejects + 1 admin pass OD-04 |

## TERMINOLOGY DISCIPLINE (NO SILENT EQUIVALENCE — USER EXPLICIT)

- **Evidence** (E1-E9): Upstream artifacts typed refs produced by prior stories. Consumed only — never modified / recomputed.
- **Proof** (PROOF-1..11): Output artifacts produced this story via static AST scan / dynamic pytest run — deliverable to auditors that CAP-5 compliance holds.
- **Verification** (method 17 header): How proof outputs are validated (script exit code / pytest FAIL = 0 / manual checklists).
- **Audit** (Header 9, FR-041): Append-only integrity fields (who, what, when, why, evidence refs, corr/caus) required per transition — part of evidence chain E1–E9 fields.
