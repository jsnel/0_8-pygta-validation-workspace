# Validation changelog

## 2026-09-06 — Final main-versus-staging validation

- Executed all 23 selected notebooks per branch at reference core `8f26be01`
  and optimized staging `f6a091eb`. Common results: 14/14 leaves, 8 PASS,
  6 EXPECTED_DIFFERENCE, zero regressions or missing artifacts.
- Retained all 40 case-study real-fit results per branch: 29 fitted-data
  comparisons meet `1e-6`, 27 have exact inputs, and 21 satisfy both. Eleven
  primary differences remain in the streak/TA protocols and publication cases.
- Fixed case-study capture collisions by including the notebook stem in save
  paths. Fixed benchmark instrumentation to execute but not time/count staging
  dry runs. Production models, notebooks, fit budgets and core are unchanged.
- Validation tests: 37 passed, 1 skipped; focused core tests: 35 passed.
  Schema/load checks: 34 schemes passed. Artifact audit: 4,692 files verified.
- Final benchmark: 12 successful workers, 150 timed samples, report-only.
  Evaluation counts match for 14/15 fits; spectral guidance uses 23 versus 21.
- Full evidence, exact revisions and residual issues:
  `issues/final-validation-run.md`. Generated outputs remain ignored; no commit.

## 2026-09-06 — Runtime optimization continuation

- Replaced xarray scalar iteration with plain NumPy label extraction in staging
  amplitude reconstruction at core `20020378` plus an uncommitted focused patch.
  No numerical operation, dependency, production input or solver setting changed.
- Fresh paired public-call benchmarks show PFID real-call mean reductions of
  42% and 67%, and spectral guidance 6.4%. Two-dataset overall timing and peak
  memory show no convincing improvement. Full distributions are retained.
- Native original and controlled result snapshots match exactly; both controlled
  standard workloads converge after four genuine steps. PFID has zero free
  parameters, so nonlinear controlled steps require a prohibited problem change.
- Fresh baseline/optimized/reference suites pass 11/11 notebooks each; staging
  self-comparison passes all 14 leaves with zero fitted-array RMS difference.
  Reference comparison has 8 PASS, 6 EXPECTED_DIFFERENCE and zero regressions.
- Validation tests: 36 passed, 1 skipped; focused staging core tests: 35 passed.
  Corrected the inherited handover's acceptance overstatement and documented
  original budget exhaustion, an inherited Gaussian-shift defect and lock drift.
- Evidence: `validation/runs/runtime-continuation-20260906/`; full handoff:
  `issues/staging-runtime-optimization-continuation.md`. No commits made.

## 2026-09-06 — Refined OC/COC two-dataset example

- Replaced the historical two-dataset transient-absorption model in both
  pinned example notebooks with the supplied refined OC/COC model, including
  fast/slow kinetic elements, coherent artifacts, weights, and explicit CLP
  relations.
- Removed optional v0.7 extras-only plotting cells that imported the existing
  unterminated `a_matrix.py` helper; the native fit, result persistence, and
  xarray plotting workflow remain executable.
- Fresh focused runs completed the v0.7 notebook and the v0.8 dry-run, fit,
  plotting, and persistence workflow. The paired result comparison reached a
  worst fitted-data normalized RMS of `8.81932458660469e-06` under the `2e-5`
  tolerance, and neither optimized parameter table contains `rates.k3d2`.
- Closed the historical `rates.k3d2` example-level investigation. The focused
  comparison retains `EXPECTED_DIFFERENCE` for bounded refined-model parameter
  and fit drift; the full 14-leaf validation rerun remains separate work.

## 2026-09-06 — Spectral-guidance isolation

- Isolated the current-tree regression to the three newly fixed example
  parameters and resulting optimizer-path sensitivity; restoring only pinned
  vary flags reproduces the accepted `3.0325968790706684e-7` RMS exactly.
