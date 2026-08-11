---
scope: Contracts + canonical envelope + data flow I/O + quality flags
status: binding
created: 2026-08-10
updated: 2026-08-10
---

# CONTRACTS — Canonical Event / Entity Sözleşmeleri

Bu dosya: (1) her event/entity’yi saran **CanonicalEventEnvelope** (AD-3), (2) 19 adet sözleşme (MarketTick → ModelEvaluation), (3) kalite bayrakları sözleşmesi, (4) veri akışında her modülün giriş/çıkış contract’larını tanımlar. Tüm sözleşmeler **live/replay parity** (AD-4) ilkesine uygundur.

## 0. Ortak tipler

- `ULID` / `UUID v7` → tercihen ULID; sıralanabilir.
- `Instant` → ISO-8601 UTC (3 haneli ms); ör: `2026-08-10T18:30:00.123Z`. Dilim ZORUNLU UTC olmalıdır (`Z` eki).
- `Symbol` → `{base}_{quote}` canonical formu, büyük harf; örn `BTC_USDT`. Exchange-native sembol → normalizer tarafından (adapter portu arkasında) çevrilir.
- `Decimal` → 18 haneli ondalık; parasal fiyat/hacim/değerler için kullanılır. Float yalnızca: regim confidence, skor olasılıkları, AI feature’ları (AD-22) ve non-monetary agnostik scalar’lar için.
- `RunMode` = enum: `paper` | `backtest` | `live` (v1’de `live` kapalı, SPEC’te sadece kelime olarak yer alır; gerçek yol yok).
- `SourceType` = enum: `live_ws` | `historical_rest` | `replay` | `simulated` | `synthetic`.
- `ContractVersion` = semver; bu SPEC’e göre `1.0.0`.

## 1. Canonical Event Envelope

Her event ya da persist edilen entity **aynı envelope** taşır. Bir downstream tüketici (feature/strategy/risk/portfolio) envelope’yi okuyabilir ve:
- `correlation_id` ile olay zincirini takip eder
- `quality_flags` ile risk kararını verir
- `source_type` ile davranışını değiştirmeden live/replay arasında aynı kodu çalıştırır

### Envelope alanları

| Alan | Tip | Zorunlu | Anlam / Birim / Kural |
| --- | --- | --- | --- |
| `event_id` | `ULID` | E | Her event için benzersiz. |
| `event_type` | `string` | E | Örn: `market_tick.v1`, `paper_fill.v1`. Sabit sözleşme adı + semver major. |
| `contract_version` | `ContractVersion` | E | Bu dosyanın sürümü; başlangıç `1.0.0`. |
| `symbol` | `Symbol \| null` | K | Olay sembol bazlıysa zorunlu (tickers/orderbook vs); sistem event’lerinde null. |
| `source` | `string` | E | Veri/karar kaynağı; örn: `binance.spot.public`, `replay.binance_spot_2026q2`, `engine.risk`, `engine.strategy.trend_following`. |
| `timestamp` | `Instant` | E | Event’in üretildiği an (normalizer/üretici saati). |
| `ingest_ts` | `Instant` | E | Sistemin event’i ilk kabul ettiği an; replay’da `timestamp == ingest_ts` OLMAZ, ingest_ts gerçek işletim saati; market event’in kendisi `timestamp` üzerinden işlenir. |
| `correlation_id` | `ULID` | E | Tüm zincir boyunca sabit tutulur. İlk adapter/replay girişinde üretilir; her downstream üretimde korunur. |
| `causation_id` | `ULID` | E | Bu event’i doğrudan tetikleyen event’in `event_id`. Zincirin ilk halkasında `causation_id == event_id`. |
| `run_mode` | `RunMode` | E | `paper` / `backtest` / `live` (v1 live yol yok). |
| `source_type` | `SourceType` | E | `replay` ise, tüketiciler `replay_clock`u kullanır (AD-4). |
| `clock_ref` | `{ wall: Instant; replay: Instant \| null }` | E | `replay_clock` sadece `source_type=replay` iken doludur. Market/rejim/zaman karşılaştırmalarında **strategi/feature/risk/portfolio kodu `clock_ref.replay ?? clock_ref.wall` kullanmalıdır**, doğrudan sistem saatini okumamalıdır. |
| `quality_flags` | `QualityFlags` | E | Aşağıda tanımlandı (§2). |
| `schema_ref` | `{ contracts_md: "CONTRACTS.md@1.0.0"; feature_version?: string; strategy_version?: string; model_id?: string }` | E | Hangi contract/feature/strategy/model sürümüyle üretildiğini bağlar. |
| `trace_id` | `string \| null` | K | OpenTelemetry trace. |
| `extra` | `object` | K | Backward uyumlu serbest alan; sözleşmeyi kıracak alanlar buraya konulmamalı; yeni alanlar için contract_version yükselt. |

