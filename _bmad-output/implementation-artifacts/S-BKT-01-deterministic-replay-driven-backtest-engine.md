# S-BKT-01 — Deterministic Replay-Driven Backtest Engine

| Alan | Değer |
|------|-------|
| **Story ID** | S-BKT-01 |
| **Epic** | E-BKT (Epic 10 — Replay-Driven Backtest Engine) |
| **Durum** | READY-FOR-DEV |
| **Baseline Commit** | `0d5515d` feat: implement deterministic 24h rolling performance |
| **Önceki Story** | S-PTF-03 |
| **Sonraki Story** | S-BKT-02 (OOS) |
| **Contract Version** | 1.0.0 (KORUNUR — Yeni canonical contract YOK) |
| **pyproject.toml deps** | `[]` (KORUNUR — Stdlib-only) |
| **Kural** | Uygulama kodu YAZILMAZ (create-story fazı sadece spec) |
| **Kural** | Git commit YAPILMAZ |
| **Kural** | Başka hikayeye GEÇİLMEZ |

---

## 1. BDD User Story + Amaç + İş Değeri

### BDD Format
```
ÖZELLİK: Deterministic Replay-Driven Backtest Engine
  Sistemin research sahibi (quant/trader) olarak
  Replay Bundle fixture verisini baştan sona deterministic şekilde backtest etmek istiyorum
  Böylece strategy/feature/risk kararlarını CANLI PARA RISKSİZ olarak doğrulayabilir,
  walk-forward foundation'ı kurabilir ve gelecekte OOS evaluation yapabilirim.

  SENARYO: Happy Path — Tek sembol 30 günlük fixture ile full pipeline backtest
    VERİLDİĞİNDE: BTCUSDT 30 günlük 1m replay fixture + default assumptions
    VE: S-STR-01 Trend+Momentum strategy, S-FEA-01 fea_01_v1 features, S-REG-01 6-state regime
    VE: S-RSK-01 fail-closed risk engine + S-RSK-02 gate enforcement
    VE: S-PTR-01 5'li maliyet modeli (fee/spread/slippage/latency/partial fill)
    ZAMAN: BacktestRunner.run(run_id, bundle_ref, strategy_version, assumptions) çağrılır
    O ZAMAN: 10-halka pipeline deterministic şekilde çalışır
    VE: Her event kronolojik sırada (epoch ASC, corr ASC, caus ASC, ULID ASC)
    VE: Her karar anında (t) SADECE ≤t verisi kullanılır (look-ahead leakage = 0)
    VE: RiskDecision.approved = false ise PaperOrder üretilmez (gate bypass = 0)
    VE: S-PTR-01 PaperExecutionSimulator fill üretir (ikinci kez fill modeli YAZILMAZ)
    VE: S-PTF-01 Position, S-PTF-02 PortfolioSnapshot, S-PTF-03 Rolling24h çağrılır
    VE: BacktestRun metadata + ResultArtifact SHA256 ile üretilir
    VE: Aynı girdi ile 10x koşu → tamamen aynı çıktı (SHA256 set len = 1)
```

### Amaç (Verbose)
Replay/historical fixture verisini, mevcut tüm domain servislerini (feature/regime/strategy/opportunity/risk/paper execution/position/portfolio/performance) TEKRAR KULLANARAK, baştan sona DETERMİNİSTİK şekilde backtest et. Backtest Engine research/orchestration katmanıdır; HİÇBİR domain state'ini doğrudan YAZMAZ. Gerçek trading, canlı exchange bağlantısı, REST/WS, DB, Kafka — HEPSİ YASAKTIR. 10x determinizm + SHA256 tekilliği KRİTİK başarı kriteridir.

### İş Değeri
- Canlı para riski olmadan strateji doğrulama
- Walk-forward training foundation'ı (ML OOS için zemin)
- Maliyet hassasiyet analizi (fees/spread/slippage/latency)
- Regime/opportunity/risk pipeline doğrulama
- Gelecek E-BKT hikayeleri için sağlam temel (S-BKT-02 OOS, S-BKT-03 Walk-Forward)

---

## 2. Ön Koşullar (Preconditions)

### 2.1 Planning Dokümanları (OKUNDU ✓)
1. Product Brief: MVP hard boundary, lifecycle tanımları
2. PRD: FR-042-046 backtest gereksinimleri, FR-047-056 pipeline, NFR-007 reproducibility
3. ARCHITECTURE-SPINE: AD-1..AD-25 (özellikle AD-7/13/24 Single Writer, AD-4 Parity, AD-19 Fail-Closed, AD-20 Determinism)
4. SPEC: CAP-1/CAP-2/CAP-3/CAP-4/CAP-5/CAP-6 yetenek kuralları
5. CONTRACTS: 19 canonical contract, envelope şeması, QualityFlags 7 bayrak
6. EPICS: E-BKT Epic 10 tanımı, 3 hikaye kapsamı

### 2.2 Önceki Hikayeler (OKUNDU + IMPLEMENTASYON VAR ✓)
| ID | Modül | Reuse Türü | Backtest İçindeki Rolü |
|----|-------|-----------|----------------------|
| S-RDH-01 | ReplayBundleAdapter | %100 Reuse | Replay fixture → canonical event stream |
| S-RDH-02 | ReplayBundleRegistry | %100 Reuse | Çoklu fixture deterministic merge |
| S-PLN-01 | InMemoryTypedEventBus | %100 Reuse | 10-halka pipeline event teslimatı |
| S-CON-02A | FeatureVector / MarketRegime / StrategyContext / StrategySignal | %100 Reuse | Contract 4lü grubu |
| S-CON-02B | RiskDecision / PaperOrder / PaperFill / Position / PortfolioSnapshot | %100 Reuse | Contract 5li grubu |
| S-CON-02C | OpportunityScore / ModelLifecycle | %100 Reuse | Opportunity + FSM contractları |
| S-FEA-01 | FeatureEngine (12-key fea_01_v1) | %100 Reuse | Feature extraction (strict_closed_only) |
| S-REG-01 | RegimeDetector (6-state) | %100 Reuse | Market rejimi tespiti |
| S-STR-01 | StrategyEngine (Trend+Momentum) | %100 Reuse | StrategySignal üretimi |
| S-OPP-01 | OpportunityScorer (12-component) | %100 Reuse | Net-of-cost opportunity skoru |
| S-RSK-01 | RiskEngine (20-check, fail-closed) | %100 Reuse | RiskDecision üretimi |
| S-RSK-02 | RiskGate (10-rule, BYPASS YOK) | %100 Reuse | PaperOrder gate kontrolü |
| S-PTR-01 | PaperExecutionSimulator (5-cost) | %100 Reuse | Fill + maliyet simülasyonu |
| S-PTF-01 | PositionEngine | %100 Reuse | Position state yönetimi |
| S-PTF-02 | PortfolioSnapshotEngine | %100 Reuse | Portfolio + drawdown |
| S-PTF-03 | RollingPerformanceEngine (24h) | %100 Reuse | Rolling 24h performans |

### 2.3 Çevresel Ön Koşullar
- Python 3.14+ mevcut
- `pyproject.toml dependencies = []` — stdlib-only
- Regression baseline: **3629 PASS + 7 SKIP = 3636 collected** (`pytest tests/ -q --tb=no` exit 0)
- Canonical contracts CONTRACT_VERSION = 1.0.0

---

## 3. Bloklayıcı Değişmez Kurallar (Hard Constraints — İHLAL = HİKAYE FAIL)

### 3.1 AD-7 / AD-13 / AD-24 — Single Writer İzolasyonu (KRİTİK)
```
Backtest Engine HİÇBİR ŞEKLİDE:
  ❌ Position state DOĞRUDAN YAZAMAZ (sadece S-PTF-01 PositionEngine çağırır)
  ❌ PortfolioSnapshot DOĞRUDAN YAZAMAZ (sadece S-PTF-02 çağırır)
  ❌ RiskDecision approval ÜRETEZ (sadece S-RSK-01 çağırır, çıktısını okur)
  ❌ PaperOrder gate BYPASS EDEMEZ (S-RSK-02 RiskGate ZORUNLU)
  ❌ Exchange/network/DB KULLANAMAZ (tamamen in-memory)
```
Doğrulama: Static AST tarayıcı — backtest klasöründe `position.` / `portfolio.` / `risk.` / `paper_order.` attribute assignment 0 match.

### 3.2 CAP-1 — Replay/Live Paritesi (KRİTİK)
```
Backtest domain kodunda:
  ❌ `run_mode` if/elif/else dallanması = 0
  ❌ `source_type` if/elif/else dallanması = 0
  ❌ `datetime.now()` çağrısı = 0
  ❌ `time.time()` çağrısı = 0
  ❌ `time.sleep()` çağrısı = 0
  ❌ `Instant.now()` benzeri çağrı = 0
```
Canlı/Replay farkı YALNIZCA upstream S-RDH-01 Adapter + ReplayClock katmanındadır. Backtest aynı canonical event contractları ve aynı pipeline'ı kullanır.

### 3.3 CAP-2 — Quality Flags Salt Okunur
```
Backtest kodunda:
  ❌ QualityFlags alanlarına assignment = 0 (mutate YOK)
  ❌ `validate_quality` fonksiyonu çağrısı = 0 (sadece upstream bayraklar OKUNUR)
  ❌ `validate_position` çağrısı = 0
  ❌ `validate_market` çağrısı = 0
```

### 3.4 Safety 10 Kategori (KRİTİK — AST 0 match)
Backtest kod klasöründe aşağıdaki pattern'lerden HİÇBİRİ bulunamaz:
1. ❌ Canlı exchange: `binance`, `coinbase`, `exchange_client`, `rest_client`, `ws_client`
2. ❌ REST API: `requests.`, `urllib.`, `http.client.`, `aiohttp`
3. ❌ WebSocket: `websocket`, `ws://`, `wss://`
4. ❌ API Key / Credential: `api_key`, `secret_key`, `password`, `token`, `credential`
5. ❌ Gerçek Para / Emir: `real_order`, `live_order`, `withdraw`, `deposit`, `bank`
6. ❌ Veritabanı: `sqlite`, `postgres`, `mysql`, `mongodb`, `sqlalchemy`, `cursor`
7. ❌ Mesaj Kuyruğu: `kafka`, `rabbitmq`, `redis`, `pika`, `celery`
8. ❌ Short Pozisyon: `side=SHORT`, `"SHORT"`, `side_short`
9. ❌ Futures / Türev: `futures`, `perpetual`, `contract_size`, `mark_price`
10. ❌ Kaldıraç >1: `leverage>1`, `leverage = 2`, `max_leverage_allowed > 1` (S-CON-02B LimitsSnapshot ZORUNLU = 1)

### 3.5 Bağımlılık Kuralı
- `pyproject.toml dependencies = []` — Yeni runtime bağımlılığı EKLENEMEZ
- Sadece Python 3.14+ stdlib kullanılabilir

### 3.6 Contract Kuralı
- CONTRACT_VERSION = 1.0.0 KORUNUR
- Yeni canonical contract OLUŞTURULMAZ
- Mevcut 19 contract'ın field isimleri/türü DEĞİŞTİRİLMEZ

### 3.7 Git Kuralı
- Git add / commit / push YAPILMAZ
- Sadece S-BKT-01 hikayesi üzerinde çalışılır
- S-BKT-02 veya başka hikayeye GEÇİLMEZ

---

