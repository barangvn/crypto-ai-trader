# Test Plan — S-FND-05

## TP-01: Import ve Public API Surface (AC-01 / AC-02)

- 2 Test: (T01) CanonicalEnvelope import, (T02) 12 yardımcı tip import
- Type check: her import dataclass / frozen / NewType / Enum gibi davranır

## TP-02: Contract Version Alignment (AC-03 / AC-04)

- T03: `envelope_instance.contract_version == "1.0.0"`
- T04: `from app.platform.config import VersionConstants; VersionConstants.contract_version == envelope.contract_version` TRUE.

## TP-03: Zorunlu Eksik Alan Fail-Closed (AC-05 / AC-06)

- T05: eksik event_id → TypeError/ValueError
- T06: eksik correlation_id → TypeError/ValueError
- Ek: kalan 12 zorunlu alanı da parametrize test (coverage maksimizasyonu)

## TP-04: Instant UTC-Z Regex (AC-07 / AC-08 / AC-09)

- T07: offset `+03:00` → ValueError
- T08: Z eksik → ValueError
- T09: `"2026-08-10T18:30:00Z"` (ms YOK) → PASS (3 haneli ms opsiyonel)

## TP-05: Enum Set Membership (AC-10 / AC-11)

- T10: RunModeE wrong → ValueError
- T11: SourceTypeE wrong → ValueError
- Pozitif: Her enum için tüm 3/6 değerleri constructor test

## TP-06: QualityFlags Invariantları (AC-12 / AC-13 / AC-14)

- T12: degraded=True, diğer 6 FALSE → ValueError FC-06
- T13: stale=True, degraded=False → AUTO degraded=True post init
- T14: quarantined=True, diğerleri False (SİLENT ADN-05-05 SOFT) → PASS NO EXCEPTION

## TP-07: Clock Parity / Source Parity Invariants (AC-15 / AC-16)

- T15: replay, None replay_clock → ValueError FC-04
- T16: replay, timestamp == ingest_ts → ValueError FC-05

## TP-08: Symbol Canonical Regex (AC-17)

- T17: lowercase "btcusdt" → ValueError FC-08. Pozitif: `"BTC_USDT"`, `"SOL_USDC"` 2 PASS.

## TP-09: Determinism 10x (AC-18)

- T18: Aynı constructor args, 10x → `len(set(10 sha digest)) == 1`
- Determinizm kapsamı: 6 boyut (D-1 envelope tuple, D-2 ULID idempotent, D-3 degraded auto, D-4 regex, D-5 enum membership, D-6 alignment). Her bir determinism fixture ile 10x.

## TP-10: Forbidden Scan (DoD-06 / HRC)

- contract markerlı test: F1 network (FND-03), F2 cred, F3 short/lev, F4 send_real_order, F5 yaml (PyYAML story scope), HRC-S5 scope drift.

## Test Distribution Summary

| TP | AC Aralığı | Test Sayısı |
|---|---|---|
| 01 | 01-02 | 2 |
| 02 | 03-04 | 2 |
| 03 | 05-06 | 2 (+ 12 bonus parametrize) |
| 04 | 07-09 | 3 |
| 05 | 10-11 | 2 |
| 06 | 12-14 | 3 |
| 07 | 15-16 | 2 |
| 08 | 17 | 1 (+ 2 pozitif) |
| 09 | 18 | 1 × 10x |
| 10 | HRC | 1 |

**Toplam: ~18 AC testleri (doğrudan AC sayısı 18). Coverage her ZORUNLU alan + her invariant.**
