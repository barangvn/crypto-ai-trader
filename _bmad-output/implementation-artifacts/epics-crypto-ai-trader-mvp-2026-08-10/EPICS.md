---
stepsCompleted:
  - step-01-validate-prerequisites-and-extract-requirements
  - step-02-design-epics-and-stories
  - step-03-first-story-prioritization-and-boundary-verification
  - step-04-final-validation-and-reporting
inputDocuments:
  - ../../planning-artifacts/briefs/brief-crypto-ai-trader-2026-08-04/brief.md
  - ../../planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md
  - ../../planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/SPEC.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/CONTRACTS.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/LIFECYCLE.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/API.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md
---

# Crypto AI Trader - Epic Breakdown (MVP v1, Modular Monolith)

## Overview

Bu doküman, Crypto AI Trader MVP’sini uygulanabilir, küçük, tek başına test edilebilir dikey dilimlere (14 Epic, ~33 Story) böler. **Tüm kararlar AD-1..AD-25 (binding) mimari kararlarını korur.** ADN-01..ADN-12 açık kararlar zorla çözülmez; ilgili hikâyeler "varsayılan + değiştirilebilir test" yaklaşır ya da bağımlılık olarak işaretlenir.
- MVP hard boundary: **Spot only, futures/lev/short yok, gerçek emir/para/API key YOK, paper-only, replay-first.**
- İlk uygulanabilir hikâye (kullanıcının istediği omurga POC): **S-RDH-01**

---

## Requirements Inventory (Step-01 çıktısı korunur)

### Functional Requirements

