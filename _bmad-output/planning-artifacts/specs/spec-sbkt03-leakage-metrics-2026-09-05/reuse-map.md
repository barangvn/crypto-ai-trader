# reuse-map.md — S-BKT-03
HIÇBIR ALGORITMA YENIDEN YAZILMAZ. Aşağıdaki componentler SALT OKUNUR veya import edilir.

| Component (Source) | Nasıl REUSE edilir | Dokunulur / SALT-OKUNUR |
|--------------------|---------------------|--------------------------|
| **S-PTR-01 FillEngine** (`app/simulation/paper_fill.py`) | `PaperFill.fill_price/qty_base/fees_quote` trade-level pnl & cost için OKUNUR. | SALT-OKUNUR (hard-red) |
| **S-PTF-01 PositionEngine** (`app/simulation/portfolio.py Position`) | Positions.realized/unrealized/fees/base_qty/avg_price/opened_ts/symbol OKUNUR. Strategy_id/regime lookup via corr chain. | SALT-OKUNUR (hard-red) |
| **S-PTF-02 PortfolioSnapshotEngine** → session cumulative (same file PortfolioSnapshot fields) | `equity_quote` (initial/final), `fees_quote_total`, `drawdown_pct` (session max DD), `peak_equity_quote`, `realized_pnl_quote_24h cumulative`, `positions_snapshot` (groupby strategy/regime) OKUNUR. | SALT-OKUNUR (hard-red) |
| **S-PTF-03 24h Rolling** (if implemented S-PTF-03) → `rolling_return_pct`, `rolling_sharpe_24h` | Runner L158 placeholder = S-PTF-03 son window sample. | SALT-OKUNUR (hard-red) |
| **ReplayClock / assert_no_look_ahead** (`ordering.py` L162-209) | HER stage için IMPORT + CALL (wrapper leakage_asserts.py 6 stage fonksiyonları = 1'er line call ordering fonksiyon). | SALT-OKUNUR (hard-red) — ordering L162-209 unchanged; sadece import + invoke. |
| **S-BKT-02 Cost Model Overrides + injection result sha** (`cost_injection.py` apply result) | `cost_overrides_sha256` metrics metadata field; taker_fee_bps/spread/slip override değerleri → cost impact hesap input. | SALT-OKUNUR (hard-red değil unchanged) — `cost_injection.py` rewrite YOK. |
| **S-BKT-02 WindowSplit canonical numeric compare** (`run_metadata.py` + `walk_forward.py`) | Cross-fold overlap assertion (CAP-L02) S-BKT-02 helper `validate_no_inter_fold_overlap` = reuse exactly; WS `__post_init__` boundary reuse. | SALT-OKUNUR (S-BKT-02 code unchanged) |
| **BacktestPerformanceSummary** (runner.py L149-168) | Placeholder `sharpe_ratio_24h None → float`, `win_rate_pct None → float` populate; YENİ alanlar (sortino, profit_factor, avg_winning, avg_losing, expectancy, trade_stability) aynı dosya SONUNA extend via NEW BacktestPerformanceExtended (frozen=False veya ek alan. backward: eski dataclass still importable; de-serialize eski json still OK via ignore unknown or alias). | EXTEND (non-hard-red); eski field isimleri unchanged; geriye dönük okuma sağla. |
| **MultiFoldBacktestResult** (multi_fold_runner.py L59-97) | `avg_total_return_pct/avg_max_drawdown_pct` mevcut → ek avg Sharpe/Sortino/PF; `per_fold_metrics: list[BacktestPerformanceSummary]` yeni alan. | EXTEND (non-hard-red); canonical sort fold_index ASC preserved. |
| **S-PLN-01 EventBus corr/caus chain** | Metrics result correlation_id = run correlation preserved; causation_id = last PortfolioSnapshot envelope | SALT-OKUNUR (hard-red) |
| **to_sorted_dict / compute_result_sha256 / save+load** (runner.py L140-259) | Deterministic serialization → metrics + leakage artifact SHA reuse; NO rewrite. | EXTEND (new fields auto-sorted via `_dc_to_sorted_dict`) |
| **CAP-1/2/4 existing AST patterns** | Tests 03/09 = existing forbidden pattern list + 6 leakage add-on. | SALT-OKUNUR (existing tests unchanged; SBKT03 NEW tests parallel yazılır) |

---
## Rewrite YAPILMAYACAKLAR (kara-liste)
1. ❌ S-PTR/S-PTF-01/S-PTF-02/S-PTF-03 fill/position/snapshot ANY math (pairs avg price, realized PnL formula, DD peak formula — rewrite YAPMA, reuse field).
2. ❌ FeeModel/SpreadModel/SlippageModel/LatencyModel/PartialFillModel/CostModel YENİ class.
3. ❌ Position/Portfolio contracttan yeni field.
4. ❌ datetime.now / time.time / clock YARATMA — exogenous clock_input.
