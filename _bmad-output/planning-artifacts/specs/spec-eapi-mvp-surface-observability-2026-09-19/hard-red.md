---
scope: E-API Epic 14 Hard-Red (FUTURE-PHASE) — N2 düzeltmesi localhost ONLY kaldırıldı
created: 2026-09-19
updated: 2026-09-19
---

# Hard-Red — E-API

**Önemli:** Mevcut zorunlu kapsam (current mandatory) HRC 21/21 tamamen korunur. Bu dosyadaki 3 "Future Exception" ancak future phase onay sonrası yürürlüğe girer.

## I. CURRENT PHASE HARD-RED (Korunuyor — değişiklik YOK)
| ID | Kural | Kaynak |
|:-:| --- | --- |
| HR-C-01 | Mevcut (current HEAD bdd8c9f) çalışma zamanında **NO network outbound / NO socket / NO HTTP call (dışarı)** | Mevcut HRC (doğrulandı) |
| HR-C-02 | Current production code pyproject.toml **NO FastAPI / Uvicorn / Prometheus-client third-party import** | 0 match (doğrulandı) |
| HR-C-03 | v1 NO keys/credentials/secret (saklama / isteme / kullanma) | FR-061 [PRD L160](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L160) |
| HR-C-04 | NO canlı emir / execution authority (yalnızca ExecutionSimulator paper) | AD-12 [ARCH L144](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L144) |
| HR-C-05 | NO external exchange integration current mandatory | PRD L194 Deferred |

## II. FUTURE PHASE EXCEPTION (Onay Sonrası)
| ID | İstisna | Koşul | Kaynak |
|:-:| --- | --- | --- |
| HR-F-EX-1 | Process içinde HTTP listener (FastAPI) açma | Gelecek faz activation onayı + AD-12 paper bağlamı | ARCH L551 FastAPI adopted |
| HR-F-EX-2 | 3 Third-party dep: `fastapi==0.141.1`, `uvicorn`, `prometheus_client` (pinli SPEC sürümleri) | Gelecek faz | ARCH L551/L554 |
| HR-F-EX-3 | In-process loopback HTTP çağrısı (127.0.0.1 test/dev dashboard) | Yalnızca geliştirme / test / paper | Standart (non-normative development practice) |

## III. FUTURE PHASE NEW HARD-RED (E-API MVP BAĞLAYICI — Onay Sonrası Mutlaka Uygulanır)
| ID | Kural | Kaynak |
|:-:| --- | --- |
| HR-F-NEW-1 | CAP-6 4 yasaklı route (+ 5. `/admin/retire-champion`) → runtime registry + static AST + OpenAPI + path variant 4 tarama = ZERO occurrence | FR-069 [EPICS L101](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L101) + S-API-03 ANA PROOF [L477](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L477) |
| HR-F-NEW-2 | 2 POST route (emergency / kill): Ayrı izin + `idempotency_key` (ULID) + `double_confirm_token` (ULID) ZORUNLU body. Başarısız validation → gateway ÇAĞRILMAZ; audit failed_attempt kaydı ZORUNLU. | AD-16 double-confirm [ARCH L168](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L168) + N1 SPEC §12 |
| HR-F-NEW-3 | **Outbound internet (non-loopback public IP) = YASAKTIR.** Paper production E-API tüm veri yerel replay/simulation read model'den gelir. Exchange socket = 0. | AD-12 [ExecutionSimulator only L144](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L144) + FR-061 no keys + PRD L194 deferred live + CAP-6 live route 0 |
| HR-F-NEW-4 | Kill/emergency davranışı default ADN-09: "Yeni emir YOK. Mevcut pozisyonları (paper) doğrudan KAPATMA." Ayrı yönetim kararı ve approval yok zorlanamaz. | [EPICS L505](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L505) |

## IV. N2 Düzeltmesi — STALE NORMATIVE REFERENCE = 0
- ❌ KALDIRILDI (artık HARD-RED normatif değil): "localhost loopback MUST / 127.0.0.1 ONLY bind address"
- ✅ OD-01 Açık Karar (non-binding, tasarım önerisi candidate resolution): "localhost loopback ONLY — geliştirmede önerilir; paper production deployment ise future-phase karar" → open-decisions.md OD-01 altında
