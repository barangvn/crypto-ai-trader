# Definition of Done S-MDL-05 CAP-5 Proof Audit (30 DoD Measurable)

Her DoD maddesi = MEASURABLE (yes/no / sayısal) + source-ref. **30/30 required = teslim için zorunlu.**

| DoD | Rule (Pass = True) | Measurable Check | Source-ref |
|---|---|---|---|
| DoD1 | 0 production code write inside HRC1–HRC14 (14 scope) 0 byte diff | git diff --stat 14 scopes=0 | HR C14 |
| DoD2 | 0 new contract CONTRACT_VERSION (1.0.0 exact preserved) | grep CONTRACT_VERSION output=1.0.0 only | CAP NG4 |
| DoD3 | Stdlib-only: AST import scan new modules = set() (stdlib subset only) | AST forbidden imports = 0 | S-MDL-01 pattern |
| DoD4 | 26 Source-backed headers table (SPEC.md L40-L78) completed 26/26 non-empty source-ref | count non-empty 26/26 | SPEC user explicit 26 |
| DoD5 | 15 CAPabilities each intent+success non-empty; ID stable unique 1..15; 15/15 pass | len(CAPs)=15 intent+success not empty | SP05 Law1 |
| DoD6 | CAP-1 direct_status_assign_scan hit_count = 0 repo-wide (AST); output file bypass_audit_report.md produced with 4 pattern each 0 | grep "direct_status_assign_hit.*=.*0" in report | CAP-1 |
| DoD7 | CAP-2 request_transition calls outside registry=0 AST | grep "non_registry_request_transition_hit.*=.*0" | CAP-2 |
| DoD8 | CAP-3 write primitives outside registry 0 hit | write_primitives_outside_registry_hit=0 | CAP-3 |
| DoD9 | CAP-4 direct mutate 8 families × raise CAP5 direct reason code + no write + no publish; ≥ 64 scenarios PASS (G1 64) | pytest G1 =64 PASS 0 FAIL | CAP-4 |
| DoD10 | CAP-5 FSM forbidden 7+1+5 → 13 negative × correct reject no write; ≥ G2 42 AC all PASS | pytest G2=42 PASS 0 FAIL | CAP-5 |
| DoD11 | CAP-6 allowed 10 edges × 4 assertions G3=40 PASS | pytest G3=40 PASS 0 FAIL | CAP-6 |
| DoD12 | CAP-7 T4 gate prereq 4 scenarios × reject G5=16 PASS | pytest G5=16 PASS 0 FAIL | CAP-7 |
| DoD13 | CAP-8 rollback prereq G6=16 PASS | pytest G6=16 PASS 0 FAIL | CAP-8 |
| DoD14 | CAP-9 audit evidence G7=28 PASS (promote/rollback evidence len ≥1) | pytest G7=28 PASS 0 FAIL | CAP-9 |
| DoD15 | CAP-10 atomic write fault inject G8=12 PASS; no partial artifacts exist after fail | pytest G8=12 PASS 0 FAIL + artifacts final after failure None | CAP-10 |
| DoD16 | CAP-11 determinism 10x 4 sha cols set_size=1 + cross instance = G9=10 PASS | pytest G9=10 PASS 0 FAIL | CAP-11 |
| DoD17 | CAP-12 reproducibility replay 3 fixtures G10=21 PASS | pytest G10=21 PASS 0 FAIL | CAP-12 |
| DoD18 | CAP-13 fail-closed 8-family ≥ 22 negative PASS = G11=22 PASS | pytest G11=22 PASS 0 FAIL | CAP-13 |
| DoD19 | CAP-14 event publish G12=12 PASS (6 valid publish / 6 invalid delta=0) | pytest G12=12 PASS 0 FAIL | CAP-14 |
| DoD20 | CAP-15 regression 4 suite preserved ≥ baseline FAIL=0 each → G13=8 PASS | pytest suite=regression FAIL=0 counts | CAP-15 |
| DoD21 | 11 PROOF artifacts P1-P11 each produced (p1.md, p2.json..p11.md) | ls 11/11 file exists | SPEC L16 header |
| DoD22 | Hard-red 21 HRC summary produced; each HRC checkmark PASS; ANY FAIL → commit block | hard-red_verdict=PASS in report | HR 21 |
| DoD23 | Non-goals NG1-NG17 count=17 explicit in SPEC (NG ≥ 10 minimum) | len(NG) =17 ≥10 | SP05 Law4 |
| DoD24 | Constraints C1-C18 explicit 18 non-vacuous; each contains "NEVER / 0 / ONLY" keyword | grep count=18 | SP05 Law3 bend the design |
| DoD25 | SP05 Law1-8 self-validation coherence = 0 MAJOR + 0 CRITICAL | 0 major 0 critical | SP05 pass1 |
| DoD26 | SP05 Preservation 1:1 = 0 silent drop upstream load-bearing claim; drop_count_wrapper_only ≤3 allowed no semantic | 0 silent drop | SP05 pass2 |
| DoD27 | Expected files allowlist only modify (1 pyproject + 5 new app/proof/ = __init__.py PACKAGE INIT + cap5_bypass_audit.py PROOF CORE + cap5_fail_matrix.py PROOF CORE + cap5_audit_validator.py PROOF PREREQ WRAPPER + cap5_dummy_inject_1.py AST POSITIVE SUPPORT NOT RUNTIME IMPORTED + 24 tests/cap5/ new); 0 modify existing contract.py/gate/eval/rollback/registry.py | diff count existing = 0; actual new prod count = 5 python, test new = 24 python, modify pyproject = 1 line | companion expected-file-changes §1 allowlist table + §Summary canonical classification 5/24/1 |
| DoD28 | Fail-closed 8-family CAP5A-H each have at least 1 negative test; 8/8 families covered | family_coverage 8/8 | CAP-13 |
| DoD29 | 6 Open decisions documented ADN-08/09/10 + OD-04/05/06; 6/6; each non-empty default value explicit | 6/6 default | companion open-decisions |
| DoD30 | AC arithmetic ≥ 260 PASS; actual AC >= 260; 0 FAIL; 0 SKIP structural allow ≤ 5 | actual PASS ≥260 FAIL=0 structural ≤5 | acceptance-criteria.md arithmetic |
