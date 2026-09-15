# S-MDL-04 Definition of Done (30/30 measurable)

| # | DoD Item | Verify method | Kaynak Referans |
|---|---|---|---|
| 01 | 272/272 AC ALL have test cases + PASS | pytest 272 AC matrix cell | AC companion G1-G18 actual count G1+G2+...+G18=272 |
| 02 | Hard-red 20 scopes 0 byte diff | git diff EMPTY for 20 paths | hard-red.md 20 scope |
| 03 | tests/rollback/ ≥ 242 PASS / 0 FAIL / 0 SKIP | pytest -q tests/rollback/ | Coverage Target SPEC §20 (arithmetic: 272 total - 30 skip max = 242) |
| 04 | 17 fail-closed reason codes 17/17 parametric T13 PASS unique exact | T13 17/17 code list identical | CAP-13 SPEC §13 code (FIX-02: 18→17 PREDECESSOR_COMPATIBILITY_MISMATCH unsourced removed) |
| 05 | S-CON-02C CONTRACT_VERSION == "1.0.0" unchanged; no new contract file | grep + AST scan 0 new @dataclass under app/contracts/ except existing | Constraints C5 |
| 06 | 17 reason codes distinct; empty reason list only eligible=True (G8) | T08 15 AC PASS | CAP-8 SPEC |
| 07 | 25 Eligibility G1 AC: E1-E5 each pass/fail validated with correct distinct reason codes | T01 25/25 PASS | CAP-1 + 20 Header §2 |
| 08 | 3 Trigger enum + invalid reject G2 11 AC trigger value pass/reject exact | T02 11/11 PASS | CAP-2 + Header §1 |
| 09 | EV1-EV6 G3 20 AC min evidence + 11 delta keys exact set match ModelEvaluation required | T03 20/20 PASS | CAP-3 + Header §4 |
| 10 | Approval min READONLY G4 15 AC: min count correct + AST append 0 | T04 15/15 PASS | CAP-4 + Header §5 |
| 11 | Staleness 30d default + integrity G5 18 AC: STALE_DEGRADATION_WINDOW + INTEGRITY_MISMATCH reasons emit correct | T05 18/18 PASS | CAP-5 + Header §6 |
| 12 | Missing Target 5 reasons G6 15 AC: M1-M5 distinct code + dedup correct | T06 15/15 PASS | CAP-6 + Header §7 |
| 13 | Target selection 1:1 predecessor G7 10 AC: immediate predecessor selected, multi-chain default skip >1 depth (FIX-02: compat mismatch AC unsourced removed) | T07 10/10 PASS | CAP-7 + Header §3 |
| 14 | Determinism 3 fixtures×10×8 tuple len(set)==1 G9 25 AC + cross-engine 2 instances identical (FIX-01: 3fixtures×8item=24+1cross=25 actual) | T09 25/25 PASS | CAP-9 + Header §9 |
| 15 | Audit payload 12-field G10 18 AC: corr/caus preserved, occurred_ts=evidence_ts, command_name literal, AST 0 publish/0 transition_call | T10 18/18 PASS | CAP-10 + Header §10 |
| 16 | Registry READONLY AST G11 18 AC: 3 allowed GET used; 7 forbidden 0; 4 write prim 0 | T11 18/18 PASS | CAP-11 + Header §11 |
| 17 | S-MDL-03 integration border G12 15 AC: only 2 reads; PromotionGate AST 0 call; 14 hard-red diff 0 | T12 15/15 PASS | CAP-12 + Header §12 |
| 18 | F5 bypass Champion→Challenger literal G16 10 AC: to_status=challenger NEVER assigned by rollback | T16 10/10 PASS | Constraints C12 + NG11 |
| 19 | Staleness / integrity combined: stale + corrupt 2 reasons ASC sorted (G8) | T05+T08 | CAP-5/CAP-8 |
| 20 | Numeric rule Decimal 1e-8 ROUND_HALF_EVEN / Float 8dp / int exact (inherit S-CON-02C C6) | pytest roundtrip 6 fixtures exact | Constraints C6 |
| 21 | Forbidden 20 AST safety patterns (network/cred/DB/short/lev/fit/live) 0 HIT (G15) | T15 20/20 PASS | Constraints C9 + NG8/9/10 |
| 22 | CAP-1 parity: 0 run_mode/source_type if-branch + datetime.now() call under app/rollback | AST scan 0 | Constraints C10 |
| 23 | 0 git add/commit/push executed; ONLY untracked new files on allowlist (app/rollback/, tests/rollback/, THIS spec folder) | git status expected pattern match untracked only | User hard-rule NO GIT |
| 24 | Regression: tests/evaluation ≥244 PASS; tests/gate ≥220 PASS; tests/registry ≥162 PASS; SBKT01 ≥222; SBKT03 ≥332 — FAIL=0 collected counts unchanged | pytest regression run unchanged collected | G18 smoke |
| 25 | pyproject.toml dependencies=[] unchanged line; 0 new dep | grep file exact | Constraints C2 |
| 26 | Open decisions 8 ADN documented in open-decisions.md; NONE silently hardcoded default without ADN flag | grep ADN tag each decision | open-decisions.md 8 |
| 27 | SP05 self-validation 2-pass 0 MAJOR violation (coherence L1-6 + preservation L7 + lean L8); CAP law 8/8 | .memlog.md 2-pass entry documented | SP05 self-val 8 law |
| 28 | Hard-red new HRC15-20: AST request_transition=0 / run_mode branch=0 / auto_rollback fn=0 / champion_challenger direct literal=0 / write to disk=0 / weighted Σ compute=0 — 6 checks | AST scan 6 = 0 | HRC15-20 hard-red.md |
| 29 | Thresholds version mismatch THRESHOLDS_VERSION_MISMATCH reason code emit (G17 8 AC PASS) | T17 8/8 PASS | CAP-13 code list |
| 30 | Expected file count matches expected-file-changes.md allowlist NEW files count; 0 modification to EXISTING file outside allowlist (except this spec folder). No production code written YET (implementation later story); ONLY spec artifacts written NOW | ls count exact match + git diff --name-only HEAD empty except spec folder untracked new | expected-file-changes.md + NO GIT + NO CODE |

---
Total DoD = **30/30 measurable**.
