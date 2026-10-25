# Current-vs-Future Boundary — S-FND-06 (Şimdi vs Sonraki Hikâyeler)

## CURRENT: Bu Hikâyede Neler Tamamlanır? (Helper Foundation Layer)

✅ Tamamlanacak şu anda:
1. JSON için **canonical serialization** (tek format).
2. **Deterministic fingerprint** 12hex SHA-256 prefix.
3. **Symbol canonical gate** (strict, 3 variant separator handle).
4. **Instant validate + fixture generator** (Z-suffix, UTC mandatory; NOW source production YOK; fixture only).
5. **Valid envelope builder factory** + quality flags builder; valid defaults + overrides; fail closed.
6. **ULID compare + validate.**
7. **Deterministic JSON equality helper.**
8. **Regex tek kaynak ya kopya ya import (K0 no modify 05).**

## FUTURE: Sonraki Hikâyelerde Neler Yaşar? (Ayrı Hikâyelerin Kapsamı — ŞİMDİ ALMA)

❌ **ŞİMDİ YOK — BU HİKÂYE DIŞI** (Future boundary):

| # | Gelecekteki Öğe | Hangi Hikâye? | Neden şimdi YOK? (Scope drift / non-goal) |
|---|---|---|---|
| 1 | **19 Payload-Specific builders** (MarketTick/Candle/StrategySignal/RiskDecision...) | S-CON-02 (19 payload schemas). | ÇOK geniş; her payload kendi builder'ını hak eder. FND-06 sadece ENVELOPE + QUALITY builders (payload generic Any). Non-goal 3. |
| 2 | **ULID/UUID7 concrete generator** (monotonic clock, thread-safe production ID üretimi). | S-RDH-01 ingest entrypoint (adapter module — owns NOW source). | HR-11 production now YOK; generator ID source tartışması ayrı hikâye. Non-goal 2. |
| 3 | **Event Bus Serialize/Dispatch, outbox, inbox, persistence** | E-PLN (S-PLN-01 typed bus, S-PLN-03 PG outbox). | Helper sadece bytes üretir; dispatch bus'ın işi. |
| 4 | **Binary formats (msgpack/pickle/protobuf/parquet)** | S-FND-08+ (Data Persistence Layer Helper FND). | JSON yeterli MVP + binary security = pickle riskli. Non-goal 1. |
| 5 | **3rd party hızlı JSON (orjson) / xxhash / pydantic v2 serdes** | Ayrı migration story (OP-06-01 explicit set 3p ise). | Default 0 dep; stdlib ok. Ayrı decision (OD-06-01) = explicit migration ise ayrı hikâye veya impl fazında tek EX satır. |
| 6 | **FeatureVector / Technical Indicator Deterministic Serialize** | S-FEA-03 (Deterministic FeatureVector generation). | FND-06 generic payload fingerprint verir; özel feature'ların kendisi S-FEA. Non-goal 11. |
| 7 | **Strategy purity / import tarayıcı** | S-STR-03. | Helper tarayıcı olarak kullanılabilir ama tarama itself S-STR-03. |
| 8 | **Database write / adapter / storage** | E-PLN (outbox) + E-RDH (replay data write) + E-MDL (registry). | Helper, serialization only; storage YOK. Non-goal 4. |
| 9 | **Real Exchange WS / REST adapter** | S-RDH-01 + S-RDH-02 adapter port. | Helper no network; adapter import eder helper'ı; tersi değil. HR-01 NETWORK YOK contracts scope. |
| 10 | **Model Lifecycle transition logic / promotion gate** | E-MDL (S-MDL-03/04/05 CAP-5). | Helper fingerprint + trace; transition logic itself MDL. |
| 11 | **API endpoint creation / Prometheus metrics / alerting** | E-API (S-API 01-04). | Helper sadece JSON bytes üret; API / metric downstream tüketir. Non-goal 13. |
| 12 | **Logging / Logger kurulumu / metric counterları** | S-FND-02 already completed. | Helper logger YAZMAZ; log araması caller yapar (non-goal 10). |
| 13 | **YAML serialization, config YAML read** | Ayrı hikâye (var olan S-FND-04/05/06 hepsi kapalı). | Kalıcı KAPALI (OD-06-03). Hard-red HR-06. |

---

### Geçiş Kontrol Noktası (Boundary Safety)
Eğer downstream (S-RDH-01 veya S-CON-02) impl aşamasında "bizim X helper'ına ihtiyacımız var" derse:
  1. Önce SPEC.md §3 IN/OUT boundary kontrol et → eğer listede YOKSA,
  2. Hemen bu hikâyeye ekle (scope creep) YAPMA;
  3. Ayrı bir FND ek story (veya ilgili downstream hikâye kendi scope'unda) olarak ekle.
**FND-06 = minimal helper foundation; genişletme sonradan ayrı hikâyeler.**
