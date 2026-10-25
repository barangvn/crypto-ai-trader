# Reuse Map — S-FND-03 (Neler Yeniden Kullanılır, Nelere Yeniden Kullanılır)

## 1. Gelen (Upstream Reuse — ALINAN)
S-FND-03, upstream completed hikâyelerden aşağıdaki öğeleri tekrar kullanabilir:
| Ürün | Upstream Story | Kullanım Şekli | SESSİZ DEĞİŞTİRME YOK — KURAL |
|---|---|---|---|
| `MarkerCatalog` / Pytest plugin mekanizması — Python stdlib ConfigParser, ast, re, hashlib, subprocess. | Python stdlib (HR-5) | 12 stdlib + pytest mevcut. | HR-5 stdlib-only; yeni bağımlılık 0. |
| Optional: AC-21 correlation label helper. | S-FND-02 (`app/platform/observability/correlation.py`, `factory.set_correlation_provider`). | Eğer import edilebilirse pattern scan findinge correlation_id ekler; yoksa no-op, import error catch. | Non-goals P-08: NO MODIFY upstream S-FND-02 code; sadece okunur import (failure-safe). |
| Completed story pytest fixtures (ör. tests/conftest.py offline_network_blocker session autouse). | S-FND-01. | S-FND-03 testleri S-FND-01 blocking faydalanır (tests are under tests/; root conftest otomatik çalışır), ama ROOT CONF TEST FİKSTÜRÜNÜ DEĞİŞTİRMEZ. | K0 HR-1 0 existing modify. AUTOUSE otomatik, fixture append YOK. |

## 2. Giden (Downstream Reuse — VERİLEN)
S-FND-03 aşağıdaki downstream hikâyelere tekrar kullanılır marker + scan sunar:
| Tüketici Story | Neyi tekrar kullanır? | Tür |
|---|---|---|
| **S-CON-01** Canonical Envelope + Quality Flags Schemas | `@pytest.mark.contract` decorator; her unit test için etiketleme, PR CI select. | Marker. |
| **S-CON-02** 19 Market/Decision/Portfolio entity schemas | Aynı + failure_injection marker (negatif schema validation testleri için). | Marker + pr-gate scan output JSON rapor consumption isteğe bağlı. |
| **S-FEA-01** Deterministic Feature Engine | `replay` marker (replay bundle input testleri), `failure_injection` (quality_flags bozuk path). | Marker. |
| **S-REG-01** Market Regime Detection | `replay` marker — rejimler replay bazında deterministik. | Marker. |
| **S-STR-01** Trend/Momentum Strategy | Aynı replay marker; contract marker strategy sözleşmeleri için. | Marker. |
| **S-RSK-01** Independent Risk Engine | `failure_injection` — Risk timeouts, stale data injection. | Marker + F3' prime leverage/short scan output consumption. |
| **S-RSK-02** Risk Decision Paper Order Gate Enforcement | `contract` marker — gate sözleşmesi testleri için. | Marker. |
| **S-PTR-01** Paper Fill Engine + S-PTF portfolio 01-03 | `contract` + `replay` marker. | Marker. |
| **BKT 01-03 Backtest Engines** | `replay` marker — backtest 100% replay bağımlı. | Marker. |
| **S-RDH-01/02** Replay Data Pipeline | `failure_injection` marker — corrupt bundle testleri. | Marker. |
| **Registry / Eval / Gate / Rollback / CAP5** (stories completed) | Mevcut testleri — contract marker isteğe bağlı eklenebilir; SFND03 mevcut testleri DEĞİŞTİRMEZ, marker sadece yeni hikâyelerce append edilir. | Bilgi (optional, K0 korunur) |