- Added a process-isolated diagnostic and opt-in cross-engine trajectory test;
  reference runtime plus reference compartment order restores exact objective,
  Jacobian, and optimizer-trajectory parity.
- Documented a secondary staging result-state restoration defect, whose fit
  effect is too small to explain the regression. No core, notebook, dependency,
  scenario tolerance, or acceptance classification was changed.
- Evidence and source revisions: `issues/spectral-guidance-current-tree.md`;
  paired probes: `validation/runs/spectral-isolation-20260906-final/`.

## 2026-09-01

- Added a reusable PEP 723 notebook process-tree profiler with optional public fit-call timing and optimizer workload metadata.
- Profiled the migrated PFID notebook across five fresh-process runs: reference mean `69.94 s` and `3327.7 MiB` peak RSS; staging mean `180.05 s` and `5143.5 MiB` peak RSS.
- Documented that staging performs two costly dry runs and reconstructs result data across three linked objectives; the exact peak-RSS allocation site remains unassigned.

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

## 2026-08-31

- Extended external case-study tooling for the local PFID repository: native
  v0.8 PFID scheme mapping, intentional unlinked-CLP experiment splitting,
  IRF-only artifact/oscillation datasets, and legacy `Project.optimize`
  notebook migration.
- Made isolated fit-result capture independent of notebook-global saving
  filters and taught the comparator to prefer instrumented result leaves and
  resolve v0.7 labeled NetCDF files.
- Added PFID plotting compatibility fields and auxiliary-coordinate cleanup,
  plus focused regression coverage (`16 passed`). The paired run at
  `validation/runs/case-studies/20260830-235141/` passed both notebooks and
  produced exact inputs with worst fitted-data normalized RMS `5.26e-13`.
- Re-ran the established baseline twice after the shared case-study tooling
  changes. Both branches executed 11/11 notebooks and produced 14/14 leaves,
  while the unchanged semantic gate reproducibly reported
  `ex_spectral_guidance` at `1.2572461877946428e-6` versus its `1e-6`
  tolerance. No tolerance or baseline classification was changed.
- Added an explicit zero-active-parameter optimizer path in staging. Resolved
  models with no varying parameters now produce a successful, single-evaluation
  reconstruction instead of passing a zero-column Jacobian to SciPy. The
  regression covers PFID's sole varying-but-unused parameter and the optimizer
  suite passes (`55 passed`).
- Re-ran the migrated PFID notebook with the optimizer fix at
  `validation/runs/case-studies/20260831-224923/pfid/staging/`. Both real fits
  pass with zero active parameters; comparison against the v0.7 reference
  retains fitted-data normalized RMS values of `1.68e-13` and `5.26e-13`.

## 2026-09-05

- Registered the local TestCaseInitConc external case study and documented its
  blocked reference execution, source revisions, and follow-up requirements.
  Existing common validation acceptance claims remain unchanged.

- Completed the authorized TestCaseInitConc portable notebook adapter and v0.8
  scheme migration, including public extras replacement plots. Fresh 13-dataset
  fit comparisons meet 1e-6 (worst 2.54e-8); secondary evidence remains reviewable.
  All 26 validation tests pass. Evidence run: 20260905-200057.

## 2026-09-06 — Shared notebook compatibility

- Extracted embedded case-study helpers into the installable validation/notebook_compat package; updated all 12 ignored source _v08 notebooks and future migration output to import it.
- Added repeatable consolidation tooling, package/source provenance, documentation, and compatibility tests (31 staging tests; four applicable v0.7 tests).
- Fresh common notebooks passed 11/11 per branch and direct conversion passed all 14 leaves. Current-tree spectral-guidance parity exceeds tolerance; see issues/notebook-compatibility-consolidation.md for exact evidence and revision drift.
- Final consolidated case-study execution passed all 12 notebooks; verified 2,896 artifact hashes with no errors. Evidence: validation/runs/case-studies/compat-20260906-022006/compatibility-verification.json.
