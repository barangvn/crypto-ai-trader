# Acceptance Criteria — S-MDL-05 CAP-5 Lifecycle Single-Writer Proof Audit

> Arithmetic total (explicit, no vacuous): **G1–G22 = 260 AC, TARGET ≥ 260 PASS / 0 FAIL**
> Each AC: G = group, N = num, Rule = source-ref testable boolean (no ambiguity).

## G1. Direct Mutation 8 Scenarios × 8 Pathway Variants (CAP-4) = 64 AC

> Canonical arithmetic: 8 distinct direct-mutation scenarios × 8 payload/sub-pathway variants each = 8 × 8 = 64 AC (source: S-MDL-01 L41 3 explicit ERRs + 5 concrete pathways L49-51 = 8 scenarios × 8 variants: dict/setattr/replace/Path.json status/constructor status kwarg/registry.model_map direct/storage list bypass/importlib.reload cheat = EXACT 64).

| AC id | Rule (PASS if TRUE) | Source-ref |
|---|---|---|
| G1.1–G1.8 | Scenario-1 (direct mv.status = champion) × variants 1..8 → all CAP5_DIRECT_STATUS_MUTATION_FORBIDDEN raised + storage 0 write + event 0 delta | S-MDL-01 L41 direct assign |
| G1.9–G1.16 | Scenario-2 (mv status assign post-read) × variants 1..8 → 0 event publish | S-MDL-01 L166 event rule |
| G1.17–G1.24 | Scenario-3 (mv.__setattr__("status", champion)) × variants 1..8 → RAISE | S-MDL-01 L41 setattr |
| G1.25–G1.32 | Scenario-4 (storage dict include "status" outside req_trans) × variants 1..8 → RAISE | SPEC-CRYPTO CAP-5 |
| G1.33–G1.40 | Scenario-5 (update_payload={"status": champion} attempt) × variants 1..8 → RAISE | S-MDL-01 L49 RAISE |
| G1.41–G1.48 | Scenario-6 (direct storage write_text mv-{}.json status modded) × variants 1..8 → CAP5 | LIFECYCLE L10 DB update forbid |
| G1.49–G1.56 | Scenario-7 (ORM-like dataclasses.replace with status change) × variants 1..8 → RAISE | CON-02C L261-L265 |
| G1.57–G1.64 | Scenario-8 (dict.update(ModelVersion) {"status": champion}) × variants 1..8 → RAISE | S-MDL-01 L41 |
| G1 TOTAL | 8 scenarios × 8 variants = 64 EXACT; no status dimension added (T4 promote_champion only challenger→champion, retired re-elevate NOT normative v1 per OD-05) | CAP-4 8×8 |

## G2. FSM Forbidden 7 edges + same-status noop + retired→* any 5 = **14 edges × 8 variants = 112**? NO: simplify arithmetic → **14 forbidden AC (G2.1-G2.14)** — EACH × (a) correct reason code; (b) no write; (c) no publish → 14×3 = **42 AC** → G2 total = 42

| G2.1 | F1 candidate→champion → FSM FORBIDDEN | S-CON-02C F1 |
| --- | --- | --- |
| G2.2 | F2 paper→champion → FSM FORBIDDEN | F2 |
| G2.3 | F3 tested→champion → FSM FORBIDDEN | F3 |
| G2.4 | F4 retired→candidate → FSM FORBIDDEN | F4 |
| G2.5 | F4 retired→tested → FSM FORBIDDEN | F4 |
| G2.6 | F4 retired→paper → FSM FORBIDDEN | F4 |
| G2.7 | F4 retired→challenger → FSM FORBIDDEN | F4 |
| G2.8 | F4 retired→champion → FSM FORBIDDEN | F4 |
| G2.9 | F5 champion→challenger → FSM FORBIDDEN (NOT rollback! F5 forbidden) | F5 / S-MDL-04 NG1 clarify T9 retired |
| G2.10 | F6 challenger→paper → FSM FORBIDDEN | F6 |
| G2.11 | F7 tested→candidate → FSM FORBIDDEN | F7 |
| G2.12 | same-status noop paper→paper → RAISE FSM NOOP (S-CON-02C L262) | CON-02C L262 |
| G2.13 | same-status noop champion→champion → RAISE | noop |
| G2.14 | same-status noop challenger→challenger → RAISE | noop |
| **G2 total** | **14 edges × (code + no write + no publish =3) = 42** | --- |

