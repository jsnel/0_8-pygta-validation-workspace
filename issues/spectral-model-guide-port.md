# Spectral model CLP guide port — October 3

## Scope and revisions

This completes the [September 22 scale_list port](scale-list-staging-port.md) with the
three source commits added after the Hamamatsu loader (`ca8d77e3` on
`jsnel/scale_list_rebased`):

| Source commit | Content |
| --- | --- |
| `2ce22078` | `skewed-gaussian-sum` shape; `spectral-model-clp-guide` megacomplex whose guide data are generated from a shape and refreshed with the parameters |
| `2012541b` | Parameter markdown for labels that are also group prefixes; explicit outer join in linked-data alignment |
| `f93c60d4` | Guide results report the current generated data |

Reference core: main checkout `temp/pyglotaran-main-dev/pyglotaran` at
`f93c60d4152e86dd340e3a462c918eac410eef41` (`scale_list` tracking
`jsnel/scale_list_rebased`). The September 22 common baseline used main `e6ba6316`.

Staging core: branch `feature/scale_list` (the pushed `codex/port-scale-list` plus its
pre-commit fix `b30889d9`), seven new local commits:

| Commit | Change |
| --- | --- |
| `7234202a` | `SpectralShapeSkewedGaussianSum` and a shared skewed-Gaussian component helper |
| `43eb0018` | `Parameters.markdown()` for prefix labels (previously `TypeError`) |
| `33156dfd` | Explicit `join="outer"` in linked-data alignment (no change on the locked xarray 2024.7) |
| `d71760ae` | `SpectralModelClpGuideElement` with inline `shapes`; reuses `SpectralDataModel` axis fields |
| `9482779c` | Missing generated datasets created after experiment resolution; values refreshed in the objective at every evaluation |
| `27d06da9` | Results report generated data at the current parameters |
| `5aaa46c9` | `devdocs/scale-list-port/DELTA.md` and `USAGE.md` updates |

`27d06da9` is the tested runtime revision. Nothing was pushed or merged.

Staging differences from the source: shapes are inline under `shapes` (staging has no
top-level shape section); the generated dataset attribute is `generated_by_model: 1`
because netCDF attributes cannot be booleans; staging results do not keep data SVD
variables, so the SVD recomputation in `f93c60d4` has no counterpart; the source
`Project.create_scheme` guard has no counterpart because staging has no `Project`.

Workspace changes (branch `codex/port-scale-list-validation`):

- `validation/case_studies/migrate.py`: translates `spectral-model-clp-guide` (target
  shape copied inline) and drops dataset groups without datasets, which v0.7 ignores and
  staging cannot optimize. Dropped groups are logged as `empty_dataset_groups`.
- `validation/compatibility/normalize.py`: `scalar_metadata` keeps non-scalar attributes
  as lists. The `scale_list` reference writes an empty `dataset_scale_list` attribute to
  every result dataset, which made all 14 leaves `BASELINE_FAILURE`.

## Tests

- Core suite: **548 passed, 9 xfailed** (534 before plus 14 new). All pre-commit hooks,
  including mypy and codespell, pass over the seven commits. mypy found that the
  "more than one data generating element" error referenced a nonexistent `DataModel.label`;
  fixed before the final commits.
- Generated-data tests cover the generated axes and values, equality of the refreshed
  linked slices with a full re-alignment, recovery of a free guide shape location in a
  linked fit (it stays at its start value when refresh is disabled), the result data
  replacement (fails without `27d06da9`), and rejection of missing measured data.
- Validation suite: **70 passed, 1 skipped** (existing opt-in spectral-guidance probe).

## Common validation rerun

Runs `validation/runs/{main,staging}/20261003-163022/`: **11/11** notebooks per branch.
`validation/comparisons/v07-v08-20261003-163022-loaderfix.json` accepts all 14 leaves:
**8 PASS, 6 EXPECTED_DIFFERENCE**, no REGRESSION, BASELINE_FAILURE or missing artifacts.
All reported metrics equal the September 22 values (two-dataset `8.81932e-6`, spectral
guidance `1.25777e-6`, weighted 3D `1.60659e-10`). The first comparison of the same runs,
`v07-v08-20261003-163022.json`, is retained; it failed only on the `dataset_scale_list`
loader issue above.

Staging pyglotaran source tree hash `6d9573c8…` matches `27d06da9` after accounting for
two new files that were LF in the working tree during the run and are CRLF after the
autosquash checkout (`core.autocrlf=true`); `git diff ORIG_HEAD HEAD` after the rebase was
empty. Examples: main `4a3268ef`, staging `ddfa6363`. Extras: main `b72a21e0`, staging
`700f9de4`. Main uses NumPy/SciPy/xarray 2.2.6/1.15.3/2025.6.1; staging 2.0.1/1.14.1/2024.7.0.
The runtime benchmark was not rerun: for datasets without a generating element the
objective adds one boolean check per evaluation.