```
FR-001 [PRD]: Exchange-independent adapter contract for public ticker, OHLCV, trades, best bid/ask, order-book updates, metadata, historical/replay data, adapter health.
FR-002 [PRD]: Exchange-specific connection/schema/rate-limit behavior only behind adapter boundary.
FR-003 [PRD]: Replay/historical data as first-class data source; v1 does NOT require live exchange connectivity.
FR-004 [PRD]: Every normalized market event carries source, instrument, exchange ts, receive ts, event type, data-quality status.
FR-005 [PRD]: Surface stale data, duplicate events, ordering/sequence gaps, disconnects, resync events, malformed payloads.
FR-006 [PRD]: Do NOT create new paper orders from pair with stale/incomplete/unhealthy data.
FR-007 [PRD]: Retain provenance linking features/signals/backtest results/paper decisions back to their input data version/range.
FR-008 [PRD]: Scanner evaluates configurable spot universe without assuming a particular exchange.
FR-009 [PRD]: For each eligible pair, calculate liquidity/volume/volatility/spread/momentum/trend/order-book imbalance/opportunity-score inputs.
FR-010 [PRD]: Filter pairs by configurable data health, min liquidity, volume, spread, volatility, market eligibility rules.
FR-011 [PRD]: Calculate versioned OHLCV-derived technical indicators; disclose their inputs in the decision record.
FR-012 [PRD]: Track BTC reference effects and market correlations as contextual/risk inputs only (not causation proof).
FR-013 [PRD]: Record why a pair was excluded/ranked/selected.
FR-014 [PRD]: Assign 6 scored regime states (Bull/Bear/Sideways/HighVol/LowVol/TransitionUncertain).
FR-015 [PRD]: Each regime result carries confidence + data/feature version.
FR-016 [PRD]: Transition/Uncertain is first-class safety state that reduces strategy eligibility.
FR-017 [PRD]: Strategy registry declares regimes each strategy supports / is cautious / rejects.
FR-018 [PRD]: Risk policy supports regime-sensitive limits; HighVol/Transition never auto-increases exposure.
FR-019 [PRD]: Opportunity record contains pair/ts/direction/strategy/regime/confidence/expected return est/risk est/volatility/liquidity/spread/est fees/est slippage/regime compat score.
FR-020 [PRD]: Opportunity score is decomposable; component values + weights visible to operator.
FR-021 [PRD]: Expected return treated as estimate with uncertainty, not a promise.
FR-022 [PRD]: Candidate requires all of: valid data, strategy eligibility, acceptable regime compat, sufficient confidence, positive net-of-cost expectation, Risk Engine approval before simulation.
FR-023 [PRD]: AI confidence alone never authorizes simulation or overrides validation/risk rejection.
FR-024 [PRD]: Label low-confidence/high-cost/degraded opportunities as non-actionable with rejection reason.
FR-025 [PRD]: Pluggable strategy architecture (Trend/Momentum/…) without changing scanner/risk/paper contracts.
FR-026 [PRD]: Each strategy declares required inputs/eligible regimes/entry/exit/invalidation criteria/config version/rationale.
FR-027 [PRD]: MVP activates at most two strategies: Trend Following + Momentum (exact rules open).
FR-028 [PRD]: Record strategy-specific and regime-specific performance (no aggregation that hides bad regime behavior).
FR-029 [PRD]: Strategy weighting may use approved compat/evaluation results; cannot be changed by unvalidated live-learning process.
FR-030 [PRD]: AI capabilities: classification/regime/opp scoring/probability/feature importance/strategy weighting.
FR-031 [PRD]: AI outputs are versioned, reproducible, attributable to model/feature/data version; carry confidence/uncertainty.
FR-032 [PRD]: AI does NOT submit orders, bypass risk, alter sizes, or change its own champion status without governed lifecycle.
FR-033 [PRD]: Governed lifecycle: Data → Train → Backtest → OOS → Walk-Forward → Paper → Eval → Challenger → Approval Gate → Champion → (Live disabled v1).
FR-034 [PRD]: v1 lifecycle stops at Paper/Eval/Challenger/Approval Gate; Live is out of scope.
FR-035 [PRD]: Candidate failing required stage/minimum sample is rejected + retained with rejection evidence.
FR-036 [PRD]: Registry records model/strategy id, version, train period, feature set, params, eval windows, metrics, approval status, rollback predecessor.
FR-037 [PRD]: Challenger runs in isolated backtest/paper eval; does NOT auto replace Champion.
FR-038 [PRD]: Promotion requires comparison across net return/maxDD/Sharpe/Sortino/profit factor/stability/trade count/fees/slippage/regime perf.
FR-039 [PRD]: Promotion rejected when high return paired with high DD/insufficient trades/unstable regime perf/degraded costs/weaker OOS/WalkForward.
FR-040 [PRD]: When degradation thresholds breach, rollback to prior Champion OR safe observe-only state.
FR-041 [PRD]: Every model/strategy change is auditable: approver/rationale/evidence/timestamp/prior state.
FR-042 [PRD]: Train/val/test/OOS are time-ordered, mutually controlled against leakage.
FR-043 [PRD]: Eval process explicitly checks + documents feature leakage, look-ahead bias, survivorship/delisting, split contamination, target leakage.
FR-044 [PRD]: Walk-forward validation uses versioned rolling/expanding windows; window definitions recorded with results.
FR-045 [PRD]: Backtests model configured fees, slippage, latency, sizing, SL/TP, regime context, multiple strategies, portfolio risk.
FR-046 [PRD]: Backtest result discloses its data range/source/universe/assumptions/versions/limitations.
FR-047 [PRD]: Paper trading uses realtime/replay market data without sending orders to any exchange.
FR-048 [PRD]: Paper engine models configurable fees/slippage/latency/spread/partial fills; all assumptions reported.
FR-049 [PRD]: Execute logical pipeline: Signal → Valid → Risk → Sizing → Execution Decision → Order Simulation → Result.
FR-050 [PRD]: Validation + Risk each independently can reject a signal; rejection terminates the pipeline with reason logged.
FR-051 [PRD]: Simulated position carries entry/exit basis, size, SL/TP policy, cost model, realized/unrealized PnL, risk state, source decision ids.
FR-052 [PRD]: Risk Engine is strategy/model-independent with authority to reject candidates.
FR-053 [PRD]: Risk policy supports: sizing, max pos, max portfolio exposure, max open pos, max daily loss, max drawdown, max consecutive losses, SL, TP, correlation/exposure limits, fee/slippage controls, long-only spot constraints.
FR-054 [PRD]: Emergency stop + kill switch halt new paper simulations immediately + surface reason/state to operator.
FR-055 [PRD]: Market-data/adapter/API failure triggers safe mode blocking new simulations for affected scope; recovery requires validated health.
FR-056 [PRD]: Risk policy values/overrides/exceptions/rejections are versioned + audit logged.
FR-057 [PRD]: Dashboard shows: system/adapter status, market status, active opportunities, AI confidence, regime, active strategies, paper positions, PnL, drawdown, models/Champion/Challenger, learning/eval history, risk state, logs, emergency stop state.
FR-058 [PRD]: Dashboard allows operator to inspect decision trail for every opp/rejected candidate/simulated order/model promotion/rollback.
FR-059 [PRD]: Performance reports include PnL, total/net return, win/loss rate, avg win/loss, profit factor, max DD, Sharpe, Sortino, fees, slippage, latency, trade count, strategy/model/regime performance.
FR-060 [PRD]: Never present gross metrics without net-of-cost and risk context.
FR-061 [PRD]: v1: never create/store/request/use any API key/secret/trading credential.
FR-062 [PRD]: Future credentials: secrets manager, isolated keys, least privilege, access control, audit log, explicit trading permission gates.
FR-063 [PRD]: Future real-trading activation requires separate approved phase, threat model, legal/compliance review, tested kill switch, explicit human authorization.
FR-064 [SPEC/CAP-1 contracts]: Live/replay parity enforced via same canonical envelope + same contracts in Feature/Regime/Strategy/Risk/Portfolio code (no `run_mode` conditional branches inside those modules).
FR-065 [SPEC/CAP-2 contracts]: Data-quality flags (stale/missing/duplicate/out-of-order/invalid/quarantined/degraded) propagate end-to-end in envelopes; consumers act on flags without RPC to validator.
FR-066 [SPEC/CAP-3 contracts]: Strategy plugins consume only typed StrategyContext; forbidden imports (network/DB/filesystem/exchange) are contract-tested.
FR-067 [SPEC/CAP-4 contracts]: Paper orders require a prior same-correlation RiskDecision.approved; RiskDecision shape explicitly carries decision/reason/limits/position sizing.
FR-068 [SPEC/CAP-5 contracts]: ModelVersion.status mutates ONLY through registry `request_transition(...)` commands; state machine graph exactly matches LIFECYCLE.md.
FR-069 [SPEC/CAP-6 contracts]: Dashboard MVP API surface is limited to 10 read groups + 2 permissioned writes; no live-execution/keys/funding routes exist.
FR-070 [BRIEF]: Future extensibility for multiple exchanges/strategy families/model families; all behind stable adapter/plugin boundaries.
FR-071 [BRIEF MVP]: First end-to-end vertical slice: replay → analysis → backtest → paper → performance → registry evidence.
```

### NonFunctional Requirements