## 2. QualityFlags Sözleşmesi (AD-5 + CAP-2)

Tür: `object`, tüm alanlar **boolean + opsiyonel `reasons[]`**; `false` = sorun yok. Açıklama: her bayrak bir sorun sınıfını işaretler. Validator tarafından doldurulur ve downstream hiçbir modül validator’u çağırmadan bu bayraklara göre davranır.

| Bayrak | Ne zaman `true` | Otomatik tepki (downstream davranış, varsayılan) |
| --- | --- | --- |
| `stale` | `now_ingest - event.timestamp > stale_threshold` (threshold ADN’de) | Risk: yeni long pozisyon açılmasını engeller; varolanları izlemeye alır; alert. |
| `missing` | Sıra numarası/aralık beklenen candlestick ya da tick’ten eksik kanıtı var | Normalizer: `missing_refs[]` doldur; Regime/Strategy: çıktı üretmeyi atla (degrade); Risk: alert |
| `duplicate` | Aynı `(source, event_type, deduplication_key)` görüldü | Atla (emit edilmez, ya da `duplicate=true` ile quarantinlenir; normal akışa sokulmaz) |
| `out_of_order` | `timestamp` veya sequence azaldığı (önceki event’ten eski) | Atla ya da sequence buffer ile düzeltilemezse `quarantined=true` atanıp özel akışa |
| `invalid` | Tip, aralık, spread anormalliği, negatif fiyat/hacim vb. kurallardan geçemedi | `quarantined=true`; strateji durdur; yeni paper order block |
| `quarantined` | Veri, geçerli olmayan ya da şüpheli olarak ayrıldı | Bu event CANONICAL akışa sokulmaz; sadece quarantine tablosunda tutulur; okunması için sadece audit/inspection endpoint’inden izinli |
| `degraded` | Yukarıdakilerden en az biri `true` ise otomatik `true`; "bir sorun var ama çalışmaya devam" seviyesi | Dashboard kırmızı/sarı state; operatör alarmı |

### Ek detay alanları (opsiyonel, kalite içeriği):
- `quality_flags.reasons[]: { code: string; message: string; context: object }`
- `quality_flags.staleness_ms: number`
- `quality_flags.dedup_key: string`
- `quality_flags.expected_sequence: number \| null`
- `quality_flags.actual_sequence: number \| null`

Kalite ile ilgili kurallar ve eşiğin seçilmesi **ADN** olarak kalır (açık kararlar dosyasında listelenmiştir).

## 3. Event / Entity Sözleşmeleri (19 adet + canonical)

Aşağıdakilerin hepsi yukarıdaki **CanonicalEventEnvelope** içinde gelir, tabloda yalnızca event’e özel alanlar (payload) listelenir. Zorunlu (E) / Opsiyonel (K) bilgisini her satırda belirtiriz.

### 3.1 MarketTick
- Amaç: En düşük seviye fiyat+ticker tick’i.
- Alanlar (payload):

| Alan | Tip | Z/K | Birim/Kural |
| --- | --- | --- | --- |
| `price` | `Decimal` | E | Quote cinsinden fiyat. `> 0`. |
| `bid_price` | `Decimal \| null` | K | En iyi alış (varsa). |
| `ask_price` | `Decimal \| null` | K | En iyi satış (varsa). |
| `last_size` | `Decimal \| null` | K | Son işlem miktarı. |
| `spread_bps` | `float \| null` | K | `10000 * (ask-bid)/mid`; `quality_flags.invalid` içinde spread kontrolü yapılır (eşik ADN). |
| `market_ts` | `Instant` | E | Exchange/replay tarafındaki orijinal tick zamanı. |

