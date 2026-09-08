# test-plan.md — S-BKT-03
## Hedef: ≥320 NEW PASS / 0 FAIL / 0 NEW SKIP unless OPEN edge expl (min 0 new skip)

### Test file isimleri (standard S-BKT naming):
1. `tests/backtest/test_sbkt03_01_l01_runtime_leakage.py` → 80 PASS (L01 6 stage injection × 10 cells)
2. `tests/backtest/test_sbkt03_02_l02_l04_fold_failclosed.py` → 60 PASS (L02 intra/inter + L04 fail-closed)
3. `tests/backtest/test_sbkt03_03_l03_ast_leakage_safety.py` → 24 PASS (6 leakage × 4 files; 20 safety repeat)
4. `tests/backtest/test_sbkt03_04_m01_placeholder_populate.py` → 20 PASS (sharpe, win_rate, rolling_24h edge)
5. `tests/backtest/test_sbkt03_05_m02_fr059_core_metrics.py` → 60 PASS (11 metric × 5 scenario)
6. `tests/backtest/test_sbkt03_06_m03_cost_aware.py` → 40 PASS (5 override × 4 symbols + sha)
7. `tests/backtest/test_sbkt03_07_m04_m05_fold_metrics.py` → 36 PASS (per-fold 3 + agg 6 × 4 fixtures)
8. `tests/backtest/test_sbkt03_08_m06_decomposition.py` → 24 PASS (strategy 2 × regime 3 × groups 4)
9. `tests/backtest/test_sbkt03_09_det_safety_regression.py` → 40 PASS (determinism 10x2; AST CAP1-2-4; single-writer; backward SBKT01/02 counts)
*Min total PASS = 80+60+24+20+60+40+36+24+40 = 384 ≥ 320 hedef ✅ (buffer 64)*

---

### 1. Leakage Boundary / Assertion Matrix (test 01 + 02)
Parametrize key matrix (AC-L01, AC-L02, AC-L04):
| Dimension | Values (N) | Coverage |
|-----------|-----------|----------|
| Decision Stage | feature, regime, strategy, opportunity, risk, fill (6) | CAP-L01 every stage |
| Symbol count | 1 (BTC), 2 (BTC+ETH), 5 (mixed) (3) | Multi-symbol aggregation |
| Injection type | input_max=decision+500, input_max=decision+1, input_max=decision-1000 PASS (3) | Fail-closed vs valid boundary |
| Overlap type | train-val / val-test / inter-fold (F0.test.end vs F1.train.start) + adjacent edge=inter_gap_ms exact + 1ms under (5) | AC-L02 5 |
| Canonical numeric 751 vs 3000 + 0-pad 000751 vs 03000 + neg boundary (3) | WS BKT-02 regression |

**Cell count: (6×3×3) + 5×3 + 11 failclosed = ~80+60 cells → PASS 140**

### 2. AST Scan Matrix (test 03)
| Pattern set | Count | Files scanned |
|-------------|-------|---------------|
| Leakage CAP-L03: `datetime.now/time.time/time.sleep/os.urandom/Instant.now/hardcoded_future` | 6 | runner.py, multi_fold_runner.py, cost_injection.py, walk_forward.py, run_metadata.py, leakage_asserts.py (YENİ), metrics_compute (YENİ), pipeline.py = 8 |
| Safety hard: `requests/websocket/redis/pymongo/short=FUTURES/leverage>1/datetime.now/sleep/urandom/fit/partial_fit/optimizer/.keys/.credential/.api_key` | 20 | 8 files + contracts (no) |
| Single Writer: `Position(` / `Portfolio(` pattern (0 match) | 2 | S-BKT-03 new modules only |
**Cell count: 6×8 + 20×8 + 2×2 = 48+160+4=212 → sampled parametric 24 PASS**

### 3. Core Metrics Fixture Matrix (tests 04/05/06/07/08)
Fixture parametrize seed: deterministic synthetic PortfolioSnapshot list:
- T0..T999, 100 trade, 60 winners, 40 losers, known equity curve → Sharpe/Sortino/PF exact hand-calc values
- 5 variant: (a) all winners, (b) all losers (edge: PF None, Sharpe negative), (c) 1 trade only (win_rate=1.0 or 0), (d) 0 trades (all placeholders → None policy), (e) mixed regime×strategy
- Overrides (AC-M03): taker 10/20/50, spread 5/10/20, slip 2/5/10, latency 50/100/200, fill_ratio 1.0/0.5/0.33
- Per-fold fixtures (M04/M05): 5 fold varying return = [-5%, -1%, +2%, +4%, +10%]; avg/compound hand verified

**Cell count: 20+60+40+36+24 = 180 → sampled to 180 cells → PASS 180 (total 384)**

### 4. Determinism & Safety Regression (test 09)
- 10 run × 2 instances (new BacktestRunner()()()()()()) → 20 result SHA == set 1
- SBKT01 222 PASS; SBKT02 547 PASS; non-backtest 3631 PASS — 3 separate subprocess call assertions
- 6 leakage + 6 cost override + artifact roundtrip 5 cases = 17 extra cells
**Total ~40 cells PASS**

---

### Her testte ZORUNLU quality:
- Assertion-less test: 0. (Her testte en az 1 assert; parametrize her cell assert)
- Duplicate cell: 0. (Fixture matrix = unique combination coverage; duplicate hash check empty)
- Count inflation: 0. (Matrix her dimension en 3 deger; no 100x unnecessary padding)
- Fail-closed raise: pytest.raises, exception type + BK_LEAK_* prefix match (no bare raises)
- Determinism: SHA set size == 1 + to_sorted_dict diff == empty (dual assert not one)
