# Expected File Changes S-MDL-05 CAP-5 Proof Audit

> Rule: 0 production code inside HRC1-HRC14. All allowlisted changes explicit below.

## 1. Production Code — NEW ONLY (0 modify existing)

Classification legend for this allowlist table:
- `[PROOF CORE]` = normative proof harness (actual logic; runs at test/proof runtime)
- `[PROOF PREREQ / WRAPPER]` = normative CAP-5 prerequisite audit validator / proof layer wrapper (runs at test/proof runtime; loads existing S-MDL-01 registry API)
- `[PACKAGE INIT]` = package structural init only (no behavior; re-exports)
- `[AST POSITIVE SUPPORT, NOT RUNTIME IMPORTED]` = AST SCANNER POSITIVE TEST FIXTURE only. Never imported at production runtime. Never imported by any test at runtime. Sole purpose: on-disk file content parsed by AST scanner to verify pattern-detector positive. Runtime use = NO. Behavior contribution = 0.
- `[GENERATED OUTPUT]` = folder for test proof-artifact writes (gitignored; not source)

| Path | New/Modify | Why | Approve |
|---|---|---|---|
| `app/proof/__init__.py` | NEW (create new package `app/proof`) `[PACKAGE INIT]` | Cap-5 audit module package init. Re-exports 34 public names from below modules. Contains NO new algorithm, NO registry mutation, NO write to storage. | YES allowlist |
| `app/proof/cap5_bypass_audit.py` | NEW — AST scan script (stdlib only: ast, os, pathlib, json, csv) `[PROOF CORE]` | Produce bypass_audit_report.md + CSVs; NO mutation of registry. Serves: CAP-1/CAP-2/CAP-3 / G4=20 AC / HRC15-HRC18 4 AST patterns (P1 direct status assign, P2 non-registry request_transition call, P3 write primitives outside registry, P4 FSM constructor bypass). | YES allowlist |
| `app/proof/cap5_fail_matrix.py` | NEW — load fail closed 8 family matrix produce json `[PROOF CORE]` | NO mutation only test harness only READONLY test helpers. Serves: fail-closed 8 CAP5A-H families enumeration (49 case exact); regression_check() numeric integer baseline compare BASELINE_REGISTRY_ARTIFACT_COUNT = 162 canonical; checkpoint BASELINE_REGISTRY_CHECKPOINT = 7604262. Serves: G11/G12/G13 / CAP-13 / registry numeric 162 canonical verify (int==int NOT text==text). | YES allowlist |
| `app/proof/cap5_audit_validator.py` | NEW — CAP-5 audit prerequisite validator / proof layer (L3) wrapper `[PROOF PREREQ / WRAPPER]` | 3 sub-validators: (a) validate_cap5_gate_prereq (T4 gate decision + min approval CAP5E); (b) validate_cap5_rollback_prereq (predecessor ref + decision + eligible CAP5F combo); (c) validate_cap5_evidence_and_audit (evidence len + audit_note non-whitespace CAP5G — admin_retire OD04 evidence empty default PASS). Plus run_cap5_audit_precheck (3-layer composition) and run_cap5_proof_then_registry (ONLY calls EXISTING S-MDL-01 `registry.request_transition(**kwargs)` unchanged — NO new write path). AC/CAP mapping: G5=16 AC (CAP-7 T4 gate prereq) / G6=16 AC (CAP-8 rollback prereq) / G7=28 AC (CAP-9 evidence audit admin OD04). 8 normative reason code constants: CAP5E_GATE_DECISION_MISSING, CAP5E_APPROVAL_MIN_UNMET, CAP5F_PREDECESSOR_POINTER_NULL, CAP5F_ROLLBACK_DECISION_MISSING, CAP5F_ROLLBACK_ELIGIBLE_FLAG_FALSE, CAP5F_ROLLBACK_COMBINED_PREREQ_INVALID, CAP5G_EVIDENCE_INCOMPLETE, CAP5G_ADMIN_AUDIT_NOTE_EMPTY. Stdlib only (ast 0 use; dataclasses + typing only). EXISTING upstream evidence consumes (NO evaluation recalc, NO weighted Σ recalc, NO promotion threshold rewrite, NO rollback eligibility reimplement). Registry mutation = NO (only delegates to existing request_transition unchanged). Domain algorithm rewrite = NO. S-MDL-01..04 behavior = UNCHANGED. OD04 auto-inject default evidence ["OD04_ADMIN_RETIRE_CANDIDATE_DEFAULT_EVIDENCE"] only when admin_retire_candidate with evidence_ref_ids empty (to align L2 evidence min≥1 with OD04 canonical rule L3 relaxation — does not touch logic). | YES allowlist |
| `app/proof/cap5_dummy_inject_1.py` | NEW — AST scanner POSITIVE test fixture on-disk only `[AST POSITIVE SUPPORT, NOT RUNTIME IMPORTED]` | 6 dummy positive pattern injections for AST scanner sanity: (P1×2 direct status assign + metadata bypass), (P2 non-registry request_transition call), (P3 write primitive open wb + Path.write_text), (P4 ModelVersion constructor status keyword bypass). NOT imported/called by ANY production module at runtime. NOT imported/called by ANY test module at runtime. Evidence: full repo grep app/ + tests/cap5/ for "cap5_dummy_inject_1 / run_all_dummies" returned 0 matches. Behavior contribution = 0. Purpose: AST-only parse file to verify cap5_bypass_audit scanner detects positive patterns. | YES allowlist (SUPPORT scope; explicitly NOT runtime — classification [AST POSITIVE SUPPORT, NOT RUNTIME IMPORTED] above) |
| `_proof-reports/cap5/` (new folder under repo) | NEW folder output artifacts; gitignore; generated test output; not tracked (gitignore add line?) `[GENERATED OUTPUT]` | 11 proof artifacts output P1–P11; generated runtime (allow as OUTPUT) | YES generated; |