### 3.2 TradeEvent
- Amaç: Gerçekleşen public trade (buy/sell taker side).
- Alanlar:
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `trade_id` | `string` | E | Exchange trade id, replay için replay-id; unique değilse normalizer `dedup`lar. |
| `side` | enum `buy` / `sell` | E | Taker side. |
| `price` | `Decimal` | E | `> 0`. |
| `quantity` | `Decimal` | E | `> 0` base miktar. |
| `quote_quantity` | `Decimal \| null` | K | İşlemin quote cinsinden büyüklüğü. |
| `market_ts` | `Instant` | E | Trade’in orijinal zamanı. |

### 3.3 OrderBookSnapshot
- Amaç: Belli derinlikte bütün snapshot.
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `depth_levels` | `int` | E | Snapshot içindeki level sayısı. |
| `bids` | `Array<[Decimal, Decimal]>` | E | `[price, qty]`; fiyat azalan sıra. |
| `asks` | `Array<[Decimal, Decimal]>` | E | `[price, qty]`; fiyat artan sıra. |
| `book_ts` | `Instant` | E | Snapshot zamanı. |
| `sequence_start` | `int64` | K | Aralık başlangıç sequence (varsa). |
| `sequence_end` | `int64` | K | Bitiş. |
| `imbalance_bps` | `float \| null` | K | Toplam bid/ask hacim farkı, bps; quality kontrolü kullanabilir. |

### 3.4 OrderBookUpdate
- Amaç: Delta güncellemesi.
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `bids_delta` | `Array<[Decimal, Decimal]>` | E | Sıfırlanan miktar = silinecek level. |
| `asks_delta` | `Array<[Decimal, Decimal]>` | E | Aynı. |
| `book_ts` | `Instant` | E | Zaman. |
| `sequence` | `int64 \| null` | K | Sıra numarası; eksikse buffer mantığı çalışmaz (degraded). |

### 3.5 Candle
- Amaç: Kapanmış ya da kapanmamış zaman dilimi mum (OHLCV)
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `timeframe` | `string` | E | Örn `1m`, `5m`, `1h`. Set ADN. |
| `open_time` | `Instant` | E | Timeframe başlangıcı. |
| `close_time` | `Instant` | E | Bitiş (mümkünse dahil değil aralığın; ikisi arasındaki fark timeframe’e eşit). |
| `open` / `high` / `low` / `close` | `Decimal` | E | Her biri `>0`; `low <= open/high/close <= high`. |
| `volume` | `Decimal` | E | Base cinsinden hacim. |
| `quote_volume` | `Decimal \| null` | K | Quote cinsinden hacim. |
| `vwap` | `Decimal \| null` | K | Zorunlu değil ama varsa tutarlılık kontrolü yapılır. |
| `closed` | `boolean` | E | `true` → timeframe tamamlandı. `false` → kısmi. Downstream feature’lar `closed=true` için sabit hesaplar; `closed=false` için “current incomplete bar” olarak kabul eder (her yeni tick güncelleyebilir; look-ahead bias için AD-16 doğrulaması yapılır). |
| `trade_count` | `int64 \| null` | K | Mum içindeki işlem sayısı (varsa). |

### 3.6 MarketRegime
- Amaç: Rejim detector çıktısı. 6 durum (AD-8).
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `timeframe` | `string` | E | Regim neyin zaman ölçeği (örn `1h`). |
| `regime` | enum `bull` / `bear` / `sideways` / `high_volatility` / `low_volatility` / `transition_uncertain` | E | Tam bu 6 değer. Yeni durum eklemek contract_version yükseltir. |
| `confidence` | `float` | E | `[0,1]` aralığında. |
| `scores` | `Record<string, float>` | E | Her rejim için alt puanlar; key’ler yukarıdaki 6 isimden oluşur. Toplam 1 olmak zorunda DEĞİLDİR; ama her anahtar tanımlanmalı. |
| `detector_version` | `string` | E | Rejim dedektörü sürümü. |
| `feature_version` | `string` | E | Girdi FeatureVector sürümü (AD-22). |
| `lookback_ts` | `{ start: Instant; end: Instant }` | E | Hesaplama aralığı. |

