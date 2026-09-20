---
scope: E-API Epic 14 Open Decisions (8 decision) — N2 düzeltmesi OD-01 explicit
created: 2026-09-19
updated: 2026-09-19
---

# Open Decisions (ADN + OD)

| ID | Açıklama | Tam Kaynak | Normative mi? | Implementation Impact | Blocker (implementation başlamadan önce çözülmeli mi?) |
|:-:| --- | --- |:-:| --- |:-:|
| ADN-03 | Stale threshold default + **SLO değerleri sonra** (numeric latency/availability) | [EPICS L499](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L499) | Non-binding (default kullan) | SLO/alert threshold | HAYIR |
| ADN-09 | Kill/emergency default davranış: "yeni emir YOK, mevcut pozisyonları KAPATMA" + sahibi | [OPEN-DECISIONS.md L52-L55](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md#L52-L55) + [EPICS L505](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L505) | Yarı-normatif (default bağlayıcı; sahibi sonradan) | POST 2 davranış | HAYIR (default uygulanır) |
| ADN-11 | Gelecek canlı spot onay sahibi / hukuk sınırı / final onay makamı | [OPEN-DECISIONS L62-L65](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md#L62-L65) + EPICS L507 "canlı onay KAPALI MVP" | Non-binding | FAR FUTURE live (E-API paper fazını ETKİLEMEZ) | HAYIR |
| ADN-12 | Coğrafya / müşteri yüzü / hukuk incelemesi + MVP auth KAPALI | [OPEN-DECISIONS L67-L70](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md#L67-L70) + EPICS L508 | Non-binding (auth kapalı, geliştirmede placeholder) | 2 POST auth placeholder | HAYIR (placeholder ULID = geçer) |
| **OD-01 ✨ (N2)** | API listener deployment topolojisi (hangi adreste dinler?) | **0 kaynak normative yazmıyor (düzeltiliyor: hard-red SPEC'ten KALDIRILDI).** | AÇIK KARAR — Non-binding | Network policy, bind address, firewal cfg | **HAYIR** — geliştirme phase default candidate resolution 1 kullanılır (aşağıya bakınız) |
| | **Candidate resolution 1 (tasarım önerisi, düşük risk):** `127.0.0.1 loopback ONLY` | Implementation sırasında ilk default olarak denenebilir ama **bağlayıcı değil** — paper production intranet istenirse değiştirilebilir. | | | |
| | **Candidate resolution 2:** Private intranet IP (çok operatör paper production) — gelecekte seçilebilir. | | | | |
| OD-02 ✨ | Paper E-API activation için explicit onay artefact (imza/rapor) gerekli mi? | FR-063 canlı için zorunlu; paper E-API için kaynak YOK | Non-binding | Phase başlangıç prosedürü | HAYIR |
| OD-03 ✨ | Tam metric ad/etiket listesi + ilk alert kuralları kaç tane? | S-API-04 + ADN-03 "ilk set + SLO sonra" | Non-binding | DoD sayısal ölçüm | HAYIR (örneklerle başla) |
| OD-04 ✨ | 2 POST için: idempotency_key + double_confirm_token ULID dışında ek crypto imza gerekli mi? | AD-16 double-confirm var ama spesifik semantik YOK; N1 body ULID olarak bağlandı | Non-binding (MVP auth kapalı) | Güvenlik derinliği | KISMEN (implementation başlamadan önce N1 body alanları kesinleşti — bu OD ek kripto isterse sonradan) |

## N2 Son Kontrol:
- ✅ "localhost loopback ONLY" HARD-RED veya SPEC normative başlıklarda YOKTUR.
- ✅ OD-01 altında explicit olarak "Candidate resolution 1: localhost (tasarım önerisi non-binding)" olarak yazılmıştır.
- ✅ Outbound internet prohibition (HR-F-NEW-3) normative olarak korunmuştur.
- ✅ Acceptance Criteria AC-10/11 localhost MUST normatif YOK.
