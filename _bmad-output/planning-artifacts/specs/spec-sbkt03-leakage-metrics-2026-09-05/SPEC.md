---
companions:
  - acceptance-criteria.md
  - dod.md
  - hard-red.md
  - test-plan.md
  - reuse-map.md
  - risks-open.md
  - expected-file-changes.md
  - safety-regression.md
sources:
  - ../../../implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md
  - ../../../implementation-artifacts/S-BKT-01-deterministic-replay-driven-backtest-engine.md
  - ../../../implementation-artifacts/S-PTF-01-deterministic-position-engine-and-pnl.md
  - ../../../implementation-artifacts/S-PTF-02-deterministic-portfolio-snapshot-equity-and-drawdown.md
  - ../../../implementation-artifacts/S-PTF-03-deterministic-24h-rolling-performance-and-pnl.md
  - ../../../planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md
  - ../../../planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md
slug: sbkt03-leakage-metrics-2026-09-05
story_id: S-BKT-03
epic: E-BKT — Replay-Driven Backtest Engine (Epic 10 L437-440)
checkpoint_baseline: bbade89 (feat: add walk-forward multi-fold and cost model injection)
---

# SPEC.md — S-BKT-03
## Leakage/Look-Ahead Hard Assertions + Source-Backed Performance Metrics

---

## 1. WHY (Neden — Business + Safety Rationale)
E-BKT 3. hikâyesi S-BKT-03: S-BKT-01 (orchestrator) + S-BKT-02 (multi-fold OOS + cost injection) sonrası **iki kritik gap kapatılır**:

1. **Leakage safety gap**: Ordering L162-209 `ReplayClock.assert_instant_accessible()` ve `assert_no_look_ahead(decision_input_max, decision)` **mevcut** ama: (a) HER pipeline stage (feature/regime/strategy/opportunity/risk/execution) **çağrılmıyor** (bug riski); (b) split contamination / cross-fold data flow **runtime exception ile fail-closed değil**; (c) AST leakage guards (datetime.now/sleep vs) mevcut ama future price/volume/signal/fill **enumaration pattern-wide 0 match enforced değil**. Sonuç: sessiz OOS look-ahead → yanlış high-return false positive.
2. **Metrics gap**: BacktestPerformanceSummary runner L149-168 `sharpe_ratio_24h | None`, `win_rate_pct | None`, `rolling_24h_return_pct | None` **placeholder**; FR-059 14 metrikten Sortino, Profit Factor, avg_win/avg_loss/expectancy, strategy/regime decomposition eksik; FR-038 promotion evaluation criteria 10 metrik stabil populate değil; cost override → metrics impact trace edilemiyor.

Güvenilir walk-forward evaluation için **ikisini birden kapatmak ZORUNLU** (FR-039 reject triggers: high return + degraded cost assumptions + weak walk-forward = reject).

---

## 2. CAPABILITIES (WHAT, not how. Each = intent + success.)
Her capability = stable ID (memlog preserved), never reused/re-numbered.

