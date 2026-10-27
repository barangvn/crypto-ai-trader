# Architecture Traceability — S-FND-05

## Mimari Kararlar (AD) → Hikâye Segment Eşleşmesi

| AD ID | Mimari Karar Başlığı | S-FND-05'de Nerede / Nasıl Karşılanır | Etki Eden Alanlar | Not |
|---|---|---|---|---|
| **AD-1** | Modular Monolith, tek repo, bounded context klasörleri | `app/contracts/` package YENİ Klasör AD-1 `app/` bounded context. | Yeni klasör: app/contracts/ (S-CON-01 location). | Aynı repo, yeni package — 0 existing modify. |
| **AD-2** | Exchange Boundary (adapter port arkası) | S-FND-05 exchange YOK. Adapter/schema ayrım korunur (payload = generic[T], 19 payload schema S-CON-02 adapter sonrası). | Tüm adapter scope RDH-01'de. | 0 network / 0 exchange. |
| **AD-3** | **Canonical Event Envelope** (Zorunlu 14 meta alan + envelope zorunluluğu) | TÜM HİKÂYE. §6.2 14 zorunlu + 2 opsiyonel = 16 alan kesin isim/tip. `CanonicalEventEnvelope[T]` frozen dataclass implementation. | UP-03 PRIMARY KAYNAK. | CONTRACT_VERSION 1.0.0 alignment FND-04 → PASSED. |
| **AD-4** | **Live/Replay Parity** (aynı kod, `source_type=replay` ayrımı) | §6.1/6.2 `SourceTypeE` · `RunModeE` · `clock_ref {wall,replay}`. FC-04 FC-05 — replay source için None clock / aynı timestamp → HARD FAIL parity invariant. | UP-04 PRIMARY KAYNAK. CAP-1 kurallar. | Downstream parity tarayıcısı S-CON-03. |
| **AD-5** | **Data Quality Is a Hard Gate** (9 kontrol quarantine/alert/block) | §6.3 QualityFlags 7 bool (stale/missing/duplicate/out_of_order/invalid/quarantined/degraded + reasons). Post-init degraded invariant, auto-set on other flags. AD-5 9 kontrol *logic* RDH-01; burada bayrak TİPLERİ + downstream consumption CAP-2 bridge. | UP-04. CAP-2 bridge. | Bayrak isimleri CONTRACTS L56-62 KESİN. |
| **AD-6** | Internal Event Bus First (in-process asyncio Queue dispatch) | NG-09 out-of-scope. | Event bus E-PLN-01. | 0 implement. |
| **AD-7** | Read Model Ownership (pay-per-write bounded) | Envelope YAZIM ADINA SAHİP DEĞİLDİR (producer consumer tarafından yazılır). Sadece TİP. | 0 impact. | |
| **AD-8** | Regime Independent Service Boundary | 6 rejim payload schema S-CON-02 §3.6 MarketRegime. | Sadece envelope; payload generic[T]. | S-CON-02 içinde MarketRegime. |
| **AD-9** | Strategy Plugins Stay Pure (sadece StrategyContext) | StrategyContext §3.8 S-CON-02. Sadece envelope run_mode/source_type copy AD-25 (bağlamsal referans, kapsam dışı). | | |
| **AD-10** | AI Has No Execution Authority | Envelope.event_type "ai_decision.v1" gibi tip destekler ama execution auth RiskEngine AD-11. | Execution RSK. | |
| **AD-11** | Risk Engine Final Approval Gate | RiskDecision payload S-CON-02 §3.11. | CAP-4 bridge. | |
| **AD-12** | Paper & Future Live Ayrık Port | RunMode enum içinde `live` YER ALIR ama gerçek yol AD-12 — S-FND-03 F4 tarayıcı + PRD hard boundary. | | Enum'da "live" sözleşmede var; pratikte kapalı. |
| **AD-13** | Portfolio Simulator Single Writer | Payload S-CON-02. | 0 impact. | |
| **AD-14** | Governed Lifecycle (Candidate→Champion state) | LIFECYCLE payload ModelVersion S-CON-02. | Status machine S-CON-04 CAP-5. | |
| **AD-15** | Storage Polyglot (PostgreSQL + Timescale) | NG. | E-PLN / storage. | |
| **AD-16** | API Control/Query Plane | API envelope S-CON-04. | | |
| **AD-17** | **End-to-End Observability via Correlation ID** | Envelope L40 correlation_id ZORUNLU. causation_id L41 ZORUNLU. SPEC §6.2 sıra 8/9. | UP-04 observability. Structured log S-FND-02. | S-FND-02 correlation ile alignment. |
| **AD-18** | Environment Separation Mandatory (dev/test/stg/paper-prod) | RunMode + S-FND-04 env 4 distinct + symbol Namespace (AD-18 config db_namespace). | 4 env alignment FND-04. | |
| **AD-19** | Failure Defaults to Safe Stop | FC fail-closed §8 (8 case). Validation fail → EXCEPTION, fallback YOK. | AD-19 safe stop. | |
| **AD-20** | Testability Architectural Constraint (contract/replay/failure unit) | Test plan TP-01..10 (unit, negatif, parity, invariant, determinism, forbidden). | TP-01..10 18 AC test. | Bütün AC'ler test edilebilir. |
| **AD-22** (2026-08-10 spine · ileriye dönük referans) | FeatureVector flat dict, nested/ndarray YOK | S-CON-02 scope. Nested YOK sözleşmesi S-FND-05 envelope değil payload. SPEC §12 NG-02 ve front-matter `non_goals`'ta açıkça non-goal olarak adlandırılır. | AD-22 S-CON-02. | Kapsam İÇİ DEĞİL; yalnızca kapsam-sınırı kaydı için tabloda (bkz. "AD Sayım Ölçütü"). |

