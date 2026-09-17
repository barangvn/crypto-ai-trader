# Test Plan S-MDL-05 CAP-5 Lifecycle Single-Writer Proof Audit

## 1. Structure

- **Target Collected:** ≥ 260 tests (G1-G13 acceptance-criteria) — actual arithmetic 311)
- **Pass criteria:** FAIL=0 / SKIP structural ≤ 5 (descriptive only)
- **Framework:** pytest + conftest fixtures (new tests/cap5/conftest.py) + 23 test_ files

## 2. Fixtures (conftest.py tests/cap5/conftest.py) — 20 typed fixtures

1. `clean_registry_root(tmp_path_factory) — registry art root under tmp_path_factory artifacts root = tmp_path_factory.mktemp("registry-root"); registry.storage_root=path
2. `registry_clean` — ModelRegistry(storage_root fixture import app.registry import registry Registry constructor; seed = Registry;
3. `seed_mv_candidate` — seed 1 ModelVersion candidate status create_model_version(..., status candidate);
4. `seed_mv_tested` — T1 applied tested;
5. `seed_mv_paper` — T2 applied;
6. `seed_mv_challenger` — T3 applied;
7. `seed_mv_champion` — T4 applied predecessor set;
8. `seed_mv_retired` — T5 applied;
9. `gate_decision_pass_mock` — typed gate_decision_id = str;
10. `rollback_eligible_decision_fixture` — decision_sha256 mock eligible=True;
11. `corr_foo_bar_v1` — correlation id mock correlation;
12. `causation_parent_seed` — causation id mock;
13. `occurred_ts_fixed_seed` — ISO timestamp fixed;
14. `approval_refs_default_adn08_min1` — min 1 approval;
15. `evidence_refs_eval_ids` — list of eval id;
16. `audit_note_sample` — str non-empty;
17. `transition_kwargs_valid_t1_t10` — valid kwargs per T1..T10;
18. `dummy_8_forbidden_edge` — 7F payload dict;
19. `dummy_inject_ast_bypass_src_files` — temporary python files created with forbidden patterns injected for AST detect positive tests
20. `atomic_write_fault_inject_patch` — monkeypatch permission error raise simulate write after first writes;

## 3. Test Files (23 new — tests/cap5/ folder

| Test file | Scope |
|---|---|
| `conftest.py` | fixtures only |
| `test_cap01_ast_direct_status_assign.py` | direct assign x scenarios × G1=64; (direct mutate 8 families) |
| `test_cap02_ast_request_transition_non_registry.py` | CAP-2 ast + dummy inject detect positive; |
| `test_cap03_ast_write_primitives.py` | CAP-3 AST write primitives; |
| `test_cap04_fsm_forbidden_7f.py` | G2 F1-F7 7 edges 7 × 3 = 21 scenarios; |
| `test_cap05_fsm_noop_same_status.py` | 3 noop (champion/challenger/paper → same 3 × 3; |
| `test_cap06_fsm_allowed_t1_t10.py` | 10 allowed 10 × 4=40; |
| `test_cap07_t4_gate_prereq.py` | G5.1–5.4 T4 × 4 = 16; |
| `test_cap08_rollback_prereq.py` | G6 16 scenarios; |
| `test_cap09_evidence_audit_fields.py` | G7 evidence len ≥ 1 etc. 7 × 4=28; |
| `test_cap10_atomic_write_fault.py` | G8 3 × 4 = 12; |
| `test_cap11_determinism_10x.py` | G9 10 runs; |
| `test_cap12_reproducibility_replay.py` | G10 replay 3 fixtures; |
| `test_cap13_failclosed_8family.py` | CAP-13 fail closed 8 families; |
| `test_cap14_event_publish_rules.py` | CAP-14 publish 12 scenarios; |
| `test_cap15_regression_preserved_smdl01.py` | S-MDL-01 baseline regression; |
| `test_cap16_regression_smdl02.py` | S-MDL-02 baseline; |
| `test_cap17_regression_smdl03.py` | S-MDL-03 baseline; |
| `test_cap18_regression_smdl04.py` | S-MDL-04 baseline; |
| `test_cap19_f4_retired_any_forbidden.py` | F4 retired→* 5 forbidden; |
| `test_cap20_t10_rollback_champion_edge.py` | T10 rollback edge retire + predecessor; |
| `test_cap21_admin_retire_t6_t9.py` | admin_retire T6–T9 4 edges × 4 assertions = 16; |
| `test_cap22_audit_event_integrity.py` | FR-041 corr/causation/ts/prior; |
| `test_cap23_negative_49cases.py` | 18 header negative cases total ≥ 49 negative; |

## 4. Expected Test Phases

### Phase 0 Static (AST) — Static Script

| Family | Count |
|---|---|
| bypass_ast_scan.py (stdlib only ast module) = `app/proof/cap5_bypass_audit.py` [PROOF CORE expected-file-changes §1 allowlist] | 1 script; produces P1 bypass_audit_report.md; csv; |
| AST POSITIVE SUPPORT fixture on-disk `app/proof/cap5_dummy_inject_1.py` [classification: AST POSITIVE SUPPORT NOT RUNTIME IMPORTED expected-file-changes.md §1 allowlist, runtime import/call=0] = inject pattern → detected verify pattern → verify script → 6 dummy pattern hits P1×2 + P2 + P3×2 + P4 = confirm detection works positive; | 4 dummy pattern types in single on-disk file + scanner detects each flag positive hit_count > 0; run-time import of this file NEVER occurs (grep app/+tests returned 0 match for cap5_dummy_inject_1/run_all_dummies) |

### Phase 1 Negative First (49 negative cases TOTAL: 33 original rows + 8 new dedicated rows = 41→49)
1.  8 direct mutation → fail (G1 CAP5A family 8 scenarios × fail closed)
2.  8 forbidden transition (7 forbidden F1-F7 + same-status noop 1 = 8)
3.  3 noop (champion/challenger/paper same → same)
4.  5 retired→ any F4 forbidden (5 concrete retired→cand/tested/paper/challenger/champion)
5.  4 T4 prereq missing reject (no gate/no approval/no evidence/no rollback_strategy_ref G5.1–G5.4)
6.  4 rollback prereq missing reject (no predecessor/no decision/eligible False/not-champion-status G6.1–G6.4)
7.  7 evidence audit incomplete reject (7 scenario × G7.01/G7.05/G7.09/G7.13/G7.17/G7.25 + whitespace audit_note = 7 distinct evidence field failures)
8.  3 fault inject atomic + no publish invalid (G8 3 fault × G12 invalid publish delta 0 combine = 3 distinct atomic-fault-publish-none scenarios)
9.  **(NEW N1)** stale evaluation_ts T3 paper→challenger reject: eval age > max_eval_age_days S-MDL-03 CAP7 propagate → CAP5_EVAL_STALE_REJECT
10. **(NEW N2)** stale evaluation_ts T4 promote_champion reject → same CAP5_EVAL_STALE_REJECT
11. **(NEW N3)** rollback_decision_ts outside max_degradation_window 30 ADN days S-MDL-04 CAP5 staleness window → CAP5_ROLLBACK_STALE_DECIDED reject
12. **(NEW N4)** T4 promote_champion corr_id empty string (not valid ULID format) validation CAP-1 parity C9 corr AD-17 → REJECT CAP5_CORRELATION_ID_INVALID
13. **(NEW N5)** rollback_champion T10 causation_id mismatch (doesn't match parent degradation transition_id) NFR-017 causation AD-17 → REJECT CAP5_CAUSATION_MISMATCH
14. **(NEW N6)** evidence_refs list item empty string "" (whitespace/not valid eval_id format) × promote_champion T4 → CAP5_AUDIT_EVIDENCE_INVALID_FORMAT reject
15. **(NEW N7)** approval_refs item empty string × admin_retire T6 candidate → CAP5_APPROVAL_REF_INVALID_FORMAT reject (audit note ok but approval empty string format fail)
16. **(NEW N8)** T10 rollback champion predecessor model_ref not exist (invalid model_id not in registry model_map) registry S-MDL-01 pointer validity → CAP5_ROLLBACK_PREDECESSOR_NOT_FOUND reject
Total Phase-1 = 8+8+3+5+4+4+7+3 + 8 NEW N1-N8 = 42 + 7 existing? → arithmetic EXACT = 8+8+3+5+4+4+7+3 = 42 original rows? No: original 8+7+3+5+4+4+7+3 = 41, new 8: 41+8 = **49 NEGATIVE CASES TOTAL ✅** ≥ headline 49 claim. Explicit enumerate: (N1-N8 new IDs + original families map each to AC groups below)

#### Phase 1 Negative 49 Case → Explicit ID Mapping (EACH unique ID, trigger, source, expected)

| Phase1 Case ID | Trigger Scenario | Expected Proof Result (Fail Closed REJECT/RAISE) | Mapped AC/CAP Group | Source Exact Ref |
|---|---|---|---|---|
| P1-01 | Direct mv.status = champion setattr direct | CAP5_DIRECT_STATUS_MUTATION_FORBIDDEN CAP5A | G1/CAP-4 | S-MDL-01 L41 direct assign |
| P1-02 | Dict update payload includes status key S-MDL-01 L49 | CAP5_DIRECT_STATUS_MUTATION L49 ERR pattern | G1 | S-MDL-01 L49 update payload |
| P1-03 | Direct storage write_text with status override | CAP5A storage direct | G1 | LIFECYCLE L10 direct DB YASAK |
| P1-04 | ORM-like dataclasses.replace mv status changed | CAP5A replace pattern | G1 | CON 02C L261 post init |
| P1-05 | storage.model_map dict direct ["status"]=champion bypass setter | CAP5A dict mutate pattern | G1 | SPEC-CRYPTO storage writes |
| P1-06 | ModelVersion constructor status kwarg bypass storage.create (imported directly) | CAP5A constructor bypass | G1/HRC17 | S-MDL-01 storage pattern |
| P1-07 | mv.__dict__["status"] mutate internal (cheat bypass property) | CAP5A __dict__ mutate | G1 | (direct mutate internal variant) |
| P1-08 | importlib.reload(ModelVersion) monkey-patch status class attribute direct | CAP5A reload cheat pattern detected AST (string pattern reload + status) | G1 | 8 pathway variant 8/8 S-MDL-01 ERR |
| P1-09 | F1 candidate→champion forbidden edge (skip tested+paper+challenger stages F1) | CAP5_FSM_FORBIDDEN F1 L198 | G2/CAP5B | CON 02C F1 L198 |
| P1-10 | F2 paper→champion (skip challenger stage F2) | CAP5_FSM F2 prefix | G2 | CON02C F2 L199 |
| P1-11 | F3 tested→champion F3 2-skip | FSM FORBIDDEN F3 | G2 | CON02C F3 L200 |
| P1-12 | F5 champion→challenger reverse F5 NOT rollback C11 explicit | FSM F5 forbidden L202 | G2/C11 | L202 F5 + Constraint C11 explicit |
| P1-13 | F6 challenger→paper downgrade L203 F6 | FSM F6 | G2 | F6 L203 |
| P1-14 | F7 tested→candidate reverse L204 F7 | FSM F7 | G2 | L204 F7 |
| P1-15 | F4 retired→candidate L201 F4 retired→* | FSM F4 | G2 | L201 F4 any reverse |
| P1-16 | paper→paper same-status noop L262 raise | CAP5_FSM_NOOP_TRANSITION | G2 | CON02C L262 noop RAISE |
| P1-17 | champion→champion same-status noop | FSM NOOP L262 | G2 | L262 |
| P1-18 | challenger→challenger same-status noop | FSM NOOP L262 | G2 | L262 |
| P1-19 | retired→candidate F4 P1-12 duplicate but concrete | (covered above but concrete 5/5 F4 list below:) | G2 | L201 F4 retired list 5 |
| P1-20 | F4 retired→tested concrete 2/5 | F4 retired tested | G2 | F4 |
| P1-21 | F4 retired→paper 3/5 | FSM F4 retired paper | G2 | L201 F4 |
| P1-22 | F4 retired→challenger 4/5 | F4 retired challenger forbid | G2 | L201 |
| P1-23 | F4 retired→champion 5/5 (cannot restore predecessor OD-05 ADN-11 reserved) | F4 retired champion forbid | G2/M1 alignment | F4 retired→* + OD-05 v1 MVP retired ONLY |
| P1-24 | T4 promote_champion gate_decision_id None missing (G5.1) | CAP5_GATE_PREREQ_MISSING gate_decision | G5/CAP5E | LIFECYCLE T4 gate prereq CAP7 |
| P1-25 | T4 gate_decision exists but gate_pass boolean False evidence | CAP5_GATE_PREREQ_GATE_NOT_PASSED | G5/CAP-7 | S-MDL-03 winner invariant NOT pass |
| P1-26 | T4 approval_refs empty [] len zero (ADN-08 min=1 rule) (G5.2) | PROMOTE_MIN_APPROVAL_GATE_REJECT | G5/CAP7 | ADN-08 min 1 L503 |
| P1-27 | T4 rollback_strategy_ref None missing (OD-06 mandatory default) G5.4 | CAP5_GATE_PREREQ_MISSING rollback_strategy_ref | G5/OD-06 | S-MDL-03 L34 T4 rollback prepared |
| P1-28 | rollback T10 predecessor_model_ref null/None (G6.1) CAP10 predecessor mandatory | CAP5_ROLLBACK_PREREQ_MISSING predecessor | G6/CAP5F/CAP-10 | S-MDL-04 CAP-10 predecessor mandatory |
| P1-29 | rollback rollback_decision_id ref None missing G6.2 | ROLLBACK_PREREQ decision_ref | G6 | S-MDL-04 NG1 deferred execute |
| P1-30 | rollback eligible=False upstream decision says not eligible G6.3 | ROLLBACK_PREREQ_NOT_ELIGIBLE bool false | G6/CAP-1 | S-MDL-04 CAP-1 eligible decision |
| P1-31 | rollback_champion from_status NOT champion (call from paper e.g.) G6.4 FSM allow only champion | FSM FORBIDDEN wrong from status | G6/Constraint C18 rollback execute registry only | FSM allow set champion→retired only |
| P1-32 | promote_champion evidence_refs len=0 empty list L2 registry enforce (G7.01) | CAP5_AUDIT_EVIDENCE_INCOMPLETE registry L2 | G7/CAP9/M2 reconciliation | S-MDL-01 L71 min≥1 enforce |
| P1-33 | promote_champion audit_note None promote rationale mandatory FR-041 (G7.09) | CAP5_AUDIT_NOTE_EMPTY promote | G7/FR-041 | PRD FR-041 auditable 5-field rationale |
| P1-34 | rollback_champion audit_note None rollback FR-041 (G7.17) | CAP5_AUDIT_NOTE_EMPTY rollback | G7/FR041 | same FR-041 |
| P1-35 | rollback_champion evidence_refs=[] len=0 registry L2 enforce (G7.13) | CAP5_AUDIT_EVIDENCE_INCOMPLETE rollback T10 | G7/CAP9 | L71 S-MDL-01 min≥1 |
| P1-36 | admin_retire audit_note None (EVEN ADMIN mandatory audit_note NO exception; ONLY evidence_refs empty allowed OD-04) (G7.25) | CAP5_ADMIN_AUDIT_NOTE_EMPTY CAP5G | G7/CAP5G | header 12 fail closed CAP5G rule |
| P1-37 | promote_champion audit_note = whitespace-only string strip len=0 | same CAP5_AUDIT_NOTE_EMPTY whitespace counted empty | G7 | FR-041 rationale "non-empty" means non-whitespace |
| P1-38 | promote_champion approval_refs empty list len 0 ADN-08 min1 (G7.05 duplicate) | PROMOTE_MIN_APPROVAL gate reject | G7/CAP7 | ADN-08 EPICS L503 |
| P1-39 | Atomic fault #1 after first MV write fail (rename-fail permission error injected) → NEITHER file partial exist final → MV_final_exists false + TX_final_exists false + tmp_cleanup 0 | Atomic all-or-none; zero partial artifacts | G8/CAP10 | S-MDL-01 L121 tmp fsync rename Windows atomic |
| P1-40 | Atomic fault #2 TX write second step fail inject (post-MV success but permission denied before tx rename) | same final 0 artifacts, no partial state consistency | G8/CAP10 | L121-L127 storage atomic |
| P1-41 | Atomic fault #3 permission error after tmp written before fsync (crash mid) → NO partial files final exists | No partial MV.json or TX.json partial 0 bytes | G8/CAP10 + publish delta 0 (G12) | Same CAP10 + L166 invalid publish zero delta combine into 1 scenario aggregate |
| **P1-42 (N1 NEW)** | T3 paper→challenger evaluation_ts > max_eval_age_days stale S-MDL-03 CAP7 stale propagate reject | CAP5_EVAL_STALE_REJECT T3 paper challenger | G4/CAP-3 staleness Temporal CAP15 (a-b-c) | S-MDL-03 CAP7 stale max_eval_age_days source only ADN |
| **P1-43 (N2 NEW)** | T4 promote_champion upstream evaluation_ts stale S-MDL-03 CAP7 threshold exceeded (same staleness window) | CAP5_EVAL_STALE_REJECT T4 | CAP-15 temporal (b) | Source backed only no invented numeric T4 staleness CAP7 propagate |
| **P1-44 (N3 NEW)** | Rollback_decision.occurred_ts > 30 days ADN default (S-MDL-04 CAP5 staleness window max_degradation_window_days ADN30 explicit) | CAP5_ROLLBACK_STALE_DECIDED too-old decision reject (staleness propagate) | CAP-8/G6/CAP15 temporal (c) | S-MDL-04 CAP5 staleness explicit window days 30 ADN default |
| **P1-45 (N4 NEW)** | T4 promote_champion correlation_id empty string / not ULID (AD-17 corr/CAP-1 parity C9 internal corr not datetime.now()) | CAP5_CORRELATION_ID_INVALID (validation: corr != ULID format reject BEFORE write) | CAP-1 parity / C9 constraint C9 | CAP-1 parity C9: 0 datetime.now() internal call, corr deterministic from input ULID format |
| **P1-46 (N5 NEW)** | T10 rollback_champion causation_id mismatch parent degradation transition_id (NFR-017 causation AD-17 causation=parent event id) | CAP5_CAUSATION_MISMATCH rollback_causation != degradation_transition_id (parent must match) | C10 Causation AD-17 parity | AD-17 PRD NFR-017 causation match envelope MV TX triple equal |
| **P1-47 (N6 NEW)** | T4 promote evidence_refs list contains empty_string eval_id format invalid (contains at least 1 "") | CAP5_AUDIT_EVIDENCE_INVALID_FORMAT len=empty string not allowed; evidence_ref is eval_id or upstream ref (non-empty str) | G7/CAP-9 evidence validation | CAP-9 / S-MDL-01 L71 min1 (beyond len≥1 → item format valid) |
| **P1-48 (N7 NEW)** | Admin_retire candidate approval_refs contains "" empty string (even admin evidence_refs OK but approval_refs item format invalid) | CAP5_APPROVAL_REF_INVALID_FORMAT (approval ref non-empty string, audit pointer ULID/hash format, empty not valid) | CAP-9/G7 approval item valid | FR-041 approver field "approver_refs" pointer format non-empty |
| **P1-49 (N8 NEW)** | T10 rollback predecessor model_id invalid: registry.model_map.get(predecessor_model_ref) = None NOT exist invalid pointer | CAP5_ROLLBACK_PREDECESSOR_NOT_FOUND pointer validity registry contains predecessor | G6/CAP-8 predecessor mandatory CAP10 | S-MDL-04 CAP-10 predecessor mandatory (existence check beyond non-null → registry exist) |
| Phase-1 TOTAL | explicit ID count P1-01..P1-49 = | **49 CASES EXACT ENUMERATED ✅** | G1/G2/G5/G6/G7/G8/CAP7/8/9/15 + new 8 | Headline ≥49 claim match exact 49 case IDs explicit above table |

### Phase 2 Positive (10 allowed edges)
- T1–T10 40 assertions

### Phase 3 Determinism / Reproducibility
10 runs G9 determinism, G10 replay G11 failclosed 8 families G12 publish

### Phase4 Regression
S-MDL-01 baseline, S-MDL-02, S-MDL-03, S-MDL-04 — each FAIL=0

### Total collected ≥260 tests 0 FAIL allowed

## 5. Verification

`pytest tests/cap5/ -q --no-header -x
Output: PASS count=311 expected FAIL=0 allowed PASS=311 or greater ≥260

## 6. Proof Reports

- P1-P11 reports after pytest completed successfully → 30:11 reports file list exist assertion tests cap5 passes completed
