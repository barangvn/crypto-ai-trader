# S-MDL-03 Definition of Done (28/28 measurable)

| # | DoD Item | Verify method |
|---|---|---|
| 01 | 290/290 AC all have tests + PASS | pytest 290 AC |
| 02 | Hard-red 0 diff audit 14 scopes | git diff EMPTY |
| 03 | tests/gate/ ≥ 240 PASS / 0 FAIL / 0 SKIP | pytest -q |
| 04 | PromotionGateResult class singleton (1 def) | grep @dataclass.*PromotionGateResult → 1 match |
| 05 | S-CON-02C version constant 1.0.0 unchanged | assert CONTRACT_VERSION == "1.0.0" |
| 06 | 22 reason codes 22/22 parametric tests T10 PASS | T10 22/22 |
| 07 | OD-01 weighted Σw×norm closed, 27 matrix exact 8dp | T03 27/27 |
| 08 | OD-02 min-max closed 66 exact 8dp | T02 66/66 |
| 09 | OD-05 tie 6 crit tie → gate=False + reason WINNER_HINT_INCONCLUSIVE_RERUN | explicit tie test 3 edge |
| 10 | OD-07 stability present w=0.015 renorm; absent skip NO missing | 2 tests |
| 11 | OD-08 fees_quote abs w=0.10; extra fees_per_trade optional 0.005 | 2 tests |
| 12 | Invariant C10 winner=challenger_promoted ↔ gate.passed=True BOTH directions 100% | T09 31/31 |
| 13 | Weight validation 4/4 invalid rules raise correct code | T01 G1 11 miss + 4 others |
| 14 | Hard 6/6 fail gate=False despite high total score | T05 6× high score still False |
| 15 | Staleness 4 cases 31+ days rejected | T07 4/4 |
| 16 | Comparability EVAL_INCOMPARABLE preserved S-MDL-02 mismatch codes | T08 6/6 |
| 17 | Approval min READ ONLY; approval append/write 0 AST writes in app/gate/ | T12 + AST 0 writes |
| 18 | Numeric rounding 8dp; NaN/Inf → fail closed gate=False | 3 NaN edge tests |
| 19 | 10x determinism 3 fixtures SHA len(set)=1 | T11 9 checks |
| 20 | Reason list ASC sorted; gate pass → reasons empty | T06 12/12 |
| 21 | Registry CRUD methods AST 0 CALL in app/gate/*.py (create/update/append/request_transition/...) | AST scan |
| 22 | Forbidden 30 patterns (network/cred/DB/short/lev>1/fit) AST 0 HIT | T14 G14 15 |
| 23 | tests/evaluation 244 PASS 0 regression | pytest tests/evaluation/ |
| 24 | tests/registry 162 PASS 0 regression | pytest tests/registry/ |
| 25 | pyproject.toml dependencies=[] unchanged | grep file |
| 26 | 0 git add/commit/push (ONLY untracked NEW allowlist + spec) | git status untracked pattern match |
| 27 | build_cc_evaluation 50x random → invariant zero failures | fuzz invariant 50 run |
| 28 | build_promotion_gate_result returns exact S-CON-02C typed 3 fields (passed/reasons/thresholds_version) | constructor 3 fields OK no schema error |

TOTAL DoD: 28 items.
