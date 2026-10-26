# Hard-Red Constraints — S-FND-04 (8 HRC)

Tüm 8 kural ZORUNLU. Audit aşamasında 8/8 PASS olmadan implementation geçmez.

| HR # | Kural | Kaynak | Audit Ölçümü |
|---|---|---|---|
| HR-1 | **0 Existing Modify (K0):** Mevcut production/test/config dosyalarından HİÇBİRİNİ değiştirme — KALICI GARANTİ. EX-01/EX-02 PERMANENTLY DROPPED via CLOSED CANONICAL OD-01/02. Başka EX yok. `git diff --name-only HEAD -- existing paths` → 0 lines (HER ZAMAN implementation fazı). | SPEC §12, DoD-4, §2 M-6, §17 CLOSED OD-01/02 | git diff filtered existing paths = 0 lines. |
| HR-2 | **No Network Live Own Code:** `app/platform/config/*` 6 new file içinde `requests/httpx/aiohttp/websocket/urllib3/socket` (gerçek network çağrısı yapan importlar) sayısı = 0. Config okur, ağdan config YÜKLEMEZ — local dosya. | SPEC §9 S-4, §12 HR-2 | AST/grep 6 files 0 matches import statements. |
| HR-3 | **No Credential Leakage:** Config dataclasses içinde ANY field value "AKIA..." / "MOCK_SECRET_..." / "BINANCE_API_KEY_VALUE" / len>=20 base64 görünümlü literal 0. Config, cred YÖNETMEZ; sadece safety kilidi okur. | SPEC §9 S-1, §12 HR-3 | Grep F2' 8 mandatory pattern scan NEW 13 files → 0 credential VALUE literals. |
| HR-4 | **No Registry Mutation / Governance Write:** 13 NEW dosyada `from app.governance` / `registry.` / `ModelVersion` / `request_transition` / `Champion` import SAYISI = 0. Config, governance state YAZMAZ / MUTATE ETMEZ. Sadece AD-7 tek owner. | AD-23, §12 HR-4 | AST import 0 match. |
| HR-5 | **Stdlib ONLY / 0 3P (PyYAML PERMANENTLY OFF CLOSED OD-01):** 13 NEW dosya import list: stdlib (configparser, json, dataclasses, typing, pathlib, os, hashlib, decimal). PyYAML = CIDDI IHLAL. Pydantic, tomlkit, attrs, loguru, dynaconf, click, pyyaml + DIĞER HİÇBİR 3. parti. `pyproject.toml [project.dependencies]` = BOŞ KALICI (HR-1 diff ile uyumlu 0 modify EX-02 DROPPED). | SPEC §3.1, §9 S-4, §12 HR-5, §17 CLOSED OD-01, §4 UP External default None | Pyproject diff KALICI 0. AST imports listed matched allowed stdlib list ONLY. pyyaml import 0. |
| HR-6 | **No Unsafe Dynamic Exec:** 13 NEW file içinde `eval(` / `exec(` / `pickle.` / `yaml.` (HERHANGI yaml kullanımı = IHLAL, OD-01 CLOSED) / `subprocess shell=True` SAYISI = 0. PyYAML KALICI KAPALI. subprocess kullanılırsa shell=False + list args + beyaz komut sadece. | SPEC §9 S-6, §12 HR-6, §8 FC-5, §17 CLOSED OD-01 | Grep 0 match yaml.*; eval/exec/pickle/shell True 0. |
| HR-7 | **Completed-Story 0 Diff (on top HR-1):** 4 completed story file list explicit byte diff 0. S-FND-01 14 file (HEAD e1bdff7) → diff lines 0. S-FND-02 NEW `app/platform/observability` **10 file** (⚠ AS-BUILT §21 MINOR-5: planlanan "9 file" düzeltildi; gerçek 10) → 0 byte diff. S-FND-03 NEW pytest.ini + 9 `tests/foundation_sfnd03` → 0 diff. E-API NEW `app/platform/api` (15 dosya; `tests/api/` 5 dosya) → 0 byte diff. | HR-1 üstü denetim, DoD-8 | 4 git diff SHA vs HEAD paths → EMPTY output. S-FND-02 144/144 PASS unchanged; S-FND-03 85/85 unchanged. |
| HR-8 | **Registry / Lifecycle Write Path 0 Import Call (AD-23):** NEW 13 file içinde ANY `registry = sys.modules[...]` / `setattr(registry, ...)` / `status=Champion` direct assignment / `lifecycle` publish sayısı = 0 (sadece config okur, registry YOK). | AD-23 (Single Writer Registry), §12 HR-4 genişletme | AST regex manual scan code patterns + grep registry mutation → 0. |

---

## F' PR-Gate (S-FND-03 scanner) Against S-FND-04 NEW Production Code — Exact Expected: 0 BLOCKER.

| Fence | Expected Finding | Reason Why Allowed / Notes |
|---|---|---|
| F1' (Network imports) | 0 finding allowed | Config okuma local file only. No ingest adapters. |
| F2' (Credential key strings LITERAL) | 0 BLOCKER finding expected (F2 allows field NAME allow_api_keys because NAME not VALUE; len threshold meaningful >=3, name false-positive guard: NAME LHS allowlist). Placeholder VALUE MOCK_ACCESS_ID_A in S-FND-01 configs (read only); config layer DO NOT write new credential values. | S-FND-03 N07 F2 len>=3 threshold + fixtures_skip skip pattern mevcutsa 0 finding. |
| F3' (Short / Lev > 1) | 0 BLOCKER expected. Config safety field `max_leverage_allowed = 1` in INI; Assignment target name. Config layer ONLY READS, not domain simulation short direction. | F3 scans: `direction="short"` assign; config layer field allow_short=False → 0 match pattern direction_name in safety lock (not inside trade order). Scanner app/ prefix ON → config layer scanned; pattern match expected 0. |
| F4' (Real order func names) | 0 expected. Config layer has ZERO "send_real_order" / "place_order_on_exchange". | F4' scan: 0 function def name match expected. |
