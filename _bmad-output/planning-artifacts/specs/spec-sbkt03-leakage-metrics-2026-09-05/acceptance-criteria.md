# acceptance-criteria.md — S-BKT-03
Her AC = source-backed FR / AD / EPICS claim. PASS = evidence with pytest id + source ref.

## L. Leakage / Look-Ahead (18 AC)
| AC | Source | What PASS means | Test id prefix |
|----|--------|-----------------|----------------|
| AC-L01-01 | FR-043 / ARCH L442 | Runtime `assert_no_look_ahead(feature) -> ts=1000, max_input=1500` raises LookAheadLeakageError BK_LEAK_RUNTIME_FEATURE | `sbkt03_l01_feature` |
| AC-L01-02 | FR-043 | Runtime assert_no_look_ahead(regime) injected future → raise BK_LEAK_RUNTIME_REGIME | `sbkt03_l01_regime` |
| AC-L01-03 | FR-043 | Runtime assert_no_look_ahead(strategy) injected future → raise BK_LEAK_RUNTIME_STRATEGY | `sbkt03_l01_strategy` |
| AC-L01-04 | FR-043 | Runtime assert_no_look_ahead(opportunity) → raise BK_LEAK_RUNTIME_OPPORTUNITY | `sbkt03_l01_opportunity` |
| AC-L01-05 | FR-043 | Runtime assert_no_look_ahead(risk) → raise BK_LEAK_RUNTIME_RISK | `sbkt03_l01_risk` |
| AC-L01-06 | FR-043 | Runtime assert_no_look_ahead(fill) → raise BK_LEAK_RUNTIME_FILL | `sbkt03_l01_fill` |
| AC-L01-07 | CAP-L01, S-BKT-01-06 backward | Valid (decision=2000, input_max=1800) → NO raise, run continues, result success | `sbkt03_l01_pass_*` |
| AC-L01-08 | ordering L195-209 | `clock.assert_instant_accessible` ts > max → BK_LEAK_CLOCK raise + code tuple | `sbkt03_l01_clock_*` |
| AC-L02-01 | EPICS L438 / FR-042 | Intra-fold overlap: val.start <= train.end → raise BK_LEAK_INTRA_FOLD_TRAIN_VAL | `sbkt03_l02_intra_tv` |
| AC-L02-02 | FR-042 | Intra-fold overlap: test.start <= val.end → raise BK_LEAK_INTRA_FOLD_VAL_TEST | `sbkt03_l02_intra_vt` |
| AC-L02-03 | S-BKT-02 WS canonical | Inter-fold overlap: fold[1].train.start <= fold[0].test.end → BK_LEAK_INTER_FOLD_OVERLAP raise | `sbkt03_l02_inter` |
| AC-L02-04 | S-BKT-02 numeric | Unequal length 751 vs 3000 no false overlap → NO raise (regression for BKT-02) | `sbkt03_l02_reg_751_3000` |
| AC-L02-05 | AD-20 canonical | Fold N+1 starts EXACTLY fold.test.end + inter_gap_ms = edge case NO raise (adjacent OK) | `sbkt03_l02_edge_adjacent` |
| AC-L03-01 | CAP-1 ext L | AST 6 leakage patterns (datetime.now/time.time/sleep/urandom/Instant.now/hard_future_literal) 6×8=48 0 HIT | `sbkt03_l03_ast_*` |
| AC-L03-02 | CAP-1 parity | `run_mode` / `source_type` if/elif/Attribute AST 0 match | `sbkt03_l03_ast_branch` |
| AC-L04-01 | Fail-closed AD-19 | Any BK_LEAK_* → 100% result.failure_reason_codes ≥1 | `sbkt03_l04_failcode` |
| AC-L04-02 | Single Writer | Leakage raise: initial_equity == final_equity (no partial fill/position mutation) | `sbkt03_l04_no_mut` |
| AC-L04-03 | Paper execution | Leakage raise: result.counts.fill_count == 0; result.counts.order_count <= gate_pass (all blocked) | `sbkt03_l04_no_order` |

