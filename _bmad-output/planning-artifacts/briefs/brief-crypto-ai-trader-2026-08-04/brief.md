---
title: "Product Brief: Crypto AI Trader"
status: ready-for-review
created: 2026-08-04
updated: 2026-08-04
product: crypto-ai-trader
---

# Product Brief: Crypto AI Trader

## Executive Summary

Crypto AI Trader, çok sayıda kripto **spot** paritesini gerçek zamanlı izleyen; piyasa verisini, teknik sinyalleri, mikro-yapı bilgisini ve denetlenebilir AI analizini birleştirerek fırsatları sıralayan bir karar-destek ve simülasyon platformudur. Ürün, “garantili kâr eden bot” değildir. Amaç; ölçülebilir, tekrar üretilebilir, test edilebilir ve risk kontrollü bir araştırma ile paper-trading sistemi kurmaktır.

İlk sürüm, veri toplama, analiz, backtest, walk-forward doğrulama, model değerlendirme ve paper trading üzerine kurulacaktır. Futures, kaldıraç, short, gerçek para, gerçek emir ve gerçek borsa API anahtarı ilk aşamada kesinlikle kapsam dışıdır. Gerçek spot işlemler ancak kanıtlanmış performans, operasyonel güvenlik, uygun risk limitleri ve açık insan onay kapılarından sonra değerlendirilir.

## 1. Problem

Spot kripto piyasasında fırsatlar çok sayıda parite, hızlı değişen likidite, parçalı veri ve rejim değişimleri arasında dağılır. Manuel takip; fiyat, hacim, order book, trade flow, volatilite, BTC etkisi ve korelasyonları aynı anda tutarlı değerlendirmekte yetersiz kalır. Tek bir stratejiyi her piyasa koşulunda çalıştırmak; aşırı uyum, maliyetlerin göz ardı edilmesi ve kontrolsüz kayıp riski doğurur.

Bugün kullanıcıların ihtiyaç duyduğu şey sinyal üreten kara kutu değil; verinin kaynağını, strateji gerekçesini, AI güvenini, risk kısıtlarını ve gerçekçi işlem maliyetini görünür kılan denetlenebilir bir karar sistemi ve güvenli deneme ortamıdır.

## 2. Vision

Ürün, farklı spot borsalara uyarlanabilen bir piyasa zekâsı platformuna dönüşür: canlı veri alır, piyasa rejimini tanımlar, uygun stratejileri ağırlıklandırır, fırsatları risk-ayarlı biçimde skorlar, aday modelleri sıkı deney kapılarından geçirir ve sonuçları kullanıcıya açıklanabilir şekilde sunar.

Uzun vadeli vizyon, gerçek işlem yapabilen bir sistem değil; önce güvenlik, doğrulama ve işletim disiplini kazanmış, izin verildiğinde de yalnızca spot piyasada kontrollü işlem yapabilen bir platformdur.

## 3. Goals

- Gerçek zamanlı spot piyasa verisini çoklu parite bazında normalleştirmek ve düşük gecikmeli izlemek.
- Fiyat, OHLCV, hacim, bid/ask, order book, trade flow, volatilite, teknik göstergeler, korelasyonlar ve BTC etkisinden açıklanabilir özellikler üretmek.
- En az Bull, Bear, Sideways/Range, High Volatility, Low Volatility ve Transition/Uncertain rejimlerini sınıflandırmak veya olasılıksal olarak skorlamak.
- Birden fazla strateji ailesinin eklenebileceği bir çerçeve ve rejime göre ağırlıklandırma mekanizması sağlamak.
- Backtest, out-of-sample test, walk-forward validation ve paper trading sonuçlarını ortak, maliyet-duyarlı metriklerle karşılaştırmak.
- Champion/Challenger, model registry, performans izleme ve rollback ile kontrollü adaptive learning yaşam döngüsü kurmak.
- Risk motorunu bütün çalışma kiplerinde zorunlu karar kapısı yapmak.

## 4. Non-goals ve Başlangıç Güvenlik Sınırları

