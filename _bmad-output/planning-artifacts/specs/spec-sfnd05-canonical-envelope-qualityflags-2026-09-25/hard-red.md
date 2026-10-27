# Hard-Red — S-FND-05 (8 PROJE + 5 HİKÂYE ÖZEL = 13 TOTAL)

8 proje HRC (S-FND-03 hard-red.md binding) + 5 hikâye özel. İhlal → IMPLEMENTATİON FAIL.

## 8 PROJE HRC (KALICI)

| HRC ID | Kural | Grep Pattern | PASS Beklentisi |
|---|---|---|---|
| HR-01 | Existing-file modification 0 lines tracked (EX listesi BOŞ default). | `git diff --name-only HEAD | grep -v ^untracked` | EMPTY implementation lines. 6 completed-story diff 0. |
| HR-02 | Network / API / Live connect imports YOK. Sadece `app/ingest/adapters` ve fixture. | `requests\|httpx\|aiohttp\|websocket\|urllib3\|socket.connect\|binance\|okx_api_key` | app/contracts/ + tests/foundation_sfnd05 = 0 match. |
| HR-03 | Credentials / Secrets / literal values 0. F2 S-FND-03 tarayıcı. | `AKIA\|_SECRET_VALUE\|BINANCE_API_KEY\|OKX_KEY\|secret=` | 0 match. `allow_external_creds` benzeri FENCE identifier kullanılabilir (literal "secret" substring YOK). |
| HR-04 | Unsafe dynamic execution: eval/exec/pickle/subprocess shell. | `eval(\|exec(\|pickle.(load\|dump)\|subprocess.*shell` | 0 match. |
| HR-05 | 0 3rd-party runtime dependency KURAL (DEFAULT). PyYAML dahil. OD-05-01 schema library EXPLICIT olarak 3p seçerse (Pydantic v2) BU HRC-05 istisnası olur; ancak EX listesinde dep belirtilmedikçe STANDART = STDLIB ONLY. | `import pydantic\|from pydantic\|import yaml\|import msgspec\|from attrs\|import cattrs` | DEFAULT 0 match. OD-05-01 stdlib→attrs-cattrs-messages-pydantic SEÇİMİ YAPILMAK ZORUNDA = İSTİSNA AYRICA ONAY. |
| HR-06 | Registry / lifecycle write YOK (S-MDL-01..05): `from app.governance` / `registry.(register\|mutate\|publish\|set_status)` / Champion kelimesi (implementasyon code değil test). | `from app\.governance\|registry\.(register\|request_transition)\|from app\.registry\|ModelVersion\.status\s*=\|Champion\s*=\s*True` | 0 match. |
| HR-07 | Completed-story diff 0 (S-FND-01..04, E-API, S-MDL 01..05, contracts, replay, backtest, failure). | `git diff HEAD -- <6 pathsets>` | EMPTY. 0 lines. |
| HR-08 | Unsafe yaml / future live path. | `yaml.load\|yaml.full_load\|/execution/live\|send_real_order\|create_order_on_exchange` | 0 match. PyYAML story-level OD-05-04 Closed. |

## 5 HİKÂYE ÖZEL HARD-RED

| HRC-STORY ID | Kural | Grep Pattern | PASS Beklentisi |
|---|---|---|---|
| SR-01 | SCOPE BOUNDARY: 19 payload schema (MarketTick/Trade/OrderBook/Candle/Regime/Feature/StrategyContext/Signal/Opportunity/Risk/PaperOrder/PaperFill/Position/Portfolio/ModelVersion/Evaluation/Lifecycle/ChampionEval + LimitsSnapshot) YOK. Sadece envelope + quality. | `class MarketTick\|class TradeEvent\|class OrderBook\|class Candle\|class MarketRegime\|class FeatureVector\|class StrategyContext\|class StrategySignal\|class OpportunityScore\|class RiskDecision\|class PaperOrder\|class PaperFill\|class Position\|class PortfolioSnapshot\|class ModelVersion\|class ModelEvaluation\|class LifecycleTransition\|class ChampionChallenger\|class LimitsSnapshot` | 0 match. Payload schema S-CON-02. |
| SR-02 | EVENT BUS DISPATCH / PERSIST / OUTBOX YOK. | `class EventBus\|def dispatch\|def publish\|psycopg\|asyncio.Queue("dispatcher")\|from app\.processing` | 0 match. E-PLN-01 scope. |
| SR-03 | ULID PRODUCTION / RANDOM WALL-CLOCK BAĞIMLILIĞI YOK (typecheck-only; ID generator RDH-01). | `time.time_ns()\|uuid.uuid1()\|ulid.new()\|random\.choices` constructor İÇİNDE (test fixture dışı). | 0 match. STORY: sadece typecheck + regex doğrula. ÜRETME. |
| SR-04 | SCOPE DRIFT S-FND-06+: execution / order / ai / simulation / backtest kodları YOK. | `from app\.simulation\|from app\.decisioning\|from app\.governance\|from app\.processing\|from app\.ingest` (ADAPTERS hariç - hiç). | 0 match. `app.contracts` package BAĞIMSIZ. |
| SR-05 | PAYLOAD DOMAİN VALİDASYONU YOK (örnek: price > 0 Decimal MarketTick için). Bu tür kontroller S-CON-02. | `if payload.price <= 0\|if payload.quantity <= 0\|FeatureVector flat kontrolü` (test dışı prod kodda) | 0 match. Sadece envelope + quality, payload generic T deferred. |

Toplam: 13 hard-red. 0 match → PASS.

## Option C Sınırı (OD-05-09) — HRC Tarama Kapsamı

SR-01..SR-05 hikâye özel HRC'leri S-FND-05 public sözleşme ailesi (`app/contracts/envelope.py`, `app/contracts/quality_flags.py`, `app.contracts.sfnd05_api`) üzerinde tarama yapar. `app/contracts/canonical.py` legacy tip ailesi S-FND-05 scope'unda DEĞİLDİR ve iki aile arasında otomatik eşdeğerlik varsayılmaz (Option C — OD-05-09). Ayrıntı: `open-decisions.md`.
