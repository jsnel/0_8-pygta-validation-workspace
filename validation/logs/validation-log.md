# Validation log

## 2026-07-11 — baseline setup and first comparison

- Initialized both orchestration worktrees at their recorded parent gitlinks and nested validation submodule pins.
- Created independent Python 3.10.19 environments with `uv sync`.
- Verified editable package versions: v0.7.4/main and v0.8.0.dev0/staging.
- Collected 577 tests from the pinned result-consistency suite in both environments.
- Executed all 11 pinned `pyglotaran-examples` notebooks in each environment through the root `validation/run_examples.py` runner: 11/11 passed on each side.
- Generated isolated result bundles under `validation/runs/` and compared the common leaf scenarios with `validation/compare_results.py`.
- Exact input-data arrays matched for every mapped dataset. Fitted-data arrays are often within the first-pass tolerance; residuals and optimized parameters differ in multiple scenarios and require scenario-level triage.
- Saved-result layouts differ materially: v0.7 stores rich per-dataset NetCDF files, while staging stores separate result components and uses a `_staging` output-folder suffix.
- `ex_doas_beta` staging currently does not save a result bundle because its `result.save(...)` line is commented out; this is recorded as a missing comparison artifact, not yet classified as a pyglotaran regression.
- The initial comparison is evidence for triage only; it is not a release-parity verdict.

### Test results

- v0.7.4 `pyglotaran-extras/tests`: 145 passed, 1 xfailed.
- v0.8 staging `pyglotaran/tests`: 424 passed, 9 xfailed.
- v0.8 staging `pyglotaran-extras/tests`: 133 passed, 2 failed, 10 errors. The failures are existing staging-support/test-API mismatches: schema fixture drift and fixtures calling the old `Scheme.optimize(parameters, ...)` signature.
- v0.7.4 pinned stored-reference validator: 577 passed after installing the validation-only `pytest-allclose==1.0.0` overlay.

### 2026-07-11 — impact-ranked comparison

Generated [v07-v08-detailed.md](../comparisons/v07-v08-detailed.md) and its JSON companion. The leading evidence is:

- the translated transient-absorption target scheme changes the `[720, 890]` weight from `0.2` in v0.7 to `0.1` in staging; its fitted-data normalized RMS difference is `2.785e-3` and its largest parameter-relative delta is `25.2%`;
- `rates.k3d2` in the two-dataset transient-absorption case changes from approximately `1.25e7` to `1.94e25` while fitted-data normalized RMS difference remains `1.383e-5` and chi-square is effectively unchanged;
- staging omits 15 `weighted_root_mean_square_error` dataset metadata values that exist in v0.7;
- `simultaneous_analysis_3d_weight` has a smaller normalized fitted-data difference (`2.446e-5`) and a `2.596e-5` relative scale delta;
- input data arrays are exact for every mapped dataset, so the dominant remaining work is model translation, parameter-pathology, diagnostics, and persistence comparison rather than data loading.

## 2026-07-12 — semantic parity remediation

- Added the manifest-driven scenario contract in `validation/scenarios.yml`: 14 declared leaves from the 11 common notebooks.
- Added the external `validation/compatibility/` layer for v0.7 monolithic and v0.8 split results. It canonicalizes dimension aliases, aligns coordinates by labels, maps scale metadata, derives weighted RMSE from persisted/default weights, and retains unmapped raw variables for review.
- Corrected the staging target notebook's optimizer budget from 11 to the v0.7-equivalent 10 function evaluations. Direct source and saved-result inspection showed that the declared target uses weight `0.1` on `[720, 890]` on both pinned branches; the `0.2` weight belongs to the separate CO/CO2 scheme, so no speculative target weight change was retained.
- Re-enabled staging DOAS result saving and preserved all four spectral-constraint leaves as separate result directories.
- Added four focused compatibility/translation tests: `4 passed`.
- Clean remediated notebook runs: v0.7.4 `11/11`, v0.8 staging `11/11`.
- Final semantic comparison: `8 PASS`, `6 EXPECTED_DIFFERENCE`, `0 REGRESSION`, `0 BASELINE_FAILURE`, `0 BLOCKED`; worst accepted fitted-data normalized RMS is `2.446e-5` in the documented weighted case.
- Remaining expected differences are limited to the weakly identified `rates.k3d2` path, non-identifiable/decomposition representations, and the documented weighted solver/scale drift. No broad pyglotaran core change was made.
- Reproducibility evidence is embedded in `comparisons/v07-v08-semantic.json`: Python/package versions, source-tree SHA-256 values, lockfile SHA-256 values, notebook source-tree SHA-256 values, and result-tree SHA-256 values.

