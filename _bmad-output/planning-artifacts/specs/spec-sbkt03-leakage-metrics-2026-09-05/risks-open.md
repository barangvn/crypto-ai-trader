# risks-open.md — S-BKT-03
## OPEN DECISIONS (Çözülmemiş, IMP aşamasında user onayı ile kapatılır; 9 kalem)

### Açık:
| # | OPEN DECISION | Önerilen Default (doğrulama yok ise uygulanır) | Risk | Kaynak |
|---|---------------|-----------------------------------------------|------|--------|
| OD-01 | Trade stability index (FR-038): "stability" tanımı float threshold [0,1] mi yoksa binary 1/0? Policy: **1 if stddev(per_trade_pnl) < 2×\|mean\| else 0**. Edge: mean=0? → 1 (flat=stable). | LOW — placeholder sonradan değiştirilebilir (audit NOT reject) | FR-038 |
| OD-02 | Sharpe / Sortino rolling sample frequency: S-BKT "1 minute candle" default → 1440 samples/gün? Veya PortfolioSnapshot frekans? Policy **use S-PTF-03 rolling 24h sample list if available; else fallback snapshot list compute**. | MEDIUM — insufficient sample → None döner (sessiz 0 YOK). OD-03 relation. | AD-20 determinism |
| OD-03 | Minimum samples Sharpe/Sortino: min N=? Önerilen **N=30**; N<30 → None (insufficient_samples info code). Raise veya None? Policy **None + info code included NOT fail-closed leakage raise**. | LOW | runner L157 placeholder backward |
| OD-04 | Profit Factor: gross_loss == 0 → PF = None veya float("inf")? Policy **None + info_code PROFIT_FACTOR_NO_LOSSES**. JSON serialize "inf" sorunundan kaçınır. | LOW (JSON serialization bug risk) | FR-038 |
| OD-05 | Strategy/Regime decomposition Position alanları var mı? Position contractta strategy_id/regime field **yok ise** → How lookup? Policy **via correlation_id → upstream StrategySignal correlation chain lookup wrapper**. Empty strategy_id → group "unknown". | MEDIUM — groupby misses → decomposition yanıltıcı; audit "unknown" grubunun oranı <%5 olmalı. | FR-028 FR-059 |
| OD-06 | None-valued fold (1 fold sharpe=None) aggregate avg: exclude (NaN-policy) or 0? Policy **EXCLUDE from mean; info_code METRICS_NA_EXCLUDED_AVG**. | LOW | CAP-M05 |
| OD-07 | BacktestPerformanceSummary (runner L149-168) frozen=True? Eğer frozen ise → yeni alanlar ne? Yeni class `BacktestPerformanceSummaryV2` veya tuple? Policy **yeni alanlar runner L148-169 extend (non-hard-red; runner approved non-hard-red). Eğer frozen=True → runner L149 satırı değiştirilmez, yerine V2 dataclass runner.py SONUNA yazılır (geriye dönük).** | MEDIUM (backward compat artifact de-serialize eski json) | runner L149 |
| OD-08 | S-PTF-03 build_rolling_24h henüz implemente OLMADI ise (geliştirme takvimi) → rolling_24h_return_pct policy? **None → info CODE ROLLING_NOT_AVAILABLE; fail-closed raise YOK**. | MEDIUM | S-PTF-03 story status |
| OD-09 | CAP-L03 hardcoded future-date literal detection AST: fixtures/data "2025-01-01" vs actual test data "2024-06-01" — false positive? Policy **sadece backtest/module gömülü date stringleri scan; test fixture json data strings scan YOK**. | LOW (false positive AST reject) | CAP-L03 |

---
## Risks (IMP veya Audit aşaması blockers olabilir)
| Risk | Olasılık | Etki | Azaltma |
|------|----------|------|---------|
| BacktestPerformanceSummary frozen=True → extend edilemez, eski artifact deserialize kırılır | MEDIUM | HIGH | V2 dataclass runner.py sonuna yaz; backward converter = old → new dict copy |
| Sharpe/Sortino floating determinizm (30 run → 8dp mismatch) | MEDIUM | MEDIUM | Tüm float metrics `round(x, 8)`; assertAlmostEqual places=8 not exact == |
| Position strategy_id/regime alanı BULUNAMAZ → decomposition group = 100% unknown | HIGH | MEDIUM → audit NOT REJECT sadece warning | OD-05 correlation wrapper; decomposition AC optional hard-fail değil "retain unknown group ok accept" |
| Cost impact slippage/latency → metrics delta monotonic değil (non-linear) | LOW | LOW | AC-M03-04 monotonic değilse → "daha kötse de olur equal geçer" → assertion >=0 not exact match |
| Leakage raise on degraded data (stale) → false positive leakage BK_LEAK | MEDIUM → breaks production runs | HIGH | AC-L07 valid pass: data_degraded info code != leakage; leakage exception RAISE if actual ts > clock, not quality |
