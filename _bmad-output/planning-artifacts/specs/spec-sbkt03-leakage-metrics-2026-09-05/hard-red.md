# hard-red.md — S-BKT-03
HIÇBIR KOŞULDA DEGISMEZ. 1 bytes change → audit REJECT.

## Domain / Contract Katmanı (6 modül)
| Klasör / Dosya (patterns) | Neden hard-red |
|---------------------------|----------------|
| `app/contracts/*.py` | S-CON-02A/B/C 19 entity schema immutable; contract_version 1.0.0 sabit. Position / PortfolioSnapshot field isimleri YENİ METRICS İÇİN DEĞİŞMEZ — runner/extension module extend. |
| `app/features/*.py` | S-FEA-01 feature engine immutable; leakage assertion feature INPUT stage çağrısı wrapper external (engine touch yok). |
| `app/regime/*.py` | S-REG-01 6 regime detector immutable; regime decomposition READ FROM existing correlation fields. |
| `app/strategies/*.py` | S-STR-01 Trend/Momentum strategy immutable; strategy_id READ ONLY for decomposition. |
| `app/opportunity/*.py` | S-OPP-01 scoring immutable; leakage assert wrapper external (not inside scoring engine). |
| `app/risk/*.py` | S-RSK-01 risk engine + AD-11 gate immutable; RiskDecision approved YALNIZ upstream OK path preserved. |

## S-PTR / S-PTR-02 Execution & Portfolio (3 dosya — AD-7/13/24 single writer protection)
| Dosya | Neden |
|-------|-------|
| `app/simulation/fill_config.py` | S-PTR-02 default spread/slip/latency config immutable. |
| `app/simulation/paper_fill.py` | S-PTR-01 fill simulation state machine — NO rewrite; leakage assertion wrap PO sonrası. |
| `app/simulation/portfolio.py` | S-PTF-01 Position Engine + S-PTF-02 PortfolioSnapshot Engine + S-PTF-03 Rolling 24h — YAZAR TEK module, S-BKT-03 OKUR, MODIFY EDEMEZ. |

## Platform & Backtest Core (AD-24 orchestration invariant)
| Dosya | Neden |
|-------|-------|
| `app/platform/event_bus.py` | S-PLN-01 typed bus immutable; corr/caus chain preserved. |
| `app/backtest/ordering.py` | ReplayClock + `assert_no_look_ahead` MEVCUT implementation immutable. S-BKT-03 bunu IMPORT EDER ve 6 stage ZORUNLU çağırır; fonksiyon body touch YOK. Leakage assertion layer EXTEND değil CALL pattern. |
| `app/backtest/pipeline.py` | 9-stage pipeline order immutable. CAP-4 gate→PO order. Stage sonu callback noktaları haricinde body change YOK. |

## Test Regression Koruması
| Dosyalar | Neden |
|----------|-------|
| `tests/backtest/test_sbkt01_*.py` (10 dosya) | 222/222 backward, NO touch. |
| `tests/backtest/test_sbkt02_*.py` (19 dosya) | 619 collected backward; S-BKT-03 bu dosyalara import/assertion change YAPMAZ, kendi NEW test file yaratır. |

## Build/Dependency
| Dosya | Neden |
|-------|-------|
| `pyproject.toml` (özellikle `dependencies=[]` satırı) | Zero-dep stdlib-only hard boundary; S-BKT-03 statistics = stdlib, no new package. |

---
*Uygulama katmanı YENİ helper/extension noktaları (onaylı non-hard-red): `app/backtest/runner.py` → placeholder extend; `app/backtest/multi_fold_runner.py` aggregate extend; YENİ `app/backtest/leakage_asserts.py` (HER stage çağıran wrapper) + YENİ `app/backtest/metrics_compute.py` (S-PTF-01/02/03 read-only aggregates). Bunlar hard-red DEĞİLDİR.*