## 2026-07-12 — main feature ports to staging

- Created staging branch `feature/port-main-features-to-staging` from `7efc9d1114a2455da8bc37fc4770a455ef2e437a` and produced five individual commits: matrix ordering `4b48f373`, PFID `f33ac3c0`, ASCII NumPy scalars `b6be5f86`, pandas 3 compatibility `fc542d27`, and SVD/simulation dimension ordering `468c4cd5`.
- Each feature commit includes its implementation, focused regression tests, and its own v0.8 `changelog.md` entry.
- Focused PFID/model/parameter tests passed (`11 passed`); ASCII tests passed (`3 passed`); SVD/simulation tests passed (`10 passed`). Parameter and pandas IO coverage passed in both Python 3.10/pandas 2 (`80 passed`) and isolated Python 3.11/pandas 3.0.1 (`80 passed`).
- Full staging suite: `448 passed, 9 xfailed`.
- Restored the previously documented staging-example parity inputs in the checked-out examples tree: target budget 10, spectral-guidance budget 21, two-dataset budget 17, DOAS saving, and four separately saved spectral-constraint leaves.
- Corrected the staging orchestration contract pin to the checked-out revision `be1c861cfce21db94e1a360e882df4c8e942a40e`.
- Fresh notebook evidence under `validation/runs/{main,staging}/20260712-175136`: v0.7.4 `11/11`, staging `11/11`.
- Semantic report `validation/comparisons/v07-v08-20260712-175136.json`: `8 PASS`, `6 EXPECTED_DIFFERENCE`, zero `REGRESSION`, zero `BASELINE_FAILURE`, all 14 declared leaves present, acceptable `true`.
- Validation-side regression tests: `10 passed`.
- Runtime report `validation/benchmarks/v07-v08-runtime-20260712-175136/runtime.json`: `REPORT_ONLY`, 12 successful workers, 150 samples, 15 summaries, all function-evaluation workloads matched, and no warnings.

## 2026-08-28 — external case-study visual-review evidence

