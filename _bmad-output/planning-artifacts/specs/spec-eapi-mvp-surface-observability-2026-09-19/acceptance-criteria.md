---
scope: E-API Epic 14 FUTURE-PHASE Acceptance Criteria (N1 + N2 düzeltmeleri dahil)
created: 2026-09-19
updated: 2026-09-19
---

# Acceptance Criteria (E-API Epic 14 — Gelecek Faz)

## Genel (Shared)
| ID | Given | When | Then (source) |
|:-:| --- | --- | --- |
| AC-00 | GET endpoint (10 gruptan herhangi biri) | Valid ULID correlation_id → call | Response envelope: `{ok: true, data, correlation_id: ULID}`. Schema API.md L23-L104 karşılığı. |
| AC-00b | Tüm 10 GET grupları | Snapshot test | 10/10 gruba karşılık en az 1 route mevcut; path prefix /api/v1. |

## N1 (POST Body / Semantics — MAJOR resolved)
| ID | Given | When | Then (source) |
|:-:| --- | --- | --- |
| AC-01 | 2 permissioned POST route (emergency-stop / kill-switch) | Body **eksik `idempotency_key`** veya **non-ULID format** | 400; envelope ok=false; error.code=`INVALID_IDEMPOTENCY_KEY`; audit row "failed_attempt"; **Risk Engine gateway çağrısı YOK** (AD-16 fail-safe + fail-closed §10). |
| AC-02 | Aynı 2 POST | Body **eksik `double_confirm_token`** veya **non-ULID format** veya **izin scope mismatch** | 403; envelope ok=false; error.code=`INSUFFICIENT_CONFIRMATION`; audit row "failed_attempt"; gateway YOK. (AD-16 ayrı permission + double-confirm [ARCH L168](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L168)) |
| AC-03 | Emergency POST başarılı (valid key + valid confirm + scope EMERGENCY) | Body `{reason, operator, idempotency_key: ULID, double_confirm_token: ULID}` | (a) Response correlation_id döner; (b) Audit payload'ında BOTH field'lar ZORUNLU (SPEC §12 N1); (c) ADN-09 default: "yeni emir yok, mevcut pozisyonları KAPATMA" zorlanmaz — yalnızca Risk Engine kill_switch_enabled=true set gateway çağrısı. |
| AC-04 | Kill POST başarılı (same valid, scope RISK + valid body scope field) | Body `{scope, symbol?, reason, operator, enabled, idempotency_key, double_confirm_token}` | (a) Response scope+state dönülür; (b) Audit payload her iki N1 field; (c) Kayıt registry direct mutate YOK. |
| AC-05 | **Idempotency replay (aynı idempotency_key 2x çağrı)** | Valid POST → 1 saniye sonra aynı body ile tekrar | (1) 2. response = 1. response **birebir aynı** (deterministic idempotent); (2) 2. gateway çağrısı YOK (sayaç / çağrı counter); (3) Main audit row sayısı = 1; (4) Ayrı bir "idempotency_duplicate" info audit row OLUŞUR. (S-RSK-02 idempotency pattern) |

## CAP-6 (Forbidden Routes — ANA PROOF)
| ID | Given | When | Then |
|:-:| --- | --- | --- |
| AC-06 | Runtime registry + static AST + OpenAPI generated + path variant 4 tarama | 4 pattern: `/execution/live/* /keys/* /accounts/funding/* /risk/limits/write` | Occurrence count = 0 (4 tarama ayrı ayrı 0). [EPICS L477](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L477) |
| AC-07 | `/admin/retire-champion` doğrudan model state write (5. yasak) | 4 tarama | Occurrence = 0. [API L112](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/API.md#L112) |

## Observability / Prometheus
| ID | Given | When | Then |
|:-:| --- | --- | --- |
| AC-08 | `/metrics` endpoint exposed | Valid scrape call | (a) 200 OK Prometheus exposition; (b) En az 10 operational metric (health/risk/opportunity/quality); (c) Credential/secret label YOK (N/GAP LOW explicit yazılmadı ama test failed pattern = "keys/secret/token" label taraması); (d) correlation_id label mevcut (AD-17). |
| AC-09 | İlk alert kural seti dosyası (`configs/prometheus_rules_base.yml`) | Static load | 10+ rule tanımı; health/risk/stale categories. (S-API-04 "ilk seti") |

## N2 Düzeltmesi (Localhost ONLY artık normative DEĞİL; OD-01 non-binding)
| ID | Given | When | Then |
|:-:| --- | --- | --- |
| AC-10 (N2 bağlantılı) | Test suite çalışma | Network permission taraması | Test code veya HARD-RED içinde "localhost loopback MUST" yazan **normative AC YOKTUR**. Aşağıdaki tek NORMATİF kural korunur: **Outbound internet call (non-loopback / public IP) = FAIL** block. |
| AC-11 | Paper Production deployment | Dinleme adresi seçimi | Seçim OD-01 Açık Karar'a bırakılır; LOCALONLY yazan hard assertion AC YOKTUR. |

## Current Scope Koruma
| ID | Given | When | Then |
|:-:| --- | --- | --- |
| AC-12 | S-MDL-01..05 production 17 scope + S-MDL contracts | E-API future implementation | S-MDL dosyalarında 0 byte diff; doğrudan registry UPDATE YOK (AD-14 single-owner). İleride E-API implementation phase sonunda test edilir. |

---
Total AC count = **12** (N1 5 tane + CAP-6 2 tane + Obs 2 tane + N2 2 tane + scope koruma 1 tane + shared 00/00b 2 tane = 15? Sayım doğrultusunda: AC-00..AC-12 = 13 item; ≥12 sağlandı ✅).
