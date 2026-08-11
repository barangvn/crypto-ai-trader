---
story_id: S-RDH-01
title: "Replay Data Adapter + Normalizer + Validation + CanonicalEventEnvelope + In-Memory Typed EventBus POC"
story_key: "3-1-replay-data-pipeline-poc"
epic: E-RDH (Replay Data & Adapter Abstraction)
status: ready-for-dev
created: 2026-08-10
updated: 2026-08-10
sources:
  - ../../planning-artifacts/briefs/brief-crypto-ai-trader-2026-08-04/brief.md
  - ../../planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md
  - ../../planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/SPEC.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/CONTRACTS.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/LIFECYCLE.md
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md
  - ../epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md
  - ../INDEX.md
contract_version: "1.0.0"
---

# Story S-RDH-01 — Replay Data Pipeline POC

## 1. Story ID
`S-RDH-01` (Epic E-RDH, Story #1)

## 2. Title
**Replay Data Adapter + Normalizer + Validation + CanonicalEventEnvelope + In-Memory Typed EventBus POC**

## 3. Goal
MVP’nin veri omurgasını, **gerçek exchange / API key / network / gerçek emir / gerçek para olmadan**, salt yerel deterministic replay/test fixture verisi üzerinden kanıtlamak. Akış uçtan uca çalışmalı:
`Replay Fixture → ReplayBundleAdapter → Normalizer → Validator → CanonicalEventEnvelope → In-Memory EventBus → Test Consumer`.
Hedef: (a) CAP-1 (Live/Replay Parity) ve (b) CAP-2 (Quality Flags end-to-end taşınımı) başarı kriterlerini bu hikâye içinde ilk kez contract testleriyle doğrulamak.

## 4. Context
MVP, AD-1 (Modular Monolith) ve AD-4 (Live/Replay Parity) çerçevesinde, replay verisini birinci sınıf veri kaynağı olarak (FR-003) konumlandırır. İlk hikâye olarak bu hikâye, *bağımlı olmadığı* hiçbir canlı dış hizmet kullanmadan; sadece yerel test fixtures ile pipeline’ın (a) sözleşmeye uyumunu, (b) kalite kapısı davranışını, (c) replay determinizmini ve (d) event bus teslimatını kanıtlar. Kullanıcının mimari vizyonuyla doğrudan örtüşür: ilk çalışan dikey dilim, veri omurgası POC’sidir.

**Kesin Sınırlar (Değiştirilemez):**
- Canlı exchange bağlantısı: **YOK**
- API key / credential: **YOK**
- HTTP / WebSocket / exchange SDK çağrısı: **YOK**
- Gerçek order / paper order: **YOK**
- Gerçek para / bakiye / pozisyon: **YOK**
- AI / ML / Strategy / Regime / Risk / Backtest / Portfolio / FastAPI / React / PostgreSQL: **YOK** — bu hikâyenin kapsamı dışındadır.

## 5. Scope
- Soyut `PublicExchangeAdapter` port’unun (sadece public metotlar, auth alanları YOK) Python interface/Protocol tanımı
- `ReplayBundleAdapter` concrete impl: yerel CSV/JSON fixture paketinden event okuyan, adapter interface’ini uygulayan concrete adapter
- `Normalizer`:
  - Provider-specific raw semboller → canonical `BASE_QUOTE` (ör. `BTCUSDT` → `BTC_USDT`)
  - Raw timestamp → UTC ISO-8601 + 3 haneli ms + `Z` eki (Instant)
  - Monetary değerler → `Decimal` (18 haneli ondalık)
  - `candle.v1`, `market_tick.v1`, `trade_event.v1`, `order_book_snapshot.v1` tiplerinden istenilenini canonical payload alanlarıyla üretme
- `Validator / DataQualityMonitor` (AD-5 9 kontrol):
  - `timestamp` (future drift, zero/null, çok eski drift)
  - `sequence` boşluk/tekrar/geri (sıra, varsa)
  - `duplicate` event (deduplication key = source, event_type, (trade_id veya candle.open_time+symbol))
  - `missing` (candle completeness / tick completeness gap)
  - `stale` (ingest_ts - timestamp > threshold, default 5dk, override edilebilir)
  - `out_of_order` (ts veya sequence azalırsa)
  - `invalid_price` (<=0, NaN, tick size ihlali, negatif)
  - `invalid_volume` (<=0, NaN, lot/step kuralı)
  - `abnormal_spread` (spread_bps > threshold, default 5000 bps, test-only)
- `CanonicalEventEnvelope` üretimi: CONTRACTS.md §1 zorunlu 15 alan (event_id, event_type, contract_version, symbol, source, timestamp, ingest_ts, correlation_id, causation_id, run_mode, source_type, clock_ref, quality_flags, schema_ref) + trace_id/extra (opsiyonel)
- `QualityFlags` üretimi ve fail-safe davranış (CONTRACTS.md §2):
  - Tüm 7 bayrak (stale, missing, duplicate, out_of_order, invalid, quarantined, degraded)
  - `degraded` = yukarıdakilerden biri `true` ise otomatik `true`
  - Bozuk / quarantined event’ler **canonical akışa sokulmaz, sadece quarantine collection/list’te tutulur, EventBus publish edilmez**
- `In-Memory Typed EventBus`:
  - `publish(envelope)` — sync/async (Python için asyncio tercih, ama sync minimal de OK)
  - `subscribe(event_type|*, callback)` — typed handler, event_type filtreli
  - Zorunlu davranış: her publish → correlation_id + causation_id korunur (ilk event’te causation_id == event_id)
  - Deterministic sıra: same fixture iki kez aynı publish sırası (FIFO)
- `Replay Clock`:
  - `source_type=replay` → `clock_ref.replay = event.timestamp`; `clock_ref.wall = actual wall-clock (ingest_ts)`
  - Domain kodu (ileride feature/regime/strategy/risk/portfolio) için zaman kaynağı: `clock_ref.replay ?? clock_ref.wall` (şu anki hikâyede doğrudan test consumer tarafından kontrol edilir)
- Deterministic test fixtures:
  - 3 sembol: `BTC_USDT`, `ETH_USDT`, `SOL_USDT` (ADN-02 — yalnızca fixture/test, production kuralı değil)
  - Timeframe: `1m` (ADN-02 — yalnızca fixture/test)
  - 1 saatlik 60 adet 1m candle fixture her sembol için (toplam 180 satır)
  - Edge case fixtures: stale event, duplicate event, missing satır, out-of-order satır, negatif fiyat, negatif hacim, 0 fiyat, anormal spread içeren satırlar

## 6. Out of Scope
- CANLI BÖLÜMLER: WebSocket Manager, live exchange adapter, REST historical API çağrısı — YOK
- DOĞRULAMA SONRASI MODÜLLER: Feature Engineering (E-FEA), Regime Detector (E-REG), Strategy Engine (E-STR), AI/Scoring (E-AIS), Risk Engine (E-RSK), Backtest Engine (E-BKT), Paper Trading (E-PTR), Portfolio Simulator (E-PTF), Model Registry (E-MDL), Dashboard/API (E-API) — BU HİKÂYEDE YOK
- KALICILIK: PostgreSQL, TimescaleDB, Object Storage, outbox/inbox tabloları (E-PLN sonrası) — YOK
- YAPAY ZEKA: ML model eğitimi, inference, açıklanabilirlik — YOK
- GERÇEK EMİR: Execution Simulator, Fill Model, Order state machine — YOK
- KULLANICI ARAYÜZÜ: FastAPI, React, Vite, Grafana UI — YOK
- SAKLAMA / API KEY: Herhangi bir credential üretme, saklama veya kullanma — YOK

## 7. Dependencies
**Öncül Hikâyeler (kod olarak mevcut olması gerekmez; fixture/contract tanımları bu hikâyede de oluşturulabilir; fakat ideal sıra EPICS.md Appendix B):**
- Önkoşul hikâyeleri (S-FND-01, S-FND-02, S-FND-03, S-CON-01, S-CON-02, S-PLN-01 minimal) — bunlar mevcut değilse, S-RDH-01 içinde minimal contract ve bus fixture olarak oluşturulabilir, ancak sonrasında ilgili hikâyelerle birleştirilmek üzere işaretlenir.
- Sadece yazılım bağımlılığı: Python 3.14+ (ad-16 stack), `pytest 9.1.1` (AD stack); *external pip dependency minimumdur (pydantic v2 opsiyonel, typed dict veya dataclass da yetişir)*.

**External Dependency: YOK** (network YOK, internet YOK, exchange SDK YOK, DB YOK). Tamamen offline.

## 8. Technical Approach
1. **Contract-First (AD-3):** İlk adım `CanonicalEventEnvelope` + `QualityFlags` + 5 market event (tick/trade/snapshot/update/candle) payload tiplerini CONTRACTS.md §1, §2, §3.1-3.5 uyarınca typed olarak koda dök (Pydantic v2 veya attrs veya dataclass + validatörler; dil: Python).
2. **Hexagonal Adapter (AD-2):** `PublicExchangeAdapter` soyut interface: `stream_market_events(fixture_ref) -> Iterable[RawFrame]`. RawFrame provider-specific tip; hiçbir alan domain koduna sızmaz, sadece Normalizer tarafından görülür.
3. **Pipeline Fonksiyonel Zincir:** `Adapter.frames() → Normalizer.normalize_many() → Validator.validate_many() → [ canonical_events[], quarantined_events[] ] → EventBus.publish_many(canonical_events)`. Burada Validator, her frame için `quality_flags` + hangi sonucu (publish/quarantine/atla) üretir.
4. **In-Memory Bus (AD-6 Minimal):** `TypedEventBus = { subscriptions: dict[event_type, list[cb]], published: list[Envelope] }`. Deterministik FIFO; her publish en son `published` listesine append; subscribe callback çağrılır.
5. **Determinizm Garantisi (NFR-007):** Bütün `ULID`/`UUID` üretimi, fixture okuma sırası, event timestamp ve adapter stream sırası — hepsi sıralı/tekrarlanabilir; random kullanılıyorsa seed dışarıdan enjekte edilir (testte sabit).
6. **Network Safety Enforcment:** `conftest.py` fixture seviyesinde `socket` / `urllib` / `requests` / `httpx` / `websocket` modüllerini monkeypatch ederek herhangi bir outbound çağrıda Exception fırlatır (test network kullandığını kesin olarak ispatlar). Aynı zamanda S-FND-03 F1/F2 testleri bu hikâye testlerinin bir parçası olarak çalışır.
7. **CAP-1 Direct Assert:** (a) Tüm event’lerde `source_type=replay` ve `clock_ref.replay` doludur. (b) Herhangi bir domain/helper dosyasında `if run_mode` / `if source_type` araması AST veya regex taraması ile FAIL olur (0 branch).
8. **CAP-2 Direct Assert:** (a) Her event, EventBus publish edilen zarfın `quality_flags` alanında 7 bayrağın hepsini taşır. (b) Test Consumer, Validator’u import etmeden, yalnızca `envelope.quality_flags.stale` vb okuyarak stale kararını verebilir (tekrar RPC yok).

## 9. Files/Modules Expected to Be Created
```
app/
  contracts/
    __init__.py                     # contract_version sabiti, import tek noktası
    canonical.py                    # CanonicalEventEnvelope, QualityFlags (Typed)
    market.py                       # MarketTick, TradeEvent, OrderBookSnapshot, OrderBookUpdate, Candle payload schemas
    types.py                        # ULID, Instant, Symbol, Decimal alias, RunMode, SourceType, ContractVersion enums
  ingest/
    __init__.py
    adapters/
      __init__.py
      base.py                       # PublicExchangeAdapter Protocol / ABC
      replay_bundle_adapter.py      # ReplayBundleAdapter (fixture CSV/JSON okur)
  processing/
    __init__.py
    normalizer.py                   # normalize(frame) → Envelope[payload] + dedup_key helper
    quality_monitor.py              # Validator; validate(envelope) → (modified_envelope, is_quarantined, reasons)
    replay_clock.py                 # set_clock_ref_for_replay(envelope) yardımcısı
  platform/
    event_bus.py                    # InMemoryTypedEventBus (publish, subscribe, published list)
tests/
  conftest.py                       # fixtures: offline_network_blocker, small_fixture, edge_case_fixtures, bus_fixture
  unit/
    contracts/
      test_envelope.py              # Zorunlu alanlar, UTC Z format, correlation/causation zorunluluğu
      test_quality_flags.py         # 7 bayrak invariantları; degraded → en az 1 bayrak true
      test_market_payloads.py       # 5 payload şema testleri, Decimal zorunluluğu
    ingest/
      test_replay_bundle_adapter.py # Fixture'den doğru frame sayısı + sırasını doğrula
    processing/
      test_normalizer.py            # Sembol normalizasyonu, timestamp UTC Z, Decimal dönüşümü
      test_validator_9checks.py     # 9 AD-5 kuralı için 9 ayrı unit test + reasons
      test_replay_clock.py          # source_type=replay + clock_ref doğru set
    platform/
      test_event_bus.py             # Publish, subscribe typed, sıra koruma, corr/causation
  integration/
    test_pipeline_happy_path.py     # 3 sim. 180 candle -> 180 publish, 0 quarantine, 0 duplicate
    test_pipeline_determinism.py    # Aynı fixture 2 çalıştırma: Aynı event_id, aynı sıra, aynı bayraklar
    test_cap1_live_replay_parity.py # source_type=replay, clock_ref.replay set; 0 run_mode branch (static scan)
    test_cap2_quality_in_envelope.py# 7 kalite durumu için her bayrak taşınımı + consumer bayraktan karar
  failure/
    test_network_safety.py          # HTTP/WS/socket çağrısı yapmaya çalışan kod testte Exception alır (S-FND-03 F1 paralel test)
    test_no_credentials.py         # kodda "api_key"/"secret"/"BINANCE_*" stringleri PASS ile taranır (S-FND-03 F2 paralel test)
  contracts/
    test_srdh01_contracts.py        # Yukarıdaki CAP-1/2 ve şema testlerinin marker=contract ile birleşimi
tests_fixtures/
  small_3sym_1h_1m_candles.csv      # 3 sim, 60 satır/sim, temiz fixture
  edge_stale.csv                    # 5dk+ eski satırlar + 1 gün eski
  edge_duplicate.csv                # Aynı trade_id x2
  edge_missing.csv                  # 30. sırada 2 candle eksik (sıra hatası + missing)
  edge_outoforder.csv               # ts monoton düşen 5 satır
  edge_invalid_price_volume.csv     # negatif fiyat, 0 fiyat, negatif hacim
  edge_abnormal_spread.csv          # spread_bps > 5000 (abnormal)
```

## 10. Acceptance Criteria
### 10.1 Pipeline / Functional AC
- **AC-01:** Temiz `small_3sym_1h_1m_candles.csv` çalıştırıldığında, EventBus.published listesinde **tam olarak 180 adet `candle.v1` tipinde canonical envelope** bulunur; hiçbiri `quarantined=true` değildir (happy path).
- **AC-02:** S-RDH-01 pipeline, her output envelope’ında CONTRACTS.md §1 zorunlu alanlarının **hiçbirini null/boş bırakmaz**: event_id, event_type, contract_version(=1.0.0), symbol, source, timestamp, ingest_ts, correlation_id, causation_id, run_mode(=paper/backtest), source_type(=replay), clock_ref, quality_flags, schema_ref.
- **AC-03:** Sembol normalizasyonu doğru:
  - Raw `BTCUSDT` → canonical `BTC_USDT`; raw `ETHUSDT` → `ETH_USDT`; raw `SOL/USDT` → `SOL_USDT` (hepsi büyük harf).
- **AC-04:** Timestamp normalizasyonu doğru:
  - `2026-08-10 10:00:00` (yerel / ms’siz) → `2026-08-10T10:00:00.000Z`
  - Z dilimi olmayan input → Z eklenir; ms sayısı 3 haneli (000-999).
- **AC-05:** Monetary değerler Decimal ve pozitif temiz fixture’da:
  - Her candle open/high/low/close/volume tipi `decimal.Decimal`’dir; string/float cast ile karşılaştırma başarılır.

### 10.2 Validation (AD-5 9 Check) AC (her biri ayrı test)
- **AC-06 (stale):** `edge_stale.csv` içindeki `stale=true` olarak işaretlenmesi gereken satır sayısı (N) kadar event’te `quality_flags.stale=true`; hepsinde `degraded=true`.
- **AC-07 (missing):** `edge_missing.csv` için Validator, Missing bayrağını true set eder; `quality_flags.reasons[]` içinde `MISSING_CANDLE_GAP` kodu bulunur.
- **AC-08 (duplicate):** Aynı `(symbol, dedup_key)` iki kez geldiğinde, ikinci event `quality_flags.duplicate=true + quarantined=true` olur ve **EventBus publish listesine GİRMEZ**.
- **AC-09 (out_of_order):** 5 satırlık ters sıra fixture’ında son 4 satır `out_of_order=true`; ilk satır normal. Quarantine’e alınanlar publish edilmez.
- **AC-10 (invalid_price):** Negatif fiyat + 0 fiyat içeren satır: `quality_flags.invalid=true + quarantined=true`.
- **AC-11 (invalid_volume):** Negatif hacim ya da 0 hacim (tick required) satır: `quality_flags.invalid=true`; reasons `INVALID_VOLUME`.
- **AC-12 (abnormal_spread):** spread_bps=6000 satırında `quality_flags.invalid=true` veya `degraded=true`, reason code `ABNORMAL_SPREAD`.
- **AC-13 (sequence):** Order book sequence’de 1001,1002,1004,1005 geldiğinde 1003 eksik → `missing=true` reason `SEQUENCE_GAP`.
- **AC-14 (timestamp drift):** Gelecekteki timestamp (2100) → `invalid=true` + `FUTURE_TIMESTAMP_DRIFT`.

### 10.3 EventBus AC
- **AC-15:** `publish()` sonrası, `subscribe("candle.v1", cb)` callback çağrı sayısı = EventBus.published `candle.v1` sayısıdır.
- **AC-16:** İlk event’te `causation_id == event_id`; ikinci ve sonrası ise bir önceki event_id’ye bağlı zincir (veya her event kendisi publish ise causation_id = event_id, parent publish varsa parent’in event_id — bu hikâyede her ikisi de kabul edilir; ama correlation_id aynı fixture boyunca AYNI olmalıdır).
- **AC-17:** İki kez run edilen identical fixture: Aynı sıra, aynı payload (timestamp/sembol/fiyat), aynı kalite bayrakları; publish order %100 aynı (determinizm — NFR-007).

### 10.4 Network / Safety AC
- **AC-18 (Offline Guarantee):** Test çalıştığı süre boyunca, socket/create_connection/HTTP/WS yapacak herhangi bir kod `tests/conftest.py:offline_network_blocker` tarafından engellenir ve çağrı başına Exception fırlatır; bütün testler bu engelle varken PASS’tir (yani aslında hiç çağrı olmaz).
- **AC-19 (No Credentials):** `app/` ve `tests/` klasörleri altında, `"api_key"`, `"secret"`, `"BINANCE_API_KEY"`, `"OKX_KEY"`, `"./keys/"` stringlerinden hiçbirini içeren dosya yoktur (tarayıcı test PASS’tir). Sadece `tests_fixtures/` ve test `conftest.py`’deki dummy ama “api_key” yazmayan test fixture’lerine izin verilir.
- **AC-20 (No Real Orders):** `app/` altında `send_real_order`, `place_exchange_order`, `live_execution` gibi isimde fonksiyon/modül YOKTUR (isim tarayıcı testi PASS’tir). Kağıt simülatörü olmadığı için bu zaten out of scope’dur.

### 10.5 CAP Proof AC (S-RDH-01 İLK KANIT)
- **AC-21 (CAP-1 A):** Tüm published eventler `source_type == "replay"` ve `clock_ref.replay is not None`; ayrıca `clock_ref.replay == envelope.timestamp` (replay clock kuralı).
- **AC-22 (CAP-1 B):** `app/contracts`, `app/processing`, `app/platform`, `app/ingest/adapters/base.py` sınıflandırmasında domain modül (processing/contracts/bus) içinde `"run_mode"` veya `"source_type"` içeren `if` / `elif` koşulları STATİC TARAMA ile 0’dır (0 forbidden branch).
- **AC-23 (CAP-2 A):** Her published envelope, `quality_flags`’in 7 boolean alanının (stale, missing, duplicate, out_of_order, invalid, quarantined, degraded) **tanımlarının hepsine sahiptir** (alanlardan hiçbiri eksik değildir; tip boolean’dir).
- **AC-24 (CAP-2 B):** Bir test consumer (`tests/test_cap2_quality_in_envelope.py::test_consumer_decision_from_flags`) — Validator import etmeden, yalnızca `envelope.quality_flags.stale` alanını okuyarak “stale → işlem yapma” kararını verebilir ve bu karar, Validator’un verdiği kararla aynıdır (RPC yok, flag yeterlidir).

## 11. Contract References (Bağlantılı Sözleşmeler)
| Sözleşme | Kısım | Hangi AC’ler |
|---|---|---|
| CONTRACTS.md §0 Ortak tipler | ULID, Instant, Symbol, Decimal, RunMode, SourceType, ContractVersion | AC-03, AC-04, AC-05 |
| CONTRACTS.md §1 CanonicalEventEnvelope | Bütün Zorunlu Alanlar (15 adet) | AC-02, AC-16, AC-21 |
| CONTRACTS.md §2 QualityFlags + Fail-safe | 7 bayrak, degraded invariant, quarantine davranışı | AC-06..AC-14, AC-23, AC-24 |
| CONTRACTS.md §3.1 MarketTick | price, bid, ask, last_size, spread_bps, market_ts | AC-12 |
| CONTRACTS.md §3.2 TradeEvent | trade_id, side, price, quantity, market_ts | AC-08 dedup |
| CONTRACTS.md §3.3 OrderBookSnapshot | depth_levels, bids/asks, book_ts, sequence_start/end, imbalance_bps | AC-13 sequence |
| CONTRACTS.md §3.4 OrderBookUpdate | bids_delta/asks_delta, book_ts, sequence | AC-13, AC-09 out_of_order |
| CONTRACTS.md §3.5 Candle | timeframe, open_time/close_time, OHLCV Decimal, closed, trade_count | AC-01, AC-04, AC-05, AC-07 |
| CONTRACTS.md §4 Data Flow I/O | Adapter → Normalizer → Validator → Bus | Bütün AC ailesi |
| CONTRACTS.md §5 Live/Replay Parity (CAP-1) | 0 run_mode branch, clock_ref zaman kaynağı | AC-21, AC-22 |
| CONTRACTS.md §6 Kalitenin Taşınımı (CAP-2) | 0 RPC to validator, flag yeter | AC-23, AC-24 |
| SPEC.md Constraints | Timestamp UTC Z, 3 haneli ms; parasal Decimal; corr/caus zorunlu | AC-02, AC-04, AC-05 |
| SPEC.md CAP-1 Başarı Kriteri | 0 run_mode/source_type branch (static scan) | AC-22 |
| SPEC.md CAP-2 Başarı Kriteri | Consumer bayrak ile karar | AC-24 |

## 12. Architecture Decision References
| AD | Uygulama Şekli / Nasıl Korunuyor | Hikâyedeki Testleri |
|---|---|---|
| **AD-1 (MVP Topology: Modular Monolith)** | Tek repo, tek Python process; app/ klasörleri bounded context; microservice YOK (bu hikâyede doğal olarak mikro servisler kurulmuyor, sadece single-process). | `test_network_safety.py` dış servis çağrısı 0 |
| **AD-2 (Exchange Boundary)** | Provider-specific davranış, `ReplayBundleAdapter` arkasında; RawFrame’ler sadece Normalizer içinde; domain sözleşmeleri exchange tip görmez. | `test_normalizer.py::*` outside adapter’dan exchange görülmemesi; `tests_fixtures/` provider isimli ama canonicala çevrilmesi |
| **AD-3 (Canonical Event Envelope)** | Tüm publish edilen event CONTRACTS §1 envelope + 5 payload tipinden biri; schema doğrulamaları unit testte. | AC-02, `test_envelope.py` |
| **AD-4 (Live/Replay Parity) — CAP-1** | Replay, `source_type=replay` + `clock_ref.replay` ile ayrılır; domainde branch YOK. | AC-21, AC-22 (static scan 0 branch) |
| **AD-5 (Data Quality Hard Gate)** | 9 check; hard failure → quarantined, canonical akıştan çıkarma, new paper order engelle (ileride risk, ama şimdilik publish etmeme) — bu hikâyede publish etmeme. | AC-06..AC-14, 9 ayrı unit test |
| **AD-11 (Risk Engine Final Gate)** | Bu hikâyede Risk Engine yoktur; ama kalite bayraklarını envelope içinde taşımak, ileride Risk Engine’in **validator çağırmadan** karar vermesini sağlar (CAP-2 hazırlık). | AC-24, Consumer bayraktan stale engelleme |
| **AD-22 (FeatureVector Typed Versioned Contract)** | Bu hikâyede FeatureVector yoktur, ama hazırlık: 5 market payload şeması (tick/trade/OB/candle) typed/sürüm 1.0.0; FeatureVector sonraki hikâyede AD-22’yi benzer şekilde alır. | `test_market_payloads.py` typed strict şema |
| **AD-25 (StrategyContext Typed, Not Raw Dict)** | Bu hikâyede Strategy yoktur; ama hazırlık: Normalizer/Validator typed pydantic/dataclass kullanır; raw dict yerine typed → downstream S-STR için AD-25 alışkanlığı kazanılır. | Normalizer/EventBus typed schemas |
| *(İlgili diğer)* **AD-6 (Internal Bus First)** | In-Memory Typed Bus, external broker yok, PostgreSQL outbox bu hikâyede yok, sadece in-memory deterministik. | `test_event_bus.py`, Determinism test AC-17 |
| *(İlgili)* **AD-17 (Correlation ID Observability)** | Her event correlation_id + causation_id taşır; Test Consumer tarafından doğrulanır. | AC-02, AC-16 |
| *(İlgili)* **AD-19 (Failure Default Safe)** | Bozuk data → quarantine, publish edilmez; degrade → bus’ta ama bayrak true; güvenli davranış. | AC-06..AC-14 |
| *(İlgili)* **AD-20 (Testability Architectural)** | 9 kalite kuralı 9 unit test + 2 CAP contract test + 2 safety failure test; 20+ test S-RDH-01 bitmeden var. | Tüm test klasörü |

## 13. CAP References (Capability Contract Proofs)
Bu hikâye, SPEC’in 6 CAP’inden **ikisini İLK KEZ** çalışır durumda kanıtlar:
| CAP | Intent | Bu Hikâyede Nasıl Kanıtlanır | Test Dosyası |
|---|---|---|---|
| **CAP-1** | Feature/Regime/Strategy/Risk/Portfolio kodu, live/replay arasında **contract dışında farklılaşmasın**; sadece adapter/clock katmanı farklılaşsın. | (a) Bütün eventler `source_type=replay` + `clock_ref.replay` set (AC-21). (b) `app/processing/ app/contracts/ app/platform/` domain klasörlerinde **0 tane `if run_mode == …` / `if source_type == …` dalı** var (static AST tarayıcı test — AC-22). | `tests/integration/test_cap1_live_replay_parity.py` |
| **CAP-2** | Veri kalitesi sorunları envelope’ın içinde taşınsın; tüketici validator’a **tekrar sormasın** (RPC yok). | (a) 7 bayrak her event’te eksiksiz (AC-23). (b) Test Consumer, Validator import etmeden, yalnızca `envelope.quality_flags.stale` alanını okuyarak “stale → işlem yapma” kararını verebiliyor; bu karar Validator’un kararlarıyla %100 uyuşuyor (AC-24). | `tests/integration/test_cap2_quality_in_envelope.py` |

Diğer CAP-3/4/5/6 daha sonraki hikâyelerde (S-STR-03, S-RSK-02, S-MDL-05, S-API-03) kanıtlanır; bu hikâyede onlar için hazırlık yapılır ama taahhüt edilmez.

## 14. Test Plan
Kategorilere göre **minimum 20 test** (gerçekte 28+). Her kategori, test sayısı + isim + doğruladığı AC:

### Kategori A: Unit Tests (14)
| # | Test | AC |
|---|---|---|
| A1 | envelope alanları zorunlu: eksik correlation → ValidationError | AC-02 |
| A2 | envelope timestamp Z dilimsiz → Z eklenmeli, 3 haneli ms | AC-04 |
| A3 | quality_flags invariantı: degraded true iken diğer 6 bayraktan en az 1 true olmalı | AC-23 |
| A4 | quality_flags 7 alan mevcut + boolean | AC-23 |
| A5 | MarketTick fiyatı Decimal + >0 zorunlu; negatif → invalid | AC-05, AC-10 |
| A6 | TradeEvent quantity Decimal + >0; negatif → invalid | AC-05, AC-11 |
| A7 | OrderBookSnapshot bids/asks Decimal, fiyat artan/azalan sıra | AC-13 |
| A8 | Candle OHLCV Decimal, low ≤ open/high/close ≤ high kuralı | AC-05 |
| A9 | Candle timeframe=1m + closed=true zorunlu fixture | AC-01 |
| A10 | ReplayBundleAdapter 180 satır okur + sıra sabit | AC-01 |
| A11 | Normalizer BTCUSDT → BTC_USDT doğru çeviri | AC-03 |
| A12 | Normalizer timestamp yerel → UTC Z 3 haneli ms doğru | AC-04 |
| A13 | Validator 9 kural için ayrı ayrı unit testler (9 test) — reasons kodları | AC-06..AC-14, 9 ayrı AC |
| A14 | replay_clock.setter: source_type=replay → clock_ref.replay = timestamp | AC-21 |
| *A13 9 kuralı için 9 ayrı test* → Toplam Unit 22 olabilir | |

### Kategori B: Integration Tests (6)
| # | Test | AC |
|---|---|---|
| B1 | Happy path: 3 sim 180 candle → 180 publish, 0 quarantine, 0 duplicate, her bayrak false, degraded false | AC-01 |
| B2 | Determinism: aynı fixture 2 kez çalıştır → published listeler derin eşitlik (sıra + id + payload + bayraklar) | AC-17 |
| B3 | EventBus subscribe: candle tick tipi A ayrı, B ayrı → callback sayıları doğru | AC-15 |
| B4 | Causation zinciri: ilk event causation == event_id; ikinci subs. eventler corr sabit | AC-16 |
| B5 | CAP-1 Static Branch Scan: domain klasörlerinde 0 `if run_mode` / `if source_type` | AC-22 |
| B6 | CAP-2 Consumer Bayrak ile Karar: Stale fixture → test consumer bayrakla reddeder; Validator ile sonuc aynı | AC-24 |

### Kategori C: Contract Marker Tests (5 — marker = `contract`)
| # | Test | AC |
|---|---|---|
| C1 | Tüm published event’ler source_type = replay & clock_ref.replay != null | AC-21 |
| C2 | Tüm published event’ler quality_flags 7 alan mevcut | AC-23 |
| C3 | Tüm semboller BASE_QUOTE form, büyük harf | AC-03 |
| C4 | Tüm timestamp ISO-8601 + Z + 3 haneli ms regex match | AC-04 |
| C5 | Tüm parasal alanlar Decimal türünde (float kontrolü) | AC-05 |

### Kategori D: Failure / Safety Tests (4 — marker = `failure_injection`)
| # | Test | AC |
|---|---|---|
| D1 | offline_network_blocker açıkken, `socket.create_connection()` çağıran kod Exception → testlerimiz aslında çağrı yapmadan PASS | AC-18 |
| D2 | static scan: `app/ tests/` altında api_key / secret / BINANCE_* / OKX_KEY string sayısı = 0 | AC-19 |
| D3 | static scan: `send_real_order`, `place_exchange_order` gibi isimlerde fonksiyon/modül sayısı = 0 | AC-20 |
| D4 | 7 Edge case fixtures (stale, dup, missing, ooo, inv_price, inv_vol, spread) her biri için quarantine count doğru; EventBus’a girmeyenler listede var | AC-06..AC-12 (en az 7 failure) |

### Kategori E: Replay Tests (2)
| # | Test | AC |
|---|---|---|
| E1 | Aynı 180 satırlık fixture 10 kez çalıştır; her birinde publish sayısı = 180 + ilk event_id değeri aynı | AC-17 |
| E2 | 1.000.000 sentetik tick deterministic üret: sıra + bayraklar aynı | AC-17 (opsiyonel, minimumta isteğe bağlı) |

## 15. Definition of Done (DoD)
Tüm maddeler **ZORUNLU**, ayrı ayrı doğrulanır:
1. ✅ Bütün AC (AC-01 → AC-24, 24 kabul kriteri) **%100 PASS**’tir.
2. ✅ **CAP-1 PASS**: (a) Bütün event source_type=replay + clock_ref.replay set, (b) domain klasörlerinde 0 run_mode/source_type branch (static scan 0 finding).
3. ✅ **CAP-2 PASS**: (a) 7 bayrak her envelope’da eksiksiz, (b) test consumer validator RPC’siz bayraktan karar verebilir.
4. ✅ **Replay Deterministic**: Aynı fixture 2 kez çalıştırıldığında %100 aynı publish listesi (sıra + id + payload + bayraklar).
5. ✅ **Canonical Envelope Doğru**: Tüm eventler CONTRACTS.md §1 + §2 + §3.1-3.5 tip/alan kurallarına tam uyum; contract_version=1.0.0.
6. ✅ **Quality Flags Doğru**: 9 AD-5 kuralının 9’u için 9 unit test PASS; her bayrak ayrı ayrı true olma durumu test edildi; quarantined eventler publish listesinde YOK.
7. ✅ **EventBus Çalışıyor**: publish/subscribe/correlation/causation/sıra 4 testi ile doğrulandı (A15-A16, B3-B4).
8. ✅ **Network Kullanılmıyor**: Kategori D D1 PASS’tir ve `tests/conftest.py` blocker aktifken tüm testler çalışıyor (aslında hiç çağrı yok).
9. ✅ **Gerçek Exchange Kullanılmıyor**: D2 tarayıcı testi PASS (0 API key string). Hiçbir modul `requests/httpx/websocket-sdk/binance-python` vb import etmez (D1 ile de engelleniyor).
10. ✅ **Gerçek Emir Yok**: D3 isim taraması PASS (0 gerçek emir fonksiyonu). Paper Execution bu hikâyede OUT OF SCOPE olduğu için doğal olarak YOK.
11. ✅ **Architecture/SPEC Contract İhlali Yok**:
    - AD-1/2/3/4/5/11/22/25 → §12’de her biri için AC ile kanıtlandı.
    - Hiçbir sözleşme ihlali (kontrat uyumsuzluğu, yanlış tip, yanlış sembol) testlerde ortaya çıkmadı.
12. ✅ **Tüm Kategoriler Test Sayısı >= Minimum**: Unit >= 14, Integration >= 6, Contract >= 5, Failure >= 4, Replay >= 2 (TOPLAM >= 31 test). Test coverage (isteğe bağlı ama tavsiye) `app/` klasörü için >= %85.

---

## Developer Notes (Ekstra Uygulama Rehberi)
- İlk adımda `app/contracts/types.py` + `canonical.py` + `market.py` yazmadan pipeline’a başlama; typed schemas olmadan testler sözleşme dayanmaz.
- `ReplayBundleAdapter` implementasyonu için Python built-in `csv.reader` veya `json.load` yeter; pandas/NumPy gibi ağır dependency EKLEME (S-RDH-01 için minimum bağımlılık prensibi, AD-20).
- 9 kalite kontrolünü tek bir `Validator.validate_one(envelope) -> Tuple[ModifiedEnvelope, IsQuarantined, Reasons[]]` fonksiyonunda topla; her kontrol ayrı iç yardımcı fonksiyon.
- EventBus basit tut: asyncio kullanma ihtiyacı yoksa sync dict+callback de OK; FIFO kesin.
- ULID/UUID üretimi için testlerde sabit seed verilebilir; determinizm garantisi için her zaman dışarıdan enjekte edilebilen bir `event_id_factory` kullan.