- Kâr, günlük getiri veya işlem başına pozitif sonuç garantisi vermek.
- Futures, kaldıraç, short pozisyon, marjin, türev ürün ya da arbitraj yürütmek.
- İlk aşamada gerçek para, gerçek emir, borsa API anahtarı veya trade izni kullanmak.
- Canlı modelin kendisini otomatik ve denetimsiz biçimde değiştirmesine izin vermek.
- İlk MVP’de tüm strateji ailelerini, tüm borsaları veya tam kapsamlı web dashboard’u bitirmek.
- Belirli bir borsaya kalıcı olarak bağlanan mimari tasarlamak.

## 5. Target Users

**Birincil kullanıcı:** Teknik yeterliliğe sahip, spot kripto piyasasını sistematik biçimde araştırmak isteyen bireysel trader/araştırmacı. Başarısı; hangi fırsatın neden öne çıktığını, hangi rejimde bulunduğunu ve risk sınırının ne olduğunu görebilmesidir.

**İkincil kullanıcı:** Strateji ve model performansını deneysel olarak yöneten ürün sahibi veya quant araştırmacı. Başarısı; deneylerin tekrar üretilebilir olması, champion/challenger kararlarının izlenebilmesi ve geri almanın güvenli olmasıdır.

## 6. Core Features ve Kullanıcı Deneyimi

Kullanıcı dashboard’da bot/sistem durumunu, market overview’u, izlenen pariteleri, aktif fırsatları, AI ve confidence skorlarını, piyasa rejimini, risk durumunu, açık/kapanmış simüle edilmiş pozisyonları, P&L, drawdown, strateji/model performansını, öğrenme geçmişini ve sistem loglarını görür.

Bir fırsat kartı; parite, zaman, yönsel tez, rejim, destekleyen sinyaller, skor bileşenleri, güven aralığı/uyarıları, beklenen maliyetler, önerilen risk limiti ve geçersizlik koşulunu gösterir. Kullanıcı, kararın dayanağını geriye doğru inceleyebilir; sistem açıklama göstermeden yalnızca “al/sat” önerisi üretmez. Emergency stop/killswitch görünür ve erişilebilir olur; başlangıçta bu yalnızca paper-trading ile gözlem modlarını durdurur.

## 7. Functional Requirements

### Market Data ve Exchange Adapter

- Exchange adapter arayüzü; WebSocket market data, REST geçmiş veri, sembol/market metadata ve sağlık durumunu soyutlar.
- Sistem; adapter üzerinden fiyat, OHLCV, hacim, en iyi bid/ask, order book güncellemeleri ve trade flow alabilmelidir.
- Veri; zaman damgası, kaynak, parite, sıra/sequence bilgisi ve kalite durumu ile saklanmalı; kopukluk, gecikme, tekrar ve sıra bozulması işaretlenmelidir.
- İlk uygulama canlı bağlanmasa bile adapter sözleşmesi, replay/simülasyon verisi ve sağlayıcı değiştirme ihtiyacını desteklemelidir.

### Analytics, Regime ve Opportunity Scoring

- Teknik analiz katmanı, sürüm kontrollü gösterge/özellik hesapları sağlar.
- Market regime detector, belirtilen altı rejim için skor/olasılık, güven ve geçiş/kararsızlık sinyali üretir.
- Opportunity scoring; sinyal kalitesi, rejim uyumu, likidite, volatilite, beklenen fee/slippage, korelasyon ve risk limitlerini birleştirir.
- Confidence scoring; veri kalitesi, model belirsizliği, örnek yeterliliği ve rejim kararlılığını ayrı gösterir.
- BTC etkisi ve piyasa korelasyonları, risk ve skorlama girdisi olarak izlenir; nedensellik iddiası olarak sunulmaz.

### Strategy, Portfolio ve Trade Simulation

- Strateji havuzu; Trend Following, Momentum, Breakout, Mean Reversion, Volume Spike, Order Book Imbalance, Volatility Based ve AI/Adaptive stratejileri eklemeye uygun plug-in sınırına sahip olur.
- MVP’de yalnızca seçilmiş, açıklanabilir stratejiler uygulanır; diğerleri kayıtlı adaydır.
- Portfolio Manager, yalnızca paper/simülasyon pozisyonlarını, nakit, maruziyet ve portföy kısıtlarını yönetir.
- Trade Engine ilk aşamada emir iletmez; paper fill, fee, slippage, latency ve kısmi dolum varsayımlarını kaydeder.