### 3.7 FeatureVector
- Amaç: İşlenmiş feature kümesi. Sıkı sözleşme (AD-22).
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `feature_version` | `string` | E | Sürüm; her sürüm için ayrı sözleşme dosyası (bu dokümanda ana hatları) vardır. |
| `timeframe` | `string` | E | Feature hesabı zaman ölçeği. |
| `features` | `Record<string, Decimal \| float \| null>` | E | **DÜZ sözlük (nested YOK, dizi YOK, ndarray YOK)**. Anahtar seti ve her anahtar için tip (Decimal/float), unit, izin verilen null, min/max/gözlenen aralık `contracts/feature_versions/{feature_version}.md` de yazılır. Regim/AI/Strategy yalnızca o sürümdeki anahtarları okuyabilir; tanımsız anahtar ya da tip uyuşmazlığı → **contract test FAIL**. |
| `lookback_window` | `{ count: int; timeframe: string }` | E | Örn `200 günlük 1h mum`. |
| `input_refs` | `ULID[]` | E | Hesaba giren event/entity id’leri (causation zinciri). |
| `null_count` | `int` | K | İçindeki null feature sayısı (izni varsa). |

### 3.8 StrategyContext (TÜRLÜ / YALNIZCA bu girdi, AD-25)
- **Not:** Bu bir event envelope taşıyan payload DEĞİLDİR; ama sözleşme olarak tanımlanır ve strateji plugini SADECE bunu alır (CAP-3).
- İçeriği:
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `symbol` | `Symbol` | E | Sembol. |
| `as_of` | `Instant` | E | Hesaplama zamanı; **SADECE** bu alan üzerinden strateji “hangi zamandayım” bilir. Sistem saati okunamaz. |
| `clock_ref` | Envelope içindeki `clock_ref` ile aynı | E | Replay/live tekdüzeliği. |
| `features` | `FeatureVector` | E | Mevcut feature vector; feature_version sabit. |
| `regime` | `MarketRegime` | E | Sembol zaman ölçeği rejimi. |
| `portfolio_ctx` | `PortfolioContextView` (salt okunur alt kümesi) | E | Mevcut pozisyon, realized/unrealized, bozuk PnL; SADECE okunur. |
| `eligibility_ctx` | `{ eligible: boolean; reasons: string[]; }` | E | Sembol o an stratejiye uygun mu (AD-21). |
| `scoring_policy` | `OpportunityScoreComponentPolicy` | E | Kullanılacak skor kalemleri. |
| `strategy_params` | `Record<string, primitive>` | K | Strategy_id/version’a özgü parametreler; değerler ADN ama sözleşme tarafından anahtarların tip/kısıtı tanımlıdır. |
| `run_mode` / `source_type` | Envelope’dan kopyalanmış | E | Strateji kodunun bakması GEREKMEZ ama hata ayıklama logu için verilir. |

### 3.9 StrategySignal
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `strategy_id` | `string` | E | Örn `trend_following` / `momentum`. |
| `strategy_version` | `string` | E | Semver benzeri. |
| `direction` | enum `long` / `flat` / `hold` | E | v1: short YASAK (ADN/PRD sınırı → ileride eklenirse contract_version yükselt). `long` = yeni/koru pozisyon aç; `flat` = mevcut long’dan çık; `hold` = sinyal yok/durum koru. |
| `entry_thesis` | `string \| null` | K | Açıklayıcı not. |
| `entry_price_ref` | `Decimal \| null` | K | Fiyat referans (long girilecek seviye); strateji çıktısı olabilir. |
| `stop_policy` | `{ stop_type: "fixed" \| "trailing"; stop_ref_price?: Decimal; stop_bps?: float; } \| null` | K | Varsa kullanılır, yoksa risk engine varsayılanını uygular. |
| `take_profit_policy` | `{ tp_type: "fixed" \| "scale"; tp_levels?: Decimal[]; tp_bps?: float[]; } \| null` | K | Aynı. |
| `signal_strength` | `float` | E | `[0,1]`, strateji içindeki güç; AI skoruna girdi olur. |

