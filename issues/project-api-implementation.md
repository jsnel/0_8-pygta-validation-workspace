# Result recording and export for v0.8: implementation

Status: implemented on staging `staging_rebase_with_project`, 14 local commits on `4c635ae6` (HEAD `778c2390`), not pushed. Example notebooks on `pyglotaran-examples` branch `staging_rewrite_with_project` (`351d5a7`, one commit on `staging_rewrite` `ddfa636`), not pushed. Specification: [project-api-proposal.md](project-api-proposal.md). The first implementation of the previous revision stays on `experimental/wip_first_attempt` (`87a591f9`) and was not used.

## Commits

| Commit | Content | Plan step |
| --- | --- | --- |
| `e31e60d0` | `Scheme.optimize` fits a deep copy of the scheme with deep copies of the data and stores a copy of the initial parameters | prerequisite 1 |
| `c9e037b9` | `OptimizerSettings` on `Result.optimizer_settings` and in `result.yml` | prerequisite 2 |
| `c38df397` | `weight` kept in `Result.input_data`; `fitted_data` of loaded results | prerequisite 4 |
| `1cbe8a0d` | original optimizer error raised when the evaluation after it fails again | prerequisite 5 |
| `440b6ce0` | cost history always, parameter history with `verbose=True`, in user coordinates | 7 |
| `9844143e` | data summary, comparison and `source_path` reference | 5 |
| `5cb303f9` | `Project.start` | 8 |
| `5d692b2d` | records written by `project.optimize`, source detection, failed and interrupted fits | 6, 9, 10 |
| `50cbe213` | parameter csv read with round-trip precision | needed for 11 |
| `04eee992` | `project.recompute`; statistics for dry runs | 11 |
| `1930888c` | `project.list_results`, `project.compare_results` | 12 |
| `aac7c6b9` | `project.export`; recompute and compare of exports | 13 |
| `96e463b9` | user guide page, getting started notebook, changelog | 15 |
| `778c2390` | `write_dict` writes lists of mappings as valid YAML | found in 15 |

Code: `glotaran/project/project.py` (the `Project` class, a thin layer), `record.py`, `data_summary.py`, `recompute.py`, `compare.py`, `export.py`. Not implemented, as specified: everything under "Not in v0.8", prerequisite 3, pyglotaran-extras plots (step 16).

## Evidence

- Core tests: 515 passed, 9 xfailed (baseline on `4c635ae6`: 456 passed, 9 xfailed). Ruff 0.14.7 check and format pass on `glotaran` and `tests`.
- Getting started notebook: `pytest --nbval docs/source/notebooks/getting_started` passes twice in a row (second run warns about the existing export and continues). Sphinx build without notebook execution: no warnings from the new page or modules.
- Validation rerun `20261004-181627` (`validation/runs/{main,staging}/20261004-181627`, `validation/comparisons/v07-v08-20261004-181627.json`): 11/11 notebooks per branch, 14 leaves, 8 PASS, 6 EXPECTED_DIFFERENCE, 0 REGRESSION, 0 BASELINE_FAILURE. Validation tests: 66 passed, 1 skipped, 4 failed; the same 4 fail on `4c635ae6` (`test_scale_list_migration.py`, scale_list features not on this branch).
- Unchanged notebooks: the staging examples run on `4c635ae6` (`validation/runs/staging/20261004-base-4c635ae6`, core imported from a `4c635ae6` worktree through `PYTHONPATH`) and on the branch (`20261004-181627`) saved identical results: 438 arrays, worst absolute difference 0.0, no file or variable added or missing. Both runs predate `778c2390`, which changes only the YAML layout of lists of mappings.
- Adopted examples: `ex_spectral_constraints` and `transient_absorption_target_analysis` executed twice in a row with nbclient on the branch.
- Recompute reproduces fitted data, residuals, element arrays and cost exactly for a scheme built in code and for a kinetic plus spectral (global) model, both reloaded from `scheme.yml`.
- Overhead (one thread, median of 5): sequential decay 2100x72, 3 nfev: `scheme.optimize` 0.147 s, `project.optimize` 0.223 s, recompute 0.064 s. `transient_absorption_target_analysis`, 10 nfev: 4.333 s, 4.415 s, recompute 0.227 s. Recording costs about 0.08 s per fit.

## Decisions where the specification was open

