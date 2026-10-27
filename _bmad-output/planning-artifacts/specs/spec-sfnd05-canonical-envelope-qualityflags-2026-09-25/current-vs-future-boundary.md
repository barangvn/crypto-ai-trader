# Current vs Future Boundary — S-FND-05

## CURRENT (MVP S-FND-05 ANİ) — NE YAPIYOR

| Bileşen | CURRENT (SCOPE) | IMPLEMENT |
|---|---|---|
| Envelope | CanonicalEventEnvelope[T] — 14 zorunlu + 2 ops = 16 alan. frozen dataclass generic[T]. payload = Any. post-init invariants: UTC-Z, clock_ref replay, timestamp != ingest_ts replay, symbol regex, enum set | ✅ BU HİKÂYEDE |
| Quality Flags | 7 bool (stale, missing, duplicate, out_of_order, invalid, quarantined, degraded) · reasons[] code/message/context · post-init degraded = any(others) invariant auto. | ✅ BU HİKÂYEDE |
| Ortak NewType & Enum | RunModeE (3), SourceTypeE (6 fixture ek), ContractVersionStr "1.0.0", Instant ISO UTC regex, ULID_SORTABLE 2 regex (ULID 26 base32 / UUID7), SymbolCanonical regex, ClockRefT/SchemaRefT/QReason nested | ✅ BU HİKÂYEDE |
| HARD-RED 13 | 8 proje + 5 hikâye özel scan | ✅ TEST |
| Determinizm 10x 6 dim | D-1 envelope hash, D-2 idempotent, D-3 degraded auto, D-4 regex, D-5 enum membership, D-6 alignment S-FND-04 | ✅ TEST TP09 |
| Fail-Closed 8 case | FC-01..08 eksik alan / UTC / replay / quality invariant | ✅ TEST TP03..08 |

**Kanonik tip sahipliği (Option C — OD-05-09):** Yukarıdaki `CanonicalEventEnvelope` / `QualityFlags` tipleri S-FND-05 kanonik tipleridir (`app/contracts/envelope.py`, `app/contracts/quality_flags.py`; public yol `app.contracts.sfnd05_api`). `app/contracts/canonical.py` içindeki aynı isimli legacy tipler ayrı bir sözleşme ailesidir; birbirinin yerine kullanılamaz ve aralarında örtük dönüşüm yoktur. Ayrıntı: `open-decisions.md` OD-05-09.

## FUTURE (Sonraki HİKÂYELER — OUT OF SCOPE S-FND-05)

| Bileşen | Gelecek Hikâye | Neden GECİKTİRİLDİ |
|---|---|---|
| **19 Event/Entity Payload Schema** (MarketTick/Trade/OrderBook Snapshot+Delta/Candle/MarketRegime/FeatureVector/StrategyContext/StrategySignal/OpportunityScore/RiskDecision/PaperOrder/PaperFill/Position/PortfolioSnapshot/ModelVersion/ModelEvaluation/LifecycleTransitionPayload/ChampionChallengerEvaluationPayload + LimitsSnapshot nested) | S-CON-02 | SR-01 HARD-RED. Her payload alan 100+ validasyon tek başına büyük hikâye. AD-22 FeatureVector flat-dict invariant S-CON-02-icinde enforce. CAP-3 StrategyContext S-CON-02. CAP-4 correlation RiskDecision↔PaperOrder S-CON-02. |
| CAP-1 Live/Replay parity SCANNER (5 module `if run_mode == ...` static tarayıcı + runtime fixture) | S-CON-03 | Branch tarayıcı modül ağacı regex. Sadece envelope alanları değil, downstream kod SCAN eder. Test scaffold ayrı hikâye. |
| API response envelope + EmergencyStop request bodies + Lifecycle forbidden routes + CAP-5/CAP-6 gates | S-CON-04 | E-API 10 grup + 2 write + LIFECYCLE grafik. Ayrı hikâye. |
| ULID concrete PRODUCER (id generation) / Replay Clock producer | S-RDH-01 | Producer vs type-gate ayrımı SR-03 HARD-RED. RDH-01 adapter normalizer yeni ULID üretir. |
| 9 Quality kuralı IMPLEMENTATION (stale threshold, neg fiyat kontrol, spread bps abnormal, duplicate dedup) | S-RDH-01 (Validator / DataQualityMonitor) | Burada sadece bayrak TİPLERİ. Logic / eşik ADN 1/2/3/7. |
| Event bus / in-process dispatcher / outbox / durability | E-PLN-01/02/03 | NG-09 out of scope. |
| Strategy plug-in / Trend + Momentum MVP 2 strategy | E-STR-01/02/03 | AD-9 pure plugin. |
| AI scoring / regime detector | E-AIS-01/02/03 | Sadece skor/confidence alanları payload içinde. |
| Risk limits / kill switch / correlation approval gate | E-RSK-01..04 | CAP-4 Risk engine. |
| Backtest / fill model / paper trading engine | E-BKT/E-PTR 01..03 | Execution simulator payload S-CON-02. |
| Portfolio PnL tek-yazar | E-PTF-01..03 | |
| Model lifecycle / registry | E-MDL-01..05 | LIFECYCLE payload schema + mutation gate. |

## FUNCTIONALITY DRIFT: SCOPE KILİTLİ (Boundary Enforcement)

- **S-FND-06? Yok.** Gelecek hikâyelerin payloads/bus/adapter — none burada.
- **S-CON-03/04?** Burada değil.
- **E-RDH? Burada değil.**
- **E-PLN? Burada değil.**
- **E-API / E-MDL / E-RSK / E-BKT / E-PTR / E-PTF / E-STR / E-AIS / E-REG? Hepsi burada YOK.**

Kural: 13 hard-red (HR-08 + SR-01..05) scan scope drift 0 match. Implementasyon sonrası 0 match ise doğrulandı.

## Kayan Yol Haritası: Sırada

1. S-FND-05 (BUDUR)
2. **S-CON-02** (19 payload schemas, FeatureVector flat invariant, CAP-3/CAP-4 schema-level enforcement)
3. **S-CON-03** (CAP-1 parity test scanner: 5 module `if run_mode` static scan test + runtime fixture)
4. **S-CON-04** (API envelope + LIFECYCLE transition graph + CAP-5/CAP-6 initial gates)
5. **S-RDH-01** (Replay POC + Normalizer + Validator (AD-5 9 kontrol) + minimal bus)
6. Sonra E-PLN / E-FEA / E-REG / E-STR / E-AIS / E-RSK / E-BKT / E-PTR / E-PTF / E-MDL-01..05 / E-API finalize — Sıra EPICS L154-169.