```
NFR-001 [PRD]: Measure ingest-to-decision and simulation latencies; numeric SLOs are ADN (open) per provider/universe/deployment.
NFR-002 [PRD]: Adapter disconnects, rate limits, malformed messages, data gaps are detectable, logged, fail-closed for affected scope.
NFR-003 [PRD]: Scanner scales pair universe without changing public contracts; capacity targets deferred until universe is selected (ADN).
NFR-004 [PRD]: Structured logs, health metrics, decision traces, alerts, data-quality indicators, risk events, model-drift signals available for investigation.
NFR-005 [PRD]: Adapter/pair failures isolated where possible and never silently corrupt unrelated decisions.
NFR-006 [PRD]: Raw provenance, timestamp semantics, sequence gaps, versioned transformations allow reconstruction of any reported decision.
NFR-007 [PRD]: Backtest/eval/model-promotion records are reproducible from versioned inputs/configs/assumptions.
NFR-008 [PRD]: v1 operates without secrets/trading credentials; future privileged paths default deny and remain separately gated.
NFR-009 [ARCH AD-1]: MVP topology is single-repo modular monolith (no microservice split in MVP).
NFR-010 [ARCH AD-4]: Live and Replay pipelines produce contract-identical events; consumers use only clock_ref + source_type for behavioral differentiation (no branching inside domain code).
NFR-011 [ARCH AD-5]: Data quality is hard gate: failures → quarantine, symbol health unhealthy, affected strategies stop, new paper orders blocked, alert emitted.
NFR-012 [ARCH AD-6]: Internal typed event bus (in-process) + PostgreSQL outbox/inbox for durability; no external broker in MVP.
NFR-013 [ARCH AD-7/13/24]: Single-writer mutation ownership (raw market→ingest, features→processing, PaperOrder/Fill/Position/Portfolio→PortfolioSimulator, registry/status→ModelRegistry). Backtest does NOT own trading state tables directly.
NFR-014 [ARCH AD-10]: AI no execution authority; all execution paths require validation + risk approval.
NFR-015 [ARCH AD-11]: Risk engine is FINAL approval gate; failure rejects pipeline, no fallback.
NFR-016 [ARCH AD-18]: 4 environments (dev/test/paper/production) strictly separated config/namespace/artifact paths.
NFR-017 [ARCH AD-19]: All 10 defined failure modes default safe: block execution, narrow scope, mark state, alert.
NFR-018 [ARCH AD-20]: All bounded contexts deterministically testable via fixture/replay inputs; contract/replay/failure-injection/regression/paper-simulation tests are architectural mandate.
NFR-019 [SPEC]: All timestamps are UTC ISO-8601 + 3-digit ms; monetary values use Decimal; correlation_id/causation_id required on all envelope events.
NFR-020 [SPEC MVP API]: Only two write endpoints (system emergency-stop, risk kill-switch); write permission boundary and audit required.
```

### Additional Requirements

```
- AD-1..AD-25 binding invariants; each story explicitly lists applicable AD refs.
- CAP-1..CAP-6 are "success of story" verifiers; every story that exercises a CAP explicitly lists it + dedicated test requirement.
- 19 event/entity contracts + envelope + typed contexts (CONTRACTS.md §1-3) and LIFECYCLE.md state machine are authoritative schemas for all inputs/outputs.
- Open Decisions ADN-01..ADN-12 are preserved; stories only use sensible defaults if swappable via tests.
```

### UX Design Requirements

```
UX-DELIBERATELY-EMPTY-001: No upstream UX contract; MVP dashboard surface = API only per API.md. Future bmad-ux workflow owns visuals/interactions.
```

### FR Coverage Map

Her hikâye Acceptance Criteria kısmında açıkça FR referansı taşır; %100 FR kapsama hedefi korunur.

---

## Epic List (İmplementasyon sırası = Epic sırası)

| Sıra | Epic ID   | Epic Title                                       | Hikâye Sayısı | Ana Odak                                              |
| ---- | --------- | ------------------------------------------------ | ------------- | ----------------------------------------------------- |
| 1    | E-FND     | Project Foundation & Environment                 | 3             | Repo yapısı, config, env ayrımı, logging, test infra   |
| 2    | E-CON     | Canonical Contracts & Schema Enforcement         | 4             | 19 sözleşme + kalite + zarflar + forbidden-pattern test |
| 3    | E-RDH     | Replay Data & Adapter Abstraction                | 3             | Replay adapter, normalizer, validation, data quality   |
| 4    | E-PLN     | Internal Event Pipeline (Typed Bus + Outbox)     | 3             | In-process bus, correlation, outbox, replay determinizm |
| 5    | E-FEA     | Feature Engineering & Technical Indicators       | 3             | Sürüm kontrollü özellikler, göstergeler, determinizm   |
| 6    | E-REG     | Market Regime Detector                           | 2             | 6 rejim, confidence, tüketim                           |
| 7    | E-STR     | Strategy Engine & 2 MVP Strategies               | 3             | Plug-in arayüzü, Trend/Momentum, purity testleri       |
| 8    | E-AIS     | Opportunity Scoring & Baseline AI                | 3             | Bileşen skor, baseline model, explainability           |
| 9    | E-RSK     | Independent Risk Engine & Kill Switch            | 4             | Limitler, pozisyon boyutlama, stale/kill, onay kapısı  |
| 10   | E-BKT     | Replay-Driven Backtest Engine                    | 3             | Maliyet modelleri, leakage kontrolleri, metrikler      |
| 11   | E-PTR     | Paper Trading Execution Simulator                | 2             | Sanal emirler, fill model, kısmi dolum                 |
| 12   | E-PTF     | Portfolio Simulator & Performance Tracking       | 3             | Tek-yazar PnL/pozisyon, metrikler, drawdown            |
| 13   | E-MDL     | Model Lifecycle / Registry & Champion-Challenger  | 4             | Kayıt, değerlendirme, promosyon, rollback, lifecycle    |
| 14   | E-API     | MVP API Surface & Observability                  | 4             | 10 grup + 2 izinli yazma, metrikler, alert/audit       |

**Toplam:** 14 Epic, 41 Hikâye (her biri tek başına test edilebilir).

---

## Epic 1 — E-FND: Project Foundation & Environment

### Epic Goal
MVP kod tabanını AD-1 (modular monolith) + AD-18 (env separation) uyarınca kur; konfigürasyon, loglama, pytest infra, v1 güvenlik sınırlarını (hard boundary) teknik olarak koruyan temel kontrol noktalarını oluştur.

