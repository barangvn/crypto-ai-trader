---
story_id: "S-CON-02A"
story_key: "2-2A-featurevector-regime-strategycontext-strategysignal-canonical-contracts"
title: "S-CON-02A FeatureVector + MarketRegime + StrategyContext + StrategySignal Canonical Contract Group (Typed, Versioned, AD-22/AD-25/CAP-1/CAP-2 Uyumlu)"
status: "ready-for-dev"
created: 2026-08-14
updated: 2026-08-14
epic: "E-CON: Canonical Contracts & Schema Enforcement (Epic 2)"
baseline_commit: "3b5b754"
workspace_clean_on_start: false  # S-PLN-01 sonrası 3M + 12?? çalışma ağacı — dokunma, regression testlerini koru
python_runtime: "cpython-3.14"
runtime_dependencies_new_allowed: 0  # stdlib-only — pydantic/attrs/pycontracts YASAK
contract_version_expected: "1.0.0"  # CONTRACTS.md §1 — yükseltme YOK (backward compat)
correlation_id_type: "ULID string"    # 26 chars Crockford base32 — app/contracts/types.py mevcut
causation_id_type: "ULID string"
event_naming_scheme: "snake_case.vN"  # örn: "feature_vector.v1", "market_regime.v1"  (contracts mevcut ile aynı)
previous_story_completed: "S-PLN-01 Typed Bus 174/174 PASS (68 S-RDH-01 + 64 S-RDH-02 + 42 yeni)"
previous_story_sha_baseline_preserved: "true"  # S-RDH-01 14 dosya SHA-256 .tmp/srdh01_baseline_sha256.json 14/14 — mevcut contracts dosyaları HALEN
---

# S-CON-02A — FeatureVector + MarketRegime + StrategyContext + StrategySignal Canonical Contract Group (Typed / Versioned / AD-22·AD-25·CAP-1·CAP-2 Compliant)

> **HARD KURAL (Geri Dönüş Uyumluluğu — İHLAL EDİLEMEZ):**
>
> 1. Mevcut 4 adet `app/contracts/` dosyasının (`__init__.py`, `canonical.py`, `market.py`, `types.py`) **hiçbir public importunu, public sınıf adını, public sabitini, public fonksiyon imzasını DEĞİŞTİRME**. Sadece yeni dosya + `__init__.py`'ye yeni `__all__` ve import EKLEMESİ yapılır.
> 2. S-RDH-01 68/68, S-RDH-02 64/64 = 132/132 regression ve S-PLN-01 42/42 yeni testi **SONUÇ DEĞİŞMEDEN** geçmelidir. TOPLAM 174/174 test + bu hikâyedeki ≥50 yeni test → ≥224.
> 3. `pyproject.toml dependencies = []` değişmez. Sadece stdlib (`dataclasses`, `decimal.Decimal`, `enum`, `typing`, `re`, `hashlib`, `json`, `functools`, `itertools`, `copy`). Pydantic/attrs/msgspec/cattrs YASAK.
> 4. `contract_version_expected` = `"1.0.0"` — `app/contracts/__init__.py` içindeki `CONTRACT_VERSION` SABİT DEĞİŞMEZ.

---

## 1. Epic ve Bağlam

**Epic:** E-CON: Canonical Contracts & Schema Enforcement — [EPICS.md §Epic 2](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L241-L283)

**Not:** EPICS Appendix B'te özgün S-CON-02 = "19 Sözleşme" idi. Bu hikâye S-CON-02A = 4 sözleşmenin *İLK GRUBU*: (1) FeatureVector (AD-22 flat sözlük + versioned), (2) MarketRegime (AD-8 6 rejim enum + confidence + scores), (3) StrategyContext (AD-25 typed pure strategy plugin input), (4) StrategySignal (FR-025/026/176 strateji çıktısı). Kalan 15 sözleşme (OpportunityScore / RiskDecision / PaperOrder / PaperFill / Position / PortfolioSnapshot / ModelVersion / ModelEvaluation / LimitsSnapshot / ...) S-CON-02B/02C hikâyelerine bırakılır. **Bu hikâye sadece 4 contract + onların contract testleri.**

**User Story:**
> *As a Strategy / Regime / Feature Engineer, I want strict typed, versioned, deterministic, Decimal/float-compliant canonical schemas for FeatureVector, MarketRegime, StrategyContext, and StrategySignal — aligned with CanonicalEventEnvelope, supporting correlation_id & causation_id propagation, UTC timestamps, canonical symbols, and quality_flags preservation per CAP-1/CAP-2 — so that downstream plugins (StrategyEngine, RegimeDetector, FeatureEngineering) can exchange data without runtime KeyError, silent type drift, or live-vs-replay branch divergence.*

---

## 2. Amaç ve Sınırlar

Bu hikâyenin TEK amacı: CONTRACTS.md §3.6, §3.7, §3.8, §3.9 sözleşmelerine **%100 uyan, typed, stdlib-only, versioned, deterministic, testable, Geriye Dönüş Uyumlu** Python dataclass sınıflarını + contract testlerini oluşturmaktır.