### 3.10 OpportunityScore
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `score_total` | `float` | E | Toplam skor; `[0,1]` aralığı. |
| `actionable` | `boolean` | E | `true` → Risk Engine’e gönderilmeye layık. |
| `score_components` | `Record<string, float>` | E | Her kalemin alt skoru (momentum, trend, mean_rev vb). Anahtar seti contract_version ile sabittir. |
| `confidence` | `float` | K | AI’nın verdiği güven; `[0,1]`. |
| `expected_edge_bps` | `float \| null` | K | Beklenen kenar (net of maliyet); değerin ne olduğu ADN (threshold). |
| `expected_cost_bps` | `float \| null` | K | İşlem maliyeti + spread + fee tahmini. |
| `model_id` | `string \| null` | K | Skoru üreten ModelVersion.model_id (varsa). |
| `policy_version` | `string` | E | Skorlama policy sürümü. |

### 3.11 RiskDecision
- **Risk Engine’in çıktısı** (CAP-4). PaperOrder olmadan önce ZORUNLU.
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `decision_id` | `ULID` | E | Benzersiz. |
| `decision` | enum `approved` / `rejected` | E | |
| `reject_reasons` | `string[]` | E | Boş dizi olsa bile her zaman dizi. Kod açıklamaları (örn `EXCEEDS_MAX_POSITION`, `STALE_DATA`, `KILL_SWITCH_ACTIVE`, `REGIME_ELIGIBILITY_FAIL`). |
| `position_sizing` | `{ base_qty: Decimal \| null; quote_qty: Decimal \| null; notional: Decimal; method: string; }` | E | Approved ise zorunlu notional. |
| `limits_snapshot` | `LimitsSnapshot` | E | Tüm limitlerin o anki durumu (aşağıda). |
| `kill_switch_state` | `{ global: boolean; per_symbol: Record<Symbol,boolean>; reason: string \| null; }` | E | AD-12 gereği. |
| `stop_loss_ref` | `Decimal \| null` | K | Uygulanan SL. |
| `take_profit_ref` | `Decimal \| null` | K | Uygulanan TP. |
| `valid_until` | `Instant` | E | Karar ne kadar süre geçerli; süresi geçen RiskDecision ile PaperOrder kabul edilmez. |
| `approval_chain` | `string[]` | K | Hangi risk kurallarından onay verildi (sırasıyla). |

#### LimitsSnapshot (RiskDecision içindeki nested):
| Alan | Tip | Z/K |
| --- | --- | --- |
| `max_position_notional_per_symbol` | `Decimal` | E |
| `max_exposure_notional_total` | `Decimal` | E |
| `max_daily_loss_notional` | `Decimal` | E |
| `max_drawdown_pct` | `float` | E |
| `max_consecutive_losses` | `int` | E |
| `max_leverage_allowed` | `1` | E | v1 hard boundary `1` olmalıdır (kısa devrede kaldıraç YOK). |
| `current_exposure_notional` | `Decimal` | E |
| `current_daily_pnl` | `Decimal` | E |
| `current_drawdown_pct` | `float` | E |
| `current_consecutive_losses` | `int` | E |

### 3.12 PaperOrder
- Not: PaperOrder yaratmak için ZORUNLU **aynı correlation_id** ile daha önce bir `RiskDecision.approved` geçmiş olmalı (CAP-4).
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `paper_order_id` | `ULID` | E | |
| `client_order_id` | `string \| null` | K | |
| `side` | enum `buy` / `sell` | E | v1 long-only: `sell` yalnızca mevcut long pozisyonunu kapatmak için kullanılır, AÇIK short olamaz (AD-18 enforcement’ında ayrıca kontrol edilir). |
| `order_type` | enum `market` / `limit` / `stop_market` / `stop_limit` | E | |
| `requested_qty_base` | `Decimal` | E | `> 0`. |
| `requested_price` | `Decimal \| null` | K | Limit/stop türleri için zorunlu. |
| `time_in_force` | enum `GTC` / `IOC` / `FOK` | K | Kaçıncı seviye ise; fill simulator davranışını etkiler. |
| `policy_refs` | `{ risk_decision_id: ULID; strategy_id: string; strategy_version: string; }` | E | Önceki karar zinciri. |
| `status` | enum `created` / `simulating` / `partially_filled` / `filled` / `canceled` / `rejected` | E | Durum makinesi. |
| `created_at` / `updated_at` | `Instant` | E | |

