# Teknoloji Sürüm Gerçekliği İncelemesi — ARCHITECTURE-SPINE.md

**İnceleme Tarihi:** 2026-08-10  
**Kapsam:** Mimari omurgada (Technology Stack / Stack seed bölümleri) belirtilen kütüphane/framework/teknoloji sürümlerinin 2026 Ağustos itibarıyla gerçekliği/güncelliği  
**Karar Verici:** Sürüm yayın geçmişi + resmi yayın kaynakları (GitHub Releases, PyPI, resmi changeloglar)

---

## Sonuç (Verdict)

**⚠️ ENDİŞELER (Concerns)** — Genel olarak sürümler güncel/gerçekçi, ancak 1 kritik uyuşmazlık ve 1 takip geriliği var.

---

## Özet Tablosu

| Teknoloji | Spine'daki Sürüm | Gerçek Durum (2026-08-10) | Durum |
| --- | --- | --- | --- |
| Python | 3.14 | 3.14.6 yayınlanmış (3.14.7 beklenen/1 hafta önce) | ✅ Gerçekçi (patch sürümü pinlenmemiş) |
| PostgreSQL | 18.4 | 18.4, 2026-05-14 yayın — güncel stable | ✅ Tam eşleşme |
| TimescaleDB | 2.29.1 | 2.29.1, 2026-08-04 yayın — son 6 gün | ✅ Tam eşleşme |
| FastAPI | 0.141.1 | 0.141.1, 2026-07-29/30 yayın | ✅ Tam eşleşme |
| React | 19.2.7 | 19.2.7, 2026-06-01 yayın | ✅ Tam eşleşme |
| Vite | 8.1.5 | 8.1.5 (2026-07-16) mevcut ama **8.2.3 (2026-08-06) güncel stable** | ⚠️ 1 minor geride |
| Prometheus | 3.13.2 | 3.13.2, 2026-07-29/30 yayın — son 12 gün | ✅ Tam eşleşme |
| Grafana | **13.1.3** | **13.1.1 (2026-07-21) mevcut; 13.1.2/13.1.3 yayınlanmamış** | ❌ Sürüm mevcut değil |
| pytest | 9.1.1 | 9.1.1, 2026-06-19 yayın | ✅ Tam eşleşme |
| scikit-learn | latest stable (pin sonraya) | — | ℹ️ Kabul edilebilir (bilinçli TODO) |
| XGBoost | latest stable (challenger ops.) | — | ℹ️ Kabul edilebilir (bilinçli TODO) |
| OpenTelemetry | latest stable Python/JS SDK | — | ℹ️ Kabul edilebilir (bilinçli TODO) |

---

## Öne Çıkan Bulgular (Top 5)

### 1. ❌ Grafana 13.1.3 — Sürüm Mevcut Değil (KRİTİK)
- Spine'da yazılan `13.1.3` yayınlanmış bir sürüm değil.
- Grafana 13.1 hattında şu ana kadar yalnızca **13.1.0 (2026-06-23)** ve **13.1.1 (2026-07-21)** yayınlandı.
- 13.2 hattı nightly aşamasında (13.2.0-31059932060, 2026-08-06) ama henüz stable değil.
- **Öneri:** `13.1.1` olarak güncelleyin veya 13.2 stabil olana dek bekleyin.

### 2. ⚠️ Vite 8.1.5 — 1 Minor Geride
- 8.1.5 (2026-07-16) mevcut ve desteklenen bir sürüm (önemli düzeltmeler backport ediliyor).
- Ancak aktif ana hat **8.2.x** — güncel stable `8.2.3` (2026-08-06) yayınlandı.
- 8.2, `experimental.bundledDev` (dev modunda ~15x daha hızlı başlangıç) ve chunk import map gibi yeni özellikler içeriyor.
- **Öneri:** MVP sonrası 8.2'ye yükseltme planlayın; 8.1.5 ile başlamak kabul edilebilir ama 8.2 hattı daha aktif.

### 3. ℹ️ Python 3.14 — Patch Sürümü Pinlenmemiş
- Major+minor (3.14) doğru, ancak 3.14.6 (Haziran 2026) yayınlanmış durumda ve 3.14.7 (Ağustos 2026) çok yakın/son 1 hafta.
- `3.14` olarak belirtmek, uygulamayı minor'ı değil ama patch'leri de alma konusunda yoruma açık bırakıyor.
- **Öneri:** `3.14.6` (veya 3.14.7 çıktıysa onu) gibi tam patch sürümü pinleyin; bilinen bir baz için reproducibility artar.

### 4. ✅ Öne Çıkan Başarı — Tam Eşleşen Sürümler
- **FastAPI 0.141.1**, **Prometheus 3.13.2**, **TimescaleDB 2.29.1**, **React 19.2.7**, **PostgreSQL 18.4**, **pytest 9.1.1** — hepsi yayın tarihleri itibarıyla (10 gün-2 ay arası) son kararlı sürümlerle birebir eşleşiyor. Bu, mimari omurganın sürüm seçiminde gerçekçi olduğunu gösteriyor.

### 5. ℹ️ Unpinned Kütüphaneler (scikit-learn, XGBoost, OpenTelemetry)
- Bu üçü için de "latest stable (MVP implementation sırasında pin)" notu düşülmüş. Bu yaklaşım kabul edilebilir — çünkü:
  - Yazıldıkları gibi, bunlar MVP ilerlerken sürümleri pinlenecek.
  - Özellikle ML kütüphaneleri için son kararlıyı seçip o noktada kilitlemek mantıklı.
- **Öneri:** Uygulama fazına geçer geçmez bu üçlüyü de tam sürüm pin'ine çevirin (örn. `scikit-learn==1.7.x`, `opentelemetry-sdk==1.30.x` gibi).

---

## Aksiyon Önerileri

1. **Grafana 13.1.3 → 13.1.1** olarak düzeltin (en yüksek öncelik, aksi takdirde kurulum başarısız olur).
2. Vite için yorum satırı ekleyin: `8.1.5 (geçiş: 8.2 stabilleşince yükselt)`.
3. Python sürümünü patch'e kadar pinleyin: `3.14.6` veya en son çıkan 3.14.x.
4. Uygulama fazı başlarken scikit-learn, XGBoost, OpenTelemetry sürümlerini pinleyin.

---

**Not:** Bu inceleme yalnızca sürüm gerçekliğiyle ilgilidir — mimari kararları, bağımlılık seçimleri veya teknoloji karşılaştırmaları kapsam dışıdır.
