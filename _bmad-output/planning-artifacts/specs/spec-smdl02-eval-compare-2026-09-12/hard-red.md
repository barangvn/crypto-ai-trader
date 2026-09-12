# S-MDL-02 Hard-Red Immutable Files (0 byte diff zorunlu)

HİÇBİRİ DEĞİŞTİRİLEMEZ — değişiklik audit anında REJECT:

```
app/contracts/                                  ← tüm 19 contract + enums (S-CON-02C 1.0.0 preserved)
app/replay/                                     ← S-RDH-0x replay pipeline
app/platform/event_bus.py                       ← S-PLN-01 typed bus
app/features/                                   ← E-FEA feature engineering
app/regime/                                     ← E-REG regime detector
app/strategies/                                 ← E-STR strategy plugins
app/opportunity/                                ← E-AIS scoring
app/risk/                                       ← E-RSK risk engine (single writer)
app/simulation/                                 ← Portfolio sim single writer
app/backtest/ordering.py                        ← SBKT ordering
app/backtest/pipeline.py                        ← SBKT pipeline stages
app/backtest/runner.py                          ← SBKT runner
app/backtest/multi_fold_runner.py               ← SBKT MF runner
app/backtest/leakage_asserts.py                 ← SBKT03 leakage
app/backtest/metrics_compute.py                 ← SBKT03 metrics
app/registry/                                   ← S-MDL-01 tek DO NOT write (read-only)
tests/backtest/test_sbkt01_*.py                 ← 222 PASS preserved
tests/backtest/test_sbkt02_*.py                 ← SBKT02 regression unchanged
tests/backtest/test_sbkt03_*.py                 ← 332 PASS preserved
tests/registry/                                 ← 162 PASS preserved
pyproject.toml                                  ← dependencies=[]
```

Doğrulama komutu (audit):
```
git diff --name-only 7604262 <listed paths above>
→ EMR boş (0 satır) olmalı → 0 byte diff.
```
