# v0.8 parity investigations

These issues track unresolved differences after the current example-level parity
pass. They are investigation-first: no pyglotaran core change should be made
until the reproduction and focused test establish that the behavior is a package
defect.

Current evidence:

- Result comparison: validation/comparisons/v07-v08-semantic.json
- Scenario contract: validation/scenarios.yml
- Remediation history: validation/logs/validation-log.md
- Pinned environments: temp/pyglotaran-main-dev and temp/pyglotaran-staging-dev

| Issue | Question | Current disposition |
|---|---|---|
| weighted-scale-drift.md | Is the 3D weighted scale/fitted-data drift caused by input translation, weighting, convergence, or a v0.8 defect? | Open; highest-priority numerical investigation |
| rates-k3d2-identifiability.md | Is the historical rates.k3d2 discrepancy caused by the example model or by v0.8 optimization/serialization? | Resolved for the maintained example by replacing the superseded model; no core fix or value normalization |
| weighted-rmse-persistence.md | Should v0.8 persist weighted RMSE and default scale metadata, or is external derivation sufficient? | Open; likely schema/reporting issue |
| kinetic-activation-normalization.md | Why do migrated coherent-artifact/DOAS datasets drift the dataset scales by an integer factor? | Root cause confirmed and fixed in the converter; re-migrated and re-run at `20260830-143435`. Core-side discrimination left to maintainers; the `77K_target_cells` single-evaluation difference is unexplained and open |
| inactive-free-parameter-count.md | Why does the first `77K_target_MCL` fit report 28 free parameters on v0.7 and 26 on v0.8? | Explained; v0.7 includes two unused varying scales, while v0.8 optimizes only parameters referenced by the active experiment |
| pfid-runtime-memory-profile.md | Why does the migrated PFID notebook take longer and use more memory in v0.8 staging? | Runtime cause localized to explicit dry runs and multi-objective result reconstruction; peak RSS difference measured, exact allocation site remains open |