## G3. FSM Allowed 9 T1-T9 + rollback_champion (T10) × 4 assertions = 10×4 = **40 AC**

| G3 group | 10 allowed edges | 4 assertions each = (status changed / tx persisted / sha differs / event emitted) → 10×4=40 |
|---|---|---|
| T1 candidate→tested | test command | 4 |
| T2 tested→paper | paper command | 4 |
| T3 paper→challenger | challenger command | 4 |
| T4 challenger→champion | promote_champion + gate prereq proof | 4 |
| T5 champion→retired | retire_champion | 4 |
| T6 admin_retire_candidate → retired | 1 (T6) | 4 |
| T7 admin_retire_tested → retired | T7 | 4 |
| T8 admin_retire_paper → retired | T8 | 4 |
| T9 admin_retire_challenger → retired | T9 | 4 |
| T10 rollback_champion champion→retired | ADN edge + predecessor set before rollback? No OOS separate; T10 retired only | 4 |
| G3 total | 40 | --- |

## G4. AST Bypass Scan 4 pattern × 5 audit dimensions = 20 AC

| AC ID (Unique) | Pattern / Trigger | Expected Proof Result | Mapped AC/CAP | Source Reference |
|---|---|---|---|---|
| G4.01 | direct-status-assign pattern family (AST Assign .status) | hit_count = 0 non_registry scope; report output exists | CAP-1 / G1 | S-MDL-01 L41 + LIFECYCLE L63 |
| G4.02 | direct-status-assign pattern family | file_count matched expected count (0 match actual) | CAP-1 / AST | LIFECYCLE DB update YASAK |
| G4.03 | direct-status-assign pattern family | line numbers in csv correct (no ghost line refs) | CAP-1 | AST scan stdlib |
| G4.04 | direct-status-assign pattern family | dummy_inject_1.py pattern detected positive hit>0 (verify scan works) | CAP-1 validation | S-MDL-01 L41 |
| G4.05 | direct-status-assign pattern family | output file bypass_audit_report.md produced with 4 pattern rows | CAP-1 / P1 report | SPEC L16 artifact |
| G4.06 | non_registry-request-transition-call pattern | hit_count = 0 outside app/registry/ | CAP-2 / HRC15 generalize | EPICS FR-068 ONLY registry |
| G4.07 | non_registry-request-transition-call pattern | file_count matches expected = 0 | CAP-2 | NG chains SMDL02/03/04 NG1/NG3 |
| G4.08 | non_registry-request-transition-call pattern | line numbers in csv valid no bogus | CAP-2 | AST grep tool |
| G4.09 | non_registry-request-transition-call pattern | dummy_inject_2.py non_registry call detect positive | CAP-2 positive | EPICS FR-068 |
| G4.10 | non_registry-request-transition-call pattern | output file owner_scope_audit.csv | CAP-2 / P4 report | SPEC L16 P4 |
| G4.11 | write_primitives_4family pattern (open_wb / write_text / mkdir+write / rename_overwrite_storage_root) | hit_count=0 non_registry origin | CAP-3 / HRC18 write primitive | S-MDL-01 L118-L136 storage single writer |
| G4.12 | write_primitives_4family pattern | file_count matches = 0 expected zero | CAP-3 | AD-7/AD-13/AD-24 sole owner |
| G4.13 | write_primitives_4family pattern | line references correct not spurious | CAP-3 | AST stdlib ast.walk() |
| G4.14 | write_primitives_4family pattern | dummy_inject_3.py open_wb outside registry detect hit>0 positive | CAP-3 positive | S-MDL-01 L118 atomic tmp |
| G4.15 | write_primitives_4family pattern | output primitive_audit.csv written (or section in P1 report) | CAP-3 / P1 | SPEC L16 artifact |
| G4.16 | fsm_bypass_constructor_code pattern (ModelVersion() constructor bypass storage; no request_transition) | hit_count=0 non storage.py | CAP-3 / HRC17 constructor bypass | S-CON-02C §3.4 contract |
| G4.17 | fsm_bypass_constructor_code pattern | file_count zero expected matches actual zero | CAP-3 | storage single writer AD-24 |
| G4.18 | fsm_bypass_constructor_code pattern | line refs valid, none phantom | CAP-3 | AST parser stdlib |
| G4.19 | fsm_bypass_constructor_code pattern | dummy_inject_4.py ModelVersion("status", …) outside storage detect positive hit>0 | CAP-3 positive validation | S-MDL-01 storage pattern |
| G4.20 | fsm_bypass_constructor_code pattern | output row appended to bypass_report with pattern_id=FSM_BYPASS_CONSTRUCTOR | CAP-3 / P1 appendix | SPEC L16 P1 |
| G4 TOTAL | 4 pattern × 5 dimensions = EXACT 20 | — | — | 20/20 row explicit |