## Case study: `testcase_spectral_model_guide`

Author notebook `20260929target_State1_7comp_day1_2_all_open1spectral_model_guide.ipynb`,
model `20260929target_State1_2_7comp_day1_2_all4_spectral_model_guide2_2mc2.yml`,
parameters `...guide81.csv`, four ASCII datasets, 15-evaluation budget, `x_scale='jac'`,
`clp_link_tolerance=0`. Eight datasets are fitted: four measured and four generated guides
(`Odata_guide_s1..s4`), 45 free parameters, NNLS.

The staging port is
`temp/case-studies/testcase_spectral_model_guide/staging/<same name>.ipynb`
(git-ignored). It was generated from the current main notebook; the previous staging copy
was an older version without main cell 29 and is retained in the evidence directory. The
model is translated to `models/..._v08.yml` by `convert_model`; the parameter CSVs are
copied unchanged. Only cells using v0.7-only API were replaced: imports, model loading,
validation (now a dry run), `Scheme`/`optimize` (now `scheme.optimize` plus
`pyglotaran_compat.convert_result`), result display/RMSE/saving (native result saved to
`results/20260929target_State1_2_v08/`), the kinetic diagram (author code rendered with the
main environment from the staging optimized parameters, as in the ST case), the parameter
table, and the scaled-concentration plot call described below. The notebook executes every
cell up to the author's first `stop` cell, the same range as the main notebook outputs.

Evidence: `validation/runs/spectral-model-guide-20261003-141447/` (`capture_fit.py`,
`compare.py`, `comparison-*.json`, `notebook-port/` with the port script, figures from both
notebooks, and the pre-port staging copy).

| Metric | Staging (SciPy 1.14.1) | Staging (SciPy 1.15.3, `.venv-stsingle`) |
| --- | ---: | ---: |
| Final cost, relative to reference `1.8051935e10` | 1.17e-6 | 1.44e-7 |
| RMSE (reference 253.693978) | 253.694127 | 253.693996 |
| Measured fitted data, worst normalized RMS | 2.08e-6 | 1.81e-7 |
| Guide fitted data, worst normalized RMS (`s1`) | 4.81e-4 | 7.76e-5 |
| Species concentration × dataset scale, worst normalized RMS | 6.35e-5 | 3.75e-6 |
| SAS, worst normalized RMS | 6.05e-5 | 5.59e-6 |
| Free parameters above `rtol=1e-4` | 17 of 45 | 3 of 45 |

Evaluating the staging objective at the reference optimized parameters gives the reference
final cost exactly (`18051935084.118805`, relative difference 0). The differences above
therefore come from the optimizer path of a budget-truncated fit and the different
NumPy/SciPy versions, not from the objective. The iteration table matches the main notebook
to its printed precision. The largest parameter difference is `Oshapes.s1v.skewness`
(0.0107 ± 0.507 on main): its standard error is about 50 times its value, so the
`s1` guide endpoint is not determined by this budget. All differences are below 0.1%.

## Reporting differences in the ported notebook

- Concentrations: v0.7 `species_concentration` includes the dataset scale; the
  compatibility projection of the v0.8 result does not. Concentration panels differ by
  exactly `Oscale.N` per dataset (same class as the MCL finding in
  [inactive-free-parameter-count.md](inactive-free-parameter-count.md)).
- Species order in concentration/SAS legends follows the activation compartment order in
  the compatibility projection (`s3so` after `s3`), so line colors differ from main.
- Overview residual panels are titled "weighted residual"; the values equal the residual
  because the measured datasets are unweighted.
- The author's `plot_scaled_st1_st2_concentrations_and_sas_one_directory` uses the first
  complete `scale.*`/`Oscale.*` parameter set. On v0.7, `optimized_parameters` contains
  every CSV parameter, so it divides by the **unfitted** `scale.3/4/7/8` (6.5–9.3), not the
  fitted `Oscale.*` (0.43–2.09). v0.8 keeps only used parameters; the port supplies the
  v0.7 parameter set to reproduce the main figure. This is an author-notebook question,
  not a port difference.
- Guide plots, traces, kinetic scheme, residual SVD grid, SAS and DAS match main.

## Pre-existing issues noticed

- Staging `ClpGuideElement` sets a private `_exclusive` attribute that the exclusivity
  check never reads, so plain CLP guides are not enforced as exclusive. Unchanged.