## CAP (Contract Adherence Principles) Bridge

| CAP-ID | Başlık | S-FND-05 ile İlişki | Neden? |
|---|---|---|---|
| **CAP-1** | Live/Replay Parity (5 domain kod NO `if run_mode == replay` branch) | Envelope fields `run_mode`, `source_type`, `clock_ref` TİPLENDİ. Branch tarayıcısı S-CON-03 ama alanlar burada tanımlandı → İLK BRIDGE. | CAP-1 success verification alanları burada SET. |
| **CAP-2** | Kalite bayrakları downstream tarafından envelope içinden okunur (validator RPC YOK) | **QualityFlags IN ENVELOPE §6.2 quality_flags.** | Bayraklar tek kaynak: envelope.quality_flags. Downstream tüketici CAP-2'yi burada doğrular. |
| **CAP-3** | Strategy plugins sadece typed StrategyContext tüketir | StrategyContext payload S-CON-02. Envelope L43 source_type L42 run_mode bu context içine kopyalanır AD-25 (bağlamsal referans, kapsam dışı). | Hazırlık. |
| CAP-4 | PaperOrder requires same-correlation RiskDecision.approved BEFORE | RiskDecision payload S-CON-02. Correlation_id alignment (envelope L40) burada zorunlu. | Shared correlation ID. |
| CAP-5 | ModelVersion.status mutate ONLY registry.request_transition | LIFECYCLE payload Status field 6 değer. Status mutation test S-CON-04. | Hazırlık LIFECYCLE enum. |
| CAP-6 | Forbidden /execution/live routes MVP API YOK | Routes S-CON-04. RunMode "live" enum içindeydi ancak AD-12. | Hazırlık. |

## ADN (Açık Mimari Kararlar) Yukarı Akış

| Önceki ADN List (spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md L) | Bu hikâyedeki etkisi | Çözüm: OD-05-XX |
|---|---|---|
| ADN-01 Replay provider/provider | Minimal: `source_type="replay"` + `source="replay.<provider>"`. Zorunlu provider S-FND-05'de YOK. | GAP YOK. String source. |
| ADN-05 model family enum | LIFECYCLE enum. payload S-CON-02 ModelVersion.model_family. Nested type FND-05'te YOK. | S-CON-02'ye aktarıldı. |
| ADN-06 score default weights | OpportunityScore payload. S-CON-02. | |
| ADN-07 fill model fields | PaperFill payload. S-CON-02. | |
| ADN-10 object storage path | SchemaRef içinde artifact path model_id null. | |