### Scope
- Monolith repo klasör iskeleti (app/ingest, contracts, processing, decisioning, simulation, governance, platform)
- Environment config (dev/test/paper/production) ayrımı (AD-18)
- Structured log (correlation_id ile) + base metrics altyapısı
- Pytest (unit/integration/contract/replay) infra + forbidden hard-boundary testleri (future-live, API key, short/lev)
- `contract_version` (1.0.0) ve proje sürüm sabitleri

### Out of Scope
- Veritabanı kurulumu (E-PLN/E-FEA sonrası)
- Herhangi bir business logic
- Canlı borsa bağlantısı / API key (KESİNLİKLE YOK)

### Stories
#### Story S-FND-01: Modular Monolith Code Skeleton & Environment Separation
- **Goal:** Tek repoda AD-1 sınırlarına uyan bounded context klasörlerini ve env ayrımı yapısını kur.
- **Scope:** `app/` klasör iskeleti, `configs/{dev,test,paper,production}.yaml` ayrımı, secret-free (boş) env örnekleri, `.env.example` (API key bölümleri yok, v1 warning).
- **Out of scope:** DB migration, business logic, test framework.
- **Dependencies:** Yok.
- **Acceptance Criteria:**
  - Given empty repo, When `S-FND-01` uygulanır, Then AD-1’de tanımlanan her bounded context için klasör (ingest/contracts/processing/decisioning/simulation/governance/platform) mevcuttur.
  - Given 4 ortam configs, Then her ortam ayrı `db_namespace`, `artifact_path`, `run_mode_default` değerleri içerir (AD-18).
  - Given development env, Then config dosyası "trading_permission_default = false", "allow_api_keys = false", "max_leverage_allowed = 1", "allow_short = false" sabitlerini taşır (v1 hard boundary).
- **Contract references:** CONTRACTS.md Ortak Tipler (RunMode), SPEC Constraints (PRD hard boundary)
- **Architecture Decisions:** AD-1, AD-18, AD-20
- **Open Decisions:** ADN-10 (object storage path örneği boş bırakılır)
- **Test requirements:** Unit test: klasör/ortam sayısı, env hardening sabitlerini doğrula.
- **Definition of Done:** (1) Env/klasörler mevcut, (2) config dosyalarında yukarıdaki 4 safety kilidi mevcut, (3) lint ok.

#### Story S-FND-02: Structured Logging & Base Observability Hooks
- **Goal:** AD-17 uyarınca correlation_id/trace_id’yi taşıyan structured log altyapısı ve temel sayaç metrik arayüzünü kur.
- **Scope:** Structured logger (JSON), correlation context (propagation helper), base metrics (counter/histogram/ gauge) soyut arayüz, log line’daki zorunlu alanlar (ts, level, module, correlation_id, causation_id, msg).
- **Out of scope:** Prometheus/Grafana deployment (E-API).
- **Dependencies:** S-FND-01
- **AC:**
  - Given logger, When correlation verilir, Then tüm log satırları `correlation_id` taşır.
  - Given module event, Then metrics arayüzü çağrı yapıldığında concrete export yokken de testte no-op çalışır.
- **Contract refs:** CONTRACTS.md §1 Envelope metadata (correlation/causation/trace)
- **AD refs:** AD-17, AD-20
- **ADN:** Yok
- **Test reqs:** Unit test: log line structure + correlation propagation
- **DoD:** Logger + metrics pass unit, structured output contains corr.

#### Story S-FND-03: Pytest Infrastructure + Hard Boundary Contract Tests (v1 Safety Gates)
- **Goal:** MVP hard boundary’lerini her PR’da çalışacak testlerle kilit altına al.
- **Scope:** Pytest yapılandırması (markers: contract, replay, failure_injection), marker `pytest.ini`, conftest fixtures, **forbidden-pattern tarayıcı test suite’i**.
- **Forbidden pattern testleri:**
  - (F1) Kod tabanında `requests/httpx/aiohttp/websocket` importunun yalnızca `app/ingest/adapters` veya test fixtures altında olması.
  - (F2) "api_key" / "secret" / "BINANCE_API_KEY" / "OKX_KEY" stringlerinin prod dışı kodlarda yer almaması (dummy test fixture anahtarları hariç fixture path’in doğrulanması).
  - (F3) Short direction (`direction=short`, `side=sell_open_short` benzeri) / leverage>1 kullanımının domain/sözleşme katmanında yokluğu.
  - (F4) Gerçek emir yolu fonksiyon isimlerinin (`send_real_order`, `place_order_on_exchange`) v1’de **var olmaması** (tüm isimler paper/simulate önekli olmak zorunda).
- **Dependencies:** S-FND-01, S-FND-02
- **AC:**
  - Given temiz kod, When yukarıdaki 4 F testi çalıştırılır, Then hiçbirinde FAIL olmaz (bu hikâye DoD).
- **Contract refs:** SPEC Constraints (PRD hard boundaries)
- **AD refs:** AD-1 (modular boundaries), AD-12 (paper/live ayrım), AD-18, AD-20
- **ADN:** Yok
- **Test reqs:** contract testleri (F1..F4) + markerların doğrulanması
- **DoD:** Forbidden-pattern testleri PASS, pytest çalışıp markerları listeliyor.

---

## Epic 2 — E-CON: Canonical Contracts & Schema Enforcement

### Epic Goal
CONTRACTS.md/LIFECYCLE.md sözleşmelerini typed model olarak kodla; CAP-1/2/3/4/5/6’nın temelini oluşturacak schema validasyonunu ekle.

### Scope
- 19 event/entity sözleşmesi + envelope + quality flags
- StrategyContext + LimitsSnapshot + nested tipler
- Forbidden-pattern sözleşme testleri (CAP-1/3/4/5/6)
- contract_version 1.0.0 zorunluluğu