### 3.13 PaperFill
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `paper_fill_id` | `ULID` | E | |
| `paper_order_id` | `ULID` | E | Hangi order’a ait. |
| `side` | `buy` / `sell` | E | Order ile aynı. |
| `fill_price` | `Decimal` | E | Gerçekleşen fiyat. |
| `fill_qty_base` | `Decimal` | E | `> 0`; partial olabilir. |
| `fill_qty_quote` | `Decimal` | E | Fiyat * miktar. |
| `fees_quote` | `Decimal` | E | Komisyon; pozitif olmalı (fee negatif olursa ayrı field kullanılır, contract version yükselt). |
| `slippage_bps` | `float \| null` | K | Model referans. |
| `latency_ms` | `int \| null` | K | Simülasyon gecikmesi (ADN). |
| `fill_ts` | `Instant` | E | Gerçekleşme zamanı (replay clock). |
| `fill_model_version` | `string` | E | Hangi fill model sürümü. |

### 3.14 Position
- Portfolio Simulator tarafından yazılır (tek writer, AD-13/AD-7/AD-24).
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `position_id` | `ULID` | E | |
| `symbol` | `Symbol` | E | |
| `side` | enum `long` / `flat` | E | Short YOK (v1). |
| `base_qty` | `Decimal` | E | Açık miktar. |
| `avg_entry_price` | `Decimal` | E | |
| `current_price` | `Decimal` | E | Son işaret/tick fiyat. |
| `unrealized_pnl_quote` | `Decimal` | E | |
| `realized_pnl_quote` | `Decimal` | E | Bu pozisyonda kapatılmalardan gelen. |
| `fees_quote` | `Decimal` | E | Bu pozisyon için ödenen toplam komisyon. |
| `opened_ts` | `Instant` | E | |
| `last_updated_ts` | `Instant` | E | |
| `stop_loss_ref` / `take_profit_ref` | `Decimal \| null` | K | |
| `open_refs` | `ULID[]` | E | Açılışı yapan PaperFill’ler. |

### 3.15 PortfolioSnapshot
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `snapshot_id` | `ULID` | E | |
| `account_ref` | `string` | E | Tek paper hesabı. |
| `ts` | `Instant` | E | Zaman. |
| `cash_quote` | `Decimal` | E | Bekleyen para. |
| `equity_quote` | `Decimal` | E | Nakit + tüm unrealized. |
| `positions_snapshot` | `Position[] \| null` | K | Dolu olursa snapshot anındaki tüm pozisyonlar. |
| `realized_pnl_quote_24h` | `Decimal` | E | Son 24 saat kâr/zarar. |
| `unrealized_pnl_quote` | `Decimal` | E | |
| `fees_quote_total` | `Decimal` | E | Toplam komisyon. |
| `exposure_notional` | `Decimal` | E | |
| `drawdown_pct` | `float` | E | Peak-e göre düşüş. |
| `peak_equity_quote` | `Decimal` | E | |

### 3.16 ModelVersion
- Lifecycle için LIFECYCLE.md ile beraber okunur (AD-14/AD-23).
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `model_id` | `string` | E | Model ailesi + amacı. |
| `version` | `string` | E | Semver-like. |
| `model_family` | `string` | E | Hangi AI ailesi (ADN’de). |
| `purpose` | enum `regime_classification` / `opportunity_scoring` / `probability_estimation` / `strategy_weighting` / `feature_importance` | E | |
| `status` | enum `Candidate` / `Tested` / `Paper` / `Challenger` / `Champion` / `Retired` | E | Durum geçişleri LIFECYCLE.md. |
| `training_data_range` | `{ start: Instant; end: Instant }` | E | Eğitim aralığı. |
| `oos_range` | `{ start: Instant; end: Instant }` | K | Out-of-sample. |
| `walk_forward_runs` | `string[]` | K | Referans. |
| `feature_version` | `string` | E | AD-22 ile uyuşmalı. |
| `strategy_version` | `string \| null` | K | Eğer strateji ağırlıklandırıcı ise. |
| `artifact_uri` | `string` | E | Model artifact nerede (object storage yol ADN). |
| `hyperparams` | `Record<string, primitive>` | K | |
| `metrics_on_paper_at_promotion` | `Record<string, float \| Decimal>` | K | |
| `created_at` / `promoted_at` / `retired_at` | `Instant \| null` | K | |
| `author` / `approval_refs` | `string \| null` / `string[] \| null` | K | |