| Özellik | Gereklilik | Referans |
|---|---|---|
| Live / Replay Parity | Contract kodu içinde 0 `if run_mode ==` / `if source_type ==` branch | CAP-1, AD-4 |
| Quality Flags Korunması | 4 sözleşme de envelope quality_flags'i KENDİNDE MUTATE ETMEZ; sadece taşıyabilir/reference gösterebilir (referans istersen StrategyContext içinde salt okunur QualityFlags view). | CAP-2, AD-5 |
| Typed & Strict Schema | Her field için doğru Python tipi; yanlış tip ya da eksik required field → `ValueError` / `TypeError` contract testiyle FAIL | AD-3, AD-22, AD-25 |
| Versioned Semver | Her contract schema_version ayrı string (`feature_version`, `detector_version`, `strategy_version`); field'ları CONTRACTS §3.7/3.6/3.8/3.9 | FR-011, FR-015, FR-026 |
| Deterministic Serialization | `to_sorted_dict()` → key'ler alfabetik SIRALI; `hashlib.sha256(json.dumps(..., sort_keys=True, separators=(',',':')))` input→aynı digest | NFR-007, AD-20 |
| Decimal vs Float Kuralı | **Parasal/fiyat/hacim**: `Decimal` (18 hane, float YOK); **Skor/Confidence/Prob/Olasılık/feature non-monetary**: `float` [0, 1] aralığı zorunlu | CONTRACTS §0 (Ortak Tipler), SPEC Constraints § |
| UTC ISO-8601 3-digit Z | Tüm zaman Instant tipi (app/contracts/types.py mevcut format_instant/validate_instant); | CONTRACTS §0 Instant |
| Symbol Canonical | `BASE_QUOTE` büyük harf; `validate_symbol_canonical` TRUE olmalı (system events NULL olabilir) | CONTRACTS §0 Symbol |
| Correlation / Causation | Her 4 sözleşme ya envelope içindedir (payload olarak zaten gelir) YA DA StrategyContext helper `derive_metadata_from_envelope(env)` ile correlation/causation/run_mode/source_type/clock_ref KOPYALAR, ASLA mutate ETMEZ (AD-17 koruma) | AD-17, FR-007 |
| Market Regime 6 Enum | Tam olarak `bull / bear / sideways / high_volatility / low_volatility / transition_uncertain` — başka değer yok; ekleme contract_version yükseltme ister | AD-8, FR-014 |
| FeatureVector Flat Dict (AD-22) | Nested YOK; dizi YOK; ndarray YOK; sadece `Dict[str, Decimal \| float \| int \| str \| None]`; her feature_version için ayrı schema REGISTRY olmalı (minimal `FEATURE_SCHEMA_REGISTRY: dict[str, FeatureSchemaSpec]` dataclass) | AD-22 |
| StrategyContext Purity (AD-25) | Strategy plugin SADECE `evaluate(ctx: StrategyContext) -> StrategySignal`; context içinde NO network/DB/FS/exchange import path'i (CAP-3 contract testi bunu daha sonra zorlar, bu hikâyede sadece context importları STATIC tarama ile doğrulanır) | AD-9, AD-25, CAP-3 |
| StrategySignal Long-Only (v1 hard boundary) | `direction` enum: yalnızca `long / flat / hold` — `short` TAMAMEN YASAK; eklenirse contract_version yükseltilmeli. | Brief §4, PRD §1 FR-061, SPEC Constraints |

---

## 3. Tamamı Bu Hikâyede — Scope Detay (4 Contract)

### 3.0 Ortak Kurallar (Tüm 4 Contract İçin)

1. **Tüm sözleşmeler `@dataclass(frozen=False, slots=False)`** — frozen: StrategyContext'te derived alanlar için hesaplama sonrası ekleme olabilir. Slots: Stdlib dataclass slots var ama eski testlerle uyum için FALSE (geri dönüş).
2. Her contract:
   - `__post_init__`: required field tiplerini kontrol + enum valid + Instant format doğrula + Symbol canonical doğrula. Hata → `ContractSchemaError(ValueError subclass)`.
   - `to_sorted_dict(self) -> dict[str, Any]`: sorted keys, tüm nested alanlar recursively sort edilmiş (deterministik).
   - `schema_sha256(self) -> str`: sha256 hexi digest of `to_sorted_dict` (determinizm için).
3. Ortak import: `app/contracts/types.py` içindeki `ULID`, `Instant`, `Symbol`, `RunMode`, `SourceType`, `format_instant`, `validate_instant`, `normalize_symbol`, `validate_symbol_canonical` **MEVCUTTUR — yeniden tanımlama**.
4. Ortak helper: `ContractSchemaError(ValueError)` — tek exception türü, tüm validasyon hataları bundan.

---

### 3.1 Contract #1: `FeatureVector` (AD-22 Flat + Versioned + Provenance Input Refs)

**Kod konumu (YENİ DOSYA — VAR OLMAYAN dosya, YENİ):**
`app/contracts/feature.py`

**Alanlar (tam CONTRACTS.md §3.7):**

| Alan | Tip | Zorunlu | Kural / Limit / Not |
|---|---|---|---|
| `feature_version` | `str` | ✅ E | Sürüm; örn `"fv_mvp_v1.0.0"`. Karakter: `^[a-z0-9_.]+$` (validasyon). |
| `timeframe` | `str` | ✅ E | Örn `"1m"`, `"5m"`, `"1h"`. ADN-02 — enum değil, string. |
| `features` | `dict[str, Decimal \| float \| int \| str \| None]` | ✅ E | **AD-22 FLAT DICT:** Nested YOK, list YOK. Key regex: `^[a-z][a-z0-9_]*$`. |
| `lookback_window` | `LookbackWindowSpec` (dataclass nested) | ✅ E | `{count: int > 0, timeframe: str}` (aynı §3.7). |
| `input_refs` | `list[ULID]` (list[str]) | ✅ E | Hesaba giren event/entity id'leri (causation/provenance). Boş liste olabilir ama `None` YOK — required. |
| `null_count` | `int \| None` | ⭕ K | Default `sum(1 for v in features.values() if v is None)` — eğer verilmezse `__post_init__` hesaplar; verilirse EŞLEŞMELİ (eşleşmezse ContractSchemaError). |

**Nested Yardımcı (aynı dosyada):**
```python
@dataclass
class LookbackWindowSpec:
    count: int                 # ≥1
    timeframe: str             # Örn "1m"
    def __post_init__(self):
        if not isinstance(self.count, int) or self.count < 1:
            raise ContractSchemaError(f"LookbackWindowSpec.count={self.count!r} must be int >=1")
```

