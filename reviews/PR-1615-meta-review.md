# PR #1615 meta-review

Inputs: [PR-1615-Fable-5.1.md](PR-1615-Fable-5.1.md) (F), [PR-1615-GPT-6.1-Sol-xhigh.md](PR-1615-GPT-6.1-Sol-xhigh.md) (G) and [PR-1615-Mystery.md](PR-1615-Mystery.md) (M), all on `staging_rebase_with_project` at `ffa4377c` against `staging_rebased` at `4c635ae6`. Finding numbers refer to the numbered findings of each review; G's and M's unnumbered questions are cited by reviewer only.

Every finding was checked against the code. "Reproduced" means reproduced on `ffa4377c` in this meta-review (Windows 11, Python 3.10.19, locale encoding cp1252); "code" means confirmed by reading the code; "reviewer" means taken from the review without an independent check.

## Decision rule

First pass: a finding is fixed when all three hold:

1. It is reproduced on `ffa4377c`.
2. It is reported by at least two reviewers and causes wrong persisted data, a crash, or a local path in an export in ordinary use; or it is a regression from this PR that makes a previously working call fail.
3. The fix is local and adds no abstraction.

Second pass: four findings from the deferred list (fixes 7 to 10) were fixed on the maintainer's decision.

## Fixed

Uncommitted, in `temp/pyglotaran-staging-dev/pyglotaran`. Each test listed fails on the `ffa4377c` sources and passes with the fix.

| # | Finding | Reviewers | Reproduced on `ffa4377c` | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| 1 | YAML is written as UTF-8 and read with the locale encoding | G#9, M#2 | `name="café"` reads back as `cafÃ©`. `Ё` raises `UnicodeDecodeError`; `list_results` then skips the record as damaged, and `recompute` and `compare_results` fail. | `load_dict` opens files with `encoding="utf8"` (`glotaran/builtin/io/yml/utils.py`) | `test_yml.py::test_non_ascii_round_trip` |
| 2 | A failed or interrupted record keeps the standard errors of the initial parameters | F#3, G#7 | A fit seeded with `first.optimized_parameters` that fails at evaluation 3 writes the first fit's standard errors to `optimized_parameters.csv`. The specification requires none for these statuses. | `FitRecord.finish` saves a copy with `standard_error = nan` (`glotaran/project/record.py`) | `test_record.py::test_failed_fit_is_recorded`, now seeded with standard errors |
| 3 | `number_of_function_evaluations` of a failed fit depends on `verbose` | F#2, M#4 | Three evaluations, then an optimizer error: `Result` and `export.yml` report 1 with `verbose=False` and 4 with `verbose=True`; `record.yml` reports 3. | `from_least_squares_result` takes `number_of_function_evaluations`; `Optimization.run` passes `len(cost_history)`, `dry_run` passes 1 (`glotaran/optimization/info.py`, `optimization.py`) | `test_record.py::test_failed_fit_with_result_is_recorded` asserts the `Result` value |
| 4 | Export sets `Result.source_path` to the removed temporary folder; a later export writes that path to `result.yml` | G#12, M#1; stale comment F#9 | After `export`, `result.source_path` is `exports/.first.<pid>.tmp`, which does not exist. A second export's `result.yml` contains `source_path: C:\...\.first.<pid>.tmp`. A loaded result writes its absolute folder the same way. | `export_result` saves `result.model_copy(update={"source_path": None})`; stale comment removed (`glotaran/project/export.py`) | `test_export.py::test_export_keeps_the_result_source_path` |
| 5 | `OptimizerSettings` rejects `ftol`, `gtol` or `xtol` of `None` | G#4 | `scheme.optimize(..., ftol=None)` raises `ValidationError`. On `4c635ae6` it fits; SciPy disables that termination condition. | Tolerances typed `float \| None` in `OptimizerSettings`, `Optimization` and `Scheme.optimize` | `test_result.py::test_result_optimizer_settings_round_trip`, now with `gtol=None` |
| 6 | Getting started says `Project.start()` uses the folder of the notebook | F#11, G#15, M#8 | Code and `project.md` use the working directory. | One sentence in `getting_started.ipynb` | none |
| 7 | Optimized parameters, cost and result arrays come from the last evaluated point; chi-square and standard errors from SciPy's solution `x` | F#1 (G: on base) | See the table below. v0.7.4 resets to `x` (`optimizer.py:312`). | `Optimization.run` sets the parameters to `ls_result.x` before the final evaluation | `test_optimization.py::test_histories` (`chi_square == 2·cost` for all three methods); `test_recompute.py::test_recompute_reproduces_the_fit` (chi-square and RMSE equal) |
| 8 | The `export.yml` summary of a recomputed result describes the dry run (`termination_reason: Dry run.`, 1 evaluation) with `converged` from the record; a recompute of that export stores the dry-run summary as `original_fit` | F#8, G#5 | Reproduced. | `export.yml` holds the original fit's summary and `recomputed_from: <record id>`; the recompute stays in `result.yml` (`export.py`, `project.md`) | `test_export.py::test_export_of_a_recomputed_result` |
| 9 | Saved data files hold `source_path` and `io_plugin_name` attributes | rest of G#12, M#1 | Every export of data loaded with `load_dataset` has the absolute raw-file path in `input_data.nc` (`data.source_path = .../project/data/raw.nc`). A second export of a result has the removed temporary folder in `residuals.nc` and the other arrays. | `save_dataset` writes a shallow copy without these two attributes, at the top level and on data variables; `load_dataset` sets them on loading (`glotaran/plugin_system/data_io_registration.py`) | `test_data_io_registration.py::test_save_dataset_without_path_attributes` |
| 10 | A fixed or expression parameter keeps a standard error from the initial parameters | found in this meta-review | Seeding with `first.optimized_parameters` and fixing `irf.width` gives it the first fit's standard error (2.14e-5). v0.7.4 behaves the same. | `calculate_parameter_errors` sets all standard errors to NaN before assigning those of the free parameters; dry runs and recompute are not affected (`info.py`) | `test_scheme.py::test_optimize_parameters_not_estimated_have_no_standard_error` |