### Out of Scope
- Fixture üretme (E-RDH)
- Event bus dispatch (E-PLN)

### Stories
#### Story S-CON-01: CanonicalEventEnvelope + QualityFlags Typed Schemas
- **Goal:** CONTRACTS.md §1/§2’ye göre zarf ve kalite sözleşmesini doğrulayan typed schema oluştur.
- **Scope:** Pydantic v2 (veya uyumlu typed schema) ile tüm envelope alanlarını, Zorunlu/Kural tanımlarını ve QualityFlags bayraklarını içeren sınıflar.
- **Dependencies:** S-FND-03
- **AC:**
  - Given eksik `correlation_id`, When envelope validate edilir, Then validation HATA verir.
  - Given `quality_flags.degraded = true`, Then en az 1 bayrak (stale/missing/duplicate/out-of-order/invalid/quarantined) true olmalıdır (invariant).
  - Given `timestamp` yerel saat dilimi, When validate, Then UTC Z eki zorunlu olduğu için HATA verir.
- **Contract refs:** CONTRACTS §1, §2
- **AD refs:** AD-3, AD-5, AD-17
- **ADN:** Yok (eşikler ADN ama yapı zorunlu)
- **Test reqs:** Pozitif/negatif schema unit testleri, kalite invariantı.
- **DoD:** Tüm contract scheması unit testlerden geçiyor.

#### Story S-CON-02: Market / Decision / Portfolio Entity Schemas (19 Sözleşme)
- **Goal:** CONTRACTS §3 sözleşmelerini typed schema olarak ekle; Decimal vs float alanları, enums, required alanları kilitle.
- **Scope:** MarketTick, TradeEvent, OrderBookSnapshot/Update, Candle, MarketRegime, FeatureVector (AD-22 düz sözlük), StrategyContext, StrategySignal, OpportunityScore, RiskDecision, PaperOrder, PaperFill, Position, PortfolioSnapshot, ModelVersion, ModelEvaluation, LifecycleTransitionPayload, ChampionChallengerEvaluationPayload.
- **Dependencies:** S-CON-01
- **AC:**
  - Given FeatureVector flat olmayan nested sözlük, Then schema HATA verir (AD-22).
  - Given RiskDecision decision=approved + correlation_id X, PaperOrder create edildiğinde aynı correlation + policy_refs.risk_decision_id ZORUNLUDUR (CAP-4 kuralının schema seviyesinde şekli).
  - Given ModelVersion status=Champion + status=Retired simultaneously (test), Then tek status zorunluluğu.
- **Contract refs:** CONTRACTS §3, §3.11 LimitsSnapshot, AD-22, CAP-3/4
- **AD refs:** AD-3, AD-22, AD-14 (status 6 değer enum), AD-25 (StrategyContext), AD-11
- **ADN:** ADN-05 (model family enum), ADN-07 (fill model fields required=false), ADN-06 (score default weights yok).
- **Test reqs:** Her sözleşme için 2+ negatif, 3+ pozitif unit test; FeatureVector flat sözlük + StrategyContext shape zorunluluğu (CAP-3 ön hazırlık).
- **DoD:** Tüm 19 + nested schemalar doğrulama testlerini geçiyor; CAP-3/4/5 için temel zorlamalar mevcut.

#### Story S-CON-03: Contract-Based Parity Test Infrastructure (CAP-1 Setup)
- **Goal:** CAP-1’i kanıtlayacak test scaffold kur: Feature/Regime/Strategy/Risk/Portfolio dosyalarında `if run_mode == ...` veya `source_type` bazlı domain dallanması varsa FAIL eden static/code-analysis tarayıcı + runtime test fixture.
- **Scope:** Pytest contract markered test: modül ağacı regex scan (5 modül: processing/features, decisioning/regime, decisioning/strategy, decisioning/risk, simulation/portfolio) + runtime run_mode parametreli fixture.
- **Dependencies:** S-FND-03, S-CON-02
- **AC:**
  - Given domain kod boş, When parity test tarayıcı çalışır, Then 0 forbidden branch.
  - Given 5 modülden birinde `if run_mode`, Then test FAIL olur ve dosya: satır çıktısı verir.
- **Contract refs:** CONTRACTS §5 (Live/Replay Parity), CAP-1
- **AD refs:** AD-4, AD-20
- **ADN:** Yok
- **Test reqs:** contract marker’lı static scan test
- **DoD:** Tarayıcı test çalışır; 0 finding (boş başlangıçta).

#### Story S-CON-04: MVP API / Lifecycle Contract Schemas + CAP-6 Gate Tests (Initial)
- **Goal:** API.md yüzeyi (okuma grubu + 2 yazma) request/response zarflarını ve LIFECYCLE geçiş grafiğini schema olarak kilitle; CAP-5/CAP-6 hazirlik.
- **Scope:** API response envelope schema (`{ok, data, error, correlation_id}`), 2 write endpoint request body schemas (emergency_stop, kill_switch), LIFECYCLE.md forbidden transition listesi + allowed tablosu.
- **Dependencies:** S-CON-02
- **AC:**
  - Given /execution/live path route tanımı, When MVP api route list validate edilir, Then FAIL (CAP-6 kuralı).
  - Given Candidate→Champion geçiş isteği, When lifecycle transition validator çalışır, Then HATA (LIFECYCLE.md forbidden list).
- **Contract refs:** API.md §1-10 + Yasaklı API yolları; LIFECYCLE.md İzin Verilmeyen Geçişler
- **AD refs:** AD-14/23, AD-16 (API control/query plane), AD-12 (future live boundary)
- **ADN:** ADN-11/12 (canlı owner, coğrafya)
- **Test reqs:** Forbidden routes static scan (CAP-6 initial); lifecycle transition matrix tests (CAP-5 initial)
- **DoD:** Route & transition validator şemaları mevcut, basic PASS.

