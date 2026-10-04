# Result recording and export for v0.8: specification

Status: agreed specification, revised 2026-10-04 after the [review](project-api-proposal-review.md); see [Changes since 2026-10-04](#changes-since-2026-10-04). Nothing is implemented. Staging revision: `a9f62fa2` (`staging_rebased`); code references re-checked at `6aa9d918`, which changes only `.github/CODEOWNERS`.

The 2026-10-03 version of this brief compared three designs (the v0.7 `Project`, a manifest with a lock file, an append-only fit journal). This specification replaces it. It was agreed with the maintainer after two independent designs, written from the staging code alone, converged on per-fit records with recompute (see [Background](#background)).

## Purpose

Every fit attempt is recorded automatically, with the minimum information needed to recompute its results. A full export, which shows exactly what the user saw, is always a deliberate action.

Requirements:

1. Record enough to recompute the results of every fit attempt from its input data, and store as little of the computable results as possible.
2. Recording the parameter history within a fit is optional.
3. A set of records contains enough information to visualize the fit progression: across attempts, within one fit, and as a lineage tree.
4. Exports include the referenced source files, the fitted input data and the full result arrays by default; each can be left out.
5. Preprocessing is described in the notebook or script. pyglotaran does not track it.
6. A project folder can carry a human-written description of the project and its data for research data management (RDM); exports include it.

Non-goals: tracking preprocessing; bitwise reproducibility across machines or library versions; automatic deletion of records; plotting in core; migrating v0.7 `Project` folders.

## Behaviour

### Project

For RDM, the work is divided over three places: a person writes the project description once (`project.gta`), pyglotaran records provenance automatically for every fit (records), and the user makes a package deliberately per result (exports).

- A project is a folder whose root contains a `project.gta` file. The file is optional, and pyglotaran never writes to it.
- pyglotaran looks for `project.gta` in the working directory and its parents; the nearest one marks the project root. Records then go to `<root>/results/` and exports to `<root>/exports/`; without a project, to `<cwd>/results/` and `<cwd>/exports/`. Explicit settings (see [Recording](#recording) and [Export](#export)) take precedence.
- `project.gta` is a human-readable YAML file describing the project and its data. Every field is optional. pyglotaran checks only that the file exists, and `export` copies it verbatim into every export. Recommended fields, named after the DataCite metadata schema where it has an equivalent (the schema will be refined later):

  ```yaml
  title: Carotenoid dynamics in LH2 complexes
  description: >
    Global and target analysis of ...
  data_description: >
    Transient absorption, 400-700 nm, pump 800 nm; samples ...; instrument ...
  creators:
    - name: ...
      orcid: 0000-0000-0000-0000
      affiliation: ...
  keywords: [transient absorption, target analysis]
  license: CC-BY-4.0
  related_identifiers:
    - doi: 10.xxxx/...        # publication, dataset, data management plan
  funding: ...
  ```

- A JSON file is valid YAML in practice, so a JSON `project.gta` written by another tool works as well. A v0.7 `project.gta` (`version: 0.7.x`) also marks a project root.
- A GUI or RDM platform defines a project by creating `project.gta`; results and exports then live in known folders under it.
- Records and exports are self-contained, so a project folder that is copied or moved keeps working.

### Recording

- A record is written for every `Scheme.optimize` call once `Optimization` has been constructed. This includes fits that fail inside the optimizer or during result construction, and interrupted fits (`KeyboardInterrupt`). Calls that fail earlier (model issues, a missing dataset label) are not recorded. `optimize(dry_run=True)` and `recompute` write no record.
- Records go to `<base folder>/<NNN>/`. The default base folder is `<root>/results/` in a project (see [Project](#project)) and `<cwd>/results/` otherwise. `NNN` is the largest existing number in the base folder plus one, starting at `001`, zero-padded to 3 digits and continuing with 4 digits after `999` (`1000`, `1001`, ...). Only folders named by a number count. The number of a deleted last record is reused; lineage uses the `uid`, so parent links stay correct.
- Folder creation is atomic. The writer creates the folder with an exclusive `mkdir` and retries with the next number if it already exists, so two notebooks writing to the same base folder at the same time get different numbers.
- The default base folder can be overridden in three ways, with the first that is set taking precedence:
  1. per call: `scheme.optimize(..., output_folder="my_results")`;
  2. per session: a pyglotaran setting set once in the notebook;
  3. environment variable: `GLOTARAN_RESULTS_FOLDER=<path>`.
- The same three mechanisms switch recording off (for test suites, CI and batch jobs) and switch the parameter history on, with the same precedence. The environment variables are `GLOTARAN_RECORD=0` and `GLOTARAN_RECORD_PARAMETER_HISTORY=1`. `GLOTARAN_RECORD=0` overrides every other setting, so CI and documentation builds never write records.
- `output_folder=` switches recording on for that call, also when the session setting has switched it off; the environment "off" still wins. `record=False` together with `output_folder=` raises `ValueError`.
- The base folder is resolved once per call, to an absolute path.
- Several notebooks may share one base folder. Each record names the notebook or script that produced it, so their records can be told apart. Where detection fails (nbclient, papermill, nbsphinx, Colab, Spyder, plain IPython), `source` is `unknown`; a session setting overrides the detected value.
- Write order: once `Optimization` exists, the writer creates the folder and writes `record.yml` with status `running`, `scheme.yml` and `initial_parameters.csv`. After the fit it writes the remaining files and replaces `record.yml` atomically (temporary file, then rename). A record left at `running` belongs to a fit that never returned to Python, for example after a kernel death or an out-of-memory kill. Folder numbers reflect the order in which fits started.
- A failure to write the record (permissions, full disk, unavailable drive, serialization error) gives a warning; `optimize` still returns the result. An error while recording never replaces the exception of a failed fit. An interrupted fit is recorded and the `KeyboardInterrupt` is re-raised.
- With `verbose=True`, `optimize` prints the record folder. `Result.record` holds its absolute path, `id` and `uid`.

### Contents of a record

```text
results/001/
  record.yml                # metadata, see below
  scheme.yml                # full scheme, for every attempt (no deduplication)
  initial_parameters.csv
  optimized_parameters.csv  # see below; absent if no point was evaluated
  cost_history.csv          # cost per function evaluation
  parameter_history.csv     # only when the parameter history is switched on
```

- Parameter files are written with `save_parameters`, which writes every `Parameter` field: value, standard error, expression, minimum, maximum, non-negative, vary.
- `optimized_parameters.csv` holds the optimized values and standard errors for a successful fit. For a failed or interrupted fit it holds the last evaluated parameters, without standard errors; after a crash in the objective these are the parameters that raised.
- `cost_history.csv` holds the cost of every function evaluation in call order, including finite-difference Jacobian evaluations and rejected trial steps. It is collected in `objective_function`, so it is filled for every method and for `verbose=False`. Its row count differs from `nfev`, which SciPy counts without the Jacobian evaluations.
- `parameter_history.csv` has one row per function evaluation, aligned with `cost_history.csv` by evaluation number. Values are in user coordinates (staging's `ParameterHistory` stores `log(value)` for non-negative parameters, `glotaran/parameter/parameter.py:268-271`).

`record.yml` holds:

| Field | Content |
| --- | --- |
| `schema_version` | Version of the record format (`1`). Readers reject a newer major version, ignore unknown fields and treat missing optional fields as empty |
| `id` | Folder number (`001`) |
| `uid` | Unique id of the attempt, used for lineage |
| `created` | Timestamp |
| `status` | `running`, `success`, `failed` or `interrupted`, with the error type and message for `failed` and `interrupted` |
| `source` | Path and file name of the notebook or script, relative to the record folder where possible; `unknown` if not detected |
| `scheme_source` | Path of the scheme file (`Scheme.source_path`); empty for a scheme built in code |
| `name` | Optional label from `optimize(..., name=...)` |
| `environment` | Versions of pyglotaran, Python, numpy, scipy, xarray and the installed glotaran plugin packages |
| `parent` | `id` and `uid` of the parent attempt (see [Lineage](#lineage)), or empty |
| `parent_data_changed` | Labels of the datasets whose data summary differs from the parent's (missing or new labels included); empty when there is no parent or nothing changed; `unknown` when the parent's record cannot be found |
| `optimizer` | Settings passed to `optimize`: method, `ftol`, `gtol`, `xtol`, maximum number of function evaluations |
| `data` | Per dataset: the data summary, see below |
| `summary` | Cost, chi-square, reduced chi-square, RMSE, degrees of freedom, number of function evaluations, termination reason, `converged`, free parameter labels, and per dataset the RMSE and weighted RMSE |

`converged` is SciPy's success flag. Staging's `OptimizationInfo.success` is `True` whenever `least_squares` returns (`glotaran/optimization/info.py:149`), also when the evaluation budget ran out; v0.7.4 behaves the same. `status` describes whether the call completed, `converged` whether the optimizer met its tolerances.

Empty fields per status:

| Status | Empty |
| --- | --- |
| `running` | `summary`; files other than `scheme.yml` and `initial_parameters.csv` |
| `failed`, `interrupted` | all of `summary` except the number of function evaluations and, where it could be computed, the cost |

The data summary holds, per dataset, the shape by dimension name and `min`, `max`, `mean` and `rms` of each coordinate of the model and global dimensions and of the variables the optimizer reads: `data` and, if present, `weight`. Weights defined in the scheme are in `scheme.yml`. Statistics are computed in float64 and do not depend on dimension order, dtype or byte order.

```yaml
data:
  ta:
    shape: {time: 500, spectral: 72}
    time:     {min: -1.0, max: 10.0, mean: 4.5, rms: 5.8}
    spectral: {min: 400.0, max: 700.0, mean: 550.0, rms: 556.0}
    data:     {min: ..., max: ..., mean: ..., rms: ...}
```

Records contain no result arrays and no data. Recomputing an attempt therefore requires that its input data was preserved or can be regenerated (see [Recompute](#recompute)). If dataset labels repeat across experiments, staging merges results by label (`glotaran/optimization/optimization.py:142`); the writer records the fit and warns that per-dataset entries are ambiguous.

### Lineage

`Result.optimized_parameters` carries the `uid` of the attempt that produced it. When those parameters (or a `Parameters` object derived from them) are passed to a later `optimize` call, that call records the attempt as its parent. Parameters that went through a file and were loaded again start a new lineage.

- The `uid` is an attribute of the `Parameters` object. Copies keep it, and in-memory edits (values, `vary`, bounds, added or removed parameters) leave it in place. It is not written to parameter files. A `Parameters` object built in code carries no `uid`.
- An attempt run with recording off gets no `uid`; its parameters start a new lineage.
- To continue a lineage after a restart, or from parameters loaded from a file, pass the parent explicitly: `optimize(..., parent="017")`, with a record id, a `uid` or a record path. An id or `uid` is looked up in the base folder of the call; a parent in another base folder is named by its record path. The record stores the parent's `id` and `uid`. An explicit `parent=` takes precedence over the `uid` carried by the parameters. Parameter files stay lineage-free.
- Lineage is resolved by `uid`. Copies of a record folder have the same `uid` and count as the same attempt.

Replacing the data in an existing notebook (for example with better measurements) is supported. Fitting never compares data with earlier attempts, so a fit on new data is not blocked. The writer compares the data summaries with those in the parent's `record.yml`, found by `uid` in the base folder, and lists the datasets that differ in `parent_data_changed`. Progression plots and `compare_results` use it to mark the data change. Whether a parameter jump comes from that change or from a model change is for the user to judge with `compare_results`.

### Recompute

The user re-runs the notebook to regenerate the input data, then recomputes a record: one function evaluation at the recorded optimized parameters, with the recorded scheme and settings. On the three cases measured (see [Evidence](#evidence)) this reproduced the fitted data and element arrays exactly, in the same process as the fit.

- Records contain no data, so an old attempt can be recomputed only if its input data was preserved or can be regenerated. Re-running a whole notebook re-runs every fit in it and writes a new record for each; a PFID fit takes 137 s on staging. The user guide recommends keeping preprocessing in a function, notebook or script that produces the input data without fitting, and keeping the input data of attempts that matter (an export contains it).
- `recompute` accepts a record id (looked up in the base folder), a record path, an export path or `Result.record`.
- Recompute compares the data summary of each supplied dataset with the recorded one. Differences up to `1e-6` times the RMS of the array count as equal, so bit-level differences between machines or numpy versions pass. A larger difference raises an error that names the dataset and says what changed and by how much (for example `ta: time max 10.0 → 8.0; data rms +0.4 %`). An explicit override (`allow_data_mismatch=True`) recomputes anyway; the recomputed result then lists the differences. A change that leaves every statistic equal, such as permuted values, is not detected; the drift check shows its effect on cost and RMSE.
- Recompute computes chi-square, reduced chi-square, RMSE and degrees of freedom from the one evaluation. Staging's `dry_run` leaves them empty and reports `success: False`, `termination_reason: "Dry run."` (`info.py:149`, `glotaran/optimization/optimization.py:172`).
- Recomputed cost and per-dataset RMSE (weighted and unweighted) are compared with the recorded values. Above a relative difference of `1e-6` a warning lists each value with its relative difference. The tolerance is provisional until recompute has been measured across machines and library versions. A recorded or recomputed value that is NaN or infinite is reported as not comparable. The comparison is attached to the recomputed result in both cases.
- The drift check measures the fit. A change in the decomposition (element arrays, CLPs) that leaves the fitted data unchanged is not detected, because records hold no arrays.
- The recomputed `Result` holds two blocks of information, written by `export` and read by `load_result`:
  - original fit: the record's `id` and `uid`, summary, standard errors and cost history;
  - reconstruction: time, environment, data differences (with `allow_data_mismatch=True`) and the drift comparison.
- The Jacobian and covariance matrix of the original fit cannot be recovered; recompute does not recompute the Jacobian. `Result.save` writes neither today (`info.py:124-126`), so an export lacks nothing it would otherwise contain.
- The recomputed `Result.optimized_parameters` carries the original attempt's `uid`, so a fit seeded from it links to that attempt.
- The recomputed `Result` is an in-memory object like any other, and can be exported.

### Export

- A full export is always a deliberate call, and always starts from an in-memory `Result`, so it contains exactly what the user saw at that moment. To export an older attempt, the user recomputes it first.
- The user names the export: `export(result, name="best_result")` writes `exports/best_result/`. Without a name it writes `exports/last_result/`. A relative name resolves under `<root>/exports/` in a project and `<cwd>/exports/` otherwise; an absolute name is used as given.
- If the folder exists, `export` raises an error, unless `overwrite=True` (default `False`). Overwrite replaces the whole folder, and only a folder that contains an export (`export.yml`).
- An export is self-contained: a folder that can be published as is and contains everything except the notebook or script. By default it contains:
  - metadata (`export.yml`), the scheme and the parameters;
  - the fitted input data as passed to `optimize`, including `weight`;
  - the full result arrays (what `Result.save` with default options writes: fitted data, residuals, element datasets, activations, fit decomposition);
  - the referenced source files: the files named by the datasets' `source_path` attributes.
- The last three can be left out with `input_data=False`, `arrays=False` and `source_files=False`. An export with input data loads with `load_result` without the original files. An export without input data does not load with `load_result` (`"Input data cannot be None."`, `glotaran/optimization/objective.py:316`); it can be recomputed with `recompute(path, datasets=...)`.
- Referenced source files: `source_path` does not reliably identify the source. In-memory data gets a made-up `dataset_<n>.nc` (`glotaran/utils/io.py:62`), the attribute can name an intermediate file, data combined from several files names at most one of them, and the file may have changed since the fit. Export copies the current contents of each named file into `source_files/<dataset label>/`. A relative `source_path` is resolved against the working directory at export time. A file that does not exist gives a warning and is listed in `export.yml` as missing.
- An export contains the same metadata as a record (`source`, `scheme_source`, `name`, `environment`, and the `id`/`uid` of the attempt it came from) and, for a recomputed result, the original-fit and reconstruction information. `source` holds the file name only, so a published export contains no local paths.
- Inside a project, the export contains a verbatim copy of `project.gta`, so a published export carries the project description.
- If `result.optimized_parameters` was changed in place after the fit, export writes the current values, warns, and lists the changed labels in `export.yml`. `Result` keeps the values from the fit for this comparison.

### Listing and comparison (core)

- `list_results(folder)` lists the records in one base folder, given as a path (absolute or relative) or, by default, the base folder resolved as for `optimize`. The table shows `id`, `created`, `source`, `name`, `scheme_source`, `status`, `parent`, shape and data RMS per dataset, cost, RMSE, number of function evaluations. A change in the shape or RMS columns shows where the data was replaced.
- Only folders with a `record.yml` are listed, so v0.7 `Project` output in the same folder is ignored. Rows are sorted by number (`999` before `1000`). The listing filters by source, scheme file, name and status.
- Records left at `running` are listed as incomplete. A damaged `record.yml` is skipped with a warning.
- `parent` is shown by id, and marked when the record with that id now has a different `uid` (a reused number) or is missing.
- Compare two records or results, given by id, path or `Result`: parameter table diff over all parameter fields (value, standard error, expression, bounds, non-negative, vary), summary statistics including weighted and unweighted RMSE per dataset, scheme text diff, and the data summary diff per dataset (what changed and by how much). Changes to weights, penalties, scales and constraints appear in the scheme diff or the data summary diff.

### pyglotaran-extras

Plotting of fit progression (across attempts, within one fit, lineage tree) and additional analysis such as fit-landscape visualization.

## API sketch

Names are provisional.

```python
from glotaran.io import load_parameters, load_scheme

scheme = load_scheme("models/scheme.yml")
parameters = load_parameters("models/parameters.yml")

result = scheme.optimize(parameters, datasets={"ta": ta})             # records results/001
result.record                                                         # path, id, uid
result2 = scheme.optimize(result.optimized_parameters, datasets={"ta": ta})
                                                                      # results/002, parent 001
scheme.optimize(load_parameters("fit2.csv"), datasets={"ta": ta}, parent="002")
                                                                      # results/003, parent 002
scheme.optimize(parameters, datasets={"ta": ta}, name="target model B")
scheme.optimize(parameters, datasets={"ta": ta}, record=False)        # nothing recorded
scheme.optimize(parameters, datasets={"ta": ta}, record_parameter_history=True)

from glotaran.project import compare_results, export, list_results, recompute

list_results()                     # table of <root>/results (or <cwd>/results)
list_results("D:/archive/lycopene/results")
compare_results("001", "002")
result = recompute("002", datasets={"ta": ta})     # raises if the data summary differs
result = recompute("002", datasets={"ta": ta_new}, allow_data_mismatch=True)
export(result)                                      # exports/last_result
export(result, name="paper_fig3", source_files=False)
export(result, name="paper_fig3", overwrite=True)  # replaces exports/paper_fig3
```

## Assumptions confirmed with the maintainer

- Data check (revised 2026-10-04, replaces the data hash): a summary of the input data as passed to `optimize` (shape; `min`, `max`, `mean`, `rms` of coordinates, `data` and `weight`) is stored per dataset. A summary that differs beyond tolerance raises an error on recompute that names what changed, unless the user explicitly overrides it. Nothing is hashed.
- Reproducibility claim: input data + notebook + the recorded environment reproduce the results within the drift tolerance.
- The scheme is stored in full with every attempt.
- Nothing is deleted automatically.
- Export of referenced source files copies the files named by `source_path`. Because `isel` and arithmetic keep that attribute, the source file can differ from the fitted data; for this export that is intended.
- Project (2026-10-04): a folder whose root holds an optional `project.gta`. Its presence sets the default location of records and exports; `export` copies it verbatim. The recommended fields will be refined later.
- Decisions of 2026-10-04 (review):
  - Records contain no input data. An old attempt can be recomputed only if the user preserved its input data.
  - Lineage across restarts uses an explicit `optimize(..., parent="017")` (record id or `uid`). Parameter files stay lineage-free.
  - Calls that fail before `Optimization` has been constructed are not recorded.
  - Per call > session > environment for the folder and the parameter history. An environment variable that disables recording overrides every other setting.

## Prerequisites in staging

These are bugs today, independent of this feature, and the feature depends on them:

1. **`Scheme.optimize` shares objects with its inputs.** `result.scheme is scheme` and `result.initial_parameters is parameters` are both `True`, and `_load_data` writes the data into the scheme in place (`glotaran/project/scheme.py:52-59`, `:110-116`). The result also shares the input arrays: `create_result_dataset` makes a shallow xarray copy (`glotaran/optimization/objective.py:617`), and `fitted_data` is computed on access as `input_data - residuals` (`objective.py:199`). A later fit, a scheme edit or an in-place change of the caller's data changes earlier `Result` objects, and so would change what a record or an export contains.
2. **Optimizer settings are not persisted.** `ftol`, `gtol`, `xtol`, `optimization_method` and `maximum_number_function_evaluations` are arguments of `Scheme.optimize` and are stored nowhere (`glotaran/project/scheme.py:68-103`).
3. **Stale `source_path` in `Result.save`** (does not block this feature, but affects current users). A fit on `raw.isel(time=slice(0, 500)) * 1000`, saved with `SAVING_OPTIONS_MINIMAL`, writes `input_data: ../raw.nc`; reloading gives input shape (2100, 72) instead of the fitted (500, 72). In-memory data without a file gets a made-up `source_path` (`glotaran/utils/io.py:61-62`).
4. **`Result.input_data` drops `weight`.** The optimization result stores `input_data=result_dataset.data`, the signal only (`objective.py:703`, `:781`, `:955`). A `weight` variable of the input dataset is lost, so an export cannot contain the input data as passed to `optimize`.
5. **A failed fit can raise again after the optimizer exception.** After an exception in `least_squares`, staging evaluates the objective at the last evaluated parameters outside the `except` block (`glotaran/optimization/optimization.py:143`). If the exception came from the objective, this evaluation raises again, regardless of `raise_exception`.

## Implementation plan

Each step is a separate, tested commit.

1. Stop `Scheme.optimize` from sharing objects with its inputs: copy the parameters, snapshot the scheme and copy the input arrays. Test that a later fit, a scheme edit and an in-place change of the caller's data each leave an earlier `Result` unchanged.
2. Store optimizer settings on `Result` and in `result.yml`. Round-trip test.
3. Keep `weight` in `Result.input_data`. Test that a weighted dataset round-trips through `Result.save` and `load_result`.
4. Report the original error when the evaluation after an optimizer exception raises again. Test with an objective that raises.
5. Data summary and its comparison, with a message that names what changed and by how much. Tests: equal for identical data, transposed data and differences below the tolerance; reports a changed shape, coordinate range, values and an added or removed `weight`.
6. Source detection for `source` (VS Code and Jupyter notebooks, scripts via `__main__`), `unknown` fallback, session override; `scheme_source` from `Scheme.source_path`. Unit tests per environment variable or global that is used, and a manual check in real VS Code and Jupyter sessions.
7. Histories collected in `objective_function`: cost per evaluation always, parameter values in user coordinates when switched on. SciPy 1.14.1 in the staging environment has no `least_squares` callback, and the current `OptimizationHistory` is parsed from `verbose=2` output (`optimization.py:122`). Tests for `trf`, `dogbox` and `lm` with `verbose=False`.
8. Project root: find `project.gta` in the working directory and its parents; default base folders for records and exports. Tests: root found from a subfolder, no project (working directory), nested projects (nearest wins), a v0.7 `project.gta`.
9. Record writer: numbered folders with atomic creation; `record.yml` written first with `running` and replaced atomically at the end; scheme, parameters, histories, environment; recording switches (per call, session, environment variable, with environment "off" overriding all; `output_folder=` switches recording on); write failures as warnings; `Result.record`. Tests with `glotaran.testing.simulated_data`: numbering, 4 digits after 999, concurrent creation, no arrays written, an unwritable folder, environment "off" against per-call `record=True`.
10. Record failed and interrupted fits with the last evaluated parameters. `except Exception` (`optimization.py:136`) does not catch `KeyboardInterrupt`, so the writer handles it and re-raises. Test with a scheme that raises during optimization, a simulated `KeyboardInterrupt`, and a record write that fails during a failed fit.
11. Lineage: `uid` attribute on `Parameters`, `parent=`, `parent` and `parent_data_changed` from the parent's record. Test chains, loading parameters from a file (new lineage), `parent=` by id, `uid` and path (also in another base folder), a missing parent record (`unknown`), recording off (no `uid`), and seeding a fit on replaced data from a parent fitted on the old data.
12. `recompute`: data summary check (raises; the override lists the differences), one evaluation at the recorded parameters, summary statistics, original-fit and reconstruction information, drift warning. Test exact agreement on the same machine with the scheme reloaded from `scheme.yml`, also for a scheme built in code and a scheme with plugin elements; a mismatching dataset with and without the override; an artificial drift; and that `dry_run` and `recompute` write no record.
13. `list_results(folder)` and `compare_results`: explicit and default folder, numeric sort, shape and RMS columns, filters, incomplete and damaged records, reused parent ids, data summary diff. Tests on a folder with records from two sources, a data replacement partway through, v0.7 `Project` output in the same folder, and a deleted last record.
14. `export`: named folder, `last_result` default, error on an existing folder, `overwrite=True` only over an export; input data, arrays and source files by default with opt-outs; metadata and a verbatim copy of `project.gta`; warning for parameters changed in place. Test that each supported combination loads with `load_result` or recomputes with `recompute(path, datasets=...)` after the original files have been removed.
15. Measure the overhead of recording on `optimize` (summaries, snapshots, histories) and the recompute time on the PFID case study.
16. Documentation: update the getting started notebook and the user guide, including keeping preprocessing separate from fitting, keeping input data, and the recommended `project.gta` fields. Changelog.
17. pyglotaran-extras (separate repository): progression plots from records.
18. Before sign-off, walk through these journeys:
    1. recover an old attempt after the notebook has changed;
    2. continue an attempt after a kernel restart with `parent=`;
    3. interrupt a long fit, and kill a kernel during a fit;
    4. switch output folders and change the working directory;
    5. load an export on a machine without the original files;
    6. fit into a base folder that already contains v0.7 `Project` output.

## Changes since 2026-10-04

Section numbers refer to the [review](project-api-proposal-review.md); "Decision n" to row n of its table "Decisions taken with the maintainer".

| Change | Review |
| --- | --- |
| Records contain no input data; requirement 1, Contents and Recompute state the precondition; user guide covers keeping and regenerating input data | Decision 1, 2.1 |
| `optimize(..., parent=)` with record id, `uid` or path; id or `uid` looked up in the base folder of the call, a parent in another base folder named by path | Decision 2, 2.3 |
| Calls that fail before `Optimization` exists are not recorded; `dry_run` and `recompute` write no record | Decision 3, 2.6 |
| Precedence of the switches; environment "off" overrides all; `output_folder=` switches recording on; `ValueError` with `record=False` | Decision 4, 2.7 |
| Data hash replaced by a data summary (shape; `min`, `max`, `mean`, `rms`); recompute error names what changed and by how much; listing shows shape and RMS; confirmed assumption revised | 1.9, 2.2 |
| Drift check on cost and per-dataset RMSE (weighted and unweighted), NaN and infinite values, provisional tolerance, reference to `scenarios.yml` removed, limit to the fit stated | 2.8 |
| Recompute computes the summary statistics; original-fit and reconstruction information kept through export and reload; Jacobian and covariance stated as not recoverable | 1.1, 2.8 |
| `converged` in `summary`, separate from `status` | 1.2 |
| Cost history per function evaluation, renamed `cost_history.csv`; parameter history per evaluation in user coordinates; the open point on interrupted fits is closed | 1.3, 1.4 |
| Failed and interrupted fits store the last evaluated parameters; recording errors never replace the fit's exception; `KeyboardInterrupt` re-raised | 1.5 |
| Prerequisite 1 covers the input arrays; new prerequisites 4 (`weight` dropped) and 5 (second exception); new steps 3 and 4 | 1.5, 1.6, 1.7 |
| `running` status, atomic final write, incomplete and damaged records in the listing, write failures as warnings | 2.5 |
| Empty fields per status | 2.6 |
| `Result.record`; ids, paths and `Result.record` accepted; base folder resolved once per call; record folder printed | 2.4 |
| Environment variables `GLOTARAN_RECORD`, `GLOTARAN_RESULTS_FOLDER` and `GLOTARAN_RECORD_PARAMETER_HISTORY` | 2.7 |
| Export self-contained by default (input data, arrays, referenced source files) with opt-outs; requirement 4 revised; user-named folder, `last_result` default, `overwrite=`; numbered export folders dropped | 1.8, 3 |
| Option renamed "referenced source files"; per-dataset subfolders; missing files listed; relative paths | 2.9 |
| `environment` replaces `glotaran_version`; reproducibility claim revised | 2.10 |
| `source: unknown` and session override; `scheme_source`; `name=`; listing filters; exports store the file name only | 2.11 |
| `compare_results` covers all parameter fields, weighted and unweighted RMSE and the data summary diff; wording on parameter jumps | 2.12 |
| `schema_version` and reading rules; parameter files stated as complete; warning for repeated dataset labels | 2.13 |
| `uid` behaviour defined (copies, edits, recording off, recomputed results, copied folders); lineage by `uid` and precedence of an explicit `parent=` in Lineage | 2.3 |
| Numeric sort; reused numbers marked through `uid`; only folders with `record.yml` listed | 3 |
| Export warns about parameters changed in place | 3 |
| Benchmark step | 3 |
| Evidence wording; scheme reload in the file test stated as unknown; scheme round-trip tests; sign-off journeys; v0.7 migration a non-goal | 4 |
| Project: folder with an optional `project.gta` (requirement 6); default location of records and exports at the project root; recommended RDM fields; verbatim copy in exports; new step 8 | — (maintainer, after the review) |
| `list_results(folder)` with an explicit or default base folder | — (collaborator question, after the review) |
| Section "Design decisions not yet discussed" removed: atomic folder creation and the environment variable names agreed (Recording), precedence of `parent=` agreed (Lineage) | — (maintainer, after the review) |
| Code references re-checked at staging `6aa9d918` | — |

## Background

### How v0.7 `Project` was used (PFID lycopene case study)

- 33 numbered run folders for two model names (17 + 16), each saved in full.
- Model versions tracked through dated file names, with alternatives commented out.
- Preprocessing (`isel`, `sel`, `* 1000`) in the notebook, not recorded.
- Fits seeded from the previous fit's optimized parameters.

### Independent designs (2026-10-03)

Two planning agents (Opus and Sonnet) were given only the staging working tree and the three requirements, with no access to v0.7, git history or this brief. Both proposed a folder of small per-fit records (scheme, parameters, data hash, optimizer settings, summary, parent link), recompute by one dry-run evaluation, and export as a standard `Result.save` folder. They found prerequisites 1–3 above.

### Evidence

Measured on staging `a9f62fa2`, Python 3.10, Windows, single process.

Recompute by one evaluation at the optimized parameters, compared in the same process with the in-memory `Result` of the fit:

| Case | Fit | Recompute | Worst normalized RMS, fitted data + element arrays |
| --- | --- | --- | --- |
| `sequential_spectral_decay` (1 dataset, 151 200 points) | 0.20 s, 3 nfev | 0.044 s | 0.0 |
| `study_transient_absorption` target (weights, CLP relation, dispersion) | 3.17 s, 10 nfev | 0.15 s | 0.0 |
| `ex_two_datasets` (2 datasets) | 0.82 s, 17 nfev | 0.10 s | 0.0 |

Through files (minimal save, reload `optimized_parameters.csv`, recompute): fitted-data normalized RMS 1.6e-16; the CSV keeps full float precision. Whether `scheme.yml` was reloaded in this test was not recorded, and no script for it remains in the workspace.

Storage for `sequential_spectral_decay`: default `Result.save` 3.93 MB (13 files); `SAVING_OPTIONS_MINIMAL` 3.4 kB (6 files, YAML and CSV).

Not measured: recompute agreement across machines and library versions; recompute time on the PFID case study (fit 137 s on staging, see [pfid-runtime-memory-profile.md](pfid-runtime-memory-profile.md)); scheme round-trip through `scheme.yml` for schemes built in code and for plugin elements.