- Pinned paired reference/staging bases for `pygta-protocol-streak-PS1` (`dcad534e0f6c809c9b7aa03c646ea1796192a0b7`), `pygta-protocol-TA-PS1` (`d7612bc9a7f79812c4ad7c5cfcef0ccaecda0c59`), and `pub-2023-05-van_Stokkum_et_al` (`6bf9c260deaa014ce9cf5327c5c8e521ce9883a2`). The initial tracked trees match, with no submodules or Git LFS files.
- Preserved all reference and original v0.7 files. Added isolated `_v08` scheme/notebook copies in staging and committed them on each repository's `staging` branch: `f186361713a74fc7c6605b0f4a442d1e1c7947eb`, `f837892b1bbf3c31e068ae79fa44ea6653fe676b`, and `e253a7ea226a069823d94568dface2b7b66cfaf4` respectively.
- Generated parameter-aware schemas where statically paired parameters were available and strictly loaded all 25 migrated schemes. The two spectral guide schemes are recorded as `NOT_PRACTICAL` for parameter-aware schema generation but loaded successfully.
- Final isolated run `validation/runs/case-studies/20260828-203340Z`: 7/7 untouched v0.7.4 reference notebooks and 7/7 committed v0.8 staging notebooks passed. The migrated notebooks recorded 30 load/dry-run validations and 30 real fits.
- Extracted paired inline plot evidence: streak 44/44, transient absorption 81/81, and publication 58/58 reference/staging images. The notebooks generated no file-based plots; manifests record empty file-plot lists. Native reloadable result artifacts and hashes are retained alongside executed notebooks, logs, commands, dependency metadata, and base-to-staging patches.
- Provisional semantic reports under `validation/comparisons/case-studies/20260828-203340Z/` contain 9/9 result leaves with no missing artifacts and matching function-evaluation counts. All three repositories remain `REVIEW_REQUIRED` at the comparison layer; notably, the linked publication result has worst fitted-data normalized RMS `1.7078610902271951`. No scientific parity, expected-difference/regression label, root cause, or subjective visual decision was assigned.
- The top-level and per-repository manifests classify all three repositories `READY_FOR_VISUAL_REVIEW`. `validation/runs/case-studies/20260828-203340Z/verification.json` passed 1,302 artifact path, hash, and executed-notebook readability checks with no errors.
- Validation-side tests: `12 passed in 1.90s`. Runtime benchmarking was not run because optimizer/runtime behavior and benchmark instrumentation were unchanged.

## 2026-08-29 — post-penalty-fix baseline rerun

- Validated reference revisions `78ffaf5a` / `8f26be01` / `5e157363` / `dcbe4baa` against staging orchestration `5889e03d`, core `fb001015`, examples `7f7fd227`, and extras `d57940be`. The staging core includes kinetic activation normalization and restored v0.7 signed/nearest-sample equal-area semantics.
- The first staging reruns exposed two result-path regressions in the equal-area implementation: xarray scalar slice indices and an unexpanded index-independent matrix during result metadata construction. Focused fixes were committed as core commits `af9d5d5d` and `fb001015`; the latter is pinned by staging orchestration commit `5889e03d`.
- Accepted notebook artifacts: reference `validation/runs/main/20260829-162147Z` and staging `validation/runs/staging/20260829-162539Z`, each 11/11 notebooks passed. Failed intermediate staging evidence remains under `validation/runs/staging/20260829-161618Z` and `validation/runs/staging/20260829-162147Z`.
- Semantic report `validation/comparisons/v07-v08-20260829-162539Z.json`: all 14 leaves present; `8 PASS`, `6 EXPECTED_DIFFERENCE`, zero `REGRESSION`, zero `BASELINE_FAILURE`, acceptable `true`.
- Scenario statuses and fitted-data metrics are unchanged from `v07-v08-20260712-175136.json`. The `rates.k3d2`, spectral-guidance decomposition, weighted 3D scale, weighted-RMSE persistence, and representation investigations therefore remain open; none was resolved by these fixes.
- Core optimization/kinetic regression tests: `73 passed`. Validation-side regression tests: `12 passed`.
- Runtime report `validation/benchmarks/v07-v08-runtime-20260829-162539Z/runtime.json`: `REPORT_ONLY`, 12 successful workers, 150 samples, 15 summaries, all function-evaluation workloads matched, and no workload warnings.

## 2026-08-30 — 2025 publication case-study migration

- Cloned `pub-2025-01-van_Stokkum_et_al` into isolated reference/staging
  checkouts at source commit `9edbe177bf4671b735fba31ebc9b2b3df1885316`;
  both started from tree `8807d2d4c96acc7ef1cdff8ffc0119c30b51551f`.
  Reference remains on `main`; staging is on a local `staging` branch.
- Migrated three publication notebooks and seven legacy model documents to
  `_v08` copies. The migration records 24 explicit multi-k-matrix compositions,
  four coherent-artifact CLP label translations, eight inert weight selectors,
  and eight inert relations belonging only to disabled datasets/elements.
