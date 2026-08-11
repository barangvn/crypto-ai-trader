---
id: SPEC-crypto-ai-trader-2026-08-10
companions:
  - ./CONTRACTS.md
  - ./LIFECYCLE.md
  - ./API.md
  - ./OPEN-DECISIONS.md
  - ../../architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md
sources:
  - ../../briefs/brief-crypto-ai-trader-2026-08-04/brief.md
  - ../../prds/prd-crypto-ai-trader-2026-08-04/prd.md
  - ../../architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md
  - ../../architecture/architecture-crypto-ai-trader-2026-08-10/.memlog.md
---

> **Canonical contract.** Bu SPEC ve `companions:` dosyaları imzalanmış sözleşmedir. Yukarıdaki `sources:` maddeleri yalnızca izlenebilirlik içindir; gereksinimlerle ilgili çelişki durumunda **önce bu SPEC + Companions** geçerlidir (ancak AD-1..AD-25 değiştirilemez; çelişki varsa OPEN-DECISIONS’e yazılır ve bmad-spec update çağrılır).

# Crypto AI Trader v1 — Companion Specification

## Why

PRD + Architecture Spine (AD-1…AD-25) sonrasında, downstream uygulama (epics/stories) öncesinde sözleşme yüzeyini kesinleştirmek ve:
- live/replay parity
- typed contract
- kalite bayrakları
- strategy purity
- risk gate zorunluluğu
- model lifecycle tek ownerlığı
- dashboard read-only MVP API sınırı

konularında **yazan/tester/operatör aynı dili konuşsun** diye bir contract setine ihtiyaç vardır. Bu spec, architecture kararlarını kırmadan, bunları uygulama öncesi sabitleyen koruyucu bir spesifikasyondur.

## Capabilities

- **CAP-1**
  - intent: Feature / Regime / Strategy / Risk / Portfolio kodu, live/replay arasında contractlar dışında farklılaşmasın.
  - success: Bu 5 modülün kod tabanında `if run_mode == "live"` ya da `if source_type == "replay"` dallanması contract testiyle yakalanır; olmamalıdır. Yalnızca adapter/clock layer farklılaşır.
- **CAP-2**
  - intent: Veri kalitesi sorunları (stale, missing, duplicate, out-of-order, invalid, quarantined, degraded), event envelope’da taşınsın; her tüketici validator çağırmadan bu bayraklara göre davranabilsin.
  - success: Risk Engine, herhangi bir RPC yapmadan yalnızca `quality_flags` + kendi `RiskDecision` input’uyla stale/data-failure kararları verebilmektedir.
- **CAP-3**
  - intent: Strategy plugin’leri SADECE typed `StrategyContext` alsın; doğrudan exchange/DB/network/fs çağrısı yapmasın.
  - success: Strategy klasörleri için `pytest` contract taraması (import ve şekil denetimi) failing olmadan geçer.
- **CAP-4**
  - intent: RiskDecision onayı olmadan PaperOrder kabul edilmesin; RiskDecision açık decision/reason/limit_snapshot/position_sizing taşısın.
  - success: Portfolio Simulator, `correlation_id` bazında onaylanmış RiskDecision bulunmayan PaperOrder’ı kesin olarak reject eder.
- **CAP-5**
  - intent: ModelVersion lifecycle state’leri SADECE registry `request_transition(...)` komutu ile değişsin.
  - success: Contract test, storage-layer status write’ını reddeder; sadece LIFECYCLE.md geçiş grafiğine uyanlar kabul edilir.
- **CAP-6**
  - intent: Dashboard MVP API yüzeyi, belirtilen 10 grup + 2 adet ayrı-izinli write endpoint (emergency-stop, kill-switch) ile sınırlı kalsın; gerçek live-spot execution yolu v1’de açılmasın.
  - success: Üretilen OpenAPI şemasında, bu API.md dışında yeni bir execution/keys/funding endpoint’i yoktur ve contract testi ileride eklenmesini engeller.

## Constraints

- PRD hard boundaries değişmez: v1’de **spot only, futures yok, leverage yok (maks 1x), short yok, gerçek emir yok, gerçek para yok, API key yok.** Bu contract’ta geçerli herhangi bir alan bu sınırı ihlal edemez (örneğin direction=short, leverage>1, vb). İhlal eden contract testleri FAIL olur.
- AD-1…AD-25 binding ve değişmez: eğer bu SPEC bir AD ile çakışırsa **AD kazanır ve SPEC’i açıktan düzeltmek için yeni bir bmad-spec update çalıştırmak gerekir** (bu durum bildirilir).
- Gelecekte canlı execution için kapalı kapı: Research → Backtest → Paper → Approval → Live kapıları bu SPEC’te açılmaz; ayrı bir future spec gerektirir.
- Tüm sözleşmelerde timestamp UTC (ISO-8601 + Z + 3-digit ms) ZORUNLUDUR.
- Tüm monetary değerler `Decimal`; AI/skor/olasılık/feature non-monetary ise `float` olabilir.
- correlation_id ve causation_id zorunludur.

## Non-goals

- Bu SPEC, ADN-01…ADN-12 açık kararları zorla cevaplamaz.
- Model eğitim pipeline kodlarını, exchange adapter implementasyonunu, ya da gerçekleştirimi (implementasyon) tanımlamaz.
- UI (dashboard) tasarım/wireframe detaylarını içermez; yalnızca API contract’ını verir (UX/DESIGN için ayrı bir BMad çalışması).
- Üretim (paper production) deployment (CI/CD, container, scaling) detaylarını içermez (mimari AD-18 bağlamı dışında).

## Success signal

- Implementasyon sonrası: (a) 19 contract’tan herhangi biri için yazılan schema testleri %100 coverage’dayken (b) CAP-1…CAP-6 başarı kriterleri contract test suite’inde geçer ve (c) dashboard, MVP API yüzeyini kullanarak kağıt üzerinde çalışır bir paper-trading akışını gösterebilir (demo).

## Assumptions

- SPEC’ten bağımsız olarak, yazım zamanında kullanıcı tarafından “spec oluştur” talebi açıkça yapıldı; interactive soru sorma (guided elicit) yerine EXPRESS distill seçildi.
- 12 ADN’nin kararlanması, downstream epic/story aşamalarında veya ayrı bir çalışmada gerçekleşecektir.
- MVP’nin paper production ortamı, ilk release’da tek örnek/tenant; çoklu tenant sözleşmesi şu anda yoktur.

## Open Questions

Açık kararların tam listesi → [OPEN-DECISIONS.md](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md) dosyasındadır. Başlıca 12 başlık ADN-01…ADN-12. Özetle:
- Exchange/universe/TF/latency SLO
- Strateji kuralları / AI ailesi / skor ve risk eşikleri
- Fill model varsayımları / promotion eşikleri / rollback sahibi
- Object storage / gelecekteki live onay / coğrafya ve hukuk sınırı

Bu sorulara bu SPEC içinde cevap verilmemiştir; future upstream input veya bmad-spec update gerektirirler.