---

## G7. Evidence & Audit fields 7 scenarios × 4 assertions = 28 AC

> 3-LAYER RECONCILIATION REMINDER: L1 S-CON-02C L255 schema evidence_refs empty ✅E; L2 S-MDL-01 L71 registry enforce len≥1 except admin OD-04; L3 CAP-9 proof audits L2 registry enforcement.

| AC ID | Scenario / Trigger | Expected result | Mapped CAP | Source |
|---|---|---|---|---|
| G7.01 | promote_champion T4 with evidence_refs=[] (empty list) | REJECT CAP5_AUDIT_EVIDENCE_INCOMPLETE (registry L2 enforce) | CAP-9 / G5.3 | S-MDL-01 L71 min≥1 |
| G7.02 | G7.01 + MV status unchanged (no write) | MV.status PRE = POST same | CAP-9 | Fail-closed AD-19 |
| G7.03 | G7.01 + storage write 0 bytes | storage_path MV + TX file NOT exist | CAP-9/CAP-10 | Atomic write L121 |
| G7.04 | G7.01 + event publish delta=0 | publish count before==after | CAP-14 / L166 invalid 0 publish | S-MDL-01 L166 |
| G7.05 | promote_champion T4 approval_refs=[] (len=0 empty) | REJECT PROMOTE_MIN_APPROVAL_GATE_REJECT (ADN-08 min=1) | CAP-7/G5.2 | ADN-08 min1 EPICS L503 |
| G7.06 | G7.05 + MV unchanged PRE POST | status PRE=POST | CAP-7 | fail closed |
| G7.07 | G7.05 + no write MV/TX file | 0 final artifacts | CAP-7/CAP-10 | atomic write |
| G7.08 | G7.05 + publish delta 0 | event count same before after | CAP-14 | L166 rule |
| G7.09 | promote_champion audit_note = None/null | REJECT CAP5_AUDIT_NOTE_EMPTY (promote T4 mandatory note FR-041 rationale) | CAP-9 / FR-041 | PRD FR-041 rationale non-empty |
| G7.10 | G7.09 + MV status unchanged | PRE=POST | CAP-9 | fail closed |
| G7.11 | G7.09 + no write storage | MV+TX 0 write bytes | CAP-9 | atomic |
| G7.12 | G7.09 + publish 0 delta | event emit before == after | CAP-14 | no publish invalid |
| G7.13 | rollback_champion T10 evidence_refs=[] empty | REJECT CAP5_AUDIT_EVIDENCE_INCOMPLETE (registry L2 T10 like T4 except admin) | CAP-9 / G6 family | S-MDL-01 L71 min≥1 apply rollback |
| G7.14 | G7.13 + MV retired status NOT applied (PRE champion → POST champion still) | champion unchanged | CAP-9 | fail closed rollback |
| G7.15 | G7.13 + storage 0 write | 0 artifact final | CAP-9/CAP-10 | atomic |
| G7.16 | G7.13 + publish delta 0 | event count zero delta | CAP-14 | invalid 0 publish |
| G7.17 | rollback_champion audit_note empty null None | REJECT CAP5_AUDIT_NOTE_EMPTY rollback mandatory rationale | CAP-9 / FR-041 | PRD FR-041 rationale |
| G7.18 | G7.17 + status unchanged champion→champion still | PRE=POST | CAP-9 | rollback fail closed |
| G7.19 | G7.17 + no write | artifacts 0 | CAP-9 | atomic |
| G7.20 | G7.17 + publish delta 0 | before after same | CAP-14 | invalid 0 emit |
| G7.21 | admin_retire T6-T9 evidence_refs=[] empty OD-04 DEFAULT ALLOW | PASS transition executed (evidence len=0 OK per OD-04 admin default) | CAP-9/OD-04 exception | open-decisions.md OD-04 |
| G7.22 | G7.21 + MV status set retired correctly (from candidate/tested/paper/challenger → retired) | status TO retired change confirmed | CAP-9 | admin override |
| G7.23 | G7.21 + WRITE atomic MV + TX both written, NEITHER partial | BOTH files exist final (atomic all-or-none) | CAP-10 | L121 tmp rename |
| G7.24 | G7.21 + publish event emitted exactly 1 | publish count +1 delta=1 | CAP-14 valid emit | success event L138 |
| G7.25 | admin_retire audit_note=[] empty None null (EVEN ADMIN audit note mandatory NO exception OD-04 only evidence_refs) | REJECT CAP5_ADMIN_AUDIT_NOTE_EMPTY | CAP-9/G CAP5G family | header 12 fail closed CAP5G rule |
| G7.26 | G7.25 + status unchanged (still original) | PRE=POST not retired | CAP-9 | fail closed admin mandatory note |
| G7.27 | G7.25 + no write bytes storage | 0 final artifact | CAP-9/CAP-10 | atomic write or none |
| G7.28 | G7.25 + event publish delta zero | event before after same count | CAP-14 invalid delta 0 | invalid 0 publish rule |
| G7 TOTAL | 7 scenario × 4 assertions = EXACT 28 | — | — | 28/28 |

