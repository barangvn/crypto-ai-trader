# Source Gaps — S-FND-04 (8 MADDELİ KANIT: NO FABRICATION)

YASAK: Herhangi bir source gap → mandatory requirement / hard threshold / algoritma ICAT EDİLMESİN. Aşağıdaki 8 gap DEFERRED / OPEN / NOT THIS STORY olarak açıkça işaretlenmiştir. Eğer downstream bunları zorunlu kılırsa, o hikâyenin SPECinde OPEN DECISIONS veya EXCEPTION listesinde çözülür — FND-04'te ZORUNLULUK YOK.

| Gap # | Konu | Neden Eksik? (Source Check) | Nasıl İşaretlendi (Davranış) | Future Hangi Hikaye Çözer? |
|---|---|---|---|---|
| G-01 | Numeric latency/recovery/data-loss thresholds for config read timeout. | PRD §7 & §9 NFR-001 sayısal eşikler ADN olarak açıkça deferred. INI okuma local disk; timeout kavramı yok (file read sistem timeout). S-FND-04 için: source YOK. | NOT THIS STORY. ConfigFactory: local file read → OS default file timeout (hiçbir explicit timeout set edilmez; subprocess/file timeout config YAZILMAZ). | E-PLN (internal pipeline durability - PG outbox timeout) veya S-RDH (data source health timeout). |
| G-02 | Scoring / opportunity / promotion explicit numeric thresholds. | PRD §7 NFR thresholds all deferred ADN. FND-04 config layer: SADECE FND alanları (env/safety/observability/platform_contract). Risk/Strategy/Score specific DEĞİL. | NOT THIS STORY. extension_sections: dict[str, Any] ile downstream kendi sectionlarını register eder; FND-04 İCAT ETMEZ sadece taşıyıcı mekanizma. | E-AIS (SCO-01), S-RSK (RSK-03), S-MDL. |
| G-03 | YAML File include / reference / inheritance syntax. | OD-FND-04-01 PyYAML DEFAULT = KAPALI. Include pattern için source YOK (CONTRACTS/EPICS/PRD hiç söylemiyor). | NOT THIS STORY. OD-01 = kapalı → include pattern ZORUNLU DEĞİL. YAML açılsa bile: basic safe_load; include G-03 deferred new story C-phase. | Eğer OD-01 açılırsa C-phase story "Config YAML include + validation". |
| G-04 | Audit-log immutability / hash-chain / append-only file storage for config-change events. | S-FND-02 SPEC §253 NG-5: "Audit immutability/hash-chain FUTURE SEC story". FND-04 aynı kuralı carry eder; doğrulandı. | NOT THIS STORY. ConfigReadAuditRecord list = in-memory; append-only file/hash chain İCAT EDİLMEZ. Future SEC-01 benzeri story. | SEC / Observability future. |
| G-05 | CI pipeline. GitHub Actions / GitLab / Azure DevOps / Docker container config. | S-FND-03 OD-SFND03-02 (CI = OPEN, defaults YOK). Doğrulandı: S-FND-03 SPEC §17 OD-02 CI = open; carry decision: FND-04 de CI YAML YAZMAZ. | NOT THIS STORY. 0 new .github/workflows/ / .gitlab-ci.yml / azure-pipelines.yml. Gelecek: DevOps / Release story. | Future DevOps/CI story. |
| G-06 | Multi-user authz / RBAC / permission config for admin UI write config. | PRD MVP: dashboard operator persona; write permission boundary (NFR-020) 2 write endpoint emergency-stop & kill switch. Genel config write endpoint Mevcut DEĞİL. | NOT THIS STORY. ConfigFactory: READ-ONLY (startup bir kez oku). No user auth / role / permission enum İCAT EDİLMEZ. | E-API (MVP API write permissions + future config write endpoint SPEC). |
| G-07 | Encrypted config fields / KMS envelope / Vault integration for secrets. | PRD §5.7 FR-062: "Future credentials: secrets manager, isolated keys, least privilege, access control, audit log, explicit trading permission gates." → explicit FUTURE. v1 allow_api_keys=false → credentials config alanı YOKTUR. | NOT THIS STORY. Config cryptography alanı: 0 import cryptography, Fernet, KMS, Vault. Şifreli dosya okuma DEĞİL. Gelecek future creds story. | Future SEC-vault / Credentials Management story (after v1 boundaries). |
| G-08 | Exhaustive list of ALL future extension sections for ALL 14 Epics. | 14 Epic / 41 story — her birinin config alanları kendi hikayelerinin SPEC'inde tanımlanır. Bütün config alanlarını FND-04'te tahmin etmek imkansız + scope ihlali. | NOT THIS STORY. extension_sections: dict[str, Any] = downstream register sonrası kullanılır; exhaustive list İCAT EDİLMEZ. Sadece 4 FND section (env/safety/observability/platform_contract) typed. | TÜM hikâyeler (E-RDH/E-FEA/S-REG/... kendi section field list ve defaultlarını SPEC'lerinde tanımlar). |

---

## Summary (Law 7 - Preservation / Source Gap Count)

- **TOPLAM GAP: 8.**
- **Hiçbiri ZORUNLULUĞA DÖNÜŞTÜRÜLMEDİ.** Tümü: NOT THIS STORY / DEFERRED / OPEN.
- **KAYNAKSIZ ICAT: 0 (NO FABRICATION).** Threshold, security rule, algorithm, dependency, SLO, retention — HEPSİ source dayalı veya explicitly gap bırakıldı.
- **8 GAP, 8 explicit deferred marker:** ✅ Eşleşiyor 8/8. (User Kural: "8 source gap requirement'a dönüştürülmeyecek.")
