---
scope: Champion/Challenger lifecycle transitions + state machine
status: binding
created: 2026-08-10
updated: 2026-08-10
---

# LIFECYCLE — ModelVersion Durum Makinesi (AD-14 / AD-23)

Bu dosya `ModelVersion.status` alanındaki geçerli **durumları**, **geçişleri**, **geçiş önkoşullarını** ve **izin veren komutları** tanımlar. Tüm geçişler SADECE `Model Registry`’nin `request_transition(...)` komut arayüzü üzerinden olur (AD-23). Doğrudan DB `status` alanı güncellemesi **YASAKTIR** (CAP-5).

## Durumlar (sıralı lifecycle)

1. `Candidate` → eğitimi tamamlanmış, ilk değerlendirme bekleyen model.
2. `Tested` → historical backtest + OOS + walk-forward değerlendirmelerinden geçmiş.
3. `Paper` → Paper Trading ortamında çalışıyor/sınanıyor; canlı skorlamada etkisi yoktur ya da challenger olarak parallel track’tedir.
4. `Challenger` → Promosyon kapısı önünde, **Champion’a** karşı karşılaştırma sonucu başarılı bulunan aday.
5. `Champion` → Üretim (v1’de sadece paper-trading production) aktif olarak scoring/decision’ı etkileyen model.
6. `Retired` → Emekli edilmiş; artık scoring kullanılmaz; audit için saklanır.

## Geçiş grafiği

```
Candidate --(run_evaluation)--> Tested
  Tested --(deploy_to_paper)--> Paper
  Paper --(evaluate_vs_champion + promotion_gate_pass)--> Challenger
  Challenger --(promote)--> Champion
    Champion --(rollback)--> [ önceki Champion (eğer varsa) Paper/Challenger ]
    Champion --(retire / yeni model promote)--> Retired
  Any --(deny / fail)--> Retired (ancak denetimli)
  Candidate/Tested/Paper/Challenger --(admin_retire)--> Retired
```

## Her geçişin kuralları

| Geçiş | Komut adı | Önkoşullar | Çıktı (audit/event) |
| --- | --- | --- | --- |
| `Candidate → Tested` | `run_backtest_and_evaluate` | En az 1 tane `ModelEvaluation` (historical_oos), 1 tane (walk_forward) mevcut; `pass_fail=true`. | `model_lifecycle_transition.v1` + eval linkleri |
| `Tested → Paper` | `deploy_to_paper_track` | Paper ortamında model artifact yüklenebilir durumda; champion/challenger track’ine parallel olarak çalıştırılacak simülasyonu başlatmak için minimum örnek sayısı **ADN** (açık kararlar). | Aynı geçiş event; deployment kaydı |
| `Paper → Challenger` | `promote_challenger_candidate` | Min paper trading günü (ADN) + min trade sayısı (ADN) + `champion_challenger_evaluation.v1` karşılaştırmasında `winner=challenger_wins` + `promotion_gate_result.pass=true`. | Geçiş event + karşılaştırma ref. |
| `Challenger → Champion` | `promote_champion` | En az bir insan onayı ya da otomatik approval policy (ADN: karesi); challenger’ın champion’dan üstün metrikleri (ADN) + rollback stratejisi hazır. | Geçiş event → eski champion otomatik `Retired` ya da `Paper` (policy ADN). |
| `Champion → Retired` | `retire_champion` | Bir `Challenger`’ın önceki adıma gelmesi ya da manuel karar. | Geçiş event; yeni champion promotion event’i ile aynı correlation altında tutulur. |
| `Champion → (önceki champion)` | `rollback_champion` | Rollback tetikleyicileri: paper track’te metrik düşüşü, ADN eşikleri aşımı, kill switch. Yeni champion → `Paper` / `Retired`; eski champion (halen kayıtlı ise) tekrar `Champion` olur. | Rollback event + audit reason. |
| `Herhangi bir durum → Retired` | `admin_retire` | Manuel kararlarda izinli; neden kaydedilir. | Geçiş event. |

## İzin Verilmeyen Geçişler (fail hard)

Aşağıdakiler `request_transition(...)` tarafından reddedilir ve audit log + alert üretir:
- `Candidate → Champion`
- `Paper → Champion` (direkt geçiş yoktur; önce Challenger adımından geçmek şarttır)
- `Retired → *` (hiçbir geri dönüş yoktur; yeniden eğitilmiş model yeni model_id/version ile Candidate olmalıdır)
- `Challenger → Paper` (Challenger unpromote edilirse ya Retired ya da özel admin action’ı ile Paper’a dönebilir; bu admin action’da ADN kapsamındadır ve her zaman audit kaydı + onay ile)

## Champion/Challenger parallel çalışma sözleşmesi

- Paper production’da aynı anda birden fazla `Challenger` ve tek bir `Champion` olabilir. İkiden fazla `Champion` olamaz (hata koşulu).
- Champion/Challenger scoring kayıtları aynı contract (OpportunityScore, ModelEvaluation) kullanır; `run_mode` ve `model_id/version` ayrımını yapar.
- Her gün/hafte otomatik `champion_challenger_evaluation.v1` üretilir; sonuç `promotion_gate_result` kaydı altındadır.

## Audit ve korumalar

- Her durum değişikliği: `model_lifecycle_transition.v1` event’i ve ayrı bir audit log tablosu.
- Registry dışından status alanı güncellenemez; contract testleri bunu teyit eder (CAP-5).
- Eski champion’ın restore edilebilmesi için Retired öncesi min 1 dönem bekletme (retired grace period, ADN).