**AD-22 Ek Özellik: FeatureSchemaSpec + REGISTRY (minimal):**
```python
@dataclass(frozen=True)
class FeatureSchemaSpec:
    """Bir feature_version anahtar setini + her anahtarın tipini/min/max/null iznini tanımlar (AD-22)."""
    feature_version: str
    required_keys: frozenset[str]        # olmadan FAIL
    allowed_keys: frozenset[str]         # ekstra YOK
    key_types: dict[str, type]           # Decimal/float/int/str; None izni ayrı
    nullable_keys: frozenset[str]        # None izin verilenler
    min_value_per_key: dict[str, Decimal \| float \| int]   # opsiyonel (YOKSA atla)
    max_value_per_key: dict[str, Decimal \| float \| int]   # opsiyonel

# Global registry (append-only, immutable erişimli list view; set state ONLY via register_feature_schema)
FEATURE_SCHEMA_REGISTRY: dict[str, FeatureSchemaSpec] = {}

def register_feature_schema(spec: FeatureSchemaSpec) -> None:
    """Sözleşmeli AD-22: sadece kayıtlı feature_version çalışma zamanında doğrulanabilir.
    Strategy/Regime SIDE-EFFECTS yapmadan çağırabilir (aynı spec tekrar → idempotent, raise DEĞİL warning log atlar, log yoksa sessizce pass — ama ilk kez kayıt OLMALI).
    """
    if spec.feature_version in FEATURE_SCHEMA_REGISTRY:
        return  # idempotent, raise DEĞİL
    FEATURE_SCHEMA_REGISTRY[spec.feature_version] = spec

def validate_feature_vector_features(fv: FeatureVector) -> list[str]:
    """Eğer feature_version kayıtlıysa AD-22 doğrulamasını yap → reasons[] list (boş = OK)."""
    spec = FEATURE_SCHEMA_REGISTRY.get(fv.feature_version)
    if spec is None:
        return []  # kaydedilmemişse AD-22 zorlaması bu hikâye için DEĞİL, yalnızca spec var ise çalışır
    reasons: list[str] = []
    keys = set(fv.features.keys())
    missing = spec.required_keys - keys
    extra = keys - spec.allowed_keys
    if missing: reasons.append(f"AD-22 missing required keys: {sorted(missing)}")
    if extra: reasons.append(f"AD-22 extra forbidden keys: {sorted(extra)}")
    for k, v in fv.features.items():
        if k not in spec.key_types: continue
        allowed_type = spec.key_types[k]
        if v is None:
            if k not in spec.nullable_keys:
                reasons.append(f"AD-22 key={k!r} NULL not allowed")
            continue
        if not isinstance(v, allowed_type):
            # Decimal geçersiz kılınmış olabilir, python type check
            reasons.append(f"AD-22 key={k!r} type mismatch: expected {allowed_type.__name__}, got {type(v).__name__}")
            continue
        mn = spec.min_value_per_key.get(k)
        mx = spec.max_value_per_key.get(k)
        if mn is not None and v < mn: reasons.append(f"AD-22 key={k} value={v!r} < min={mn!r}")
        if mx is not None and v > mx: reasons.append(f"AD-22 key={k} value={v!r} > max={mx!r}")
    return reasons
```

---

### 3.2 Contract #2: `MarketRegime` (AD-8 6 Enum + Scores + Detector Version)

**Kod konumu (YENİ DOSYA):** `app/contracts/regime.py`

**Alanlar (tam CONTRACTS.md §3.6):**

| Alan | Tip | Zorunlu | Kural |
|---|---|---|---|
| `timeframe` | `str` | ✅ E | Örn "1h". |
| `regime` | `MarketRegimeState` (StrEnum) | ✅ E | Tam 6 değer: `bull`, `bear`, `sideways`, `high_volatility`, `low_volatility`, `transition_uncertain`. Başka değer → ValueError. |
| `confidence` | `float` | ✅ E | `0.0 <= confidence <= 1.0` (0 ve 1 dahil). |
| `scores` | `dict[str, float]` | ✅ E | ANAHTARLAR: tam olarak 6 rejim ismi (yukarıdaki). Her key mevcut OLMALI; keyset tam 6 olmalı; her value `float`; her değer ≥ 0.0 (TOPLAM 1.0 olmak ZORUNDA DEĞİLDİR, CONTRACTS §3.6: "Toplam 1 olmak zorunda DEĞİLDİR"). |
| `detector_version` | `str` | ✅ E | Örn `"regime_kb_v1.0.0"`; regex benzeri feature_version. |
| `feature_version` | `str` | ✅ E | Girdi FeatureVector sürümü (AD-22 bağlantısı). |
| `lookback_ts` | `TimeRangeSpec` (nested dataclass) | ✅ E | `{ start: Instant, end: Instant }`; start ≤ end (string compare çalışır çünkü ISO-8601 UTC sıralanabilir). |

**Enum + Nested:**
```python
from enum import StrEnum

class MarketRegimeState(StrEnum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITION_UNCERTAIN = "transition_uncertain"

_REGIME_KEYS = frozenset(s.value for s in MarketRegimeState)

@dataclass
class TimeRangeSpec:
    start: Instant
    end: Instant
    def __post_init__(self):
        if not validate_instant(self.start): raise ContractSchemaError(f"lookback_ts.start bad instant: {self.start!r}")
        if not validate_instant(self.end): raise ContractSchemaError(f"lookback_ts.end bad instant: {self.end!r}")
        if self.start > self.end:  # ISO string compare YETER
            raise ContractSchemaError(f"TimeRangeSpec.start {self.start} > end {self.end}")
```

**Invariant (post_init):** `scores.keys() == _REGIME_KEYS` → 6 key TAM; her value `isinstance(float)` + ≥ 0.0 + ≤ 1.0 (max 1, confidence ayrı). `confidence` yine [0, 1].

---

### 3.3 Contract #3: `StrategyContext` (AD-25 Typed, Pure, Reference ONLY Fields — NO Mutations)

**Kod konumu (YENİ DOSYA):** `app/contracts/strategy.py` (aynı zamanda StrategySignal burada)

**Not:** StrategyContext bir envelope payload DEĞİLDİR. Strategy plugin arayüzü (ileride S-STR-01) için input DTO. AD-25 uyarınca alanlar SADECE reference/nested typed dataclass içinden okunur; context içinde EXCHANGE/DB/FILE/WS importu YOK (dosya kendisi yapmaz — sadece helper olarak `derive_from_envelope` metodu vardır).

**Alanlar (tam CONTRACTS.md §3.8 + eksik Placeholder tipleri):**

