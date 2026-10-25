# Source Gaps — S-FND-03 (8 MİRAS, SESSİZCE KAPATILMAZ)

Bu 8 açık gap proje genelidir; S-FND-03 HİÇBİRİNİ kapatmaz, sessizce requirement YAPMAZ. Audit aşamasında bu 8 maddenin herhangi biri SFND03 implementasyonu tarafından "kapatılmış" bulunursa SCOPE DRIFT MAJOR.

| G # | Gap Açıklaması | Önceki Sahiplik / Açılış | Neden SFND03 kapatmaz |
|---|---|---|---|
| G-1 | Vault / Secrets Manager integration (NFR-008, FR-062 credential gelecek) | SEC future story (SEC-01), henüz SPEC yazılmadı. | S-FND-03 sadece test tarayıcı — no production secrets manager; production HR-3 F2' tarama ama Vault integration KAPSAM DIŞI (P-01). |
| G-2 | Registry immutable hash chain + append-only audit log (AD-14, AD-23) | Model Governance, Registry future story. | SFND03 registry write path içermez (HR-4), chain YAPMAZ (P-08 production yok). |
| G-3 | Unified Shared Redaction Pattern Library — S-FND-02 `app/platform/observability/redaction.py` regex ve concat-split pattern ile F2' tarayıcı regexleri TEKRAR etmemeli. Future foundation shared lib (S-FND-04+) tarafından paylaşılmalı. | S-FND-02 / Foundation future. | S-FND-03 şu an 2 ayrı regex seti (Küçük risk, minimal duplicate) — GAP tutulur, kapatılmaz. Paylaşım için gelecekte S-FND-04. |
| G-4 | OTel / Prometheus Remote Write / Grafana Dashboard Export | E-API S-FND-02 GAP miras. | SFND03 test altyapısı — no metrics export, P-01 platform UI export YOK. |
| G-5 | F1..F4 Contract REDefinition — S-FND-01 mevcut 7 tests/failure/*.py safetytestleri. | S-FND-01 completed ownership. | Non-goals P-04: REDEFINITION YOK. SFND03 = farklı prime (F1'..F4'), farklı katman (collection/static scan). |
| G-6 | Dashboard UI — PR-gate scan sonuçlarını görselleştirme, trend report | S-FND-04+ Platform Dashboard gelecek story. | SFND03 sadece JSON report (SPEC §10 A-1) export eder. Görselleştirme YOK. Dashboard yok (P-01). |
| G-7 | Scan report retention / arşivleme / silme policy | Veri Yönetimi future story. | Retention eşikleri SPEC uydurulmaz (Non-goals P-09). Report JSON diske yazılır, saklanması — user sorumluluğu. |
| G-8 | Audit rotation — report append-only dosyası + integrity hash zinciri | Audit future story. | Rotation / hash zinciri YOK. Sadece her test run tek JSON. P-09: eşik uydurma yok. |
