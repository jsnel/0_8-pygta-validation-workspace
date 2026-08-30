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

## 2026-08-28

- Added isolated external case-study inventory, v0.7-to-v0.8 migration, notebook execution, schema validation, provisional semantic comparison, evidence packaging, and hash-verification tooling under `validation/case_studies/`.
- Prepared image-complete reference/staging evidence for seven selected notebooks across three repositories at `validation/runs/case-studies/20260828-203340Z/`; all 14 executions passed and produced 366 extracted inline images in paired reference/staging sets.
- Added provisional comparison reports for nine reloadable result leaves under `validation/comparisons/case-studies/20260828-203340Z/`, without final scientific or root-cause classification.
- Added focused case-study tooling tests; the complete validation-side suite passes (`12 passed`).

## 2026-08-29

- Pinned staging pyglotaran fixes for kinetic activation normalization and v0.7-compatible signed, nearest-sample equal-area penalties, including xarray-axis and result-packaging regression coverage.
- Re-ran the established 11-notebook/14-leaf validation: both branches completed 11/11 notebooks and the semantic report remained acceptable at 8 `PASS`, 6 documented `EXPECTED_DIFFERENCE`, and no regressions or missing artifacts.
- Re-ran the report-only runtime benchmark with 12 successful workers, 150 timed samples, 15 summaries, and matching function-evaluation workloads.

## 2026-08-30

- Added `pub-2025-01-van_Stokkum_et_al` as the fourth external case-study
  contract with isolated single-slug inventory, migration, execution,
  comparison, and packaging support.
- Extended the migration layer for coherent-artifact CLP label changes,
  explicitly inert legacy selectors/relations, parameter path variables,
  v0.8 simulation calls, and legacy spectral/lifetime result consumers.
- Added opt-in fit-result capture to the isolated notebook runner so notebooks
  with commented save calls still produce reloadable, hashable comparison
  leaves without modifying source notebooks.
- Hardened the comparator against false `PASS` results when both sides contain
  zero result leaves, and included untracked staging migration files in source
  patches and changed-file manifests.
- Added focused case-study tooling and v0.8 CLP-relation regression tests.
- Fixed the migration converter to exclude injected coherent-artifact and
  damped-oscillation amplitudes from the v0.8 kinetic normalization sum, which
  had drifted every free dataset scale in affected case studies by an integer
  factor. See `issues/kinetic-activation-normalization.md`.
- Re-migrated and re-ran all four external case studies under
  `validation/runs/case-studies/20260830-143435` with the corrected converter:
  20/20 notebooks passed and package verification reports 3693 artifacts with
  zero errors.
- Preserved explicit v0.7 Scheme-level CLP-link tolerances in migrated v0.8
  experiments and restored legacy species ordering in the plotting projection.
  The affected 22-dataset publication fit now matches its reference cost and
  1,886-CLP workload, with fitted-data normalized RMS `2.41e-8` and a
  pixel-identical Fig. 7.