---

## G11. Fail-Closed CAP-5 8-family (CAP5A-H) Extended Matrix = 22 AC

| AC ID | Family / Trigger Scenario | Expected reason_code prefix or exact | Storage write? Publish delta? | CAP source |
|---|---|---|---|---|
| G11.01 | CAP5A Direct mv.status = challenger (non-registry context) | CAP5_DIRECT_STATUS_MUTATION_FORBIDDEN prefix match | NO write 0 bytes. Delta publish 0 | CAP-4 direct mutate |
| G11.02 | CAP5A payload dict status update S-MDL-01 L49 ERR_DIRECT_STATUS pattern | Same CAP5A direct reason prefix | NO write. Publish 0 delta | SPEC-CRYPTO CAP-5 |
| G11.03 | CAP5A storage Path write_text mv-{id}.json status override (outside request_transition flow) | CAP5 DIRECT prefix | No final mv.json file | LIFECYCLE L10 DIRECT DB YASAK |
| G11.04 | CAP5B F1 candidate→champion forbidden edge (S-CON-02C F1 L198) | CAP5_FSM_FORBIDDEN_TRANSITION F1 prefix | No write. Delta 0 publish | CON 02C F1 L198 |
| G11.05 | CAP5B F2 paper→champion forbidden edge L199 | CAP5_FSM_FORBIDDEN F2 prefix | No write. Publish 0. | CON 02C F2 |
| G11.06 | CAP5B F5 champion→challenger forbidden edge L202 F5 (NOT rollback! F5 explicit YASAK) | CAP5_FSM_FORBIDDEN_TRANSITION F5 reason prefix | No write. Delta 0. | Constraint C11 F5 explicit bypass YOK |
| G11.07 | CAP5B FSM same-status noop champion champion (S-CON 02C L262 noop RAISE) | CAP5_FSM_NOOP_TRANSITION prefix | No write. Publish 0. | CON02C L262 noop |
| G11.08 | CAP5B F4 retired→champion forbidden edge L201 (concrete 5/5 any reverse F4) | CAP5_FSM_FORBIDDEN F4 retired prefix | No write. Publish 0. | Lifecycle Forbidden L51 retired→* |
| G11.09 | CAP5C non-owner app/gate module call request_transition pattern AST dummy inject file positive detection | CAP5C NON_REGISTRY_REQUEST_TRANSITION call count reported (dummy positive: count>0 report PASS detect works) | N/A static audit only, no runtime write | CAP-2 AST non-registry 0 |
| G11.10 | CAP5C actual production codebase scan app/{backtest,risk,simulation,replay,platform,features,regime,strategies,opportunity,gate,evaluation,rollback} × 2 family request_transition call AST 0 | HIT COUNT = zero ALL 14 scopes | No runtime mutation scope readonly | HRC15 generalize 14 scope call count 0 |
| G11.11 | CAP5D write primitive Path.write_text() under .registry-artifacts/ filepath origin NOT under app/registry/ module (dummy inject positive test verify scan catches) | Positive pattern detected hit_count>0 PASS validation works | N/A static only. No production write actual zero. | HRC18 write primitive 4 family origin path |
| G11.12 | CAP5D actual repo wide open(… 'wb') + Path.write_text + mkdir+write + rename overwrite storage = 4 family hits outside registry storage module ALL ZERO | 0 hits ALL families. Report csv all rows zero counts | No actual write. | S-MDL-01 L118 single writer AD-24 |
| G11.13 | CAP5E T4 promote_champion gate_decision_id NULL missing (CAP-7 G5.1) | CAP5_GATE_PREREQ_MISSING gate_decision_id prefix | No write. Publish delta 0 | LIFECYCLE T4 gate prereq CAP-7 |
| G11.14 | CAP5E T4 gate_decision_id exists BUT gate.pass == False upstream evidence invalid | CAP5_GATE_PREREQ_GATE_NOT_PASSED reason prefix | No write. 0 event delta emit | S-MDL-03 CAP-4/5 winner invariant NOT pass |
| G11.15 | CAP5F rollback_champion predecessor_model_ref = None missing mandatory (CAP-8/G6.1) | CAP5_ROLLBACK_PREREQ_MISSING predecessor NULL | champion status UNCHANGED still champion → no write publish 0 | S-MDL-04 CAP-10 predecessor mandatory |
| G11.16 | CAP5F rollback eligible=False upstream decision ref says not eligible (CAP-8 G6.3) | CAP5_ROLLBACK_PREREQ_NOT_ELIGIBLE decision | champion status SAME. No write. Publish 0. | S-MDL-04 CAP-1 eligible bool. |
| G11.17 | CAP5G admin_retire audit_note empty (G7.25 scenario duplicate: CAP5G CAP5_ADMIN_AUDIT_NOTE_EMPTY) | exact reason CAP5_ADMIN_AUDIT_NOTE_EMPTY | status unchanged no write publish 0 | Header 12 item CAP5G admin rule |
| G11.18 | CAP5G admin_retire audit_note = whitespace-only string len 0 strip() | same CAP5_ADMIN_AUDIT_NOTE_EMPTY reason (only whitespace not counted as non-empty) | No write. Publish 0. | FR-041 audit rationale non-empty |
| G11.19 | CAP5H event publish invalid raise (attempt emit "model_version_status_transitioned.v1" BEFORE request_transition successful return) (CAP-14 scenario invalid publish) | REJECT with EventBusPublishBeforeTransitionCommit CAP5H reason | Event publish count delta 0 even if code tries | S-MDL-01 L166 NO publish BEFORE commit |
| G11.20 | CAP5H invalid event publish after CAP5 raise (attacker pattern catch emit on fail) | EVENT delta 0 (publish blocked for failure) | No write. Publish delta 0. | S-MDL-01 L166 invalid ZERO publish |
| G11.21 | Regression sanity: ALL 8 families CAP5A-H have at LEAST one negative test (8 families coverage each has ≥1 scenario above) | 8/8 families have row present (G11.01/04/09/11/13/15/17/19 each family) | coverage count = 8/8 100% | Header 12 fail closed 8 family each ≥ 1 |
| G11.22 | Final aggregate FAIL CLOSED ratio negative = FAIL/PASS ratio for all CAP5A-H rows 22 rows × all MUST return error/RAISE, never PASS silently | PASS count = 0, FAIL count = 22 (100% ratio fail closed — zero silent success on invalid CAP5 family input) | No write aggregate, publish aggregate delta 0 all 22 rows | AD-19 default block fail safe rule |
| G11 TOTAL | 8 family + aggregate = EXACT 22 rows | — | — | 22/22 explicit ids |

