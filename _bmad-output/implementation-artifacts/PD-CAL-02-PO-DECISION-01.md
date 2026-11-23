# PD-CAL-02 — PO DECISION RECORD

**Record ID:** PD-CAL-02-PO-DECISION-01  
**Decision status:** APPROVED  
**Decision type:** Feature data-contract version retention

## 1. Decision

The PO approves Option A: retain the existing feature version `fea_01_v1`.

The normative unit of `mom_10_pct` under `fea_01_v1` is **decimal return**.

Example:
- `0.02` represents a 2% return.
- `-0.02` represents a -2% return.

## 2. PO confirmation

The PO confirms that:
- The project is used only by the PO.
- No other person uses this computer for the project.
- The project is not being developed on another computer.

## 3. Accepted residual risk

The PO accepts the residual risk that undiscovered external, backed-up, or otherwise unobserved legacy FeatureVector data may use the previous percentage-point scale.

This confirmation does not constitute proof that every external storage location is free of legacy data.

## 4. Constraints and implications

- Retain `fea_01_v1`; do not bump the feature version as part of PD-CAL-02.
- Do not implement automatic legacy-data migration or conversion.
- Interpret `mom_10_pct` as decimal return for this feature version.
- Any future change to this field's normative unit requires a separately authorized versioning and migration decision.
- This record documents the PO decision; it does not authorize additional code, test, schema, or documentation changes.

## 5. Record integrity

This is an independent, standalone, append-only PO decision record.

It does not replace, rewrite, or modify `OPEN-DECISIONS.md`, any `OD/CLAR` register, or any other existing governance record.

## 6. Authorization boundary

This authorization permits creation of this exact file only.

No other file may be created or modified under this authorization.

No staging, commit, push, stash, reset, checkout, clean, or other Git mutation is authorized.