### 3.17 ModelEvaluation
| Alan | Tip | Z/K | Kural |
| --- | --- | --- | --- |
| `eval_id` | `ULID` | E | |
| `model_id` / `version` | `string` / `string` | E | ModelVersion ile aynı. |
| `dataset_kind` | enum `historical_oos` / `walk_forward` / `paper_replay` / `paper_live` | E | |
| `dataset_range` | `{ start: Instant; end: Instant }` | E | |
| `metrics` | `Record<string, float \| Decimal>` | E | Örn: sharpe, sortino, max_dd, calmar, win_rate, n_trades, edge_bps. |
| `thresholds_config_version` | `string` | E | Hangi eşik ayarıyla değerlendirildi. |
| `pass_fail` | `boolean` | E | Geçti/kaldı. |
| `reject_reasons` | `string[]` | K | Neden kaldı? |
| `evaluation_ts` | `Instant` | E | |
| `compare_to` | `{ model_id: string; version: string; metrics_delta: Record<string, float> } \| null` | K | Challenger ise champion’a göre delta. |

### 3.18 Champion/Challenger Lifecycle Events (2 event tip)
- Event tip isimleri (envelope `event_type`):
  - `model_lifecycle_transition.v1`
  - `champion_challenger_evaluation.v1`

#### 3.18.1 model_lifecycle_transition.v1 payload
| Alan | Tip | Z/K |
| --- | --- | --- |
| `model_id` | `string` | E |
| `version` | `string` | E |
| `from_status` | ModelVersion.status enum (üstte) | E |
| `to_status` | Aynı enum | E |
| `transition_command` | string (örn `request_transition("promote_challenger")`) | E |
| `gate_decision_id` | `string \| null` | K |
| `approval_refs` | `string[] \| null` | K |
| `occurred_at` | `Instant` | E |
| `audit_ref` | `string \| null` | K |

#### 3.18.2 champion_challenger_evaluation.v1 payload
| Alan | Tip | Z/K |
| --- | --- | --- |
| `champion_ref` | `{ model_id: string; version: string }` | E |
| `challenger_ref` | `{ model_id: string; version: string }` | E |
| `window_range` | `{ start: Instant; end: Instant }` | E |
| `comparison_metrics` | `Record<string, float \| Decimal>` | E |
| `winner` | enum `champion_keeps` / `challenger_wins` / `inconclusive` | E |
| `decision_ts` | `Instant` | E |
| `promotion_gate_result` | `{ pass: boolean; reasons: string[]; thresholds_used_version: string }` | E |

## 4. Data Flow I/O Contracts

Aşağıdaki zincirin her **modülünün** hangi contract türleriyle girdi aldığını ve hangilerini ürettiğini tanımlar (CAP-1 korur):

```
Exchange Adapter (port)
 -> Normalizer (adapter port arkada)
   -> Validation / Quality (AD-5)
     -> In-process typed Event Bus
       -> Feature Engine
         -> Market Regime Detector
           -> Strategy Engine
             -> Opportunity Scoring / AI Engine
               -> Risk Engine
                 -> Paper Execution Simulator (Fill Model)
                   -> Portfolio Simulator
```