---

## G12. Event publish valid/invalid rules (S-MDL-01 L138-L167) = 12 AC

| AC ID | Scenario Trigger | Expected Publish Delta (before → after count change) | Status changed? CAP? | Source |
|---|---|---|---|---|
| G12.01 | T1 candidate→tested VALID allowed pass | Delta +1 (event emit exactly 1) | Yes. MV tested ✅. CAP-6 G3 | S-MDL-01 L138 valid emit |
| G12.02 | T2 tested→paper VALID pass | Delta +1 exactly | Yes. CAP-6. | L138 success event. |
| G12.03 | T3 paper→challenger VALID pass | Delta +1 exactly. | Yes CAP6 | L138 emit. |
| G12.04 | T4 challenger→champion VALID gate pass evidence ok | Delta +1 exactly event envelope event_type=model_version_status_transitioned.v1 match string | Yes champion promoted CAP6 | L138-L167 payload corr/caus matches MV. |
| G12.05 | T5 champion→retired VALID retire command pass | Delta +1 exactly | Yes retired CAP6 | T5 allowed edge |
| G12.06 | T6 admin_retire candidate VALID (audit_note non-empty + evidence len 0 ok OD-04) | Delta +1 exactly 1 event | Yes → retired CAP6. | Admin OD-04 exception evidence empty allowed note mandatory ok |
| G12.07 | F1 candidate→champion FORBIDDEN CAP5 invalid RAISE | Delta 0. NO event emitted at all even if code wants. Publish count before attempt = after. | No status change (forbidden raise). CAP-5B/14. | S-MDL-01 L166 NO publish invalid CAP5 REJECT audit log append ONLY |
| G12.08 | direct mv.status = champion (CAP5A DIRECT invalid raise) | Delta 0 publish count same before/after | No status change direct mutation. CAP-5A / CAP-14. | L166 rule invalid zero emit. |
| G12.09 | T4 gate_decision_id missing CAP5E prereq missing reject | Delta 0 publish NO event before after same. | Status unchanged challenger→still challenger. CAP5E/CAP14. | L166 invalid no emit. |
| G12.10 | rollback T10 predecessor_ref missing CAP5F REJECT | Publish count delta 0 still same. | Status champion unchanged. CAP5F / CAP14. | S-MDL-01 L166 zero publish invalid reject CAP5 |
| G12.11 | F5 champion→challenger FORBIDDEN edge attempt (CAP5B raise F5 champion challenger YASAK C11) | Publish 0 delta (zero event emit). F5 bypass never allowed. | Status champion still same. F5 FORBIDDEN. Constraint C11. | L202 F5 + Constraint C11 explicit F5 no bypass write |
| G12.12 | Event Bus Audit: VALID emit event envelope fields corr_id causation_id match MV correlation and causation (envelope.corr == MV.corr == envelope.payload.from_transition.corr). Event payload from/to/command match transition from/to/command literal. | MATCH 3 CORR assertions: envelope=MV=TX triple equal. payload literal fields match TX. | Valid emit integrity. CAP-14 audit envelope. | AD-17 correlation / causation parity rule; transition_command AD-23 literal string |
| G12 TOTAL | 6 valid emit delta+1 + 6 invalid delta0 + aggregate envelope match = EXACT 12 rows | — | — | 12/12 explicit IDs |

