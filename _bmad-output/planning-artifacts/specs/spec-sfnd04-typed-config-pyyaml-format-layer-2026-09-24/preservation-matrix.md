# Preservation Matrix — S-FND-04 (4 Completed Stories + New Story = 5×5 Invariants)

LAW-7 (SP05): "Preserve all load-bearing claims." Yani: Tüm tamamlanmış hikâyelerin (E-API, S-FND-01, S-FND-02, S-FND-03) production/test kodlarının bytediff 0 garantisi; S-FND-04 yeni yazılacak kodlar mevcut hiçbir şeyi bozmaz.

## §1 — Baseline SHA Commit Reference (DOĞRULANDI)
K0: Mevcut tüm completed story dosyaları KESİNLİKLE değişmeyecek. Sadece NEW 13 dosya yazılacak.

| Story ID | Commit SHA | What it owns | Preserve |
|---|---|---|---|
| E-API MVP Surface | `80933f8a7feecfbcb63dc3da72b10f7f459baade` | `app/platform/api/` (2 write endpoint; 15 dosya), `tests/api/` (5 dosya) — ⚠ AS-BUILT §21 MINOR-5: planlanan `app/api/` + `tests/api_eapi/` yolları düzeltildi | ✅ ZERO MODIFY by S-FND-04 |
| S-FND-01 Env Separation | `e1bdff70134cc5e797e7901a10fe9f28924a5cdc` | `configs/config.{4env}.ini` (4 file), `tests/foundation/*.py` 4 env smoke | ✅ ZERO MODIFY (EX-01 DROPPED default) |
| S-FND-02 Observability | `d02f58ba99e57c66172828668a59305c4dae62ac` | `app/platform/observability/` (structured logger/metric nullsink json stdlib), `tests/foundation/` observability smoke | ✅ ZERO MODIFY |
| S-FND-03 Pytest Gates | `55fd13e5c794c748b5268bfd891d37968cf407b9` | `pytest.ini` (strict markers, 10x plugins), `tests/foundation_sfnd03/` 9 files F1'/F2'/F3'/F4' scanners | ✅ ZERO MODIFY. S-FND-04 production code tested under F1/F2/F3/F4 gates → 0 finding expected. |
| S-FND-04 (NEW, not written yet) | N/A (impl phase commit) | `app/platform/config/` 6 NEW + `tests/foundation_sfnd04/` 7 NEW = 13 files total | ✅ ZERO MODIFY TO OTHERS; own scope only. ⚠ AS-BUILT §21: implementation TAMAMLANDI @ commit `946a6b5` (13 files, 948 insertions, hepsi `A`); aşağıdaki satır artık PLANNED değil AS-BUILT'dir. |

## §2 — Preservation Matrix Row × Column = 0 Byte Diff (ZBD)

| ROW Story Owns → ↓ COLUMN Story Touches ↓ | E-API (80933f8) files touched? | S-FND-01 (e1bdff7) files touched? | S-FND-02 (d02f58b) files touched? | S-FND-03 (55fd13e) files touched? | S-FND-04 (NEW) files touched? |
|---|---|---|---|---|---|
| E-API (own) | ✅ ZBD self. No modify self. | ❌ NEVER. | ❌ NEVER. | ❌ NEVER. | ❌ NEVER E-API modifies FND-04 (reverse dep: 04 → E-API not vice). |
| S-FND-01 (own) | ❌ NEVER. | ✅ ZBD self. Default EX-01 DROPPED = ini 0 modify. | ❌ NEVER. | ❌ NEVER. | ❌ NEVER FND01 modifies FND04 (FND04 reads FND01 ini, not vice). |
| S-FND-02 (own) | ❌ NEVER. | ❌ NEVER. | ✅ ZBD self. OD-FND-04 SFND02 JSON-only preserved; FND04 YAML gate for config layer = separate scope. | ❌ NEVER. | ❌ NEVER FND02 modifies FND04. FND04 references OD mapping for log_level defaults only. |
| S-FND-03 (own) | ❌ NEVER. | ❌ NEVER. | ❌ NEVER. | ✅ ZBD self. pytest.ini STRICT MARKERS unchanged. S-FND-04 tests use existing markers only. | ❌ NEVER FND03 modifies FND04. FND04 runs UNDER FND03 gates (audit 0 finding required). |
| S-FND-04 (NEW owner) | ❌ NEVER ✅ ZBD verified (no E-API file in SPEC allowlist N-01..13). | ✅ EX-01 PERMANENTLY DROPPED (CLOSED OD-FND-04-02). 4 ini = 0 modify. ✅ ZBD KALICI GARANTİ. | ❌ NEVER ✅ ZBD (no observability path in N-01..13). | ❌ NEVER ✅ ZBD (no pytest.ini or sfnd03 test path in allowlist). | ✅ NEW writes only N-01..13 = 13 files, exact count. |

## §3 — Pre-Existing Regressions (2 items, UNCHANGED / Out of Scope)
Aşağıdaki 2 başarısız test S-FND-03 sonrası mevcut (baseline), S-FND-04 HİÇ etkilemez: preservation invariant = unchanged.