## 4. 10-Halka Backtest Pipeline (ZORUNLU SIRA)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              10-HALKA DETERMİNİSTİC BACKTEST PIPELINE                        │
│                                                                              │
│  correlation_id = SABİT (ilk ReplayTick'den itibaren)                         │
│  causation_id   = bir ÜST halkanın ürettiği event_id                          │
│  Tie-Break      = (epoch_ms ASC, corr_id ASC, caus_id ASC, ULID ASC)         │
└─────────────────────────────────────────────────────────────────────────────┘

  HALKA 1   REPLAY DATA          S-RDH-02 Registry → S-RDH-01 Adapter
            GİRDİ: ReplayBundleRegistry.bundle_ref (fixture hash + provenance)
            ÇIKTI: Canonical MarketTick[] / Candle[] — QualityFlags korunur
            KURAL: Kronolojik sıra, duplicate snapshot_id KEEP FIRST

  HALKA 2   FEATURE EXTRACTION   S-FEA-01 FeatureEngine
            GİRDİ: MarketTick/Candle (timestamp t)
            ÇIKTI: FeatureVector (fea_01_v1 — 12 key)
            KURAL: strict_closed_only — t+1 candle KULLANILAMAZ

  HALKA 3   REGIME DETECTION     S-REG-01 RegimeDetector
            GİRDİ: FeatureVector + son N regime geçmişi
            ÇIKTI: MarketRegime (6-state: bull/bear/sideways/high_vol/low_vol/transition)
            KURAL: Tie threshold 0.05 → near-tie → transition_uncertain

  HALKA 4   STRATEGY SIGNAL      S-STR-01 StrategyEngine
            GİRDİ: StrategyContext {regime, feature_vector, position_state}
            ÇIKTI: StrategySignal (LONG / FLAT / HOLD — short YASAK)
            KURAL: Regime uyum matrisi — uyumsuz rejimde Sinyal = HOLD

  HALKA 5   OPPORTUNITY SCORE    S-OPP-01 OpportunityScorer
            GİRDİ: StrategySignal + FeatureVector + MarketRegime + maliyet önizlemesi
            ÇIKTI: OpportunityScore (12 bileşen, net-of-cost, actionable bool)
            KURAL: actionable=false ise sonraki halkaya PASS (skip)

  HALKA 6   RISK DECISION        S-RSK-01 RiskEngine
            GİRDİ: OpportunityScore + Position + LimitsSnapshot + Portfolio
            ÇIKTI: RiskDecision (approved / rejected — fail-closed default)
            KURAL: 20-check list — tek kural fail → REJECTED

  HALKA 7   PAPER ORDER GATE     S-RSK-02 RiskGate + OrderFactory
            GİRDİ: RiskDecision + OpportunityScore + StrategySignal
            ÇIKTI: PaperOrder | None
            KURAL: RiskDecision.approved=false → PaperOrder = None (BYPASS YOK)
            KURAL: LimitsSnapshot.max_leverage_allowed ZORUNLU = 1

  HALKA 8   PAPER EXECUTION      S-PTR-01 PaperExecutionSimulator
            GİRDİ: PaperOrder + FillAssumptionsConfig (5-cost) + MarketTick (t)
            ÇIKTI: PaperFill[] (partial fill olabilir)
            KURAL: Reference Price Policy — closed=False candle LOOK-AHEAD BLOCK
            KURAL: 5 maliyet: taker_fee + spread + slippage + latency + partial_fill_rate

  HALKA 9   POSITION UPDATE      S-PTF-01 PositionEngine
            GİRDİ: PaperFill[] + mevcut Position state
            ÇIKTI: Position (side ∈ {LONG, FLAT} — short YASAK)
            KURAL: avg_price, realized_pnl, unrealized_pnl — Decimal kesinlik

  HALKA 10  PORTFÖY + PERFORMANS S-PTF-02 PortfolioSnapshot + S-PTF-03 Rolling24h
            GİRDİ: Position[] + MarketTick (t for mark)
            ÇIKTI: PortfolioSnapshot + Rolling24hPerformance
            KURAL: equity = cash + Σ exposure, drawdown ∈ [0,1], 24h window = 86400000ms

→ BacktestOrchestrator → BacktestRun Metadata + ResultArtifact (SHA256 ile)
```

---

## 5. BacktestRun Metadata Şeması (§3 USER)

### 5.1 Frozen Dataclass Taslağı (CONTRACT YENİ DEĞİL — sadece backtest internal)
```python
# SADECE BACKTEST İÇİ KULLANIM — CANONICAL CONTRACT DEĞİLDİR
# app/backtest/run_metadata.py
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime

@dataclass(frozen=True)  # Determinism için FROZEN
class BacktestWindowSplit:
    train_start_ms: int
    train_end_ms: int
    validation_start_ms: Optional[int]
    validation_end_ms: Optional[int]
    test_start_ms: Optional[int]
    test_end_ms: Optional[int]

@dataclass(frozen=True)
class BundleProvenance:
    bundle_ref: str                    # S-RDH-02 Registry referansı
    fixture_hashes: Dict[str, str]     # symbol → fixture sha256
    source_count: int
    total_events: int
    registry_version: str              # S-RDH-02 version

@dataclass(frozen=True)
class PipelineVersions:
    feature_engine: str                # S-FEA-01: "fea_01_v1"
    regime_detector: str               # S-REG-01: "regime_6s_v1"
    strategy_engine: str               # S-STR-01: "trend_mom_v1"
    opportunity_scorer: str            # S-OPP-01: "opp_12c_v1"
    risk_engine: str                   # S-RSK-01: "risk_20c_v1"
    risk_gate: str                     # S-RSK-02: "gate_10r_v1"
    paper_execution: str               # S-PTR-01: "paper_5c_v1"
    position_engine: str               # S-PTF-01: "pos_v1"
    portfolio_engine: str              # S-PTF-02: "pf_v1"
    rolling_performance: str           # S-PTF-03: "roll24h_v1"

@dataclass(frozen=True)
class BacktestAssumptions:
    assumptions_id: str                # deterministic ULID
    assumptions_version: str           # "assumptions_v1"
    fee_taker_bps: float               # S-PTR-01: default 7.5
    spread_bps: float                  # S-PTR-01: default 3.0
    slippage_bps: float                # S-PTR-01: default 5.0
    latency_ms: int                    # S-PTR-01: default 50
    partial_fill_rate: float           # S-PTR-01: default 1.0 (full fill fixture default)
    max_position_pct: float            # OOS için: default 0.25
    gap_tolerance_ms: int              # ADN-8: default 300000 (5dk)
    assumptions_sha256: str            # frozen alanların hash'i

@dataclass(frozen=True)
class BacktestRunCounts:
    total_input_events: int
    feature_vectors: int
    regime_events: int
    strategy_signals: int
    opportunity_scores: int
    risk_decisions_approved: int
    risk_decisions_rejected: int
    paper_orders_generated: int
    paper_fills_total: int
    paper_fills_partial: int
    position_updates: int
    portfolio_snapshots: int
    rolling_24h_windows: int
    quality_invalid_skipped: int
    quality_quarantine_skipped: int
    out_of_order_rejected: int
    duplicate_snapshot_discarded: int
    negative_fee_delta_clamped: int    # ADN-PTF03-03 reuse

@dataclass(frozen=True)
class BacktestRun:
    # RUN IDENTITY
    run_id: str                        # Deterministic ULID (seeded from inputs)
    created_at_ms: int                 # Replay clocktan (NOT wall clock — CAP-1)

    # PROVENANCE
    bundle: BundleProvenance
    pipeline_versions: PipelineVersions
    assumptions: BacktestAssumptions

    # WALK-FORWARD FOUNDATION (§7 USER)
    window_split: BacktestWindowSplit

    # TIME BOUNDARIES
    start_time_ms: int                 # İlk replay event epoch
    end_time_ms: int                   # Son replay event epoch
    duration_ms: int                   # end - start

    # EVENT COUNTS
    counts: BacktestRunCounts

    # PERFORMANCE SUMMARY (S-PTF-02/03 REUSE — yeniden hesaplama YOK)
    total_return_pct: float
    realized_pnl: str                  # Decimal string
    unrealized_pnl: str
    total_fees_paid: str
    max_exposure: str
    max_drawdown_pct: float
    rolling_24h_avg_return_pct: float
    rolling_24h_sharpe_proxy: float    # S-PTF-03 CORR fallback değil, gerçek veri varsa
    win_rate_pct: float
    total_trades: int
    avg_trade_pnl: str
    best_trade_pnl: str
    worst_trade_pnl: str

    # DETERMINISM VERIFICATION
    event_sequence_sha256: str         # Bütün event'lerin sıralı serialize hash'i
    fills_sha256: str
    positions_sha256: str
    portfolio_snapshots_sha256: str
    performance_sha256: str
    full_run_sha256: str               # Yukarıdakilerin hepsinin birleşik hash'i

    # OOS FLAG (§8 USER)
    is_contains_oos: bool              # window_split.test_start_ms varsa True
    oos_returns_separated: bool        # In-sample / OOS metrikleri ayrıldı mı?

    # FAIL-SAFE
    completed_successfully: bool
    fail_safe_events: List[str]        # Hangi event'ler skip edildi (deterministic liste)
```

---

## 6. 5'li Maliyet Modeli (§4 USER — S-PTR-01 %100 REUSE)

### 6.1 Tekrar Kullanım Prensibi
```
BACKTEST KENDİ FILL MODELİNİ İKİNCİ KEZ YAZMAZ.

Sadece şu çağrı yapılır:
  from app.simulation.execution import (
      PaperExecutionSimulator,
      FillAssumptionsConfig
  )

  fills: list[PaperFill] = PaperExecutionSimulator.execute_order(
      order=paper_order,
      market_snapshot=current_market_tick_candle_t,  # SADECE ≤t — t+1 YOK
      assumptions=fill_assumptions                    # BacktestAssumptions → FillAssumptionsConfig'e map
  )
```

### 6.2 Maliyet Bileşenleri (Fixture Varsayılanları — ADN-4 production kararı DEĞİL)
| Bileşen | Fixture Default | Açıklama | S-PTR-01 Field |
|---------|----------------|----------|----------------|
| Taker Fee | 7.5 bps | Binance spot taker fee | `fee_taker_bps` |
| Spread | 3.0 bps | BTCUSDT tipik spread | `spread_bps` |
| Slippage | 5.0 bps | Piyasa etkisi kayması | `slippage_bps` |
| Latency | 50 ms | Emir → fill arası | `latency_ms` |
| Partial Fill | 1.0 (full) | Fixture'de %100 dolarlık | `partial_fill_rate` |

### 6.3 Deterministic Fill Referans Fiyatı (LOOK-AHEAD BLOCK)
- S-PTR-01 Reference Price Policy: `closed=False` ise **ANLIK tick** kullanılır, sonraki kapanış YOK
- Backtest: Her zaman `reference_price_policy = "CURRENT_TICK_CLOSED_FALSE"` — `t+1` fiyatı KESİNLİKLE KULLANILAMAZ

---

## 7. Look-Ahead Leakage Sıfır Tolerans (§5 USER — KRİTİK)

### 7.1 Tanım
Her karar anında (t = event timestamp):
```
ERİŞİLEBİLİR:   tüm data/event timestamp ≤ t
ERİŞİLEMEZ:     tüm data/event timestamp > t  (t+1, t+2, ..., future)
```

### 7.2 Statik AST Tarama Testi (Implementation Guard)
```python
# tests/backtest/test_leakage_static_ast.py
# Backtest klasöründeki tüm .py dosyaları için:

FORBIDDEN_LEAKAGE_PATTERNS = [
    # Gelecek candle erişimi
    (r'candles\[i\s*\+\s*1\]', 'Gelecek candle erişimi — LEAKAGE'),
    (r'candles\[idx\s*\+\s*1\]', 'Gelecek candle erişimi — LEAKAGE'),
    (r'future_close', 'Gelecek close referansı — LEAKAGE'),
    (r'future_high', 'Gelecek high referansı — LEAKAGE'),
    (r'future_low', 'Gelecek low referansı — LEAKAGE'),
    (r'next_candle', 'Sonraki candle — LEAKAGE'),
    (r'next_tick', 'Sonraki tick — LEAKAGE'),
    # Yanlış pencere: end > t
    (r'window_end\s*[>=]+\s*t\s*\+', 'Window t+1 uzanıyor — LEAKAGE'),
    # S-PTR-01 reference price policy yanlış kullanımı
    (r'reference_price_policy.*NEXT_CLOSE', 'NEXT_CLOSE look-ahead — LEAKAGE'),
    (r'reference_price_policy.*FUTURE', 'FUTURE reference — LEAKAGE'),
    # t+1 decision
    (r'decision_timestamp\s*\+\s*1', 'Karar t+1 — LEAKAGE'),
]
```

### 7.3 Runtime Leakage Assertion Testi
Her pipeline halkası için test:
```python
def test_runtime_leakage_t_plus_1_block():
    # Feature Halkası
    fe = FeatureEngine()
    t_candle = Candle(timestamp=1000, close=100.0, ...)  # t
    t1_candle = Candle(timestamp=1001, close=101.0, ...) # t+1
    result = fe.compute([t_candle, t1_candle], decision_ts=1000)
    # Assert: result içinde t1_candle etkisi 0
    assert strict_closed_only_verified(result, [t_candle])

    # Backtest Halkası — en kritik
    runner = BacktestRunner()
    # Fixture içinde t ve t+1 var
    events = runner.run(decision_boundary_assert=True)
    # Her halkada, decision_ts ile input event max timestamp karşılaştırması
    for decision in extract_decisions(events):
        assert decision.input_max_ts <= decision.decision_ts, (
            f"LEAKAGE: {decision.name} input_max_ts={decision.input_max_ts} > "
            f"decision_ts={decision.decision_ts} delta={decision.input_max_ts - decision.decision_ts}ms"
        )
```

---

## 8. Event Sıra + Tie-Break Kuralları (§6 USER)

### 8.1 Deterministic Sıralama Anahtarı (4'lü)
```
TÜM event'ler için sıralama kuralı (ASCENDING):
  1. event_epoch_ms          (öncelik 1 — zaman damgası)
  2. correlation_id           (öncelik 2 — pipeline zinciri)
  3. causation_id             (öncelik 3 — parent event)
  4. ULID (event_id)          (öncelik 4 — tekillik)
```

### 8.2 Aynı Timestamp İçin 10 Halka Zorunlu Sıra
Aynı `epoch_ms` değeri için 10 halka ZORUNLU sırasını takip eder (correlation_id ile enforce edilir):
```
İLK → SON:
  1. MarketTick/Candle        (HALKA 1)
  2. FeatureVector            (HALKA 2)
  3. MarketRegime             (HALKA 3)
  4. StrategySignal           (HALKA 4)
  5. OpportunityScore         (HALKA 5)
  6. RiskDecision             (HALKA 6)
  7. PaperOrder               (HALKA 7)
  8. PaperFill                (HALKA 8)
  9. Position                 (HALKA 9)
  10. PortfolioSnapshot       (HALKA 10)
```

### 8.3 Out-of-Order Input Policy (Açık Kural)
Giriş olarak sırasız event gelirse:
- **Policy = REORDER & WARN (deterministic)**
- Tüm event'ler buffer'a alınır
- 4'lü anahtara göre sıralanır
- Orijinal sıra hash ile karşılaştırılır
- `counts.out_of_order_rejected++` — ancak event'ler discard edilmez, doğru sıraya konur
- Not: Bu policy ADN-9 kapsamında production'da değiştirilebilir (fixture default = REORDER)

---

## 9. Walk-Forward Foundation + OOS İzolasyonu (§7-8 USER)

### 9.1 BacktestWindowSplit Şeması (§5.1'de tanımlandı)
```
┌──────────────────────────────────────────────────────────────┐
│              Backtest Temporal İzolasyon                      │
│                                                               │
│  ◄────────────────────── BacktestRun ──────────────────────► │
│                                                               │
│  ┌──────────────┐┌──────────────┐┌───────────────────────┐   │
│  │   TRAIN SET  ││   VAL SET    ││     TEST / OOS SET    │   │
│  │  (in-sample) ││ (in-sample)  ││   (out-of-sample)     │   │
│  └──────────────┘└──────────────┘└───────────────────────┘   │
│  ts         train_end_ms  val_end_ms                 end_ms  │
│                                                               │
│  KURAL: TRAIN aşamasında VAL/TEST verisi ASLA GÖRÜLMEZ        │
│  KURAL: VAL aşamasında TEST verisi ASLA GÖRÜLMEZ              │
│  KURAL: Parameter selection SADECE TRAIN/VAL üzerinde yapılır │
│  KURAL: OOS metrikleri RAPORDA AYRICA BULDURULUR              │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 Fixture Varsayılan Split Oranları (ADN-5 production kararı DEĞİL)
| Set | Fixture Default Oran | Açıklama |
|-----|---------------------|----------|
| TRAIN | %70 | 30 günlük fixture: 21 gün |
| VAL | %15 | 4.5 gün |
| TEST (OOS) | %15 | 4.5 gün |

### 9.3 Örnek Fixture Timeline (BTCUSDT 30 gün)
```
start_ms:        1714521600000 (2024-05-01 00:00:00 UTC)
train_end_ms:    1716336000000 (2024-05-22 00:00:00 UTC) — 21 gün TRAIN
val_start_ms:    1716336000000 (VAL = TRAIN sonrası — overlap YOK)
val_end_ms:      1716940800000 (2024-05-29 00:00:00 UTC) — 7 gün VAL (fixture özel %23/%7/%0 — ADN-5)
test_start_ms:   1716940800000 (TEST = VAL sonrası — overlap YOK)
test_end_ms:     end_ms (TESLER %0 — ADN-5 walk-forward için foundation)
end_ms:          1717113600000 (2024-05-31 00:00:00 UTC)
```
Not: Split oranları ADN-5 kapsamında AÇIK KARARDIR.

---

## 10. Performans Metrikleri (§9 USER — S-PTF-02/03 %100 REUSE)

### 10.1 Yeniden Hesaplama YOK
```
YENİ portfolio calculation İMPLEMENTASYONU YAPILMAZ.

Sadece mevcut engine'ların çıktıları toplanır:
  1. S-PTF-02 PortfolioSnapshotEngine:
     - total_return_pct
     - realized_pnl, unrealized_pnl
     - total_fees_paid
     - max_exposure
     - peak_equity
     - max_drawdown_pct
     - equity_curve[]

  2. S-PTF-03 RollingPerformanceEngine (24h = 86400000ms):
     - rolling_24h_avg_return_pct
     - rolling_24h_peak_return_pct
     - rolling_24h_drawdown_pct
     - rolling_24h_realized_pnl_delta
     - rolling_24h_fees_delta (NEGATIVE FEES CLAMP — ADN-PTF03-03)
     - rolling_24h_count
     - CORR_UNKNOWN_ROLLING / CAUS_UNKNOWN_ROLLING fallback (ADN-PTF03-04 empty window)
```

### 10.2 Backtest Run İçinde Raporlanan Minimum Metrik Listesi
BacktestRun.performance_summary içinde ZORUNLU:
- ✅ total_return_pct
- ✅ realized_pnl (Decimal string)
- ✅ unrealized_pnl (Decimal string)
- ✅ total_fees_paid (Decimal string)
- ✅ max_exposure (Decimal string)
- ✅ max_drawdown_pct
- ✅ rolling_24h_avg_return_pct
- ✅ rolling_24h_sharpe_proxy (S-PTF-03 varsa)
- ✅ win_rate_pct (trade-based)
- ✅ total_trades (fill-based)
- ✅ avg_trade_pnl
- ✅ best_trade_pnl
- ✅ worst_trade_pnl
- ✅ trade_fill_count (S-PTR-01 fill sayısı)

---

## 11. Tüm Modül Reuse Matrisi

| # | Modül | Hikaye | Backtest Erişimi | Yazma İzni | Zorunlu Kontroller |
|---|-------|--------|-----------------|-----------|-------------------|
| 1 | ReplayBundleAdapter | S-RDH-01 | Sadece ÇAĞIRMA | ❌ YOK | Deterministic fixture yükleme |
| 2 | ReplayBundleRegistry | S-RDH-02 | Sadece ÇAĞIRMA | ❌ YOK | Bundle hash doğrulama |
| 3 | InMemoryTypedEventBus | S-PLN-01 | Sadece ÇAĞIRMA | ❌ YOK | Event sıra + corr/caus |
| 4 | FeatureEngine | S-FEA-01 | Sadece ÇAĞIRMA | ❌ YOK | strict_closed_only leakage |
| 5 | RegimeDetector | S-REG-01 | Sadece ÇAĞIRMA | ❌ YOK | 6-state, tie_threshold 0.05 |
| 6 | StrategyEngine | S-STR-01 | Sadece ÇAĞIRMA | ❌ YOK | Long/flat/hold only |
| 7 | OpportunityScorer | S-OPP-01 | Sadece ÇAĞIRMA | ❌ YOK | 12-component, net-of-cost |
| 8 | RiskEngine | S-RSK-01 | Sadece ÇAĞIRMA | ❌ YOK | Fail-closed, 20-check |
| 9 | RiskGate | S-RSK-02 | Sadece ÇAĞIRMA | ❌ YOK | BYPASS YOK, 10-rule |
| 10 | PaperExecutionSimulator | S-PTR-01 | Sadece ÇAĞIRMA | ❌ YOK | 5-cost, reference price |
| 11 | PositionEngine | S-PTF-01 | Sadece ÇAĞIRMA | ❌ YOK | Single writer, long only |
| 12 | PortfolioSnapshotEngine | S-PTF-02 | Sadece ÇAĞIRMA | ❌ YOK | Single writer, drawdown |
| 13 | RollingPerformanceEngine | S-PTF-03 | Sadece ÇAĞIRMA | ❌ YOK | 24h window, fee clamp |

---

## 12. Correlation / Causation Zinciri (§18 USER — AD-17)

### 12.1 10-Halka Zincir Kuralı
```
İLK REPLAY EVENT correlation_id = CORR_INIT (deterministic fixture'den)
  → HER SONRAKİ HALKA: correlation_id = AYNI (değişmez)
  → HER HALKA: causation_id = BİR ÖNCEKİ HALKANIN event_id'si

Örnek (tek bir tick için full pipeline):
  ┌───────────────────────────────────────────────────────────┐
  │ correlation_id = "CORR-BTC-1714521600000-00001" (SABİT) │
  └───────────────────────────────────────────────────────────┘
  HALKA 1 MarketTick:      event_id = "EVT-MT-00001"
                           causation_id = "CAUS-REPLAY-ROOT"
  HALKA 2 FeatureVector:   event_id = "EVT-FV-00001"
                           causation_id = "EVT-MT-00001"  ← parent
  HALKA 3 MarketRegime:    event_id = "EVT-RG-00001"
                           causation_id = "EVT-FV-00001"  ← parent
  HALKA 4 StrategySignal:  event_id = "EVT-SS-00001"
                           causation_id = "EVT-RG-00001"  ← parent
  HALKA 5 OpportunityScore:event_id = "EVT-OP-00001"
                           causation_id = "EVT-SS-00001"  ← parent
  HALKA 6 RiskDecision:    event_id = "EVT-RD-00001"
                           causation_id = "EVT-OP-00001"  ← parent
  HALKA 7 PaperOrder:      event_id = "EVT-PO-00001" (eğer approved)
                           causation_id = "EVT-RD-00001"  ← parent
  HALKA 8 PaperFill:       event_id = "EVT-PF-00001"
                           causation_id = "EVT-PO-00001"  ← parent
  HALKA 9 Position:        event_id = "EVT-POS-00001"
                           causation_id = "EVT-PF-00001"  ← parent
  HALKA 10 PortfolioSnap:  event_id = "EVT-PF-00001" (PF = portfolio)
                           causation_id = "EVT-POS-00001" ← parent
```

### 12.2 Deterministic Correlation ID Üretimi
- `correlation_id = f"CORR-{symbol}-{epoch_ms}-{seq:05d}"`
- seq = fixture içindeki sıra numarası (deterministic)
- Rastgele ULID YOK — fixture'den gelen veriyle üretilebilir

---

## 13. Quality Flags Taşıma (§19 USER — CAP-2)

### 13.1 Kural
```
QualityFlags:
  ❌ MUTATE EDİLMEZ (backtest kodunda assignment YOK)
  ❌ Validator TEKRAR ÇAĞRILMAZ (validate_quality çağrısı = 0)
  ✅ SADECE OKUNUR — upstream'den taşınır
```

### 13.2 Quality'li Event'lerde Güvenli Davranış
| Quality Flag | Backtest Davranışı | counts Artışı |
|-------------|-------------------|---------------|
| `invalid = true` | Event SKIP — sonraki halkalara PASS YOK | `quality_invalid_skipped++` |
| `quarantined = true` | Event SKIP — sonraki halkalara PASS YOK | `quality_quarantine_skipped++` |
| `missing = true` | S-PTF-03 window dışı tutma kuralı REUSE | Pencere dışı |
| `stale = true` | FeatureEngine'e iletilir (S-FEA-01 kendi kuralı uygular) | Upstream karar |
| `degraded = true` | RegimeDetector'a iletilir | Upstream karar |

---

## 14. Fail-Closed Davranış (§20 USER — AD-19)

### 14.1 Fail-Closed Default
Her türlü hata durumunda:
```
DEFAULT = FAIL-CLOSED (REJECT / SKIP)
Sessizce APPROVED trade ÜRETİLMEZ.
```

### 14.2 Hata Senaryoları ve Deterministik Karşılığı
| Hata Senaryosu | Davranış | Not |
|--------------|----------|-----|
| Eksik alanlı contract | Event reject + fail_safe_events listesine ekle | Deterministic sıra numarası ile |
| Contract type mismatch | Sonraki halkaya PASS YOK | corr/caus korunur |
| Simulation exception (any) | Try/except ile yakala → event skip | Exception tip hash ile kayıt |
| RiskEngine exception | RiskDecision = REJECTED (fail-closed default) | Approved YOK |
| RiskGate exception | PaperOrder = None | Bypass YOK |
| PaperExecution exception | Fill = [] (sıfır fill) | Position değişmez |
| PositionEngine exception | Önceki Position state korunur | State mutate YOK hata durumunda |
| PortfolioEngine exception | Önceki PortfolioSnapshot korunur | State mutate YOK |

---

## 15. Versionlu Assumptions (§21 USER)

### 15.1 BacktestAssumptions Frozen Şeması (§5.1'de detaylı)
- `assumptions_id`: Deterministic ULID (seed = tüm fieldların hash'i)
- `assumptions_version`: `"assumptions_v1"`
- Her alan değiştiğinde `assumptions_sha256` değişir → `run_id` deterministik olarak farklı üretilir
- Fixture default ≠ production optimum → Açıklık var (ADN-4)

---

## 16. Result Artifact Formatı (§22 USER)

### 16.1 Deterministic Serialization
```
ResultArtifact = BacktestRun frozen dataclass → to_sorted_dict() → JSON (sort_keys=True) → SHA256

İçindekiler:
  1. run_summary (BacktestRun — §5.1)
  2. config_hash = hash(pipeline_versions + assumptions)
  3. input_provenance = bundle + registry hash
  4. strategy_version, feature_version (pipeline_versions'dan)
  5. assumptions_hash
  6. metrics = performance_summary (§10)
  7. event_counts = counts (§5.1 BacktestRunCounts)
  8. fill_counts = total + partial
```

### 16.2 Local Artifact Abstraction (Object Storage OOS — §22)
- Bu hikayede S3/GCS object storage YOK
- Sadece `app/backtest/artifact.py` altında soyutlama:
  - `save_artifact(run: BacktestRun, path: Path) -> None`
  - `load_artifact(path: Path) -> BacktestRun`
  - `verify_artifact_hash(path: Path) -> bool`
- Deterministic JSON: `sort_keys=True, separators=(',', ':')` — beyaz alan standartlaştırılmış

---

## 17. 9 Açık Karar (ADN — §29 USER)

Production kararlarını şimdilik ZORLA KAPATMA. Fixture varsayılanları ile belirtilir.

| ADN # | Açık Karar | Fixture Default Açıklaması | Production İçin |
|-------|-----------|--------------------------|----------------|
| ADN-BKT-01 | Exact Backtest Universe | BTCUSDT + ETHUSDT + SOLUSDT (S-RDH-01 3 fixture) | Top 10 / Top 20 / Sektörel |
| ADN-BKT-02 | Timeframe | 1m (S-RDH-01 fixture) | 5m / 15m / 1h / 4h / Karışık |
| ADN-BKT-03 | Benchmark | BTCUSDT buy-and-hold | SPX / ETH / Equal-weight / Fama-French |
| ADN-BKT-04 | Execution Cost Kalibrasyon | 7.5 / 3.0 / 5.0 bps + 50ms + 1.0 fill | Gerçek taker/maker, slip kalibrasyon, takas derinliği |
| ADN-BKT-05 | OOS Split Oranları | TRAIN 70% / VAL 15% / TEST 15% | Walk-forward 60-20-20, Expanding window |
| ADN-BKT-06 | Walk-Forward Window Uzunlukları | Bu hikayede foundation (implementation YOK) | 1 yıl train / 3 ay test / 1 ay step |
| ADN-BKT-07 | Artifact Persistence Provider | Local filesystem (JSON) | S3 / GCS / Parquet / HDF5 |
| ADN-BKT-08 | Data-Gap Policy | 5dk (300000ms) tolerance sonrası sıfırla | 1dk / 10dk / Forward-fill / Interpolate |
| ADN-BKT-09 | Failure / Retry Policy | Fail-closed + deterministic skip | Retry 3x / exponential backoff / circuit breaker |

---

## 18. Implementation Guards (Forbidden Pattern Static Testler)

Backtest implementation sonrası AŞAĞIDAKİ STATİK TESTLER YAZILACAK (implementation guard):

| Guard # | Test | Doğrulama |
|---------|------|----------|
| G-BKT-01 | CAP-1 run_mode/source_type branch | AST scan: `if.*run_mode` / `if.*source_type` = 0 match |
| G-BKT-02 | CAP-1 tarih/saat fonksiyonu | AST scan: `datetime.now` / `time.time` / `sleep` = 0 match |
| G-BKT-03 | CAP-2 Quality mutate | AST scan: `quality_flags.*=` = 0 match |
| G-BKT-04 | CAP-2 Validator çağrısı | AST scan: `validate_quality` / `validate_position` çağrısı = 0 |
| G-BKT-05 | Single Writer — Position write | AST scan: `position.` attribute assign dışında (engine çağrısı HARİÇ) = 0 |
| G-BKT-06 | Single Writer — Portfolio write | AST scan: portfolio snapshot assign dışında = 0 |
| G-BKT-07 | Single Writer — Risk mutate | AST scan: `RiskDecision.approved = True` doğrudan = 0 |
| G-BKT-08 | Single Writer — Gate bypass | AST scan: `RiskGate.bypass` / `skip_gate` = 0 match |
| G-BKT-09 | Safety — Live Exchange | AST scan: binance/coinbase/rest_client/ws = 0 |
| G-BKT-10 | Safety — REST API | AST scan: requests/urllib/http.client/aiohttp = 0 |
| G-BKT-11 | Safety — WebSocket | AST scan: websocket/ws:///wss:// = 0 |
| G-BKT-12 | Safety — Credential | AST scan: api_key/secret_key/password/token = 0 |
| G-BKT-13 | Safety — Real Order | AST scan: real_order/live_order/withdraw/deposit = 0 |
| G-BKT-14 | Safety — Database | AST scan: sqlite/postgres/mysql/mongodb/sqlalchemy = 0 |
| G-BKT-15 | Safety — Message Queue | AST scan: kafka/rabbitmq/redis/pika/celery = 0 |
| G-BKT-16 | Safety — Short | AST scan: side=SHORT / "SHORT" / side_short = 0 |
| G-BKT-17 | Safety — Futures | AST scan: futures/perpetual/mark_price/contract_size = 0 |
| G-BKT-18 | Safety — Leverage > 1 | AST scan: leverage.*[2-9] / max_leverage_allowed > 1 = 0 |
| G-BKT-19 | Leakage Static | AST scan: candles[i+1] / next_candle / future_close = 0 |
| G-BKT-20 | Fill Model İkinci Kez Yazılma | AST scan: backtest klasöründe `class.*FillSimulator` / `def.*execute.*fill` (S-PTR-01 import HARİÇ) = 0 |
| G-BKT-21 | Yeni Dependency | pyproject.toml diff scan: `dependencies.*[^\[\]]` = 0 değişiklik |
| G-BKT-22 | Contract Version | CONTRACTS.md CONTRACT_VERSION değişmez = 1.0.0 |

---

## 19. Dosya Yapısı Planı (Yeni Backtest Klasörü)

```
app/backtest/                          # YENİ KLASÖR (toplam 6-8 .py)
├── __init__.py
├── runner.py                          # BacktestRunner — ana orchestrator
├── run_metadata.py                    # BacktestRun + BacktestAssumptions + WindowSplit
├── artifact.py                        # save/load/verify artifact (JSON stdlib only)
├── clock.py                           # Deterministic ReplayClock — CAP-1 için
├── pipeline.py                        # 10-halka pipeline çağrı sıralayıcı
├── leakage_guard.py                   # Runtime leakage assertion helper
└── sort_utils.py                      # 4'lü tie-break sıralama utility

tests/backtest/                        # YENİ KLASÖR (300+ yeni test)
├── __init__.py
├── test_runner_determinism_10x.py     # 10x determinizm SHA256 (20+ test)
├── test_pipeline_order.py             # Event sıra tie-break (40+ test)
├── test_leakage_static_ast.py         # Guard G-BKT-19 + runtime (30+ test)
├── test_leakage_runtime.py            # Runtime t+1 block (30+ test)
├── test_single_writer_ast.py          # Guard G-BKT-05-08 (20 test)
├── test_cap1_parity.py                # Guard G-BKT-01-02 (20 test)
├── test_cap2_quality.py               # Guard G-BKT-03-04 (15 test)
├── test_safety_10_category.py         # Guard G-BKT-09-18 (10 test)
├── test_cost_model_reuse.py           # S-PTR-01 doğrudan çağrı (25 test)
├── test_risk_gate_nobypass.py         # S-RSK-02 bypass=0 (20 test)
├── test_portfolio_reuse.py            # S-PTF-01/02/03 yeniden yazma=0 (25 test)
├── test_backtest_window_split.py      # Walk-forward + OOS izolasyon (25 test)
├── test_corr_caus_chain.py            # 10-halka zincir (20 test)
├── test_fail_closed.py                # AD-19 hata senaryoları (20 test)
├── test_artifact_hash.py              # Result artifact SHA256 (15 test)
├── test_regression.py                 # 16 hikaye regression koruma (15 test)
└── fixtures/                          # Replay fixture test data (S-RDH-01/02 reuse)
    ├── BTCUSDT_30d_1m_small.json
    ├── ETHUSDT_7d_1m_tiny.json
    └── mixed_symbols_quality_flags.json
```

---

## 20. Acceptance Criteria (AC — TOPLAM 312 ADET)

AC'ler 19 kategoriye ayrılmıştır. Her AC doğrulanabilir, fail/pass sonuçludur.

### KATEGORİ 1: Happy Path Full Pipeline (32 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-001 | Boş olmayan replay bundle ile BacktestRunner.run() çağrıldığında `completed_successfully = true` döner |
| AC-BKT-002 | run_id deterministic üretildi — aynı inputta koşu başına aynı run_id |
| AC-BKT-003 | BundleProvenance fixture hashleri S-RDH-02 Registry ile eşleşir |
| AC-BKT-004 | PipelineVersions 10 sürüm alanı ZORUNLU doludur |
| AC-BKT-005 | BacktestAssumptions 5 maliyet alanı ZORUNLU doludur |
| AC-BKT-006 | start_time_ms = ilk replay event timestamp |
| AC-BKT-007 | end_time_ms = son replay event timestamp |
| AC-BKT-008 | HALKA 1: MarketTick/Candle sayısı counts.total_input_events ile eşleşir |
| AC-BKT-009 | HALKA 2: FeatureVector sayısı > 0 (kaliteli veri varsa) |
| AC-BKT-010 | HALKA 3: MarketRegime sayısı = FeatureVector sayısı |
| AC-BKT-011 | HALKA 4: StrategySignal sayısı = Regime sayısı |
| AC-BKT-012 | HALKA 5: OpportunityScore sayısı = StrategySignal sayısı |
| AC-BKT-013 | HALKA 6: RiskDecision sayısı = OpportunityScore sayısı |
| AC-BKT-014 | HALKA 6: `risk_decisions_approved + risk_decisions_rejected = RiskDecision sayısı` |
| AC-BKT-015 | HALKA 7: PaperOrder sayısı ≤ risk_decisions_approved (1:1 olması normal) |
| AC-BKT-016 | HALKA 8: PaperFill sayısı ≥ PaperOrder sayısı (partial fill nedeniyle çoğalabilir) |
| AC-BKT-017 | HALKA 9: Position sayısı ≥ 1 (en azından initial FLAT) |
| AC-BKT-018 | HALKA 10: PortfolioSnapshot sayısı ≥ 1 |
| AC-BKT-019 | HALKA 10: Rolling24h sayısı ≥ 0 |
| AC-BKT-020 | total_return_pct float tipinde ve -100.0 ile +∞ arasındadır |
| AC-BKT-021 | max_drawdown_pct ∈ [0.0, 100.0] |
| AC-BKT-022 | total_fees_paid Decimal string ve 0.0 ≤ değer (fees pozitif olmalı) |
| AC-BKT-023 | win_rate_pct ∈ [0.0, 100.0] |
| AC-BKT-024 | total_trades ≥ 0 |
| AC-BKT-025 | full_run_sha256 64 karakterli hex string (SHA256) |
| AC-BKT-026 | event_sequence_sha256 benzersiz ve deterministik |
| AC-BKT-027 | fills_sha256 benzersiz ve deterministik |
| AC-BKT-028 | positions_sha256 benzersiz ve deterministik |
| AC-BKT-029 | portfolio_snapshots_sha256 benzersiz ve deterministik |
| AC-BKT-030 | performance_sha256 benzersiz ve deterministik |
| AC-BKT-031 | BacktestWindowSplit.train_start_ms < train_end_ms |
| AC-BKT-032 | VAL/TEST setleri TRAIN seti ile overlap YOK |

### KATEGORİ 2: Determinism 10x + SHA256 (28 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-033 | Aynı input ile 10 backtest → run_id 10 tanesi aynı (set len = 1) |
| AC-BKT-034 | 10 koşu → full_run_sha256 10 tanesi aynı |
| AC-BKT-035 | 10 koşu → event_sequence_sha256 10 tanesi aynı |
| AC-BKT-036 | 10 koşu → fills_sha256 10 tanesi aynı |
| AC-BKT-037 | 10 koşu → positions_sha256 10 tanesi aynı |
| AC-BKT-038 | 10 koşu → portfolio_snapshots_sha256 10 tanesi aynı |
| AC-BKT-039 | 10 koşu → performance_sha256 10 tanesi aynı |
| AC-BKT-040 | 10 koşu → ordered event listesi (by epoch/corr/caus/ULID) 10 tanesi aynı |
| AC-BKT-041 | 10 koşu → fills listesi 10 tanesi aynı |
| AC-BKT-042 | 10 koşu → positions listesi 10 tanesi aynı |
| AC-BKT-043 | 10 koşu → portfolio snapshots listesi 10 tanesi aynı |
| AC-BKT-044 | 10 koşu → performance summary tüm field'lar 10 tanesi aynı |
| AC-BKT-045 | 10 koşu → counts 22 alanı 10 tanesi aynı |
| AC-BKT-046 | 10 koşu → fail_safe_events listesi 10 tanesi aynı |
| AC-BKT-047 | Assumptions değişti (örn fee 7.5→10 bps) → full_run_sha256 FARKLI olur (determinizm kırılmaz) |
| AC-BKT-048 | Strategy version değişti → full_run_sha256 FARKLI olur |
| AC-BKT-049 | Feature version değişti → full_run_sha256 FARKLI olur |
| AC-BKT-050 | Fixture değişti (sembol değiştir) → full_run_sha256 FARKLI olur |
| AC-BKT-051 | Farklı rastgele süreçlerde 10x koşu aynı sonucu üretir (tox 3 kez) |
| AC-BKT-052 | Shuffled input event (aynı veri farklı sıra) → son yine aynı (sıralama yapıldığı için) |
| AC-BKT-053 | 10 koşu sonunda her koşunun to_sorted_dict()'i == diğerleri |
| AC-BKT-054 | assumptions_sha256 kendisi deterministik (aynı assumptions → aynı hash) |
| AC-BKT-055 | config_hash kendisi deterministik (aynı pipeline + assumptions → aynı hash) |
| AC-BKT-056 | 10 koşuda correlation_id 10 tanesi aynı (aynı event için) |
| AC-BKT-057 | 10 koşuda causation_id 10 tanesi aynı (aynı event için) |
| AC-BKT-058 | ULID üretimi deterministik seeded (10 koşuda aynı ULID) |
| AC-BKT-059 | 10 koşu sonrası fills içindeki fee/spread/slip değerleri AYNI (Decimal kesinlik) |
| AC-BKT-060 | 10x after-sort JSON serialize SHA256 set len = 1 |

### KATEGORİ 3: Event Sıra + Tie-Break (25 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-061 | Tüm event'ler epoch_ms ASC sıralıdır (loop i: events[i].epoch ≤ events[i+1].epoch) |
| AC-BKT-062 | Aynı epoch_ms olan event'ler correlation_id ASC sıralıdır |
| AC-BKT-063 | Aynı epoch ve corr → causation_id ASC sıralıdır |
| AC-BKT-064 | Aynı epoch/corr/caus → ULID ASC sıralıdır |
| AC-BKT-065 | Aynı timestamp için 10 halka ZORUNLU sıra takip edilir (1→10) |
| AC-BKT-066 | MarketTick her zaman FeatureVector'den ÖNCE gelir (aynı ts) |
| AC-BKT-067 | FeatureVector her zaman MarketRegime'den ÖNCE gelir |
| AC-BKT-068 | MarketRegime her zaman StrategySignal'dan ÖNCE gelir |
| AC-BKT-069 | StrategySignal her zaman OpportunityScore'dan ÖNCE gelir |
| AC-BKT-070 | OpportunityScore her zaman RiskDecision'dan ÖNCE gelir |
| AC-BKT-071 | RiskDecision her zaman PaperOrder'dan ÖNCE gelir |
| AC-BKT-072 | PaperOrder her zaman PaperFill'den ÖNCE gelir |
| AC-BKT-073 | PaperFill her zaman Position'dan ÖNCE gelir |
| AC-BKT-074 | Position her zaman PortfolioSnapshot'dan ÖNCE gelir |
| AC-BKT-075 | Out-of-order input verildiğinde → sıralanmış çıktı |
| AC-BKT-076 | Out-of-order verildiğinde → counts.out_of_order_rejected > 0 |
| AC-BKT-077 | Aynı snapshot_id duplicate → KEEP FIRST policy (ADN-PTF03-01 reuse) |
| AC-BKT-078 | Duplicate → counts.duplicate_snapshot_discarded artar |
| AC-BKT-079 | Tie-break 4'lü anahtar → tam sıralama (eşit kalan durum YOK) |
| AC-BKT-080 | Farklı sembol aynı ts → correlation_id sıralaması ile ayrılır |
| AC-BKT-081 | Tek event'in 10 halka zinciri → kesintisiz bağlantı (causation zinciri kırılmaz) |
| AC-BKT-082 | 4'lü anahtarla sort → stable sort, ikinci kez sort değişmez |
| AC-BKT-083 | 1000 event karışık sıra → sort sonrası doğru sıra |
| AC-BKT-084 | Epoch 0 olan sentinel event'ler en başta (fixture HEADER) |
| AC-BKT-085 | Epoch MAXINT olan sentinel event'ler en sonda (fixture FOOTER) |

### KATEGORİ 4: Look-Ahead Leakage — Static + Runtime (30 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-086 | G-BKT-19 Static AST: `candles[i+1]` pattern'ı = 0 match |
| AC-BKT-087 | G-BKT-19 Static AST: `next_candle` pattern'ı = 0 match |
| AC-BKT-088 | G-BKT-19 Static AST: `future_close` pattern'ı = 0 match |
| AC-BKT-089 | G-BKT-19 Static AST: `future_high` pattern'ı = 0 match |
| AC-BKT-090 | G-BKT-19 Static AST: `next_tick` pattern'ı = 0 match |
| AC-BKT-091 | Runtime: FeatureVector HALKA 2 decision_ts ile input_max_ts karşılaştırması → ≤ |
| AC-BKT-092 | Runtime: MarketRegime HALKA 3 → input_max_ts ≤ decision_ts |
| AC-BKT-093 | Runtime: StrategySignal HALKA 4 → input_max_ts ≤ decision_ts |
| AC-BKT-094 | Runtime: OpportunityScore HALKA 5 → input_max_ts ≤ decision_ts |
| AC-BKT-095 | Runtime: RiskDecision HALKA 6 → input_max_ts ≤ decision_ts |
| AC-BKT-096 | Runtime: PaperOrder HALKA 7 → input_max_ts ≤ decision_ts |
| AC-BKT-097 | Runtime: PaperFill HALKA 8 → reference_price ts = t (t+1 DEĞİL) |
| AC-BKT-098 | Runtime: Position HALKA 9 → mark_price ts ≤ decision_ts |
| AC-BKT-099 | Runtime: Portfolio HALKA 10 → mark_prices ts ≤ portfolio_ts |
| AC-BKT-100 | Runtime: RollingPerformance → window_end_ms ≤ decision_ts |
| AC-BKT-101 | Feature Engine strict_closed_only doğru kullanılıyor |
| AC-BKT-102 | S-PTR-01 Reference Price Policy: CURRENT_TICK_CLOSED_FALSE kullanılıyor |
| AC-BKT-103 | Reference Price Policy'de NEXT_CLOSE / FUTURE KULLANILMIYOR |
| AC-BKT-104 | t=1000 karar verildiğinde window_end_ms = 1000'den büyük olamaz |
| AC-BKT-105 | Manually t+1 data inject edilmiş test → decision REDUCE EDİLİR veya hata |
| AC-BKT-106 | FeatureVector içinde t+1 close etkisi 0 (sıfır) (statistical test) |
| AC-BKT-107 | StrategySignal içinde t+1 etkisi 0 (permütasyon testi) |
| AC-BKT-108 | 10 koşuda leakage sayaçları 0 (sıfır) kalır |
| AC-BKT-109 | Rolling 24h window: t+1ms event window içine alınmaz (boundary) |
| AC-BKT-110 | Rolling 24h window: t tam kenar → event window içine ALINIR (≤ dahil) |
| AC-BKT-111 | OpportunityScorer içinde net edge hesap t+1 fiyat kullanmıyor |
| AC-BKT-112 | RiskEngine içinde future exposure hesaplaması YOK |
| AC-BKT-113 | BacktestRunner içinde "lookahead detected" assertion test |
| AC-BKT-114 | 1000 event + 1000 future inject → 0 leakage (fark edilmez gelecek) |
| AC-BKT-115 | LeakageGuard runtime helper testi — enjekte hatayı yakalar |

### KATEGORİ 5: Cost Model — S-PTR-01 Reuse (22 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-116 | PaperExecutionSimulator DOĞRUDAN S-PTR-01 import edilmiş — ikinci kez class YOK |
| AC-BKT-117 | FillAssumptionsConfig DOĞRUDAN S-PTR-01 import edilmiş |
| AC-BKT-118 | G-BKT-20: backtest klasöründe yeni Fill simulator class = 0 |
| AC-BKT-119 | Fee bileşeni fill fiyatına dahil (fee_taker_bps × quantity × price) |
| AC-BKT-120 | Spread bileşeni fill fiyatına dahil (spread_bps × price) |
| AC-BKT-121 | Slippage bileşeni fill fiyatına dahil (slippage_bps × price) |
| AC-BKT-122 | Latency bileşeni PaperFill.fill_ts = order_ts + latency_ms |
| AC-BKT-123 | Partial fill: partial_fill_rate < 1.0 → birden fazla PaperFill üretilebilir |
| AC-BKT-124 | Full fill fixture (partial_fill_rate=1.0) → her order için 1 fill |
| AC-BKT-125 | BacktestAssumptions → FillAssumptionsConfig mapping doğruluğu (1:1 field) |
| AC-BKT-126 | Fee 0 bps → fee alanları 0 |
| AC-BKT-127 | Spread 0 bps → mid-price ile fill |
| AC-BKT-128 | Slippage 0 bps → slip etkisi 0 |
| AC-BKT-129 | Latency 0 → fill_ts = order_ts |
| AC-BKT-130 | Partial 0.5 → 2 fill, herbiri yaklaşık yarım quantity |
| AC-BKT-131 | Total 5 maliyetin toplamı tek bir trade'de doğru hesaplanmış |
| AC-BKT-132 | S-PTR-01 çıktısı ile backtest fill çıktısı BİREBİR aynı (aynı input) |
| AC-BKT-133 | Fee negatif delta 0'a clamp — ADN-PTF03-03 reuse → counts negatif clamp artar |
| AC-BKT-134 | 10x determinizm: fills içindeki 5 maliyet bileşeni 10 koşuda aynı |
| AC-BKT-135 | counts.paper_fills_partial ≥ 0 |
| AC-BKT-136 | counts.negative_fee_delta_clamped ≥ 0 |
| AC-BKT-137 | 5 maliyet bileşeni fixture varsayılanları ile doğru eşleşir (7.5/3.0/5.0/50ms/1.0) |

### KATEGORİ 6: Single Writer + CAP-1/CAP-2 (22 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-138 | G-BKT-05: Position state DOĞRUDAN yazılmıyor (engine çağrısı HARİÇ assign YOK) |
| AC-BKT-139 | G-BKT-06: PortfolioSnapshot DOĞRUDAN yazılmıyor |
| AC-BKT-140 | G-BKT-07: RiskDecision.approved DOĞRUDAN TRUE atanmıyor |
| AC-BKT-141 | G-BKT-08: RiskGate BYPASS YOK (skip_gate pattern = 0) |
| AC-BKT-142 | PositionEngine çağrısı var (S-PTF-01 reuse doğrulama) |
| AC-BKT-143 | PortfolioSnapshotEngine çağrısı var (S-PTF-02 reuse) |
| AC-BKT-144 | RollingPerformanceEngine çağrısı var (S-PTF-03 reuse) |
| AC-BKT-145 | RiskEngine çağrısı var (S-RSK-01 reuse) |
| AC-BKT-146 | RiskGate.validate çağrısı var (S-RSK-02 reuse — BYPASS YOK) |
| AC-BKT-147 | G-BKT-01: run_mode if/elif branch = 0 |
| AC-BKT-148 | G-BKT-01: source_type if/elif branch = 0 |
| AC-BKT-149 | G-BKT-02: datetime.now() çağrısı = 0 |
| AC-BKT-150 | G-BKT-02: time.time() çağrısı = 0 |
| AC-BKT-151 | G-BKT-02: time.sleep() çağrısı = 0 |
| AC-BKT-152 | G-BKT-03: QualityFlags mutate = 0 (attribute assignment YOK) |
| AC-BKT-153 | G-BKT-04: validate_quality çağrısı = 0 |
| AC-BKT-154 | G-BKT-04: validate_position çağrısı = 0 |
| AC-BKT-155 | G-BKT-04: validate_market çağrısı = 0 |
| AC-BKT-156 | ReplayClock deterministik — created_at_ms = replay end (NOT wall) |
| AC-BKT-157 | Tek bir run'da Position state sadece PositionEngine tarafından değiştirilmiş |
| AC-BKT-158 | Tek bir run'da Portfolio state sadece PortfolioEngine tarafından değiştirilmiş |
| AC-BKT-159 | CAP-1: run_mode / source_type BacktestRun metadata'da OKUNUR, branch DEĞİL |

### KATEGORİ 7: Safety 10 Kategori (10 AC — AST 0 match)
| AC # | Açıklama |
|------|----------|
| AC-BKT-160 | G-BKT-09: Canlı Exchange pattern = 0 match |
| AC-BKT-161 | G-BKT-10: REST API pattern = 0 match |
| AC-BKT-162 | G-BKT-11: WebSocket pattern = 0 match |
| AC-BKT-163 | G-BKT-12: Credential / API Key pattern = 0 match |
| AC-BKT-164 | G-BKT-13: Real Order / Para pattern = 0 match |
| AC-BKT-165 | G-BKT-14: Database pattern = 0 match |
| AC-BKT-166 | G-BKT-15: Message Queue pattern = 0 match |
| AC-BKT-167 | G-BKT-16: Short pattern = 0 match |
| AC-BKT-168 | G-BKT-17: Futures pattern = 0 match |
| AC-BKT-169 | G-BKT-18: Leverage > 1 pattern = 0 match |

### KATEGORİ 8: Risk Gate No-Bypass + Fail-Closed (18 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-170 | RiskDecision.approved=false → PaperOrder = None (ZORUNLU) |
| AC-BKT-171 | PaperOrder üretildi ise, her zaman corresponding RiskDecision.approved=true |
| AC-BKT-172 | Tüm PaperOrder'lar için: correlation_id = RiskDecision.correlation_id |
| AC-BKT-173 | RiskDecision 20-check'ten TEK KURAL fail → REJECTED |
| AC-BKT-174 | RiskGate 10-kural TEK kural fail → PaperOrder=None |
| AC-BKT-175 | LimitsSnapshot.max_leverage_allowed ZORUNLU = 1 (S-CON-02B) |
| AC-BKT-176 | max_leverage_allowed > 1 enjekte edilirse → RiskDecision REJECTED |
| AC-BKT-177 | Short pozisyon emri enjekte edilirse → RiskGate REJECT (S-CON-02B Position.side YASAK) |
| AC-BKT-178 | Sessiz onay YOK: input eksik → risk_decision REJECTED |
| AC-BKT-179 | RiskEngine exception → default REJECTED |
| AC-BKT-180 | RiskGate exception → default PaperOrder=None |
| AC-BKT-181 | Onaysız emir → fill = 0, position değişmez |
| AC-BKT-182 | 100% risk onaysız fixture → fills sayısı = 0 |
| AC-BKT-183 | 50% onay → fills ≤ 50% emir |
| AC-BKT-184 | corr/caus uyuşmayan emir → gate REDUCE |
| AC-BKT-185 | Opportunity actionable=false → risk kararına geçmez, counts düşmez? |
| AC-BKT-186 | StrategySignal HOLD → opportunity/ risk akışı optional (skip/continue policy deterministik) |
| AC-BKT-187 | Fail-closed assertion testi: high-confidence failure injection → 0 approved trade |

### KATEGORİ 9: Walk-Forward + OOS İzolasyon (18 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-188 | BacktestWindowSplit.train_start_ms < train_end_ms |
| AC-BKT-189 | VAL varsa: val_start_ms = train_end_ms (no gap, no overlap) |
| AC-BKT-190 | TEST varsa: test_start_ms = val_end_ms (no gap, no overlap) |
| AC-BKT-191 | test_end_ms = end_ms |
| AC-BKT-192 | TRAIN setindeki event timestamp'leri test setinde YOK (izole) |
| AC-BKT-193 | FeatureTrain'de → TEST setinden feature YOK |
| AC-BKT-194 | Parameter selection (varsayımsal) TEST verisi görmez |
| AC-BKT-195 | In-sample return_pct ayrı hesaplanmış (TRAIN+VAL) |
| AC-BKT-196 | OOS return_pct ayrı hesaplanmış (TEST) |
| AC-BKT-197 | is_contains_oos = test_start_ms is not None ise True |
| AC-BKT-198 | oos_returns_separated = True (insample / OOS raporu ayrı) |
| AC-BKT-199 | Fixture split oranları (70/15/15) doğrulanır (ms bazında) |
| AC-BKT-200 | Split değiştir (örn 80/10/10) → SHA256 farklı (deterministik) |
| AC-BKT-201 | TRAIN setindeki hiçbir decision > train_end_ms timestamp KULLANILAMAZ |
| AC-BKT-202 | VAL setindeki hiçbir decision > val_end_ms timestamp KULLANILAMAZ |
| AC-BKT-203 | TEST setindeki hiçbir decision geleceğe uzanmaz |
| AC-BKT-204 | Walk-forward foundation metadata alanları DOLUDUR |
| AC-BKT-205 | Gelecek ML training OOS için zemin hazır — şimdilik gerçek training YOK |

### KATEGORİ 10: Performans — S-PTF-02/03 Reuse (15 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-206 | Portfolio calculation İKİNCİ KEZ YAZILMIYOR — S-PTF-02 output'u doğrudan |
| AC-BKT-207 | Rolling performance İKİNCİ KEZ YAZILMIYOR — S-PTF-03 output'u doğrudan |
| AC-BKT-208 | Drawdown değeri S-PTF-02 max_drawdown_pct ile BİREBİR eşleşir |
| AC-BKT-209 | Total return S-PTF-02 total_return_pct ile BİREBİR eşleşir |
| AC-BKT-210 | Realized PnL S-PTF-02 ile eşleşir (Decimal string kesinlik) |
| AC-BKT-211 | Unrealized PnL S-PTF-02 ile eşleşir |
| AC-BKT-212 | Total fees S-PTF-03 ile eşleşir (24h delta toplamı) |
| AC-BKT-213 | Rolling 24h window = tam 86400000ms |
| AC-BKT-214 | Empty window → CORR_UNKNOWN_ROLLING ve CAUS_UNKNOWN_ROLLING fallback (ADN-PTF03-04) |
| AC-BKT-215 | Win rate doğru: (kazanan trade sayısı) / (toplam trade sayısı) |
| AC-BKT-216 | Max exposure = S-PTF-02 max exposure değeri |
| AC-BKT-217 | Trade sayısı S-PTR-01 fill sayısı ile tutarlı |
| AC-BKT-218 | Best/worst trade PnL doğru (trade listesinden) |
| AC-BKT-219 | S-PTF-03 10x determinizm korunur (aynı backtest input → aynı rolling çıktı) |
| AC-BKT-220 | Yeni rolling 24h SHA256 ile backtest SHA256 ilişkili (doğru hash) |

### KATEGORİ 11: Correlation / Causation Zinciri (15 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-221 | Tek pipeline zinciri (10 halka) → correlation_id SABİT (10 event'te aynı) |
| AC-BKT-222 | HALKA 2 causation_id = HALKA 1 event_id |
| AC-BKT-223 | HALKA 3 causation_id = HALKA 2 event_id |
| AC-BKT-224 | HALKA 4 causation_id = HALKA 3 event_id |
| AC-BKT-225 | HALKA 5 causation_id = HALKA 4 event_id |
| AC-BKT-226 | HALKA 6 causation_id = HALKA 5 event_id |
| AC-BKT-227 | HALKA 7 causation_id = HALKA 6 event_id |
| AC-BKT-228 | HALKA 8 causation_id = HALKA 7 event_id |
| AC-BKT-229 | HALKA 9 causation_id = HALKA 8 event_id |
| AC-BKT-230 | HALKA 10 causation_id = HALKA 9 event_id |
| AC-BKT-231 | Kırık zincir YOK: hiçbir event causation_id referansı null/unknown değil |
| AC-BKT-232 | correlation_id deterministic üretim: fixture seq numarası kullanılmış |
| AC-BKT-233 | Farklı tickler farklı correlation_id (çakışma 0) |
| AC-BKT-234 | 10x determinizm: corr/caus 10 koşuda aynı |
| AC-BKT-235 | causation zinciri döngü YOK (DAG — Directed Acyclic Graph) |

### KATEGORİ 12: Quality Flags + Skip (10 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-236 | invalid=true event → counts.quality_invalid_skipped++ |
| AC-BKT-237 | invalid=true event → sonraki 9 halka PASİF (skip) |
| AC-BKT-238 | quarantined=true event → counts.quality_quarantine_skipped++ |
| AC-BKT-239 | quarantined=true event → sonraki halkalar PASİF |
| AC-BKT-240 | QualityFlags.backtest içinde mutate EDİLMEDİ (CAP-2) |
| AC-BKT-241 | Validate_quality çağrısı backtest içinde YOK (CAP-2) |
| AC-BKT-242 | missing=true event → S-PTF-03 window dışı (ADN-PTF03-02 reuse) |
| AC-BKT-243 | stale=true event → FeatureEngine'e aktarılır, backtest karışmaz |
| AC-BKT-244 | Kaliteli ve kalitesiz karışık fixture → counts doğru |
| AC-BKT-245 | Kaliteli event'te de QualityFlags okunur ama değiştirilmez |

### KATEGORİ 13: Fail-Safe + Hata İzolasyon (12 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-246 | Eksik field'lı contract → deterministic reject, fail_safe_events listesine ekle |
| AC-BKT-247 | Yanlış contract type → reject, sonraki aşamaya PASS YOK |
| AC-BKT-248 | Simulation exception → try/except, event skip |
| AC-BKT-249 | PaperExecution exception → fill listesi BOŞ, position KORUNUR |
| AC-BKT-250 | PositionEngine exception → önceki position state KORUNUR |
| AC-BKT-251 | PortfolioEngine exception → önceki portfolio state KORUNUR |
| AC-BKT-252 | RiskEngine exception → REJECTED (fail-closed default) |
| AC-BKT-253 | RiskGate exception → PaperOrder=None |
| AC-BKT-254 | Hata sonrası 10x determinizm korunur (aynı hatayı 10 kez) |
| AC-BKT-255 | Sessiz onay YOK: high-volume bozuk input → 0 approved trade |
| AC-BKT-256 | fail_safe_events listesi deterministik (10 koşuda aynı) |
| AC-BKT-257 | Bütün run exception verse bile completed_successfully=false üretilir (crash YOK) |

### KATEGORİ 14: Assumptions + Artifact (12 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-258 | BacktestAssumptions frozen — runtime'da alan değiştirilemez (frozen test) |
| AC-BKT-259 | assumptions_sha256 = tüm alanların sıralı hash'idir |
| AC-BKT-260 | Tek bir alan değişti (örn fee 7.5→10) → assumptions_sha256 DEĞİŞİR |
| AC-BKT-261 | config_hash = pipeline_versions + assumptions hash |
| AC-BKT-262 | ResultArtifact serialization: JSON sort_keys=True, separators standart |
| AC-BKT-263 | save_artifact → load_artifact → orijinal run == yüklenen run (== test) |
| AC-BKT-264 | verify_artifact_hash doğruluğu: doğru hash → true |
| AC-BKT-265 | Artifact hash bozulursa → verify false |
| AC-BKT-266 | 10x koşu → artifact dosyası byte-by-byte aynı |
| AC-BKT-267 | Artifact SHA256 file content ile full_run_sha256 eşleşir |
| AC-BKT-268 | Provenance alanları artifact içinde tam olarak saklanır |
| AC-BKT-269 | metrics + counts artifact içinde bozulmadan saklanır |

### KATEGORİ 15: Strategy / Regime / Opportunity Reuse (10 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-270 | Strategy Engine DOĞRUDAN S-STR-01'den çağrılır — ikinci kez class YOK |
| AC-BKT-271 | StrategySignal LONG/FLAT/HOLD dışında DEĞER YOK (short yasak) |
| AC-BKT-272 | RegimeDetector DOĞRUDAN S-REG-01'den çağrılır — ikinci kez YOK |
| AC-BKT-273 | 6-state regime (bull/bear/sideways/high_vol/low_vol/transition) dışında DEĞER YOK |
| AC-BKT-274 | OpportunityScorer DOĞRUDAN S-OPP-01'den çağrılır |
| AC-BKT-275 | OpportunityScore 12 bileşen DOĞRU — backtest içinde yeniden üretim YOK |
| AC-BKT-276 | Aynı input için S-STR-01 direkt çağrı → backtest çıktısı BİREBİR aynı |
| AC-BKT-277 | Aynı input için S-REG-01 direkt çağrı → backtest çıktısı BİREBİR aynı |
| AC-BKT-278 | Aynı input için S-OPP-01 direkt çağrı → backtest çıktısı BİREBİR aynı |
| AC-BKT-279 | Regime uyum matrisi backtest tarafından korunur (yanlış rejim → HOLD) |

### KATEGORİ 16: Position Side — Long Only (5 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-280 | Tüm Position.side ∈ {LONG, FLAT} — SHORT YOK |
| AC-BKT-281 | Backtest içinde short emir enjekte edilirse → RiskGate REDUCE |
| AC-BKT-282 | PaperFill'de short taraf YOK (her zaman long giriş/çıkış flat) |
| AC-BKT-283 | Leverage her zaman 1.0 — S-CON-02B LimitsSnapshot ile doğrulanır |
| AC-BKT-284 | Position side değiştirme sadece PositionEngine tarafından yapılır |

### KATEGORİ 17: pyproject.toml + Contract Version (4 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-285 | G-BKT-21: pyproject.toml dependencies = [] — yeni runtime DEP YOK |
| AC-BKT-286 | G-BKT-22: CONTRACTS.md CONTRACT_VERSION = 1.0.0 — değişmedi |
| AC-BKT-287 | 19 canonical contract field isimleri değişmedi |
| AC-BKT-288 | Yeni canonical contract OLUŞTURULMADI |

### KATEGORİ 18: Regression Koruması (16 AC — 16 hikaye için)
| AC # | Açıklama |
|------|----------|
| AC-BKT-289 | S-RDH-01 testleri: PASS (hiçbiri FAIL olmadı) |
| AC-BKT-290 | S-RDH-02 testleri: PASS |
| AC-BKT-291 | S-PLN-01 testleri: PASS |
| AC-BKT-292 | S-CON-02A testleri: PASS |
| AC-BKT-293 | S-CON-02B testleri: PASS |
| AC-BKT-294 | S-CON-02C testleri: PASS |
| AC-BKT-295 | S-FEA-01 testleri: PASS |
| AC-BKT-296 | S-REG-01 testleri: PASS |
| AC-BKT-297 | S-STR-01 testleri: PASS |
| AC-BKT-298 | S-OPP-01 testleri: PASS |
| AC-BKT-299 | S-RSK-01 testleri: PASS |
| AC-BKT-300 | S-RSK-02 testleri: PASS |
| AC-BKT-301 | S-PTR-01 testleri: PASS |
| AC-BKT-302 | S-PTF-01 testleri: PASS |
| AC-BKT-303 | S-PTF-02 testleri: PASS |
| AC-BKT-304 | S-PTF-03 testleri: PASS |

### KATEGORİ 19: Boundary + Edge Case + Matrix (8 AC)
| AC # | Açıklama |
|------|----------|
| AC-BKT-305 | 1 event (minimal) fixture → run SUCCESSFULLY, SHA256 deterministic |
| AC-BKT-306 | 10000 event (büyük) fixture → run SUCCESSFULLY (bellek/time sınırı yok) |
| AC-BKT-307 | Tek event (ts=0) → extreme boundary |
| AC-BKT-308 | Çoklu sembol (3+) aynı anda → correlation/sıralama korundu |
| AC-BKT-309 | Empty fixture → completed_successfully=true, empty window fallback (ADN-PTF03-04) |
| AC-BKT-310 | Fixture sonunda 24h dolmamış pencere → rolling değerleri doğru (partial window) |
| AC-BKT-311 | Tüm event'ler risk REJECTED → 0 fill, 0 position değişikliği (deterministic) |
| AC-BKT-312 | Fixture determinizm: S-RDH-02 Registry hash ile S-BKT run hash ilişkili (doğru kanıt) |

**TOPLAM AC: 312 ADET** (≥300 hedefi aşıldı)

---

## 21. Definition of Done (DoD — TOPLAM 38 ADET)

Her DoD doğrulanabilir, objektif ve ölçülebilirdir.

| DoD # | Kriter | Doğrulama Yöntemi |
|-------|--------|-----------------|
| DoD-BKT-001 | 312 AC'den PASS sayısı = 312 (hiçbiri FAIL/SKIP olmamalı) | pytest test report |
| DoD-BKT-002 | 10x determinizm testi: full_run_sha256 set len = 1 | `test_runner_determinism_10x.py` |
| DoD-BKT-003 | Runtime leakage testleri PASS (0 leakage detected) | `test_leakage_runtime.py` |
| DoD-BKT-004 | Static AST leakage taraması: 0 match | `test_leakage_static_ast.py` |
| DoD-BKT-005 | Single Writer Guards PASS (G-BKT-05-08): 0 match | AST tarama |
| DoD-BKT-006 | CAP-1 Parity Guards PASS (G-BKT-01-02): 0 match | AST tarama |
| DoD-BKT-007 | CAP-2 Quality Guards PASS (G-BKT-03-04): 0 match | AST tarama |
| DoD-BKT-008 | Safety 10 Kategori Guards PASS (G-BKT-09-18): 0 match | AST tarama |
| DoD-BKT-009 | S-PTR-01 reuse doğrulandı: ikinci kez fill model YAZILMADI | G-BKT-20 PASS |
| DoD-BKT-010 | S-RSK-02 gate bypass = 0 onaylandı | test_risk_gate_nobypass.py |
| DoD-BKT-011 | S-PTF-01/02/03 reuse doğrulandı: ikinci kez portfolio hesabı YOK | AST + karşılaştırma |
| DoD-BKT-012 | S-FEA-01 strict_closed_only doğru kullanıldı | test + feature karşılaştırma |
| DoD-BKT-013 | S-REG-01 6-state reuse doğru | regime karşılaştırma testi |
| DoD-BKT-014 | S-STR-01 Trend+Momentum reuse doğru | strategy karşılaştırma testi |
| DoD-BKT-015 | S-OPP-01 12-component reuse doğru | opportunity karşılaştırma testi |
| DoD-BKT-016 | S-RDH-01/02 replay bundle doğru akışta kullanıldı | provenance hash eşleşmesi |
| DoD-BKT-017 | S-PLN-01 event bus corr/caus korunur | corr/caus zincir testleri |
| DoD-BKT-018 | Event 4'lü tie-break sıralama doğruluğu 100% | test_pipeline_order.py |
| DoD-BKT-019 | 10-halka pipeline ZORUNLU sıra takip edildi (1→10) | event sıra denetim |
| DoD-BKT-020 | 5'li maliyet modeli (fee/spread/slip/latency/partial) her fill'de var | maliyet denetim testi |
| DoD-BKT-021 | Negative fee delta clamp → counts doğru (ADN-PTF03-03) | fee clamp testi |
| DoD-BKT-022 | Duplicate KEEP FIRST policy → counts doğru (ADN-PTF03-01) | duplicate testi |
| DoD-BKT-023 | Empty window fallback CORR/CAUS UNKNOWN doğru (ADN-PTF03-04) | empty fixture testi |
| DoD-BKT-024 | Fail-closed default → bütün high-risk injection senaryolarında 0 onay | fail_closed testi |
| DoD-BKT-025 | Correlation/Causation 10-halka zinciri KOPMADAN | zincir testi PASS |
| DoD-BKT-026 | BacktestWindowSplit 3-set izolasyonu (TRAIN/VAL/TEST overlap 0) | split testi |
| DoD-BKT-027 | OOS return_pct ayrı hesaplanmış, raporlanmış | OOS testi |
| DoD-BKT-028 | Artifact save/load/verify integrity doğru | artifact testi |
| DoD-BKT-029 | ResultArtifact SHA256 = BacktestRun full_run_sha256 | hash eşleşmesi |
| DoD-BKT-030 | pyproject.toml dependencies = [] DEĞİŞMEDİ | G-BKT-21 + diff |
| DoD-BKT-031 | CONTRACT_VERSION = 1.0.0 DEĞİŞMEDİ | G-BKT-22 |
| DoD-BKT-032 | Regression: Önceki 16 hikayenin testleri = 3629 PASS + 7 SKIP (SIFIR FAIL) | `pytest tests/ -q --tb=no` |
| DoD-BKT-033 | Yeni test sayısı ≥ 300 (Hedef 312 AC karşılığı) | test count |
| DoD-BKT-034 | Toplam test sayısı (yeni + regression) ≥ 3629 + 300 = 3929 collected | pytest |
| DoD-BKT-035 | Position side ∈ {LONG, FLAT} — SHORT 0 | AST + tüm position kayıtları scan |
| DoD-BKT-036 | Leverage = 1.0 — LimitsSnapshot.max_leverage_allowed > 1 YOK | tüm risk kararları scan |
| DoD-BKT-037 | 9 ADN fixture varsayılanları dokümanda açıkça yazıldı, production zorlanmadı | spec denetim |
| DoD-BKT-038 | Tam determinizm kanıt: 10x koşu → (event, fill, pos, pf, perf) 5'lisinin sorted dict == | to_sorted_dict() 10x karşılaştırma |

**TOPLAM DoD: 38 ADET** (≥35 hedefi aşıldı)

---

## 22. Yeni Test Planı (TOPLAM 308 YENİ TEST — Hedef ≥300)

### Test Dağılımı (17 test dosyası, 308 yeni test)

| Test Dosyası | Test Sayısı | Kapsadığı AC Kategorileri |
|-------------|-------------|--------------------------|
| `test_runner_determinism_10x.py` | 28 | Kategori 2 (Determinism 10x) |
| `test_pipeline_order.py` | 35 | Kategori 3 (Event Sıra + Tie-Break) + boundary |
| `test_leakage_static_ast.py` | 30 | Kategori 4 (Static Leakage + 19 Guard) |
| `test_leakage_runtime.py` | 32 | Kategori 4 (Runtime Leakage 10 halka) |
| `test_single_writer_ast.py` | 18 | Kategori 6 (Single Writer + CAP-1/CAP-2) |
| `test_cap1_parity.py` | 18 | Kategori 6 (CAP-1 branch + tarih fonksiyonu) |
| `test_cap2_quality.py` | 12 | Kategori 6 (CAP-2) + Kategori 12 (Quality) |
| `test_safety_10_category.py` | 12 | Kategori 7 (Safety 10 kategori AST 0) |
| `test_cost_model_reuse.py` | 25 | Kategori 5 (S-PTR-01 reuse + 5 maliyet) |
| `test_risk_gate_nobypass.py` | 22 | Kategori 8 (Risk Gate No-Bypass) |
| `test_portfolio_reuse.py` | 20 | Kategori 10 (S-PTF-02/03 reuse) |
| `test_backtest_window_split.py` | 22 | Kategori 9 (Walk-Forward + OOS) |
| `test_corr_caus_chain.py` | 18 | Kategori 11 (Corr/Caus Zinciri) |
| `test_fail_closed.py` | 15 | Kategori 13 (Fail-Safe) |
| `test_artifact_hash.py` | 15 | Kategori 14 (Assumptions + Artifact) |
| `test_regression_backward.py` | 16 | Kategori 18 (Regression 16 hikaye) |
| `test_strategy_regime_opp_reuse.py` | 10 | Kategori 15 (S-STR/REG/OPP reuse) |
| **TOPLAM** | **308 YENİ TEST** | **19 kategori, 312 AC kapsama** |

### Test Yazım Stratejisi
- **Orthogonal**: Her AC için en az 1 test
- **Matrix Parametrize**: 4'lü tie-break, 5 maliyet, 10 halka, 9 ADN — pytest parametrize ile çarp
- **Boundary**: t, t-1, t+1 ms; 0, 1, 10K event; empty/full window; 0/1 leverage; 0/partial/full fill
- **Replay Fixture Kullanımı**: S-RDH-01 3 sembol fixture'ını testlerde direkt import et (yeniden yaratma!)
- **Fail Injection**: Monkeypatch ile S-RSK-01 exception, S-PTR-01 exception, S-FEA-01 bozuk çıktı enjekte et
- **Regression Guard**: Her test dosyasının başında `skip_if_backtest_not_implemented` helper — şu anda SKIP, implementation sonrası PASS

---

## 23. Regression Koruma Planı

### Hedef
S-BKT-01 implementation sonrası **MEVCUT 3629 PASS + 7 SKIP = %100 KORUNACAK**.

### Yöntem
1. **Pre-Freeze**: Implementation ÖNCESİ pytest çıktısını SHA256 ile kaydet (zaten = `3629 passed, 7 skipped in 18.79s`)
2. **Her commit'te (implementation sırasında)** `pytest tests/ -q --tb=no` koş — FAIL varsa implementation DURDUR
3. **Kırılma Noktaları Analizi**: Eğer S-BKT-01 changes mevcut 16 hikayeden birini kırarsa:
   - Önce: Değişikliği geri al
   - Sonra: Kırılan hikayenin contract'ı ihlal edildi mi diye analiz et
   - Sadece ve sadece: Contract değişikliği PLANLANMIŞSA ve AC ile onaylanmışsa devam et — aksi halde Backtest kodunu DÜZELT
4. **Final Verification**: Implementation SONU — pytest = 3629 PASS + 7 SKIP (eski) + 308 yeni PASS (S-BKT-01) = **TOPLAM 3937 COLLECTED, 3930 PASS, 7 SKIP (0 FAIL)** beklenir

---

## 24. Implementation Readiness Değerlendirmesi

| Kontrol | Durum | Not |
|---------|-------|-----|
| Ön koşullar (24 kaynak okundu) | ✅ TAMAMLANDI | 24/24 planning + hikaye spec |
| Regression baseline doğrulandı | ✅ 3629 PASS + 7 SKIP | exit 0 |
| Bloklayıcı kurallar netleştirildi | ✅ 7 Ana Kural | AD-7/13/24, CAP-1/2, Safety, Deps=[] |
| 10-Halka Pipeline tasarımı | �% 100 detay | Her halka: giriş/çıkış/reuse modül/kontrol |
| BacktestRun metadata şeması | ✅ Frozen dataclass | 22+ field + 5 hash |
| 5'li Maliyet Model Reuse | ✅ S-PTR-01 1:1 | İkinci kez yazılmama kuralı |
| Leakage Kontrol Mekanizmaları | ✅ Static + Runtime | 22 leakage test planı |
| Event Sıra + Tie-Break | ✅ 4'lü anahtar + 10 halka sıra | 25 AC kapsama |
| Walk-Forward + OOS Foundation | ✅ BacktestWindowSplit 3-set | 18 AC kapsama |
| Modül Reuse Matrisi | ✅ 13 modül %100 reuse | İkinci kez implementasyon YOK |
| Corr/Caus Zinciri | ✅ 10 adım, korunan | 15 AC |
| Quality + Fail-Closed | ✅ CAP-2 + AD-19 | 22 AC |
| Assumptions + Artifact | ✅ Versionlu + Hash'lenmiş | 12 AC |
| 9 Açık Karar (ADN) | ✅ Yazıldı — 9 madde | Fixture defaults |
| Implementation Guards | ✅ 22 Guard (G-BKT-01 → G-BKT-22) | Static AST testleri |
| Dosya Yapısı Planı | ✅ 6-8 .py + 17 test dosyası | Standart konum |
| AC Sayısı | ✅ 312 (≥300 hedef) | 19 kategori |
| DoD Sayısı | ✅ 38 (≥35 hedef) | Hepsi doğrulanabilir |
| Yeni Test Planı | ✅ 308 (≥300 hedef) | 17 dosya, orthogonal |
| Regression Koruma Planı | ✅ 3629 PASS + 7 SKIP | 16 hikaye %100 koruma |
| CONTRACT_VERSION 1.0.0 | ✅ Korunur | Yeni contract YOK |
| pyproject.toml deps=[] | ✅ Korunur | Yeni runtime dep YOK |
| Git Kuralı (bu create-story için) | ✅ No commit | Şu anda sadece spec yazıldı |

---

### Implementation Readiness: **READY-FOR-DEV** ✅

Tüm ön koşullar sağlanmıştır. Spec, 312 AC, 38 DoD ve 308 test planı ile birlikte S-BKT-01 Deterministic Replay-Driven Backtest Engine hikayesi **implementation fazına hazırdır**.

`bmad-dev-story S-BKT-01` workflow'u ile bir sonraki aşamaya geçilebilir.
