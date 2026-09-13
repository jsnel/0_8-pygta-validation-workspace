# v0.8 parity investigations

These issues track unresolved differences after the current example-level parity
pass. They are investigation-first: no pyglotaran core change should be made
until the reproduction and focused test establish that the behavior is a package
defect.

Current evidence:

- [Final main-versus-staging run](final-validation-run.md): all 23 notebooks per
  branch execute; common examples meet the contract, while 11/40 case-study
  fitted-data comparisons remain above `1e-6`.

- Relative-magnitude assessment (2026-09-13): against a 0.1% relative
  acceptance band, all 14 common example scenarios pass, worst fitted-data
  difference `2.4463e-5` = 0.0025%. Among the case studies, 8 of 49 non-zero
  fits exceed 0.1%; after the 2026-09-12 MCL refresh supersedes three of them,
  4 unique fits remain. Every one terminated on *maximum function evaluations*
  on at least one branch, so they are budget-truncated intermediates rather
  than converged solutions. See the final-run report for the table.

- Result comparison: validation/comparisons/v07-v08-semantic.json
- Scenario contract: validation/scenarios.yml
- Remediation history: validation/logs/validation-log.md
- Pinned environments: temp/pyglotaran-main-dev and temp/pyglotaran-staging-dev

| Issue | Question | Current disposition |
|---|---|---|
| weighted-scale-drift.md | Is the 3D weighted scale/fitted-data drift caused by input translation, weighting, convergence, or a v0.8 defect? | Resolved 2026-09-13: optimizer termination on a flat direction. Both branches take 86 evaluations, terminate on `ftol`, and agree on `chi_square` to 5.4e-16; `scale.3` differs by 0.0026% because dataset3 is weighted 0.0025. No core change |
| rates-k3d2-identifiability.md | Is the historical rates.k3d2 discrepancy caused by the example model or by v0.8 optimization/serialization? | Resolved for the maintained example by replacing the superseded model; no core fix or value normalization |
| weighted-rmse-persistence.md | Should v0.8 persist weighted RMSE and default scale metadata, or is external derivation sufficient? | Resolved 2026-09-13: confirmed unintentional omission, fixed in staging core. `exclude_defaults=True` dropped `scale == 1` and the unweighted weighted-RMSE; both are now always persisted, matching v0.7. Two scalars per leaf |
| kinetic-activation-normalization.md | Why do migrated coherent-artifact/DOAS datasets drift the dataset scales by an integer factor? | Root cause confirmed and fixed in the converter; re-migrated and re-run at `20260830-143435`. Core-side discrimination left to maintainers; the `77K_target_cells` single-evaluation difference is unexplained and open |
| inactive-free-parameter-count.md | Why does the first `77K_target_MCL` fit report 28 free parameters on v0.7 and 26 on v0.8? | Explained; v0.7 includes two unused varying scales, while v0.8 optimizes only parameters referenced by the active experiment |
| pfid-runtime-memory-profile.md | Why does the migrated PFID notebook take longer and use more memory in v0.8 staging? | Runtime superseded 2026-09-13: reprofiled after the `f601c1a4`/`5dd45d5f` optimizations, staging drops 180.05 s to 137.32 s and the ratio 2.57x to **1.93x**. Memory finding unchanged and still open: peak RSS gap stays +55%, allocation site unattributed |
| [staging-runtime-optimization-continuation.md](staging-runtime-optimization-continuation.md) | Can reconstruction overhead be reduced while preserving current staging results? | Label conversion gives exact native parity and reduces PFID real-call means by 42%/67%; fresh 14-leaf reference comparison passes. Inherited dependency-lock, Gaussian-shift and convergence limitations remain documented |
