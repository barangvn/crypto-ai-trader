---
story_id: "S-PLN-01"
story_key: "S-PLN-01"
title: "Typed In-Memory Event Bus + Rich Correlation/Causation Propagation"
status: "ready-for-dev"
created: 2026-08-14
updated: 2026-08-14
epic: "E-PLN: Internal Event Pipeline (Epic 4 — AD-6 Omurga)"
baseline_commit: "3b5b754 feat: implement S-RDH-02 replay bundle registry"
workspace_clean_on_start: true
python_runtime: "cpython-3.14"
runtime_dependencies_new_allowed: 0  # stdlib-only — hiçbir yeni PyPI package YASAK
contract_version_expected: "1.0.0"  # CONTRACTS §1 contract_version yükseltilmemeli
correlation_id_type: "ULID string"  # 26 chars Crockford base32
causation_id_type: "ULID string"    # 26 chars Crockford base32
max_causation_chain_depth_default: 32
event_naming_scheme: "snake_case.vN"  # örn: "candle.v1", "paper_fill.v1", "quarantine_event.v1"
---

# S-PLN-01 — Typed In-Memory Event Bus + Rich Correlation/Causation Propagation

> **HARD KURAL (Geri Dönüş Uyumluluğu — HİÇBİR ŞEKİLDE İHLAL EDİLEMEZ):**
> Mevcut `app/platform/event_bus.py` içindeki `InMemoryTypedEventBus` sınıfının mevcut 4 public metodu:
> 1. `__init__()` imzası + `self.subscribers: dict[str, list[Callable]]` public görünürlüğü
> 2. `subscribe(event_type: str, callback: Callable[[CanonicalEventEnvelope], None]) -> None`
> 3. `publish(envelope: CanonicalEventEnvelope) -> None`
> 4. `publish_many(envelopes: Iterable[CanonicalEventEnvelope]) -> int`
> 5. `clear() -> None`
>
> **BU 5 ÖĞENİN (özellik + metot imzaları) DAVRANIŞI KESİNLİKLE AYNI KALMALIDIR.** S-RDH-01 68/68 testi ve S-RDH-02 132/132 toplam regresyon testi **KAYNAK KOD DÜZENLEMESİZ** geçmelidir. Yeni public özellikler ve metotlar SADECE EKLENEBİLİR; mevcut public metotlar OVERLOAD edilemez, imzaları GENİŞLETİLEMEZ (örn yeni zorunlu parametre YOK). Yeni davranışlar için YENİ adlandırılmış metotlar (örn. `subscribe_typed`, `unsubscribe`, `publish_with_causation`) kullanılmalıdır. SHA-256 hashleri **S-RDH-01 15 kaynak dosyasında** KESİN olarak değişmemelidir (S-RDH-02 testleri SHA-256 değişmemesini assert eder).

---

## 1. Epic ve Bağlam

**Epic:** E-PLN: Internal Event Pipeline (Typed Bus + Outbox) — [EPICS.md §Epic 4](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L396-L402)

> Özgün EPICS Appendix B sıralamasında S-PLN-01 = "#8 In-memory typed event bus (determinist)" idi (bkz [EPICS.md Appendix B madde 8](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L488)). Kullanıcı POC yaklaşımıyla RDH-01/02'yi önden bitirdi; bu hikâye artık onların üstüne inşa ederek minimal POC bus'ı tam AD-6/AD-17/AD-19 seviyesine yükseltir.
>
> Ayrıca: EPICS'te S-PLN-02 (Correlation/Causation Propagation) özgünde ayrı hikâyeydi; kullanıcı bu story içinde birleştirdi. S-PLN-03 (PostgreSQL outbox/inbox) ise açıkça **OUT OF SCOPE**'tur (MVP için memory bus yeterli — durability ihtiyacı sonradan gelir).

**User Story:**
> *As a System Operator / Quant Researcher, I want the in-memory typed event bus to enforce strict typed event filtering, preserve correlation & causation chains, isolate subscriber failures, preserve quality flags in envelopes, and stay fully deterministic with identical publish/delivery order across runs — so that every downstream event from Feature to Regime to Strategy to Risk is traceable end-to-end, a bad subscriber cannot crash the pipeline, and replay fixtures produce bit-wise identical decision outputs.*

---

## 2. Scope — Tamamı Bu Hikâyede

Bu hikâye SADECE aşağıdakileri kapsar (EPICS S-PLN-01 + S-PLN-02 birleşim):