## 2. Test Code — NEW ONLY (0 modify existing tests under registry/evaluation/gate/rollback)

| Path | New/Modify | Why |
|---|---|---|
| `tests/cap5/conftest.py` | NEW cap5 fixtures only | NEW fixtures only |
| `tests/cap5/test_cap01_ast_direct_status_assign.py` through `tests/cap5/test_cap23_negative_49cases.py` | 23 NEW test files | Phase 0-4 test files NEW only |

## 3. Configuration — MINOR Allowlista allowlist ONLY 1 line add

| Path | Change |
|---|---|
| `pyproject.toml:L13 [tool.pytest.ini_options] python_files` | add `cap5_*` test pattern (ONLY 1 line; no other modify) → `python_files = ["test_registry_*.py", "test_evaluation_*.py", "test_gate_*.py", "test_rollback_*.py", "cap5_*.py"]` |

## 4. Companion SPEC artifacts — ALL NEW (existing SPEC untouched 0 modify)

| Path | NEW |
|---|---|
| `spec-smdl05-cap5-proof-2026-09-15/SPEC.md` | NEW main |
| + 12 companion files | NEW |
| `.memlog.md` (S-MDL-05) | append-only entries |

## 5. 0 MODIFY (Hard-Red Forbidden Modify Existing File)

DO NOT modify ANY existing files below:
- app/contracts/*.py (0 modify existing contract; ONLY import NOT edit)
- app/registry/*.py (0 modify existing registry code; import only)
- app/gate/* (0 modify)
- app/evaluation/* (0 modify)
- app/rollback/* (0 modify)
- S-MDL-01/02/03/04 existing SPEC files (0 modify; reference only)

## Summary

| Category | Count | Type | Details with exact file names & classification |
|---|---|---|---|
| SPEC artifact NEW | 1 SPEC.md + 12 companion = 13 NEW | Markdown | Companion list: acceptance-criteria, dod, expected-file-changes, hard-red, open-decisions, test-plan, reuse-map, proof-boundary, evidence-chain, preservation-matrix, source-traceability, sp05-self-validation. Matches SPEC L9-L21 companions list. |
| PROD NEW (app/proof/) | 5 .py NEW (split: 1 PACKAGE INIT + 2 PROOF CORE + 1 PROOF PREREQ WRAPPER + 1 AST POSITIVE SUPPORT NOT RUNTIME) | Python | 1) [PACKAGE INIT] `__init__.py`; 2) [PROOF CORE] `cap5_bypass_audit.py` (AST scanner); 3) [PROOF CORE] `cap5_fail_matrix.py` (8 family fail matrix 49 case); 4) [PROOF PREREQ WRAPPER] `cap5_audit_validator.py` (G5/G6/G7 gate/rollback/evidence validators + L3 wrapper, 8 reason codes, NO registry write, stdlib only, NO recalc); 5) [AST POSITIVE SUPPORT NOT RUNTIME IMPORTED] `cap5_dummy_inject_1.py` (AST scanner positive fixture; runtime import=0; behavior contribution=0). Classification legend present in §1 above. All 5 rows explicit §1 allowlist table with YES approve. |
| TEST NEW (tests/cap5/) | 1 conftest.py + 23 test_*.py = 24 NEW .py | Python | Exact 24: conftest fixtures + cap5_01_ast_direct, 02_fsm_forbidden, 03_fsm_allowed, 04_ast_verify, 05_gate_prereq, 06_rollback_prereq, 07_evidence_audit, 08_atomic_write, 09_determinism, 10_replay, 11_fail_closed, 12_event_publish, 13_regression, 14_phase1_negative, 15_contract_schema, 16_registry_storage, 17_registry_crud, 18_evidence_append, 19_predecessor_filters, 20_od_decisions, 21_event_bus, 22_transition_history, 23_integration. |
| CONFIG MODIFY (pyproject.toml L13) | 1 modify (0 elsewhere) — ONLY `python_files` insert `cap5_*.py` pattern | Python TOML | ONLY 1 line exact: `python_files = ["test_*.py", "rollback_*.py", "cap5_*.py"]`. 0 other modify. Stdlib dependencies preserved. |
| EXISTING MODIFY forbidden (S-MDL-01..04) | ABSOLUTE 0. NONE. | 0 byte diff | app/contracts/*.py, app/registry/*.py, app/gate/*, app/evaluation/*, app/rollback/*, S-MDL-01..04 SPEC files = 0 modify. git diff --name-only only lists `pyproject.toml`. Confirmed via audit. |