---

## Epic 3 — E-RDH: Replay Data & Adapter Abstraction (İLK UYGULANABİLİR HİKÂYEYİ İÇERİR)

### Epic Goal
AD-2 (adapter boundary) + FR-003 (replay-first) ilkesine göre, gerçek borsa/API key olmadan test fixture’larıyla çalışan ilk Replay Adapter + Normalizer + Validation + QualityFlags pipeline’ını kur; CAP-1/2 ilk kanıtını ver.

### Scope
- ExchangeAdapter soyut port (public-only, credentials YOK), ReplayBundleAdapter (fixture csv/parquet okuyan)
- Normalizer: exchange-native frames → canonical event env
- Data Quality Monitor / Validation (9 kontol AD-5) → kalite bayrakları → quarantine akışı
- Replay Clock & source_type=replay set’lenmesi

### Out of Scope
- Canlı WS (E-RDH için KESİNLİKLE YOK)
- Persist (DB) (E-PLN)
- Tüm ADN-01/02/07 sayısalları (sabit defaults ile çalış, testte override et)

---

### **ÖNCELİK 1 — İLK UYGULANABİLİR HİKÂYE — S-RDH-01**
#### Story S-RDH-01: Replay Data Adapter + Normalizer + Validation + CanonicalEvent + In-Memory EventBus POC
- **Goal:** Kullanıcının istediği **omurga POC** hikâyesi: gerçek borsa, API key, gerçek emir, gerçek para OLMADAN; sadece test fixture/veriyle çalışan, veri → zarf → kalite → bus akışını çalıştırır. **MVP uygulama sırasındaki İLK gerçeğe dönük hikâyedir.**
- **Context:** Epic 1, 2 ve Epic 4 minimal (in-mem bus) hikâyeleri tamamlandıktan sonra bu hikâye bağımlı olduğu parçalarla birlikte "teknik omurga"yı kanıtlar.
- **Scope:**
  - Soyut `PublicExchangeAdapter` port (connect, disconnect, subscribe, get_candles, stream_events — sadece public, auth yok).
  - `ReplayBundleAdapter` (CSV/JSON fixture okur; event sırasını replay_clock ile emit eder).
  - Normalizer: exchange-native symbol (örn BTCUSDT) → canonical BTC_USDT; ts UTC yap; envelope doldur.
  - Validation: AD-5 9 kontrol (timestamp, sequence, duplicate, missing, stale, out-of-order, invalid price, invalid volume, abnormal spread). Kalite bayraklarını set eder, `invalid/quarantined/degraded` olayları quarantine’e ayırır.
  - In-memory typed event bus (S-PLN-01 varsayar, E-PLN bitmeden önce bu hikâyede minimal impl ile kanıtlanabilir, sonrasında E-PLN hikâyeleriyle tamamlanır).
- **Out of Scope:**
  - Canlı borsa bağlantısı, private API, herhangi bir credential
  - Herhangi bir DB yazımı
  - Gerçek emir, paper emir yok
- **Dependencies:** S-FND-03, S-CON-01/02, (S-PLN-01 minimal versiyonu veya hikâye içinde minimal in-mem bus fixture kullanılabilir; sonrasında S-PLN-01 tarafından impl.)
- **Acceptance Criteria:**
  - Given 1 saatlik 1m candle fixture 3 sembol, When Replay adapter çalıştırılır, Then toplam N canonical `candle.v1` event’leri envelope + quality_flags ile yayılır.
  - Given fixture içine bir NEGATIVE price satırı enjekte edildi, When validation çalışır, Then **stale/invalid/quarantined=true** bayrakları set edilir, event normal bus akışına girmez, quarantine listesine alınır (FR-005/AD-5).
  - Given 2 event aynı (trade_id,symbol), When dedup çalışır, Then ikinci duplicate bayraklı + emit edilmez (normalizasyon sonrası bus’a çıkmaz).
  - Given replay source, When her event üretilir, Then envelope `source_type=replay` ve `clock_ref.replay` alanları doludur; `ingest_ts` != `timestamp` (replay clock ayrımı).
- **Contract References:**
  - CONTRACTS §1 Envelope, §2 QualityFlags, §3.5 Candle, §3.1-3.4 MarketTick/Trade/OrderBook (fixture tipine göre)
  - **CAP-1:** live/replay parity kontrolü için ilk fixture — source_type/replay_clock setini doğrular (run_mode branch tarayıcısı zaten S-CON-03 var)
  - **CAP-2:** kalite bayraklarının downstream kullanım için envelope içinde mevcut olduğunu ilk kez kanıtlar
- **Architecture Decision References:** AD-2, AD-3, AD-4, AD-5, AD-11 (kaliteden risk kapısı ileride, burada kalite bayrakları üretimi)
- **Open Decision References:** ADN-01 (Replay provider: test fixtures kullanıyoruz, karar sonradan), ADN-02 (symbol/timeframe/depth: test seti 3 sembol 1m, geçersiz kılınabilir), ADN-03 (stale eşiği: default 5 dakika testte override), ADN-07 (abnormal spread eşiği: testte 5000 bps sabit)
- **Test Requirements:**
  - Unit: her bir kalite kuralı (9 kural) için ayrı negatif test (AD-5 kapsam)
  - Integration: 3 sembol 1000 satır fixture → 9 kontrolden geçen event count, quarantine count, bayrak oranları assert
  - **Contract tests (CAP-1/CAP-2 kanıt):**
    - (CAP-1A) Bütün çıktı eventlerinde `source_type` ve `clock_ref.replay` alanları set (replay modu zorlaması)
    - (CAP-2A) Herhangi bir consumer’ın (örnek test consumer) kalite bayraklarını doğrudan `envelope.quality_flags` alanından okuyabiliyor olması
    - Forbidden: testte adapter dışında exchange spesifik tip (ör. `BinanceKline`) kullanılmaması (S-FND-03 F1 ile de taranır)