| Grup | Madde | Açıklama | AD/CAP |
|---|---|---|---|
| 1 | **Typed Publish/Subscribe** | `subscribe_typed` (event_type + contract_version_min doğrulamalı), wildcard "*", yanlış payload/yanlış event_type reddi (subscriber bazlı, event DLQ) | AD-6, AD-3 |
| 2 | **Subscriber Lifecycle** | `unsubscribe(token)`, double-unsubscribe güvenli, subscription token dönüş tipi | AD-6 |
| 3 | **Correlation ID Propagation** | Her event publish'te correlation_id EMPTY ise ilk event_id; sonrakilerde AYNI koruma. Helper `derive_child_correlation()` (aynı — sadece set if missing). | AD-17, FR-007 |
| 4 | **Causation ID Propagation + Chain/Depth/Cycle** | `publish_with_causation(envelope, parent_event_id)` → yeni event.causation_id = parent.event_id; causation_depth_counter++; ancestors stack tut; cycle varsa fail-safe DLQ; max_depth=32 aşılırsa DLQ | AD-17, NFR-006 |
| 5 | **Subscriber Failure Isolation** | Tek cb exception → try/except; diğer subscriber'lar devam; failure `dead_letters[]` listesine append; DLQ event'leri correlation ile izlenebilir. Varsayılan: exception YAYILMAZ (break_glass=False). | AD-19, NFR-005 |
| 6 | **Deterministic Publish/Delivery Order** | Aynı event listesi Run 1 vs Run 2: published list same, callback invocation order same, wildcard callbacks type-callbacks SONRA (S-RDH-01'deki sıra aynen korundu: önce type_cb'ler registration order, sonra wildcard_cb'ler registration order — geri dönüş) | AD-20, AD-4, CAP-1 |
| 7 | **Quality Flags Korunması + Quarantined Davranışı** | Bus, envelope.quality_flags üzerinde HİÇBİR değişiklik YAPMAZ (0 set, 0 reset). Quarantined=true olanlar: accept_quarantined=true flagli subscriber alır, diğerleri GÖRMEZ (ancak published log'da hala mevcuttur — test edilebilirlik). | AD-5, CAP-2, CONTRACTS §2 |
| 8 | **Live/Replay Parity** | Bus kodunda `if run_mode == …` veya `if source_type == …` YOK. run_mode/source_type bilgisi SADECE envelope içinde korunur, bus onu USES ETMEZ, TARAMAZ. | AD-4, CAP-1 |
| 9 | **AD-7 Single Writer — State Ownership Ayırımı** | EventBus SADECE kendi state'inin (subscribers sözlüğü + published list + dead_letters list + subscription_token counter + ancestors_causation_stack PER-PUBLISH çağrısı — YANI global olmayan) single-writer'ıdır. Başka modül state'lerini (FeatureVector, Regime, Signal, Risk, PaperOrder) mutate ETMEZ, READ bile ETMEZ (sadece typed subscriber üzerinden event'in payload'ını alan callback'ler yapar). | AD-7 |

---

## 3. Out of Scope (Kesin — Bu Hikâyede Dokunulmaz)

| Kapsam Dışı | Neden |
|---|---|
| ✖️ Kafka, RabbitMQ, Redis Streams, herhangi bir external broker | AD-6 "MVP için typed in-process bus + Postgres outbox sonradan" kuralı — external broker MVP sınırı dışı |
| ✖️ PostgreSQL outbox/inbox tablo implementasyonu, `pg_notify`, TimescaleDB | S-PLN-03 ayrı hikâye; OOS (EPICS Appendix B sonrası) |
| ✖️ S-CON-02 (19 Entity Schema) — FeatureVector / StrategyContext / RiskDecision / MarketRegime / PaperOrder / Portfolio vb eksik 15 contract'ı tamamlama | Ayrı S-CON-02 hikâyeleri; bu bus hikâyesi SADECE zarf + tip + kalite + zincir + subscriber davranışı + teslimat sırası |
| ✖️ S-ELG-01 (eskiden EPICS S-RDH-02 Symbol Eligibility Coordinator, isim çakışması) | AD-21 tek writer view; ayrı hikâye |
| ✖️ S-RDH-03 Market Scanner | Önkoşul = S-ELG-01 + S-CON-02; bu hikâye sonrası gelebilir ama bu hikâyede YOK |
| ✖️ Feature Engineering, Regime Detection, Strategy, Risk, Paper Trading, Backtest, Walk-Forward, Model Registry | Sonraki Epic 5/6/7/8/9/10; bu hikâye sadece OMBURGA |
| ✖️ Exchange WebSocket/REST gerçek bağlantı, API key, gerçek emir | MVP hard boundary (Brief §4, PRD §1 FR-061/063) |
| ✖️ Asyncio event loop, async publish/subscribe (asyncio.Queue) | AD-6 "asyncio queue/topic dispatcher" yazıyor ama MVP için synchronous bus yeterli. İleride async port'u — ama şimdi memory synchronous (S-RDH-01'le uyum) |
| ✖️ Dashboard API, /api/v1 HTTP router implementasyonu | S-API-03 (API contract test) sonraki; bu hikâyede yok |
| ✖️ AI model training / feature leakage lock | E-FEA + S-FEA-03; OOS |
| ✖️ Herhangi bir yeni PyPI runtime dependency (stdlib-only ZORUNLU) | Kullanıcı geçmiş hikâyelerde stdlib-only kuralını 3 kez teyit etti; pyproject.toml dependencies=[] korunur |

---

## 4. Öncüllük Bağımlılıkları (Direct Dependencies — HEPSİ MEVCUT)

```
S-FND-01 Skeleton   → ✅ VAR (AD-1 klasör iskeleti)
S-FND-03 Forbidden Tests  → ✅ VAR (markers + offline blocker conftest)
S-CON-01 Envelope + QualityFlags Schema  → ✅ VAR (app/contracts/canonical.py 4/19 schema)
S-RDH-01 Replay Data Pipeline POC (Minimal InMemoryTypedEventBus + Publish) → ✅ 68/68 PASS
S-RDH-02 Replay Bundle Registry + Multi-Fixture → ✅ 64/64 PASS (TOPLAM 132)
```

---

## 5. Technical Contract — Mimari + Zorunlu Sınıf/Metot Haritası

### 5.1. Mevcut API — KORUNACAK (Geriye Dönüş Uyumluluğu)