| Modül | Girdi contract tipleri (envelope.event_type match) | Çıktı contract tipleri | Kısıt |
| --- | --- | --- | --- |
| Exchange Adapter (public socket/replay) | exchange-specific (port arkasında) → adapter → canonical | `market_tick.v1`, `trade_event.v1`, `order_book_snapshot.v1`, `order_book_update.v1`, `candle.v1` | ZORUNLU `QualityFlags` alanlarını dolduran normalizer’den geçmeli. |
| Normalizer | Exchange-native frames | Yukarıda 5 adet + envelope metadata | Sembol `Symbol` formatına çevir; timestamp UTC yap. |
| Validation | 5 adet market event | Aynı event (modified quality_flags) + `quarantine_event.v1` (sadece quarantine ise) | Emit kuralları §2’ye göre. |
| Event Bus (typed) | Tüm | Tüm | Sıra, at-most-once, outbox; replay’da deterministik order. |
| Feature Engine | `candle.v1`, `market_tick.v1`, `trade_event.v1`, `order_book_snapshot.v1`, `order_book_update.v1` (toplu) | `feature_vector.v1` | Doğrudan Sistem saat okuma YOK, `clock_ref` kullan. |
| Market Regime Detector | `feature_vector.v1` | `market_regime.v1` | Yalnızca 6 rejim. |
| Strategy Engine | `feature_vector.v1`, `market_regime.v1`, `portfolio_snapshot.v1`, `eligibility_ctx` + StrategyContext bütünleştiği yer | `strategy_signal.v1` | **Strategy plugin tarafında network/DB/fs çağrısı YOK (AD-9/25).** |
| Opportunity Scoring / AI Engine | `strategy_signal.v1`, `feature_vector.v1`, `market_regime.v1`, (ops.) ModelVersion skorlayıcıları | `opportunity_score.v1` | AI kendi başına PaperOrder üretemez (AD-10). |
| Risk Engine | `opportunity_score.v1`, `strategy_signal.v1`, `portfolio_snapshot.v1`, `limits_snapshot.current_state`, KillSwitch | `risk_decision.v1` | Approved olmadan paper order olmaz (CAP-4). |
| Paper Execution Simulator | `risk_decision.v1` + gerekirse `paper_order.v1` (önceden yaratılmış) | `paper_order.v1` (status güncellemeleri), `paper_fill.v1` | Fill model parametreleri ADN. |
| Portfolio Simulator | `paper_fill.v1`, `paper_order.v1` durum güncellemeleri, ayrıca periodic pricing için `market_tick.v1` | `position.v1`, `portfolio_snapshot.v1` | **Tek writer** (AD-7/13/24). |
| Model Registry / Learning Pipeline | `model_evaluation.v1`, `model_lifecycle_transition.v1` | `model_version.v1`, lifecycle event’leri | Durum değişikliği SADECE registry komutlarıyla (AD-23). |

## 5. Live / Replay Parity Kuralları (CAP-1 / AD-4)

1. Yukarıdaki 19 sözleşmeden hiçbiri `run_mode` alanına göre payload’u değiştirmez.
2. Sadece `source_type`, `clock_ref`, `ingest_ts` fark yaratır.
3. Feature/Regime/Strategy/Risk/Portfolio kodlarında `if run_mode == "replay"` ya da eşdeğer dallanma **YASAKTIR** (CAP-1 success test’i tarar).
4. Zaman mantığı: kod, “şimdi” olarak **clock_ref içinden** değer almalı. Sistem saatini doğrudan okuyan herhangi bir kod contract test’inde FAIL olur.
5. Determinism: replay sabiti aynı ise çıktı tam olarak tekrar edebilir olmalı (random seed, shuffle vb. hepsi contract tarafından ya sarılmalı ya da dışarıya verilmeli).

## 6. Kalitenin Her Contract’a Taşınması

Herhangi bir event’ten başlayıp Risk’e kadar, tüketici şu soruyu cevaplayabilmelidir: “Bu zincirin kalitesi çalışmaya müsait mi?” — bunun için tek başına `envelope.quality_flags` yeterlidir. Zorunlu kural: **Hiçbir tüketici validator modülüne RPC/import yaparak “bu data iyi mi?” diye sormaz.** (CAP-2)

## 7. Backtest / Look-ahead bias kontrol sözleşmesi

- Feature engine’in geçmiş `close_time` sonrası verilere erişmesi mühendislik duvarıyla engellenir (AD-16).
- `candle.closed=false` kısmi mumlar feature’da kullanılırsa: sözleşme şunu garanti eder: `as_of < next(open_time)` ve ileride gelen düzeltmeler (high/low/close değişebilir) feature vector’ü etkilemez (replay sırasında deterministik olarak aynı anda erişim).
- FeatureVector sözleşmesinde `input_refs`, backtest regression test’lerinde kullanılır: “aynı girdiler → aynı çıktı” doğrulanır.

## 8. Notlar

- Yeni sözleşme eklemek ya da varolanda kırıcı değişiklik yapmak → **contract_version** yükseltmek ve ADN onaylarını almak zorunda.
- Backward uyumlu ek alanlar → `extra` ya da opsiyonel yeni alan; kırıcı ise semver.
- Tüm sözleşmeler için otomatik `pytest` contract testleri (schema + kalite + live/replay branch kontrolü + forbidden import kontrolü) uygulanacaktır; bu SPEC test sözleşmesinin çerçevesidir.
