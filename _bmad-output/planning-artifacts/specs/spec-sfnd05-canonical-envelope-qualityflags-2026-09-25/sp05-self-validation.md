# SP05 Self-Validation — S-FND-05 (Spec Law 1-8)

SELF-SWEEP: 2 pass (Coherence 1-6,8 + Preservation 7) → PASS/FAIL.

## Pass 1: Coherence (Spec Law 1-6 + 8)

| Law # | Kural | S-FND-05 Karşılığı | Sonuç |
|---|---|---|---|
| **Law 1** | Her capability BOTH intent AND success. | 5 Capability (CAP-ENVELOPE-01/02, CAP-QUALITY-01/02, CAP-PARITY-01) → HEPSİ için "intent + success" ayrı ayrı yazıldı. SPEC §2 Measurable Success her biri için test-kriter. | ✅ PASS (5/5 both intent+success) |
| **Law 2** | WHAT not HOW. | SPEC: frozen dataclass, type-gate, validation. HİÇBİRİ: "class MySchema(BaseModel)" YADA "pydantic v2 kullan" (HOW). Sadece OD-05-01 default stdlib — selection mechanism açık karar, değil implementation kuralı. Sadece WHAT: alanlar, tipler, invariants, test-kriter. | ✅ PASS. WHAT. Tüm HOW OD-05-01 açık karar. |
| **Law 3** | Constraints GERÇEKTEN design kararını büker. (Constraints herhangi bir şeyi rule-out etmiyorsa süslü.) | Hard-Red 13 (8 proje + 5 hikâye özel). İnvariants: degraded=any(other) zorunlu. Instant UTC Z zorunlu. replay_clock NONE + replay SOURCE = FAIL. Bunlar tasarım alanını GERÇEKTEN daraltır (örn. instant offsetli → tasarım dışı). PyYAML Closed Permanent: tüm YAML çözümleri dışarıda bırakır. | ✅ PASS. HRC + invariants constraint daraltıyor. |
| **Law 4** | Non-goals AÇIK, en az 1 tane. | Non-goals 12 tane (NG-01..NG-12): "19 payload schema, flat-dict AD-22, parity tarayıcı, CAP-3/4/5/6, ULID üretim, serialization, bus, AD-5 logic, pydantic seçimi, PyYAML format" — AÇIKÇA dışarıda. | ✅ PASS (12 explicit non-goals) |
| **Law 5** | Success signal T-est edilebilir / gösterilebilir. | 18/18 AC (TP-01..09). Determinizm len(set(10)) == 1 ölçülebilir. HRC scan count 0 ölçülebilir. Contract version alignment VersionConstants.contract_version == envelope.contract_version test edilebilir. | ✅ PASS. 18 AC executable. |
| **Law 6** | Capability IDs stabil / benzersiz, hiçbiri yeniden kullanılmaz, boşluk yok. | 5 Kapasite: `CAP-ENVELOPE-01 / -02, CAP-QUALITY-01 / -02, CAP-PARITY-01` benzersiz, stabil, tekrar kullanılmamış. Gelecek CAP'lar artan numara. `CAP-*` ID'ler E-CON upstream CAP-1/2/3/4/5/6 ile çakışmaz, çünkü `CAP-ENVELOPE-XX` prefix. Çakışma 0. | ✅ PASS. 5 unique. Prefix çakışma 0. |
| (Law 7 Pass-2'de) | Preservation — source claims SPEC.md veya companion içine düşer. | See Pass 2. | → Pass 2 |
| **Law 8** | Lean prose. Sadece yük-taşıyan cümle. | Kısaltmalar: her section Load-bearing; Non-goals explicit, 12 tane, her biri 1 satır. Success signal 18 AC, her biri 1 satır. Tüyolar ("Great!" gibi) 0 cümle. SPEC.md 20 section, her biri sadece zorunlu + sözleşme tabloları (16 alan × 6 sütun). | ✅ PASS. Lean. |

## Pass 2: Preservation (Law 7)

Kaynak claim'leri (CONTRACTS §1 22 satır, §2 7 bayrak, PRD FR-001..007, AD-3/4/5/17/19/20, EPICS E-CON S-CON-01 AC'leri) → SPEC/companion içinde DÜŞTÜ MÜ?