[app/platform/event_bus.py InMemoryTypedEventBus](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/app/platform/event_bus.py#L8-L84) Mevcut 5 public API:

```python
# AYNI — dokunulmadan korunmalı
class InMemoryTypedEventBus:
    def __init__(self) -> None:            # KORU: self.subscribers, self.published
    def subscribe(self, event_type: str, callback):  # KORU: no token, None dönüyordu — DEĞİŞTİRME
    def publish(self, envelope): ...      # KORU: sıra: append → type_cb → wildcard_cb
    def publish_many(self, envelopes) -> int: ...  # KORU
    def clear(self) -> None: ...          # KORU
```

> ⚠️ KORU MAKSI: Eski S-RDH-01 testleri `bus.subscribe("candle.v1", cb)` ardından `bus.publish(env)` çağırıyor; yeni `subscribe_typed` ayrı bir metot olmalı. `subscribe`'ın imzası DEĞİŞMEMELİ (token DÖNMEMELİ — eski kod `x = bus.subscribe(…)` kullanmıyor; ama yine de geriye dönüş için None dönmeye devam etmeli. Yeni token dönen subscribe ismi `subscribe_typed` olmalı).

### 5.2. YENİ Eklenecek Public API (Stdlib-only, dataclass)

```python
# YENİ — app/platform/event_bus.py İÇİNE EKLENECEK
# Ama mevcut satırlar DÜZENLENMEYECEK; sadece class içi/sonuna ekleme.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional, Iterable, Protocol, runtime_checkable
from collections import deque

# Yeni tip yardımcılar (stdlib dataclass — YENİ DEP YOK)
@dataclass(frozen=True)  # immutable token
class SubscriptionToken:
    token_id: int            # monotonic counter (busa özgü)
    event_type: str
    created_at_iso: str
    contract_version_min: Optional[tuple[int,int,int]] = None  # (major, minor, patch); None = no check
    accept_quarantined: bool = False

@dataclass
class DeadLetterRecord:
    """Subscriber failure / type mismatch / quarantined skip / causation cycle / depth exceeded → DLQ."""
    dlq_code: str             # "E_SUBSCRIBER_EXC", "E_CONTRACT_VERSION_MIN", "E_CYCLE_DETECTED", "E_CAUSATION_DEPTH", "E_WRONG_EVENT_TYPE", "E_QUARANTINED_SKIP"
    dlq_message: str
    envelope_event_id: str
    envelope_event_type: str
    correlation_id: Optional[str]
    causation_id: Optional[str]
    subscription_token_id: Optional[int]   # None for publish-level errors (cycle/depth)
    exc_type_name: Optional[str] = None    # None for non-exception DLQ
    exc_message: Optional[str] = None
    recorded_at_iso: str = field(default_factory=_utc_iso)

class InMemoryTypedEventBus:  # MEVCUT class — ÜSTÜNE YENİ METOTLAR EKLENİR
    # Yeni public state (ek — geri dönüş kırmaz, eski test published/subscribers erişebilir)
    dead_letters: list[DeadLetterRecord]   # constructor'da [] olarak init — eski __init__ kodunu kırma: "if not hasattr:" kullan veya ek satır
    subscription_counter: int              # sequential token counter

    # ================ YENİ METOTLAR ================
    def subscribe_typed(
        self,
        event_type: str,
        callback: Callable[[CanonicalEventEnvelope], None],
        *,
        contract_version_min: Optional[tuple[int,int,int]] = None,  # None = no contract_version semver check; varsa >= min
        accept_quarantined: bool = False,  # False = quarantined=true olanları GÖRMEZ (DLQ "E_QUARANTINED_SKIP" ile kaydedilir)
    ) -> SubscriptionToken:
        """Return edilen immutable token ile sonra unsubscribe edilebilir."""
        ...

    def unsubscribe(self, token: SubscriptionToken) -> bool:
        """True if bulundu ve çıkarıldı; False double-unsubscribe (idempotent, no-raise)."""
        ...

    def publish_with_causation(
        self,
        envelope: CanonicalEventEnvelope,
        parent_event_id: str,
        *,
        causation_max_depth: int = 32,
    ) -> None:
        """
        publish()'ın causation zinciri sürümü:
          1. Ancestors stack → parent'in parent'ının ... root'a kadar (ancestors traversal —
             published log içinde önceki event'ler üzerinden yürür)
          2. CYCLE kontrol: envelope.event_id ancestors içinde ise → DLQ E_CYCLE_DETECTED,
             publish GERÇEKLEŞMEZ, exception YAYILMAZ.
          3. Depth > causation_max_depth → DLQ E_CAUSATION_DEPTH, publish GERÇEKLEŞMEZ.
          4. OK durumda envelope.causation_id = parent_event_id; correlation_id korunur
             (yoksa parent'ın correlation_id kopyalanır).
          5. Normal publish() yolunu devam ettir.
        """
        ...

    # Helper (public utility — AD-17 observability)
    def trace_causation_chain(self, leaf_event_id: str) -> list[str]:
        """
        published log'dan leaf_event_id başlayıp .causation_id == diğer.event_id
        ile root'a kadar liste çıkar. Root için causation_id == kendi.event_id ise
        zincir orada biter. Olmazsa boş liste. Causation zinciri DETERMİNİSTİK
        (published log insertion-ordered — heapq benzeri determinizm).
        """
        ...

    def get_subscription_count(self) -> dict[str, int]:
        """Snapshot — helper, testing için: event_type → count (wildcard "*" dahil)."""
        ...
```

### 5.3. Backward Compat Mechanik — DETAY

| Eski Davranış | Yeni Hikâye Sonrası Davranış | Uyumlu mu? |
|---|---|---|
| `bus.subscribe("candle.v1", cb)` → `None` dön; `bus.publish(env)` → cb çağrılır | ✅ AYNI (eski subscribe YENİ subscribe_typed DEĞİL). Kendi callback listesinde hala ilk type sonra wildcard — sıra değişmez. | ✅ 100% |
| `bus.published.append(env)` internal append sırası | ✅ AYNI — publish ilk satır append | ✅ 100% |
| Exception cb içinde raise olunca publish çağıranına propagate | ✅ VARSAYILAN AYNI — AMA: YENİ metot `subscribe_typed` ile kaydedilenler için YALNIZCA `break_glass_on_exception=True` set edilmemişse exception DLQ. ESKİ subscribe ile kaydedilenler için İSTİSNA PROPAGASYONU AYNI — çünkü eski testler bunu varsayabilir. Bunu nasıl yapıyorsun: eski subscriber listesi `self.subscribers_old_compat` veya callback kaydında bir flag; DLQ'ya ALMADAN ESKİ GİBİ raise. Bu KESİN — eski 68 test kırılmamalı. | ⚠️ EN ÖNEMLİ DETAY — AC'larde yazıldı, test edildi |

---

## 6. Correlation / Causation Zinciri — Zorunlu Kurallar (CONTRACTS.md §1 ile uyum)

Alıntı [CONTRACTS.md §1](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/CONTRACTS.md#L34-L45):
> `correlation_id` = TÜM zincir boyunca SABİT. İlk adapter/replay girişinde üretilir; her downstream üretimde korunur.
> `causation_id` = BU event'ı DOĞRUDAN tetikleyen event'in `event_id`. Zincirin ilk halkasında `causation_id == event_id`.

Bu hikâyede zorunlu ek mekanikler (AD-17):

| # | Kural | DLQ Kodu |
|---|---|---|
| C1 | Eğer yeni envelope'nin `correlation_id` boş (`None` veya "") ve parent verilmişse → parent'ın `correlation_id` kopyalanır. Parent yoksa ve correlation boş → correlation_id = envelope.event_id (CONTRACTS §1 kural). | Yok |
| C2 | `publish_with_causation` çağrıldığında, ancestors zinciri (published log traversal) oluşturulur: leaf → parent.causation_id → grandparent → ... root'a kadar. Döngü: eğer `envelope.event_id` ancestors listesinde ZATEN mevcut ise → CYCLE — publish GERÇEKLEŞMEZ. DLQ kaydı "E_CYCLE_DETECTED" ile dead_letters.append(). | `E_CYCLE_DETECTED` |
| C3 | Depth check: ancestors sayısı >= `causation_max_depth` (default 32) → publish GERÇEKLEŞMEZ. "E_CAUSATION_DEPTH". | `E_CAUSATION_DEPTH`. |
| C4 | Eğer parent_event_id mevcut eventlerden (published log) BULUNAMAZSA → uyarı ama publish YAPILIR (strict değildir; çünkü replay fixture parent id'leri sıfırdan gelebilir). Sadece uyarı loglu. (Not: future-live strict mode ADN'dir.) | Yok |
| C5 | `trace_causation_chain()` helper: her zaman published log'dan geriye doğru O(N) — OYUNCAK. DETERMİNİSTİK. döndürür. | Yok |

---

## 7. Quality Flags + Quarantined (AD-5 + CAP-2)

| # | Davranış | Doğrulama |
|---|---|---|
| Q1 | Bus, publish yolu boyunca envelope.quality_flags'ın 7 boolean alanını (stale, missing, duplicate, out_of_order, invalid, quarantined, degraded) **ASLA DEĞİŞTİRMEZ.** Sadece okuma yapan subscriber callback'ler görür. 7 boolean + `reasons[]` + `staleness_ms` + `dedup_key` + `expected/actual_sequence` — HEPSİ aynen korunur. Bus hiçbir bayrak set/reset YAPMAZ. | Unit test: 3 farklı envelope quality_flag seti publish. publish SONRASI bayraklar derin-eşit. |
| Q2 | **Quarantined = true olan event'ler:** publish() çağrılınca published log'a AYNEN eklenir. Ancak `accept_quarantined=False` (varsayılan) olan `subscribe_typed` ile kayıtlı subscriber'lar bu event'i ALMAZ. onlara teslim edilmez. Teslim edilmeyen her olay için DLQ `"E_QUARANTINED_SKIP"` kaydı atılır (kaç tane subscriber atladıysa o kadar ayrı record). | Acceptance Criterion'ta test edilir. |
| Q3 | Eski `subscribe()` ile kaydedilen compat subscriber'lar (backward compat): quarantine kabul EDERLER. çünkü eski S-RDH-01 testlerinde quarantined olaylar var. Bu davranış bozulmamalı. Yani eski subscribe → etkilenmez. Yalnızca `subscribe_typed(…, accept_quarantined=False)` filtreler. | Backward compat AC'te test edilir. |

---

## 8. Acceptance Criteria — TOPLAM 28 MADDE

### Grup 1 — Geriye Dönüş Uyumluluğu (YIKILMASIN: 6 AC)

| # | Verilişte | Uygulandığında | Olması Gereken | AD/CAP |
|---|---|---|---|---|
| AC-01 | `from app.platform.event_bus import InMemoryTypedEventBus` import edilip eski 5 public API (__init__, subscribe, publish, publish_many, clear) çağırılırsa | metot imzaları ve parametre sayıları AYNI. Type hint değişikliği sadece genişletme yönlü. Eski callers kırılmaz. | AD-20 |
| AC-02 | S-RDH-01 conftest.py + tüm 68 test DÜZENLEMESİZ çalıştırıldığında | 68/68 PASS. Regression F1: HİÇBİR test FAIL YOK. | Tüm regression |
| AC-03 | Toplam regression (S-RDH-01 + S-RDH-02 birlikte 132 test) | 132/132 PASS. 0 FAIL. | Regression |
| AC-04 | S-RDH-01 15 kritik dosyanın SHA-256 hashleri | ÖNCEKİ baseline (.tmp/srdh01_baseline_sha256.json) İLE KARŞILAŞTIRILDIĞINDA 15/15 AYNI. 0 DEĞIŞIKLIK. Regression F2 PASS. | SHA-256 immutable |
| AC-05 | Eski `bus.subscribe("candle.v1", cb)` ile kaydedilen bir callback içinde Exception raise edilirse | O exception publish çağıranına AYNEN propagate edilir (eski davranış). subscribe_typed ile kaydedilen callback'ten gelen exception PROPAGATE OLMAZ. İki davranış birbirinden ayrıdır. KESİN OLARAK. KARIŞTIRILMAZ. | Backward compat + AD-19 |
| AC-06 | S-RDH-01 test_event_bus_publish_ordered testinde beklenen FIFO + type→wildcard sıra | AYNI. Önce type_cb'ler registration order. Sonra wildcard_cb'ler registration order. published log append İLK OLARAK. Yani sıra: 1) append → 2) type_cb'ler → 3) wildcard_cb'ler. AYNEN S-RDH-01 gibi. — publish_many() davranışı da aynen — sıra değişmez. | Determinism + compat |

