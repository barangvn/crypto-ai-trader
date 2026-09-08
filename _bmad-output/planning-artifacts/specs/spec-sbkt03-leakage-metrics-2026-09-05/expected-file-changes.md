# expected-file-changes.md — S-BKT-03
Toplam: **3 production (extend) + 2 production YENİ + 9 test YENİ** = 14 dosya. Hard-red 0 changes.

## Production Changes (Non-hard-red, EXTEND or NEW)
| # | Path | Tür | Ne değişir / neden | HARD-RED? | AC/DoD karşılığı |
|---|------|-----|-------------------|-----------|------------------|
| P1 | `app/backtest/runner.py` | EXTEND (modify) | L149-168 BacktestPerformanceSummary: (a) placeholder None alanları → compute before L703 return (sharpe/win_rate); (b) sortino_ratio, profit_factor, avg_winning_trade_quote, avg_losing_trade_quote, expectancy_quote, trade_stability_idx yeni alanlar; (c) BacktestRunResult performance + failure_reason_codes BK_LEAK_* code list append when leakage; (d) L640-720 performance_summary hesap adımları → S-PTF-01/02/03 reuse. NEW helper `_compute_extended_performance(snapshots: list, fills: list, initial_eq, cost_assumptions)` pure. | ❌ NO (runner approved non-hard-red S-BKT-02 already M) | CAP-M01/M02/M03 CAP-L04 DET01 |
| P2 | `app/backtest/multi_fold_runner.py` | EXTEND (modify) | (a) `per_fold_metrics: list[BacktestPerformanceSummary]` (fold_index ASC sorted); (b) aggregate: avg_sharpe_24h, avg_sortino, avg_profit_factor, compound_return_pct, min_fold_return_pct, max_fold_return_pct; (c) cost_overrides_sha256 metadata propagate; (d) aggregate leakage fail if any fold failed → aggregate failure codes union. | ❌ NO (new file ?? S-BKT-02 kurulum sonrası extend) | CAP-M03/M04/M05 CAP-L04 |
| P3 | `app/backtest/leakage_asserts.py` | YENİ | HER stage 6 wrapper func: `enforce_leakage_feature(ctx)` / enforce_regime / enforce_strategy / enforce_opportunity / enforce_risk / enforce_fill. HER func → `ordering.assert_no_look_ahead(decision_ts=ctx.clock.decision_ts, decision_input_max_ts=stage_max, clock=ctx.clock)`; returns None → pass; raises → propagate BK_LEAK_RUNTIME_STAGE code prefix; per-fail failure_reason append via ctx.backref. Pipeline stage callback endpoints ile çağrılır (pipeline.py HARD-RED dokunulmaz; runner.run stage sonu callback hook NON-HARD-RED add). | ❌ NO (new file) | CAP-L01/L04 |
| P4 | `app/backtest/metrics_compute.py` | YENİ | Pure helpers: (a) `_compute_trade_level(fills: list[PaperFill], positions: list[Position])` → winners/losers list; (b) `_compute_sharpe_sortino(equity_curve: list[Decimal], rf=0.0, freq_min=1)` → round8 float; (c) `_compute_profit_factor(gross_win, gross_loss)` → None or float; (d) `_compute_expectancy(win_rate, avg_win, loss_rate, avg_loss)` → Decimal; (e) `_group_strategy_regime(positions: list[Position], correlation_lookup: Callable)` → sorted (strategy_id, regime) groups. TÜM helpers OKUR positions/fills, S-PTF alanları SALTOKUR, yeniden hesap YOK. | ❌ NO (new file) | CAP-M01/M02/M06 |
| P5 | `app/backtest/pipeline.py` **stage callbacks** (optional minimal change) | EXTEND (minimal) | Eğer stage sonu callback hook MEVCUT DEĞİL → stage 3/4/5/6/7/8 sonu leakage enforce çağrısı 1 line func call; stage body dokunulmaz. Callback hook add non-hard-red (stage ordering unchanged; CAP-4 gate preserved). | ❌ NO (minimum touch; approved if needed) | CAP-L01 |

*P5 opsiyonel: eğer runner.run her stage sonu callback mevcut ise pipeline change 0 bytes. Audit NOT reject changes if body order unchanged.*

## Test Files (NEW — 9 dosya)
| T1 | `tests/backtest/test_sbkt03_01_l01_runtime_leakage.py` | YENİ 80 PASS parametrize 6 stage × symbols × injection boundary |
| T2 | `tests/backtest/test_sbkt03_02_l02_l04_fold_failclosed.py` | YENİ 60 PASS intra/inter overlap + fail-closed mutation zero |
| T3 | `tests/backtest/test_sbkt03_03_l03_ast_leakage_safety.py` | YENİ 24 PASS AST 48+20+2 pattern scan |
| T4 | `tests/backtest/test_sbkt03_04_m01_placeholder_populate.py` | YENİ 20 PASS sharpe/win_rate/rolling_24h |
| T5 | `tests/backtest/test_sbkt03_05_m02_fr059_core_metrics.py` | YENİ 60 PASS 11 FR metrics × fixtures |
| T6 | `tests/backtest/test_sbkt03_06_m03_cost_aware.py` | YENİ 40 PASS cost override impact + sha |
| T7 | `tests/backtest/test_sbkt03_07_m04_m05_fold_metrics.py` | YENİ 36 PASS per/aggregate |
| T8 | `tests/backtest/test_sbkt03_08_m06_decomposition.py` | YENİ 24 PASS strategy regime group |
| T9 | `tests/backtest/test_sbkt03_09_det_safety_regression.py` | YENİ 40 PASS determinism/safety/backward counts |

---
### KESINLIKLE DEGISMEYECEKLER (byte diff 0):
- hard-red.md listesi 100% unchanged
- S-PTR-01/02/03 simulation files — 0 byte
- contracts/*, features/*, regime/*, strategies/*, opportunity/*, risk/* — 0 byte
- ordering.py (ReplayClock implementation) — 0 byte
- pipeline.py stage ordering unchanged; P5 optional only if hook yok
- event_bus.py — 0 byte
- SBKT01/SBKT02 test files — 0 byte
- pyproject.toml dependencies=[] — 0 byte