- **Definition of Done:**
  1. Tüm AC’ler testler tarafından kanıtlanıyor (coverage: her kalite kuralı en az 1x tetiklenmiş)
  2. API key / credential hiçbir yerde yok (S-FND-03 F2 PASS)
  3. Gerçek borsa çağrısı yok (network çağrısı bulunamıyor)
  4. Gerçek emir yok (paper order even not implemented — out of scope)
  5. Replay determinizm: aynı fixture + aynı seed → aynı sıra + aynı event count

### Epic 3 — Diğer Hikâyeler
#### Story S-RDH-02: Symbol Eligibility Coordinator (AD-21 Single Owner)
- **Goal:** AD-21 uyarınca "sembol uygun mu" aggregate’ini tek owner olarak üreten eligibility coordinator ekle.
- **Scope:** eligibility view (data_quality + scanner inputs), reason aggregation, API (internal) read + event-based reasons.
- **Dependencies:** S-RDH-01
- **AC:** 3 farklı kaynaktan (quality, liquidity, spread) reason toplandığında tek aggregated durum meydana gelir.
- **Contract refs:** CONTRACTS StrategyContext eligibility_ctx (AD-21)
- **AD:** AD-21, AD-5
- **ADN:** ADN-02 (min likidite/spread default)
- **Test reqs:** Unit, Integration with 3 reasons
- **DoD:** Aggregator 3 inputtan tek durum + neden listesi üretir.

#### Story S-RDH-03: Market Scanner (Universe Evaluation)
- **Goal:** FR-008/009/010 uyarınca universe değerlendirmesi + dahil/hariç tutma nedenlerini kaydeden scanner.
- **Scope:** Configurable universe, liquidity/vol/spread/signal input, selection reason logları.
- **Dependencies:** S-RDH-02
- **AC:** 10 sembol universe 5 dahil 5 hariç → her sembol için neden + score kaydedilir (FR-013).
- **Contract refs:** CONTRACTS MarketTick/Candle (inputs)
- **AD:** AD-5 (unhealthy pair hariç), AD-21
- **ADN:** ADN-02 (evren parametreleri defaults + override)
- **Test reqs:** Integration, 20-fixture edge-case.
- **DoD:** Scanner nedenlerle çalışır, output contract mevcut.

---

## Epic 4 — E-PLN: Internal Event Pipeline (Typed Bus + Outbox)

### Epic Goal
AD-6 uyarınca typed in-process event bus, correlation/causation zinciri ve determinizm + replay sırasını garanti altına al.
- Stories: S-PLN-01 (Typed In-Mem Bus), S-PLN-02 (Correlation/Causation Propagation), S-PLN-03 (PG Outbox/Inbox + durability)
- **CAP-1:** replay event ordering deterministiği

---

## Epic 5 — E-FEA: Feature Engineering & Technical Indicators (AD-22 Sıkı Sözleşme)
- Stories: S-FEA-01 (FeatureVersion Schema Registry — AD-22), S-FEA-02 (Sürüm kontrollü temel indikatörler: EMA/RSI/ATR/MACD/VWAP), S-FEA-03 (Deterministic FeatureVector generation + leakage input locks)
- **CAP-1:** Feature modülünde run_mode branch tarayıcısı çalışır, 0 finding
- **CAP-2:** FeatureVector üretiminde degraded input’larda behavior test

---

## Epic 6 — E-REG: Market Regime Detector (6 Rejim)
- Stories: S-REG-01 (6 rejim + confidence kural tabanlı ilk detector), S-REG-02 (Strategy/Risk consumption patterns + TransitionUncertain safety)
- **AD:** AD-8, FR-016

---

## Epic 7 — E-STR: Strategy Engine & MVP Strategies (Trend/Momentum)
- Stories: S-STR-01 (StrategyPlugin interface + registry), S-STR-02 (Trend Following + Momentum MVP), **S-STR-03 (Strategy Purity Tests — CAP-3 Forbidden Import Scan)**
- **CAP-3 directly:** Forbidden imports + StrategyContext type & nullability contract testleri

---

## Epic 8 — E-AIS: Opportunity Scoring & Baseline AI
- Stories: S-AIS-01 (Composite Scoring Policy - FR-020), S-AIS-02 (Baseline ML model (ADN-05 default baseline: LogReg / benzeri)), S-AIS-03 (Explainability (feature importance) + probability outputs)
- **AD:** AD-10 (AI execution authority yok)

---

## Epic 9 — E-RSK: Independent Risk Engine & Kill Switch
- Stories: S-RSK-01 (Limits + Regime-aware policies FR-053), S-RSK-02 (**RiskDecision.approved → PaperOrder gate — CAP-4 direct proof**), S-RSK-03 (Position Sizing Methods), S-RSK-04 (Stale data + Kill Switch + Emergency Stop downstream)
- **CAP-4: S-RSK-02 has dedicated contract test:** without approved RiskDecision (same corr) → PaperOrder reject
- **CAP-2: S-RSK-04 uses only envelope.quality_flags (no validator RPC)**

---

## Epic 10 — E-BKT: Replay-Driven Backtest Engine
- Stories: S-BKT-01 (Run orchestrator + PortfolioSimulator çağrısı — AD-24, no direct write), S-BKT-02 (Fee/slippage/latency/spread model injection), S-BKT-03 (Leakage/Look-Ahead hard assertions (AD-16) + performance metrics)
- **AD:** AD-13, AD-24

---

## Epic 11 — E-PTR: Paper Trading Execution Simulator
- Stories: S-PTR-01 (Execution Simulator + Order state machine), S-PTR-02 (Fill Model: spread/slippage/latency/partial — defaults + override)
- **AD:** AD-12 (no real orders), AD-11 (risk gate)