### Grup 2 — Typed Bus + Subscriber Lifecycle (8 AC)

| # | Given | When | Then |
|---|---|---|---|
| AC-07 | Boş bus. 2 farklı cb (`cb_a=for candle.v1`, `cb_b=for candle.v1`). İkisi `subscribe_typed("candle.v1", cb)` ile kayıtlı. | 1 tane `event_type="candle.v1"` envelope publish edilir. | Her iki cb de 1 kez çağrılır. Kayıt sırasına göre: önce cb_a → sonra cb_b. |
| AC-08 | `cb_tick = subscribe_typed("market_tick.v1", cb_tick)` kayıtlı. | "candle.v1" envelope publish edilir. | cb_tick 0 kez çağrılır. Yanlış event_type teslim edilmez. DLQ'da YOK (filtre başarılı, DLQ sadece hata için). |
| AC-09 | `subscribe_typed("candle.v1", cb_min, contract_version_min=(1,0,0))` kayıtlı. Envelope contract_version = "1.0.0" | Publish edildi. | cb_min çağrılır. PASS. |
| AC-10 | contract_version_min=(2,0,0) ama envelope contract_version = "1.5.0" | Publish. | cb çağrılmaz. DLQ'da 1 adet "E_CONTRACT_VERSION_MIN" dead_letter kaydı. |
| AC-11 | Wildcard "*" subscriber `subscribe_typed("*", cb_all)` ile kayıtlı. | "candle.v1", "market_tick.v1", "paper_order.v1" 3 event publish. | cb_all 3 kez çağrılır. Sıra: her event için önce type_cb → sonra wildcard_cb. Her zaman. |
| AC-12 | Token = subscribe_typed(...) döndü. | `unsubscribe(token)` çağrılır. Aynı token ile tekrar unsubscribe → double. | İlk unsubscribe True döner. İkinci False döner. Hata YOK. Her ikisi de idempotent. Ardından aynı tip event publish → cb çağrılmaz (çıkarıldı). |
| AC-13 | "wrong-event-type-with-ÜNİCODE-⛄-chars" gibi event_type ve bir de "..slash/dot.notation" event_type. | Her ikisi için subscribe ve publish. | Typed bus bunu reddetmez. İsimlendirme contract enforcement ayrıca S-CON-02/04'tedir; bus sadece string eşitliği yapar. EQUAL ise teslim. |
| AC-14 | contract_version_min parametre tuple yanlış format (ör. (0,) veya (1, 2, 3, 4) — fazla/az) | subscribe_typed çağrısı. | TypeError/ValueError raised (validasyon). Bus kabul etmez. (Kötü kullanıcı — DLQ olmadan raise: bu API kullanıcı hatası, runtime subscriber hatası değil.) |

