# Validation changelog

## 2026-07-12

- Ported the five main-only changes to the v0.8 staging architecture as individual commits on `feature/port-main-features-to-staging`, with implementation, tests, and a changelog entry in every commit.
- Added native v0.8 PFID element support plus the matrix-ordering, ASCII NumPy-scalar, pandas 3, SVD dimension-order, and deterministic simulation-noise fixes.
- Verified the staging suite (`448 passed, 9 xfailed`), Python 3.10/pandas 2 and Python 3.11/pandas 3 parameter IO coverage (`80 passed` each), and validation tests (`10 passed`).
- Generated fresh parity evidence at `validation/comparisons/v07-v08-20260712-175136.json`: 11/11 notebooks per branch, 14/14 leaves, 8 PASS, 6 documented EXPECTED_DIFFERENCE, and no regressions or missing artifacts.
- Corrected the validation contract's staging orchestration revision to the checked-out source revision.
- Generated report-only runtime evidence at `validation/benchmarks/v07-v08-runtime-20260712-175136/`: 12 workers, 150 samples, 15 matched workloads, and no warnings.
- Added validation-side fit-runtime benchmarking for 15 optimizer invocations, with isolated warm-ups, five timed repetitions, workload metadata, and mean ± sample-standard-deviation plots.
- Normalized staging fit budgets to the pinned v0.7.4 observed workloads: 21 evaluations for spectral guidance and 17 for the two-dataset example; reran the full benchmark with no workload warnings.
- Added a manifest-driven 14-leaf scenario contract and external v0.7-compatible result comparison layer.
- Fixed staging result coverage: DOAS saving and all four spectral-constraint leaves.
- Corrected the staging target optimizer budget from 11 to 10 evaluations; verified target fitted-data normalized RMS 4.90e-8.
- Added focused compatibility and translation regression tests (4 passed).
- Clean matrix result: 11/11 notebooks per branch; 8 PASS and 6 documented EXPECTED_DIFFERENCE leaves, with no regressions or missing artifacts.
- Recorded source, lockfile, notebook, and result hashes in validation/comparisons/v07-v08-semantic.json.
- Added issues/ with investigation briefs for weighted scale drift, rates.k3d2 identifiability, and weighted-RMSE persistence.