| Pre-existing Reg Fail ID | Test Path | Why Unchanged | Preservation Expectation |
|---|---|---|---|
| REG-1 | `tests/failure/test_no_credentials.py` (2 matches credential literal) | Kaynak: tests/registry/test_smdl01_19_safety_boundary L147/L162 fixed literals (CRED SCANNER false positive — user workaround = runtime concat, NOT YET APPLIED). S-FND-04 config layer credentials NEVER imports registry; so 0 impact. | UNCHANGED: FAIL count same (2) pre/post S-FND-04 impl (±0). |
| REG-2 | env=TEST pipeline runs fail; env=DEV pass | Cause: baseline environment TEST section value not in INI (S-FND-01 completed behavior). S-FND-04 typed mapping default: section yoksa defaults düşer — yani DEV passes still; TEST status unchanged. | UNCHANGED: env=TEST behavior identical (no regression introduced). |

## §4 — CAP ID Collision / Stability (SP05 Law-6 "CAP IDs stable unique")
S-FND-04 CAP-01..CAP-10 (current vs future companion 'lean kernel capabilities'): NO collision with S-FND-01/02/03 existing CAP IDs (S-FND-03: F1'..F4' prime scanner IDs; S-FND-02 AD observe; S-FND-01 4env; all different namespace).

| ID Namespace | Scope | Collision Expected |
|---|---|---|
| CAP-SFND04-01..CAP-SFND04-10 (10 lean kernel now) | Current mandatory | ✅ NO: prefix `CAP-SFND04-` unique. |
| AC-SFND04-01..AC-SFND04-24 (24 AC) | Acceptance Criteria | ✅ NO: prefix `AC-SFND04-` unique. |
| FC-1..FC-8 (8 fail-closed) | S-FND-04 only | ✅ NO: S-FND-02 FC IDs OD scope different; S-FND-03 F1'..F4' = different. |
| N-01..N-13 (Allowlist NEW) | 13 files | ✅ NO: Not in other stories' allowlists. |

## §5 — Invariant Claims (Preservation Pass — 6/6 Source Claims Landed)
Aşağıdaki 6 kaynak iddia SPEC'te yerine oturdu. Auditte doğrulanır:

| # | Source Claim | SPEC Section Landed | Verification Method |
|---|---|---|---|
| P-1 | EPICS L185: "contract_version (1.0.0) + proje sürüm sabitleri teslim edilmedi" (unimplemented) → S-FND-04 teslim eder. | §1 Intent + §2 M-1 + §6.1 VersionConstants frozen | Import test + assert equality literal "1.0.0". |
| P-2 | S-FND-02 SPEC L411/L84/L262: OD-FND-04 PyYAML FUTURE C3 kararı SFND02 tarafından TASINMAZ, ACIK KORUNUR. | §3.1 + §9 S-4/S-6 + §14 DoD #5 + §17 CLOSED OD-01 PERMANENTLY OFF + §8 FC-5 RuntimeError exact message | Test T19: exact RuntimeError string == §7 D-3 literal. F4 scan pyyaml import=0. |
| P-3 | PRD §1 + S-FND-01 C2: safety kilitleri 4 tane strict closed (allow_api_keys=false, max_leverage=1, allow_short=false, trading_perm=false) | §6.2 EnvSafetyLocks + §8 FC-3 (4 safety violations fail-closed) + §9 S-2/S-5 | TP-03 4 fail-closed tests T13..T16 raise ConfigValidationError. |
| P-4 | ARCH AD-18 4 env (dev/test/stg/paper-prod) — başka ortam yok. | §6.3 AppConfig.env_name Literal 4 + §5 UP-01 4 INI dosyaları | TP-02 T08 distinct 4 + T12 unknown raises ValueError. |
| P-5 | OD-FND-04-01 CLOSED 5 kaynak: PyYAML PERMANENTLY OFF. EX-02 pyproject dep add DROPPED. (pyproject deps=[], F4 fail_closed pyyaml, SFND02 HR5 L82, SPEC HR5, EPICS L185 no yaml req.) | §17 CLOSED OD-01 + §12 HR-1/5 + expected-file §2 EX-02 PERM DROPPED + §2.1 K0 guarantee | pyproject.toml L5 diff=0. F4 marker 6 NEW files = 0 finding. yaml import 0 NEW 13 file. |
| P-6 | OD-FND-04-02 CLOSED 4 kaynak: EX-01 INI section append PERMANENTLY DROPPED (0 modify). (SFND02 EX DROPPED ACCEPTED L106/150, SFND02 OD-B defaults, 4 INI real sections YOK + PASS, K0 default=0.) | §17 CLOSED OD-02 + §12 HR-1 + expected-file §2 EX-01 PERM DROPPED + §2.1 K0 guarantee + preservation L21/L24 ZBD | 4 INI git diff SHA e1bdff7 → HEAD = 0 lines. AppConfig default section drops loader rule PASS. |

**6/6 CLAIMS VERIFIED (LANDING: PASS). 2 NEW CLAIMS P-5/P-6 added after CLOSED CANONICAL ODs.**
