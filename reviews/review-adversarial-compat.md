---
title: "Adversarial Compat Review — Architecture Spine"
review_type: adversarial-compat
scope: ARCHITECTURE-SPINE.md (2026-08-10)
focus: "İki veya daha fazla geliştirici her AD'yi harfiyen uygular ama yine de birbiriyle uyumsuz / çakışan implementation üretir. Aranan üç çatışma ekseni: (1) çelişen shared-data shape, (2) tek entity'nin iki/üç sahibi, (3) çelişen mutation yolları."
status: final
date: "2026-08-10"
---

# Adversarial Compatibility Review — Crypto AI Trader Architecture Spine

**Karar:** RED — Mimari omurga, her AD harfiyen uyulsa bile en az 4 ciddi module-arası uyumsuzluk doğuracak şekilde boşluklar içeriyor. En kritik üçü doğrudan incorrect trading state / yanlış PnL / audit kaybı üretir. Implementation öncesi kapatılması şart.

Aşağıdaki her bulgu için: iki/üç geliştirici, her AD'yi tamamen uyduğu halde, ortaya çıkan uyumsuzluk anlatılmaktadır.

---

## Finding 1 — Position / PnL Entity Dual Ownership: Portfolio Simulator (Dev A) vs Backtest Engine (Dev B)

- **Taraflar:**
  - Dev A → `app/simulation/portfolio` (Portfolio Simulator)
  - Dev B → `app/simulation/backtest` (Backtest Engine)
- **İkisi de hangi AD'leri harfiyen uyuyor:**
  - AD-13 ("Balance, equity, positions, unrealized/realized PnL, fees, exposure, drawdown yalnızca Portfolio Simulator tarafından türetilir.")
  - AD-7 ("paper order/fill/position → simulation tarafından yazılır.")
  - AD-4 (Live/Replay Parity — same contracts)
  - AD-1 (Modular monolith — same bounded context same codebase)
- **Uyumsuzluk mekanizması:**
  - AD-7, yazım yetkisini *bounded context* (simulation) seviyesinde verir. AD-13 ise *alt-modül* (Portfolio Simulator) seviyesinde "tek kaynak" olduğunu söyler. İki kural çelişmez görünür ama birlikte yanlış yorumlanabilir.
  - Dev A (Portfolio): AD-13'ü en dar okur → **Position, PnL, drawdown satırlarına SADECE Portfolio Simulator yazar.** Diğer tüm modüller (Backtest dahil) SADECE okur; Fill event'lerini dinleyip Portfolio kendisi türetir.
  - Dev B (Backtest): AD-7'yi en doğal okur → Backtest Engine de `simulation` bounded context'i içindedir. §10 Backtest Engine sorumluluk listesinde "historical evaluation, cost-aware simulation, walk-forward input" yazıyor. Backtest bir sürü batch Position/PnL satırı üretmesi gerektiğinden, performans ve doğruluk için **doğrudan storage'a Position/PnL yazar.** AD-13'nün "kaynak" sözcüğünü "mantıksal kaynak" olarak yorumlar; backtest ise aynı hesaplamayı batchte yapar.