| ID | Intent (WHAT) | Success signal (testable/demonstrable) |
|----|---------------|----------------------------------------|
| **CAP-L01** | Runtime hard assertion: HER decision stage (feature/regime/strategy/opportunity/risk/paper fill) `decision_input_max_ts <= decision_ts && <= ReplayClock.max_allowed_future_ts` ZORUNLU call. | Injected future timestamp (decision=1000, input_max=1500) 100% → `LookAheadLeakageError` BK_LEAK_RUNTIME; failure_reason_code tuple includes code; 5 stage × 2 symbol matrix **all raise**. |
| **CAP-L02** | Train/validation/test intra-fold OOS + inter-fold gap hard assertion (multi-fold). | Any overlap (fold[0].test.end 751 vs fold[1].train.start 3000 canonical numeric WS compare correctly; fold[0].val.start ≤ fold[0].train.end → `BK_LEAK_INTRA_FOLD_OVERLAP` raise. |
| **CAP-L03** | Static/AST leakage-forbidden patterns 0 match (CAP-1 extended for leakage): `datetime.now()`, `time.time()`, `time.sleep()`, `os.urandom`, `Instant.now()`, hardcoded future-date literal > fixture_ts_range. | AST scan 6 pattern × 8 files (runner, multi_fold, cost_inj, walk_for, run_md, ordering, pipeline, SBKT03 new module) = **48/48 0 HIT**; any 1 HIT → test FAIL. |
| **CAP-L04** | Fail-closed leakage: ANY BK_LEAK_* → run terminated; artifact failure_reason_codes non-empty; result_sha deterministic; portfolio/position state **MUTATE 0**. | 12 leakage injection (6 runtime + 4 cross-fold + 2 AST fake): (a) fold result.sha 2 runs ==; (b) initial_equity unchanged (no partial execution); (c) NO PaperFill generated. |
| **CAP-M01** | BacktestPerformanceSummary placeholder populate → real computed. | `sharpe_ratio_24h is not None` (samples≥30); `win_rate_pct is not None` (total_trades≥1); `rolling_24h_return_pct` from S-PTF-03 output; regression old results with None still deserializable (backward). |
| **CAP-M02** | FR-059 + FR-038 **full set** compute from S-PTF-01 (trade-level) + S-PTF-02 (cumulative) + S-PTF-03 (rolling 24h); duplicate PnL YOK. | 10 metrics computed: Sortino, Profit Factor, avg_win, avg_loss, expectancy, trade_stability, total/net return, max DD, Sharpe, fees/slippage; each = independent verifiable sum/delta of upstream fields. |
| **CAP-M03** | Cost-aware (S-BKT-02 override inject) metrics: cost_impact_pct, cost_overrides_sha256, gross vs net return comparison. | taker=10 (default) vs taker=50 override: fee_quote_diff/initial_equity ≈ cost_impact_pct_diff delta ≤1e-6; overrides_sha unique per config; 5 override × 2 symbol = 10 deterministic PASS. |
| **CAP-M04** | Per-fold deterministic metrics: 5 fold → 5 separate BacktestPerformanceSummary, canonical fold_index ASC sort. | 5 fixture (F0..F4), reverse input list → output sorted F0..F4; per-fold_metrics[i].total_return matches single-fold S-BKT-01 run with same events; 10 run → 10 same. |
| **CAP-M05** | Aggregate multi-fold metrics: avg + compound return, avg Sharpe/Sortino/Profit Factor, min/max fold return, canonical SHA. | 2 runner instances × same config → aggregate result.sha identical (set len=1); compound = Π(1+r_i) - 1 exact Decimal; 5 symbol × 10 run = 50 PASS. |
| **CAP-M06** | Strategy × Regime decomposition matrix (trade_count / win_rate / avg_realized_pnl) from S-PTF-02 pos snapshot correlation chain. | 2 strategy × 3 regime = 6 groups, each non-null count correct (compare manual enumeration of fills); groupby sort canonical ASC(strategy_id, regime). |
| **CAP-DET01** | Cross-instance determinism + SHA: same input bundle, same cost overrides, same walk-forward config → 10 run × 2 instances → 10 identical to_sorted_dict, 20 sha256 set size 1. | Float metrics rounded 8dp quantize; Decimal q 8; 20 compare all 0 diff; result file load_backtest_artifact sha verify 20/20. |
| **CAP-SAFE01** | CAP-1/CAP-2/CAP-4 guards, Single Writer AD-7/13/24 preserved **no regression**. | Existing AST 12 forbidden network/credential/DB/short/lev>1/fit patterns + direct Position()/Portfolio() write + RiskGate bypass → 12/12 patterns scan count 0 unchanged. |
| **CAP-REG01** | Backward compat: S-BKT-01 = 222/222; S-BKT-02 ≥619 collected unchanged; 4405 PASS + 5 SKIP regression preserved. | pytest full: (a) old counts (SBKT01 222, non-backtest 3631 PASS/5 SKIP) unchanged; (b) all old artifact sha load unchanged. |

---

## 3. CONSTRAINTS (Design benders)
1. **Hard-red immutability**: hard-red.md listesi %100 korunur (herhangi 1 değişiklik → audit reject).
2. **Zero dep**: pyproject.toml `dependencies=[]` korunur; numpy/pandas/scipy/talib YASAK; stdlib `statistics` (mean/stdev) ALLOWED (builtin).
3. **No algorithm rewrite**: S-PTF-01 (position), S-PTF-02 (snapshot/DD/peak), S-PTR-01 (fill), S-BKT-02 (cost injection, WS compare) **source read-only; wrapper kullanılır**.
4. **No new contract folder class**: contracts/*.py değişmez; yeni metrics fields → runner.py veya multi_fold_runner.py mevcut dataclass extend, contract version preserved unchanged.
5. **Fail-closed first**: Leakage varsayılan RAISE (sessiz info code YOK; whitelist explicit degrade: data_degraded ile leakage değil).
6. **Decimal monetary / float rate clamp**: return/drawdown/sharpe/sortino → `round(x, 8)`; qty/fee/pnl/equity → `Decimal.quantize(Decimal("1e-8"), ROUND_HALF_EVEN)`.
7. **Deterministic sort key**: EVERY list (metrics, groups, overrides) → explicit key ASC (fold_index, strategy_id, symbol, regime) — **NO dict insertion order güvenmesi**.
8. **CAP-1 parity**: backtest module code `datetime.now / time.time / time.sleep / Instant.now / run_mode / source_type if-branch` **AST 0 match**.
9. **Single Writer extend**: Yeni metrics class SADECE snapshotları OKUR ve aggregate eder; PortfolioSnapshotEngine / PositionEngine write path **touch YOK**.
10. **Placeholder backward**: Sharpe/win_rate None → eski test fixture "is None" assertions; S-BKT-03 YENİ test populated fixtures; OLD testler break YAPMAZ (geriye dönük uyum).

---

## 4. NON-GOALS (Açıkça dışı — no downstream fill vacuum)
1. ❌ S-PTF-03 Rolling 24h window hesaplama re-write (rolling_24h_return_pct ALINIR, yeniden hesap YOK).
2. ❌ Yeni FeeModel / SpreadModel / SlippageModel / LatencyModel / PartialFillModel class (S-PTR-01 + S-BKT-02 wrapper korunur).
3. ❌ ML train/fit/partial_fit call; optimizer (FR-030/AD-10 disabled — sonraki S-MDL-02 story).
4. ❌ Model-level champion/challenger metrics decomposition (S-MDL-01/02 sonraki — BU STORY sadece Strategy/Regime).
5. ❌ Frontend dashboard rendering, FastAPI endpoint expose (AD-16 → S-API story sonrası; BU STORY YALNIZ artifact dict + sha + persistence json).
6. ❌ Real exchange / network / credentials / DB / Redis (always v1 hard boundary).
7. ❌ Short / futures / leverage>1 (domain enums long-only korunur, hard safety v1).
8. ❌ Contract version bump — tüm mevcut dataclass field isimleri korur; backward de-serialize S-BKT-01/S-BKT-02 artifacts possible.
9. ❌ SBKT01/02 test dosyalarında assertion güncelleme (NO touch; backward compat preserved).

---

## 5. SUCCESS SIGNAL (Concrete, test/audit against)
*   **Full pytest**: `total PASS ≥ 4725`, `FAIL = 0`, `SKIP ≤ 5`. (Breakdown: baseline 4405 + **≥ 320 S-BKT-03 NEW PASS**.)
*   **Regression preserved**: S-BKT-01 = 222/222; S-BKT-02 collected ≥619 unchanged PASS set; non-backtest 3631 PASS / 5 SKIP unchanged.
*   **Leakage behavioral**: CAP-L01/L02/L04 injection 18/18 → exception BK_LEAK_* prefix; failure_reason_code non-empty; 0 PaperFill, 0 Position mutation (verified wrapper).
*   **Metrics identity**: CAP-M01/M02/M03/M04/M05/M06 × 10 run × 2 instances → to_sorted_dict() diff == empty; SHA set size = 1.
*   **Cost override metrics**: default(10bps) vs override(50bps) → fee_diff/init_equity within 1e-6 of cost_impact_pct diff (5 case PASS).
*   **Safety AST**: CAP-L03 leakage 6 patterns × 8 files (48) + existing 20 safety patterns = **total 68 AST 0 HIT**.
*   **Audit DoD**: dod.md 28 madde 28/28 source evidence.
