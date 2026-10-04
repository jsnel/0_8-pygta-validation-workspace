Review of PR #1615 (`staging_rebase_with_project` at `ffa4377c` against `staging_rebased` at `4c635ae6`). The implementation follows the specification closely. No blocking defect. Three findings should be fixed before merge, and one bundled change needs a decision.

## Findings

**1. Should fix. Optimized parameters, cost and result arrays come from a finite-difference probe point, while chi-square and standard errors come from SciPy's solution.** [optimization.py:159-171](temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/optimization.py#L159-L171). After `least_squares` returns, the final evaluation runs at whatever point `objective_function` saw last. For `trf` that is the last Jacobian probe `x + h·e_n`. Reproduced on the sequential decay: the last free parameter differs from `ls_result.x` by 1.49e-7 relative, and `2·cost` differs from `chi_square` by 3.5e-11 relative. v0.7.4 resets the parameters to `ls_result.x` first ([optimizer.py:312](temp/pyglotaran-main-dev/pyglotaran/glotaran/optimization/optimizer.py#L312)). This predates the PR, and the PR description discloses it as an observation, but the PR now persists the perturbed values in every `optimized_parameters.csv` and `record.yml`, and `test_recompute_reproduces_the_fit` codifies the inconsistency. Fix: on success call `set_from_label_and_value_arrays(labels, ls_result.x)` before the final evaluation. Then cost, chi-square, arrays, parameters and standard errors describe one point, and recompute reproduces chi-square too. The change is within validation tolerance but needs a validation rerun.

**2. Should fix. A failed fit's `number_of_function_evaluations` depends on `verbose`.** [info.py:177-179](temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/info.py#L177-L179) uses `parameter_history.number_of_records`, which now grows per evaluation only with `verbose=True`. Reproduced with `raise_exception=False` and three evaluations before the optimizer error: `verbose=False` reports 1, `verbose=True` reports 4. The record is right because `FitRecord.finish` uses `len(cost_history)`; the in-memory `Result` is wrong. Fix: pass `len(self.cost_history)` into `from_least_squares_result`.

**3. Should fix. A failed or interrupted record keeps stale standard errors.** [record.py:368](temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/record.py#L368) writes `optimization.parameters`, which are resolved from the initial parameters including their `standard_error`. Reproduced: a fit seeded with `first.optimized_parameters` that then fails writes `optimized_parameters.csv` with the previous fit's standard errors next to the last evaluated values. The specification says "without standard errors", and `recompute` later copies them into `recomputation.original_fit.standard_errors`. Fix: reset `standard_error` to NaN on a copy before saving a non-success record.

**4. Question. The validation submodule bump is unrelated to the feature.** Commit `2d075c21` moves `validation` to `c15b2b9c`, which relaxes `ex_spectral_guidance` from 2e-6 to 3e-6 citing a CI value of 2.23e-6. The validation README says not to increase thresholds without fresh paired evidence, and the workspace issue brief has no entry for the CI number. Was the CI drift observed on base `staging_rebased` as well? If it only appears on this branch, the PR changes a fit result. The PR's own local comparison shows 438 identical arrays, which points to CI environment drift, but this should be stated in the PR.

**5. Question. Jupyter notebook detection probably only works for notebooks in the server root.** [record.py:74](temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/record.py#L74) resolves `JPY_SESSION_NAME` against the working directory. jupyter_server sets it to the path relative to the server root, while the kernel's working directory is the notebook's folder. A notebook in a subfolder then fails `is_file()` and records `unknown`, which is the safe fallback. The user guide claims detection "in VS Code, Jupyter and for scripts". Not verified in a live session; the PR says the same.

**6. Question. `project.optimize` writes `parameter_history.csv` by default.** [project.py:141](temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/project.py#L141) inherits `verbose=True`. The specification's API sketch shows `verbose=True` as the opt-in. Also, every `scheme.optimize` call with the default `verbose` now keeps one history row per evaluation in memory and in `Result.save`. Disclosed in the PR; a maintainer decision.

**7. Minor. Record parameters and `Project.start`.** `Project.start(folder)` creates `folder` with parents ([project.py:96](temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/project.py#L96)), so a typo silently creates a new project with its own `project.gta`. The specification says "opens"; the docstring says "created if it does not exist". Worth confirming.

**8. Minor. `export.yml` of a recomputed result mixes two fits.** [export.py:172](temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/export.py#L172): `summary` describes the recompute (`termination_reason: Dry run.`, one evaluation) while `converged` is copied from the original record.

**9. Minor. Stale comment.** [export.py:100](temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/export.py#L100) says saving sets the scheme source path; `serialize_scheme` now passes `update_source_path=False`.

**10. Minor. YAML layout of nested lists.** The indent change in [utils.py:44](temp/pyglotaran-staging-dev/pyglotaran/glotaran/builtin/io/yml/utils.py#L44) fixes lists of mappings but renders a list inside a list as `-   - 0.5`. Valid YAML, cosmetic, only affects schemes with nested lists.

**11. Minor. Getting started wording.** The notebook says `Project.start()` "uses the folder of the notebook"; the code uses the working directory, as the user guide states correctly.

**12. Minor. Parameter history files from earlier v0.8 dev builds.** They hold `log(value)` for non-negative parameters; `Parameters.set_from_history` now reads them as user values. Only dev builds are affected; the changelog entry covers it.

Checked and found sound: record claiming with exclusive `mkdir` and concurrent processes, atomic `record.yml` replacement, failed and interrupted fits recorded and re-raised, record-write failures as warnings, damaged and hand-edited records skipped in listing, export written to a temporary folder with a race check, input data always written as data, missing source files, `weight` round-trip, `scheme.yml` excludes data, relative paths on Windows, `dry_run` and `scheme.optimize` writing nothing. The Windows overwrite case with a loaded result holding the old export open did not reproduce.

## Specification coverage, commands, scope

Not implemented or deviating: the `force_write_input_data` serialization flag is replaced by removing `input_data` from the data filter, with the same effect, and the PR says so. Not measured: recompute time and recording overhead on the PFID case (plan step 14). Not exercised: a real kernel kill and `Project.start("..")` from a subfolder (step 17). pyglotaran-extras plots are out of this repository. Everything else in the specification is present.

Commands run, from the pyglotaran folder with the staging venv:

| Command | Result |
| --- | --- |
| `python -m pytest -q -p no:cacheprovider tests` | all passed, 9 xfailed, exit 0 |
| `uvx ruff@0.14.7 check glotaran tests` | All checks passed |
| `uvx ruff@0.14.7 format --check glotaran tests` | 208 files already formatted |
| `pre-commit run --all-files` | all hooks passed, including mypy |
| five scratch scripts in the session scratchpad | findings 1, 2, 3 reproduced; overwrite case not reproduced |

The working tree is at `ffa4377c` and clean. One stray one-byte file remains in my session temp folder under a mistyped path; the safety hook blocked its deletion.

Not reviewed: live VS Code and Jupyter sessions, memory and time of the per-fit deep copies at PFID scale, the docs build, the examples branch, the validation rerun evidence, and POSIX behaviour.