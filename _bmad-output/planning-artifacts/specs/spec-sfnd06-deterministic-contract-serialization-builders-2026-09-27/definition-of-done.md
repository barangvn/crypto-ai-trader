# Definition of Done (DoD) — S-FND-06

Implementasyonun TAMAMLANDIĞI olarak kabul edilmesi için aşağıdaki 10 kriterin HEPSİ sağlanmak zorundadır.

1. **AC 20/20 PASS:** `acceptance-criteria.md` içindeki 20 kabul kriterinden (AC-01..20) 20/20 executable PASS. SKIP sayısı ≤ 2 (yalnızca downstream henüz mevcut olmadan skip edilebilir; explicit skip marker required).
2. **Hard-Red 13/13 GREEN:** `hard-red.md` içindeki 8 proje genel + 5 hikâye özel HRC kuralı tamamı 0 violation. 13/13 PASS. Tek bir ihlal → DoD FAIL.
3. **Default Existing Modify = 0 Line:** K0 kuralı çerçevesinde EX istisna listesi BOŞ (bu hikâyede EXCEPTION yok). `git diff parent→HEAD -- app/contracts/__init__.py app/platform/config.py tests/conftest.py pyproject.toml pytest.ini tests/foundation_sfnd05/ tests/foundation_sfnd04/ tests/api tests/contracts tests/failure` satır sayısı 0.
4. **Allowlist Tam Eşleşme (Expected File Changes):** `expected-file-changes.md` içinde listelenen new production 6 dosya ve new test **16** dosya dışında **hiçbir new/modified tracked dosya yok.** Staged area size = **22** expected (6 prod + 16 test). Exact count match.
5. **Determinism Audit PASS:** Determinism 7 ölçüm (D-01..07) 10x tekrar hepsinde set len 1. 7/7 PASS. Audit raporu mevcut.
6. **Upstream Regression PASS:** S-FND-01..05 + E-API (06 hikaye dışı tamamlanan) test suitesi fresh run; 0 new FAIL (önceden bilinen L5 credential self-match failure hariç). 0 yeni regression.
7. **3rd Party Drift = 0 (Default stdlib-only):** pyproject.toml yeni runtime dependency eklenmedi. 3rd party import count new prod 6 dosyasında 0. OD-06-01 default stdlib korunmuş (eğer 3p seçilmişse explicit EX + pyproject 1 satır + ADN kaydıyla; default DRIFT YOK).
8. **Kullanım/Import Contract Public API Doğru:** `app.contracts.sfnd06_serialize.__all__` tam 18 isim (17 fonksiyon + 1 exception class; SPEC §6.1 gövde listesi). Eksik/fazla isim → FAIL.
9. **Signature Doğruluğu (Type Hint / SPEC §6.1):** Her public fonksiyonun positional-only, keyword-only, parametre isimleri ve dönüş tipleri, raise edilen exception subclass SPEC §6 Signature sözleşmesiyle %100 uyumlu. Parametre ismi farklıysa (örneğin `symbol_raw` yerine `raw`) → FAIL (downstream signature mismatch).
10. **Audit & Evidence Zinciri Tam:** §10 AUDIT 6 kanıt (AUD-01..06) için ayrı test veya dosya olarak kaydedilmiş, tekrarlanabilir. SHA-256 determinizm raporu, regex tek kaynak raporu, AST scan Raporu mevcut.

---

DoD geçemezse → implementation-phase'e geri dön. DoD sağlandığında → BLACKOUT COMMIT hazır (staging exact allowlist).