- Added v0.8 caller handling for parameter-path variables and the changed
  simulation API, plus compatibility projection for spectral shapes and kinetic
  lifetime coordinates used by legacy plotting/display cells.
- Confirmed and minimally fixed a v0.8 relation-resolution defect: unlike v0.7,
  staging indexed relation labels even when absent from the local aligned CLP
  axis. The focused core regression test passes (`2 passed`). See
  `issues/clp-relation-missing-label.md`.
- The final captured run `validation/runs/case-studies/20260830-182522/` passed
  3/3 reference and 3/3 staging notebooks, with seven load/dry-run checks and
  seven real fits. Six fit-associated migrated schemes strictly load; four have
  parameter-aware schemas and two spectral schemes are `NOT_PRACTICAL` for
  static parameter pairing. The seventh migrated scheme is simulation-only and
  loads during notebook execution.
- The whole-cell migration now preserves the notebook's Scheme-level
  `clp_link_tolerance=2.1` in both v0.8 experiments. Its objective cost and CLP
  count match exactly (`5.1245e+05`, `1886`), and its worst fitted-data
  normalized RMS improved from `2.67e-1` to `2.411819127175127e-8`.
- The compatibility projection restores the v0.7 initial-concentration species
  order. The reference/staging Fig. 7 PNGs are pixel-identical (486,356 pixels,
  zero differing pixels), while label-aligned concentration and SAS arrays agree
  to normalized RMS `2.1e-16` and `5.7e-15`, respectively.
- All seven result leaves are present in the provisional semantic comparison.
  Every leaf remains `REVIEW_REQUIRED`: the whole-cell fit and two
  room-temperature fits meet the primary fitted-data tolerance but retain
  secondary representation evidence; the four MCL leaves remain between
  `3.17e-4` and `2.94e-2`. The first spectral fit also has a workload mismatch
  (`20` vs `25` evaluations).
- No scientific parity, expected-difference/regression label, or subjective
  visual acceptance is assigned. Runtime benchmarking was not run because the
  case-study evidence records fit workloads directly and the shared benchmark
  contract was unchanged.
- Validation-side tests: `22 passed`. The pinned established baseline rerun at
  `validation/comparisons/v07-v08-20260830-110309.json` is acceptable with
  11/11 notebooks per branch and all 14 declared leaves present.

## 2026-08-30 — kinetic activation normalization inflated by injected amplitudes

- Investigated the `pub-2023-05-van_Stokkum_et_al` TA target analysis, where the
  staging initial cost was `30162.0` against the reference `869.51` while the
  final costs nearly agreed and the migrated `plot_fitted_traces` figure
  disagreed visibly with the publication figure.
- Root cause: the v0.8 `KineticElement` divides its initial concentrations by
  the sum over *every* `activation.compartments` entry. The migration must add
  coherent-artifact element labels and damped-oscillation labels there, because
  those v0.8 elements require them, so each injected `label: 1` inflated the
  denominator by exactly `1.0` over the v0.7
  `InitialConcentration.normalized()` denominator.
- Measured effect: denominators `1.028 -> 3.028` for `670TR1` and
  `1.000 -> 2.000` for `700TR1`. With `scale.670` fixed at 1 the estimated CLPs
  absorbed the inflation (measured `2.9465`, predicted `2.945525`) and every
  free `scale.*` parameter drifted by the reciprocal, up to a factor of three.
  `pyglotaran_extras` divides plotted traces by `dataset_scale`, which is why
  the drift was visible in the figure while the native `fitted_data` and
  `residual` arrays still agreed with v0.7.
- Remediation is migration-side only: `validation/case_studies/migrate.py` now
  also lists every injected artifact/oscillation label under
  `activations.<name>.not_normalized_compartments`. No pyglotaran core change.
- Verification with the corrected activation: cost `780.2826936484729` at
  `nfev=3` against the reference `780.28`, and `778.4181898707781` at `nfev=15`
  against the reference `778.42`. Every optimized parameter matches v0.7.4 to
  at most `2.945e-06` relative deviation, against factor-of-three deviations
  before the fix.