### Validation, Learning ve Model Governance

- Backtest motoru zaman sıralı veride fee, slippage, gecikme ve veri boşluğu varsayımlarını açıkça uygular.
- Her aday; training → backtest → out-of-sample → walk-forward → paper trading → evaluation sırasını tamamlamadan champion olamaz.
- Model registry; veri aralığı, özellik/strateji sürümü, parametreler, metrikler, onaylayan kişi/süreç ve durum bilgisini tutar.
- Champion/Challenger; challenger’ı izole değerlendirir, champion değişimini yalnızca önceden tanımlı eşik ve onay kapısıyla yapar.
- Performans bozulmasında otomatik rollback önceki champion’a veya güvenli “trading disabled / observe only” durumuna geçer.

## 8. Risk Requirements

Risk Engine, bir fırsat ya da simüle emir uygulanmadan önce zorunlu kontrol noktasıdır. En az şunları destekler: position sizing, stop loss, take profit, maksimum pozisyon boyutu, günlük kayıp limiti, maksimum drawdown, ardışık kayıp limiti, maksimum açık pozisyon, parite/portföy maruziyet limiti, korelasyon yoğunlaşması, slippage kontrolü, fee accounting, emergency stop, kill switch, API/adapter arızası ve market-data arızası davranışları.

Limit ihlali veya veri sağlığı belirsizliğinde varsayılan davranış güvenli taraftır: yeni paper pozisyonu açılmaz, mevcut simülasyonun durumu işaretlenir, olay loglanır ve kullanıcıya uyarı verilir. Risk kuralları deney sonucu tarafından sessizce gevşetilemez.

## 9. AI ve Controlled Adaptive Learning Requirements

AI; sinyal/özellik analizi, rejim tahmini, fırsat skoru ve model değerlendirmesinde yardımcı olur; risk kurallarının yerini almaz. Her model çıktısı sürüm, veri kesiti, özellik seti, eğitim/validasyon ayrımı ve güven bilgisiyle izlenebilir olmalıdır.

Kontrollü yaşam döngüsü: **Live/Replay Data → Feature Engineering → Training → Backtest → Out-of-Sample Test → Walk-Forward Validation → Paper Trading → Evaluation → Challenger → Champion → izinli Live aşaması**. İlk ürün kapsamındaki son eylem paper trading veya shadow observation’dır; “Live” burada yalnızca gelecekteki, ayrı yetkilendirme gerektiren hedef durumdur.

Overfitting önlemleri; zaman-temelli veri ayrımı, sızıntı kontrolleri, walk-forward pencereleri, maliyet sonrası metrikler, yeterli örneklem eşiği, rejim bazlı kırılımlar, challenger izolasyonu ve anlamlı performans bozulmasında rollback içerir.

## 10. Data, Performance ve Non-functional Requirements

- Gerçek zamanlı veri mimarisi düşük gecikmeyi hedefler; kesin gecikme SLA’ları seçilecek borsa, veri sağlayıcı, altyapı ve parite kapsamından sonra belirlenir.
- Çoklu parite taraması yatay ölçeklenebilir, geri basınç/backpressure farkındalığı olan ve veri kaybını görünür kılan tasarımla çalışmalıdır.
- Tarihsel veri, ham olay, türetilmiş özellik, sinyal, karar, fill simülasyonu ve model sonucu arasında izlenebilirlik kurulmalıdır.
- Gözlemlenebilirlik; yapılandırılmış log, metrik, alarm, veri gecikmesi, adapter sağlığı, model drift ve risk ihlali olaylarını kapsar.
- Ana performans metrikleri: total return, win rate, average win/loss, profit factor, maximum drawdown, Sharpe, Sortino, trade sayısı, fees, slippage, latency, strateji/model/rejim performansı.
- Sonuçlar mutlak getiri yanında maliyet, risk, örneklem büyüklüğü ve rejim dağılımı ile raporlanır.

## 11. Security ve Safety Requirements