- **Ortaya çıkan hasar:**
  - Tek bir `positions` / `portfolio_snapshots` tablosuna **iki ayrı writer.** Backtest batch yazımı, Portfolio'nun event-tabanlı yeniden türetimiyle yarışırcasına aynı satırları günceller/overwrite eder.
  - Backtest raporunda görünen PnL ile Portfolio read-model'inde (API/Dashboard) görünen PnL **aynı replay input'una rağmen farklı olur.** (Biri doğrudan yazılmış, diğeri fill-event'lerinden türetilmiş; fee/slippage yuvarlama sırası, partial fill birleştirme sırası farklı olduğundan kesin olarak sapar.)
  - Üstelik AD-13'nün "API/Dashboard bu read model'i tüketir; yeniden hesaplayıp overwrite etmez" sözü ihlal edilmemiş olur — overwrite'i Backtest yapar, API/Dashboard zaten sadece okur.
- **Neden hiçbir AD ihlal edilmedi:**
  - Dev A AD-13 harfiyen (Portfolio türetir).
  - Dev B AD-7 harfiyen (simulation yazma yetkisi var) + §10 Backtest sorumluluk listesi (cost-aware simulation PnL hesaplaması bariz içerir).
  - İki AD arasında "simulation içindeki alt modüllerden hangisinin *hangi* tabloya *nasıl* yazacağı" kuralı yok.

---

## Finding 2 — `FeatureVector.features{}` Shared-Data Shape Conflict: Feature Engineering (Dev C) vs Regime/AI (Dev A) vs Strategy Plugins (Dev B)

- **Taraflar:**
  - Dev C → `app/processing/features` (Feature Engineering + TA)
  - Dev A → `app/decisioning/regime` + `app/decisioning/ai` (Regime Detector + AI Engine)
  - Dev B → `app/decisioning/strategy` plugins (TrendFollowing + Momentum)
- **Hepsi hangi AD'leri harfiyen uyuyor:**
  - AD-3 (Canonical Event Envelope — envelope + zorunlu payload alanları var)
  - AD-4 (Live/Replay Parity — her iki modda aynı contract)
  - AD-8 (Regime, input FeatureVector, output MarketRegime — event üzerinden tüketir)
  - AD-9 (Strategy pure — sadece FeatureVector, MarketRegime, portfolio context üzerinden çalışır; DB çağırmaz)
  - AD-10 (AI, FeatureImportance üretir — FeatureVector tüketir)
- **Uyumsuzluk mekanizması:**
  - §4 "Başlıca Domain Event'ler" tablosunda `FeatureVector` için zorunlu payload alanları listelenmiş: `feature_version`, `timeframe`, `features{}`, `lookback_window`, `input_refs[]`.
  - `features{}` sözlüğünün **iç yapısı, anahtar isimlendirme kuralı, value tipi, iç içe geçme seviyesi** hiçbir yerde tanımlı değil. Sadece sözlüğün varlığı zorunlu.
  - Üç ayrı geliştirici aynı `feature_version="fv1"` sürümünü kullanarak **üç tamamen farklı sözlük shape** üretir/tüketir:
    - Dev C (Feature): `"flat"` şekil. `Dict[str, Decimal]`. Anahtarlar: `"rsi_14"`, `"ema_50"`, `"volume_24h_usdt"`, `"atr_20"`, … (standart gösterim, tire/alt tire ayırıcı, sayı eki). Bütün göstergeler tek seviye.
    - Dev A (Regime + AI): `"kategorili"` şekil. `Dict[str, Dict[str, float]]`. Anahtarlar: `{"momentum": {"rsi_14": ...}, "trend": {"ema_50": ...}, "volatility": {"atr_20": ...}, "volume": {"v_24h": ...}}`. §3 bileşen tablosundaki "Technical Analysis RSI, EMA, ATR vb. versioned indicators" ayrımını kategori ismine çevirmiş. AI/Regime kodları `features["momentum"]["rsi_14"]` şeklinde okuyor.
    - Dev B (Strategy Plugin — TrendFollowing): `"timeframe iç içe"` şekil. Çünkü §25 "Architecture Decision Needed" item 2 timeframe setini açık bırakmış. Plugin, §7 "uygun olduğu rejimler + config sürümü + gerekli input'ları deklare eder" kuralını uyarak — ve timeframe seti bilinmediğinden — her timeframe için ayrı feature seti altında gömüyor: `features = {"tf_1m": {"rsi_14": ...}, "tf_15m": {"rsi_14": ..., "ema_50": ...}, "tf_1h": {...}}`. Aynı zamanda değerler np.ndarray (Python ML std — §25 item 5 "ilk AI family" açık bırakıldığından plugin kendisi numpy kullanıyor) çünkü strategy wrapper sklearn arayüzü ile yazılmış.
- **Ortaya çıkan hasar:**
  - Aynı `schema_version` + aynı `feature_version` dizesine rağmen runtime'da üç ayrı shape.
  - Regime Detector, `features["momentum"]` anahtarını aradığında KeyError (Dev C flat üretmiş). Ya da tam tersi — Regime kendi kategorili yapıyı bekliyor, flat gelince iç içe sözlükte tip hatası.
  - Strategy plugin, `features["tf_15m"]["ema_50"]` bekliyor; ne flat ne kategorili onu sağlamıyor. Hepsinin sürüm string'i aynı (`fv1`) olduğundan AD-3'nün şema versiyonu kuralı da ihlal edilmemiş — çünkü hiçbir AD, `features{}` iç anahtarları sözleşmeye bağlamamış.
  - AI Engine `FeatureImportance` ürettiğinde flat anahtar isimleri kullanıyor; Strategy kategorili + timeframe iç içe anahtarlarla çalıştığından, importance skorları **hiçbir feature ile eşleşmiyor** (anahtar uyuşmazlığı) ama sistem sessizce 0 importance gibi davranıyor.
- **Neden hiçbir AD ihlal edilmedi:**
  - AD-3 envelope + listelenmiş payload field'larının *varlığını* zorunlu kılar; *içinde* ne olduğu konusunda sessiz. `features{}` bir sözlüktür, üç geliştirici de sözlük vermiştir.
  - AD-8/9/10, ilgili modüllerin FeatureVector *tüketmesini* söyler; *hangi şekliyle* tükettiğini değil.
  - AD-4 sadece live/replay parity zorunlu kılar (üç taraf da kendi modunda kendi şeklini koruduğu için live/replay arasında fark yok).
  - Architecture Decision Needed (§25 item 2) açık bırakılmış yerleri sadece "değişiklik bekleyen" diye işaretler — ama açık bırakılan yerin, mevcut AD'leri ihlal etmeden üç farklı şekil üretmesine engel olmaz.

---

## Finding 3 — Symbol Eligibility / Health Entity Triple Ownership + Conflicting Mutation Paths: Data Quality (Dev C) vs Market Scanner (Dev B) vs Risk Engine (Dev A)

- **Taraflar:**
  - Dev C → `app/processing` (Data Quality Monitor)
  - Dev B → `app/processing` (Market Scanner)
  - Dev A → `app/decisioning/risk` (Risk Engine)
- **Hepsi hangi AD'leri harfiyen uyuyor:**
  - AD-5 (Data Quality Is a Hard Gate — quality_state set; symbol unhealthy → strategies stop → order block → alert)
  - AD-7 (Read Model Ownership — raw market data → ingest; feature store → processing; … — quality_state veya symbol_eligibility için ayrı bir ownership satırı YOK)
  - AD-8 (Strategy/Risk, rejimi event üzerinden tüketir — ama sembol sağlığı/eligibility için böyle kural YOK)
  - AD-11 (Risk Engine Is the Final Approval Gate — *stale data protection*, *exchange/data failure protection*, *long-only/spot-only zorunlu kısıt* + "Risk failure varsa pipeline reject eder; fallback yoktur.")
  - AD-19 (Failure Defaults to Safe Stop — stale data → yeni paper execution engelle, state işaretle)
  - Ayrıca §195 bileşen tablosu: Market Scanner sorumluluğu "Universe tarar, candidate list + exclusion reason üretir"; Risk Engine sorumluluğu "stale data protection" + "exchange/data failure protection".
- **Uyumsuzluk mekanizması:**
  - Aynı mantıksal entity: **"Şu an sembol X, strateji sinyali üretmek / paper order geçmek için uygun mu?"** — ama bu entity'nin canonical yazarı hiçbir AD ile atanmamış. Üç ayrı modül de **kendi state'ini** tutar ve kendi kuralıyla günceller:
    - Dev C (Data Quality): AD-5'i uygular → `quality_state` alanını yönetir. Zorunlu kontrollerden herhangi biri (stale, missing, invalid_price, …) tetiklenirse `quality_state = unhealthy` yapar, `SymbolHealth` event'i yayınlar. AD-5'e göre etkilenen stratejiler *stop* edilir. Bu Dev C'nin gözünde gerçektir. Kalıcı storage'ta `symbol_health` tablosuna yazar (processing bounded context — processing yazma yetkisi ile uyumlu).
    - Dev B (Market Scanner): §195 bileşen tablosundaki kendi sorumluluğunu uygular. Bir sembolün "candidate" olup olmadığına karar verir; eligibility kendi kriterleri (spread eşiği, likidite eşiği, quote currency uyumu, §3 Scanner kriterleri). §25 item 2/6 "Architecture Decision Needed" açık bırakıldığından eşikleri kendisi makul setler. Sonucu: **kendi `symbol_eligibility` tablosuna (processing bounded context — AD-7 processing feature store yazabilir, eligibility da processing'dir) + `SymbolEligibility` derived event (AD-3 source_type=derived izin verir).** Scanner eligibility'si, quality_state'den bağımsız çalışabilir: spread aşırı ise quality_state *healthy* olsa bile Scanner eligible DEĞİLDİR der.
    - Dev A (Risk Engine): AD-11'i ve §12 Risk sorumluluk listesini uygular. Listede açıkça **stale data protection** ve **exchange/data failure protection (FR-055)** + uzun pozisyon only / spot only kısıtlar var. AD-11 "Risk failure varsa pipeline reject eder; fallback yoktur." Risk Engine, kendi içindeki `risk_symbol_blocked: Dict[symbol, reason_code_set]` state'ini korur; ve AD-19 "state işaretle" kuralını bu iç state'e uyarlar. Üstelik §21 Failure Modes tablosu "Stale market data → yeni strategy sinyalleri block, paper order reject (AD-5 + AD-11)" diyor — Risk Engine bunu AD-11 çerçevesinde kendi state'inden yapar, Data Quality'nin state'ine güvenmek zorunda olduğunu söyleyen hiçbir kural yoktur. Risk Engine, örn. 3 ardışık paper order'ın stale reject sonrası sembolü *kendi* internal state'inde 10 dakika süreyle block'layabilir (consecutive losses + stale kombinasyonu AD-11 kapsamında).
- **Ortaya çıkan hasar:**
  - Aynı sembol X için 3 ayrı state aynı anda **çelişir:**
    - Quality: `quality_state=healthy`
    - Scanner: `eligibility=excluded (spread_bps_threshold)`
    - Risk: `blocked=True (stale_protection_cooldown)`
  - AD-11 "Risk Engine final approval gate" der ama AD-11 sadece *order anında* rejections üzerinde finaldir. Sembol state'inin canonical "yazarı" değildir. Dolayısıyla:
    - Scanner, eligibility=false olsa da stratejiye hiç sinyal üretilmemesini garanti edemez (çünkü Scanner AD-9 strategy plugin'lerine erişemez; sadece candidate list yayınlar — strategy plugin yine de eski data'dan çalışabilir).
    - Data Quality, unhealthy yapsa bile Risk Engine'in kendi cooldown state'i ile sıfırlanması arasında saatler fark olabilir; birinde açılıp diğerinde kapalı kalır.
    - API/Dashboard read model'i (AD-7 sadece okur) — hangi state'i gösterir? Ucundan tutarsız UI.
    - En kötüsü: *bir modül recovery tetikler (ör. DQM health reset), diğer iki modül kendi state'ini sıfırlamadığı için* sembol aslında sağlıklı olmasına rağmen sürekli block'ta kalır.
- **Neden hiçbir AD ihlal edilmedi:**
  - Dev C: AD-5 zorunlu kıldığı her şeyi yaptı (quality_state + event + downstream etkile).
  - Dev B: §195 "candidate list + exclusion reason" sorumluluğunu yerine getirdi; processing bounded context olduğu için kendi eligibility read/write yapmak AD-7 ile uyumlu; derived event AD-3 ile uyumlu.
  - Dev A: AD-11 "stale/exchange-failure protection" + "final approve gate" zorunluluklarını yerine getirdi; kendi internal state'i §21 "state işaretle" kuralı ile uyumlu.
  - Hiçbir AD, "sembol ticaret uygunluğu" adlı mantıksal entity için tek yazarı ve tek mutation yolunu söylemedi.

---

## Finding 4 — Model Lifecycle State (`ModelVersion.status`) Triple Ownership: Registry (Dev A) vs Learning Pipeline (Dev B) vs Champion-Challenger (Dev C)

- **Taraflar:**
  - Dev A → `app/governance/registry` (Model Registry)
  - Dev B → `app/governance/learning` (Learning Pipeline)
  - Dev C → `app/governance/promotion` (Champion / Challenger promotion gate)
- **Hepsi hangi AD'leri harfiyen uyuyor:**
  - AD-7 (Read Model Ownership → "registry → governance tarafından yazılır.")
  - AD-14 (Governed Learning Lifecycle → lifecycle `Candidate → Tested → Paper → Challenger → Champion → Retired`. Promotion için zincir zorunlu. Champion değişimi audit log ile kaydedilir; rollback mümkün olmalı.)
  - §14 Model Registry: "durumlar … her geçişte evidence … Champion→Challenger geçişinde audit log … her sürüm için predecessor tutulur."
  - §9 Adaptive Learning akış şeması: Learning Pipeline, `Train → Backtest → Out-of-Sample → Walk-Forward → Paper → Evaluation → Challenger` zincirini *orkestra eder.*
  - §195 bileşen tablosu: Learning Pipeline "Train/evaluate/promote lifecycle orkestrasyonu"; Model Registry "Model/version/state/metrics/audit saklar"; Champion/Challenger "Promotion gate ve rollback kararı yönetir."
- **Uyumsuzluk mekanizması:**
  - Aynı fiziksel alan: `ModelVersion.status` (enum: `Candidate → Tested → Paper → Challenger → Champion → Retired`).
  - Yazım yetkisi AD-7'de sadece *governance bounded context* seviyesinde — üç alt modül de governance içinde. AD-14 ve §14 "Registry saklar" der ama *kimin güncelleyeceğini* söylemez.
  - Üç geliştirici kendi sorumluluk tanımından hareketle status alanını günceller:
    - Dev A (Registry): §14 "Model Registry saklar" + AD-14 "Champion değişimi audit log ile kaydedilir" → **status sadece Registry API'si üzerinden değiştirilebilir.** `registry.transition(model_id, to_status, evidence, approver=None)` metoduyla; evidence olmadan, approval olmadan, predecessor kaydetmeden, audit yazmadan transition olmaz. Registry bu geçişleri kendi transaction'ında yapar, status alanını bu metot dışında kimse dokunmaz diye varsayar.
    - Dev B (Learning Pipeline): §9 akış şemasında zinciri kendisinin *orkestra ettiğini* okur + §195 "Train/evaluate/promote lifecycle orkestrasyonu" + AD-14 zinciri. Yani: bir stage (örn. Backtest) başarıyla tamamlandıktan sonra **kendisi doğrudan status = Tested günceller** (storage'a doğrudan UPDATE — governance bounded context, AD-7 izin verir). Dev B'nin argümanı: "Registry sadece *sakar*; karar verip güncelleyen benim çünkü ben orkestra ediyorum." Evidence'yi kendi artifacts klasörüne yazar ve URI'yi registry row'una başka bir alandan (evidence_uri) yazar; ama Registry transition API'sinden geçmediği için Registry'nin *kendi* audit log tablosuna kayıt düşmedi.
    - Dev C (Champion / Challenger): §195 "Promotion gate ve rollback kararı yönetir." + AD-14 "human gate zorunlu v1". Promosyon anında, approval geldikten sonra **kendisi status = Champion yapar ve eski champion'ın status'ünü Retired yapar.** Üstelik bu modül, aktif champion'ın kim olduğunu hızlıca sorgulamak için `active_champion_per_strategy` adında ayrı bir tablo tutar (§14 "predecessor tutulur; rollback doğrudan mümkün" kuralını hızlı karşılık için önbellek olarak görür).
- **Ortaya çıkan hasar:**
  - `ModelVersion.status` alanına 3 ayrı mutation yolu:
    - Registry API → audit log + predecessor + evidence check ile.
    - Learning Pipeline → doğrudan UPDATE, audit log düşmez, evidence check yok (sadece URI yazar).
    - Champion-Challenger → aynı anda iki row'u (eski + yeni champion) günceller; ayrıca paralel `active_champion_per_strategy` tablosu.
  - Tutarsızlık örnekleri:
    - Learning Pipeline, Backtest'i geçti diye status = Tested yapar ama OOS/WF/Paper aşamalarından hiçbirini Registry transition'ından geçirmeden doğrudan atlar; AD-14'nün zinciri `Tested → Paper → Challenger → Champion` olarak beklemesine rağmen — doğrudan Paper veya Challenger'a bile atlayabilir. "AD-14 zinciri zorunlu" der ama kimin zorunlu kıldığını söylemez; Dev B kendince zinciri takip eder (sadece sırasını) ama Registry'nin doğrulamasını atlar.
    - Audit kaybı: Registry'nin `lifecycle_audit` tablosuna Learning Pipeline ve Champion-Challenger doğrudan UPDATE attığı için **yarısı boş.** AD-14 "Champion değişimi audit log ile kaydedilir" — Champion-Challenger modülü audit log'u *kendi* tablosuna yazmış olabilir; Registry'ninkini yazmamıştır. Audit sorgusu iki tabloya bakması gerekir, öyle bir kural yok.
    - `active_champion_per_strategy` tablosu (Dev C) ile `ModelVersion.status = Champion` row'ları (Registry + Pipeline güncelledikçe) **çelişir.** Örn. Pipeline status = Champion yapmış, Dev C'nin tablosu eski champion'ı gösteriyor çünkü Dev C kendi decision flow'u henüz bitmedi.
  - Rollback sırasında zarar büyür: AD-14 "rollback mümkün olmalı" der — ama hangi modül rollback yapar? Registry'si, Cancellor'ı, Pipeline'ı? Üç ayrı state'ten hangisi alınır?
- **Neden hiçbir AD ihlal edilmedi:**
  - Dev A: §14 "registry saklar" + AD-14 "audit log" → status geçişlerini denetleyen tek doğru API'yi yapmıştır.
  - Dev B: §9 + §195 "orkestra eder" + AD-14 zinciri var → her aşamayı başarıyla tamamladıktan sonra status güncellemesi yapma yetkisinin olduğunu iddia eder. Üstelik AD-7 governance yazma yetkisi verir.
  - Dev C: §195 "promotion gate ve rollback kararı yönetir" + AD-14 "human gate zorunlu v1" → approval sonrası status değiştirme yetkisi kendinde der.
  - Üç yorum da yazılı AD metniyle desteklenir.

---

## Özet / Sıralama (En Kritik → Daha Az Kritik)

| # | Bulgu | Çarpışma Ekseni | Etki |
|---|---|---|---|
| 1 | Finding 3 — Symbol Eligibility / Health triple ownership | **Tek entity 3 yazarı + 3 mutation yolu** | INCORRECT TRADING STATE — stokasten sürekli açık/kapalı, yanlış recovery |
| 2 | Finding 1 — Position / PnL dual ownership (Portfolio vs Backtest) | **Tek entity 2 yazarı** | YANLIŞ PnL — backtest raporu ≠ dashboard state, finallerde yanıltır |
| 3 | Finding 2 — FeatureVector.features{} shape conflict (3 taraf) | **Çelişen shared-data shape** | RUN-KEYERROR / SESSIZ SKOR HATASI — AI/Regime/Strategy hiç çalışmaz veya yanlış skorlar |
| 4 | Finding 4 — ModelVersion.status triple ownership | **Tek entity 3 yazarı + paralel tablo** | AUDIT KAYBI + GOVERNANCE DELİĞİ — promosyon/rollback kayıpları, denetlenemez durum |

---

## Kapatma Önerileri (İmplementation Öncesi)

Her bulgu için minimum düzeltme önerisi:

1. **Finding 3 → Yeni AD:** "Symbol eligbility/health tek canonical entity'dir. Yazarı: Risk Engine. Data Quality ve Scanner, kendi state'lerini publish eder ancak Risk Engine, final canonical `symbol_tradeability` state'ini merge eder ve tek yazar. Diğer tüm modüller (Strategy dahil) sadece Risk'in yayınladığı event üzerinden okur."
2. **Finding 1 → Yeni AD + AD-7/13 düzeltme:** "Backtest Engine, Position/PnL/Portfolio satırı yazamaz. Backtest, Portfolio Simulator'u replay modunda çağırarak PnL üretir; storage yazma yine Portfolio tarafından gerçekleştirilir. Backtest sadece input replay paketi ve evaluation çıktılarını (object storage/relational eval tablosu) yazar."
3. **Finding 2 → Canonical sözleşmeyi genişlet:** "`FeatureVector.features{}` → `features` flat `Dict[str, Decimal]` (mecburi) + opsiyonel `feature_groups: Dict[str, List[str]]`; timeframe embedding `input_refs[]` ile yapılır; numpy tip olayda iptal — sözleşmede value tipi Decimal olmalıdır. Tüketiciler, ihtiyaç duyarlarsa flat sözlükten kendi kategorilerini runtime'da gruplar; schema_version aynı kalmaz ama sözleşme dahili olarak kilitlenir."
4. **Finding 4 → Yeni AD:** "`ModelVersion.status` YALNIZCA Model Registry modülü tarafından güncellenebilir. Learning Pipeline ve Champion-Challenger, Registry'nin `propose_transition(...)` API'sini çağırır. Registry, evidence ve lifecycle zincirini doğrular, audit yazar, predecessor set eder, sonra transition'ı commit eder. Aynı anda `active_champion_per_strategy` tablosu da sadece Registry tarafından tutulur."