- Validation-side regression tests: `11 passed`, including the new
  `test_convert_model_excludes_non_kinetic_amplitudes_from_normalization`.
- Affected migrated models are enumerated in
  `issues/kinetic-activation-normalization.md`: the 2023 publication model,
  eight datasets of the 2025 `77K_target_cells` model, and ten
  `pygta-protocol-ta-ps1` models. Those case studies need re-migration and a
  fresh paired run before their evidence packages are valid.

## 2026-08-30 — four-repository case-study re-migration and paired rerun

- Re-migrated all four case studies with the corrected converter and re-ran
  every reference/staging pair under timestamp `20260830-143435`.
- Execution: 8/8 run sets exited 0 and 20/20 notebooks passed. Package
  verification is `PASS` at 3693 checked artifacts with zero errors, and all
  four repositories are `READY_FOR_VISUAL_REVIEW`.
- Schema validation: every migrated scheme passes strict loading. Only the two
  `pub-2025-01` spectral schemes remain `NOT_PRACTICAL` for parameter-aware
  schema generation, unchanged from the previous handoff.
- Change containment: a structural comparison of every regenerated scheme
  against its pre-fix version yields 29 differences, all
  `not_normalized_compartments` additions or extensions. Remaining textual
  churn is YAML anchor expansion only. `pygta-protocol-streak-ps1`, which has
  no coherent-artifact or damped-oscillation element, is structurally identical
  to its committed schemes (0 differences) and serves as the control.
- The re-migration also brought `pub-2023-05` and `pygta-protocol-ta-ps1`
  notebooks onto the current converter, picking up the previously added
  simulation adapter, kinetic lifetime/rate coordinates, and spectral squeeze
  handling. Those two case studies had been migrated before those changes.
- `pub-2023-05` `20230522PSI_TA_Scy6803target`: every optimized parameter now
  matches v0.7.4 to at most `2.945e-06` relative, against factor-of-three
  deviations before. The linked 25-dataset analysis improved from `1.7079` to
  `4.3105e-02` worst fitted-data normalized RMS.
- The primary fitted-data metric is blind to this defect class: the
  `results/20230520` leaf reads `7.2284e-07` both before and after, because the
  inflation is exactly compensable by the free dataset scales. Parameter
  comparison, initial cost, and scale-divided trace plots are what expose it.
- Still unexplained and separate: `pub-2025-01`
  `77K_target_cells/case-study-results/fit-001-target_result1` remains at
  `0.2673076675046294` worst fitted-data normalized RMS with `0.0` input
  difference across all 22 datasets. Its single-evaluation cost moved only from
  `449930.0` to `449440.0` against a reference `512450.0`, and optimality
  differs by four orders of magnitude. See
  `issues/kinetic-activation-normalization.md`.
- All leaves remain provisional `REVIEW_REQUIRED`; no scientific parity,
  expected-difference, or regression classification is assigned.
- Validation-side regression tests: `21 passed`. No pyglotaran core change was
  made in this pass.

## 2026-08-31 — PFID local case-study migration and paired validation

- Added the local `pfid` repository as a case-study contract. Its independent
  reference/staging Git histories have different commits
  (`39976053cb29eebfdb25a2625b4b62249ab57314` and
  `52082fb4e705117a0438c45bb3ff3dcb844c16d9`) but the same initial tree
  `83d924beec8659bb7af7e8103530d2a947e7244d`; neither checkout has a remote.
- Migrated the sole notebook and both legacy models to additive `_v08` files.
  PFID label/frequency/rate arrays now use typed `oscillations`; PFID datasets
  receive the required multi-Gaussian activation in addition to kinetic
  activations. The global model's intentional `link_clp: false` groups are
  preserved by splitting their datasets into independent v0.8 experiments
  while retaining shared nonlinear optimization.