| G5.1 | T4 promote_champion no gate_decision_id → REJECT | T4 precond LIFECYCLE |
| --- | --- | --- |
| G5.2 | T4 no approval_refs empty → REJECT (ADN-08 min 1) | ADN-08 min 1 |
| G5.3 | T4 evidence_refs 0 → REJECT (FR-041) | FR-041 |
| G5.4 | T4 rollback_strategy_ref not set (per S-MDL-03 T4 precond) → REJECT | S-MDL-03 L34 |
| G5 total | 4 × 4 assertions | 16 |

## G6. Rollback Prerequisite 4 × 4 = G6 **16 AC**

| G6.1 | rollback_champion no predecessor ref → REJECT | S-MDL-04 CAP-10 prereq |
| --- | --- | --- |
| G6.2 | rollback_champion no decision_id → REJECT | S-MDL-04 NG1 execute deferred |
| G6.3 | rollback_champion eligible=False referenced → REJECT | S-MDL-04 CAP-1 eligible proof |
| G6.4 | rollback_champion status!=champion → FSM reject (only champion allowed) | T10 allowed from champion only |
| G6 total | 4 × 4 =16 | --- |

## G7. Evidence & Audit fields 7 scenarios → 7×4 = G7 **28 AC**

| G7 | 7 cases × (code match/no write/no publish/status unchanged =4) → 28 |
|---|---|

