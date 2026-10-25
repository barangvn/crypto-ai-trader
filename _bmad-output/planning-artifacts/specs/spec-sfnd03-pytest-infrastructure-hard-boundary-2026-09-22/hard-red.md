# Hard-Red Constraints — S-FND-03 (8 HRC)

Tüm 8 kural ZORUNLU. Audit aşamasında 8/8 PASS olmadan implementation geçmez.

| HR # | Kural | Kaynak | Audit Ölçümü |
|---|---|---|---|
| HR-1 | **0 Existing Modify (K0):** Mevcut git-tracked baseline **1,720** dosyadan (`git ls-files` = 1720; app/ 125, tests/ 412, configs/ 5) HİÇBİRİNİ değiştirme. `git diff HEAD` — existing tracked files (özellikle tests/conftest.py, tests/foundation/conftest.py S-FND-02, tests/failure/*, tests/registry/*, pyproject.toml, configs/*, app/ platform contracts risk simulation strategies features regime processing ingest governance proof — output EMPTY) except NEW N01..N10. | SPEC §12, DoD-4 | `git diff --stat` existing sayısı = 0. |
| HR-2 | **No Network Live (applies also test infra OWN CODE):** S-FND-03 10 NEW dosya içinde `requests/httpx/aiohttp/websocket/urllib3/socket` import SAYISI 0. (Not: F1' scan BULUR ama kendi kodu network kullanmaz.) | SPEC §9 S-4, §12 HR-2 | grep 0 match 10 new file. |
| HR-3 | **No Credential Leak Scan Output:** F2' scan çıktısı stdout/stderr/json report — credential VALUES asla görünmez; `REDACTED:sha256[:6]` maskeli, ya da sadece dosya/satır + RULE_ID görünür. Hassas değerler NEVER print edilmiş. | SPEC §9 S-5 | Test mock key "MOCK_SECRET_123" scan sonrası output string search 0 match value. |
| HR-4 | **No Registry Mutation / No Governance Write:** app/governance/registry.py, events.py, storage.py gibi ANY registry write path — 10 NEW dosya import sayısı 0 (okuma bile yok, izole). | AD-23, §12 HR-4 | grep 0 match registry import. |
| HR-5 | **Stdlib Only (+ pytest existing):** NEW 10 dosyanın import listesi: (stdlib 12 adet: ast, re, pathlib, hashlib, json, subprocess, dataclasses, typing, os, sys, collections, itertools) + pytest (mevcut). 3. PARTY YENİ BAĞIMLILIK 0 (pydantic, rich, pyyaml, click, fastapi vb. eklenmez) → pyproject.toml 0 diff (HR-1 uyumlu). | SPEC §12 HR-5, §4 external dep none | pyproject diff 0. Import scan 0 new 3party. |
| HR-6 | **No Unsafe Dynamic Exec:** NEW dosyalarda `eval(` / `exec(` / `pickle.` / `yaml.load` / `subprocess shell=True` SAYISI 0. `subprocess.run([...])` ile KULLANILABİLİR (arg listesi, shell=False, capture_output=True, check=True yalnızca `pytest --markers` gibi güvenli beyaz liste komutlar için). | SPEC §12 HR-6 | grep 0 match unsafe + subprocess beyaz liste validation |
| HR-7 | **Completed-Story 0 Diff Continue:** S-FND-02 commit (`d02f58b`) sonrası NEW **8** production under app/platform/observability + **6** test under tests/foundation = **SAYI 14** → 0 byte diff. HR-7 on top of HR-1 for completed stories. E-API commit 80933f8 NEW files under app/platform/api/* — 0 diff. S-FND-01 e1bdff7 configs/* test env separation — 0 diff. | HR-1 kapsama alanı + üstü denetim | 3 completed story git diff check 0 |
| HR-8 | **Registry General Write Invariant (AD-23):** SFND03 kodunda ANY registry status mutate etme, ANY `ModelVersion` obj create/update etme, ANY lifecycle event publish etme — 0 import 0 call. | AD-23, §12 HR-4 genişletme | AST scan 0 registry-write path |

---

## AS-BUILT Reconciliation Notları (Görev H)

> - **HR-1 (m1 — DOCS INCORRECT, çözüldü):** "2000+" doğrulanmamış planning tahminidir. Kanıt: `git ls-files` = **1,720** tracked dosya (repo-wide), app/ 125, tests/ 412, configs/ 5. SPEC §12 HR-1'deki "1400+ test dosyası" ifadesi (tests/ = 412) ile tutarsızdı; her iki doküman da gerçek baseline sayısına hizalandı.
> - **HR-7 (M3 — DOCS INCORRECT, çözüldü):** S-FND-02 teslimatı `git show --stat d02f58b` = `14 files changed, 2020 insertions(+)` → **8 production** (app/platform/observability) + **6 test** (tests/foundation). Önceki "9 production + 6 test = SAYI 15" aritmetik olarak yanlıştı; doğru toplam **14**. Bu düzeltme yalnızca S-FND-03 dokümanındadır; S-FND-02 belgelerine dokunulmadı.

---

## Masking for SFND03 F2' — 8 MANDATORY KEY CASES (F2' scanning rules — different from S-FND-02 masking)
S-FND-02 masking 10 mandatory (key+value prefix). SFND03 F2' scan SADECE KEY ADLARINI tarar (value prefix SPEC GAP G-3 future):
1. `api[_-]?key`
2. `secret[_-]?key` / `secret` alone (C-3 legacy sorununa dikkat: test fonksiyon isimlerinde substring false positive için AST regex değil def/assignment TARGETLAMA)
3. `password`
4. `access[_-]?token`
5. `credential`
6. `private[_-]?key`
7. `BINANCE[_-]?API[_-]?KEY` (EPICS L227 explicit)
8. `OKX[_-]?KEY` (EPICS L227 explicit)

= Tam 8 zorunlu. >8 ise ekstra varsa documented. <8 ise BLOCKER. EPICS L227 4 tane verdi; regex genişletildi 8'e, OK.
