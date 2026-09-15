# S-MDL-03 Test Plan (tests/gate/ — ≥ 240 PASS / 0 FAIL / 0 SKIP target)

Test families CAP ordered T01..T15 (15 files + conftest):

| # | Family | CAP | Scenarios | Assertions |
|---|---|---|---|---|
| T01 | gate_01_weights_load | CAP-9 | 22 (valid + 5 invalid × 4 edge + 3 configs) | weight sum tolerance 1e-8, invalid 4/4 raises |
| T02 | gate_02_normalize_minmax | CAP-10 | 66 (11 keys × 3 samples × 2 dir) | 8dp exact match manual |
| T03 | gate_03_weighted_total | CAP-1 | 31 (27 matrix + 4 edge) | exact 8dp, NaN/bounds |
| T04 | gate_04_thresholds_soft | CAP-2 | 33 (11 × pass/fail/boundary) | correct THRESHOLD_* codes |
| T05 | gate_05_hard_constraints | CAP-3 | 18 (6 hard × 3) | gate=False despite high score |
| T06 | gate_06_reason_codes_sort | CAP-6 | 12 (12 failure mixes + empty pass) | ASC determinism |
| T07 | gate_07_staleness | CAP-7 | 4 (5d/29d/30d boundary/31d stale) | EVAL_STALE reason |
| T08 | gate_08_comparability_consume | CAP-8 | 6 (2 OK / 2 flag / 2 raise) | preserve inner mismatch codes |
| T09 | gate_09_invariant | CAP-5 / C10 | 31 (30 edges + 1 invariant break) | winner↔gate 100% |
| T10 | gate_10_22_reasons | CAP-12 | 22 (parametrize each code) | 22 unique exact 1/22 |
| T11 | gate_11_determinism_10x | CAP-11 | 9 (3 fixtures × 10 × 3 vectors) | len(set)==1 |
| T12 | gate_12_min_approvals | CAP-13 | 5 (0/1/2 / min=2 / None list) | GATE_MIN_APPROVALS_FAIL |
| T13 | gate_13_cce_promotiongate_inject | CAP-4 | 11 (5 pass/ 5 fail / 1 invariant break) | typed dataclass no errors |
| T14 | gate_14_safety_ast_backward | SAFETY/CON | 20 (30 AST / 3 regression / 3 config / deps) | AST 0 forbidden hit; backward PASS |
| T15 | gate_15_smoke | smoke | 1 | imports clean |

Sum: 22+66+31+33+18+12+4+6+31+22+9+5+11+20+1 = 291 scenarios. Structural conditional SKIPS allowed ≤ 51. Expected ≥ 240 PASS.
