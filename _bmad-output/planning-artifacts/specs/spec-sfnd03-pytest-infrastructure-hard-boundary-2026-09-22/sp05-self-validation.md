# SP05 Self-Validation — S-FND-03 (8 Kanun)

SPEC, SP05 8 kanununa göre kendi kendini denetler. Sonuç: **8/8 PASS** (Spec Prep aşamasında self-val 8/8 gerekli).

| SP05 Kanun | Uygulama | Durum | Kaynak |
|---|---|---|---|
| SP05-1: What not How (NEİS, NASIL DEĞİL) | SPEC: 3 marker, 4 prime scan tanımlar. NASIL (AST mı regex mi? recursive walk mı?) implementasyon karar. SPEC sadece contract ve zorunlu çıktıyı tanımlar (PatternScanFinding, PRGateScanReport format). Helper implementation details SPEC YAZMAZ. | PASS | SPEC §3.1 IN scope description §6 contracts |
| SP05-2: Measurable Success (sayılabilir 6 koşul M-1..M-6) | 6 explicit sayılabilir metrik M1..M6, her biri PASS/FAIL boolean | PASS | SPEC §2 M1-M6 measurable |
| SP05-3: Single Source Count Truth — AC 1 dosya, sayı 24 | acceptance-criteria.md 24 AC, TAM 24. SPEC §13'de sadece başlıklar, companion authoritative. Çift sayım yok. | PASS | acceptance-criteria.md + SPEC §13 |
| SP05-4: Stable CAP IDs — 15 CAP matrix unique id (CAP-1..15) | architecture-traceability.md 15 unique CAP, AD ve NFR bağlamaları 1:1 sabit, isimler unique. | PASS | architecture-traceability CAP-1..15 |
| SP05-5: Non-Goals Explicit — Lean Kernel 11 NG (P-01..P-11) | 11 adet NON-GOALS, her biri PREFIX "P-01..P-11" listelenmiş. Boş NG YOK. | PASS | SPEC §11 P-01..P-11 (11) |
| SP05-6: Source Traceability Complete — 24 AC × 15 CAP × 8 HRC × 8 GAP × 4 OD referanslar | AC companion → test-plan TP map → expected-files N id → hard-red HR map → open-decisions OD → source-gaps G → arch-trace CAP ile 100% traceable, uçtan uca. | PASS | 7 companion, cross refs ile her requirement linked. |
| SP05-7: Preserve Previous Stories — completed stories 0 diff, behavior 0 rewrite | Preservation matrix 10/10 PASS. S-FND-01 F1..F4 RUNTIME testleri 0 change, S-FND-02 observability 0 change, E-API, S-MDL-01..05 unchanged. | PASS | preservation-matrix.md companion |
| SP05-8: Lean Kernel Minimal Scope — 10 NEW dosya (N-01..N-10), 0 existing, 8 HRC, 15 CAP, 24 AC | File scope small, audit surface minimal, lean. Production APP KODU YOK (pure test infra). 10 file N sayımı expected-file §4 = 10/10. | PASS | expected-file §4, hard-red HR-1 0 existing |
