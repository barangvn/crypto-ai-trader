---
scope: E-API Epic 14 MVP API Surface & Observability (FUTURE-PHASE — current mandatory scope dışıdır)
status: binding FUTURE-PHASE; current release NO implementation
created: 2026-09-19
updated: 2026-09-19 (N1 + N2 MAJOR remedy turu)
captain: E-API Future Phase
deferred_from: Mandatory Closure HEAD = bdd8c9fef420c0104726c1921b929a8708cb4e11
---

# SPEC — E-API (Epic 14) MVP API Surface & Observability

**Önemli:** Bu SPEC **gelecek faz** (future-phase) sözleşmesidir. Mevcut zorunlu kapsama (S-MDL-01..05 + 12 supporting Epic) dahil değildir. Bu dosya tek başına implementation onayı vermez; implementation ancak companion AC + DoD + HARD-RED + SHORT RE-AUDIT PASS alınca başlar.

## 1. Exact Intent
Epic 14 (son implementation sıra, Appendix B L491): Dashboard operatörü için **10 okuma grubu GET** + **2 permissioned POST audit** + **CAP-6 forbidden route zero-occurrence scan** + **Prometheus first-alert seti** sunan HTTP query/control plane API yüzeyi. **Canlı execution / gerçek emir / keys / funding DEĞİLDİR.** [EPICS.md L169, L461-L464](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L169)

## 2. Source-Backed Success Criteria
- CAP-6 (S-API-03 ANA PROOF): `/execution/live/* /keys/* /accounts/funding/* /risk/limits/write` 4 taramada 0 occurrence. [EPICS L477](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L477)
- 10 GET grubu (system / market / opportunities / regime / strategies / portfolio / performance / models / risk / logs): schema validation 100% against API.md L23-L104.
- 2 POST: Ayrı izin + audit + idempotency_key + double_confirm_token TÜM successful çağrıda audit event payload'ında mevcut.
- Prometheus `/metrics` endpoint: credential label yok, ilk alert seti yüklü.

