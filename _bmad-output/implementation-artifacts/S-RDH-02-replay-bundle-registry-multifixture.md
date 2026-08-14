---
story_id: S-RDH-02
title: "Replay Bundle Registry + Multi-Fixture Discovery & Integrity (Registry Single Owner)"
story_key: "3-2-replay-bundle-registry-multifixture"
epic: E-RDH (Replay Data & Adapter Abstraction)
status: ready-for-dev
created: 2026-08-11
updated: 2026-08-11
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
  - ./S-RDH-01-replay-data-pipeline-poc.md
contract_version: "1.0.0"
---

# Story S-RDH-02 — Replay Bundle Registry + Multi-Fixture

## 1. Story ID
`S-RDH-02` (Epic E-RDH, Story #2)

## 2. Title
**Replay Bundle Registry + Multi-Fixture Discovery & Integrity (AD-7 Single Writer Ownership)**

## 3. Goal
S-RDH-01 ile tekil `ReplayBundleAdapter(tek dosya)` yerine; **çoklu replay bundle**’ını keşfeden, metaveriyle kataloglayan, bütünlüğünü (hash/row-count/semantik) doğrulayan ve tek bir sahiplikle yöneten **ReplayBundleRegistry** oluştur. Hedef:
1. FR-007 (provenance linking) + NFR-006 (raw provenance) gereğini karşılamak: Her replay run, hangi bundle sürümüyle çalıştığını bilmeli ve bu bilgi envelope’ya taşınabilmeli.
2. Çoklu fixture üzerinde deterministik koşu: Birden fazla CSV fixture (ör. 7 adet mevcut `tests_fixtures/*.csv` ya da `tests_fixtures/` altındaki tüm set) keşfedilip listelenmeli.
3. Bundle bütünlüğü: Hash check, satır sayısı, sembol/timeframe beyanları, expected event count; integrity FAIL → bundle **kullanıma alınmaz (fail-closed)**.
4. Multi-bundle sıralı stream: Seçilen N tane bundle’ı, satır satır merge-eden timestamp-ordered stream `PublicExchangeAdapter` arayüzü ile (S-RDH-01 ile uyumlu) stream edebilme.
5. S-RDH-01 kodunu **DEĞIŞTİRMEDEN**: Mevcut `ReplayBundleAdapter`(single-fixture) koduna dokunmadan, bunu registry üzerinden compose et. S-RDH-01 68/68 test sonucu **BOZULMAMALI**.

## 4. Context
S-RDH-01 tek `ReplayBundleAdapter(fixture_path)` ile tek CSV üzerinde çalışıyor, ancak:
- Eklenen her yeni fixture elle kodlanmak zorunda (düşük ölçeklenebilirlik)
- Hangi fixture’ın neyi kapsadığı (sembol listesi, timeframe, tarih aralığı, satır sayısı, checksum) kayıtlı DEĞIL — run sonu kanıtlamada yetersiz
- Hatalı / değiştirilmiş fixture ile test çalışması detection YOK (fr-007 provenance açığı)
- Birden fazla fixture (ör. happy path + edge caseler) üzerinde tek run yapmak için caller’ın manuel loop yazması gerekir

Bu hikâye E-RDH epic’i devamı niteliğinde; AD-7 (Single Writer Mutation Ownership) gereğince **bundle registry tek yazandır** — diğer modüller (backtest, scanner, paper vs.) sadece `list()`/`get()`/`stream_selected()` okuma API’lerini kullanır, registry state’ini dışarıdan değiştiremez. CAP-1 ve CAP-2 S-RDH-01 tarafından kanıtlanmıştı; bu hikâyede CAP-1/2 korunur ve ek olarak FR-007 (provenance) ile NFR-006 doğrulanır.

**Kesin Sınırlar (Değiştirilemez):**
- Canlı exchange bağlantısı: **YOK**
- API key / credential: **YOK**
- HTTP / WebSocket / exchange SDK çağrısı: **YOK**
- Gerçek order / paper order: **YOK**
- Gerçek para / bakiye / pozisyon: **YOK**
- AI / ML / Strategy / Regime / Risk / Backtest / Portfolio / FastAPI / React / PostgreSQL: **YOK** — bu hikâyenin kapsamı dışındadır.
- **S-RDH-01 KODUNU DEĞIŞTIRME YASAK**: `app/ingest/adapters/replay_bundle_adapter.py`, mevcut `tests/*` — S-RDH-01’e ait dosyalar sadece **OKUNUR**, düzenlenmez.

## 5. Scope
### 5.1 ReplayBundleManifest (Typed Schema)
Her bundle için yan manifest: hangi semboller, hangi timeframe, hangi tarih aralığı, kaç satır, expected row types (candle/tick/trade/OB), integrity checksum (SHA-256 veya stdlib benzeri hash), fixture_path (göreceli), bundle_id, bundle_version, tags (ör. "happy", "edge_stale", "small").
- Stdlib-only yapı: `dataclass` veya `TypedDict`, ek bağımlılık YOK.
- Manifest formatı: tek JSON dosyası veya her CSV yanında `<fixture>.manifest.json` — tercih: merkezi `tests_fixtures/_registry.index.json` + her fixture için yan manifest.

### 5.2 ReplayBundleRegistry (Single Writer, AD-7)
- **Sadece okuma API’leri (public):**
  - `list() -> list[ReplayBundleManifest]`: Tüm kayıtlı bundle’ları dön.
  - `get(bundle_id: str) -> ReplayBundleManifest | None`: id ile al.
  - `find_by(tag: str | None = None, symbol: str | None = None, event_type: str | None = None) -> list[ReplayBundleManifest]`: Filtreli keşif.
  - `get_adapter(bundle_id: str) -> ReplayBundleAdapter`: Tek bundle için S-RDH-01 ReplayBundleAdapter örneği DÖN (constructor’ını çağır, **ReplayBundleAdapter kodunu DEĞIŞTIRME** — kullan).
  - `stream_multiple(bundle_ids: list[str], *, merge_order: str = "timestamp") -> Iterator[RawFrame]`: Birden fazla bundle satırını tek stream’de merge et. Merge kuralı: varsayılan `raw_timestamp` ascending (CSV satır sırasını birinci seviye tut, timestamp ikinci seviye). Eğer fixture içinde timestamp yoksa `_row_index` kullanılır.
- **Validasyon API’leri (sadece registry içinden çağrılır, AD-7):**
  - `validate_integrity(manifest: ReplayBundleManifest) -> IntegrityResult`: (a) dosya var mı, (b) expected satır sayısı eşleşiyor mu, (c) SHA-256 hash eşleşiyor mu, (d) header/kolonlar beklenen şemada mı, (e) sembol/timeframe beyanları ile CSV kolonları arasında tutarlılık var mı. Her biri ayrı doğrulama. Fail → IntegrityResult.passed=False + reasons[] + integrity_fail bayrağı.
  - Integrity FAIL olan bundle: `get_adapter()` çağrıldığında `RegistryIntegrityError` raise eder; `stream_multiple()` içinde atlanır + degrade modda "skip count" alanı sonuçla dönülür.

### 5.3 Fixture Keşif (Auto-Discovery)
- `scan_directory(fixture_dir: Path) -> list[Path]`: Standart `tests_fixtures/` klasörü veya caller tarafından verilen path altında `*.csv` (veya `*.manifest.json`) dosyalarını tarar.
- `register_from_manifest_files(manifest_paths: list[Path])`: Toplu kayıt.
- `auto_register(fixture_dir: Path)`: Manifestleri tara + integrity checkle + kaydet → sonucu döndür.

### 5.4 Provenance: Bundle Bilgisi Envelope’a Sızmaz (CAP-1 Koruması)
- Registry, veri akışında **salt adapter (left-side)** katmanında çalışır; downstream envelope/schema/processing koduna `run_mode` veya `source_type` için yeni branch EKLEMEZ.
- Provenance bilgisi, ReplayBundleAdapter’ın `default_source` alanına (S-RDH-01’de zaten var: `default_source="replay.csv_default"`) bundle_id+version eklemesiyle taşınır: ör. `replay.small_3sym_1h_1m.v1.0.0@sha256:abcd…`. Bu alan envelope’da `source` içinde görünür. **ReplayBundleAdapter constructor argümanı bunu alır ama adapter kodu değiştirilmez — Registry, adapter’ı çağırırken parametreyi geçer.**

### 5.5 Merge Iterator (Multi-Fixture Stream)
- Merge kuralı: (a) her bundle içindeki satırlar **orijinal CSV sırasını korur** (stability), (b) bundle’lar arası `raw_timestamp` alanı varsa UTC parse edilip sıralanır, yoksa `manifest.first_ts` veya `_row_index` sırasına göre naive-order.
- Deterministik: Aynı `bundle_ids` listesi + aynı manifestler → **aynı merged stream satır sırası** (derin-equal 2x run).
- `PublicExchangeAdapter` Protocol ile uyum: Iterator, her satırı RawFrame dict olarak yield eder; `_bundle_id`, `_bundle_row_index`, `_merge_priority` gibi ekstra meta alanlar RawFrame’e eklenebilir (Normalizer bu alanları görürse görmezden gelmeli — ama bu alanlar S-RDH-01 normalizer kodunu bozmamalı, zaten normalizer sadece ihtiyacı olan kolonları seçer. **S-RDH-01 testleri BOZULMAMALI.**).

## 6. Out of Scope
- CANLI BÖLÜMLER: WebSocket Manager, live exchange adapter, REST historical API çağrısı — YOK
- DOĞRULAMA SONRASI MODÜLLER: Feature Engineering (E-FEA), Regime Detector (E-REG), Strategy Engine (E-STR), AI/Scoring (E-AIS), Risk Engine (E-RSK), Backtest Engine (E-BKT), Paper Trading (E-PTR), Portfolio Simulator (E-PTF), Model Registry (E-MDL), Dashboard/API (E-API) — BU HİKÂYEDE YOK
- KALICILIK: PostgreSQL, TimescaleDB, Object Storage — YOK. Sadece filesystem + memory.
- YAPAY ZEKA, GERÇEK EMİR, KULLANICI ARAYÜZÜ — YOK
- **S-RDH-01 KODUNU DÜZENLEME**: 68 mevcut testten herhangi birini etkilememek için S-RDH-01 tarafından oluşturulan dosyalar (app/ingest/adapters/replay_bundle_adapter.py, app/contracts/*.py, app/processing/*.py, app/platform/*.py, tests/unit/*/*.py, tests/integration/*) **OKUNUR, DÜZENLENMEZ**.

## 7. Dependencies
- **Öncül Hikâye:** S-RDH-01 (ReplayBundleAdapter + PublicExchangeAdapter Protocol mevcut — yeniden kullanılacak, adapter koduna dokunulmadan).
- **Kod seviyesinde bağımlılıklar:**
  - `from app.ingest.adapters.base import PublicExchangeAdapter, RawFrame` — var, yeniden kullan.
  - `from app.ingest.adapters.replay_bundle_adapter import ReplayBundleAdapter` — S-RDH-01 kodunu import ET, ama DEĞIŞTİRME. Sadece constructor’ını çağır.
- **External Dependency: YOK** (stdlib-only, hash için `hashlib.sha256`, path için `pathlib`, CSV için `csv`, JSON için `json` — hepsi stdlib).

## 8. Technical Approach
1. **Contract-First Manifest:** İlk adım `ReplayBundleManifest` typed dataclass/TypedDict + `IntegrityResult` tiplerini tanımla. Manifestte alanlar: `bundle_id: str`, `bundle_version: str`, `display_name: str`, `fixture_path: str`, `manifest_path: str | None`, `event_type: str` (candle/tick/trade/ob_snapshot), `symbols: list[str]` (canonical `BASE_QUOTE`), `timeframes: list[str]` (örn `["1m"]`), `expected_rows: int`, `expected_first_ts: Instant`, `expected_last_ts: Instant`, `checksum_sha256: str`, `tags: list[str]`, `registered_at: Instant`, `notes: str | None`.
2. **AD-7 Single Writer Enforcement:**
   - `ReplayBundleRegistry.__init__(fixture_dir, manifest_paths)` dışında **public setters YOK**.
   - Private `_register_internal()` tarafından state set edilir. Diğer sınıflar `list/get/stream_selected` dışında metot çağıramaz.
   - State mutation testi: `_register_internal()` dışında API çağrıları → registry nesnesinin state’inde değişiklik YOK (unit test ile assert).
3. **Integrity Check (5 ayrı doğrulama):**
   - (I1) `fixture_path` mevcut dosya mı?
   - (I2) `expected_rows == actual rows (csv.DictReader ile say)`
   - (I3) `checksum_sha256 == actual sha256 (fixture dosyasının bytes hash’i)`
   - (I4) Header schema: CSV başlığında gerekli kolonlar (raw_symbol, raw_timestamp, open/high/low/close/volume en az biri veya event_type’a göre) mevcut mu?
   - (I5) Beyazlistedeki semboller ile CSV’de geçen raw_symbol sayısı tutarlı mı? (Örn 3 sembol beyan, CSV’de sadece 2 → warning I5; ama integrity fail değil, sadece degrade warning.)
   - Her doğrulama ayrı reason kodu: `I1_FILE_MISSING`, `I2_ROWCOUNT_MISMATCH`, `I3_CHECKSUM_MISMATCH`, `I4_HEADER_MISMATCH`, `I5_SYMBOL_COVERAGE_WEAK`. Başarısızlıkların 3’ü (I1/I2/I3) **hard-fail** → kullanım dışı; I4/I5 **soft-warn** → kullanılabilir ama reasons[] listelenir + `degraded=true` integrity sonucu.
4. **Reuse S-RDH-01 Adapter (NO EDIT):** `get_adapter(bundle_id)` → `ReplayBundleAdapter(fixture_path=manifest.fixture_path, default_source=f"replay.{manifest.bundle_id}.{manifest.bundle_version}@sha256:{manifest.checksum_sha256[:12]}")` çağrısı ve return; adapter koduna dokunma.
5. **Multi-Bundle Merge Iterator:**
   - `stream_multiple()` → her bundle için `adapter.stream_market_events()` çağır → her birinin iterator’unu heapq.merge benzeri stdlib ile timestamp-ordered merge et.
   - Key fonksiyonu: `parse_timestamp_or_rowindex(raw_frame)` — önce `raw_timestamp` parse etmeyi dene, başarısız veya yoksa `(_bundle_id, _row_index)` tuple kullan.
   - Kararlılık (stable sort): Eşit timestamp/rowindex’li satırlar, bundle listesindeki orijinal sıra ile gelir.
6. **Determinism Guarantee:** Aynı manifestler + aynı fixture dosyaları 2 kez → (a) `list()` çıktısı aynı sıra (sorted by bundle_id), (b) `stream_multiple` çıktısı aynı satır sırası 2x run arası derin eşitlik.
7. **Provenance Link (FR-007 / NFR-006):** Merge iterator, her RawFrame’e `_provenance_bundle_id`, `_provenance_checksum_prefix`, `_provenance_version` extra alanları ekler. Bu alanlar S-RDH-01 Normalizer’da "extra"nın bir parçası olarak zarfın `extra` objesinde tutulabilir (Normalizer zaten `_row_index` gibi ekstra kolonları nasıl ele alıyorsa aynı davranış — **testlerle doğrula, S-RDH-01’i bozmuyorsun.**).
8. **Network Safety & Credential Safety:** S-RDH-01 conftest’i (offline_network_blocker) + static scan testleri bu hikâye testleri tarafından da çalıştırılmalıdır; S-RDH-02 kod tabanında `api_key/secret/BINANCE_*` stringleri 0 match olmalıdır.

## 9. Files/Modules Expected to Be Created (YENİ DOSYALAR — S-RDH-01 DOSYALARI DÜZENLENMEZ)
```
app/
  ingest/
    registry/
      __init__.py                     # Public API export: ReplayBundleRegistry, ReplayBundleManifest, IntegrityResult
      manifest.py                     # ReplayBundleManifest, IntegrityResult typed schemas (dataclass)
      bundle_registry.py              # ReplayBundleRegistry (single writer, list/get/find/get_adapter/stream_multiple/validate_integrity/auto_register)
      manifest_builder.py             # Helpers: generate manifest from CSV (fixture → manifest), compute checksum_sha256
      merge_iterator.py               # stream_multiple: timestamp-ordered deterministic merge N adapter iterators → RawFrames
tests/
  unit/
    ingest/
      registry/
        __init__.py
        test_manifest_schema.py       # ReplayBundleManifest alanları + contract_version zorunluluğu
        test_integrity_checks.py      # 5 ayrı integrity test (I1/I2/I3/I4/I5), her biri için ayrı negatif case
        test_registry_api.py          # list/get/find/auto_register — 7 adet mevcut CSV + yan manifestleriyle çalışma
        test_get_adapter_no_edit.py   # get_adapter() çağrınca, S-RDH-01 ReplayBundleAdapter örneği dönmesi + source string doğru
        test_stream_multiple_deterministic.py  # 2x run merge stream derin eşitlik
        test_merge_order.py           # timestamp-order merge 3 farklı bundle üzerinde doğru
        test_ad7_single_writer.py     # API dışında registry state değişmez (mutation isolation — AD-7)
  integration/
    test_srdh02_full_registry_flow.py # Fixture dizini auto_register → 7 manifest integrity PASS → 2 bundle merge stream
    test_srdh02_provenance_in_envelope.py # merge stream 2 bundle → adapter → srdh01 normalizer kullan envelope üret; envelope.source + extra._provenance_* alanları var
    test_srdh02_integrity_fail_closed.py # checksum bilerek bozulmuş CSV → integrity fail → adapter raise, stream_multiple içinde atlanır
  replay/
    test_registry_determinism_10x.py  # Aynı fixtures 10 kez auto_register + stream_multiple; her seferinde aynı sıra/satır (marker=replay)
  failure/
    test_registry_network_safety.py   # registry testleri, conftest network blocker açıkken PASS
    test_registry_no_credentials.py   # app/ingest/registry/*.py + testleri için api_key/secret taraması 0 match (marker=failure_injection)
  contracts/
    test_srdh02_contracts.py          # Marker=contract: manifest şeması, get_adapter Protocol uyumluluğu, PublicExchangeAdapter.merge çalışan interface
tests_fixtures/
  _registry.index.json                # Otomatik oluşturulur (veya elle yazılır — build aracı): 7 CSV için manifest listesi
  <her-fixture>.manifest.json         # Her CSV için manifest. small_3sym_1h_1m_candles.manifest.json, edge_stale.manifest.json …
```

## 10. Acceptance Criteria

### 10.1 Registry + Manifest Contract AC
- **AC-01:** `ReplayBundleManifest` dataclass alanları tam olarak §5.1/§8.1’de belirtilen 13 alanı (bundle_id, bundle_version, display_name, fixture_path, event_type, symbols, timeframes, expected_rows, expected_first_ts, expected_last_ts, checksum_sha256, tags, registered_at) taşır; eksik alan → ValidationError (veya dataclass field required).
- **AC-02:** `tests_fixtures/` altında 7 adet CSV dosyası için `auto_register(tests_fixtures)` çağrıldığında → `registry.list()` sonucunda **7 manifest** kayıtlıdır; her biri için `bundle_id` benzersizdir.
- **AC-03:** `find_by(tag="edge")` çağrıldığında → `edge_*.csv` manifest sayısı 6’dır (small hariç).

### 10.2 Integrity Checks (5 ayrı doğrulama, her biri ayrı test)
- **AC-04 (I1 dosya yok):** fixture_path bozuk bir manifest → validate_integrity sonucu `passed=False` ve reason kodu `I1_FILE_MISSING`.
- **AC-05 (I2 satır sayısı):** `expected_rows` 180 yazılmış ama dosyada 179 satır → `I2_ROWCOUNT_MISMATCH`.
- **AC-06 (I3 checksum):** checksum wrong (gerçek hesaplanan bilerek değiştirilmiş manifest) → `I3_CHECKSUM_MISMATCH`.
- **AC-07 (I4 header):** CSV başlığında `raw_timestamp` kolon eksik → `I4_HEADER_MISMATCH`.
- **AC-08 (I5 sembol coverage):** Manifest symbols=["BTC_USDT","ETH_USDT","SOL_USDT"] ama CSV’de sadece ilk 2 sembol → integrity `degraded=true`, reason code `I5_SYMBOL_COVERAGE_WEAK` ama hard-fail DEĞİL (passed=true, degraded=true).
- **AC-09 (Fail-closed hard-fail):** I1/I2/I3 hard-fail olan manifestler → `registry.get_adapter(bundle_id)` çağrıldığında **`RegistryIntegrityError` raise eder**; kullanılamaz.
- **AC-10 (Soft-warn pass):** Sadece I4/I5 içeren manifestler → adapter alınabilir ama `validate_integrity().reasons` listesinde I4/I5 nedenleri döner.

### 10.3 Adapter Reuse & Multi-Bundle Stream (S-RDH-01 KOdu DEĞİŞMEDEN)
- **AC-11 (Adapter Reuse — No Edit):** `registry.get_adapter("small_3sym_1h_1m_candles.v1")` çağrısı → dönen nesnenin tipi `ReplayBundleAdapter` S-RDH-01 sınıfıdır; `type(result).__name__ == "ReplayBundleAdapter"` ve `hasattr(result, "stream_market_events")` == True. **S-RDH-01 source dosyası editlenmez.**
- **AC-12 (Source string includes provenance):** Dönen adapter’in `default_source` değeri `"replay.{bundle_id}.{version}@sha256:{hash_prefix}"` formatında; bundle_id ve version içerir.
- **AC-13 (Multi-Bundle merge N=2):** 2 farklı bundle id (small + edge_stale) listesiyle `stream_multiple([id1, id2])` → toplam satır sayısı = `(expected_rows1 + expected_rows2)`. Her satırın `_bundle_id` alanı doğru bundle’ı gösterir.
- **AC-14 (Merge sıralaması doğru):** Bundle A ts:10:00-10:10, Bundle B ts:09:55-10:05 → merged stream’de ilk satırlar Bundle B’den (09:55) başlar; timestamp azalan sıra YOK.
- **AC-15 (Determinizm 2x run):** Aynı `bundle_ids` ile `stream_multiple` 2 kez çalıştırıldığında → ortaya çıkan RawFrame listeleri (timestamps, semboller, _row_index, _bundle_id bazında) **derin eşitlik** (deep equality) ile eşleşir.

### 10.4 AD-7 Single Writer Mutation Ownership
- **AC-16 (Public API read-only):** Registry’nin public metotları (list/get/find/get_adapter/stream_multiple/validate_integrity) **hiçbirisi** registry’nin internal manifest listesini (self._manifests dict’i) değiştirmez. Unit test: test önce `len(registry.list())` = 7 kaydeder; sonra her public metodu çağırır; sonra tekrar list() → hala 7 (ekleme/silme YOK).
- **AC-17 (Sadece init + private register_internal mutate):** Tek mutation yolu `__init__` (veya private `_register_internal`). Registry, kullanıcı tarafından public API üzerinden manifest ekleme/silme/upgrade yapmasına izin VERMEZ. Yeni manifest ancak `auto_register` ile inited sırasında eklenir (constructor-time init), immutable snapshot olarak tutulur (read-only frozen dict benzeri).

### 10.5 Provenance Envelope (FR-007 / NFR-006)
- **AC-18:** Multi-bundle stream’den 2 farklı bundle’dan alınan RawFrame’ler, S-RDH-01 mevcut Normalizer üzerinden geçirildiğinde — her bir envelope’ın `source` stringi **farklı bundle_id içerir** (aynı değil); provenance ayrımı doğru.
- **AC-19:** Envelope’ın `extra` dicti (veya doğrudan zarf meta alanlarından uygun olan) `_provenance_bundle_id` ve `_provenance_checksum_prefix` anahtarlarını içerir; downstream (ileride backtest) bu alanları okuyarak hangi fixture sürümüyle çalıştığını kaydedebilir.

### 10.6 Network / Safety AC
- **AC-20 (Offline Guarantee):** Tüm S-RDH-02 testleri, `tests/conftest.py:offline_network_blocker` (S-RDH-01 conftest) aktifken PASS’tır; hiçbir socket/HTTP çağrısı gerçekleşmez.
- **AC-21 (No Credentials):** `app/ingest/registry/` ve `tests/unit/ingest/registry/` + `tests/integration/test_srdh02_*` dosyaları static tarandığında `"api_key"`, `"secret"`, `"BINANCE_API_KEY"`, `"OKX_KEY"` — hiçbiri bulunmaz (count=0).
- **AC-22 (No Real Orders):** Registry klasöründe `send_real_order`, `place_exchange_order`, `live_execution` gibi isimde fonksiyon/modül YOKTUR.

### 10.7 CAP Proof (Koruma — S-RDH-01 CAP’ları BOZULMAMALI)
- **AC-23 (CAP-1 Koruması — 0 yeni branch):** `app/contracts`, `app/processing`, `app/platform`, domain katmanlarında ve **hatta `app/ingest/registry/` içinde** bile — `run_mode` veya `source_type` içeren `if/elif` koşulları **static AST/regex taraması ile 0’dır**. Yeni branch eklenmemiştir; sadece adapter/registry layer’ında source stringi güncellenmiştir. S-RDH-01 test_suite’i 68/68 PASS olmalıdır S-RDH-02 sonrası (bozulma YOK).
- **AC-24 (CAP-2 Koruması):** Multi-bundle stream + normalizer sonrası her envelope, 7 quality_flags boolean’inin HEPSİNİ taşır; registry, quality_flags yapısını **değiştirmez veya silmez.**

## 11. Contract References
| Sözleşme | Kısım | Hangi AC’ler |
|---|---|---|
| CONTRACTS.md §0 Ortak tipler | Instant, Symbol, ContractVersion, SourceType | AC-01, AC-03, AC-12, AC-18 |
| CONTRACTS.md §1 Envelope | source, correlation, extra alanları | AC-18, AC-19, AC-24 |
| CONTRACTS.md §2 QualityFlags + CAP-2 | 7 bayrak değişmez, registry onları bozmaz | AC-24 |
| CONTRACTS.md §3.5 Candle + 3.1-3.4 Market payloads | EventType fixture içeriği | AC-01, AC-07, AC-13 |
| CONTRACTS.md §4 Data Flow I/O | Adapter → Normalizer → Validator | AC-11, AC-18, AC-19 |
| CONTRACTS.md §5 Live/Replay Parity (CAP-1) | 0 run_mode branch zorlaması | AC-23 |
| SPEC.md § CAP-1 | Domain branch yok, adapter farklılaşır | AC-23 |
| SPEC.md § CAP-2 | Kalite bayrakları envelope içindedir | AC-24 |
| SPEC.md Constraints | Stdlib-only, timestamp Z, Decimal, corr/caus zorunlu | Bütün AC’ler |
| PRD FR-007 / NFR-006 | Provenance linking + raw provenance kaydı | AC-12, AC-18, AC-19 |
| PRD FR-003 | Replay/historical data first-class | Scope + tüm AC |
| EPICS.md Appendix B — Sıra 10 | S-RDH-02 Hemen S-RDH-01 sonrası | Hikâye bağımlılığı |

## 12. Architecture Decision References
| AD | Uygulama Şekli / Nasıl Korunuyor | Hikâyedeki Testleri |
|---|---|---|
| **AD-2 (Exchange Boundary)** | Registry davranışı, `ReplayBundleAdapter` port’u arkasında; raw frame’ler sadece Normalizer. | AC-11, AC-12 |
| **AD-3 (Canonical Envelope)** | Provenance bilgisi envelope.extra veya source içine taşınır; envelope şeması DEĞİŞMEZ (sadece extend edilen extra) | AC-18, AC-19 |
| **AD-4 (Live/Replay Parity) — CAP-1** | Domainde yeni run_mode/source_type branch YOK; sadece adapter source stringi değişir. | AC-23 (static scan 0 branch) |
| **AD-5 (Data Quality Hard Gate)** | Registry integrity FAIL → adapter fail-closed (RegistryIntegrityError); NİTEKİ bozuk veriyle çalışılmaz (AD-5 çerçevesinde). | AC-09 |
| **AD-6 (Internal Bus First)** | Bu hikâyede bus yoktur; ama registry’nin çıktısı S-RDH-01 bus’yla %100 uyumlu (RawFrame’ler → Normalizer). | AC-18, AC-19 |
| **AD-7 (Single Writer Mutation Ownership)** | **Bu hikâyenin KÖK konusu:** Registry tek yazandır; diğer modüller sadece read API kullanır. Public API’ler state mutate etmez. | AC-16, AC-17 (iki test) |
| **AD-12 (Paper vs Live Ayrımı)** | Paper execution YOK; sadece replay fixture + registry. | AC-22 no-real-order |
| **AD-17 (Correlation Observability)** | Provenance alanları ile her zarf hangi bundle sürümü ile çalıştığını söyler; ileride log correlation. | AC-18, AC-19 |
| **AD-19 (Failure Default Safe)** | Integrity check I1/I2/I3 FAIL → bundle kullanım dışı, stream atlar, neden raporlanır; sessiz bozulma YOK. | AC-04..AC-09 |
| **AD-20 (Testability)** | Unit (9) + Integration (3) + Replay (1) + Failure (2) + Contract (1) — TOPLAM >=16 yeni test; S-RDH-01 68 testiyle BIRLIKTE çalışmalı. | Tüm test planı §14 |

## 13. CAP References
| CAP | Intent | Bu Hikâyede Nasıl Korunur / Pekiştirilir | Test Doğrulaması |
|---|---|---|---|
| **CAP-1 (Parity)** | Domain kodu mod değiştirmez; sadece adapter katmanı. | Registry adapter katmanında çalışır; **domain klasörlerinde 0 yeni run_mode/source_type branch.** S-RDH-01 test_suite 68/68 tekrar çalıştırılmalı. | `test_cap1_live_replay_parity.py` S-RDH-01’den DEĞİŞTİRİLMEDEN çalışır + AC-23 |
| **CAP-2 (Quality in Envelope)** | Kalite bayrakları zarf içinde taşınır. | Registry, QualityFlags yapısına dokunmaz; 7 bayrak aynen korunur. Yeni bayrak EKLEMEZ. | AC-24 + S-RDH-02 testi flags yapısı değişmediğini assert |
| CAP-3/4/5/6 | Bu hikâyede doğrudan kanıtlanmaz; hazırlık yapılır. | İlerideki hikâyeler (S-STR-03, S-RSK-02, S-MDL-05, S-API-03) tarafından kanıtlanır. | — |

## 14. Test Plan
**Minimum 16 yeni test (Unit 7 + Integration 3 + Replay 1 + Failure 2 + Contract 1 + Regression 2).**
S-RDH-01 kodunun düzenlenmemesi nedeniyle S-RDH-01 68 testi BOZULMAMALI — son test toplamı ≥ 84.

### Kategori A: Unit Tests (9)
| # | Test | AC |
|---|---|---|
| A1 | Manifest schema: eksik checksum_sha256 → ValidationError / Required Field Hatası | AC-01 |
| A2 | auto_register tests_fixtures/ dizini: list() uzunluğu 7 → 7 manifest | AC-02 |
| A3 | find_by(tag="edge") → 6 result; find_by(symbol="BTC_USDT") → ≥1 small dahil | AC-03 |
| A4 | Integrity I1_FILE_MISSING: bozuk path → passed=False + reason=I1 | AC-04 |
| A5 | Integrity I2_ROWCOUNT_MISMATCH: expected_rows 180 ama dosya 179 → I2 fail | AC-05 |
| A6 | Integrity I3_CHECKSUM_MISMATCH: checksum değiştirilmiş manifest → I3 fail + RegistryIntegrityError adapter’da | AC-06 + AC-09 |
| A7 | Integrity I4_HEADER_MISMATCH: raw_timestamp kolon eksik CSV → I4 degrade true | AC-07 |
| A8 | Integrity I5_SYMBOL_COVERAGE_WEAK: manifest 3 sembol, CSV 2 → I5 warning degrade true (not hard fail) | AC-08, AC-10 |
| A9 | **AD-7 Public API mutation yok:** list/get/find/validate çağırdıktan sonra self._manifests uzunluğu aynı → AC-16 | AC-16 |
| A10 | AD-7 Private immutable: registry._manifests Read-only (örnek: MappingProxyType veya benzeri kullanılırsa) → dışarıdan key seti AttributeError | AC-17 |
| A11 | get_adapter: dönen nesne `isinstance` ReplayBundleAdapter (S-RDH-01 import) → TRUE; source string bundle_id+version içerir | AC-11, AC-12 |
| A12 | stream_multiple 2 bundle merge: toplam expected_rows = beklenen toplam; her RawFrame `_bundle_id` anahtarı içeriyor | AC-13 |

### Kategori B: Integration Tests (3)
| # | Test | AC |
|---|---|---|
| B1 | Full Flow: auto_register → integrity 7 PASS → get_adapter small → stream 180 satır; sonra stream 2 bundle → merge satır sayısı doğruluğu. | AC-02, AC-13, AC-09 |
| B2 | Integrity fail-closed: küçük bozuk checksumlu 1 adet sentetik CSV + manifest yaz; registry auto_register → integrity FAIL → `stream_multiple([id_bozuk, id_küçük])` içinde bozuk ATLANIR, küçük çalışır; sonuç skip sayısı = 1 bundle, error reasons list döner. | AC-09 |
| B3 | Provenance End-to-End: merge stream → S-RDH-01 Normalizer → Envelope; envelope.source iki bundle için farklı; envelope.extra._provenance_bundle_id == bundle_id. | AC-18, AC-19 |

### Kategori C: Determinism / Replay Tests (1 marker=replay)
| # | Test | AC |
|---|---|---|
| C1 | **10× run determinizm test:** Aynı 7 fixtures + registry auto_register + stream_multiple([small, edge_duplicate, edge_missing]) → her 10 koşuda merged list (index, symbol, ts, _bundle_id, _row_index) **derin eşitlik** ile aynı; ilk 100 satır assert. | AC-15 |

### Kategori D: Failure / Safety Tests (2 marker=failure_injection)
| # | Test | AC |
|---|---|---|
| D1 | offline_network_blocker aktifken registry unit/integration testlerinin HEPSİ çalışıyor → PASS (socket çağrısı 0). | AC-20 |
| D2 | Static scan: `app/ingest/registry/`, `tests/*/test_srdh02_*`, `tests/*/registry/` altında "api_key" / "secret" / "BINANCE_*" / "OKX_KEY" regex case-insensitive → 0 match. İsim taraması: `send_real_order` benzeri → 0 match. | AC-21, AC-22 |

### Kategori E: Contract Marker Tests (1 marker=contract)
| # | Test | AC |
|---|---|---|
| E1 | PublicExchangeAdapter Protocol Compliance: registry.get_adapter(id) dönen nesne + `stream_multiple` sonucu custom adapter sarmalayıcısı → her ikisi de `isinstance(p, PublicExchangeAdapter)` veya isinstance checkli Protocol testi → TRUE. `hasattr(stream_market_events)` + Iterator[RawFrame] dönüş tipi uyumu. | AC-11, AC-13 |

### Kategori F: Regression Protection (2)
| # | Test | AC |
|---|---|---|
| F1 | **KRİTİK — S-RDH-01 68 test BOZULMAMALI:** Tüm `pytest tests -q` çalıştır. S-RDH-02 eklendikten SONRA bile S-RDH-01 68/68 PASS’tir; hiçbir test FAIL olmaz (regression yok). | AC-23, GLOBAL |
| F2 | **KRİTİK — S-RDH-01 Kod Doku:** `app/ingest/adapters/replay_bundle_adapter.py`, `app/processing/quality_monitor.py`, `app/contracts/canonical.py`, `tests/integration/test_pipeline_happy_path.py` gibi S-RDH-01 tarafından yaratılan **dosyaların hiçbirinin satır sayısı veya byte boyutu değiştirilmemiş** (static check: importlib.metadata benzeri değil, basit: sha256(self, before) == (after, known hash from S-RDH-01 test)). Bu test, öykü boyunca dokunulmama kuralını enforce eder. | GLOBAL "S-RDH-01 KODUNU DEĞIŞTIRME" |

## 15. Definition of Done (DoD) — Zorunlu 12 Madde
1. ✅ **AC-01 → AC-24, 24 kabul kriterinin HEPSİ testlerle KANITLANMIŞTIR.**
2. ✅ **Integrity 5 ayrı test**: I1/I2/I3 hard-fail → adapter + stream içinde fail-closed. I4/I5 degrade warning. (A4-A8)
3. ✅ **AD-7 Single Writer**: Public API’ler state mutate etmez; sadece constructor (veya private _register_internal) manifestleri ayarlar. (A9, A10)
4. ✅ **S-RDH-01 Koduna DOKUNULMADI:** Regression F2 test PASS — S-RDH-01 dosyalarının sha256 hashleri bilinen halleriyle aynı.
5. ✅ **S-RDH-01 Testleri 68/68 Hala GEÇİYOR:** Regression F1. S-RDH-02’den sonra toplam test ≥ 84; S-RDH-01 sayısı azalma YOK.
6. ✅ **CAP-1 Koruması:** Domain klasörlerinde 0 yeni `if run_mode` / `if source_type` branch. AC-23 static scan.
7. ✅ **CAP-2 Koruması:** QualityFlags 7 bayrak değişmemiş. Multi-bundle stream sonrası her envelope 7 boolean’ı taşıyor.
8. ✅ **Provenance Working (FR-007 / NFR-006):** Envelope source string + extra._provenance_* alanları doğru bundle_id + version + checksum içeriyor.
9. ✅ **Deterministik:** Aynı fixtures ile 2 kez stream_multiple → derin eşitlik. 10× run testi (C1) PASS.
10. ✅ **Offline & No Credentials:** Network blocker test D1 PASS. Static scan credentials D2 0 match.
11. ✅ **Stdlib-Only:** `pyproject.toml` dependencies=[]. Yeni runtime bağımlılığı EKLENMEDİ. hash, csv, json, pathlib, dataclass, heapq → hepsi stdlib.
12. ✅ **Toplam Yeni Test Sayısı ≥ 16 (Unit ≥9, Integration ≥3, Replay ≥1, Failure ≥2, Contract ≥1, Regression ≥2).** Test coverage `app/ingest/registry/` için ≥ %85.

---

## Developer Notes (Önemli Uygulama Rehberi)
1. **İlk kural: 2 kez düşün, 0 kez S-RDH-01 koduna dokun.** S-RDH-01 dosyalarını Read-Only davran. Hiçbir Edit kullanma; sadece import et.
2. Manifest hash’i için `hashlib.sha256(Path(fixture_path).read_bytes()).hexdigest()` yeter; büyük dosyalarda streaming hash gerekirse `chunk_size=65536` ile — ama şimdiki test fixtures 180 satır, okunması kolay.
3. Merge Iterator için stdlib `heapq.merge(key=...)` kullanabilirsin. Her bundle iterator’u `(sort_key, bundle_priority_int, raw_frame)` tuple üreten bir wrapper generator ile sar → heapq.merge doğru ve stabil (aynı key’lerde bundle_priority_int ilk geldiği gibi).
4. Registry’nin manifest dict’ini `types.MappingProxyType(self._manifests_internal)` ile dışarı ver → public read API’ler döndüğünde kullanıcılar dict setitem denerse TypeError. AD-7 enforcement: tek satır.
5. Integrity I5 sembol coverage: Önce CSV’de geçen raw_symbol’leri unique topla, sonra canonical çevir (S-RDH-01 normalizer symbol helper’ını kullanabilirsin — eğer import edip fonsiyonu çağırmak mevcut kodu bozmuyorsa **evet, kullan; ama fonksiyonu düzenle YOK.**); eğer helper public değilse — S-RDH-02 içinde kopya alma, aynı regex/transformu minimal yaz.
6. Auto_register manifest builder her CSV için tek sefer manifest üretir; testler başlamadan önce build manifest tool çalıştırılır (test fixture setup) ya da ilk testin setup phase’ında — test setup içinde fixtures/_registry.index.json in-memory oluşturulabilir veya dosyaya yazılabilir.
7. **Bağımsız test çalıştırma:** `pytest tests/unit/ingest/registry tests/integration/test_srdh02_* tests/replay/test_registry_determinism_10x.py tests/failure/test_registry_* tests/contracts/test_srdh02_contracts.py -v` PASS olmalı.
8. **Regresyon koruması (KRİTİK):** `pytest tests -q` ile S-RDH-01 68 + S-RDH-02 ~16 = ≥84 testin HEPSİ GEÇMELİ.
9. Python typing zorunlu: Bütün public fonksiyon/method → type annotations.
10. pytest markers: Her test dosyası başına `pytest.mark.<contract|failure_injection|replay>` marker’larını kullan; pyproject.toml’daki markers listesini **genişletme (yeni marker gerekirse ama mevcut 3 marker yeter).**

## Proje Yapısı Notları (AD-1 Uyumu)
- Yeni klasör: `app/ingest/registry/` — AD-2 adapter ingest bounded context altında yer alır. doğru.
- Yeni test klasör: `tests/unit/ingest/registry/` — mevcut `tests/unit/ingest/` altında `test_replay_bundle_adapter.py` dosyası yanında; AD-1 uyumlu.
- S-RDH-01 ile çakışma YOK. Registry, ReplayBundleAdapter’ı import eder, çağırır — ama onu değiştirmez.
- `tests_fixtures/` altında manifest JSON dosyaları: Fixture data yanında metadata; Yeni CSV eklendiğinde manifest üretmek tek adım.

## S-RDH-01 Dev Sonrası Öğrenilenler (Önceki Hikâye İstihbaratı)
1. **S-RDH-01 için UUID determinizm:** uuid5(namespace, f"evt-{n}") closure kullanılmış — bu model, S-RDH-02 determinizm test C1’le tam uyumlu; aynen çalışır.
2. **EventBus publish():** Sadece tek arg (envelope). Registry, bus’a doğrudan erişmez; sadece adapter + raw_frame üretir. Uyumlu.
3. **Quality Monitor state update order:** S-RDH-01 sonunda state’i güncelleme sırası düzeltilmiş — S-RDH-02 validation quality monitor’ünü etkilemez.
4. **Static scan false-positive exclusion pattern:** test_no_credentials.py kendi kendini taramaması için exclude path listesi var; S-RDH-02 failure test D2 bunu dikkate almalı (kendini taramayı atla).
5. **Stdlib-only kesin kural:** pydantic v2 kullanma YOK (daha önce pyproject runtime bağımlılığı boş olduğu için); dataclass + kendi doğrulama yeter.
6. **Tight 1s stale threshold override:** Edge testlerde bu pattern kullanılmış — S-RDH-02 integrity testlerinde de aynı pattern: bilerek bozulmuş fixtures üret, fail-closed assert et.

## References
- [S-RDH-01 story](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/S-RDH-01-replay-data-pipeline-poc.md) — Reuse edilen ReplayBundleAdapter + contract yapısı
- [EPICS.md](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L313-L392) — E-RDH epic
- [ARCHITECTURE-SPINE.md AD-7](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L110-L115) — Single Writer
- [CONTRACTS.md §0-§5](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/CONTRACTS.md#L12-L218) — Ortak tipler + CAP-1/2
- [SPEC.md CAP-1/2](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/SPEC.md#L31-L52) — Capability tanımları

---

## Dev Agent Record
### Agent Model Used
<!-- doldurulacak (implementation dev-story sırasında) -->

### Debug Log References
<!-- doldurulacak -->

### Completion Notes List
<!-- doldurulacak -->

### File List
<!-- implementation sonrası doldurulacak. Şu anki saf create-story sonrası:

YENİ OLUŞTURULACAK DOSYALAR (implementation aşamasında):
  app/ingest/registry/__init__.py
  app/ingest/registry/manifest.py
  app/ingest/registry/bundle_registry.py
  app/ingest/registry/manifest_builder.py
  app/ingest/registry/merge_iterator.py
  tests/unit/ingest/registry/__init__.py + 7 unit test dosyası
  tests/integration/test_srdh02_full_registry_flow.py
  tests/integration/test_srdh02_provenance_in_envelope.py
  tests/integration/test_srdh02_integrity_fail_closed.py
  tests/replay/test_registry_determinism_10x.py
  tests/failure/test_registry_network_safety.py
  tests/failure/test_registry_no_credentials.py
  tests/contracts/test_srdh02_contracts.py
  tests_fixtures/_registry.index.json
  tests_fixtures/*.manifest.json (7 adet)
-->
