---
scope: MVP dashboard API contract surface (MVP only)
status: binding
created: 2026-08-10
updated: 2026-08-10
---

# API — MVP Dashboard Yüzeyi (Sadece v1 Paper/Backtest)

Bu dosya dashboard’ın ihtiyaç duyduğu **sözleşmesini** (route grubu, HTTP method, girdi/çıktı contractları) tanımlar. **Gerçek kod yazılmaz.** Gelecekte gerçek canlı spot trading API’leri bu SPEC’te YOKTUR; MVP hard boundary korunur (bknz OPEN-DECISIONS).

## Kurallar

1. Tüm endpointler:
   - Prefix: `/api/v1`
   - Authentication: MVP development’da opsiyonel ama spec’te zordur. Gelecekte auth spec’i ayrıntılandırılacak (ADN).
   - Response envelope: `{ ok: boolean, data: T | null, error: { code, message, details } | null, correlation_id: ULID }` (zorunlu correlation_id).
2. Gelecekte live-spot execution endpoint’leri bu SPEC’te **bulunmaz**. Yeni bir ayrı SPEC yükseltmesi gerektirir (ve trading gate onayı).
3. WRITE (POST/PUT/DELETE) izni olan 2 tane endpoint vardır. **Tüm diğerleri read-only (GET).**

## Gruplar

### 1. `/system`

| Method | Path | Girdi (QS) | Çıktı contract | Not |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/system/health` | - | `{ status: ok/degraded/unhealthy, components: ComponentHealth[], ts: Instant, run_mode, source_type_global }` | ComponentHealth: `{ module: string, status, reason_codes[] }`. |
| GET | `/api/v1/system/info` | - | Sabit sürümler: backend, contracts_version (1.0.0), feature set, strategy set, active champion list. | |
| **POST** | `/api/v1/system/emergency-stop` | Body: `{ reason: string, operator: string }` | `{ kill_switch_enabled: true, scope: "global", correlation_id }` | **Ayrı izin katmanı**; tüm yeni emirleri durdurur, portfolio zararı satmaz (davranış ADN). Audit log + correlation ile kayıt altına alınır. |

### 2. `/market`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/market/tickers` | symbols[]?, run_mode=paper, source_type? | `{ items: CanonicalEnvelope<MarketTick>[] }` |
| GET | `/api/v1/market/candles` | symbol, timeframe (ADN setinden), start, end | `{ items: CanonicalEnvelope<Candle>[] }` |
| GET | `/api/v1/market/regimes` | symbols[]?, timeframe? | `{ items: CanonicalEnvelope<MarketRegime>[] }` |
| GET | `/api/v1/market/orderbook` | symbol, depth (int, varsayılan ADN) | `CanonicalEnvelope<OrderBookSnapshot>` |
| GET | `/api/v1/market/trades` | symbol, limit | `{ items: CanonicalEnvelope<TradeEvent>[] }` |

### 3. `/opportunities`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/opportunities` | status=actionable/all, score_min?, symbol?, run_mode=paper, limit | `{ items: CanonicalEnvelope<OpportunityScore>[] + strateji sinyali ref + risk_decision_ref (varsa) }` |
| GET | `/api/v1/opportunities/:correlation_id` | - | Detay: sinyal + skor + risk decision zinciri |

### 4. `/regime`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/regime/summary` | timeframe (ADN setinden), symbols[]? | `{ items: { symbol, regime, confidence, scores{} }[]; ts }` |
| GET | `/api/v1/regime/history` | symbol, timeframe, start, end | `{ items: CanonicalEnvelope<MarketRegime>[] }` |

### 5. `/strategies`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/strategies` | - | Strategy meta list (id, version, type, durum: enabled/disabled per run_mode) |
| GET | `/api/v1/strategies/:id/signals` | symbol?, start?, end?, run_mode=paper, limit | `{ items: CanonicalEnvelope<StrategySignal>[] }` |
| GET | `/api/v1/strategies/:id/performance` | window (1d/7d/30d etc) | Metrikler: signals_count, hit_rate, pnl_contrib, drawdown_contrib. |