- API key hiçbir kaynak koda, brief’e, log’a veya test verisine yazılmaz; ileride secrets/environment management kullanılır.
- İlk aşamada gerçek API key yoktur; trading permission varsayılan olarak kapalıdır.
- Gelecekte minimum API izni, anahtar rotasyonu, erişim denetimi, denetim izi ve güvenli hata maskelemesi zorunlu tasarım kararlarıdır.
- Paper trading ile gerçek işlem yolu mantıksal ve operasyonel olarak ayrılır; gerçek işlem yolu gelecekte ayrıca tehdit modellemesi, onay ve kill-switch testi gerektirir.
- Sistem, yatırım tavsiyesi veya getiri garantisi sunmaz; skorlar karar desteğidir.

## 12. Future Extensibility ve Teknoloji Yaklaşımı

Exchange adapter, strateji, özellik, model, değerlendirme ve emir/portföy sınırları bağımsız evrimleşebilmelidir. Bu, ileride Binance, Bybit, Coinbase ve diğer spot sağlayıcılarının eklenmesine; ayrıca yeni strateji ve model ailelerinin kayda alınmasına imkân verir.

Teknoloji seçimi bu brief’te kilitlenmez. Python; veri bilimi, ML, eğitim ve backtesting için güçlü adaydır. Node.js; WebSocket orkestrasyonu, API, dashboard backend’i ve servis koordinasyonu için güçlü adaydır. Tek dil veya hibrit yaklaşım; ekip becerisi, gecikme hedefi, operasyonel karmaşıklık, gözlemlenebilirlik ve veri hattı sınırları değerlendirildikten sonra mimari aşamada seçilecektir.

## 13. MVP Scope

MVP, güvenli araştırma ve karar desteği dikey dilimidir:

- Tek veya sınırlı sayıda adapter sözleşmesi ile replay/historical market data akışı; gerçek API anahtarı veya emir yok.
- Sınırlı parite evreni ve veri kalite/sağlık göstergeleri.
- OHLCV, hacim, temel volatilite ve seçilmiş teknik göstergeler.
- İlk rejim sınıflandırma yaklaşımı ve en az iki açıklanabilir strateji adayı.
- Fee/slippage varsayımlarını içeren backtest, out-of-sample ve başlangıç walk-forward raporu.
- Paper portfolio, risk limitleri, kill switch ve fırsat/risk görünümü.
- Basit model/strateji kayıtları, challenger değerlendirme kaydı ve rollback kararı için tasarım.
- İlk dashboard veya API görünümü: sistem durumu, rejim, fırsat skoru, paper P&L, drawdown, risk/sağlık uyarıları.

## 14. MVP Dışı Kapsam

- Gerçek spot emir iletimi ve canlı sermaye.
- Futures, kaldıraç, short veya türev ürünler.
- Tüm strateji havuzunun üretim uygulaması.
- Çoklu borsa arasında aynı anda canlı yürütme.
- Tam otomatik champion terfisi ve insan onayı olmadan model değişimi.
- Mobil uygulama, sosyal işlem, yatırım tavsiyesi, sinyal satışı veya getiri vaadi.

## 15. Success Criteria

- MVP, belirlenen veri akışında zaman sıralı ve denetlenebilir analiz/paper-trading döngüsünü uçtan uca tamamlar.
- Her raporlanan fırsat; kaynak veri durumu, rejim, skor gerekçesi, güven ve risk değerlendirmesi ile izlenebilir.
- Backtest ve paper sonuçları fee/slippage dahil edilir; train/test sızıntısı ve look-ahead bias için kontroller belgelenir.
- En az bir challenger değerlendirmesi, bir champion kararı veya “terfi yok” kararı ve bir rollback/kill-switch tatbikatı denetlenebilir kayda sahiptir.
- Risk limiti ya da veri sağlığı ihlalinde sistem yeni simüle pozisyon açmayı güvenli biçimde engeller.
- Başarı, garanti edilmiş getiriyle değil; ölçüm bütünlüğü, karar izlenebilirliği, güvenlik sınırları ve doğrulama disiplininin sağlanmasıyla değerlendirilir.

## 16. Key Risks