Difference between the saved parameters and SciPy's solution on `ffa4377c`, sequential decay, measured in this meta-review. After fix 7 it is 0.0 in every case.

| Method | Relative difference of the parameters | Relative difference of the cost |
| --- | --- | --- |
| Trust Region Reflection (default), converged or stopped by `maximum_number_function_evaluations` | about 1.5e-7 (`irf.width`) | up to 2e-8 |
| Levenberg-Marquardt, converged | 6.1e-5 | 5.7e-6 |
| Levenberg-Marquardt, stopped after 12 evaluations | 1.2e-3 | 3.3e-6 |

Notes:

- Fix 4 was first written with a deep copy of the result. `Result` cannot be deep-copied, because `Parameters` holds an asteval evaluator that references `sys.stdout`, and a deep copy would double the memory of an export.
- Fix 5 has one reviewer. It is included under rule 2 because this PR introduced the failure in plain `Scheme.optimize`, outside the project API. Nothing in the workspace passes `None` today.
- Fix 7 changed four existing test assertions that assumed the result is the last evaluated point: `test_histories` and `test_parameter_history_in_user_coordinates` compared the last history entry with the result, and `test_global_data` asserted that the optimized parameters differ from the initial ones. That fit starts at the true parameters of noiseless data, so SciPy's solution equals the start, and the assertion held only because of the finite-difference step. It was removed; the test still checks `optimized_parameters.close_or_equal(parameters)`.
- Fix 9: after an export, the in-memory `Parameters.source_path` and array attributes of the result still name files in the removed temporary folder. They are no longer written to any file.
- pyglotaran `changelog.md`: bug-fix lines for fixes 1, 3, 7, 9 and 10, which change behavior from before this PR. Fixes 2, 4, 5 and 8 correct code that is new in this PR.

## Decisions

