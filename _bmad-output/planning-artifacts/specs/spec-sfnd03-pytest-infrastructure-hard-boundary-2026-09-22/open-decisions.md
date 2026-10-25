# Open Decisions — S-FND-03 (OD-01..OD-04)

Bu kararlar IMPLEMENTATION aşamasında SESSİZCE ÇÖZÜLMEZ. Her biri için:
- (a) kullanıcı/domain onayı, (b) SPEC MD update, (c) ark-traceability güncelleme, (d) audit öncesi kanıt bağlama.
OD "açık" = default behavior BU HİKÂYEDE change YAPMAZ, aşağıdaki her madde CAP davranışını etkilemez (non-blocking, future).

| OD # | Başlık | Default Davranış (OD kapansa kadar) | Risk/Not |
|---|---|---|---|
| OD-01 | 4. ve sonrası pytest.markers ekleme (ör `@pytest.mark.performance`, `smoke`, `data_quality`, `slow`, `fast`). | DEFAULT: 3 marker (contract/replay/failure_injection) dışında 4. marker YOK. Eğer bir test `@pytest.mark.smoke` konursa; SPEC §2 M-4 uyarınca — audit aşamasında `pytest --markers` 3'ten fazla custom marker listelerse FAIL sayılır. Gelecekte marker ekleme için SPEC change request zorunlu. | Risk: Downstream hikâyeler (S-FEA-01, S-REG-01) acil marker ihtiyacı → çözüm: `failure_injection` parent marker kullanılabilir; yeni marker için SPEC update. |
| OD-02 | CI pipeline konfigürasyonu (Github Actions / GitLab CI / Azure DevOps) — PR'da hangi marker setleri çalıştırılır? `-m contract`, `-m "contract and not replay"`, full regression, PR-gate scan mandatory mı? | DEFAULT: CI pipeline YOK. Pytest marker çalışması LOCAL user a bağlı. PR otomasyonu SFND03 tarafından yazılmaz (Non-goals P-03). | Gelecekte CI yazılınca `contract` + `pr_gate_scan` markerları mandatory; `replay` opsiyonel. |
| OD-03 | PYTEST plugin auto-load sandbox (pytest plugins 3rd party) — default plugin loading (pytest-cov, pytest-xdist, vb.) marker çalışmasını etkileyebilir mi? | DEFAULT: dokunulmayan (pytest default, no change K0). Eğer plugin collision → marker testi FAIL olur ve OD-03 kapatılır (pytest.ini add `addopts = -p no:xdist` gibi explicit pluginoff. | Risk: Düşük; plugin marker isimleri (cov, xdist) SFND03 ile collision yapmaz. |
| OD-04 | Parse engine seçimi: pytest.ini okurken Python sürümü 3.10 vs 3.11 — `tomllib` (3.11+) stdlib TOML, ConfigParser (3.8+) INI. | DEFAULT: ConfigParser stdlib INI. pyproject.toml marker ekleme YASAK (HR-1 K0). pytest.ini INI format → ConfigParser her Python 3.8+ sürümde çalışır. TOML kullanma ihtimali 0. | Gelecek Sürüm Python 3.13+: pytest.ini still çalışır, problem yok. |
