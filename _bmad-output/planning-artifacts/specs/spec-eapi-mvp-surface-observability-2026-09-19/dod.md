---
scope: E-API Epic 14 Definition of Done (FUTURE-PHASE)
created: 2026-09-19
updated: 2026-09-19 (N1 + N2 remedy sonrası güncelleme)
---

# DoD — E-API (Gelecek Faz)

1. **4 hikâye (S-API-01..04) AC 13/13 PASS.**
   - S-API-01 10 GET grubu: schema 10/10 smoke test PASS
   - S-API-02 2 POST: AC-01..05 idempotency + double confirm 5/5 PASS (N1 zorunlu)
   - S-API-03 CAP-6: AC-06..07 4 tarama = ZERO occurrence PASS
   - S-API-04 Prometheus: AC-08..09 metrics + first-alert PASS
2. **N1 zorunlu:** Her başarılı/başarısız 2 POST audit payload'ında `idempotency_key` + `double_confirm_token` mevcut (SPEC §12). Hiçbir başarılı gateway çağrısı bu field'lardan biri olmadan oluşamaz.
3. **N2 zorunlu:** Companion artifact'lerde "localhost ONLY" normative kural YOK. Sadece OD-01 açık karar altında tasarım önerisi candidate olarak yazılı. Outbound internet forbidded normative KORUNUR.
4. **Current Scope koruma:** S-MDL-01..05 diğer 13 Epic production scope'larında 0 byte diff; hiçbir E-API kodu doğrudan domain registry UPDATE yapmaz (AD-14).
   C1 explicit exception: YALNIZCA `pyproject.toml` [project.optional-dependencies] subgroup `eapi` 5 satır (Msg4 + SPEC §8/§14 source-backed). S-MDL çalışma zamanı etkisi = 0.
5. **Hard-Red:** HR-C (current mevcut) 5/5 + HR-F-NEW 4/4 E-API new HRC + 3 future exception onaylı; ihlal 0.
6. **Audit evidence:** 2 POST her çağrı (fail dahil) structured audit row correlation + idempotency + double_confirm + auth_scope + final_result ile kaydedilir.
7. **SP05:** 8/8 PASS (SPEC başlığından bağımsız re-doD).
8. **Expected file changes:** 10 companion mevcut; 18 yeni production (app/platform/api 15 + app/platform/observability 2 + configs 1); 5 yeni test (tests/api/*); **1 explicit existing-file C1 exception: pyproject.toml eapi optional subgroup 5 lines.** C1 dışındaki existing domain/test dosyaları MODIFY = 0.