**Toplam:** 21 AD (1-20 + 22) → 12 doğrudan bu hikâyeyi bağlar (özellikle AD-3, AD-4, AD-5, AD-17, AD-19, AD-20 PRIMARY binding). Sayım ölçütü: aşağıdaki "AD Sayım Ölçütü" bölümü.

## AD Sayım Ölçütü (OD-05-10 — Architecture Provenance / Option A)

**Normatif kaynak:** `architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md` (AD-1..AD-25). SPEC front-matter bu sürümü kaynak gösterir (OD-05-10).

**Ölçüt:** İzlenebilirlik tablosu ve AD sayımı, hikâyenin **kapsam-sınırı beyanlarında** (SPEC §3 IN/OUT ve SPEC `non_goals` / §12 NG) **adı geçen** AD'leri içerir. Yalnızca companion metinde **bilgilendirici çapraz-referans** olarak geçen AD'ler tabloya ve sayıma **ALINMAZ**.

Bu ölçüte göre:

- **AD-1..AD-20** (2026-08-10 spine baseline): tabloda ve sayımda — hikâyenin bağlı olduğu kararlar.
- **AD-22** (ileriye dönük referans): SPEC §12 NG-02 ve front-matter `non_goals`'ta **açıkça adlandırıldığı** için kapsam-sınırı kaydı olarak tabloda ve sayımda tutulur. **Kapsam İÇİ DEĞİLDİR** ve uygulama kapsamına girdiği anlamına GELMEZ (FeatureVector shape → S-CON-02).
- **AD-25** (bağlamsal referans): Yalnızca bu belgenin AD-9 ve CAP-3 notlarında, envelope `run_mode`/`source_type` alanlarının `StrategyContext`'e kopyalanması bağlamında anılır; SPEC kapsam-sınırı beyanlarında **adı geçmez** ve S-FND-05'in devrettiği/kapsadığı bir sınır tanımlamaz (tamamen strategy katmanı → S-CON-02/03). Bu nedenle tabloya ve sayıma **alınmaz**.
- **AD-21, AD-23, AD-24**: Ne kapsam-sınırı beyanında ne de companion metinde anılır → tablo/sayım dışı (scope-owner kararı: AD-21 kapsam dışı).

**Sayım doğrulaması:** AD-1..AD-20 (20) + AD-22 (1) = **21**; tabloda AD-1..AD-20 + AD-22 = 21 satır. Ölçütle tutarlı → `21 AD (1-20 + 22)` korunur.

Referans: `open-decisions.md` → OD-05-10.

## Canonical Tip Sahipliği Sınırı (Option C — OD-05-09)

AD-3 (Canonical Event Envelope) ve AD-5 (Data Quality Hard Gate) iki paralel tip ailesi tarafından karşılanır ve bu ailelerin sahipliği **OD-05-09** ile açıkça ayrılmıştır. Sınır tablosunun kanonik kaydı `open-decisions.md` → "Mimari Sınır — Kanonik Tip Sahipliği (Option C / OD-05-09)" bölümündedir.

- S-FND-05 canonical-envelope sözleşmesinin AD-3/AD-5 karşılığı: `app/contracts/envelope.py` + `app/contracts/quality_flags.py` (commit `9314eb4`); public import yolu `app.contracts.sfnd05_api`.
- `app/contracts/canonical.py` (S-RDH-01, `9ec9106`) içindeki aynı isimli tipler legacy tüketiciler içindir; S-FND-05 tipleriyle otomatik eşdeğer DEĞİLDİR.
- AD-3 için `app/contracts/__init__.py` export seti Option C kapsamında değiştirilmemiştir (root public API korunur).

