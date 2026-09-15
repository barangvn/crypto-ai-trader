# S-MDL-03 Acceptance Criteria (290 AC testable 1/1)

Groups G1..15.

G1 Weights (T01) 22 AC: G1-01..11 missing 1/11 each raise WEIGHT_MISSING_REQUIRED. G1-12 neg raise. G1-13 w>1 raise. G1-14 sum=0.8 renorm off raise. G1-15 sum=1.00000002 → raise. G1-16 unknown key raise. G1-17 default weights v1 deserializes OK sum renorm = 1.0. G1-18 stability presence w=0.015 OK. G1-19 fees_per_trade w=0.005 OK. G1-20..22 3 overrides OK.

G2 Normalization (T02) 66 AC: 11 keys × 3 samples × 2 dir = 66 exact 8dp match.

G3 Weighted Total (T03) 31 AC: G3-01..27 27 matrix; G3-28 zero weights reject; G3-29 NaN values fail closed gate=False; G3-30 OOB clamped + THRESHOLD code emitted; G3-31 norm bounds hi≤lo invalid NORM_BOUNDS_INVALID.

G4 Soft Thresholds (T04) 33 AC: 11 keys × pass/fail/boundary = 33 correct THRESHOLD_* code.

G5 Hard Constraints (T05) 18 AC: G5-01..06 6 hard fail → gate=False; G5-07..12 6 hard pass still OK; G5-13..18 even weighted_total=0.99 super-high → hard block still False → pass=False PROVEN.

G6 Reason Sort/Empty (T06) 12 AC: 11 failure mixes sorted; G6-12 gate pass → reasons EMPTY [].

G7 Staleness (T07) 4 AC: 5d pass; 29 pass; 30 boundary pass; 31 stale EVAL_STALE.

G8 Comparability (T08) 6 AC: 2 True, 2 flag False, 2 raise catch → EVAL_INCOMPARABLE + preserved mismatch.

G9 Invariant (T09) 31 AC: 30 edge True/False mix; G9-31 inject winner=challenger + gate=False → GateInvariantError raised POST.

G10 22 Reasons (T10) 22 AC: 22 unique codes 1/1 parametric.

G11 10x Determinism (T11) 9 AC: 3 fixtures × 10 × (score/sha/reasons) = 9 checks len(set)==1.

G12 Approvals Read (T12) 5 AC: 0/1/2 approvals min=1; min=2 count=1; None list len 0 → fail.

G13 CCE Contract (T13) 11 AC: 5 pass gate valid CCE; 5 fail valid CCE with passed=False reasons[]; G13-11 inject winner=challenger gate=False error raise.

G14 Safety/AST/Regression (T14) 20 AC: G14-01..15 15 forbidden patterns 0 HIT; G14-16 tests/evaluation still 244 PASS; G14-17 tests/registry 162 PASS; G14-18 SBKT01 222 SBKT03 332 unchanged; G14-19 deps=[]; G14-20 registry write methods 0 AST CALL under app/gate/.

G15 Smoke (T15) 1 AC: import gate public exports OK.

TOTAL = 22+66+31+33+18+12+4+6+31+22+9+5+11+20+1 = **290 AC**.
