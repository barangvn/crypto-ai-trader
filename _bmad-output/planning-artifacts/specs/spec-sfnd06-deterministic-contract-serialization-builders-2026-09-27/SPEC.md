---
title: "SPEC — S-FND-06: Deterministic Contract Serialization & Canonical Builders"
slug: spec-sfnd06-deterministic-contract-serialization-builders-2026-09-27
status: draft-spec-prep
story_id: S-FND-06
epic_id: E-FND
story_title: "Deterministic Contract Serialization, Canonical Builders & Fingerprint Helpers (Foundation Layer 6, Pre-RDH POC Substrate)"
classification: CURRENT (MVP) (Extended Foundation epic; bridges typed-contracts layer (S-FND-05) → first applied POC story S-RDH-01, Appendix B #9 priority)
created: 2026-09-27
sources:
  - ../prds/prd-crypto-ai-trader-2026-08-04/prd.md
  - ../../implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md
  - spec-crypto-ai-trader-2026-08-10/CONTRACTS.md
  - spec-crypto-ai-trader-2026-08-10/LIFECYCLE.md
  - spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md
  - ../architecture/architecture-crypto-ai-trader-2026-08-07/ARCHITECTURE-SPINE.md
  - spec-sfnd04-typed-config-pyyaml-format-layer-2026-09-24/SPEC.md
  - spec-sfnd05-canonical-envelope-qualityflags-2026-09-25/SPEC.md
  - spec-eapi-mvp-surface-observability-2026-09-19/SPEC.md
adopted_companions:
  - spec-sfnd03-pytest-infrastructure-hard-boundary-2026-09-22/hard-red.md
  - spec-sfnd02-logging-observability-hooks-2026-09-21/architecture-traceability.md
  - spec-sfnd05-canonical-envelope-qualityflags-2026-09-25/expected-file-changes.md
spec_authored_companions:
  - hard-red.md
  - acceptance-criteria.md
  - definition-of-done.md
  - test-plan.md
  - expected-file-changes.md
  - open-decisions.md
  - source-gaps.md
  - architecture-traceability.md
  - preservation-matrix.md
  - sp05-self-validation.md
  - current-vs-future-boundary.md
  - implementation-readiness.md
capability_ids:
  - CAP-SER-01 (Canonical JSON serialization: sort_keys, compact separators, no whitespace, str(Decimal), str(Instant), str(ULID), no NaN no Inf default)
  - CAP-SER-02 (Deterministic envelope/quality/nested-ref fingerprint: SHA-256 over canonical JSON, truncated 12 hex prefix)
  - CAP-SER-03 (Symbol canonicalizer: native exchange form → BASE_QUOTE uppercase, single-source regex gate)
  - CAP-SER-04 (Instant helpers: parse UTC-Z, validate regex, now_utc generator for test fixtures)
  - CAP-SER-05 (Envelope builder factory: valid envelope defaults + mandatory-field override, fail-closed on missing)
  - CAP-SER-06 (QualityFlags builder: reason code aggregation, degraded auto-set, safe append-only reasons)
  - CAP-SER-07 (ULID Sortable validate + sort ordering compare helper for event streams)
  - CAP-SER-08 (Deterministic JSON equality helper for envelope compare (== fingerprint))
non_goals:
  - Implement binary serialization (msgpack / pickle / protobuf) → future S-FND-08+/S-RDH-04 data layer story
  - Implement exchange adapter, live WS, REST connectivity, network client → S-RDH-01 scope
  - Implement 19 payload contract builders (MarketTick/Candle/...) → S-CON-02 payload-specific build helpers
  - Implement ULID/UUID7 concrete generator → deferred S-RDH-01 ingest entrypoint (OD-06-04 default: reuse test helper only for fixture)
  - Implement event bus, outbox, inbox, persistence → E-PLN scope
  - Implement FeatureVector deterministic builder → S-FEA-03 own story (reuses CAP-SER-01/02 generic)
  - Introduce new runtime third-party dependency: orjson/rapidjson/xxhash (stdlib only default, OD-06-01 explicit open)
  - Implement PyYAML/any YAML parsing/serialization: CLOSED PERMANENT for this story scope per K0 + S-FND-04 evidence chain, independent decision
  - Implement S-MDL / E-API endpoint routes: out of scope, consumers only
  - Implement live trading order routing / credential handling: NEVER for v1 MVP hard boundary
success_signal:
  - "20/20 executable acceptance-criteria PASS on fresh pytest run (0 FAIL, non-zero SKIP < 3 accepted)"
  - "0 existing-tracked file modification lines in git diff parent→HEAD at implementation completion (allowlist only new files)"
  - "13/13 hard-red HRC PASS (8 project-wide + 5 story-specific)"
  - "10x repeat serialization of identical envelope object → fingerprint set len = 1 (D-1)"
  - "S-FND-05 types importable unchanged: 0 regression in 45 tests + upstream regression suites (S-FND-04/03/02, E-API, contracts suite)"
---

# SPEC — S-FND-06 — Deterministic Contract Serialization & Canonical Builders

_Extended Foundation Epic layer 6. Logical immediate successor to S-FND-05 (typed envelope/quality contracts) and mandatory prerequisite gatekeeper for S-RDH-01 (first applied Replay POC story #9 in Appendix B sequence)._

---

## 1. Intent (WHY)

S-FND-05 (previous story) delivered **typed envelope + quality contract classes** as frozen dataclass instances with constructor-level validation and invariants. However, downstream consumers (listed §5) require four operations S-FND-05 explicitly deferred as non-goals:
1. **Deterministic byte-identical serialization** of envelope instances to JSON for: event bus dispatch deduplication, replay idempotency checks, backtest bundle writes, audit trail persistence.
2. **Canonical builders** (factory functions / builder dataclasses) to construct valid envelope & quality flags from partial positional data without consumers repeating boilerplate 16-field constructors.
3. **Common newtype helpers** (symbol canonicalizer, instant formatter/validator, ULID sortable compare, deterministic fingerprint) shared across 10+ downstream stories so contract behavior does not drift across module boundaries.
4. **Deterministic identity / fingerprint (SHA-256 over canonical JSON)** for envelope-level dedup, caching, idempotent bus dispatch, and CAP-1 replay parity signature verification (fixture→output hash same across runs).

Without this layer, S-RDH-01 (first applied POC) would reimplement serialization/symbol canonicalization/fingerprint in adapter code → each downstream module would diverge on sort_keys / compact / Decimal→str handling → CAP-1 (determinism parity) would be unprovable.

## 2. Measurable Success (Kanıtlanabilir Başarı)

- **T-01 (Binary import 3 packages):** `from app.contracts.sfnd06_serialize import canonical_json, envelope_fingerprint` SUCCESS (no ImportError) (AC-01)
- **T-02 (10x serialization identity):** Same envelope object → `canonical_json(env)` bytes identical 10/10 iterations → `len(set(digests)) == 1` (AC-03)
- **T-03 (10x fingerprint identity):** Same envelope → `envelope_fingerprint(env)` same 12-hex output 10/10 iterations (AC-04)
- **T-04 (Symbol canonicalizer):** `"btcusdt"` → `"BTC_USDT"` + regex match; `"BTC/USDT"` → `"BTC_USDT"`; invalid `"<script>"` → raise ValueError (3 AC sub) (AC-08/09/10)
- **T-05 (Instant validator + generator):** `validate_instant("2026-01-01T00:00:00.123Z")` OK; "+03:00 offset" → ValueError; `now_instant_utc_fixture()` Z suffix (3 AC) (AC-11/12/13)
- **T-06 (Envelope valid builder):** `build_valid_envelope(event_type="candle.v1", payload=sample_dict)` → all 12 required non-nullable fields present & valid; post-init invariants FC-01..08 PASS; 0 manual 16-field constructor consumer side (AC-14/15)
- **T-07 (QualityFlags builder + degraded invariant):** `build_quality(stale=True)` → degraded auto-True; `append_quality_reason(qf, "STALE_MS", msg)` → reasons list len increases by 1; append duplicate code idempotent (2 AC) (AC-16/17)
- **T-08 (ULID sortable compare):** 2 ULID strings older/newer → `ulid_compare(a,b) == -1/0/1 int` sortable matches string sort (AC-18)
- **T-09 (Deterministic JSON rules):** output JSON must have: sort_keys=True, separators=(",", ":"), no whitespace, Decimal→str without exponent, Instant→raw str, bool lowercase, None→null, no default dict-like dataclass fallback raise (6 rule AC sub) (AC-05/06/07)
- **T-10 (Backward compat / zero regression):** S-FND-05 tests re-run unchanged → `45/45 PASS` (AC-20 baseline preserved)
- **T-11 (Fail-closed unknown field):** Envelope.builder with extra non-declared kwarg → raise; unknown quality code → ValueError; invalid JSON default override raise (3 AC) (AC-07/15/16)
- **T-12 (Version alignment 1.0.0):** All serialized envelope `contract_version="1.0.0"` literal EXACT; all serialized schema_ref contracts_md field = `"CONTRACTS.md@1.0.0"` → EXACT string equality against S-FND-04 VersionConstants (AC-02/19)

## 3. IN / OUT Boundary

| Sınıf | DAHİL (IN SCOPE) | DIŞI (OUT OF SCOPE — başka hikâye) |
|---|---|---|
| Serialization | **Canonical JSON only** (stdlib `json` module default): sort_keys, compact sep, Decimal→str no exponent, Instant→str no reformat, bool→lowercase, None→null, dict traversal, frozen dataclass→dict via `dataclasses.asdict` ordering guarantee | msgpack, protobuf, pickle, bson, orjson, rapidjson binary / fast-lib formats → deferred S-FND-08 / S-PLN-03 durable layer |
| Builders | Canonical envelope + quality flags builder; symbol canonicalizer; instant validate; ULID compare; fingerprint sha256 12hex truncated | 19 payload-specific builders (MarketTick/Candle/StrategySignal/...) → S-CON-02 + S-CON-03 own scope per payload contract |
| Hash / Fingerprint | Envelope full SHA-256 over canonical JSON bytes (sortable, reproducible) | Per-payload field hashing, perceptual hashing, rolling hash, bloom filters → S-FEA-03 leakage lock layer |
| Helpers | Symbol canonical regex, Instant regex, ULID sortable compare (shared regex single source w/ S-FND-05 `_validation.py` imports — NO DUPLICATE REGEX CONSTANTS) | ID generators, concrete ULID/UUIDv7 producer, time source abstraction (S-RDH-01 ingest entrypoint owns NOW() source) |
| Validators | Regex reuse (import from `app/contracts/_validation.py` if available — avoid duplicate; if import fails → story's own regex copies single-source; do NOT modify S-FND-05 files per K0) | Network health validator, exchange-specific payload validator (S-RDH-01 normalizer / S-RDH-02 eligibility own scope) |
| Fail-Closed | Unknown builder kwargs / invalid quality code / invalid symbol / invalid instant / serialization circular → raise ValueError; silent coerce YOK | Risk engine fail-closed, strategy signal fail-closed → downstream E-RSK/E-STR scope |

## 4. Upstream Dependencies

| Bağımlılık ID | Tür | İsim / SHA | Gerekçe |
|---|---|---|---|
| UP-01 (ZORUNLU) | Story | S-FND-03 `55fd13e` (pytest + forbidden-pattern tarayıcı) | Unit/invariant/determinism testleri + F2 cred-scan + F4 gerçek-emir-isim tarayıcısı mevcut |
| UP-02 (ZORUNLU) | Story | S-FND-04 `946a6b5` (typed INI config + VersionConstants) | `contract_version="1.0.0"` literal alignment UYUM testi AC-12; frozen dataclass pattern reuse |
| UP-03 (ZORUNLU) | Story | S-FND-05 `9314eb4` (Canonical envelope + quality + newtypes) | This story provides serialization HELPERS for S-FND-05 dataclasses; imports from `app.contracts.sfnd05_api` public API path (no internal module access) |
| UP-04 (REFERANS) | MD Canonical | CONTRACTS.md §0 Ortak Tipler · §1 Envelope 16 alan · §2 QualityFlags 8 bool + reasons | Symbol regex, Instant regex, 16 field SIRALAMA guarantee (asdict preserves field order → serialization order determinism) |
| UP-05 (REFERANS) | AD | ARCHITECTURE-SPINE AD-3 (envelope) · AD-4 (parity) · AD-5 (quality) · AD-17 (correlation trace) · AD-19 (safe-stop fail closed) · AD-20 (deterministic fixtures/testability) | Tüm mimari kararlar helpers davranışını şekillendirir |
| UP-06 (REFERANS) | PRD | PRD §5 FR-001/002/005/013 · §7 NFR-002 (determinism) · NFR-006 (structured observation) · NFR-008 (no drift parity) | Determinism + idempotency + traceability PRD yazılımları |
| UP-07 (REFERANS) | EPICS Appendix B | Implementation Sequence 9: S-RDH-01 requires foundation helpers NOW (before POC) | Hikâye sırası = FND06 → S-RDH01 |
| UP-08 (REFERANS) | CAP | CAP-1 (parity: deterministic replay) · CAP-2 (quality flags carry through) · CAP-3 (strategy purity helper share) · CAP-4 (risk gate correlation traceability) · CAP-6 (no live paths: helper scope no exec) | Helper CAP köprüsü |

SİLENT INHERIT YOK — bağımsız değerlendirme:
- **S-FND-04 PyYAML OFF kararı (OD-FND-04-01) → BU HİKÂYEDE AYRICA KAPALI (OD-06-03 CLOSED PERMANENT)**. Helper serialization JSON only; YAML hiçbir biçimde kullanılmaz. Sessiz inherit değil, kendi explicit decision.
- **S-FND-05 Path B public API → BU HİKÂYEDEN import path yalnızca `app.contracts.sfnd05_api` üzerinden (internal _validation.py import etmeye gerek yoksa tercih et; regex tekrar etmek yerine import et ama internal modül değişimi YOK, K0 korunur).**

## 5. Downstream Consumers

| Tüketici ID | Hikâye İsmi | Ne tüketir (helper IDs) | Zorunluluk |
|---|---|---|---|
| DOWN-01 (ZORUNLU) | S-RDH-01 | CAP-SER-01 canonical JSON, 03 symbol, 04 instant, 05 envelope builder, 06 quality builder, 07 ULID compare, 02 fingerprint | ZORUNLU (ilk POC bu helper'siz yazılamaz) |
| DOWN-02 | S-CON-02 (19 payload schemas) | CAP-SER-01 canonical JSON, 02 fingerprint, 04 instant, 05 envelope builder (payload generic build) | ZORUNLU |
| DOWN-03 | S-PLN-01 (Typed In-Mem Bus) | CAP-SER-01 serdes, 02 fingerprint dedup, 07 ULID sortable for ordered dispatch | ZORUNLU |
| DOWN-04 | S-FEA-03 (Deterministic FeatureVector) | CAP-SER-01 canonical JSON, 02 feature fingerprint for leakage lock | ZORUNLU |
| DOWN-05 | S-REG-02 (Regime consumption patterns) | CAP-SER-04 instant, 03 symbol canonical | ZORUNLU |
| DOWN-06 | S-STR-03 (Strategy Purity test CAP-3) | CAP-SER-01/02 helper import consistency | ZORUNLU |
| DOWN-07 | S-RSK-02 (CAP-4 risk→order gate) | CAP-SER-02 correlation fingerprint trace, 04 instant, 03 symbol | ZORUNLU |
| DOWN-08 | S-BKT-03 (Leakage / Look-Ahead assertions) | CAP-SER-02 envelope fingerprint for ordered backtest bundle signature | ZORUNLU |
| DOWN-09 | S-PTR-01/S-PTF-01 | CAP-SER-04 instant, 02 fill/position portfolio snapshot fingerprint | ZORUNLU |
| DOWN-10 | E-API (S-API 01/04) | CAP-SER-01 canonical JSON response envelope | ZORUNLU (E-API final boundary) |

## 6. Contracts / Data Types (Helpers Signature Contracts)

### 6.1 Exported Public Function Signatures (Exact name + exact parameters — load-bearing)

_Dil: Python 3.12+, stdlib only default. Tüm fonksiyonlar SAFE, I/O YOK, network YOK, credential YOK, NOW() source YOK (fixture generator haricinde explicit annotation)._

```python
# =========================================================================
# APP.CONTRACTS.SFND06_SERIALIZE PUBLIC API (17 fonksiyon + 1 exception class = 18 export)
# =========================================================================

# Exception subclass (ValueError gibi concrete type — built-in subclass)
class CanonicalSerializationError(ValueError):
    """Fail-closed helper exception; catchable as ValueError."""

# ---------- 1. Canonical JSON (CAP-SER-01) ----------
def canonical_json(obj: Any, /) -> bytes:
    """Return deterministic JSON bytes for obj.
    Rules: sort_keys=True, separators=(",", ":"), no indent,
    Decimal → str (no exponent notation), datetime disallowed (must be Instant str),
    None→null, bool lowercase, dataclass→asdict, circular raise, unknown type raise."""

def canonical_loads(raw: bytes | bytearray | str, /) -> Any:
    """Inverse of canonical_json; stdlib json.loads; strict=True."""

def canonical_json_equal(a: Any, b: Any, /) -> bool:
    """CAP-SER-08: return canonical_json(a)==canonical_json(b)."""

# ---------- 2. Fingerprint (CAP-SER-02) ----------
def envelope_fingerprint(env: "CanonicalEventEnvelope", /) -> str:
    """Return 12 lowercase hex chars. SHA256(canonical_json(env))[:12]."""

def payload_fingerprint(payload: Any, /) -> str:
    """Generic payload fingerprint; same algo; helper for S-FEA-03 leakage."""

# ---------- 3. Symbol Canonical (CAP-SER-03) ----------
def canonical_symbol(raw: str, /) -> "SymbolCanonical":
    """Accept base/quote forms: btcusdt → BTC_USDT; BTC/USDT → BTC_USDT;
    BTC-USDT → BTC_USDT. Non-matching raw → raise ValueError.
    Regex single source: import from S-FND-05 SYMBOL_RGX if possible (no copy)."""

def is_canonical_symbol(s: str, /) -> bool:
    """Return True iff s matches canonical regex (no raise)."""

# ---------- 4. Instant Helpers (CAP-SER-04) ----------
def validate_instant(raw: str, /) -> "Instant":
    """Match S-FND-05 INSTANT_RGX. OK return raw str; else ValueError.
    Accepts fractional digits 1-6 (Z suffix mandatory; UTC offset +HH:MM disallowed)."""

def now_instant_utc_fixture(*, _clock: object = None) -> "Instant":
    """Fixture-only (test & replay) UTC ISO Z Instant; fractional 3-digit default ms;
    _clock override for test injection; NOT FOR PRODUCTION NOW() (S-RDH-01 ingest owns clock)."""

# ---------- 5. Envelope Builder Factory (CAP-SER-05) ----------
def build_valid_envelope(
    *,
    event_type: str,
    payload: Any,
    # 12 required non-nullable — OMITTED → DEFAULT SAFE VALUES set by builder
    # caller overrides any of the 12 when known; missing overrides OK because defaults valid
    event_id: str | None = None,
    contract_version: str = "1.0.0",
    symbol: str | None = None,
    source: str = "fixture.unknown",
    timestamp: str | None = None,
    ingest_ts: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    run_mode: str = "backtest",
    source_type: str = "static_fixture",
    clock_ref: dict | None = None,
    quality_flags: object | None = None,
    schema_ref: dict | None = None,
    trace_id: str | None = None,
    extra: dict | None = None,
) -> "CanonicalEventEnvelope":
    """Construct envelope with sane defaults. Missing → fixture ULID/instant generated;
    Final envelope MUST PASS S-FND-05 post-init invariants; invalid → raise."""
    # NOTE (D-06-B rectification, canonical): `event_id` is an OPTIONAL override.
    # When omitted, the builder generates a deterministic fixture ULID — it does
    # NOT raise. This is the load-bearing behavior (executable AC-14) and it
    # supersedes the earlier, non-mandatory OD-06-07 preference ("raise when no
    # event_id override"). See open-decisions.md OD-06-07 (RESOLVED / SUPERSEDED).

# ---------- 6. QualityFlags Builders (CAP-SER-06) ----------
def build_quality(
    *,
    stale: bool = False,
    missing: bool = False,
    duplicate: bool = False,
    out_of_order: bool = False,
    invalid: bool = False,
    quarantined: bool = False,
    reasons: list | None = None,
    degraded: bool = False,  # keyword-only, default False; only accepted value is False
) -> "QualityFlags":
    """Build QualityFlags; degraded auto-set post-init (S-FND-05 invariant).
    Appends reasons list items passed.
    `degraded` (keyword-only bool, default False): NOT an independent toggle —
    S-FND-05 derives `degraded` from the other six flags, so the only accepted
    value is False. Passing `degraded=True` -> raise ValueError (FC-16/HR-12
    default-safety reject; executable AC-17). Classification: non-binding
    optional future safety choice (not a mandatory upstream CONTRACTS §2 rule)."""

def append_quality_reason(
    qf: "QualityFlags", /, code: str, message: str, context: dict | None = None
) -> "QualityFlags":
    """Append QualityReason to new list (frozen workaround; return NEW instance).
    Duplicate code → NOOP idempotent (no grow). Invalid code (empty / >64) → raise."""

def set_quality_flag(
    qf: "QualityFlags", /, flag_name: str, value: bool = True,
) -> "QualityFlags":
    """Return new QualityFlags with one flag toggled; degraded invariant re-checked."""

# ---------- 7. ULID Sortable (CAP-SER-07) ----------
def validate_ulid_sortable(raw: str, /) -> "ULID_SORTABLE":
    """Match S-FND-05 ULID_CROCKFORD_RGX or UUID7_RGX; raise otherwise."""

def ulid_compare(a: str, b: str, /) -> int:
    """Lexicographic compare (CROCKFORD preserves time sort). Returns -1/0/1 int."""

def ulid_newer(a: str, b: str, /) -> bool: return ulid_compare(a, b) > 0
def ulid_older(a: str, b: str, /) -> bool: return ulid_compare(a, b) < 0
```

### 6.2 Shared Reuse Principle (Tek Kaynak)
- Regex constants (INSTANT_RGX, SYMBOL_RGX, ULID_* RGX, EVENT_TYPE_RGX): if public importable from `app.contracts` (S-FND-05 public API path exposes them), **import edip kullan; duplicate etme.** Eğer export edilmemişse — bu hikâyede aynı regex string değerlerini bu hikâyenin kendi `_sfnd06_constants.py` modülünde tek kaynak olarak tut. **NE YAPMA:** S-FND-05 source dosyalarını (özellikle `_validation.py`) K0 nedeniyle MODİFİYE ETME.
- Frozen dataclass ordering guarantee: `dataclasses.asdict` outputs field declaration order → canonical JSON key order for nested dataclasses must be **stable**; we must explicitly sort dict keys top-level and all nested levels (deep sort).

## 7. Determinism (7 Ölçüm)

| D-ID | Test | Beklenen (Pass) |
|---|---|---|
| D-01 | Aynı envelope → 10 kez canonical bytes → set 1 | `len(set(canonical_json(envs))) == 1` |
| D-02 | Aynı envelope → 10 kez fingerprint → aynı 12hex | `len(set(fp)) == 1` |
| D-03 | 2 farklı ULID sırayla → ulid_compare 10 kez aynı sonuç → sortable | Deterministic |
| D-04 | Sembol canonical `"btc/usdt"` → 10 kez → `"BTC_USDT"` (aynı çıktı) | 10/10 eşit |
| D-05 | QualityFlags builder stale=True → 10 kez → reasons+degraded aynı | 10/10 aynı bayrak+reason len |
| D-06 | Dictionary order random shuffle input → canonical_json → sort_keys → aynı çıktı | `canonical_json(shuffled_dict_a)==canonical_json(sorted_dict_b)` |
| D-07 | Decimal `Decimal("123.456")` vs `Decimal("123.456000")` → canonical JSON string representation aynı mı? (NOT: bu hikâyede normalleştirmek zorunda değiliz; SPEC 06: Decimal→str WITHOUT NORMALIZE (bug'ı avoid). Not: bu determinism = aynı Decimal input → aynı str output; farklı equal Decimal farklı str output olabilir mi? → AÇIK KARAR OD-06-02 default preserve string representation.) | Same Decimal input → same output. |

## 8. Fail-Closed Behavior (8 Case — FC-09..16 extending S-FND-05 FC-01..08)

| FC ID | Senaryo | Hata Türü | Kök Kaynak |
|---|---|---|---|
| FC-09 (SER) | Bilinmeyen type (datetime, set, custom class without asdict) pass to canonical_json → SESSİZ coerce YOK → HATA | CanonicalSerializationError (ValueError subclass) | CAP-SER-01 rule: unknown type raise, no default(o) fallback with silent guess |
| FC-10 (SER) | Circular reference → HATA (not silently truncated) | CanonicalSerializationError | Determinism: no recursive cut-off arbitrary |
| FC-11 (BLD) | `build_valid_envelope(event_type="")` empty string event_type → ValueError (S-FND-05 EVENT_TYPE_RGX no-match) | ValueError / CVE | SPEC §6 envelope builder — no silent default empty → K0 closed |
| FC-12 (BLD) | `append_quality_reason(qf, code="", message="x")` empty code → HATA; code len >64 → HATA | ValueError | CAP-SER-06 reason code integrity |
| FC-13 (SYM) | `canonical_symbol("btc/usdt<script>")` regex no-match → HATA; no sanitization (sanitize bug: false positive) — we only accept strict subset. Inputler safe değilse reject. | ValueError | K0 AD-19 safe stop: ambiguous symbol accept YOK |
| FC-14 (INST) | `validate_instant("2026-01-01T00:00:00+03:00")` offset varsa → HATA; Z suffix mandatory; fractional 7+ digits → HATA (S-FND-05 regex 1-6 digit). TAM S-FND-05 regex ile aynı kural. | ValueError | CONTRACTS §0 L15 UTC Z mandatory |
| FC-15 (FP) | `envelope_fingerprint(None)` / `envelope_fingerprint(not_an_envelope)` — isinstance check yoksa? → HATA, TypeError / CanonicalSerializationError. Geçersiz argüman → HATA. | CanonicalSerializationError | Fail-closed: fingerprint only envelopes. |
| FC-16 (BLD) | `set_quality_flag(qf, "degraded", True)` (manual degraded set) → overwrite manual → HATA (default safety: degraded sadece diğer 6 bayrak tarafından otomatik set edilir; S-FND-05 post-init invariant zaten bunu enforce eder. **Classification: Non-binding Optional Future Safety Choice** (upstream CONTRACTS §2'de kalıcı normatif MANDATORY kural değildir; downstream hikâyelerde builder API expanded olabilir. Davranış raise = geçerli güvenlik seçeneği korunur.) | ValueError (ContractValidationError subclass) | S-FND-05 FC-06 invariant extension: manual degraded override → default SAFETY RAISE (non-binding classification, future explicit) |

## 9. Security & Safety

| SEC ID | Kural | Uygulama |
|---|---|---|
| SEC-01 | Credential Free: Helper hiçbir yerde API key, secret, credential pattern okumaz/tutmaz. Sadece symbol string & regex process. | S-FND-03 F2 tarayıcısı kontrol eder; `canonical_json` does not have any credential fields by design. |
| SEC-02 | Long-Only: No direction / leverage field processing in helper layer. Symbol only BASE/QUOTE. Short/lev S-CON-02 StrategySignal payload scope → helper'siz. | S-FND-03 F3 forbidden tarayıcı: no `short`, `leverage` keyword in this story's new production modules (outside test fixtures). |
| SEC-03 | No network: helper imports only stdlib `json`, `hashlib`, `re`, `dataclasses`, `decimal`, `typing`, `functools`. Sockets, requests, httpx, websocket — YOK. | S-FND-03 F1 tarayıcı geçmesi. |
| SEC-04 | No execution injection: `canonical_json` has no default(o) that executes callable. No eval/exec/pickle/subprocess. | Project HRC (HR-SR-03 dynamic eval). |
| SEC-05 | Safe symbol regex: no HTML tag, no path traversal, no quote injection characters — strict A-Z0-9 underscore only. `canonical_symbol` rejects anything else explicitly. | AD-19: güvenli dur — geçersiz sembol → reject, downstream pipeline hiç işleme sokmaz. |
| SEC-06 (Future Live) | Live execution: helpers contain no paper/live branching. RunMode is opaque passed through as string; helper code does `if run_mode == "live":` branch YOK (CAP-1 parity S-CON-03 tarayıcısı için: static scan zero match). | S-FND-03 F1/F4 + S-CON-03 parity branch tarayıcısı. |

## 10. Audit / Evidence

| AUID | Kanıt | Nerede |
|---|---|---|
| AUD-01 | Canonical JSON output → bytes tam olarak sort_keys+compact → testlerde raw bytes diff (byte-by-byte) against known fixture. | test_sfnd06_canonical_json_stable.py |
| AUD-02 | 10x determinizm → SHA set len=1 rapor. | test_sfnd06_determinism_audit_10x.py |
| AUD-03 | Helper → regex constants imported from S-FND-05 public API (if available) OR copied single-source in story's own constants. NO 3rd source of truth → test assert regex equality. | test_sfnd06_regex_single_source.py |
| AUD-04 | K0 existing modify → git diff HEAD~ (expected 0 existing lines) audit by auditor. | Git diff parent→HEAD in implementation phase |
| AUD-05 | HRC scan → new production 6 modules 11 categories 0 match. | test_sfnd06_hrc_sanity.py 11 forbidden pattern |
| AUD-06 | No `if run_mode` → AST scan 0 matches. | test_sfnd06_parity_static.py |

## 11. Non-Goals (Açıkça Dışında) — 14 kalem

1. Binary serialization formats (msgpack/pickle/protobuf/parquet/orjson/xxhash) — deferred separate FND data layer (S-FND-08 maybe).
2. ULID/UUIDv7 concrete generator with real-time monotonic source (S-RDH-01 / ingest module owns time source; we only validate & compare).
3. 19 payload-specific builders (MarketTick/Candle/OrderBook/Trade/Regime/Feature/Strategy/Signal/Opportunity/RiskDecision/PaperOrder/Fill/Position/PortfolioSnapshot/ModelVersion/Evaluation/Lifecycle/ChampionEvaluation) → own scope S-CON-02 per payload.
4. Database write, persistence adapter, object storage write → E-PLN/E-RDH/E-MDL.
5. PyYAML / YAML serialization — **CLOSED PERMANENT (OD-06-03)**. YAML NO.
6. Network connection, REST client, WebSocket client → S-RDH-01 adapter.
7. Real trading order paths, credential, send_real_order → NEVER v1 (F4 tarayıcı).
8. Strategy / Risk / Portfolio logic.
9. Model registry / lifecycle transitions (CAP-5) → S-MDL scope.
10. Logging/metric instrumentation (we do not add logs; we return raw bytes/str; caller logger caller side). S-FND-02 logger already exists; do NOT re-create logger here.
11. Feature engineering / technical indicator calculation.
12. Regime detection / clustering.
13. API endpoint creation (E-API only consumer).
14. Config YAML/env var read write (S-FND-04 owns config; we only accept explicit string literals).

## 12. Hard-Red (Kırmızı Çizgiler — HARD RED / HRC)

- Ayrı companion `hard-red.md` içinde. Toplam 13: 8 proje genel + 5 hikâye özel.

## 13. Acceptance Criteria (20 Kabul Kriteri)

- Ayrı companion `acceptance-criteria.md` içinde. Her biri Given/When/Then + PASS/FAIL.

## 14. Definition of Done (Tamamlandı Tanımı 10 Başlık)

- Ayrı companion `definition-of-done.md` içinde.

## 15. Test Plan (TP-01..14)

- Ayrı companion `test-plan.md` içinde. Unit + negatif + invariant + determinism + parity + HRC + K0 regression.

## 16. Expected File Changes (Allowlist: 0 Existing Modifications Default)

- Ayrı companion `expected-file-changes.md` içinde. New production 6 new files; new test **16** new files. Existing modify = 0. EX list boş.

## 17. Open Decisions (8 OD-06-01..08)

- Ayrı companion `open-decisions.md` içinde. Hiçbiri MANDATORY BLOCKER. Hepsi default çözüm + optional explicit override imkanı.

## 18. Source Gaps (8 GAP-06-01..08)

- Ayrı companion `source-gaps.md` içinde. Kaynak dokümanda (PRD/EPICS/ARCH/CONTRACTS) yazılmayan ama implementation sırasında karar verilmesi gereken 8 nokta. Hepsi ADN ya da default çözüm ile çözülebilir. MANDATORY YOK.

## 19. Current-vs-Future Boundary (Şimdi vs Sonraki Hikâyeler)

- Ayrı companion `current-vs-future-boundary.md` içinde: What stays in FND-06 helpers vs what moves to later stories (DOWN-01..10 listesinin ayrıntılı sınır).

## 20. Architecture Traceability + CAP Köprüleri

- Ayrı companion `architecture-traceability.md` içinde: AD-1..25 10+ direct bağlar, CAP-1..6 helper-level köprü, upstream / downstream ADN forward map.
