# Architecture Traceability — S-FND-06

## AD Mapping — 25 AD'den 15 Doğrudan Bağ

| AD ID | AD Başlığı | S-FND-06 ile Bağlantı |
|---|---|---|
| **AD-1** | Modular Monolith Topology | Helper'lar `app/contracts/` bounded context altında; tek module; microservice bölünmesi YOK. |
| **AD-2** | Exchange Boundary | Helper'lar exchange-specific schema YOK. Symbol canonicalizer AD-2 boundary içindedir (normalizer port helper). |
| **AD-3** | Canonical Event Envelope | Tüm hikâyenin temel bağlantısı. Envelope serialization builders. AD-3 yazdığı 16 alan → CAP-SER-01/02/05 aracılığıyla serialize edilir. |
| **AD-4** | Live/Replay Parity | Deterministic serialization, fingerprint identity → backtest/paper sonuçları reproducible → parity sağlanır. CAP-1 bridge. |
| **AD-5** | Data Quality Hard Gate | QualityFlags builder, append_reason, degraded invariant → AD-5 kalite bayraklarının downstream taşınmasını helper'lar sağlar. CAP-2 bridge. |
| **AD-6** | Internal Event Bus First | S-PLN-01 bus'ın envelope dedup ihtiyacı → fingerprint helper (CAP-SER-02) + canonical JSON serialize bus message body için gerekir. DOWN-03. |
| **AD-8** | Regime Independent Service Boundary | Regime detector'leri kalite bayrağı okurken fingerprint ile event geçmişi → helper'lar altyapı. |
| **AD-10** | AI No Execution Authority | Helper'lar AI execution YOK; sadece scoring/serialization. No exec authority AD-10 preserve. |
| **AD-11** | Risk Engine Final Gate | Risk→order correlation fingerprint (CAP-4). Helper correlation_id + fingerprint trace → risk decision audit. |
| **AD-12** | Paper vs Future Live Boundary | Helper'larda `if run_mode == "live"` branch YOK (HR-11 + CAP-1 parity). No live leak. |
| **AD-13** | Portfolio Single Writer | PortfolioSnapshot fingerprint identity S-PTF-02/03 tarafından kullanılacak → reproducible PnL snapshots. |
| **AD-14** | Governed Learning Lifecycle | Model evaluation bundle fingerprint → reproducible evaluation. LIFECYCLE transition correlation trace. CAP-5 bridge. |
| **AD-17** | Correlation ID Traceability | `correlation_id`/`causation_id` string helpers + fingerprint → end-to-end audit AD-17. |
| **AD-19** | Failure Defaults to Safe Stop | Symbol/Instant invalid → raise ValueError, accept YOK. Helper'lar fail-closed → AD-19 safe stop uygulama katmanı. |
| **AD-20** | Testability Architectural Constraint | Tüm helper'lar deterministic fixtures + parametrize test edilebilir. 10x determinizm audit planı var. AD-20 doğrudan bağ. |

## CAP Bridge (Capability Proof — Helper Level)

| CAP ID | İsmi | S-FND-06 Bridge Yardımcısı | Nasıl kanıtlanır? |
|---|---|---|---|
| **CAP-1** | Live/Replay Parity | canonical_json determinism + fingerprint; parity branch tarayıcı (TP-12) → 0 branch. | 10x aynı input = aynı output + 0 `if run_mode` AST match. |
| **CAP-2** | Quality in Envelope Downstream Consumption | build_quality + quality builders + quality serialize → bayrakların downstream taşınması. | serialize → deserialize → bayraklar aynı. |
| **CAP-3** | Strategy Plugin Purity | Helper importları strategy tarafında yeniden yazılmaz; tek kaynak → strategy purity testleri tek yardımcıyı kullanır. | TP-12 AST scan 0 forbidden import. |
| **CAP-4** | RiskGate + PaperOrder Correlation | Fingerprint + correlation_id trace helper'lar. Risk decision → PaperOrder same corr ID + same fingerprint hash. | Integration test downstream (S-RSK-02) CAP-4. |
| **CAP-5** | Lifecycle Only Registry Mutation | LIFECYCLE transition payload fingerprint identity → reproducible lifecycles. S-MDL-05 CAP-5 evidence. | Helper serialize → yeniden aynı hash. |
| **CAP-6** | MVP API No Live Routes | Helper'lar E-API response canonical JSON olarak kullanır. API layer'da /execution/live routes YOK. (CAP-6 S-API-03 own test.) | Helper no network → E-API sadece consumer. |

## ADN Forward Map (Bağlı Açık Kararlar)

| ADN ID | S-FND-06 Etkisi | Not |
|---|---|---|
| ADN-01 | Exchange provider sembol → canonical_symbol helper ihtiyacı. | Doğrudan kullanılacak (DOWN-01). |
| ADN-02 | Symbol universe regex allowance. | SYMBOL_RGX 20/12 uzunlukları ADN-02 ile değişirse → upgrade contract version. |
| ADN-03 | Stale threshold numeric value. | Helper'lar threshold value process etmez, sadece reason code string tutar. Etki LOW. |
| ADN-07 | Fill model latency varsayımları. | Fingerprint timestamp identity → reproducible paper fill sims. |
| AdN-10 | Object storage URI format. | Snapshot artifact fingerprint 12 hex prefix → artifact name helper (DOWN-05 PTF). |

## EPICS Appendix B Priority Sırası Doğrulaması

B #9: S-RDH-01 first applied story. B #8 (önceki) S-PLN-01 bus. FND-06 = bu iki hikâyeden ÖNCE. FND-06 → S-PLN-01 → S-RDH-01. Sıra DOĞRU. Helper layer olmadan downstream stories yazılamaz.
