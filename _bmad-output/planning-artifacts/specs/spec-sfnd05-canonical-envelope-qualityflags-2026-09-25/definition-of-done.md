# Definition of Done — S-FND-05 (8/8 HEADLINE)

Her başlık bağımsız olarak doğrulanabilir.

| # | Başlık | Doğrulama Yöntemi | PASS / FAIL kriteri |
|---|---|---|---|
| DoD-01 | 18/18 AC Executable Fresh Run | `python -m pytest tests/foundation_sfnd05 -v --tb=short` | 18/18 PASS, exit 0, 0 NEW fail regression |
| DoD-02 | Fail-Closed FC-01..08 çalışıyor | TP-03..07 tek fail-injection testleri | Her FC için ayrı test dosyası · exception tipi + message SPEC uyuşuyor |
| DoD-03 | Existing tracked file modification = 0 (EX listesi default BOŞ) | `git diff --name-only HEAD` + `git diff HEAD --stat` + 6 completed-story paths diff | EMPTY lines S-FND-05 implementation code. 0 modify. |
| DoD-04 | Determinism ≥ 10x 6 dimension | tests/foundation_sfnd05/test_sfnd05_determinism_audit.py 6 dimension @10x | `len(set(10 runs)) == 1` her boyut |
| DoD-05 | 0 new third-party runtime dependency | pyproject.toml deps check + scan_3rd_party_imports | `dependencies` == [] BEFORE AND AFTER. No pydantic installed unless exception approved by OD-05-01. If OD-05-01 = pydantic, dep ENUMERATED and EXPLICIT (no silent install). Default: stdlib-only. |
| DoD-06 | 8/8 PROJE + 5/5 HİKÂYE ÖZEL = 13 TOTAL HARD-RED | HRC grep scan (`test_sfnd05_hrc_sanity.py`; SR-01 yalnız S-FND-05 production seti üzerinde, diğer patternler `app/contracts` + `tests/foundation_sfnd05`) | 0 unexpected match. HRC-H5 (0 3p) stdlib-only default kural. PyYAML = 0 match. |
| DoD-07 | S-FND-06+ FUNCTIONALITY SCOPE DRIFT 0 | Grepped: registry mutation / order fill / paper engine / feature calcs / live ws / DB. | 0 match in app/contracts and tests/foundation_sfnd05. |
| DoD-08 | PyYAML Hikâye-Seveli SCOPE OFF (OD-05-04 Closed Permanent) | Scan app/contracts / test_sfnd05 : `import yaml|from yaml|_YAML_ENABLED\s*=\s*True` | 0 import / 0 True assign. OD-05-04 kendine ait (inherit FND-04 DEĞİL). |

Sonuç: DoD = 8/8 ise IMPLEMENTATION READY → YES.
