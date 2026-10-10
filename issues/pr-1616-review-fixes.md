# PR #1616 review fixes on `staging_final_fixes` — 2026-10-05

Greptile reviewed the staging-to-main PR #1616 at `e32f1c97` and reported six findings. Codex
reproduced all six (`validation/runs/pr1616-greptile-20261005-014727/`). The maintainer also
asked to remove the deprecations due in 0.8.0. The fixes are on the pyglotaran branch
`staging_final_fixes`, started from `origin/staging` `e32f1c97`, as seven commits (not pushed):

| Commit | Finding | Fix |
|---|---|---|
| `cab45ab3` | `glotaran` console script points to the removed `glotaran.cli` | Script and `glotaran.cli.*` mypy override removed; a built wheel has no `console_scripts` |
| `0d38ae4a` | Deprecations due in 0.8.0 still present | `glotaran.examples`, `glotaran.parameter.ParameterGroup` and the unused `clp_area_penalties` YAML shim removed; changelog lists them |
| `a1bd12ff` | `forward` linking selects the wrong coordinate | `align_index` takes the position from the eligible coordinates; `backward` on descending axes had the same error |
| `c4e408d8` | Dataset labels redirect file writes | `Result` and `OptimizationResult` reject dataset, element and activation labels that are empty, `.`, `..` or contain `/`, `\`, `:` |
| `16e8d14b` | Duplicate dataset labels discard results | `Optimization` rejects a dataset label used in more than one experiment, before any evaluation or record |
| `b023819f` | Global concentrations include observation weights | All three result paths report unweighted matrices; see below |
| `3edaa514` | `add_svd` has no effect | The result SVD was computed and discarded on every path since #1562; the computation and the `add_svd` argument are removed (maintainer decision) |

## Findings beyond the review comments

- **Alignment** is inherited from v0.7.4: `glotaran/optimization/data_provider.py` of the reference
  has the same `align_index`. The existing `test_linking_methods` passed with the bug because in
  its cases the filter removed no coordinate before the nearest one. All examples and case
  studies use `nearest`.
- **Weighted matrices**: Greptile reported the global path only. The single-dataset and linked
  paths also built the reported matrix with `OptimizationMatrix.from_data`, which applies the
  weight by default, so `fit_decomposition.matrix`, element concentrations and activation results
  of a weighted dataset held the weighted matrix with an extra global dimension. v0.7.4 reports
  the unweighted `MatrixProvider` containers. Amplitudes, residuals and fitted data were not
  affected.
- **Label rule**: none of the 140 dataset and 189 library labels in the 73 scheme files of
  pyglotaran-examples, the case studies, the PFID workspace and the pyglotaran docs/tests is
  rejected. The check runs
  when the result is created, so an unsafe label fails after the fit; a dry run shows it first.

## Validation

- Core: 566 passed, 9 xfailed at `3edaa514` (528 at `e32f1c97`). Ruff 0.14.7 and all pre-commit
  hooks (including mypy, interrogate, codespell) pass on the changed files.
- Common rerun `20261005-023524`: 11/11 notebooks per branch, no failures; 14 leaves, 9 PASS and
  5 EXPECTED_DIFFERENCE, no REGRESSION or BASELINE_FAILURE. The leaf table and every fitted-data
  metric equal those of `20261004-234112` under the tightened contract. Staging source tree hash
  `aaf833ee8622…`.
- `simultaneous_analysis_3d_weight`: the matrices of the weighted datasets 2 and 3 were
  `structural_mismatch` (extra global dimension). They now compare as `different`, with a constant
  v0.7.4/v0.8 ratio per dataset equal to the dataset scale (1, 0.88005, 72.7362): v0.7.4 reports
  the matrix multiplied by the dataset scale, v0.8 the unscaled matrix. This is the dataset-scale
  representation difference already seen in the unweighted 3D/6D examples; the leaf stays PASS.
- Validation tests: 66 passed, 1 skipped, 4 failed (the known `test_scale_list_migration.py`
  failures).
- Runtime benchmark not rerun. Removing the result SVDs shortens every fit call by two
  decompositions per dataset; the alignment and label changes do not change the fits of the
  examples.

## Caveat on the reference environment

The reference checkout `temp/pyglotaran-main-dev/pyglotaran` is on `scale_list` (`f93c60d4`)
since the 2026-10-03 spectral-model guide port, not on the pinned v0.7.4 `8f26be01` of
`validation/scenarios.yml`. Its source tree hash `f73adf84…` equals that of the accepted reruns
of 2026-10-04, so this rerun is like-for-like with them, but none of these October reruns used
the pinned reference revision.

## Workspace changes

- `validation/case_studies/migrate.py`: `add_svd` is no longer forwarded from a v0.7
  `Scheme(...)` to `optimize`.
- `validation/profile_staging_objective.py`: SVD timing removed (the function no longer exists).
- `issues/project-api-proposal.md`: repeated dataset labels are rejected, no longer only warned.