- **Veri kalitesi ve gecikme:** Eksik/sırasız order-book veya trade verisi yanlış sinyal üretebilir. Mitigasyon: kalite bayrakları, adapter health, replay ve fail-closed davranış.
- **Overfitting/model drift:** Tarihsel başarı geleceğe taşınmayabilir. Mitigasyon: out-of-sample, walk-forward, rejim bazlı ölçüm, challenger ve rollback.
- **Maliyet yanılsaması:** Fee, slippage ve latency ihmal edilirse kârlılık sahte görünür. Mitigasyon: maliyet modelini tüm değerlendirmelerde zorunlu kılmak.
- **Operasyonel karmaşıklık:** Çoklu dil/servis/adapter bakım maliyetini artırabilir. Mitigasyon: mimari karar kaydı, dar MVP ve açık sınırlar.
- **Güvenlik ve yetki genişlemesi:** Gerçek işlem eklenirse anahtar ve erişim riskleri artar. Mitigasyon: ilk aşamada anahtarsız çalışma, varsayılan kapalı trading, ayrı yetkilendirme kapıları.
- **Pazar/veri sağlayıcı bağımlılığı ve uyum:** Borsa erişimi, stream limitleri, kullanıcı coğrafyası ve yatırım tavsiyesi algısı ürün sınırlarını etkileyebilir. Mitigasyon: non-custodial ve simülasyon-only sınırını teknik olarak korumak; sağlayıcı koşullarını sürümlü bağımlılık kabul etmek; müşteri odaklı kullanımdan veya emir bağlantısından önce yetkin hukuk/uyum incelemesi yapmak.
- **Yanlış kullanıcı beklentisi:** AI skorları kesin tahmin sanılabilir. Mitigasyon: açıklanabilirlik, belirsizlik göstergeleri ve getiri garantisi vermeme.

## 17. Open Questions / Decisions Needed

1. İlk MVP’de hedef kullanıcı yalnızca proje sahibi mi, yoksa çok kullanıcılı bir araştırma ürünü mü?
2. İlk veri kaynağı/replay dataset’i nedir; hangi pariteler, zaman çözünürlükleri ve order-book derinliği gereklidir?
3. “Düşük gecikme” için kabul edilen ölçülebilir gecikme, kullanılabilirlik ve veri kaybı hedefleri nelerdir?
4. İlk MVP’de uygulanacak iki strateji hangileridir ve her biri için başarı/başarısızlık eşiği nedir?
5. Rejim sınıflandırması başlangıçta kural tabanlı, istatistiksel veya ML tabanlı mı olacak; karar açıklaması nasıl sunulacak?
6. Opportunity ve confidence skorlarının insan tarafından anlaşılır ağırlıkları/kalibrasyonu nasıl belirlenecek?
7. Paper-trading fill, fee, slippage ve latency modeli hangi borsa/market varsayımlarına dayanacak?
8. Champion terfisi için minimum örneklem, risk-ayarlı metrik, rejim kapsamı ve insan onay gereksinimi nedir?
9. Rollback tetikleyicileri ile emergency stop/killswitch yetkisine kim sahip olacak?
10. Veri saklama süresi, kişisel veri kapsamı, hedef coğrafya ve uyum/hukuk gereksinimleri nedir?
11. Python, Node.js veya hibrit mimari için ekip yetkinliği, dağıtım ortamı ve operasyon bütçesi nedir?
12. Gerçek spot trading’e geçiş için ayrı güvenlik incelemesi, yasal değerlendirme ve kullanıcı onay kapıları nasıl tanımlanacak?
13. Hedef kullanıcı coğrafyası ve ürünün araştırma aracı/son kullanıcı ürünü sınırı nedir; fırsat skorları için gerekli risk bildirimi, kayıt tutma ve hukuk/uyum incelemesi nasıl yürütülecek?

## 18. Handoff to the PRD

PRD; MVP kullanıcı akışlarını, kapsam dışı sınırlarını, veri şemalarını, kabul kriterlerini, ilk strateji seçimini, rejim/score açıklanabilirlik gereksinimlerini, risk limitlerinin varsayılan değerlerini, paper-trading senaryolarını, dashboard önceliklerini ve hata/uyarı davranışlarını kesinleştirmelidir. Mimari aşaması; adapter sözleşmesi, veri hattı, depolama, servis sınırları, teknoloji seçimi, gözlemlenebilirlik ve güvenlik tehdit modelini karar kayıtlarıyla netleştirmelidir.
