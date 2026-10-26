# Definition of Done — S-FND-04

All 8 DoD items TRUE before story closure.

| DoD-ID | Kriter (Pass = TAMAMLANDI) | Kaynak | Nasıl Ölçülür |
|---|---|---|---|
| DoD-1 | Production NEW klasör tam: `app/platform/config/__init__.py`, `constants.py`, `models.py`, `loader.py`, `validation.py`, `errors.py` = 6 dosya. 0 dosya eksik. | SPEC §3.1, §14 | LS count 6 under app/platform/config/ |
| DoD-2 | Test NEW klasör tam: `tests/foundation_sfnd04/__init__.py`, `conftest.py`, `_helpers.py`, 4 test modülü (`version_constants`/`config_typed`/`validation`/`determinism_audit`) = 7 dosya TOPLAM. | SPEC §16 expected | LS count 7 under tests/foundation_sfnd04/ |
| DoD-3 | S-FND-04 tests PASS: `python -m pytest tests/foundation_sfnd04 -v --tb=short` → **0 FAIL** (tüm AC-01..AC-24 executable, 0 XFAIL/XPASS dışı). Regression AC-24 0 NEW fail. | SPEC §2 M-1..M-6, §13 | Run pytest, count fails == 0. |
| DoD-4 | K0 HARD ZERO existing modify: `git diff HEAD -- configs app/platform app/ingest app/contracts app/processing app/decisioning app/simulation app/governance tests/conftest.py tests/foundation tests/failure tests/contracts tests/registry tests/backtest pyproject.toml` → BOŞ SATIR (0 existing diff). SADECE NEW file'lar staged. | SPEC §12 HR-1, §2 M-6 | Run git diff --name-only filtered → 0 lines |
| DoD-5 | Safety + fail-closed FC1..8: companion test planında FC1..8 8/8 PASS. (AC-13..19 kapsar.) | SPEC §8 FC | TP-03 + TP-04 |
| DoD-6 | Determinism 6D × 10: D1 version constant hash stable, D2 ConfigFactory read_env 10x stable, D3 ConfigValidationError sorted fields 10x message same, D4 extension_sections sorted stable, D5 audit json 10x same, D6 safety locks ordered → len(set 10x)=1 ALL 6 dims. | SPEC §7 D1..D6 | TP-05 determinism testleri (aşağıdaki AS-BUILT sayaç) |
| DoD-7 | HARD-RED 8/8 PASS: HR-1..HR-8 inventory/import/static regex scan 0 violation. SFND03 F1..F4 gate tarayıcı config NEW files 0 BLOCKER finding. | SPEC §12 HR-1..HR-8, §9 | See hard-red.md audit script output 8/8 GREEN |
| DoD-8 | S-FND-01/02/03 + E-API byte diff 0: 4 completed story NEW file list → `git diff (first story commit SHA) HEAD -- (their production paths)` → 0 byte changed; regression test suite S-FND-02 144/144, SFND-03 85/85, SFND-01 FAIL count unchanged (2 pre-existing). | SPEC §12 HR-7 | Git diff + pytest runs for each |

## ⚠ AS-BUILT STATUS (2026-10-25 doc reconciliation — §21 MINOR-1/2/8)
Yukarıdaki tablo PLANNED (pre-impl) kriterlerdir. As-built doğrulaması (commit `946a6b5`):
- **DoD-1:** ✅ 6 production dosyası mevcut (`app/platform/config/`: `__init__`, `constants`, `models`, `loader`, `validation`, `errors`).
- **DoD-2:** ✅ 7 dosya mevcut (4 test modülü + `__init__.py` + `conftest.py` + `_helpers.py`). Planlanan "4 test dosyası (version/env/validation/pyyaml)" isimlendirmesi as-built ile eşleşmiyordu (gerçek 4. modül `determinism_audit`); bu satır düzeltildi.
- **DoD-3:** As-built kanıt yalnız S-FND-04 grubunu kapsar: `pytest -p no:cacheprovider tests/foundation_sfnd04/ -q` → **90 passed, exit 0** (önceki taze Package C / K-3 turunda raporlandı; bu doküman turunda YENİDEN ÇALIŞTIRILMADI — yalnız `--collect-only` ile 90 test toplandığı doğrulandı). 51 test fonksiyonu pytest tarafından 90 teste toplanır (version_constants 6, config_typed 17, validation 46, determinism_audit 21). Bu sonuç tam regresyon DEĞİLDİR; AC-24 regression smoke ayrı kanıt gerektirir (bu turda toplanmadı).
- **DoD-6:** ⚠ Planlanan "TP-05 6D × 10 parametrize → 60 subtest" AS-BUILT'te YOKTUR. Gerçek: `test_sfnd04_determinism_read_env_10x` `_DET_ENVS` (4 env) üzerinden parametrize edilir, her run içinde inner 10-loop → **4×10 = 40 iterasyon**; `test_sfnd04_determinism_version_constants_10x` ve `test_sfnd04_determinism_validation_fields_sorted` her biri kendi iç 10-loop'unu çalıştırır; audit tek testtir. Tek bir 6×10=60 parametrize üretimi YOKTUR. (MINOR-8)
- **DoD-7 / DoD-8:** Bu turda doğrulanmadı (F' gate ve 4-story byte diff kanıtı toplanmadı).

## Commit öncesi BLACKOUT checklist:
- [ ] DoD-1..8 8/8 TRUE
- [ ] AC 24/24 executable PASS
- [ ] K0 0 existing modify except EX list (if any)
- [ ] OD list unchanged — no silent resolutions
- [ ] No S-FND-05+ features inside scope
- [ ] PyYAML KALICI KAPALI (CLOSED OD-01). pyproject diff KALICI 0; 3p dep YOK.
- [ ] git status staged count EXACT match allowlist N01..N13
- [ ] Push = 0