## G8. Atomic Write 3 fault inject × 5 assertions = 15? → G8 = 3 × 4 = **12 AC**

- 3 scenario × (MV_final_exists == No / Tx_final_exists == No / tmp_file_count_clean ==0 / audit_log_fault_entry_exists) = 3×4 = 12

## G9. Determinism 10x runs + cross-instance 2 = G9 **10 AC**

| G9.1-G9.4 | 4 sha columns set_size=1 each → 4 |
|---|---|
| G9.5-G9.8 | cross instance sha equal → 4 |
| G9.9-G9.10 | path deterministic + transition_id deterministic + 2 = G9 total 10 |

## G10. Reproducibility replay 3 fixtures × 7 fields = G10 **21 AC**

- 3 fixture × 7 = 21

## G11. Fail-Closed CAP-5 8-family (CAP5A-H) 22+ scenarios → G11 **22 AC** each = pass when fail closed

## G12. Event publish 12 → G12 **12 AC**

(6 valid publish +1 + 6 invalid delta=0 = 12)

## G13. Regression 4 suites × (collected≥baseline + FAIL=0) = 4×2 = G13 **8 AC**

| G13.1 | S-MDL-01 baseline + FAIL 0 |
|---|---|
| G13.2 | S-MDL-02 baseline + FAIL 0 |
| G13.3 | S-MDL-03 baseline + FAIL 0 |
| G13.4 | S-MDL-04 baseline + FAIL 0 |
| G13 | 4 ×2 = 8 |

---

# Arithmetic TOTAL (Explicit Check)

| Group | AC Count |
|---|---|
| G1 Direct Mutation | 64 |
| G2 FSM Forbidden | 42 |
| G3 FSM Allowed | 40 |
| G4 AST Bypass Scan | 20 |
| G5 T4 Gate Precondition | 16 |
| G6 Rollback Prerequisite | 16 |
| G7 Evidence Audit Fields | 28 |
| G8 Atomic Write | 12 |
| G9 Determinism 10x + cross | 10 |
| G10 Reproducibility replay | 21 |
| G11 Fail-Closed 8-family | 22 |
| G12 Event publish | 12 |
| G13 Regression 4 suite | 8 |
| **TOTAL** | **64+42=106, +40=146, +20=166, +16=182, +16=198, +28=226, +12=238, +10=248, +21=269, +22=291, +12=303, +8=311. Round TARGET ≥ 260 ACTUAL = 311** |

PASS threshold: ≥260 PASS / 0 FAIL / 0 SKIP structural allowed only descriptive companions allowed.