---

## Epic 12 — E-PTF: Portfolio Simulator & Performance (Single Writer)
- Stories: S-PTF-01 (Portfolio state tek yazar — PaperOrder/Fill/Position/PortfolioSnapshot — AD-7/13/24), S-PTF-02 (PnL/equity/drawdown/fees calculations), S-PTF-03 (Performance metrics FR-059 gross/net + strategy/model/regime breakout)
- **AD:** AD-7, AD-13, AD-24

---

## Epic 13 — E-MDL: Model Lifecycle / Registry & Champion-Challenger
- Stories: S-MDL-01 (ModelVersion CRUD + evidence refs), S-MDL-02 (ModelEvaluation & comparison), S-MDL-03 (Promotion Gate + approval policy), **S-MDL-04 (Rollback), S-MDL-05 (**CAP-5 proof — lifecycle forbidden transition test & direct DB UPDATE FAIL)**
- **AD:** AD-14/23, LIFECYCLE.md tüm kurallar

---

## Epic 14 — E-API: MVP API Surface & Observability
- Stories: S-API-01 (FastAPI routes 10 okuma grubu), S-API-02 (2 permissioned writes: /system/emergency-stop + /risk/kill-switch with audit), **S-API-03 (CAP-6 Forbidden Route Scan)**), S-API-04 (Prometheus metrikleri + alert kuralları ilk seti)
- **CAP-6:** S-API-03 test: /execution, /keys, /funding route’ları yok — fail
- **AD:** AD-16, AD-17

---

## Appendix A: CAP Coverage Summary (Hikâyelerle)

| Contract Proof | İlk Hikâye (kanıt)       | Sonraki Hikâyeler (pekiştirme)           |
| -------------- | ------------------------ | ---------------------------------------- |
| CAP-1 (Parity) | S-RDH-01, S-CON-03       | S-FEA-03, S-REG-02, S-STR-03, S-RSK-04   |
| CAP-2 (Quality in Envelope) | S-RDH-01         | S-RSK-04, S-API-04 (quality metrics)     |
| CAP-3 (Strategy Purity) | S-CON-02 setup    | **S-STR-03 (ANA test)**                  |
| CAP-4 (RiskGate + PaperOrder) | S-RSK-02 setup | **S-RSK-02 (ANA test)**, S-PTR-01        |
| CAP-5 (Lifecycle only-Registry) | S-CON-04 setup | **S-MDL-05 (ANA test)** + S-MDL-03/04    |
| CAP-6 (MVP API No Live Routes) | S-CON-04 setup | **S-API-03 (ANA test)**                  |

## Appendix B: MVP Implementation Sequence (İlk 10 Hikâye Sırası)

1. **S-FND-01** → Skeleton & env separation
2. **S-FND-02** → Logger/metrics hooks
3. **S-FND-03** → Pytest + hard-boundary forbidden tests (can’t trade, keys, short, lev)
4. **S-CON-01** → Envelope + QualityFlags schema
5. **S-CON-02** → 19 Entity schemas + StrategyContext/Limits
6. **S-CON-03** → Parity test scaffold (branch tarayıcı)
7. **S-CON-04** → API/Lifecycle forbidden schemas
8. **S-PLN-01** → In-memory typed event bus (determinist)
9. **(FIRST USER POC)** → **S-RDH-01 (İLK UYGULANAN HİKÂYE)**: Replay/Normalizer/Validation/EventBus POC, fixture-only, no real deps
10. **S-RDH-02** → Eligibility coordinator (single owner)
11. Sonrası: Epic 3/4/5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14

## Appendix C: ADN Dependency Map (Hikâye başına kritik ADN)

| ADN ID   | Hikâyelerde kritik bağımlılık (varsayılan + override test) |
| -------- | ---------------------------------------------------------- |
| ADN-01   | S-RDH-01/03 (test fixtures kullanılır, sonra real provider) |
| ADN-02   | S-RDH-03, S-FEA (defaults 3 sym/1m/200 candle, test değiştirir) |
| ADN-03   | S-RDH-01 (stale threshold default), S-API-04 (SLO sonra)   |
| ADN-04   | S-STR-02 (Trend/Momentum parametreleri defaults + search)  |
| ADN-05   | S-AIS-02 (baseline LogReg, model family sonradan)           |
| ADN-06   | S-RSK-01/03 (risk limit defaults + score weights defaults)  |
| ADN-07   | S-PTR-02, S-BKT-02 (fill model defaults + kalibrasyon)      |
| ADN-08   | S-MDL-03 (promote eşiği: min örnek + policy: "ilk aşamada insan onayı şart" olarak kilit) |
| ADN-09   | S-RSK-04, S-API-02 (kill/emergency davranış: "yeni emir yok, mevcut pozisyonları kapatma" default) |
| ADN-10   | S-MDL-01 (artifact_uri: local fs klasörü default)          |
| ADN-11   | S-API-02 (canlı onay katmanı: kapalı)                       |
| ADN-12   | S-API-01 (UI auth/cog: kapalı MVP)                          |

## Appendix D: Hard Boundary DoD (Tüm Hikâyeler İçin Genel)
Herhangi bir hikâye için DoD’da aşağıdaki 6 madde **ZORUNLUDUR**:
1. No gerçek borsa çağrısı (network, credentials) — S-FND-03 F1/F2 PASS
2. No real order / paper dışında emir yolu — F4 PASS
3. No short / leverage>1 (domain kod + schemas) — F3 + schemas PASS
4. No API key / secret / gerçek para — F2 PASS
5. AD-1..25 ihlali yok
6. İlgili CAP testleri (o hikâyenin sorumlu olduğu) PASS — coverage raporu varsa.