- Added migration support for v0.7 `Project` data loading/optimization calls,
  v0.8 saving-options syntax, IRF-only artifact/oscillation datasets, PFID
  legacy plotting projection, and auxiliary xarray-coordinate cleanup.
- Final paired run: `validation/runs/case-studies/20260830-235141/`. Both the
  untouched v0.7.4 notebook and migrated v0.8 notebook pass end-to-end, each
  with 58 extracted inline images and two captured result leaves. Both v0.8
  schemes pass parameter-aware schema generation and strict loading; both dry
  runs pass.
- All 26 dataset inputs compare exactly. Worst fitted-data normalized RMS is
  `1.67741866882088e-13` for the global fit and
  `5.255481356856353e-13` for the guide-assisted target fit, far below the
  ordinary `1e-6` threshold. Residual differences are numerical noise; matrix,
  CLP, parameter-set, and result-layout differences remain secondary evidence.
- Both fits use one evaluation on each branch. v0.7 reports success because it
  includes the sole varying but inactive `alpha.1`; v0.8 resolves zero active
  varying parameters and returns complete initial-fit results with the
  non-success reason `zero-size array to reduction operation maximum which has
  no identity`. The comparison therefore remains provisional
  `REVIEW_REQUIRED`, and the package is `BLOCKED_STAGING` despite numerical
  fitted-data agreement. See `issues/inactive-free-parameter-count.md`.
- Focused case-study tooling tests: `16 passed`. No pyglotaran core or runtime
  benchmark change was made.
- The required established-baseline protection reran twice, at
  `20260831-000137` and `20260831-000520`. Both attempts executed 11/11
  notebooks on each branch and produced all 14 leaves, but both independently
  classified `ex_spectral_guidance` as `REGRESSION`: fitted-data normalized RMS
  `1.2572461877946428e-6` exceeds the unchanged `1e-6` contract. The PFID work
  did not modify `validation/run_examples.py`, `validation/compare_results.py`,
  baseline compatibility code, either pyglotaran tree, or the examples. The
  tolerance was not relaxed. Full validation-side tests still pass (`26
  passed`).

## 2026-08-31 — PFID zero-active-parameter optimizer resolution

- Confirmed that both PFID parameter tables contain exactly one varying
  parameter, `alpha.1`, while neither migrated model references it. Model
  resolution therefore correctly removes it from the v0.8 optimizer vector.
- Reproduced the failure in a focused optimizer test: passing the resulting
  empty vector to SciPy's trust-region solver raises
  `zero-size array to reduction operation maximum which has no identity`.
  v0.7 avoided that path only because it retained the unused parameter as a
  flat optimizer direction.
- Added a v0.8 optimizer path for zero active varying parameters. It evaluates
  the model once without calling SciPy and returns `success: true`, zero free
  parameters, zero Jacobian evaluations, an empty-column Jacobian, a `0 x 0`
  covariance matrix, and termination reason `No free parameters to optimize.`
- The regression test includes an unused varying parameter alongside fixed
  model parameters, matching PFID's resolved parameter topology. The optimizer
  test directory passes (`55 passed`). The full core suite reached `449 passed,
  9 xfailed`; five unrelated result-path tests compare relative and absolute
  temp paths differently under this workspace's forced pytest base directory.
- Re-ran the migrated staging notebook at
  `validation/runs/case-studies/20260831-224923/pfid/staging/`: the notebook
  passed with 58 inline images, and both real-fit markers report `PASS` with
  the explicit zero-parameter termination reason.
- Compared the repaired staging capture with the original v0.7 reference. The
  primary numerical evidence is unchanged: fitted-data normalized RMS
  `1.67741866882088e-13` and `5.255481356856353e-13`, with one function
  evaluation on each branch. Reactivating an arbitrary model parameter was
  rejected because it would turn a validated reconstruction into a truncated
  or moving optimization.
