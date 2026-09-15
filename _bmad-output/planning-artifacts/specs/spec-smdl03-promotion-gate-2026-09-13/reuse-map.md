# S-MDL-03 Reuse Map (reuse / do not reimplement)

| Source | Reused content | Used where | DO NOT REIMPLEMENT | Owner (no touch) |
|---|---|---|---|---|
| S-CON-02C app/contracts/model.py | PromotionGateResult, ChampionChallengerEvaluation, CCWinnerEnum, 11 required keys, ModelRef, status, approval_refs | builder/engine/__init__ typed output | Any duplicate class, contract new field, version bump | E-CON Epic2 |
| S-CON-02C numeric rules | Decimal 1e-8 ROUND_HALF_EVEN, Float 8dp, int/bool exact | weights/thresholds | Different precision or rounding mode | E-CON |
| S-MDL-02 app/evaluation/ | CCE payload wrapper, metric deltas, comparability flag, evidence_refs, direction table, build_cce_payload, CRITICAL_DELTA_KEYS_ORDERED | engine consume payload; NEVER re-evaluate | Recompute PnL/DD/Sharpe/cost/fill/portfolio from raw fills | E-MDL S-MDL-02 |
| S-MDL-01 app/registry/registry.py | get_model_version(approval_refs count READ), predecessor_ref (READ) | engine CAP-13 | Any create/update/append/transition/set_predecessor mutation | E-MDL S-MDL-01 single writer |
| S-BKT-03 metrics aggregate | Per-fold struct, Strategy×Regime matrix, compound Π(1+r)-1, 1/N mean Sharpe/Sortino/PF inside S-MDL-02 payload | thresholds weights | Fold compound re-aggregation; regime matrix re-compute | E-BKT S-BKT-03 |
| S-BKT-02 cost version | cost_config_version inside evidence_refs | engine version mismatch gate | Fee schedule/slippage/spread/latency/partial-fill | E-BKT S-BKT-02 |
| PRD FR-038/039 / AC-06/07 | Default weights, hard blocks, soft thresholds defaults | weights.py thresholds.py v1 default config | Keyfi sayısal uydurma (invented numbers) | PRD owner |
| LIFECYCLE T3 / T4 FSM preconditions | Paper→Challenger gate.pass=true; T4 approval min 1; rollback prep req | engine builder CAP-7/13/8 | New FSM states; new allowed transitions | E-MDL CAP-5 |
| CPython stdlib | dataclasses, StrEnum, Decimal, hashlib sha256, json sort_keys, re, pathlib, statistics.mean | all gate files | Any 3rd party non-stdlib import numpy/pandas/sklearn/ccxt/requests | Python stdlib |
