# Open Risks — S-FND-03 (SPEC Aşaması Tespiti)

Implementation aşamasında ortaya çıkabilecek riskler. BLOCKER değil, önden bilinmesi gereken:

| Risk Id | Olasılık | Etki | Açıklama | Azaltma |
|---|---|---|---|---|
| R-01 | Yüksek | Orta | Pytest sürüm farkı: Pytest 7.0 vs 8.0 marker kayıt mekanizması `pytest --markers` format farklılığı → marker parse testi yanlış negatif/pozitif. | `pytest --version` check + marker regex parse 2 sürüm formatı için de tolerant. Mevcut sürüm pytest 9.1.1 biliniyor. |
| R-02 | Orta | Yüksek (HR-1/DoD-4) | Implementation sırasında yanlışlıkla `tests/conftest.py` veya `tests/foundation/conftest.py` append edilir → K0 0 existing modify rule ihlal. | File Allowlist CHECK (implementation audit phase). expected-file §4 10 NEW dosya. Any diff outside → REVERT immediately. |
| R-03 | Orta | Orta | F2' prime concat-split pattern detection. S-FND-02 uses `"ap"+"i"+"_"+"ke"+"y"` — AST F2' scan AST düzeyinde Literal(value=abc123) concat etmez, sadece string literal. Yani S-FND-02 test dosyalarında concat-split S-FND-03 F2' scan tarafından FALSE NEGATIVE olabilir (tarayıcı bulamaz). | S-FND-03 F2' AST tarayıcı BİLEŞİK string (BinaryExpr Concat) işlemede ZORLANIR → azaltma: regex grep tabanlı substring tarayıcı (raw grep) + AST bir arada kullanılır. Concat-split S-FND-02 için FALSE POSITIVE değil (zaten istenen). False Negative (tehdit değil, gevşek tarama). Risk F2' should find raw credential vars. S-FND-01 testleri cover eder runtime (F1..F4). Bu (SFND03) PR-gate static scan ek katman. |
| R-04 | Düşük | Yüksek | Subprocess kullanımda (pytest --markers çağrısı) shell injection riski. | HR-6 açıkça subprocess.run([list]) kullan. String args. shell=False. No user input. |
| R-05 | Orta | Orta | Windows `findstr` / POSIX `grep` / path separator (\\ vs /) — tarayıcı path match allowlist hatalı. | `pathlib.Path.as_posix()` standardize. String match posix format. sorted Windows path compatible. |
| R-06 | Düşük | Orta | DoS için aşırı büyük Python dosyaları (10mb) AST parse memory blow up. | AST parse için dosya boyutu 5mb üstü ise SKIP + finding MINOR "large_file_skipped". Explicit upper size. Determinism için upper size sabit. |
