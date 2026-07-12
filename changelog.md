# Validation changelog

## 2026-07-12

- Added validation-side fit-runtime benchmarking for 15 optimizer invocations, with isolated warm-ups, five timed repetitions, workload metadata, and mean ± sample-standard-deviation plots.
- Normalized staging fit budgets to the pinned v0.7.4 observed workloads: 21 evaluations for spectral guidance and 17 for the two-dataset example; reran the full benchmark with no workload warnings.
- Added a manifest-driven 14-leaf scenario contract and external v0.7-compatible result comparison layer.
- Fixed staging result coverage: DOAS saving and all four spectral-constraint leaves.
- Corrected the staging target optimizer budget from 11 to 10 evaluations; verified target fitted-data normalized RMS 4.90e-8.
- Added focused compatibility and translation regression tests (4 passed).
- Clean matrix result: 11/11 notebooks per branch; 8 PASS and 6 documented EXPECTED_DIFFERENCE leaves, with no regressions or missing artifacts.
- Recorded source, lockfile, notebook, and result hashes in validation/comparisons/v07-v08-semantic.json.
- Added issues/ with investigation briefs for weighted scale drift, rates.k3d2 identifiability, and weighted-RMSE persistence.
