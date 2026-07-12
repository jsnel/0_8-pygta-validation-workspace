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
| rates-k3d2-identifiability.md | Is the enormous rates.k3d2 value genuinely unidentifiable or a v0.8 optimization/serialization defect? | Open; do not normalize or overwrite the value |
| weighted-rmse-persistence.md | Should v0.8 persist weighted RMSE and default scale metadata, or is external derivation sufficient? | Open; likely schema/reporting issue |