| Kaynak Claim (Load-Bearing) | Hangi SPEC/Companion bölümünde düştü? | DÜŞTÜ (Y/N) |
|---|---|---|
| CONTRACTS §1 14/16 alan isimleri + tipleri + Zorunlu/Kural tablosu L33-L48 | SPEC §6.2 16 Alan × 6 sütun tablo | ✅ Y |
| CONTRACTS §0 L15 Instant ISO-8601 UTC, 3 haneli ms "örnek" + Z dilim ZORUNLU | SPEC §6.1 Instant regex; AC-07/08/09; FC-02; GAP-03 default toler MS opsiyonel | ✅ Y (tolerance ADN) |
| CONTRACTS §2 QualityFlags L56-70 7 bool + degraded any invariant + reasons | SPEC §6.3 + FC-06 + TP-06 (AC 12-14) | ✅ Y |
| PRD §5.1 FR-005: stale/duplicate/gaps surface et. Bayraklar görünür. | CAP-QUALITY-02 (downstream consumption without validator RPC → CAP-2 bridge) SPEC §1 Intent AD-5. | ✅ Y |
| AD-3 CanonicalEventEnvelope zorunluluğu, her event aynı zarf | SPEC §1 Intent; §2 Success T-01/T-02 import test; §6.2 14 zorunlu + 2 opsiyonel = 16 alan. | ✅ Y |
| AD-4 Live/Replay Parity (aynı contract, source_type=replay ayrımı) | SPEC §6.1 SourceTypeE 6 değer (fixture ek); §6.2 clock_ref L12; FC-04/05 invariants parity; CAP-PARITY-01. | ✅ Y |
| AD-5 Data Quality Hard Gate → bayraklar set olunca risk reject / quarantine | SPEC §6.3 QualityFlags quarantined = True ise canonical akış YOK sözleşmesi L61 CONTRACTS; SPEC §9 SEC-03; HR-02/HR-08. | ✅ Y |
| AD-17 Correlation ID zorunluluğu, end-to-end trace | SPEC §6.2 sıra 8 correlation_id ZORUNLU; sıra 9 causation_id ZORUNLU; AC-06 eksik corr_id fail; S-FND-02 logger.corr alignment preservation matrix. | ✅ Y |
| AD-19 Failure safe-stop → fallback yok, fail hard | SPEC §8 Fail-Closed 8 case; FC-01..08 exception raise; no silent clamp, no default. | ✅ Y |
| AD-20 Testability Architectural Constraint → contract/replay/failure unit | Test plan TP-01..10; 18 AC executable; determinism 10x. | ✅ Y |
| EPICS E-CON S-CON-01 AC'leri L261-268 (corr eksik HATA, quality.degraded + en az 1 bayrak, UTC Z eksik HATA) | AC-05/06, AC-12 degraded invariant, AC-07/08 UTC HATA. | ✅ Y (tam match) |
| CAP-1 Parity / CAP-2 downstream bayrak tüketimi bridge | SPEC §4 UP-06 referans; CAP-PARITY-01; CAP-QUALITY-02; architecture-traceability bridge section. | ✅ Y |
| PRD Hard-Boundary §1: No real orders, API keys, short/lev in v1 | HRC 8 proje; S-FND-03 F1..F4 scan; preservation matrix tüm rows 0 drift. | ✅ Y |

Wrapper-ceremony drops (BUNLAR drop edilirler. Normal. Load-bearing DEĞİLLER):
- EPICS.md Epic 2 S-CON-03/04 story'leri SPEC içinde "Future" olarak listelendi. (Wrapper, downstream.)
- PRD "Counter-metrics" §4 3 counter-metric. FND-05 scope dışı (future performance story'leri.)
- AD-6 Internal Bus — non-goals NG-09 (gecerli drop.)

Drops: 3 wrapper = ✅ ACCEPTABLE. Load-bearing drops: 0.

## SP05 Verdict

| Pass | Hukük |
|---|---|
| Pass 1 Coherence | ✅ **PASS** 8/8 Laws (Law-7 Pass-2'de) |
| Pass 2 Preservation | ✅ **PASS** 13/13 Load-bearing claim düştü. 0 load-bearing drop. 3 Wrapper OK. |

**SP05 Self-Validation = TOTAL PASS (2/2)**

## Planlama Snapshot vs Güncel Durum

Bu self-validation **planlama zamanı** snapshot'ıdır (SPEC/companion yazımı). As-built durumu (implementation commit `9314eb4`) ayrıdır:

- Bu turda yapılan Option C uzlaştırması (OD-05-09 + `acceptance-criteria.md` import yolu düzeltmesi) **yalnızca dokümantasyondur**. Kod veya test değişikliğinin tamamlandığı anlamına GELMEZ.
- Bu belgedeki sayısal düzeltmeler (7 bool; 14 zorunlu + 2 opsiyonel = 16 alan) SPEC/companion metni ile hizalama içindir; çalıştırılmış test sonucu iddiası DEĞİLDİR.