| Alan | Tip | Zorunlu | Kural |
|---|---|---|---|
| `symbol` | `Symbol` (str) | ✅ E | `validate_symbol_canonical(symbol) == True`. |
| `as_of` | `Instant` | ✅ E | "Şu anki zaman" strateji için tek kaynak — sistem saati ASLA okunmaz (pure). |
| `clock_ref` | `ClockRef` (app/contracts/canonical.py — MEVCUT) | ✅ E | Doğrudan envelope'dan kopyalanır, **DEEP COPY** olmalı — envelope reference ile yanlışlıkla değiştirilmeye karşı. AD-4/CAP-1 korur. |
| `features` | `FeatureVector` (bu hikâye 3.1) | ✅ E | AD-22 flat sözlük; frozen DEĞİL ama AD-9: Strategy **SADECE okur, mutates ETMEZ (test asserts)**. |
| `regime` | `MarketRegime` (bu hikâye 3.2) | ✅ E | AD-8 6 rejimli reference. |
| `portfolio_ctx` | `PortfolioContextView` (YENİ nested minimal salt okunur placeholder — bu hikâyede FIELDS YOK, sadece iskelet ve typed alanlar ZORUNLU DEĞİL, placeholder — Gelecek S-CON-02B'de PortfolioContext tamamlanacak) | ✅ E | Minimal placeholder (required olsun ama body boş olabilir dataclass). |
| `eligibility_ctx` | `EligibilityContextView` (nested minimal placeholder dataclass) | ✅ E | CONTRACTS §3.8 şeklinde: `{ eligible: bool, reasons: list[str] }`. |
| `scoring_policy` | `OpportunityScoreComponentPolicy` (nested minimal placeholder) | ✅ E | Gelecekte S-CON-02B'de şema tanımlanacak; şimdilik `policy_version: str` + `component_keys: list[str]` placeholder. |
| `strategy_params` | `dict[str, int \| float \| str \| bool \| Decimal \| None]` | ⭕ K | Opsiyonel; Default boş dict. Primitif dışı tip (nested/list) YASAK (AD-25 purity). |
| `run_mode` | `RunMode` (types.py mevcut) | ✅ E | Envelope'dan kopya. **STRATEJİ KODU BRANCH YAPMAZ** ama metadata mevcut (debugging için). |
| `source_type` | `SourceType` (types.py mevcut) | ✅ E | Aynı şekilde kopya. |

**Nested Placeholder'lar (gelecek hikâyelerde tamamlanacak, bu hikâyede iskelet + type safety):**
```python
@dataclass
class PortfolioContextView:
    """AD-25/3.8 — Salt okunur portfolio görünümü (gelecek S-CON-02B'de field'lar dolacak).
    Şimdilik placeholders: sadece 'view_id' (correlation_id benzeri) + boş default. Strateji kodunun
    gerçek pozisyonlara erişmeden çalışması için şimdilik placeholder (contract testleri asserts
    TÜM FIELD'lar immutable (dondurma değil, getattr ile setattr DENENDİĞINDE StrategyContext biz
    __setattr__ ile ENGELLEMEYECEĞİZ — ama contract testleri strategy kodunda bunu zorlar,
    şimdilik context sınıfı dataclass)."""
    view_id: str = ""  # Default empty; gelecekte ULID; şimdilik validasyon boş
    placeholder: bool = True

@dataclass
class EligibilityContextView:
    eligible: bool
    reasons: list[str]  # Boş olabilir.

@dataclass
class OpportunityScoreComponentPolicy:
    policy_version: str
    component_keys: list[str]  # Örn ["trend", "momentum", "regime_compat"]; boş olabilir.
```

**Helper (constructor kısa yol — AD-17):**
```python
@staticmethod
def derive_from_envelope(
    envelope: CanonicalEventEnvelope,
    *,
    features: FeatureVector,
    regime: MarketRegime,
    as_of: Instant | None = None,
    portfolio_ctx: PortfolioContextView | None = None,
    eligibility_ctx: EligibilityContextView | None = None,
    scoring_policy: OpportunityScoreComponentPolicy | None = None,
    strategy_params: dict | None = None,
) -> "StrategyContext":
    """Envelope'dan safe (deep-copy clock_ref) olarak StrategyContext üret (AD-17/CAP-1).
    as_of = None ise envelope.timestamp kullanılır (doğru davranış)."""
```

---

### 3.4 Contract #4: `StrategySignal` (FR-025/026/027 + v1 Hard Boundary)

**Kod konumu (aynı `app/contracts/strategy.py`, 3.3 ile beraber)**

**Alanlar (tam CONTRACTS §3.9 + ek Kullanıcı gereksinimi: confidence, expected return / edge, supporting feature/regime refs, correlation & causation meta):**

| Alan | Tip | Zorunlu | Kural |
|---|---|---|---|
| `strategy_id` | `str` | ✅ E | Örn `"trend_following"`, `"momentum"`; regex `^[a-z][a-z0-9_]*$`. |
| `strategy_version` | `str` | ✅ E | Örn `"1.0.0"`; semver benzeri. |
| `direction` | `SignalDirection` (StrEnum) | ✅ E | Tam: `long / flat / hold`. **`short` YASAK (v1)**. Başka değer Yok. |
| `entry_thesis` | `str \| None` | ⭕ K | Opsiyonel. |
| `entry_price_ref` | `Decimal \| None` | ⭕ K | Opsiyonel; parasal → Decimal (float YOK). |
| `stop_policy` | `StopPolicySpec \| None` (nested) | ⭕ K | CONTRACTS §3.9 şeklinde: `stop_type: Literal["fixed","trailing"]`; `stop_ref_price?: Decimal`; `stop_bps?: float`. |
| `take_profit_policy` | `TakeProfitPolicySpec \| None` (nested) | ⭕ K | Aynı: `tp_type: Literal["fixed","scale"]`; `tp_levels?: list[Decimal]`; `tp_bps?: list[float]`. |
| `signal_strength` | `float` | ✅ E | `[0.0, 1.0]` dahil. |
| `confidence` | `float \| None` | ⭕ K | Kullanıcı gereksinimi (ek alan). Verilirse [0, 1]. |
| `expected_edge_bps` | `float \| None` | ⭕ K | Beklenen edge (net of cost); bps. Negatif olabilir (kayıp beklentisi). |
| `supporting_feature_keys` | `list[str]` | ✅ E | Kullanıcı gereksinimi. Referans gösterilen feature anahtarları (AD-22 feature_vector.features key). Boş dizi olabilir. |
| `supporting_regime_evidence` | `dict[str, float]` | ✅ E | Kullanıcı gereksinimi. Hangi rejimler sinyali destekledi — keyset = 6 rejim olmasa da olur (keys REGIME_KEYS içindedir, ekstra YOK) → validate. |
| `correlation_id` | `ULID` (str) | ✅ E | Kullanıcı gereksinimi. Zincir sabit — StrategyContext.correlation_id ile AYNI. |
| `causation_id` | `ULID` (str) | ✅ E | Kullanıcı gereksinimi. Bu sinyali doğrudan tetikleyen event_id (genellikle StrategyContext'i üreten parent ya da envelope). |

**Nested ve Enum:**
```python
class SignalDirection(StrEnum):
    LONG = "long"
    FLAT = "flat"
    HOLD = "hold"
    # NOTE: SHORT YOK (v1 hard boundary)

@dataclass
class StopPolicySpec:
    stop_type: Literal["fixed", "trailing"]
    stop_ref_price: Decimal | None = None
    stop_bps: float | None = None
    def __post_init__(self):
        if self.stop_bps is not None and not isinstance(self.stop_bps, float):
            raise ContractSchemaError("StopPolicySpec.stop_bps must be float or None")

@dataclass
class TakeProfitPolicySpec:
    tp_type: Literal["fixed", "scale"]
    tp_levels: list[Decimal] | None = None
    tp_bps: list[float] | None = None
```

---

## 4. Out of Scope (Kesin)

| Kapsam Dışı | Neden |
|---|---|
| ✖️ Kalan 15 sözleşme (OpportunityScore, RiskDecision, PaperOrder, PaperFill, Position, PortfolioSnapshot, ModelVersion, ModelEvaluation, LimitsSnapshot, LifecycleTransitionPayload, ChampionChallengerEvaluationPayload, 2-3 Placeholder nested) | Ayrı hikâyeler S-CON-02B / S-CON-02C. |
| ✖️ Feature hesaplama, Regime detection algorithm kodu, Trend/Momentum Strategy implementasyon | BUNLAR E-FEA / E-REG / E-STR hikâyeleri. Contract SADECE TIP. |
| ✖️ AI/ML, Model eğitim, Feature leakage kontrolleri (AD-16/FR-043) | E-AIS / E-FEA SCOPE. |
| ✖️ Risk Engine, Backtest Engine, Paper Trading, Fill Model | Ayrı hikâyeler (E-RSK, E-BKT, E-PTR). |
| ✖️ PostgreSQL / TimescaleDB / Object Storage / Kafka / Redis / External Broker | E-PLN/E-STORAGE; AD-6, AD-15. |
| ✖️ WebSocket/REST canlı adapter, API key, gerçek emir, gerçek para | MVP Hard Boundary (Brief §4, PRD §1 FR-061/063). |
| ✖️ FastAPI/React dashboard, MVP API surface (CAP-6) | S-API-03, E-API epic. |
| ✖️ Pydantic, attrs, msgspec, cattrs, pyright, contracts.py — yeni runtime DEP | Stdlib-only kuralı (3 kez teyit: S-RDH-01, S-RDH-02, S-PLN-01). |
| ✖️ Asyncio, async event loop, async publish/subscribe | E-PLN async port (ileride). Bu hikâye SYNC contract dataclasses. |
| ✖️ Mevcut `app/contracts/{canonical,market,types,__init__}.py` public import kırma | Geriye Dönüş Uyumluluğu. |
| ✖️ Yeni PyPI bağımlılığı — pyproject.toml `dependencies=[]` değişmemeli | Stdlib-only. |

---

## 5. Öncüllük Bağımlılıkları (HEPSİ MEVCUT)

```
S-FND-01 Skeleton           → ✅ VAR (klasör iskeleti)
S-FND-03 Forbidden Tests    → ✅ VAR (offline blocker + credential tarayıcı)
S-CON-01 Envelope+Quality   → ✅ VAR (app/contracts/canonical.py 4 sınıf + types 4 enum)
S-RDH-01 Replay Pipeline    → ✅ 68/68 PASS (app/contracts/market.py 5 payload şeması)
S-RDH-02 Replay Registry    → ✅ 64/64 PASS (toplam 132)
S-PLN-01 Typed Bus + Corr   → ✅ 42/42 PASS (toplam 174)
```

**Yeni Dosya (Sadece EKLE, mevcutları düzenleme):**
```
app/contracts/
  feature.py          # YENİ: FeatureVector + LookbackWindowSpec + FeatureSchemaSpec + REGISTRY + validate
  regime.py           # YENİ: MarketRegimeState (enum 6) + MarketRegime + TimeRangeSpec
  strategy.py         # YENİ: 3 nested placeholder + StrategyContext + 2 enum + 2 policy nested + StrategySignal
# Mevcut (düzenleme YOK, SADECE __init__.py'de import+__all__ EKLE):
  __init__.py         # MODIFİYE: Yalnızca yeni import satırları + __all__ ekleri. YENİ public API:
                      #   FeatureVector, LookbackWindowSpec, FeatureSchemaSpec,
                      #   FEATURE_SCHEMA_REGISTRY (read-only görünürlük),
                      #   register_feature_schema, validate_feature_vector_features,
                      #   MarketRegimeState, MarketRegime, TimeRangeSpec,
                      #   SignalDirection, StopPolicySpec, TakeProfitPolicySpec,
                      #   StrategyContext, StrategySignal,
                      #   PortfolioContextView, EligibilityContextView, OpportunityScoreComponentPolicy,
                      #   ContractSchemaError
```

> **GERİYE DÖNÜŞ ÖNLEMİ:** `__all__`'a sadece YENİ ekleme; mevcut 22 öğe (CONTRACT_VERSION, RunMode, CanonicalEventEnvelope, MarketTick vb.) SİLİNMEZ, SIRALARI DEĞİŞMEZ, AYNEN KORUNUR. `from app.contracts import MarketTick` çalışmaya DEVAM etmeli (S-RDH-01 68 testi).

---

## 6. Technical Approach — Adım Adım

### 6.1 ContractSchemaError Ortak Exception
- Her 3 yeni dosyanın içinde ya da ortak `app/contracts/exceptions.py` (tek dosya) oluştur.
- `ContractSchemaError(ValueError)` subclass — message dosya:alan:sebep.

### 6.2 3 Yeni Dosya Oluştur (feature.py, regime.py, strategy.py)
- Sadece stdlib dataclass + imports: types.py mevcut helpers, canonical.py ClockRef/QualityFlags/SchemaRef/CanonicalEventEnvelope GEREKTİĞİNDE import; market.py içindeki şeylere ihtiyaç YOK (SIL — bağımsız).
- Her sınıfta `__post_init__` validasyon; `to_sorted_dict()`; `schema_sha256()`.

### 6.3 `app/contracts/__init__.py`'i GENİŞLET (sadece ekleme)
- Mevcut 22 satırlık `__all__`'ı AYNI TUT; sonuna 22 yeni isim EKLE.
- Mevcut import satırlarını DOKUNMA; yeni `from app.contracts.feature import ...` blokları EKLE.

### 6.4 Contract Testlerini Oluştur
Alt bölme: **Unit (5 sözleşme × 7) + Integration (Feature↔Regime↔Context↔Signal zinciri) + CAP-1 parity static scan + CAP-2 quality bayrakları koruma (referans) + Determinism (to_sorted_dict 10× aynı digest) + Network/Credential safety + AD-22 FeatureSchema registry validate + AD-25 StrategyContext purity (forbidden import static scan)**. Toplam ≥ 50 yeni test.

---

## 7. Acceptance Criteria — 30/30 (Her biri Test Edilebilir)

> Grup adları ve her AC için test planı aşağıda "Test Planı" bölümünde detaylandırılmıştır.

### Grup 1: Geriye Dönüş Uyumluluğu (5 AC)

| # | AC | Kriter | Referans |
|---|---|---|---|
| C-01 | **S-RDH-01 68/68 PASS DÜZENLEMESİZ** | Mevcut 68 test — hiçbir S-RDH-01 dosyası değiştirilmeden. | Hard Kural 2 |
| C-02 | **S-RDH-02 64/64 PASS** | Aynen. | Hard Kural 2 |
| C-03 | **S-PLN-01 42/42 PASS** | Aynen (toplam 174/174 regression). | Hard Kural 2 |
| C-04 | **app/contracts/__init__.py public importları KORUNDU** | `from app.contracts import CONTRACT_VERSION, RunMode, CanonicalEventEnvelope, MarketTick` — hepsi çalışır. | Hard Kural 1 |
| C-05 | **pyproject.toml dependencies = [] HALEN** | 0 yeni PyPI dep. | Hard Kural 3 |

### Grup 2: FeatureVector + AD-22 (7 AC — AD-22)

| # | AC | Kriter |
|---|---|---|
| C-06 | `FeatureVector` alanları REQUIRED — `feature_version`, `timeframe`, `features`, `lookback_window`, `input_refs` eksik → ContractSchemaError. |
| C-07 | `features` nested dict/list VERİLDİ → raise ContractSchemaError (AD-22 flat). |
| C-08 | `FeatureSchemaSpec` registry: `fv_mvp_v1.0.0` için 3 required key tanımla → validate_feature_vector_features EKSİK anahtarda reasons[] 1 öğe. |
| C-09 | Yanlış tip (örn Decimal olması gereken feature float verildi) → validate_feature_vector reasons[] type mismatch. |
| C-10 | `to_sorted_dict()` 2 kez → içerik AYNI ise digest AYNI (determinism). |
| C-11 | `null_count` verilmemiş → `__post_init__` hesaplar ve eşleştir; yanlış verilmiş → FAIL (ContractSchemaError). |
| C-12 | `lookback_window.count < 1` ya da timeframe boş → raise. |

### Grup 3: MarketRegime + AD-8 6 Enum (6 AC)

| # | AC | Kriter |
|---|---|---|
| C-13 | `MarketRegimeState` enum 6 değer: tam isimler, başka değer atanamaz. |
| C-14 | `regime = "bullx"` (yanlış string enum cast) → raise. |
| C-15 | `confidence < 0.0 or confidence > 1.0` → raise. |
| C-16 | `scores` 6 key TAM değil — EKSİK ya da EKSTRA → raise. |
| C-17 | `scores["bull"] = -0.1` ya da > 1.0 → raise. |
| C-18 | `lookback_ts.start > end` → raise. |

### Grup 4: StrategyContext + AD-25 Purity (6 AC — AD-25)

| # | AC | Kriter |
|---|---|---|
| C-19 | `StrategyContext` REQUIRED alanları verildi → `__post_init__` OK; `symbol` canonical değil → raise. |
| C-20 | `derive_from_envelope(envelope, features, regime)` helper → `run_mode`, `source_type`, `clock_ref` envelope'dan kopyalı; `as_of` None → `envelope.timestamp`; `clock_ref` **DEEP COPY** (sonra envelope.clock_ref değiştirilse de Context etkilenmez). |
| C-21 | `eligibility_ctx` placeholder: `eligible=True/False` ile çalışır; `reasons=[]` boşsa OK. |
| C-22 | `strategy_params` nested dict VERİLDİ → raise ContractSchemaError (AD-25 purity, primitif ONLY). |
| C-23 | Static AST scan: `app/contracts/strategy.py` içinde `requests / httpx / websocket / asyncpg / psycopg / sqlalchemy / pydantic / kafka` YOK — 0 match. |
| C-24 | `scoring_policy.policy_version` boş değil, `component_keys` string listesi → raise. |

### Grup 5: StrategySignal + v1 Hard Boundary (3 AC)

| # | AC | Kriter |
|---|---|---|
| C-25 | `direction = "short"` VERİLDİ → SignalDirection enum → **ValueError (geçersiz)** (v1 hard boundary — brief §4, PRD §1 FR-061). |
| C-26 | `signal_strength = -0.01 or 1.01` → raise; `expected_edge_bps` float değilse raise; Decimal ise `entry_price_ref` outside Decimal → raise. |
| C-27 | `supporting_regime_evidence` içinde "bullx" EKSTRA key (REGIME_KEYS içinde değil) → raise; correlation/causation ID'ler format olarak ULID benzeri uzunluk (26 chars) kontrolü (types.py yoksa basit length ≥ 8, bu hikâyede basit validasyon). |

### Grup 6: CAP-1 · CAP-2 · Determinism · Forbidden Pattern (3 AC)

| # | AC | Kriter |
|---|---|---|
| C-28 | **CAP-1:** 4 yeni contract dosyasında `run_mode` / `source_type` if-branch AST taraması 0 finding. (Sadece field isimlerinde geçebilir ama `if run_mode ==` YOK.) |
| C-29 | **CAP-2:** StrategyContext içindeki `clock_ref`/`features`/`regime` referansları ile envelope quality_flags KENDİNDE MUTATE EDİLMİYOR; test "Context aldıktan sonra envelope.quality_flags.stale = True yap → Context.features.features dict id AYNI (mutable referans TUTULUYOR AMA contract KENDİSİNDE SET YOK)". Bu hikâyede 0 set attribute 4 contract dataclass için manuel assertion yok — sadece AD-22/AD-25 doğrulaması. |
| C-30 | **Determinism 10×:** FeatureVector(aynı input), MarketRegime(aynı input) için 10 kez → `schema_sha256()` 10 kez eşit (`all(digests[0] == d for d in digests)`). |

---

## 8. Definition of Done — 14/14 (Hepsi Ölçülebilir)

| # | DoD Kriteri | Test/Doğrulama |
|---|-------------|-----------------|
| DoD-01 | 30/30 AC HEPSİ testlerle doğrulandı → PASS. | pytest contract marker + unit. |
| DoD-02 | Geriye Dönüş: S-RDH-01 (68/68), S-RDH-02 (64/64), S-PLN-01 (42/42) — **174/174 regression PASS**. | Full suite. |
| DoD-03 | Toplam test sayısı: **≥ 224** (174 eski + 50 yeni contract). PASS oranı ≥ 99.5% (tek fail yok). | Test collect + run. |
| DoD-04 | **Stdlib-only.** `pyproject.toml dependencies = []` HALEN; 0 yeni PyPI install. | pyproject diff. |
| DoD-05 | **`CONTRACT_VERSION` HALEN `"1.0.0"`** (S-CON-01 ile tutarlı — yükseltme YOK). | `from app.contracts import CONTRACT_VERSION` assert. |
| DoD-06 | 3 Yeni dosya + 1 modify (`__init__.py`) — başka mevcut `app/contracts/*.py` public API IMZA değişmedi. | Diff incelemesi + test import. |
| DoD-07 | **AD-22:** FeatureSchemaRegistry + validate çalışıyor; 1 scenario positive + 2 negative PASS. | tests/contracts unit. |
| DoD-08 | **AD-25:** StrategyContext purity static scan + `strategy_params` nested YOK. | AST. |
| DoD-09 | **CAP-1 static scan:** 4 yeni dosya 0 forbidden branch. | regex + AST. |
| DoD-10 | **v1 hard boundary:** SignalDirection.short enum değeri YOK + C-25 test PASS. | unit. |
| DoD-11 | **Determinism 10×:** 4 contract 2 tanesi için digest 10× eşit. | unit loop. |
| DoD-12 | **Network Safety + Credential Safety:** (a) yeni contract dosyalarında "api_key", "BINANCE_API_KEY" concat HİÇBİR ŞEKİLDE YOK (tarayıcı testi çalışırken YENİ exclude name GEREKİRSE test dosyası adını exclude_names EKLE — bu bir HİKÂYE GÖREVİ — credential tarayıcıların kendi listelerine `test_contracts_no_credentials.py` ekle (opsiyonel: ya da concat kullanmıyorsak zaten 0 match). | credential tarayıcı PASS. |
| DoD-13 | **Contract Tüm 4 sözleşme to_sorted_dict() çalışıyor; empty ya da boş nested list/feature vector için JSON dumps sort_keys çalışır.** | unit. |
| DoD-14 | **Örnek End-to-End zincir testi:** (a) candle payload → FeatureVector (5 özellik: rsi14=70.2 float, sma20=Decimal("45000.5") …), (b) FeatureVector → MarketRegime (confidence=0.8, bull=0.82, … 6) (c) envelope → StrategyContext derive, (d) StrategySignal üret (direction=long, signal_strength=0.7). (e) HEPSİ -> ayrı zarf olarak publish et (S-PLN-01 bus). (f) bus.published listesinde 4 olay var; her birinin correlation_id AYNI (zincir) → causation_id sırasıyla öncekinin id'si (doğru zincir). Bu 1 integration test → S-CON-02A DOĞRULAMA zoru. | integration test. |

---

## 9. Test Planı — Detaylı (Toplam Tahmini ≥ 52 yeni test)

### 9.1 Test Konumları (YENİ DOSYALAR)

```
tests/
  contracts/
    test_contract_s02a_feature.py            # 14 unit (C-06 → C-12 + 2 AD-22 ek + 3 determinism + to_sorted_dict edge)
    test_contract_s02a_regime.py             # 12 unit (C-13 → C-18 + 2 scores all zero + 1 invalid time range + 3 enum invariant)
    test_contract_s02a_strategy.py           # 14 unit (C-19 → C-27 + 1 context equality + 2 signal deep copy + 2 placeholder)
    test_contract_s02a_cap_parity.py         #  4 contract (C-28 CAP1 + C-29 CAP2 quality ref safe + C-30 10x digest + AD-25 AST forbidden imports scan)
    test_contract_s02a_credentials.py        #  2 credential/network safety (concat kullanmıyorsak boş test + AST scan 0 match — marker contract + failure_injection)
  integration/
    test_s02a_contract_chain_with_bus.py     #  2 integration: DoD-14 (bus ile zincir) + backward compat 174 regression include + 14/14 DoD
  # EXCLUDE: S-RDH-01, S-RDH-02, S-PLN-01 test dosyaları DOKUNULMAZ
```

**TOPLAM:** 14 + 12 + 14 + 4 + 2 + 2 = 48 unit + 2 integration = **≥ 50 yeni test**. Tam tam ≥ 52 (varsayımsal — implementation ek assertion ekleyebilir).

### 9.2 Her Grup İçin Test Case Sayıları

| Grup | AC | Test Sayısı |
|---|---|---|
| G1 Backward Compat | C-01..C-05 | Tam 5 test (4 import + 1 pyproject check + regression full suite — aslında regression var, testi sadece C-04/C-05 unit + fullsuite — 2 contract unit) |
| G2 FeatureVector AD-22 | C-06..C-12 | Tam 14: C-06 (4 eksik field), C-07 (3 çeşit nested), C-08 (3 eksik anahtar), C-09 (2 yanlış tip), C-10 (2 tekrar), C-11 (2 — yanlış + otomatik hesap), C-12 (2) — toplam 14. |
| G3 MarketRegime | C-13..C-18 | 12: C-13 (6 enum + 1 invalid), C-14 (2), C-15 (2), C-16 (2 — eksik/ekstra), C-17 (2), C-18 (1). |
| G4 StrategyContext AD-25 | C-19..C-24 | 14: C-19 (3), C-20 (4 — helper deep copy), C-21 (2), C-22 (2 nested çeşit), C-23 (AST scan — 1), C-24 (2). |
| G5 StrategySignal v1 | C-25..C-27 | 6: C-25 (2 — short enum), C-26 (3 çeşit invalid), C-27 (2). |
| G6 CAP/Det/Forbidden | C-28..C-30 + DoD-12/13/14 | 7: C-28 (1), C-29 (2), C-30 (2 + 2 çeşit contract). |
| **TOTAL** | | **58** unit; + **1 DoD-14 integration** + 1 regression smoke = **≥ 60 yeni test (TAHMİNİ)** — bu hikâyedeki 30 AC için yeterli. |

---

## 10. Mimari Sözleşmelere Uyum Tablosu

| Kural | Bu hikâyedeki uygulaması |
|---|---|
| **AD-3 Canonical Envelope** | 4 contract — ya envelope.payload olarak kullanılır ya da `StrategyContext.derive_from_envelope` aracılığıyla metadata kopyalar. ARA YOK. |
| **AD-4 / CAP-1 Live/Replay Parity** | 4 yeni dosyada 0 forbidden branch; run_mode/source_type SADECE field (AD-25 metadata), if kontrol YOK. |
| **AD-5 / CAP-2 Quality Bayrakları** | 4 contract, quality_flags KENDİNDE SET ETMEZ; StrategyContext sadece envelope içine reference tutabilir (deep copy clock_ref — quality_flags referans). |
| **AD-6 MVP Internal Bus First** | Bus S-PLN-01'de mevcut; bu hikâyede YENİ contract'lar bus ile çalışır (DoD-14 integration test). |
| **AD-7 (Single Writer)** | FeatureSchema kaydı YALNIZCA `register_feature_schema()` ile; FEATURE_SCHEMA_REGISTRY dışarıdan overwrite EDİLEBİLİR ama contract testleri `register_feature_schema` idempotent olduğunu test eder (tek yazma senaryosu). Başka 4 contract'ta state mutation YOK — StrategyContext evaluate dışında. |
| **AD-8 Regime 6 Enum** | Tam uygulanır. |
| **AD-9 Strategy Purity** | StrategyContext SADECE typed reference; network/DB/FS importları strategy.py İÇİNDE 0 match (AST scan). |
| **AD-17 End-to-End Corr/Caus** | StrategySignal `correlation_id` + `causation_id` TAŞIR. StrategyContext helper bunu zarftan kopyalar. |
| **AD-20 Determinism** | `to_sorted_dict()` recursive sorted + schema_sha256 10× aynı. |
| **AD-22 FeatureVector Versioned Flat Dict** | Tam uygulanır (FEATURE_SCHEMA_REGISTRY + validate). |
| **AD-25 StrategyContext Typed** | Tam uygulanır. 4 placeholder dahil. |
| **CAP-3 (ileride)** | StrategyContext içinde forbidden imports AST taranıyor (Hazırlık). |
| **CAP-6 (ileride)** | API contract bu hikâyede YOK. |

---

## 11. Kalan Riskler / Dikkat Edilecekler

1. **`app/contracts/__init__.py` sırayı bozma:** Yeni importlar **SONA EKLENECEK**. Eski 22 `__all__` öğesinin sırası ve adları AYNI. Sıra değişimi S-RDH-01 testlerini KIRABİLİR (örneğin import sırası bağlı code).
2. **Decimal vs Float Karıştırma:** FeatureVector `features` value olarak Decimal/float BOTH kabul eder. `isinstance` kontrollerinde Python `bool` subclass of int old için dikkat: booleans feature value olarak KABUL EDİLMEZ → `isinstance(x, bool)` ise raise (AD-22 helper).
3. **Credential tarayıcı exclude_names:** Yeni oluşturulan `test_contract_s02a_credentials.py` ya benzeri isim — eğer testte hassas pattern kullanıyorsak (KULLANMIYORUZ, zaten concat yoksa 0 match) — 3 credential tarayıcının listelerine yeni test dosyası adı eklenmeli (S-PLN-01'de yapıldı).
4. **SHA-256 Yeni regression baseline:** S-CON-02A'da **YENİ DOSYALAR** mevcut; S-RDH-01 14 dosya SHA listesine dokunulmadığı için (bu dosyalar o listede YOKTUR) regression testleri KIRILMAZ.
5. **v1 Short Kuralı Kalıcılığı:** StrategySignal.SignalDirection.short EKLENMESİN; eklenirse contract_version yükseltildiğine dair bir test yazılmalı (bu hikâyede yok).

---

## 12. Sonuç: Implementation Readiness

Bu hikâyedeki SPEC **tam test edilebilir, tam deterministic, tam backward uyumlu, stdlib-only** şekildedir. Implementation (dev-story) aşamasına hazır.

**Implementation Öncesi Son Kontroller (Hikâye Spec Seviyesinde TAMAMLANDI):**
- ✅ AC sayısı: 30
- ✅ DoD sayısı: 14
- ✅ Tahmini yeni test: ≥ 50 (unit + integration)
- ✅ Forbidden pattern: 0 (pydantic/external broker/short direction YOK)
- ✅ CAP-1/CAP-2: Uygulanabilir (static scan + test)
- ✅ AD-22/AD-25/AD-8/AD-17: Alanlar ve sözleşmeler tam.
- ✅ Backward compat: 174 regression + 5 public contract API'si değişmez.
- ✅ Runtime dep: 0.
- ✅ DoD-14 zincir test: Bus ile doğrulama planı dahil.

**Özel Not:** Bu hikâyede `contract_version_expected` = `"1.0.0"` — bu dosyada bir kırılma (e.g. FeatureVector alan ismi değişseydi) olsaydı version yükseltilirdi. Ama bu hikâye YENİ sözleşmeler ekliyor, mevcut sözleşmeleri değiştirmiyor — contract_version yükseltme YOK.
