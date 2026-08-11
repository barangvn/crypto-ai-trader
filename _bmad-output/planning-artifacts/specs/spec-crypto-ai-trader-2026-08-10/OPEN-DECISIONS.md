---
scope: Open Decisions (ADN) inherited from architecture and preserved
status: deferred
created: 2026-08-10
updated: 2026-08-10
---

# OPEN-DECISIONS — Architecture Decision Needed

Bu dosyadaki maddeler **SPEC tarafından çözülmez**. SPEC’in amacı bunları çözmek değil; downstream implementasyon/epikler sırasında HANGİ kararların verilmesi gerektiğini netleştirmektir. Her madde: karar sahibi (ADN-owner), karar neyi etkiliyor (impact_surface) ve önerilen çözüm yolu olarak 3 alanda listelenir.

## ADN-01 Exchange / Replay data provider (İlk)
- Ne: İlk exchange (Binance/Bybit/Coinbase/başka) ve/veya replay provider; sembol normalizasyonu, veri lisansı, halka açık endpoint’ler vs.
- Impact: Exchange Adapter implementation, symbol sözleşmesi, historical veri depolama.
- Çözüm önerisi: Provider seçimi ve ilk adapter port contract’ında kesinleşir.

## ADN-02 Başlangıç symbol universe / quote currency / timeframes / order-book depth / historical lookback
- Ne: Hangi semboller, hangi quote (USDT/USDC/BUSD vs), hangi TF seti (örn 1m,5m,15m,1h,4h,1d), kaç level order book, kaç senelik history, minimum veri kapsama oranı.
- Impact: Scanner, storage boyutu, backtest window, feature sözleşmesi, UI.
- Çözüm önerisi: İlk release öncesi backtest kapsamı ile kesinleştir.

## ADN-03 Latency / availability / recovery / kabul-edilebilir data-loss SLO’ları (sayısal)
- Ne: WebSocket reconnect SLA, veri tekrar oynatma, data loss oranı, backtest/validation latency.
- Impact: Monitoring, data quality toleransları, AD-5 eşikleri.
- Çözüm önerisi: MVP paper trading production SLO doc’u içinde yazılır.

## ADN-04 Trend Following & Momentum kesin kuralları / eligibility eşikleri
- Ne: Hangi indikatörler (örn MA/EMA kesişimleri, RSI, MACD, ADX), giriş/çıkış parametreleri, hangi rejimlerde aktif.
- Impact: Strategy plugins, backtest sonuçları, scoring, AD-9/AD-25 context.
- Çözüm önerisi: İlk strateji specii (veya epics) içinde keşif + parameter search sonuçlarına göre.

## ADN-05 İlk AI model family ve explainability kalibrasyon standardı
- Ne: Classification/regression model ailesi (örn GBDT/LR/RF/NN vb), feature importance standartları, SHAP/PDP vs ile açıklanabilirlik zorunluluğu.
- Impact: AI Engine, model evaluation sözleşmesi, registry metadata.
- Çözüm önerisi: Research POC sonuçları ve yorumlanabilirlik beklentisi.

## ADN-06 Opportunity score weights / confidence thresholds / net-of-cost edge eşiği / Risk defaults (sayısal)
- Ne: `OpportunityScore` bileşen ağırlıkları, `actionable=true` için min skor, `expected_edge_bps` eşikleri, Risk engine limit default’ları (ADN-03 dışındaki sayısallar).
- Impact: Scoring Engine, RiskDecision output.
- Çözüm önerisi: İlk backtest ve sensitivity analizinden sonra.

## ADN-07 Paper fill / fee / slippage / latency / partial-fill varsayımları ve curve’leri
- Ne: Hangi market verisine göre kalibre edilecek, fee schedule (maker/taker), latency dağılımı, partial fill olasılığı.
- Impact: Execution Simulator + PaperFill contract.
- Çözüm önerisi: İlk exchange seçimi (ADN-01) sonrası gerçek trade kayıtlarından kalibrasyon.

## ADN-08 Champion promotion eşikleri / değerlendirme penceresi / approver politikası
- Ne: Min örnek sayısı, paper günü, outperform büyüklüğü, insan onayı zorunlu mu, onay sayısı, rollback degrade eşiği.
- Impact: LIFECYCLE.md promotion gate + champion_challenger_evaluation.
- Çözüm önerisi: Paper track’deki ilk 4-8 hafta sonucu gözlem.

## ADN-09 Rollback / degradation eşikleri ve Emergency Stop / Kill Switch’in davranışı + sahibi
- Ne: Hangi durumda rollback (max_dd, consecutive_loss, exposure anormalliği vb.), kill switch’in tüm pozisyonları kapatıp kapatmayacağı, sahibi (insan/otomasyon).
- Impact: Risk Engine, system emergency stop endpoint.
- Çözüm önerisi: Operatör el kitabı + ayrı risk politikası.

## ADN-10 Object Storage Provider (artifact storage)
- Ne: Model artifact, evaluation artifact, backtest raporları için storage (local fs, MinIO, S3-uyumlu, provider).
- Impact: ModelVersion.artifact_uri, deployment.
- Çözüm önerisi: MVP öncesi infra seçimi.

## ADN-11 Gelecekte canlı (future live) spot için permission owner / hukuk/uyum sınırı / final onay makamı
- Ne: Trading gates’te Research→Backtest→Paper→Approval→Live (gerçek) kapısında son onayı kim verecek, hukuki sorumluluk sınırı, ülke/bölge kısıtları.
- Impact: Gelecekte execution boundary.
- Çözüm önerisi: Canlıya geçmeden önce yasal/güvenlik incelemesi + izin matrisi.

## ADN-12 Hedef coğrafya / müşteri yüzü product boundary / hukuk/uyum incelemesi scope’u
- Ne: Product’ın kullanıcı hedefi (bireysel / enstitü / sadece araştırma), sunulacağı bölgeler, KYC/AML ihtiyacı olup olmayacağı.
- Impact: Dashboard UI (diller, yetkilendirme), ödeme/hesap akışı (v1’da yavaş), paper vs live ayrımı.
- Çözüm önerisi: Product kararları; MVP v1 tamamen “paper only + kendi kendine kullanım”.

---

## Uygulanış

- Her ADN için bir karar verildiğinde, ilgili kaynak (brief/PRD/AD) güncellenir ve bu dosyadan çıkar; yeni karar için memlog + (gerekirse) spec güncellemesi (bmad-spec update) yapılır.
- Bir ADN’nin kararı, contract kırıcı bir etki yaratıyorsa **CONTRACTS.md / contract_version** yükseltilir.
