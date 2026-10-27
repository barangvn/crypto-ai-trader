# Source Gaps — S-FND-05 (Tam 8 GAP, HİÇBİRİ SESSİZCE İCAT EDİLMEDİ)

GAP = SOURCE OF TRUTH içinde açıkça belirtilmemiş, karar için gerekli ama implementasyon sırasında default veya ADN ile çözülecek. **8 GAP, hiçbiri mandatory bloke değil.**

| GAP # | GAP İçeriği | Eksik Source Location | Default Çözüm (ADN) | Neden İcat Etmediğimizi Kanıt (Referans) |
|---|---|---|---|---|
| GAP-01 | Schema library seçimi: stdlib / pydantic / msgspec / attrs? PRD §9.9 "Python, Node.js hybrid" → Python seçildi ama spesifik schema kütüphanesi PRD/EPIC/CONTRACTS içinde YAZILMIYOR. | EPIC-2 S-CON-01 L259 Pydantic v2 "(veya uyumlu typed schema)" açıklama; ancak bağlayıcı DEĞİL. | OD-05-01 DEFAULT = stdlib frozen dataclass + man post-init. HR-05 0 3p korur. | Eksik source: EXPLICIT CONTRACTS.md §1/§2 "tip kütüphanesi" söylenmiyor. Non-binding EPIC kelime. Icat ETMEK yerine stdlib varsayılan. |
| GAP-02 | ULID concrete Python package seçilemedi. "ULID/UUIDv7" CONTRACTS L14: "tercihen ULID; sıralanabilir." Tek kelime "tercihen" non-binding. | CONTRACTS §0 L14. Kelime "tercihen". Bağlayıcı paket önerisi YOK. | OD-05-02: Constructor Sadece regex doğrulama, üretmez. UUID7 3.11+ stdlib ise RDH-01 producer kullanır. ULID Crockford 26 BASE32 regex. Üretim hikâyesi = RDH-01. | 3p python-ulid BLOK HR-05. Kaynak yok. İcat etmeyiz. Doğrulama/üretim AYRI hikâyeler (boundary bu hikâyede sadece doğrula). |
| GAP-03 | QualityFlags.reasons[].code set: kaç tane code? Tam hangi isimlerde? (AD-5 9 kontrol var ama code set EXACT isim CONTRACTS L65 "code: string" olarak boş.) | CONTRACTS §2 L65 reasons[].code. AD-5 9 kontrol (timestamp/seq/dup/missing/stale/ooo/invalid price/invalid vol/abnormal spread) ancak code exact isim YOK. | Default code set: `["timestamp_invalid","sequence_gap","duplicate_event","missing_refs","stale_data","out_of_order","invalid_price","invalid_volume","abnormal_spread"]` 9 kod. Ama validator 9 kural AD-5 RDH-01 içinde; FND-05 sadece code string max 64. Exact isimleri enforce ETME. | Yalnızca code isimleri CONTRACTS'da listelenmediği için İCAT ETMEYİZ, string format zorlarız. RDH-01 concrete kodları üretir. |
| GAP-04 | `event_type` regex strictliği: `^[a-z_]+\.v[0-9]+$` YETERLİMİ? Major version zorunlu, minor yok. Contratlarda L34: "Sabit sözleşme adı + semver major" ama minor/patch nasıl gider? | CONTRACTS §1 L34 Açıklama satırı: "... adı + semver major." Sadece MAJOR. Patch nasıl ayrım YOK. | Default: regex sadece `{snake_name}.v{major_int}`; minor version payload.schema_ref içinde veya payload.version taşır. Envelope event_type MAJOR ONLY. | Kaynak: "semver major" kelimesinden ötürü MAJOR sadece. İcat ETMEYİP (full semver v1.0.0 event_type yapmak yerine) major only regex. |
| GAP-05 | Instant epoch tolerance: minimum tarih 2020-01-01T00:00:00Z üst sınır 2100? / Zero time? / Negatif Instant (pre-Unix epoch) geçerli mi? | CONTRACTS L15 "ISO-8601 UTC" demek ama tarih aralığı YOK. | Default: regex format doğrula, aralık ZORLAMA. Gelecekteki NTP skew/negative için RDH-01 validation. Bu hikâyede format + UTC + zorunlu. | Tarih aralığı YAZILMADIĞI için icat ETMEYİZ. Sadece regex. |
| GAP-06 | envelope.event_id / correlation_id: SAME generator? Yani event_id produced aynı zaman; ama zincirin başlangıcında `causation_id == event_id` invariant. 3 id alanı için hangi sırayla üretildiği, produce side validation RDH-01, ama bu hikâyede type check. | CONTRACTS §1 L33/40/41. 3 id var. | Default: 3 id'ler her biri sortable regex match. Eşitlik invariant: İLK HALKA `causation_id == event_id` post-init kontrol EKLENEBİLİR (ancak üretim tarafı RDH). Bu hikâyede opsiyonel invariant. | Producer RDH-01 olduğu için, burada sadece sortable type-gate + opsiyonel causation==event id doğrulaması (eğer payload first_halka ise). |
| GAP-07 | Decimal precision / rounding: CONTRACTS L17 "18 haneli ondalık" kuralı var, ama 18'den fazla Decimal input OLURSA NE OLUR? HATA mı clamp mı? ROUNDING mod? | CONTRACTS §0 L17 Decimal "18 haneli ondalık". Fail/fail-closed yok. | Default: Bu HİKÂYEDE payload generic T → Decimal doğrulama S-CON-02 MarketTick/Trade. GAP-07 = CON-02'ye AKTARILIR. FND-05 ENVELOPE 18 haneli kuralını ENFORCE ETMEZ (payload generic). | İcat etmemek. Sözleşme §0 Decimal 18 haneli ancak payload doğrulaması S-CON-02. |
| GAP-08 | Hash/digest algorithm for determinism (D-1): sha256[:12] mi? md5 (hash() built-in not stable)? JSON sort keys? | SPEC §7 D-1 "hash(dataclass_tuple)" AÇIK. Ancak builtin hash() sürümler arası istikrarsız olabilir. | Default: test helper helper sha_json (json.dumps sort_keys+compact separators + hashlib.sha256 hexdigest[:12]) FND-04 helper'dan reuse. Implementation tarafında ANA HASH belirtmek zorunda değiliz; determinism testte sha_json kullanılır. | JSON + SHA256 cryptographically stable. Helper FND-04'de var. Reuse = no icat. |

## GAP Toplamı

| Sınıf | Adet |
|---|---|
| Mandatory (READY'i bloke eder) | 0 |
| Optional (ADN çözülebilir) | 8 |
| Closed Permanent | 0 (burada değil open-decisions içinde OD-05-04 Closed orada) |
| Yeni requirement icat etme riski (SİLİNDİ) | 0 |

Default çözüm sayesinde 8 gap = 0 mandatory. → Implementation READY için yeterli.

## Option C Sınırı (OD-05-09) — Kanonik Tip Sahipliği

GAP-01/02'nin default çözümleri S-FND-05 tiplerini (`app/contracts/envelope.py`, `app/contracts/quality_flags.py`; public yol `app.contracts.sfnd05_api`) kanonik kabul eder. `app/contracts/canonical.py` legacy tipleri ayrı sözleşmedir; aynı isimler eşdeğerlik garantisi DEĞİLDİR ve aralarında örtük dönüşüm/adaptör varsayılmaz (Option C — OD-05-09). Root `app/contracts/__init__.py` export seti değişmez. Ayrıntı: `open-decisions.md`.
