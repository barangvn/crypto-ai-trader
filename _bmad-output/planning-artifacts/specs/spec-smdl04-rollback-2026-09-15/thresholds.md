# S-MDL-04 Thresholds Reference (Rollback Degradation — 8 ADN defaults reference table, OD-01..OD-08 companion)

NOT: **TÜM SAYISAL DEĞERLER ADN (Açık Karar)**. PRD §9 OQ10 "degradation thresholds govern rollback" explicitly açık decision; hiçbir değere source-ta sayı atanmamış. Aşağıdakiler **test fixture defaults** (overrideable); governance tarafından son değer atanmadan production KESİNLİKLE kullanılmamalıdır.

## 1. trigger_enum (NOT numeric — zorunlu 3 değer)
kaynak: [FR-040 prd.md:L123](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L123) + LIFECYCLE T4 + ADN-09 kill

| value | Açıklama | Kaynak |
|---|---|---|
| degradation_breach | Tanımlı ADN sayısal eşikler ihlal edildi (metric delta kötüleşme) | FR-040 |
| manual_governance | Operatör / insan onayı ile manuel rollback talebi | FR-041 approver/rationale |
| kill_switch_emergency | Emergency stop / kill switch tetik (FR-054, ADN-09) | FR-054 prd:L146, ADN-09 EPICS:L504 |

## 2. Degradation Window (staleness) — OD-02

| Threshold Key | ADN Default (test) | Birim | Açıklama | Open Decision |
|---|---|---|---|---|
| max_degradation_window_days | 30 | gün | Değerlendirme yaşı > 30 → STALE_DEGRADATION_WINDOW | OD-02 |

## 3. Evidence Minimums — OD-04

| Threshold Key | ADN Default | Tip | Açıklama | Open Decision |
|---|---|---|---|---|
| min_degradation_evidence_count | 2 | int | ≥2 independent degradation breach required; below → DEGRADATION_EVIDENCE_COUNT_BELOW_MIN | OD-04 |
| delta_metrics_required_keys | exact set 11 (FR-038) | str set | return_pct, max_drawdown_pct, sharpe_ratio, sortino_ratio, profit_factor, total_fees_quote, avg_slippage_bps, trade_count, regime_coverage_count, window_days, oos_flag | G3 EV1 zorunlu — kaynak FR-038 sayısız set eşleşmesi ADN değil |

## 4. Approval Semantics — OD-03

| Threshold Key | ADN Default | Açıklama | Open Decision |
|---|---|---|---|
| min_rollback_approval_count | 1 | len(approval_refs) + explicit_approval_count ≥ 1; ADN-08 kalıtım | OD-03 |

## 5. Eligibility Target Status Set — OD-05

| eligible_status_set default | ModelLifecycleStatus.value listesi | Open Decision |
|---|---|---|
| default | ["retired", "paper", "challenger"] | OD-05 | NOT: candidate, tested (promotion aşaması tamamlanmamış) |

## 6. Target Mode Default — OD-06

| default_target_mode | Açıklama (her ikisi de eligibility aynı) | Open Decision |
|---|---|---|
| restore_prior_champion | Önceki champion'ı geri yükle; observe_only operator override | OD-06 |

## 7. rollback_strategy_ref Artifact Schema — OD-07

| Pattern ADN Default | Lokasyon | Open Decision |
|---|---|---|
| `.registry-artifacts/rollback-strategies/{ref}.json` | Local filesystem ADN-10 kalıtım | OD-07 |

## 8. Predecessor Pointer Cardinality — OD-08

| Cardinality Default | Max Derinlik | Open Decision |
|---|---|---|
| 1:1 tekil | depth=1 (sadece immediate predecessor) | OD-08 multi-chain OOS |

## 9. Version Mismatch (non-ADN — source)

| Key | Value | Kaynak |
|---|---|---|
| thresholds_config_version_required | "1.0.0" initial (S-MDL-03 kalıp) | THRESHOLDS_VERSION_MISMATCH reason code pattern (S-MDL-03 CAP-12 L52 aynen) |

## 10. Per-Metric Degradation Thresholds Numeric (BÜTÜN OD-01 ADN — sayısal değerler KAYNAKTA YOK)

OD-01 = Açık. Aşağıdakiler ADN fixture nominal (karşılaştırma için sadece test); hiçbir şekilde bağlayıcı DEĞİLDİR.

| Metric Key | Direction (Higher/Lower Better) | ADN test fixture "degraded" threshold (NOT binding) |
|---|---|---|
| return_pct | HigherBetter | champion - baseline > -0.05 (%5 negative? ADN — NO SAYI source) |
| max_drawdown_pct | LowerBetter | champion > baseline + 0.10 (DD artışı) |
| sharpe_ratio | HigherBetter | champion < baseline - 0.30 |
| sortino_ratio | HigherBetter | champion < baseline - 0.20 |
| profit_factor | HigherBetter | champion < baseline - 0.20 |
| total_fees_quote | LowerBetter | champion > baseline + 10% |
| avg_slippage_bps | LowerBetter | champion > baseline + 5 bps |
| trade_count | HigherBetter (minimum sample) | champion < baseline - 20% or |
| regime_coverage_count | HigherBetter | champion < baseline - 3 regime |
| window_days | invariant match | should be equal within ±1 (not degraded) |
| oos_flag | invariant bool | True required |

**Önemli:** Yukarıdaki 11 satır sayısal değerlerin HEPSİ source-ta YOK; sadece test fixtures ADN override olarak işaretlenecek. Production öncesi governance onayı ile gerçek değerler yazılacaktır. Open-Decisions OD-01 altında kayıtlıdır.