- **Validation threshold bump** (F#4, G, M#7): kept in this PR. Paragraph for the PR description:

  > This PR also moves the `validation` submodule to `c15b2b9c`, which raises the fitted-data normalized-RMS threshold of `ex_spectral_guidance` from 2e-6 to 3e-6. The constrained guided fit is sensitive to the optimizer path: its normalized RMS is 1.26e-6 locally and 2.23e-6 in CI (2.2327672845782456e-6). The new bound accepts that drift and does not establish convergence. The change is unrelated to the Project API.

- **Old parameter histories** (G#1 "blocking", F#12): v0.7.4 and earlier v0.8 dev builds store `log(value)` for non-negative parameters, and `set_from_history` now reads them as values. No action: an edge case, and v0.8 is not required to load v0.7 results. The changelog states the change.
- **Overwriting an export** (G#2 "blocking"): the old export is removed before the new one is renamed into place, so a failed rename loses it. No action: an edge case; the new export stays in the temporary folder.
- **`project.optimize` writes `parameter_history.csv` by default** (F#6), because it inherits `verbose=True`. Decision 1 in `issues/project-api-implementation.md`; unchanged.
- **`Project.start` creates a missing folder** (F#7), so a typo starts a new project. Decision 7; unchanged.

## Deferred

| Finding | Reviewers | Checked | Note |
| --- | --- | --- | --- |
| Two exports to the same name from one process share the temporary folder | G#3, M#8 | code | Concerns threads only; the folder name contains the PID. |
| An objective error at the first evaluation loses its parameters | G#6 | code | SciPy first moves `x0` off a bound by 1e-10. The record shows the initial parameters and 0 evaluations. |
| `KeyboardInterrupt` during record initialization leaves a folder without `record.yml` | G#8 | code | The window lasts milliseconds, and the fit has not started. |
| Custom `parameters_format` or `scheme_plugin` saving options give exports that do not load | G#10 | reviewer | Predates the PR; serializer behavior. |
| A damaged original scheme file prevents export | G#11 | code | Requires the user to replace the file with invalid YAML after the fit. |
| A hand-edited `created` timestamp without time zone breaks `list_results` | G#13 | code | The sort runs outside the guarded read; one-line fix. |
| Export folders named `*.yml` or `*.yaml` cannot be loaded | G#14 | code | `load_result` treats the folder as a file. |
| `schema_version` of `export.yml` is not checked on reading | G | code | Records are checked. |
| `compare_results(result, record)` shows `converged: None -> True` | G, M#5 | code | Decision 5; the comparison test drops the row. |
| Damaged or newer-schema metadata gives raw ruamel, `KeyError` or `TypeError` errors in `recompute` and `compare_results`; listing reports a newer schema as damaged | M#6 | reviewer | Listing behaves as specified. |
| The "Optimization failed" warning points into `scheme.py` | M#3 | code | Introduced by this PR: `_run_optimization` adds a frame. `stacklevel=4` is correct for both `Scheme.optimize` and `Project.optimize`. Affects only the reported location. |
| Stale `record_id` after the record folder was deleted; `add_svd` not recorded; older dev builds reject `result.yml` with `optimizer_settings` | M#8 | reviewer, code for `add_svd` | Edge cases or outside the specification. |
| Jupyter detection through `JPY_SESSION_NAME` may work only for notebooks in the server root | F#5 | not verified | Falls back to `unknown`. Needs a live Jupyter session. |
| Nested lists are written as `-   - 0.5` | F#10 | reviewer | Valid YAML. |

## Verification

- The new and changed tests fail on the `ffa4377c` sources (the `glotaran/` changes stashed): 5 in the first pass, 11 test cases in the second. All pass with the fixes.
- Core tests, run from `temp/pyglotaran-staging-dev/pyglotaran` with the staging venv: 525 passed, 9 xfailed. `ffa4377c`: 521 passed, 9 xfailed.
- `uvx ruff@0.14.7 check glotaran tests` and `uvx ruff@0.14.7 format --check glotaran tests` pass. `pre-commit run --files <changed files>` passes all hooks, including mypy.
- Reproduction scripts (session scratchpad) on the fixed code: UTF-8 names round-trip; standard errors of the failed record are NaN; 3 evaluations in `Result`, `record.yml` and `export.yml` for both `verbose` values; `result.source_path` stays `None`, and the second export's `result.yml` has no `source_path`; `ftol=None` fits; saved parameters and cost equal SciPy's solution for both methods and every budget; the `.nc` files of a first and a second export hold no path attributes.
- First-pass validation rerun `20261004-230130` (fixes 1 to 6): 11/11 notebooks per branch; 8 PASS, 6 EXPECTED_DIFFERENCE; leaf table identical to the implementation rerun `20261004-181627`.
- Second-pass validation rerun `20261004-234112` (all ten fixes; `validation/runs/{main,staging}/20261004-234112`, `validation/comparisons/v07-v08-20261004-234112.{json,md}`): 11/11 notebooks per branch, 0 runner failures; 14 leaves with 8 PASS and 6 EXPECTED_DIFFERENCE, no REGRESSION, BASELINE_FAILURE or missing artifact. Validation tests: 66 passed, 1 skipped, 4 failed; the 4 are the `test_scale_list_migration.py` tests that also fail on `4c635ae6`. The staging examples are on `staging_rewrite` (`ddfa636`), so the rerun does not exercise the project API.

Fix 7 brings v0.8 closer to v0.7.4 in 12 of 14 leaves. Fitted-data normalized RMS against v0.7.4:

| Leaf | Status | Before fix 7 (`20261004-230130`) | After (`20261004-234112`) |
| --- | --- | --- | --- |
| `study_fluorescence` | PASS | 1.48e-9 | 3.25e-10 |
| `study_transient_absorption/target_analysis` | PASS | 4.90e-8 | 5.85e-10 |
| `study_transient_absorption/two_dataset_analysis` | EXPECTED_DIFFERENCE | 8.82e-6 | 8.82e-6 |
| `ex_spectral_constraints` (4 leaves) | PASS | 2.28e-8 | 1.0e-12 to 1.3e-11 |
| `ex_spectral_guidance` | EXPECTED_DIFFERENCE | 1.2572e-6 | 1.2578e-6 |
| `ex_two_datasets` | PASS | 1.63e-10 | 1.21e-10 |
| `ex_doas_beta/target_analysis` | PASS | 2.73e-9 | 3.25e-16 |
| `simultaneous_analysis_3d_disp` | EXPECTED_DIFFERENCE | 3.81e-12 | 3.94e-14 |
| `simultaneous_analysis_3d_nodisp` | EXPECTED_DIFFERENCE | 9.97e-9 | 4.19e-10 |
| `simultaneous_analysis_3d_weight` | EXPECTED_DIFFERENCE | 2.45e-5 | 1.61e-10 |
| `simultaneous_analysis_6d_disp` | EXPECTED_DIFFERENCE | 1.01e-8 | 4.78e-15 |

**Consequence for the validation contract.** `simultaneous_analysis_3d_weight` has a 3e-5 tolerance and the reason "weighted solver/scale convention leaves a small reproducible fit drift". The drift fell from 2.45e-5 to 1.61e-10, and the largest parameter difference from 2.6e-5 (`scale.3`) to 4.3e-9, when only the final evaluation point changed. The documented root cause therefore no longer holds: that drift was the final-point artifact. On the maintainer's decision the leaf uses the default 1e-6 tolerance and is a PASS, in `validation/scenarios.yml` and in the pyglotaran `validation` submodule (`cca4c5c`). The comparison of the same runs under the tightened contract, `validation/comparisons/v07-v08-20261004-234112-tightened.{json,md}`, gives 9 PASS and 5 EXPECTED_DIFFERENCE, with this leaf at 1.61e-10 against 1e-6. Workspace validation tests: 66 passed, 1 skipped, 4 failed (`test_scale_list_migration.py`, which belongs to the post-v0.8 scale_list work); submodule `semantic/tests`: 26 passed. `issues/weighted-scale-drift.md` records the revised root cause. `ex_spectral_guidance` is unchanged, so the 3e-6 bound is still needed there. The other four EXPECTED_DIFFERENCE leaves keep a `different` parameter status with value differences of 1e-8 or less, in line with their documented label and representation reason.

Not run: the runtime benchmark (fix 7 adds one parameter update per fit and no function evaluation), live VS Code and Jupyter sessions, the docs build.

## Commits

Not pushed. pyglotaran `staging_rebase_with_project`, on `ffa4377c`, one commit per fix with its tests:

| Fix | Commit | Subject |
| --- | --- | --- |
| 1 | `26f848f7` | 🩹 Read YAML files as UTF-8 |
| 2 | `a7df31d2` | 🩹 Record failed and interrupted fits without standard errors |
| 3 | `ea5b59e8` | 🩹 Report the completed evaluations of a failed optimization |
| 4 | `5e25f256` | 🩹 Keep Result.source_path unchanged when exporting |
| 5 | `e43f13a2` | 🩹 Accept None tolerances for the optimizer again |
| 6 | `f891a1fd` | 📚 Say that Project.start() uses the working directory |
| 7 | `d6d6fc5e` | 🩹 Report the optimizer's solution instead of the last evaluated point |
| 8 | `9f0679e4` | 🩹 Describe the original fit in export.yml of a recomputed result |
| 9 | `00baaacd` | 🩹 Write no path attributes into data files |
| 10 | `cf01270e` | 🩹 Clear the standard errors of parameters a fit does not estimate |
| contract | `917addbe` | 🚇 Update validation submodule: default tolerance for 3D weighted case |

The validation submodule commit is `cca4c5c` on `main` of `jsnel/pyglotaran-validation`.

## Copilot threads on the PR (2026-10-05)

Six unresolved Copilot threads at `917addbe`, checked against the code:

| Thread | Claim | Outcome |
| --- | --- | --- |
| `export.py:124` | A destination created during the export is deleted, also with `overwrite=False` | True at `778c2390`; fixed in `ffa4377c` (re-check that raises `FileExistsError`). |
| `optimization.py:200` | Evaluation count of a failed fit depends on `verbose` | Fixed in `ea5b59e8` (fix 3). |
| `record.py:325`, `export.py:107` | A scheme file with `data:` paths is copied verbatim, so recompute and `load_result` of an export fail once the data file moves | Reproduced. Fixed in `4244b79a`: such a scheme is written from memory, without the data paths; other scheme files are still copied verbatim, so their comments and layout are kept (maintainer's choice). |
| `export.py:96` | Overlapping exports to one name in one process share the temporary folder | Fixed in `adf36289`: the temporary folder name ends in a random uuid. `tempfile.mkdtemp` was not used because it creates the folder owner-only. |
| `project.py:276` | Comparing an export shows `converged: None` | Deferred, as in the deferred table above. |

A third Copilot review of `917addbe` added three threads:

| Thread | Claim | Outcome |
| --- | --- | --- |
| `export.py:104` | Same as `export.py:107` above | Fixed in `4244b79a`. |
| `recompute.py:134` | A recompute of an export of a recomputed result loses the original cost history | Fixed in `85113de1`: recompute of an export takes the original fit's id and cost history from the `recomputation` block of its `result.yml` when the export has no cost history file or no record id. |
| `export.py:159` | After recompute → export → recompute → export, the original record id is lost | Fixed in `85113de1`, as above. |

Core tests 528 passed, 9 xfailed; ruff and pre-commit pass; `4244b79a` and `adf36289` pass on their own. No validation rerun: the changed code runs only in `project.optimize`, `project.export` and `project.recompute`, which the validation notebooks do not call. Pushed to the PR branch: `917addbe..85113de1`. Every commit of the series passes ruff and the core tests on its own, checked in a separate worktree. The final commit gives the 525 passed and 9 xfailed of the working tree. In that worktree, five path tests fail on every commit, `ffa4377c` included, because the worktree lies next to pytest's temporary folder; they were deselected there and pass in the main checkout.