## M. Performance Metrics (33 AC) — FR-059 + FR-038 source-backed
| AC | Source | What PASS means | Test id prefix |
|----|--------|-----------------|----------------|
| AC-M01-01 | runner L157 placeholder | Sharpe 24h computed (samples>=30, rolling_24h return array stdev>0) → is not None; float round8 | `sbkt03_m01_sharpe` |
| AC-M01-02 | runner L159 placeholder | Win rate = winning_trades / total_trades; 10 trades → value computed; 0 trades → None (no div0) | `sbkt03_m01_winrate` |
| AC-M01-03 | runner L158 placeholder | Rolling 24h return sourced from S-PTF-03 (no re-calc) → matches rolling_24h return snapshot last | `sbkt03_m01_rolling24` |
| AC-M02-01 | FR-059 Sortino | Sortino = (mean_excess / downside_std) stdev_negative_only; no trades → None | `sbkt03_m02_sortino` |
| AC-M02-02 | FR-038 Profit Factor | Profit Factor = gross_win / abs(gross_loss); loss=0 → PF=inf→None capped policy explicit | `sbkt03_m02_pf` |
| AC-M02-03 | FR-059 avg win/loss | Avg winning trade = total_win_pnl / winning_trades; Avg losing = total_loss / losing | `sbkt03_m02_avg_wl` |
| AC-M02-04 | expectancy formula | Expectancy = (win_rate * avg_win) - (loss_rate * abs(avg_loss)) computed | `sbkt03_m02_expect` |
| AC-M02-05 | FR-038 stability | Trade stability = 1 if stddev(per_trade_pnl) < 2*mean, else 0 (OPEN decision default) | `sbkt03_m02_stab` |
| AC-M02-06 | FR-059 total return | Total return = (final_eq - initial_eq) / initial_eq * 100; matches runner L657 | `sbkt03_m02_totalret` |
| AC-M02-07 | FR-059 net return | Net return = gross - total_fees_quote / initial_eq * 100; delta verify | `sbkt03_m02_netret` |
| AC-M02-08 | FR-059 max DD | Max drawdown matches S-PTF-02 session peak; no rewrite | `sbkt03_m02_dd` |
| AC-M02-09 | FR-059 trade count | total_trades == winning_trades + losing_trades (signed) | `sbkt03_m02_count` |
| AC-M02-10 | FR-059 fees | total_fees_quote matches S-PTF-02 pos sum → double-count 0 | `sbkt03_m02_fees` |
| AC-M02-11 | FR-059 slippage / latency impact | assumptions field in metadata; metric cost_impact include slip bps × notional / initial | `sbkt03_m02_slip_lat` |
| AC-M03-01 | S-BKT-02 cost override taker=10→50 | fee_delta = result.fees(taker50) - fees(taker10); cost_impact_pct_diff ≈ fee_delta / initial_eq × 100; delta <=1e-6 | `sbkt03_m03_taker_fee` |
| AC-M03-02 | S-BKT-02 spread override | default spread=5bps vs spread=20bps → gross_notional × spread_bps_diff / 10000 == fees impact delta | `sbkt03_m03_spread` |
| AC-M03-03 | S-BKT-02 slippage override | slip=2→10 bps → slip impact diff compute matches metric cost_impact delta | `sbkt03_m03_slip` |
| AC-M03-04 | S-BKT-02 latency override | latency=50→200ms → fill_price worse; metrics net return delta monotonic (higher lat=worse) | `sbkt03_m03_latency` |
| AC-M03-05 | S-BKT-02 partial fill ratio | ratio 1.0 → 0.33 → trade count + notional delta; metrics aggregate fill_count monotonic decrease | `sbkt03_m03_partial` |
| AC-M03-06 | cost overrides sha | cost_overrides_sha256 per config unique; same config → same sha (6 case) | `sbkt03_m03_sha_cost` |
| AC-M04-01 | per-fold metrics | 5 fold → len(per_fold_metrics) == 5 | `sbkt03_m04_len` |
| AC-M04-02 | canonical per-fold order | Input folds [F4,F3,F2,F1,F0] → output per_fold_metrics order = F0..F4 | `sbkt03_m04_sort` |
| AC-M04-03 | per-fold == single-fold | Fold[2] metrics == S-BKT-01 single run with same event range (SHA256 match) | `sbkt03_m04_equality` |
| AC-M05-01 | aggregate avg return | avg_total_return = mean(F0..F4 total_return) | `sbkt03_m05_avg_ret` |
| AC-M05-02 | aggregate avg DD | avg_max_drawdown = mean(F0..F4 max_dd) (matches MFR L66 existing) | `sbkt03_m05_avg_dd` |
| AC-M05-03 | aggregate avg Sharpe/Sortino/PF | mean computed; None fold → exclude from mean not zero inject | `sbkt03_m05_avg_sharpe_sortino_pf` |
| AC-M05-04 | compound return | compound = Π(1 + r_i/100) - 1 exact Decimal | `sbkt03_m05_compound` |
| AC-M05-05 | min/max fold | min_return = min(F0..F4); max_return = max(F0..F4) | `sbkt03_m05_minmax` |
| AC-M05-06 | aggregate SHA determinism | 2 instance × 10 run → set(sha) len=1 | `sbkt03_m05_sha` |
| AC-M06-01 | Strategy decomposition | 2 strategy → strategy group trade_count sum == total_trades | `sbkt03_m06_strat_total` |
| AC-M06-02 | Regime decomposition | 3 regime → regime group sum trade_count == total_trades | `sbkt03_m06_regime_total` |
| AC-M06-03 | Cross (strategy×regime) | 6 groups, each group win_rate = group.winners / group.count | `sbkt03_m06_grouped_winrate` |
| AC-M06-04 | Canonical group sort | [(strat A,B / reg LOW,HIGH)] → sorted(strategy, regime) deterministic | `sbkt03_m06_sort` |
| AC-DET01 | 10 run × 2 instance cross-determinism | 20 result.to_sorted_dict diff == {}; 20 sha set len=1 | `sbkt03_det_10x2` |

Total AC count: **18 + 33 = 51 AC** (her AC ≥ 2 parametrize case = minimum 102 test cells; 320+ target PASS expectation reachable).