### Grup 3 — Correlation / Causation + Cycle + Depth (6 AC)

| # | Given | When | Then |
|---|---|---|---|
| AC-15 | E1 event_id=E1, correlation_id=C1, causation_id=E1 (ilk zincir). published log'a eklendi. | publish_with_causation(E2, parent_event_id="E1") çağrılır. E2 correlation_id başlangıçta None idi. | E2 publish SONRASI: E2.correlation_id == C1 (parent'tan kopyalandı). E2.causation_id == "E1". Zincir doğru. trace_causation_chain("E2") → ["E2", "E1"]. |
| AC-16 | 33 event'lik lineer zincir (E1→E2→…→E33), her biri publish_with_causation ile. max_depth default 32. | 33. event için çağrı yapılırken depth 33 olacak. | Publish GERÇEKLEŞMEZ. dead_letters içinde "E_CAUSATION_DEPTH" ile kayıtlı. published log'da 33. event YOK. 32 önceki hala mevcut. |
| AC-17 | E1 publish edildi. Sonra E2 = publish_with_causation(E2, E1). Sonra E3 = publish_with_causation(E3, E2). Sonra: ELT = aynı E1.event_id ile yeni bir envelope (id collision). ELT.causation_id == E3.event_id ile. Zincir E3→E2→E1→ELT→E1 OLARAK döngüsel olsun. (Yani ELT.event_id == E1.event_id.) | publish_with_causation(ELT, E3.event_id). | CYCLE DETECTED. publish GERÇEKLEŞMEZ. DLQ E_CYCLE_DETECTED. published log'u temiz. Önceki E1/E2/E3 aynen korunur. |
| AC-18 | Parent event_id published log'da BULUNAMAZ. (ör. parent id = "OLMAYAN-EVENT-999999") | publish_with_causation(YeniEnvelope, "OLMAYAN-EVENT-999999"). | Publish YAPILIR. (Sadece uyarı — strict değil; fixture için tolerans.) DLQ'da YOK. causation_id doğru atanır. correlation_id parent bulunamadığı için envelope kendi event_id veya mevcut haliyle korunur. |
| AC-19 | İki ayrı parallel zincir (C1 korolu: A→B→C; C2 korolu: X→Y→Z). 2 farklı correlation_id. | trace_causation_chain("C") ve trace_causation_chain("Z") ayrı ayrı çağrılır. | Her iki zincir de kendi root'una kadar doğru. Biri 3 elemanlı, diğeri 3 elemanlı. Birbirine karışmaz. Deterministik sıralama. |
| AC-20 | E1 → E2 (C1 correlation). Yeni envelope EX.correlation_id = None. EX.event_id = EX_ID. publish_with_causation(EX, E2.event_id). | Sonra EX dahil. trace_causation_chain(EX_ID). | [EX, E2, E1]. EX.correlation_id == C1 (parent hattından geldi). DOĞRU. |

### Grup 4 — Subscriber Failure Isolation (AD-19) + DLQ (4 AC)

| # | Given | When | Then |
|---|---|---|---|
| AC-21 | cb1 (success) + cb2 (raise ValueError("simulate bad subscriber")) + cb3 (success) — ÜÇÜ subscribe_typed("candle.v1", …) ile kayıtlı. | 1 tane candle.v1 envelope publish. | cb1 çağrıldı → cb2 exception → cb3 çağrıldı. Sıra cb1, cb2, cb3. cb2 HATASI cb3'ü ENGELLEMEDİ. Bus çökmedi. Exception çağıran publish() fonksiyonuna YAYILMADI. dead_letters içinde 1 adet "E_SUBSCRIBER_EXC"; exc_type_name="ValueError"; exc_message includes "simulate bad subscriber". |
| AC-22 | AC-21 ile aynı ama cb2 eski `subscribe()` ile (compat modu) kaydedilmiş. | Publish. | Eski davranış. ValueError publish çağıranına YAYILIR. (Çünkü AC-05 geriye dönüş kuralı. Eski testler böyle.) Ancak ÖNEMLİ: type_cb olarak kaydedilmiş cb1 (typed) çağrıldıysa onlar ÇAĞRILMIŞ OLABİLİR (sıra matters). Sıra kayıtta cb1 → cb2 (compat) → cb3 ise: cb1 → cb2 raise → cb3'ün çağrılma garantisi YOKTUR (eski davranış). Bu beklenen davranıştır — çünkü eski compat subscribe, exception raise eder. Bunu AC'ler içinde yazıyoruz ki geliştirici yanlışlıkla compat path'i de DLQ'ya almasın. KESİN. |
| AC-23 | Quarantined=true olan bir envelope. 3 subscriber var: S1 accept_quarantined=True, S2=False (default), S3=False. | Publish. | S1 ALDI. S2 ALMADI. S3 ALMADI. dead_letters'da 2 adet "E_QUARANTINED_SKIP". published log'da envelope mevcut. published list 1 eleman arttı. |
| AC-24 | Bus'ta 1000 başarı, 1 başarısız cb hatası, 1 cycle hatası, 1 depth, 2 quarantine skip DLQ'ları var. | Toplam dead_letters sayısı. | 1 + 1 + 1 + 2 = 5. Her bir dlq_code benzersiz ve doğru. correlation_id'leri uyumlu. Sıra: first-fail-first-record. FIFO. Deterministik. |

### Grup 5 — Determinism + Parity + Regression Güvenliği (4 AC)