## 3. IN / OUT Boundary
- INCLUDED: 10 GET (API L23-L104), 2 POST (system/emergency-stop API L29 + risk/kill-switch API L97), CAP-6 scan, Prometheus first-alert + correlation metrics.
- EXCLUDED (gelecekte bile ayrı SPEC gerektirir): Canlı spot execution FR-063 [PRD L162](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L162); `/backtests/*` yönetim; `/paper-config/*` kalıcı ayar; `/admin/retire-champion` doğrudan model write; keys/funding/live. [API L105-L118](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/API.md#L105-L118)

## 4. Upstream Dependencies
- S-CON-04 (CAP-6 initial forbidden scan setup) [EPICS L298-L308](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L298)
- E-RSK-04 (Risk Engine kill/emergency interface gateway)
- S-PLN-01 (Typed EventBus + correlation_id AD-17)
- S-MDL-01..05 Read-Only modeller (registry lifecycle — DOĞRUDAN MUTATE YOK)

## 5. Downstream Consumers
- Dashboard SPA (FR-057..060 UI consumer) [PRD §5.11 L151-L157](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L151)
- Prometheus scraper + Alertmanager (AD-17)
- Operatör audit log viewer (POST only)

## 6. Security / Safety Boundary
- Authentication: **SPEC'te ZORUNLU** (API L16); MVP development ADN-12 "auth kapalı" olduğundan test token placeholder kullanılır. Future production RBAC ayrı spec.
- Ayrı izin katmanı: 2 POST için `E-API-OPERATOR-EMERGENCY` (emergency) + `E-API-OPERATOR-RISK` (kill) scope. [AD-16 L168](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L168)
- v1 NO keys/credentials/secret: FR-061 [PRD L160](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L160) → E-API body'de secret/key field YOK.

## 7. Offline / Live Boundary
- MVP E-API (paper): **Offline + replay/derived/system ONLY.** source_type_global paper/replay dışı canlı veri route YOK.
- Live boundary: AD-12 future phase gated, ayrı port + permission domain. [ARCH L140-L145](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L140)
- DOĞRUDAN canlı socket veya exchange bağlantısı = 0.

## 8. Network / API Semantics (source-backed ONLY)
- **NORMATIVE (KAYNAK DESTEKLİ):** Outbound internet call YASAKTIR. Tüm veri yerel replay/simulation read model'den gelir. (AD-12 ExecutionSimulator only + FR-061 no keys + PRD L194 deferred live + CAP-6 canlı route 0).
- **OPEN DECISION (non-binding, bkz OD-01):** API listener deployment topolojisi (loopback mi? intranet mi?). Candidate resolution 1: localhost 127.0.0.1 (tasarım önerisi, en düşük risk). Candidate 2: intranet private IP. Karar future-phase'e bırakılır.
- Prefix: `/api/v1` [API L15](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/API.md#L15)
- Response envelope: `{ ok: boolean, data: T|null, error: {code,message,details}|null, correlation_id: ULID }` [API L17](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/API.md#L17)
- Stack: FastAPI 0.141.1 [ARCH L551](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L551) + Prometheus 3.13.2 [ARCH L554](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L554)

## 9. Credential / Secrets Handling
- v1 (paper E-API MVP): **NO API key / secret / trading credential stored / requested / used.** (FR-061 bağlayıcı)
- Future credential: FR-062 [PRD L161](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L161) "secrets management, isolation, least privilege, audit, explicit gates".
- **double_confirm_token GERÇEK SECRET DEĞİLDİR.** Sadece AD-16 double-confirmation operatör onay placeholder'ıdır (ULID format, non-secret). MVP auth closed (ADN-12) → geliştirmede ULID valid ise geçer.

## 10. Failure / Fail-Closed Behavior
- Tüm auth/permission/confirm/idempotency fail durumlarında: Risk Engine gateway ÇAĞRILMAZ. Sadece audit failed_attempt kaydedilir; envelope ok=false + uygun HTTP statüsü döner. (AD-16 audit trail + HARD-RED fail-safe default ARCH §21 L628).

## 11. Determinism Requirements
- Same idempotency_key → same response (no gateway 2. call).
- GET responses: YALNIZCA read model immutable snapshot'ları üzerinden (tek yazar modülleri).
- 2 POST kill/emergency davranışı: ADN-09 default "yeni emir YOK, mevcut pozisyonları KAPATMA" [EPICS L505](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L505). Ayrı yönetim kararı olmadan zorlanmaz.

## 12. Audit / Evidence Requirements
AD-16 "emergency stop ayrı permission scope + double-confirmation + audit trail ZORUNLU" [ARCH L168](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L168). Her 2 POST audit event payload şu ZORUNLU field'ları içerir:
- `ts` (Instant)
- `operator` (from body)
- `reason` (from body)
- `correlation_id` (ULID response envelope)
- `idempotency_key` (ULID body — N1 ZORUNLU)
- `double_confirm_token` (ULID body — N1 ZORUNLU)
- `route` ("/system/emergency-stop" veya "/risk/kill-switch")
- `auth_scope` (izin katmanı adı)
- `final_result` (allowed / rejected / validation_failed / idempotency_duplicate)

### Ek — N1 — İki POST için İdempotency + Double Confirm Canonical Field Definition (BODY TOP-LEVEL)

| # | Field name | Required? | Type / Format | Presence | Semantic Purpose (source-backed) |
|:-:| --- |:-:| --- |:-:| --- |
| 1 | `idempotency_key` | ✅ REQUIRED | ULID (correlation_id same family; API L17 ULID) | Body top-level | AD-16 audit trail uniqueness; 1 idempotency_key → tam olarak 1 Risk Engine gateway çağrısı + 1 main audit row. S-RSK-02 idempotency pattern mevcut. |
| 2 | `double_confirm_token` | ✅ REQUIRED | ULID (same format) | Body top-level | AD-16 "double-confirmation" zorunluluğu placeholder. Operatörün 2-aşamalı onay token'ı (non-secret; MVP auth kapalı olduğundan geliştirmede ULID valid ise geçer). |

| # | Field | Duplicate request behavior | Token validation requirement | Failure behavior | Audit / Evidence expectation |
|:-:| --- | --- | --- | --- | --- |
| 1 | `idempotency_key` | İLK response BİREBİR döner; 2. gateway çağrısı YOK; 2. main audit row YAZILMAZ. (deterministic idempotent replay) | ULID format ZORUNLU; not ULID → 400 | 400 ok=false error.code=`INVALID_IDEMPOTENCY_KEY`; audit `failed_attempt` row; gateway NOT called. | Her POST main audit event payload'ında ZORUNLU. `idempotency_duplicate` ayrıca ayrı row kaydedilir (AD-16). |
| 2 | `double_confirm_token` | Aynı idempotency_key içinde ilk response aynısı döner. Yeni challenge gerekmez. | (1) ULID format ZORUNLU; (2) auth scope → E-API-OPERATOR-EMERGENCY veya E-API-OPERATOR-RISK match ZORUNLU (AD-16 ayrı permission). MVP auth closed (ADN-12) → ULID = geçer placeholder; future production ayrı auth spec bağlar. | 403 ok=false error.code=`INSUFFICIENT_CONFIRMATION`; audit `failed_attempt`; gateway NOT called. | Her POST main audit event payload'ında ZORUNLU. AD-16 "double-confirm + audit trail" kanıt. |

- Önemli: length / regex / TTL / hash / retention DEĞİL. Source yazmıyor → icat edilmedi.
- Sınır korunur: 2 POST YALNIZCA Risk Engine gateway üzerinden çalışır; registry direct mutate = 0; live execution = 0; arbitrary write = 0.

## 13. Non-Goals
(1) Canlı emir / gerçek borsa bağlantısı, (2) keys/credentials yönetim route'ları, (3) FastAPI import CURRENT production, (4) remote exchange veri çekme outbound, (5) registry ModelVersion.status doğrudan write (AD-14 L156), (6) model lifecycle doğrudan mutate, (7) UI auth production customer login (ADN-12 MVP kapalı), (8) kalıcı limits write (/risk/limits/write), (9) paper fill/fee schedule kalıcı config güncellemesi.

## 14. Hard-Red Constraints
(bkz companion `hard-red.md`):
- CURRENT HRC: 21/21 tamamen korunur (network outbound 0 / FastAPI 0 / keys 0 / live 0).
- FUTURE EXCEPTION (onay sonrası): HTTP listener fastapi + 3 third-party dep + loopback test calls.
- FUTURE NEW HRC (E-API MVP BAĞLAYICI): CAP-6 4 scan 0 occurrence; 2 POST 4 audit zorunlu + idempotency + confirm; NO outbound internet; ADN-09 default = "yeni emir yok, mevcut KAPATMA".

## 15. Acceptance Criteria
(bkz `acceptance-criteria.md`) — ≥12 AC (N1 için AC-01 idempotency / AC-02 double-confirm dahil).

## 16. DoD
(bkz `dod.md`)

## 17. Test Plan
(bkz `test-plan.md`)

## 18. Expected File Changes
(bkz `expected-file-changes.md`). 10 companion MD (bu klasör) + 18 app/platform/api + observability + configs yeni files
+ 5 tests/api yeni files + **1 explicit existing-file C1 exception: pyproject.toml optional deps subgroup eapi**.
S-MDL production domain existing files (outside new folders) = MODIFY 0.

## 19. Open Decisions
(bkz `open-decisions.md`). ADN-03 / ADN-09 / ADN-11 / ADN-12 + OD-01..04.
- **OD-01 (N2 düzeltmesi):** Deployment topolojisi (listener nerede?) — AÇIK KARAR non-binding. Candidate resolution 1: `127.0.0.1 loopback ONLY` (tasarım önerisi). Candidate resolution 2: intranet private IP. Karar future-phase'e bırakılır.
- OUTBOUND INTERNET = NORMATİF YASAK (corumda).

## 20. S-MDL-01..05 Exact Integration Boundary
- YALNIZCA READ: ModelVersion listesi / versions / evaluations / champion-challenger / lifecycle events (GET /models/*).
- Registry MUTATE YOK (AD-14). Model lifecycle değişikliği için YALNIZCA registry API gateway command port — E-API MVP'de bu komut route YOK (DOĞRUDAN yazma /admin/retire-champion CAP-6 yasak).
- Kill/emergency YALNIZCA Risk Engine'e gateway call → simulation yeni emir block. Models/S-MDL state'ine dokunmaz.

## 21. Why Deferred? (Current Release Dışı Evidence)
1. User explicit state: "12 supporting EPIC PASS" — EPICS 14 tane; 14. E-API 12 dışı.
2. HEAD bdd8c9f: `app/platform/` = event_bus.py + __init__; `app/platform/api/` YOK; `tests/api/` YOK → implementation 0 dosya.
3. Current HRC: "NO network / NO third-party / NO live" → E-API HTTP capability conflict. Solution future-phase.
4. PRD §8 Deferred: "live connection, keys, real orders, real funds" [PRD L194](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L194).