### 6. `/portfolio`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/portfolio/snapshot` | account_ref (tek), run_mode=paper | `CanonicalEnvelope<PortfolioSnapshot>` |
| GET | `/api/v1/portfolio/positions` | account_ref, run_mode | `{ items: Position[] }` |
| GET | `/api/v1/portfolio/fills` | start, end, symbol?, order_id?, limit | `{ items: CanonicalEnvelope<PaperFill>[] }` |
| GET | `/api/v1/portfolio/orders` | status (created/filled/canceled/rejected), start, end | `{ items: CanonicalEnvelope<PaperOrder>[] }` |

### 7. `/performance`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/performance/equity` | run_mode=paper, account_ref, start, end, timeframe (bar) | `EquityPoint[]: { ts, equity, cash, positions_notional, drawdown_pct }` |
| GET | `/api/v1/performance/summary` | window (1d/7d/30d/all) | `{ sharpe, sortino, max_drawdown_pct, total_return_pct, win_rate, n_trades, total_fees_quote, avg_slippage_bps }` |
| GET | `/api/v1/performance/risk` | window | Daily loss, consecutive losses, exposure history. |

### 8. `/models`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/models` | purpose?, status?, family? | `{ items: ModelVersion[] }` |
| GET | `/api/v1/models/:model_id/versions` | - | `versions[] + lifecycle transitions list` |
| GET | `/api/v1/models/evaluations` | model_id?, version?, dataset_kind? | `{ items: ModelEvaluation[] }` |
| GET | `/api/v1/models/champion-challenger` | window | Son değerlendirme: `{ champion, challenger[], comparisons: champion_challenger_evaluation[] }` |
| GET | `/api/v1/models/lifecycle-events` | start, end, model_id? | `{ items: CanonicalEnvelope<model_lifecycle_transition.v1 payload>[] }` |

### 9. `/risk`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/risk/limits` | run_mode=paper | `LimitsSnapshot (current)` |
| GET | `/api/v1/risk/decisions` | start, end, decision (approved/rejected), reason_code? | `{ items: CanonicalEnvelope<RiskDecision>[] }` |
| GET | `/api/v1/risk/health` | - | Kill switch state, stale data state, per-module health, alert count 24h |
| **POST** | `/api/v1/risk/kill-switch` | Body: `{ scope: "global" \| "per-symbol", symbol?: Symbol, reason: string, operator: string, enabled: boolean }` | `{ scope, state: enabled, reason, correlation_id }` | **Ayrı izinli endpoint.** |

### 10. `/logs`

| Method | Path | QS | Çıktı |
| --- | --- | --- | --- |
| GET | `/api/v1/logs` | correlation_id?, module?, severity (info/warn/error/critical), start, end, limit | `{ items: StructuredLogLine[] }` — correlation/trace/timestamps ile |
| GET | `/api/v1/logs/quality` | symbol?, timeframe?, limit | Son quality bayrakları ve nedenleri (CAP-2 izleme) |

## Yasak / Gelecekteki API’ler (v1’de KAPALI)

Aşağıdakiler bu SPEC’te **tanımlı DEĞİLDİR** ve gelecekte eklense de ayrı kapı gerektirir:
- `/execution/live/*` (gerçek borsa emirleri)
- `/keys/*` (API key yönetimi)
- `/accounts/funding/*` (gerçek para transferi)
- `/risk/limits/write` v.b. kalıcı limit değişikliği (ayarlar ayrı bir yönetim modülü ister)
- `/admin/retire-champion` benzeri doğrudan model state write’ları (sadece registry geçiş komutları üzerinden — ayrı yönetim API’si ADN kapsamındadır)

## Gelecekte açılması muhtemel olanlar ama MVP dışı

- `/backtests/*` (çalıştırma/sonuç yönetim arayüzü; ADN)
- `/paper-config/*` (fill model varsayımları, fee schedule güncelleme; ADN)
- `/auth/*`, `/rbac/*` (authentication/authorization; ADN)