| # | Given | When | Then |
|---|---|---|---|
| AC-25 | 100 tane fixture event listesi (karışık tip: 40 candle.v1, 30 market_tick.v1, 30 trade_event.v1). 3 typed subscriber (her tipe bir) + 1 wildcard. 2 ayrı bus instance (bus_a, bus_b) — tamamen ayrı. | Run 1: bus_a.publish_many(Liste). Run 2: bus_b.publish_many(Liste). Ardından (a) published log uzunluk + derin eşitlik. (b) her subscriber'ın iç state'i (ör. cb_local_count sayaçları) — eğer aynı sayarsa. | Run 1 == Run 2 — published list DERİN EŞİT. callback invocation order DERİN EŞİT. dead_letters order DERİN EŞİT. Deterministik. |
| AC-26 | BUS source kodunu AST ile taradığımızda `if run_mode ==` veya `if source_type ==` string (case-insensitive) aramasında (import/class/method body). allowlist: `app/processing/replay_clock.py` (bilinen — CAP-1 allowlist). Allowlist dışında 0 match. | CAP-1 static scan çalıştır. | 0 finding. BUS içinde 0 branch. CAP-1 korunur. Doğrudan Bus Sınıfı KENDİSİNDE live/replay ayrımı YOKTUR. (envelope içindeki source_type bilgisi kullanılırsa da subscriber callback'lerinin sorunudur; bus bunu KULLANMAZ.) |
| AC-27 | network-safety conftest'teki offline socket blocker aktifken. bus 100 event publish + subscriber failure 10 tane. | Hicbir outbound network çağrısı YAPILMAZ. pytest network blocker PASSED. | No network: PASS. |
| AC-28 | credentials taraması (api_key, secret, BINANCE_API_KEY, OKX_KEY, send_real_order, place_exchange_order, live_execution) regex'leri app/platform/event_bus.py (YENİ hal) + yeni test dosyaları için çalıştırıldığında. S-RDH-02 sonrası mevcut test_registry_no_credentials.py gibisinden yeni test dosyasındaki hassas kelimeler concat ile gizlenmiş (örn `_S_AP = "api" + "_"` gibi pattern definition — böylece kendi kendini taramaz). | 0 match. PASS. | No credentials: PASS. |

---

## 9. Definition of Done — 12 Maddesi — TAMAMI ZORUNLU

| # | DoD | Doğrulama Yöntemi |
|---|---|---|
| DoD-01 | 28/28 Acceptance Criteria HİÇBİRİ EKSİKSİZ. test suite ile doğrulanmış. | pytest test_pln_01_*.py → tamam PASS. |
| DoD-02 | S-RDH-01 68/68 regression TESTSİ GEÇTİ. HİÇBİR KAYNAK KOD DÜZENLEMESİ OLMADAN. | pytest -k "SRDH01 or tests from tests/unit/* + tests/integration/* for S-RDH-01" — 68 PASS. |
| DoD-03 | Toplam Test Suite (S-RDH-01 68 + S-RDH-02 64 + S-PLN-01 tahmini 35) = **≥ 167 test TOPLAM**. %100 PASS. | pytest tests/ --tb=short — son satır: `≥167 passed in X.XXs`. 0 failed. 0 skipped except allowlisted. |
| DoD-04 | SHA-256: S-RDH-01 15 kaynak dosyasının hash'i 15/15 DEGISMEDI. Regression F2 testi PASS. | tests/unit/ingest/registry/test_regression_srdh01_protection.py parametrize 15 tane PASS. |
| DoD-05 | CAP-1: DOMAIN (bus dahil) içinde 0 yeni run_mode/source_type branch allowlist dışı. | tests/integration/test_srdh02_cap_proofs.py — Hala PASS. Bus için yeni test: test_srdh02_cap_proofs genişletilmiş veya yeni test_pln01_cap1_bus.py PASS. |
| DoD-06 | CAP-2: 7 kalite bayrağı envelope'da BUS publish/subscribe yolu boyunca değişmemiş. QualityFlags testi: 3 farklı set publish → 3 set aynen korunmuş. | test_pln01_cap2_quality_preserved.py PASS. |
| DoD-07 | No network + No credentials: 2 failure injection testi marker ile GEÇTİ. | tests/failure/test_bus_network_safety.py PASS. tests/failure/test_bus_no_credentials.py PASS. marker=failure_injection. |
| DoD-08 | AD-7 Single Writer: Bus, yalnızca KENDİ state'ini (subscribers dict, published list, dead_letters list, subscription_counter) mutate eder. Başka domain state'lerine (feature/regime/strategy/risk/paper order) BUS KODUNDA yazılım YOK. Static scan ile doğrulanır: bus.py içinde bu modüllerin importu YOKTUR. (sadece contracts var — zarf içi, YAZMA YOK.). | test_pln01_ad7_single_writer_bus_only.py — static scan PASS. |
| DoD-09 | Runtime dependency 0: pyproject.toml `dependencies = []` HALEN. 0 yeni PyPI package. | cat pyproject.toml. grep dependencies → []. |
| DoD-10 | Backward compatibility: AC-01..AC-06'daki 6 kural HEPSİ test ile doğrulanmış. subscribe/publish eski yol ile 6 test PASS. Yeni yol 22 test PASS. Ayrı test dosyaları. | test_bus_backward_compat.py (6+) PASS. |
| DoD-11 | Determinism 10×: aynı 100 event 10 kez publish_many — her bir run'da published list, callback count listesi, dead_letters listesi DERİN-EŞİT. Marker = replay. pytest --count=10 plugin yerine — 10x loop ile inline (çünkü --count bağımlılığı — stdlib-only için 10x for loop yeterli). | tests/replay/test_bus_determinism_10x.py 10 kez PASSED. Derin eşit. |
| DoD-12 | Tüm yeni dosyalar Architecture sözleşmesine (AD-1 klasör yapısı) göre konumlandırılmış: yeni kod app/platform/event_bus.py (MEVCUT dosyaya EKLEME — ÜSTÜNE YAZMA!). Yeni testler: tests/unit/platform/*.py (unit), tests/integration/test_pln01_*.py, tests/replay/test_bus_determinism_10x.py, tests/failure/test_bus_*.py — Klasörler AD-1 ile UYUMLU. | Static LS check: paths doğru. app/platform altında; tests/ altında doğru marker paketleri. |

---

## 10. Test Planı — Tahmini ~35 Test — 8-9 Yeni Dosya

> Not: **Mevcut S-RDH-01/S-RDH-02 test dosyalarına DOKUNMA.** Hepsini YENİ test dosyası olarak yaz. Klasör yapısı AD-1.

| Test Dosyası (YENİ) | Marker | Count (Tahmin) | Kapsar (AC/DoD) |
|---|---|---|---|
| `tests/unit/platform/__init__.py` | — | 0 | package marker |
| `tests/unit/platform/test_bus_typed_subscribe.py` | unit | 6 (AC-07..AC-14 arası 8 AC'den 6) | Typed subscribe, wrong type, contract_version min/max, wildcard, unsubscribe (double), unicode event_type, contract_version_min tuple validation |
| `tests/unit/platform/test_bus_backward_compat.py` | unit + regression | 7 (AC-01, AC-06 + 5 ek geriye dönüş) | Eski 5 public API imzası, eski sır (append→type→wildcard), compat exception propagation vs. ESKİ subscribe 2 cb hatası yayılır testi. |
| `tests/unit/platform/test_bus_correlation_causation.py` | unit | 8 (AC-15..AC-20 6 tane + 2 ek: trace boş, trace tek root) | Zincir kuralları, cycle, depth, parent bulunamaması, parallel chains, correlation kopyalama, trace determinizm. |
| `tests/unit/platform/test_bus_failure_isolation.py` | unit + failure_injection preparation | 5 (AC-21..AC-24 4 tane + dlq sıralaması) | cb hatası izole, compat exception yayılma, quarantine skip teslim + dlq kayıtları. |
| `tests/integration/test_pln01_full_pipeline_with_typed_bus.py` | integration | 4 (karma AC birkaçı) | S-RDH-01/02 fixture üzerinden: adapter → normalizer → validator → bus → 3 downstream subscriber (quarantinedleri kabul etmeyen + kabul eden + correlation izleyen). Tüm 200 satırlık veri için teslimat doğru. Dead letters doğru. Causation zinciri: her 4 aşamada. |
| `tests/integration/test_pln01_cap1_bus_no_runmode_branch.py` | integration + contract | 1 (AC-26 + extend) | AST static scan — bus.py içinde 0 allowlist dışı run_mode/source_type branch. 0 finding. |
| `tests/integration/test_pln01_cap2_quality_preserved.py` | integration + contract | 2 (AC-Q1/Q2 + 3 bayrak seti) | 3 ayrı envelope (hepsi farklı 7 boolean combinations) publish → bayraklar aynen. 3 test. |
| `tests/replay/test_bus_determinism_10x.py` | replay | 2 (DoD-11 2x — list + dlq) | 10 kez aynı 100 event — Run i vs Run j: published derin eşit. dead_letters derin eşit. callback_sayaç listesi aynı. |
| `tests/failure/test_bus_network_safety.py` | failure_injection | 2 (AC-27) | Offline blocker aktifken 100 event publish + 3 cb failure — hata yok. Socket monkeypatch RuntimeError bekleniyorsa hiç tetiklenmemiş PASS. |
| `tests/failure/test_bus_no_credentials.py` | failure_injection | 2 (AC-28) | Hassas kelimeler concat ile gizlenmiş pattern. app/platform/event_bus.py (yenisi) + TÜM yeni test dosyaları taraması → 0 match. exclude_names'te kendini + eski S-RDH-01 test_no_credentials.py + S-RDH-02 test_registry_no_credentials.py (exclude edilmişler). 2 test. |
| `tests/contracts/test_pln01_bus_contracts.py` | contract | 2 | Structural check: isinstance InMemoryTypedEventBus; hasattr subscribe_typed + unsubscribe + publish_with_causation + trace_causation_chain. Protocol isinstance TypeError handle et (try/except — hasattr fallback). |
| **TOPLAM** | | **~35 Test** | 28 AC kapsar (bazı AC'ler birden fazla testle — 7+ fazla). Toplam ≥35. |

> Tahmini Final Test Sayısı: 68 (RDH-01) + 64 (RDH-02) + **35 (PLN-01)** = **167 TOPLAM**. Bazı AC'ler 2-3 testle doğrulanırsa ~170+ olabilir.

---

## 11. CAP / AD Referansları — Hikâyede Ele Alınanlar

### Contract Proofs (CAP) — 2'si Doğrudan, 3 Hazırlık

| CAP | Başlık | S-PLN-01'de Durum |
|---|---|---|
| ✅ **CAP-1 (Live/Replay Parity)** | 5 domainde 0 run_mode/source_type branch | **DOĞRUDAN**. Bus dahil 0 branch. AC-26 ve test_pln01_cap1_bus_no_runmode_branch. Geçmiş S-RDH-01/02 testleriyle birlikte 2 katı korunmuş. (Allowlist: `app/processing/replay_clock.py` + gelecekte bus'ta 0.) |
| ✅ **CAP-2 (Quality in Envelope)** | Kalite bayrakları zarf içinde taşınır; her tüketici tek başına kullanır. | **DOĞRUDAN**. Q1: bus 7 bayrağı ASLA değiştirmez. Quarantine=true teslimat filtresi accept_quarantined flag ile. DoD-06 ve test_pln01_cap2_quality_preserved.py. |
| 🧱 **CAP-3 (Strategy Purity)** | Strategy plugin SADECE typed context alır. | **HAZIRLIK**. subscribe_typed + contract_version_min — artık feature_vector.v1 subscriber'ı SADECE onu alır. Gelecekte S-STR-03 bunu kullanır. (Bu hikâyede ana test yok — hazırlık.) |
| 🧱 **CAP-4 (RiskGate + PaperOrder)** | RiskDecision onayı olmadan order YOK. | **HAZIRLIK**. correlation + causation zinciri — RiskDecision → PaperOrder zinciri daha sonra doğrulanabilir. (Ana test S-RSK-02'dir.) |
| 🧱 **CAP-5 (Lifecycle Only-Registry)** | Status sadece registry transition. | **HAZIRLIK**. Bus state AD-7 single writer — ayrışım doğru. Gelecekte CAP-5 bus üzerinden audit event yayınlayabilir. |

### Architecture Decisions — 9 AD

| AD | Başlık | S-PLN-01 Kapsamı |
|---|---|---|
| ✅ **AD-3** | Canonical Event Envelope | **TEMEL KURAL**. Bus, envelope.event_type ve envelope.contract_version ile typed çalışır. contract_version_min doğrulaması. Doğrudan CONTRACTS §1 uygulanır. |
| ✅ **AD-4** | Live/Replay Parity | Bus kodu 0 branch. Sıra her iki run_mode'da aynı. Determinism. |
| ✅ **AD-5** | Data Quality Hard Gate | Bus kalite bayrakları değiştirmez. Quarantine=true → default subscriber teslim ALMAZ. Hard gate downstream. Bus publish sonrası quarantine hala gözükür — ama tüketiciye teslim edilmez. Bu da AD-5'in bir parçasıdır (veri sağlıksız ise akışı kes). |
| ✅ **AD-6** | Internal Event Bus First | **ANA KONU**. Artık POC minimal değil: typed, lifecycle, correlation, causation, failure izole, dead letter, deterministik. Tam MVP gereksinim. (S-PLN-03 outbox OOS.) |
| ✅ **AD-7** | Single Writer State Ownership | Bus, KENDİ state'inin yazarı. Başka domain state'lerine DOKUNMAZ. Unit test ile doğrulandı. Import statik scan ile: feature/regime/strategy/risk/paper_order BUS'TA İMPORT EDİLMEZ. SADECE contracts (read-only). |
| ✅ **AD-17** | End-to-End Observability by Correlation ID | **DOĞRUDAN**. correlation_id koruma, causation zinciri, cycle/depth koruması, trace_causation_chain helper. FR-007 ve NFR-006 uygulanır. |
| ✅ **AD-19** | Failure Defaults to Safe Stop | Subscriber failure → OTHERS etkilenmez. DLQ kaydı. Bus continue. Exception compat path dışında yayılmaz. Safe. |
| ✅ **AD-20** | Testability Architectural Constraint | 8 yeni test dosyası, 35+ test, failure injection, replay 10x determinizm, contract structural, regression — mimari sözleşmesinin testleri. |

---

## 12. Implementation Readiness — Hazırlık Değerlendirmesi

| Madde | Durum | Not |
|---|---|---|
| Öncel Bağımlılıkları — Hepsinin mevcut (FND-01/03, CON-01, RDH-01/02) | ✅ HEPİSİ MEVCUT. 132 test PASS. | Hazır. |
| Kullanıcı S-RDH-01 SHA-256 koruma kuralı | ✅ Mevcut test var — tekrar çalıştırılacak. | Hazır. |
| Typed Bus — AD-6 bağlamı net mi? | ✅ SPEC + ARCHITECTURE-SPINE AD-6 + CONTRACTS §1. | Tam. |
| Correlation/Causation sözleşmesi — CONTRACTS §1 L34-L45 | ✅ Okundu. Aynen uygulanacak. Ek cycle/depth kuralları AC'lerde yazıldı. | Tam. |
| Subscriber Failure Isolation — AD-19 | ✅ Anlaşıldı. DLQ mekanizması + break_glass False varsayılan. | Tam. |
| Quality Flags Quarantine Filtresi — AD-5 CAP-2 | ✅ CONTRACTS §2. Eski compat vs yeni typed ayrımına dikkat. | Tam. |
| Determinism — 10x replay testi | ✅ S-RDH-02 10x testi örnek alınabilir — aynı kalıp. | Hazır. |
| Network + Credentials Safety | ✅ S-RDH-02 aynı kalıp — concat ile pattern parçalama, exclude_names. | Hazır. |
| Stdlib-only 0 dep rule | ✅ Yeni kod: dataclass + collections.deque + typing + time/datetime UTC. hepsi stdlib. | Hazır. |
| İsim çakışması (RDH-02 Registry vs Eligibility) | ⚠️ Bilinen. Bu hikâyede ilgisiz — dokunulmuyor. | Not only. |
| Asyncio queue/topic (AD-6 future) | ⚠️ MVP'de sync. Gelecek için genişletilebilir — public interface'ler async ileride overload edilebilir; ama story içinde dokunulmuyor. | OOS. |
| DLQ persistence (disk/Postgres) | ❌ MVP memory-only. Gelecek hikâyelerde S-PLN-03. | OOS. |

**SONUÇ: HAZIRLIK DURUMU = YEŞİL (READY-FOR-DEV).** Geliştirici tarafında eksik bilgi veya bağımlılık YOKTUR. Hikâye hemen implement edilebilir.

---

## 13. Değiştirilecek/Yeni Dosyalar — Tahmin (Implementation'da — Şu an sadece PLAN)

> ⚠️ BURASI PLAN KISMI. Şu an KOD YAZILMAZ. Uygulama aşamasında:

```
GÜNCELLENECEK (APP KATMANI — 1 DOSYA, SADECE EKLEME, Mevcut 5 public API DOKUNULMAYACAK):
  app/platform/event_bus.py    # InMemoryTypedEventBus İÇİNE yeni metotlar + yeni dataclasslar EKLENECEK.
                               # Mevcut satırlar ÜSTÜNE YAZILMAYACAK. Sadece SONUNA/İÇİNE ek.

YENİ TEST DOSYALARI (9 DOSYA, tahmini 35+ test — HEPSİ YENİ. ESKİ TEST DOSYALARINA DOKUNULMAYACAK):
  tests/unit/platform/__init__.py
  tests/unit/platform/test_bus_typed_subscribe.py            (6 unit)
  tests/unit/platform/test_bus_backward_compat.py            (7 compat + regression)
  tests/unit/platform/test_bus_correlation_causation.py      (8 unit)
  tests/unit/platform/test_bus_failure_isolation.py          (5 unit)
  tests/integration/test_pln01_full_pipeline_with_typed_bus.py  (4 integration)
  tests/integration/test_pln01_cap1_bus_no_runmode_branch.py    (1 cap)
  tests/integration/test_pln01_cap2_quality_preserved.py       (2 cap)
  tests/replay/test_bus_determinism_10x.py                     (2 replay marker)
  tests/failure/test_bus_network_safety.py                     (2 failure injection)
  tests/failure/test_bus_no_credentials.py                     (2 failure injection, concat pattern)
  tests/contracts/test_pln01_bus_contracts.py                  (2 contract marker)

DÜZENLENECEK YOK. SADECE EKLEME. Geri dönüş %100 korunur.
```

---

## 14. Dev Agent Guardrails (EN ZORUNLU 6 MADDE — TEKRAR)

1. 🚫 **S-RDH-01 15 kaynak dosyasını DÜZENLEME.** Onların 68 testi DÜZENLEMESİZ geçmeli. SHA-256 15/15 değişmemeli.
2. 🚫 **Mevcut InMemoryTypedEventBus'un 5 public API (__init__/subscribe/publish/publish_many/clear) — İMZA, DAVRANIŞ, PARAMETRE — değiştirme.** Eski davranış aynen korunmalı. Yeni metotlar EKLE.
3. 🚫 **Exception propagation kuralını KARIŞTIRMA.** Eski `subscribe()` ile kaydedilen compat → exception yükseltilir (AC-05). Yeni `subscribe_typed()` ile kaydedilen → exception DLQ. Yayılmaz. İki ayrı mekanizma.
4. 🚫 **Yeni runtime dep EKLEME.** pyproject.toml dependencies=[] koru. Stdlib kullan (dataclass, collections.deque, typing, datetime UTC, re/gerekirse).
5. 🚫 **Quarantine filtresinde eski subscriber'ları ETKİLEME.** Eski `subscribe()` ile kaydedilenler quarantine olayları GÖRÜR (accept_quarantined=True gibi). Sadece YENİ subscribe_typed(accept_quarantined=False) — default — filtreler.
6. ✅ **Publish sırasını DEĞIŞTIRME.** 1) self.published.append(env) — İLK. 2) type_cb'ler registration order. 3) wildcard_cb'ler registration order. Bu KESİN — S-RDH-01 testleri buna bağımlı (AC-06).
