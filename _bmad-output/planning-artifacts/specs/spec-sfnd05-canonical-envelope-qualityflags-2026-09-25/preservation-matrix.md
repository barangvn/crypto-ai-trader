# Preservation Matrix — S-FND-05

Satırlar: Completed stories / Upstream artifacts.
Sütunlar: Davranış değişikliği riski · Dosya değişikliği riski · Contract dependency (yeni FND-05 eskisini kullanır mı) · PyYAML devralma riski · Özet koruma / drift risk.

KURAL: Mevcut completed story davranışları DEĞİŞMEZ. EX listesi default BOŞ.

| Öğe (Row) | Davranış Değişir mi? (Y/N Default N) | Existing File Modify Risk? (0/N) | Contract Dependency (FND-05 → ONES ÜSTÜNDEN?) | PyYAML Inherit Risk? | Not / Koruma Mekanizması |
|---|---|---|---|---|---|
| **S-FND-01** (Monolith Skeleton 4 env INI) | Hayır (N) | 0 (4 env INI app klasör FND-01 oluşturdu; hiçbiri app/contracts değiştirmez) | Sembolik: 4 env FND-04 read_env ile; FND-05 RunMode sadece enum. DB namespace 4 distinct → FND-04 AppConfig.db_namespace != envelope.symbol (AD-18). | Sessiz YOK. FND-04 sadece config. FND-05 PyYAML OD-05-04 kendi closed var. | Default: 0 modify. Sadece YENİ klasör app/contracts. |
| **S-FND-02** (Logging + Correlation hooks) | Hayır (N). Logger correlation_id propogate — bu hikâyedeki envelope.correlation_id aynı isimde. Alignment. | 0 (app/platform/observability dokunulmaz). | Sembolik: correlation_id alanları AYNI ISIM → alignment avantajı, çakışma yok. | No effect. S-FND-02 0 pyyaml. | 0 drift. Same field name = avantaj. |
| **S-FND-03** (Pytest infra + 4 F forbidden pattern) | Hayır (N). Pytest markers: `contract`, `replay`, `failure_injection`. Yeni testler FND-05 `contract` markerını kullanır. Test fixture'ları extend ETMEZ yeni fixture'lar. | 0 (pytest.ini DEĞİŞMEZ. Sadece yeni dosya tests/foundation_sfnd05/_sfnd05_markers.py yoksa default — already FND-03 markers var.) | Contract testler FND-03 F1/F2/F3/F4 scan'ından GEÇER. | No. FND-03 F5 (pYYAML) SİLİNDİ (S-FND-04 yok). FND-05 HR-05 0 3p stdlib. | 0 modify. Alignment markers existing. |
| **S-FND-04** (Typed INI + VersionConstants "1.0.0") | **Davranış AYNI**. Envelope.contract_version == "1.0.0" (aynı). S-FND-04'te değişiklik YOK. | 0. Sadece karşılaştırma test (AC-04). | **Zorunlu Contract Alignment.** VersionConstants.contract_version ↔ CanonicalEventEnvelope.contract_version dize UYUMLU. Aynı 1.0.0. | **KRİTİK: NO INHERIT RISK.** FND-05 PyYAML decision OD-05-04 KENDİNE AİT Closed. Sadece alignment test string. FND-04 loader.yaml gate FND-05 içinde OLMAZ. app/contracts import yaml YOK. | Alignment PASS. No inherit risk. OD-05-04 explicit closed. |
| **E-API** (MVP API 10 grup + 2 write) | Hayır (N). API request/response envelope LIFECYCLE forbidden routes S-CON-04. FND-05 app/contracts → API `correlation_id` / `contract_version` share. | 0 (tests/api veya app/platform/api dokunulmaz). | İleri doğru: E-API error envelope correlation_id artık ortak ULID_SORTABLE regex kullanabilir (gelebilecek enhancement, şimdilik 0 zorunlu değişiklik). | No effect. | 0 drift. |
| **S-MDL-01** Registry Foundation | Hayır (N). ModelVersion payload S-CON-02. | 0. tests/registry dokunulmaz. | Sadece model_id payload null. | No. | |
| **S-MDL-02** Evaluation Compare | Hayır (N). ModelEvaluation payload S-CON-02. | 0. | | No. | |
| **S-MDL-03** Promotion Gate | Hayır (N). Payload S-CON-02. | 0. | | No. | |
| **S-MDL-04** Rollback | Hayır (N). Payload S-CON-02. | 0. | Lifecycle state 6 enum. | No. | |
| **S-MDL-05** CAP-5 Proof | Hayır (N). request_transition S-CON-04. | 0. CAP-5 status mutation S-CON-04 story. | Status alanı ModelVersion.payload içinde. | No. | |
| **tests/contracts/** (Existing contract tests) | Hayır (N). Sadece yeni dosya tests/foundation_sfnd05/ altında. Existing tests/contracts/* değişmez. | 0. | Common helpers (helpers.sha_json) reuse. FND-04 _helpers.py import → 0 existing change, new import reference only. | No. | |
| **tests/failure/** (Fail injection) | Hayır (N). Fail injection FC-01..08. | 0. | Yeni testler benzer kalıp. | No. | |
| **tests/replay/** + **tests/backtest/** | Hayır (N). RDH-01/BKT-01 downstream. | 0. Payload generic T deferred. | No. | |
| **S-CON-02** (Future 19 payload) | HAZIRLIK YAPILIR ama payload schemas implement edilmez. | 0. | Generic[T] envelope payload → payload typings deferred. | No. | Yeni hikâye downstream. |

### Risk Özeti:
- **Toplam existing file modify riski: 0.** Her satır = 0 file modify (EX listesi boş, sadece YENİ app/contracts/ ve tests/foundation_sfnd05/ new).
- **Completed story behavior drift: 0.** Alignment S-FND-04 1.0.0 string aynı; S-FND-02 correlation_id same isim; S-FND-03 markers existing.
- **PyYAML inherit risk: 0.** OD-05-04 KENDİ closed permanent. Sadece alignment test.
- **Scope drift S-FND-06+: 0.** HRC SR-01..05 8/8 scan payload/bus/live/execution/registry YOK.

Preservation = **PASS 14/14 rows (10 completed story + 3 test-dir + 1 future) 0 drift 0 modify.**

### Option C Sınırı (OD-05-09) — Legacy Tip Ailesi Korunur

S-RDH-01 (`9ec9106`) tarafından oluşturulan `app/contracts/canonical.py` legacy tip ailesi (`CanonicalEventEnvelope`, `QualityFlags`) ve mevcut tüketicileri Option C kapsamında KORUNUR; S-FND-05 bu dosyayı değiştirmez (0 modify). S-FND-05 kanonik tipleri ayrı dosyalardadır (`app/contracts/envelope.py`, `app/contracts/quality_flags.py`; public yol `app.contracts.sfnd05_api`) ve iki aile arasında örtük dönüşüm varsayılmaz. Ayrıntı: `open-decisions.md` OD-05-09.