1. `project.optimize` keeps the defaults of `Scheme.optimize`, so `verbose=True` and `parameter_history.csv` is written unless `verbose=False`. The API sketch suggests no parameter history by default; that would need a different default for `verbose` in `project.optimize`.
2. `parameter_history.csv` keeps the existing `iteration` column: row 0 holds the initial values, row n the parameters of evaluation n, aligned with `evaluation` in `cost_history.csv`. Without `verbose` the in-memory history keeps only row 0, as before.
3. `record.yml` has `status` as a plain string and a separate `error: {type, message}` (null on success).
4. `optimized_parameters.csv` of a failed or interrupted fit is written when at least one evaluation completed. Otherwise the last evaluated parameters are the initial ones (also when the first evaluation raised), which `initial_parameters.csv` already holds. The summary of such a record holds the number of completed evaluations and the cost of the last one.
5. `converged` (SciPy's success flag) is kept on `Optimization.converged` and written to records and exports; `OptimizationInfo` and `result.yml` are unchanged. For a result without a record (`scheme.optimize`, `load_result`) it is unknown (`null`).
6. All paths in a record (`source`, `scheme_source`, `source_path`) are relative to the record folder where possible. An export holds file names only.
7. `Project.start` creates a missing project folder (with parents). `results=` may be absolute.
8. `list_results` filters `source`, `scheme_source` and `name` by contained text and `status` exactly. A record left at `running` is listed with status `running`; the documentation explains that such a record is incomplete.
9. `compare_results` returns a `FitComparison` (parameter differences and summary as DataFrames, scheme diff, data differences) that renders as markdown. The schemes are compared in one normalized YAML form, so a verbatim copied scheme file and a scheme dumped from memory compare equal. Columns are the record ids, or `a`/`b`.
10. The recomputed result: `Result.recomputation` is one optional dict field with `original_fit` and `reconstruction`; `initial_parameters` come from the record; the optimized parameters carry the recorded standard errors (read from the csv); `Result.record` refers to the record it was recomputed from, so its export carries the record metadata. Recompute from an export has no cost history.
11. Dry runs now report chi-square, reduced chi-square, RMSE and degrees of freedom of their one evaluation (`success` stays `False`). This changes `Scheme.optimize(dry_run=True)` for every caller.
12. `export` returns the export folder, also when an existing export was kept. It writes to a temporary folder and renames it when complete. `export.yml` holds the optimizer settings, data summary and fit summary, so that `recompute` and `compare_results` also accept an export folder. For a recomputed result the fit summary is that of the original fit, with `recomputed_from` (review follow-up).
13. Difference messages use `->`: printing `→` fails in a Windows console with code page cp1252.
14. The record's environment lists the distributions that provide `glotaran.plugins.*` entry points, other than pyglotaran.
15. Errors: changed data raise `GlotaranUserError`; an unknown record or export `FileNotFoundError`; `overwrite=True` over a folder without `export.yml` `FileExistsError`.

## Deviation from the specification

The specification proposes a serialization-context flag (`force_write_input_data`) so that export writes the input data even with `input_data` in the data filter. Export instead removes `input_data` from the data filter it passes to `Result.save`. That filter entry only selects the branch that writes a reference to the source file, so the effect is the same without a change to the serializers.

## Fixes beyond the prerequisites

- Loaded results returned an empty dataset as `fitted_data` (`c38df397`).
- `ParameterHistory` stored `log(value)` of non-negative parameters (`440b6ce0`).
- Parameter csv files lost the last bit on reading; a recompute from `optimized_parameters.csv` then differed by about 1e-13 (`50cbe213`).
- `Result.save` set `result.scheme.source_path` to the saved file, so a second save after moving the first folder failed; the YAML `save_scheme` failed when the scheme's source file was gone (`aac7c6b9`).
- `write_dict` wrote lists of mappings as invalid YAML, so schemes built in code with penalties, relations or constraints could not be loaded after `Result.save` (`778c2390`).
- `docs/remove_notebook_written_data.py`, run by the docs build, deleted `my_project/*.gta`; it now keeps the committed `project.gta` and removes `my_project/exports` (`96e463b9`).

## Observation, changed in the review follow-up

A staging fit took `chi_square`, reduced chi-square and RMSE from SciPy's residual at its solution `x`, but cost, optimized parameters and result arrays from the last evaluated point, often a finite-difference Jacobian step. v0.7.4 resets the parameters to `ls_result.x` before building the result. Since the review follow-up, staging does the same (see below).

## Open points

- Source detection was unit-tested for VS Code (`__vsc_ipynb_file__`), Jupyter (`JPY_SESSION_NAME`), scripts and the `unknown` fallback, but not checked in real VS Code and Jupyter sessions. Under nbclient and nbval it is `unknown`, as specified.
- Not measured: recompute time on the PFID case study; recompute across machines and library versions.
- Journeys of step 17 covered by tests: recompute after a data change, two record collections, a simulated interrupt, a record left at `running`, working directory changed after `start`, an export loaded after the data file moved, a v0.7 `project.gta` with 0.7 results, a re-run with an existing export. Not exercised: a real kernel kill and a notebook in a project subfolder (`Project.start("..")`).
- If the examples branch is pinned for validation: the adopted notebooks write `results/` and `exports/` into the examples checkout (ignored by git). `validation/run_examples.py` hashes all files of the examples tree, so `examples_tree_sha256` would change from run to run.
- The fit-runtime benchmark handoff was not run. `Scheme.optimize` now deep-copies scheme and data once per fit and computes one dot product per evaluation; the base-vs-branch run showed no change in saved results.

## Review follow-up (2026-10-04)

Three reviews of PR #1615 at `ffa4377c` (`reviews/PR-1615-*.md`), triaged in [reviews/PR-1615-meta-review.md](../reviews/PR-1615-meta-review.md). Fixed on `staging_rebase_with_project` in `26f848f7`..`cf01270e` (one commit per fix, not pushed), each with a test that fails on `ffa4377c`:

- YAML read as UTF-8 (`load_dict`); before, a non-ASCII record name was garbled on Windows or made the record unreadable.
- Failed and interrupted records save the last evaluated parameters without standard errors.
- `number_of_function_evaluations` of a failed fit is the number of completed evaluations, independent of `verbose`.
- `export` saves a copy of the result without `source_path`, so `Result.source_path` no longer points into the removed temporary folder and `result.yml` of an export holds no local path.
- `OptimizerSettings` accepts `None` tolerances again (a regression of `c9e037b9` for `Scheme.optimize`).
- Getting started: `Project.start()` uses the working directory.

Second pass, on the maintainer's decision:

- `Optimization.run` sets the parameters to SciPy's solution `x` before the final evaluation, so optimized parameters, cost, result arrays, chi-square and standard errors describe one point. Before, the saved parameters differed from `x` by about 1.5e-7 relative with Trust Region Reflection and by up to 1.2e-3 with Levenberg-Marquardt stopped by its evaluation budget (sequential decay).
- `export.yml` of a recomputed result holds the summary of the original fit and `recomputed_from: <record id>` (decision 12); before, it held the dry-run summary.
- `save_dataset` no longer writes the `source_path` and `io_plugin_name` attributes into data files; before, every export of data loaded with `load_dataset` held the absolute raw-file path in `input_data.nc`.
- After a successful fit, fixed and expression parameters have no standard error; before, they kept the one of the initial parameters, as in v0.7.4.

Core tests 525 passed, 9 xfailed; ruff and pre-commit pass. Validation reruns: `20261004-230130` after the first pass (leaf table identical to `20261004-181627`) and `20261004-234112` after the second: 11/11 notebooks per branch, 8 PASS, 6 EXPECTED_DIFFERENCE, no REGRESSION. Reporting SciPy's solution lowers the fitted-data normalized RMS against v0.7.4 in 12 of 14 leaves; `simultaneous_analysis_3d_weight` falls from 2.45e-5 to 1.61e-10, so the documented root cause of its 3e-5 tolerance no longer holds. The leaf now uses the default 1e-6 tolerance as a PASS (`validation/scenarios.yml`; validation submodule `cca4c5c`, pinned by `917addbe`); under the tightened contract the same runs give 9 PASS and 5 EXPECTED_DIFFERENCE (`v07-v08-20261004-234112-tightened`). The remaining findings are listed in the meta-review.

## Environment changes

- `temp/pyglotaran-staging-dev/.venv`: `uv sync --group test` from the `pyglotaran` member added the test dependencies and removed packages of the parent project; `uv sync --frozen --inexact` from the parent restored them (papermill, tenacity, tqdm, yaargh), and `validation/notebook_compat` was reinstalled as in `validation/AGENT_RERUN.md`. Before, `import glotaran` failed in this environment because of a stale editable install (`glotaran.builtin.io.hamamatsu.img_file_reader`).
- That `uv sync` also rewrote `temp/pyglotaran-staging-dev/uv.lock`; the change is in `stash@{0}` of `temp/pyglotaran-staging-dev` and can be dropped.
