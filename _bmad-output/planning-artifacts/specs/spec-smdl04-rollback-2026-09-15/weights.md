# S-MDL-04 Weights Reference — EXPLICIT NOT APPLICABLE / N/A (ROLLBACK KAPSAM DIŞI; weighted score S-MDL-03 SAHİBİ)

## Açıklama (boundary to S-MDL-03)

**S-MDL-04 rollback eligibility decision: HİÇBİR weighted composite total score (Σ w_i × norm(metric_i)) KULLANMAZ.**

Sınır:
- S-MDL-03 SPEC NG2 (L58-60): rollback/pred restore explicitly → S-MDL-04 sorumluluğunda.
- Ters: **S-MDL-04 SPEC HRC20 (hard-red L20 scope)** → AST pattern `weighted_total` / `Σw×norm` compute under app/rollback/*.py SAYISI = 0. Kesinlikle YASAK.

Neden weights.md var ise?
- Klasörde weights.md template S-MDL-03 kalıbı match (10 md + SPEC.md = structure symmetry).
- Açık border marker — downstream reader "S-MDL-04'te weighted score var mı?" diye sorduğunda N/A cevabı açık.
- Non-Goals NG3 zaten Promotion gate/weighted score YOK yazıyor. weights.md YİNELE (double confirm) border.

## Sınır Özeti Tekrar

| Feature | S-MDL-03 | S-MDL-04 |
|---|---|---|
| Weighted composite total score Σw×norm | KULLANIR (CAP-1, 27 matrix, S1 success) | YOK (HRC20 0 literal/call) |
| Weights definition validation (11 required keys) | KULLANIR (CAP-9, G1 weights) | YOK — sadece READ CCE.rollback_strategy_ref pointer |
| Soft thresholds per metric 11 key | KULLANIR (CAP-2 11 threshold 22 scenario) | KULLANMAZ — degradation ADN threshold open decisions OD-01, source-ta YOK |
| Promotion gate.pass / winner invariant | KULLANIR (CAP-5, winner↔gate BOTH way) | YOK — sadece CCE.promotion_gate_result.pass True flag READ T4 precondition check |
| Rollback eligible / target selection / evidence min / approval min READONLY | NG2 ❌ YOK | CAP-1..CAP-13 bu hikâyenin konusu |

## Gelecekte weighted rollback-risk score ihtiyacı?

Eğer governance gelecekte "rollback risk composite score" isterse → ayrı yeni story (S-MDL-06 ADN). S-MDL-04 şu an weighted score KAPSAM DIŞI = N/A.

Ağırlık dosyası: **N/A** / boş.
