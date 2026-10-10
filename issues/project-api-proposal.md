# Result recording and export for v0.8: specification

Status: agreed specification, revised 2026-10-04 after feedback from Sebastian Weigand (Slack) and the maintainer's follow-up; see [Changes after collaborator feedback](#changes-after-collaborator-feedback-2026-10-04). Implemented on staging `staging_rebase_with_project` (`778c2390`); decisions, deviations and evidence in [project-api-implementation.md](project-api-implementation.md). A first implementation of the previous revision is on staging branch `experimental/wip_first_attempt` (`87a591f9`); it records every `Scheme.optimize` call, numbers record folders and implements lineage, so it does not match this revision. Staging revision: `a9f62fa2` (`staging_rebased`); code references re-checked at `4c635ae6`, which changes nothing under `glotaran/` since `6aa9d918`.

The 2026-10-03 version of this brief compared three designs (the v0.7 `Project`, a manifest with a lock file, an append-only fit journal). This specification replaces it. It was agreed with the maintainer after two independent designs, written from the staging code alone, converged on per-fit records with recompute (see [Background](#background)). The review of 2026-10-04 and the revision that followed it are in git at `1ba9b99` (`issues/project-api-proposal-review.md`).

## Purpose

Every fit run through a `Project` is recorded automatically, with the minimum information needed to recompute its results. A full export, which shows exactly what the user saw, is always a deliberate action. Plain pyglotaran works as a library without a project: `Scheme.optimize` records nothing.

v0.8 ships the smallest explicit version of this API. The features under [Not in v0.8](#not-in-v08) are not implemented in v0.8, also not partially or behind a flag; they will be designed for v0.9 after first usage experience.

Requirements:

1. Record enough to recompute the results of every fit run through a project from its input data, and store as little of the computable results as possible.
2. The cost history of every recorded fit is stored. The parameter history within a fit is stored only with `verbose=True`.
3. The records of a project contain enough information to visualize the fit progression across attempts and within one fit.
4. An export always contains the input data, the scheme and the parameters. Which result arrays it contains, and in which file formats, is set with the `SavingOptions` that `Result.save` uses; by default all result arrays. Referenced source files are copied only on request.
5. Preprocessing is described in the notebook or script. pyglotaran does not track it.
6. A project folder carries a human-written description of the project and its data (`project.gta`) for research data management (RDM); exports include it.

Non-goals: tracking preprocessing; bitwise reproducibility across machines or library versions; automatic deletion of records; plotting in core; migrating v0.7 `Project` folders; recording fits run without a project.

## Terms

- **Input data**: the datasets exactly as passed to `optimize`, after any preprocessing in the notebook, including `weight` where present. They are part of the meaning of a result, and every export contains them.
- **Referenced source files**: the files named by the datasets' `source_path` attributes. They show where the input data came from and can differ from it, because the notebook may slice, scale, combine or otherwise preprocess the data, and pyglotaran does not track that. Records store the path only; exports copy the files on request.
- **Record**: the folder written automatically for each fit run through a project. It contains no data and no result arrays.
- **Export**: a self-contained folder written deliberately from an in-memory `Result`.

## Behaviour

### Project

For RDM, the work is divided over three places: a person writes the project description once (`project.gta`), pyglotaran writes a record for every fit run through the project, and the user makes an export deliberately per result.

- Projects are opt-in. `project = Project.start(folder)` opens the project in `folder` (default: the working directory). If `folder` has no `project.gta`, `start` creates one with the recommended fields (below) left empty. An existing `project.gta` is used as is and never modified. Calling `Project.start` again on the same folder, for example when a notebook cell is re-run, opens the same project.
- `Project.start` does not search parent folders. A notebook in a subfolder of the project passes the project folder (`Project.start("..")`). A project found by searching upwards would capture every fit below a stray `project.gta`; during the first implementation, a v0.7 `project.gta` in the maintainer's home folder did this.
- The project instance defines where its records go: `<folder>/<results>/`, with `results="results"` by default. Exports go to `<folder>/exports/`. Both are resolved to absolute paths in `Project.start`, so a later change of the working directory has no effect.
- One notebook keeps separate record collections with separate instances, for example for two approaches in the same project folder: `Project.start(results="results_with_guide")` and `Project.start(results="results_no_guide")`. Both share `project.gta` and `exports/`.
- `project.gta` is a human-readable YAML file describing the project and its data. Every field is optional. pyglotaran reads no field from it, and `export` copies it verbatim into every export. Recommended fields, named after the DataCite metadata schema where it has an equivalent (the schema will be refined later):

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

- A folder with a v0.7 `project.gta` (`version: 0.7.x`) opens as a project; the file is used as is. v0.7 run folders in `results/` have no `record.yml` and are ignored by the listing.
- A GUI or RDM platform defines a project by creating `project.gta`; records and exports then live in known folders under it.
- Records and exports are self-contained, so a project folder that is copied or moved keeps working.

### Recording

- `project.optimize(scheme, parameters, datasets=..., name=None, **kwargs)` runs `scheme.optimize` with the same arguments and writes a record. `name=` is an optional label for the record and the only argument `project.optimize` adds. `Scheme.optimize` gets no new arguments and never writes a record, so test suites, CI and documentation builds that do not start a project write nothing.
- A record is written for every `project.optimize` call once `Optimization` has been constructed. This includes fits that fail inside the optimizer or during result construction, and interrupted fits (`KeyboardInterrupt`). Calls that fail earlier (model issues, a missing dataset label) are not recorded. `optimize(dry_run=True)` and `recompute` write no record.
- A fit claims its record folder when it starts. Once `Optimization` exists, the writer creates the folder and writes `record.yml` with status `running`, `scheme.yml` and `initial_parameters.csv`. After the fit it writes the remaining files and replaces `record.yml` atomically (temporary file, then rename). A record left at `running` belongs to a fit that never returned to Python, for example after a kernel death or an out-of-memory kill.
- Record folders are named by the local start time of the fit, `YYYY-MM-DD_HH-MM-SS` (for example `results/2026-10-04_14-28-05/`; Windows does not allow colons in folder names). The folder name is the record `id`. The writer creates the folder with an exclusive `mkdir`. If the name is taken, because two fits started in the same second in one notebook or in two notebooks sharing the results folder, it appends `_2`, `_3`, and so on.
- `record.yml` stores the start time with its UTC offset in `created`. The listing sorts by `created`; folder names sort the same way except across a daylight-saving change.
- Several notebooks may share one results folder. Each record names the notebook or script that produced it (`source`), so their records can be told apart. Where detection fails (nbclient, papermill, nbsphinx, Colab, Spyder, plain IPython), `source` is `unknown`.
- A failure to write the record (permissions, full disk, unavailable drive, serialization error) gives a warning; `optimize` still returns the result. An error while recording never replaces the exception of a failed fit. An interrupted fit is recorded and the `KeyboardInterrupt` is re-raised.
- With `verbose=True`, `project.optimize` prints the record folder and writes the parameter history. `Result.record` holds the absolute record path and `id`; it is `None` for a result of `scheme.optimize`.

### Contents of a record

```text
results/2026-10-04_14-28-05/
  record.yml                # metadata, see below
  scheme.yml                # full scheme, for every attempt (no deduplication)
  initial_parameters.csv
  optimized_parameters.csv  # see below; absent if no point was evaluated
  cost_history.csv          # cost per function evaluation, always
  parameter_history.csv     # only with verbose=True
```

- Parameter files are written with `save_parameters`, which writes every `Parameter` field: value, standard error, expression, minimum, maximum, non-negative, vary.
- `optimized_parameters.csv` holds the optimized values and standard errors for a successful fit. For a failed or interrupted fit it holds the last evaluated parameters, without standard errors; after a crash in the objective these are the parameters that raised.
- `cost_history.csv` holds the cost of every function evaluation in call order, including finite-difference Jacobian evaluations and rejected trial steps. It is collected in `objective_function`, so it is filled for every method and for `verbose=False`; it does not depend on SciPy's verbose output, from which staging currently parses `OptimizationHistory` (`glotaran/optimization/optimization.py:122`). Its row count differs from `nfev`, which SciPy counts without the Jacobian evaluations.
- `parameter_history.csv` is written when `optimize` runs with `verbose=True`; there is no other switch. It has one row per function evaluation, aligned with `cost_history.csv` by evaluation number. Values are in user coordinates (staging's `ParameterHistory` stores `log(value)` for non-negative parameters, `glotaran/parameter/parameter.py:268-271`).

`record.yml` holds:

| Field | Content |
| --- | --- |
| `schema_version` | Version of the record format (`1`). Readers reject a newer major version, ignore unknown fields and treat missing optional fields as empty |
| `id` | Folder name (`2026-10-04_14-28-05`) |
| `created` | Start time of the fit, ISO 8601 with UTC offset |
| `status` | `running`, `success`, `failed` or `interrupted`, with the error type and message for `failed` and `interrupted` |
| `source` | Path and file name of the notebook or script, relative to the record folder where possible; `unknown` if not detected |
| `scheme_source` | Path of the scheme file (`Scheme.source_path`); empty for a scheme built in code |
| `name` | Optional label from `project.optimize(..., name=...)` |
| `environment` | Versions of pyglotaran, Python, numpy, scipy, xarray and the installed glotaran plugin packages |
| `optimizer` | Settings passed to `optimize`: method, `ftol`, `gtol`, `xtol`, maximum number of function evaluations |
| `data` | Per dataset: the referenced source file and the data summary, see below |
| `summary` | Cost, chi-square, reduced chi-square, RMSE, degrees of freedom, number of function evaluations, termination reason, `converged`, free parameter labels, and per dataset the RMSE and weighted RMSE |

`converged` is SciPy's success flag. Staging's `OptimizationInfo.success` is `True` whenever `least_squares` returns (`glotaran/optimization/info.py:149`), also when the evaluation budget ran out; v0.7.4 behaves the same. `status` describes whether the call completed, `converged` whether the optimizer met its tolerances.

Empty fields per status:

| Status | Empty |
| --- | --- |
| `running` | `summary`; files other than `scheme.yml` and `initial_parameters.csv` |
| `failed`, `interrupted` | all of `summary` except the number of function evaluations and, where it could be computed, the cost |

The data summary holds, per dataset, the shape by dimension name and `min`, `max`, `mean` and `rms` of each coordinate of the model and global dimensions and of the variables the optimizer reads: `data` and, if present, `weight`. Weights defined in the scheme are in `scheme.yml`. Statistics are computed in float64 and do not depend on dimension order, dtype or byte order.

Each dataset entry also holds `source_path`: the dataset's `source_path` attribute, relative to the record folder where possible, as an unchecked reference to the file the data was loaded from. It is empty for data not loaded with `load_dataset`, which is the only function that sets `io_plugin_name` next to `source_path` (`glotaran/plugin_system/data_io_registration.py:206-207`); in-memory data carries a made-up `dataset_<n>.nc` (`glotaran/utils/io.py:62`). After `isel`, arithmetic or other preprocessing the attribute still names the original file, so the file can differ from the input data. This is accepted for v0.8: preprocessing in memory between loading and fitting is treated as an edge case (requirement 5).

```yaml
data:
  ta:
    source_path: ../../data/ta_raw.nc
    shape: {time: 500, spectral: 72}
    time:     {min: -1.0, max: 10.0, mean: 4.5, rms: 5.8}
    spectral: {min: 400.0, max: 700.0, mean: 550.0, rms: 556.0}
    data:     {min: ..., max: ..., mean: ..., rms: ...}
```

Records contain no result arrays and no data. Recomputing an attempt therefore requires that its input data was preserved or can be regenerated (see [Recompute](#recompute)). Dataset labels must be unique across experiments: since `staging_final_fixes` (2026-10-05, PR #1616 review) `Optimization` rejects a repeated label before the fit and before a record is created. Before, staging merged results by label and kept one experiment's arrays, and the writer only warned that per-dataset entries were ambiguous.

Replacing the data in an existing notebook (for example with better measurements) is supported. Fitting never compares data with earlier attempts, so a fit on new data is not blocked. The data summaries show the change: `list_results` shows shape and RMS per dataset, and `compare_results` shows the data summary diff. Whether a parameter jump comes from the data change or from a model change is for the user to judge with `compare_results`.

### Recompute

The user re-runs the notebook to regenerate the input data, then recomputes a record: one function evaluation at the recorded optimized parameters, with the recorded scheme and settings. On the three cases measured (see [Evidence](#evidence)) this reproduced the fitted data and element arrays exactly, in the same process as the fit.

- Records contain no data, so an old attempt can be recomputed only if its input data was preserved or can be regenerated. The record's `source_path` names the file the data was loaded from, as a starting point. Re-running a whole notebook re-runs every fit in it and writes a new record for each; a PFID fit takes 137 s on staging. The user guide recommends keeping preprocessing in a function, notebook or script that produces the input data without fitting, and keeping the input data of attempts that matter (an export contains it).
- `project.recompute` accepts a record id (looked up in the project's results folder), a record path, an export path or `Result.record`.
- Recompute compares the data summary of each supplied dataset with the recorded one; `source_path` is not compared. Differences up to `1e-6` times the RMS of the array count as equal, so bit-level differences between machines or numpy versions pass. A larger difference raises an error that names the dataset and says what changed and by how much (for example `ta: time max 10.0 → 8.0; data rms +0.4 %`). An explicit override (`allow_data_mismatch=True`) recomputes anyway; the recomputed result then lists the differences. A change that leaves every statistic equal, such as permuted values, is not detected; the drift check shows its effect on cost and RMSE.
- Recompute computes chi-square, reduced chi-square, RMSE and degrees of freedom from the one evaluation. Staging's `dry_run` leaves them empty and reports `success: False`, `termination_reason: "Dry run."` (`info.py:149`, `glotaran/optimization/optimization.py:172`).
- Recomputed cost and per-dataset RMSE (weighted and unweighted) are compared with the recorded values. Above a relative difference of `1e-6` a warning lists each value with its relative difference. The tolerance is provisional until recompute has been measured across machines and library versions. A recorded or recomputed value that is NaN or infinite is reported as not comparable. The comparison is attached to the recomputed result in both cases.
- The drift check measures the fit. A change in the decomposition (element arrays, CLPs) that leaves the fitted data unchanged is not detected, because records hold no arrays.
- The recomputed `Result` holds two blocks of information, written by `export` and read by `load_result`:
  - original fit: the record's `id`, summary, standard errors and cost history;
  - reconstruction: time, environment, data differences (with `allow_data_mismatch=True`) and the drift comparison.
- The Jacobian and covariance matrix of the original fit cannot be recovered; recompute does not recompute the Jacobian. `Result.save` writes neither today (`info.py:124-126`), so an export lacks nothing it would otherwise contain.
- The recomputed `Result` is an in-memory object like any other, and can be exported.

### Export

- A full export is always a deliberate call, and always starts from an in-memory `Result`, so it contains exactly what the user saw at that moment. To export an older attempt, the user recomputes it first.
- The user names the export: `project.export(result, name="best_result")` writes `<folder>/exports/best_result/`. Without a name it writes `exports/last_result/`. A relative name resolves under the project's `exports/`; an absolute name is used as given.
- If the folder exists, `export` warns that an export with this name already exists and may be stale, writes nothing, and returns. A re-run notebook therefore continues past its export cell. `overwrite=True` (default `False`) replaces the whole folder, and only a folder that contains an export (`export.yml`); for any other existing folder `export` raises an error.
- An export is self-contained: a folder that can be published as is and contains everything except the notebook or script. It contains:
  - metadata (`export.yml`), the scheme and the parameters;
  - the input data as passed to `optimize`, including `weight`, always;
  - the result arrays selected by `saving_options` (by default all: fitted data, residuals, element datasets, activations, fit decomposition);
  - the referenced source files, only with `include_source_files=True`.
- `project.export(result, saving_options=...)` takes the `SavingOptions` of `Result.save` (`glotaran/io/interface.py:39`, `glotaran/project/result.py:78`), with the same default `SAVING_OPTIONS_DEFAULT`. `data_filter` leaves result arrays out; the format and plugin fields choose the file formats of data, parameters and scheme. Export adds no option of its own for this.
- Export always writes the input data into the export folder as data, also when `data_filter` contains `input_data`. `Result.save` writes a relative `source_path` instead in that case if the data was loaded with a glotaran plugin (`glotaran/optimization/objective.py:254-271`). Export bypasses this with a flag passed through the serialization context (Sebastian's proposal: `force_write_input_data`), so preprocessed input data is never replaced by a reference to the raw file.
- Every export loads with `load_result` without the original files.
- Referenced source files: with `include_source_files=True`, export copies the current contents of each file named by a dataset's `source_path` into `source_files/<dataset label>/`, on a best-effort basis, as a reference next to the input data. Export does not compare them with the input data; they can differ (see [Terms](#terms)), data combined from several files names at most one of them, and a file may have changed since the fit. A relative `source_path` is resolved against the working directory at export time. Data not loaded with `load_dataset` has no source file (see [Contents of a record](#contents-of-a-record)). A file that does not exist or cannot be read gives a warning and is listed in `export.yml` as missing; the export still succeeds, because it contains the input data.
- An export contains the same metadata as a record (`source`, `scheme_source`, `name`, `environment`, and the `id` of the record it came from) and, for a recomputed result, the original-fit and reconstruction information. `source` holds the file name only, so a published export contains no local paths.
- The export contains a verbatim copy of `project.gta`, so a published export carries the project description.
- If `result.optimized_parameters` was changed in place after the fit, export writes the current values, warns, and lists the changed labels in `export.yml`. `Result` keeps the values from the fit for this comparison.

### Listing and comparison (core)

- `project.list_results()` lists the records in the project's results folder. Another results folder is listed through its own project instance, for example `Project.start("D:/archive/lycopene").list_results()`; `Project.start` creates `project.gta` there if it is missing.
- The table shows `id`, `created`, `source`, `name`, `scheme_source`, `status`, shape and data RMS per dataset, cost, RMSE, number of function evaluations. A change in the shape or RMS columns shows where the data was replaced.
- Only folders with a `record.yml` are listed, so v0.7 `Project` output in the same folder is ignored. Rows are sorted by `created`. The listing filters by source, scheme file, name and status.
- Records left at `running` are listed as incomplete. A damaged `record.yml` is skipped with a warning.
- `project.compare_results(a, b)` compares two records or results, given by id, path or `Result`: parameter table diff over all parameter fields (value, standard error, expression, bounds, non-negative, vary), summary statistics including weighted and unweighted RMSE per dataset, scheme text diff, and the data summary diff per dataset (what changed and by how much). Changes to weights, penalties, scales and constraints appear in the scheme diff or the data summary diff.

### pyglotaran-extras

Plotting of fit progression (across attempts and within one fit) and additional analysis such as fit-landscape visualization.

## API sketch

Names are provisional.

```python
from glotaran.io import load_parameters, load_scheme
from glotaran.project import Project

project = Project.start()              # working directory; creates project.gta if missing
scheme = load_scheme("models/scheme.yml")
parameters = load_parameters("models/parameters.yml")

result = project.optimize(scheme, parameters, datasets={"ta": ta})
                                       # records results/2026-10-04_14-28-05
result.record                          # path and id
result2 = project.optimize(scheme, result.optimized_parameters, datasets={"ta": ta},
                           name="target model B")
project.optimize(scheme, parameters, datasets={"ta": ta}, verbose=True)
                                       # also writes parameter_history.csv
scheme.optimize(parameters, datasets={"ta": ta})   # library call, nothing recorded

project.list_results()
project.compare_results(result, result2)
project.compare_results("2026-10-04_14-28-05", "2026-10-04_14-31-40")
result = project.recompute("2026-10-04_14-31-40", datasets={"ta": ta})
                                       # raises if the data summary differs
result = project.recompute("2026-10-04_14-31-40", datasets={"ta": ta_new},
                           allow_data_mismatch=True)
project.export(result)                 # exports/last_result
project.export(result, name="paper_fig3")                  # if it exists: warns, writes nothing
project.export(result, name="paper_fig3", overwrite=True)  # replaces exports/paper_fig3
project.export(result, name="paper_fig3", overwrite=True, include_source_files=True)

with_guide = Project.start(results="results_with_guide")   # two record collections
no_guide = Project.start(results="results_no_guide")       # in one project folder
```

## Not in v0.8

Deferred to v0.9 or dropped. A v0.8 implementation does not add any of these, also not partially or behind a flag.

- Lineage: a `uid` per attempt carried by `Parameters`, parent links in records, `optimize(..., parent=...)`, `parent_data_changed`, continuing a lineage after a kernel restart, lineage-tree plots.
- Recording arguments on `Scheme.optimize`: `output_folder=`, `record=`, `record_parameter_history=`, `parent=`.
- A separate switch for the parameter history; it follows `verbose=True`.
- Session-wide settings and precedence rules between per-call, session and environment settings, including a session override of the detected `source`.
- Configuration by environment variables (`GLOTARAN_RECORD`, `GLOTARAN_RESULTS_FOLDER`, `GLOTARAN_RECORD_PARAMETER_HISTORY`).
- Finding a project by searching the working directory and its parents for `project.gta`.
- JSON `project.gta` files; the file is YAML.
- An export without input data (`input_data=False`).
- Checking at export whether the referenced source files match the input data.
- `Parameters.diff()` and `Scheme.diff()` as public utilities. They are useful in general and `compare_results` could later use them, but the v0.8 API does not require them.

## Decisions confirmed with the maintainer

- Data check (revised 2026-10-04, replaces the data hash): a summary of the input data as passed to `optimize` (shape; `min`, `max`, `mean`, `rms` of coordinates, `data` and `weight`) is stored per dataset. A summary that differs beyond tolerance raises an error on recompute that names what changed, unless the user explicitly overrides it. Nothing is hashed.
- Reproducibility claim: input data + notebook + the recorded environment reproduce the results within the drift tolerance.
- The scheme is stored in full with every attempt.
- Nothing is deleted automatically.
- Records contain no input data. An old attempt can be recomputed only if the user preserved its input data or can regenerate it.
- Calls that fail before `Optimization` has been constructed are not recorded.
- Decisions of 2026-10-04 after the collaborator feedback:
  - The v0.8 API stays small and explicit; refinements follow in v0.9 after usage experience.
  - A project is opt-in and starts with `Project.start(folder)`, which creates `project.gta` (YAML) if missing and opens an existing project otherwise. Fits are recorded through `project.optimize`; listing, comparison, recompute and export are `Project` methods. Plain `Scheme.optimize` stays unchanged.
  - The project instance defines its results folder. Two independent record collections use two instances. There are no per-call, session or environment settings.
  - The fit claims its record folder when it starts, so interrupted and crashed fits own a folder.
  - Record folders are named by the start time.
  - Lineage is deferred to v0.9.
  - The cost history is always recorded; the parameter history only with `verbose=True`.
  - Records store each dataset's `source_path` as an unchecked reference.
  - Exports always contain the input data. Referenced source files are copied only with `include_source_files=True`, on a best-effort basis; a missing file gives a warning and does not fail the export.
  - An existing export is kept with a warning unless `overwrite=True`.
  - The relative `source_path` written by a minimal `Result.save` for data loaded from a file (prerequisite 3) is accepted for v0.8.

## Prerequisites in staging

These are bugs today, independent of this feature; the feature depends on all of them except 3:

1. **`Scheme.optimize` shares objects with its inputs.** `result.scheme is scheme` and `result.initial_parameters is parameters` are both `True`, and `_load_data` writes the data into the scheme in place (`glotaran/project/scheme.py:52-59`, `:110-116`). The result also shares the input arrays: `create_result_dataset` makes a shallow xarray copy (`glotaran/optimization/objective.py:617`), and `fitted_data` is computed on access as `input_data - residuals` (`objective.py:199`). A later fit, a scheme edit or an in-place change of the caller's data changes earlier `Result` objects, and so would change what a record or an export contains.
2. **Optimizer settings are not persisted.** `ftol`, `gtol`, `xtol`, `optimization_method` and `maximum_number_function_evaluations` are arguments of `Scheme.optimize` and are stored nowhere (`glotaran/project/scheme.py:68-103`).
3. **Stale `source_path` in a minimal `Result.save`** (accepted for v0.8, see [Decisions](#decisions-confirmed-with-the-maintainer)). With `input_data` in the saving filter, the serializer writes a relative path to the file the data was loaded from (`objective.py:254-271`). A fit on `raw.isel(time=slice(0, 500)) * 1000`, saved with `SAVING_OPTIONS_MINIMAL`, writes `input_data: ../raw.nc`; reloading gives input shape (2100, 72) instead of the fitted (500, 72). Data not loaded with `load_dataset` has no `io_plugin_name` and is written as data. Exports write the input data regardless (see [Export](#export)).
4. **`Result.input_data` drops `weight`.** The optimization result stores `input_data=result_dataset.data`, the signal only (`objective.py:703`, `:781`, `:955`). A `weight` variable of the input dataset is lost, so an export cannot contain the input data as passed to `optimize`.
5. **A failed fit can raise again after the optimizer exception.** After an exception in `least_squares`, staging evaluates the objective at the last evaluated parameters outside the `except` block (`glotaran/optimization/optimization.py:143`). If the exception came from the objective, this evaluation raises again, regardless of `raise_exception`.

## Implementation plan

Each step is a separate, tested commit.

1. Stop `Scheme.optimize` from sharing objects with its inputs: copy the parameters, snapshot the scheme and copy the input arrays. Test that a later fit, a scheme edit and an in-place change of the caller's data each leave an earlier `Result` unchanged.
2. Store optimizer settings on `Result` and in `result.yml`. Round-trip test.
3. Keep `weight` in `Result.input_data`. Test that a weighted dataset round-trips through `Result.save` and `load_result`.
4. Report the original error when the evaluation after an optimizer exception raises again. Test with an objective that raises.
5. Data summary and its comparison, with a message that names what changed and by how much; `source_path` per dataset, empty for data not loaded with `load_dataset`. Tests: equal for identical data, transposed data and differences below the tolerance; reports a changed shape, coordinate range, values and an added or removed `weight`; `source_path` for loaded, preprocessed and in-memory data.
6. Source detection for `source` (VS Code and Jupyter notebooks, scripts via `__main__`) with `unknown` fallback; `scheme_source` from `Scheme.source_path`. Unit tests per environment variable or global that is used, and a manual check in real VS Code and Jupyter sessions.
7. Histories collected in `objective_function`: cost per evaluation always, parameter values in user coordinates with `verbose=True`. SciPy 1.14.1 in the staging environment has no `least_squares` callback, and the current `OptimizationHistory` is parsed from `verbose=2` output (`optimization.py:122`). Tests for `trf`, `dogbox` and `lm` with `verbose=False` (cost only) and `verbose=True` (cost and parameters).
8. `Project.start(folder, results="results")`: creates `project.gta` with the recommended fields left empty if missing, never modifies an existing one, resolves the results and exports folders to absolute paths, no parent-folder search. Tests: an empty folder (file created), an existing `project.gta` (unchanged byte for byte), a v0.7 `project.gta`, `start` called twice on one folder, two instances with different results folders, the working directory changed after `start`.
9. Record writer and `project.optimize`: timestamp folders with exclusive `mkdir` and `_2` suffix; `record.yml` written first with `running` and replaced atomically at the end; scheme, parameters, histories, environment, data summaries; `name=`; write failures as warnings; `Result.record`. Tests with `glotaran.testing.simulated_data`: folder name and a collision within one second, concurrent creation from two processes, no arrays written, an unwritable folder, `scheme.optimize` writes nothing.
10. Record failed and interrupted fits with the last evaluated parameters. `except Exception` (`optimization.py:136`) does not catch `KeyboardInterrupt`, so the writer handles it and re-raises. Test with a scheme that raises during optimization, a simulated `KeyboardInterrupt`, and a record write that fails during a failed fit.
11. `project.recompute`: data summary check (raises; the override lists the differences), one evaluation at the recorded parameters, summary statistics, original-fit and reconstruction information, drift warning. Test exact agreement on the same machine with the scheme reloaded from `scheme.yml`, also for a scheme built in code and a scheme with plugin elements; a mismatching dataset with and without the override; an artificial drift; and that `dry_run` and `recompute` write no record.
12. `project.list_results()` and `project.compare_results`: sort by `created`, shape and RMS columns, filters, incomplete and damaged records, data summary diff. Tests on a folder with records from two sources, a data replacement partway through, v0.7 `Project` output in the same folder, and a damaged `record.yml`.
13. `project.export`: named folder, `last_result` default; an existing folder gives a warning and is left unchanged; `overwrite=True` only over an export; `saving_options` passed to the result serialization; input data always written as data through a serialization-context flag, also when `data_filter` contains `input_data`; `include_source_files=True` best effort with missing files listed; metadata and a verbatim copy of `project.gta`; warning for parameters changed in place. Tests: an export with the default saving options loads with `load_result` after the original files have been removed; a dataset loaded from a file and preprocessed (`isel`, `* 1000`) exports the fitted input data, also when `data_filter` contains `input_data`; a missing source file gives a warning and the export succeeds; a second export to the same name warns and leaves the folder unchanged; `overwrite=True` over a folder without `export.yml` raises.
14. Measure the overhead of recording on `optimize` (summaries, snapshots, histories) and the recompute time on the PFID case study.
15. Documentation: update the getting started notebook and the user guide with `Project.start`, keeping preprocessing separate from fitting, keeping input data, the recommended `project.gta` fields and the warning for an existing export. Changelog.
16. pyglotaran-extras (separate repository): progression plots from records, across attempts and within one fit.
17. Before sign-off, walk through these journeys:
    1. recover an old attempt after the notebook has changed;
    2. run two approaches side by side with two `Project` instances in one notebook;
    3. interrupt a long fit, and kill a kernel during a fit;
    4. change the working directory after `Project.start`, and start the project from a notebook in a subfolder;
    5. load an export on a machine without the original files;
    6. start a project in a folder with a v0.7 `project.gta` and v0.7 `results/` output;
    7. re-run a notebook whose export already exists.

## Changes after collaborator feedback (2026-10-04)

Relative to commit `1ba9b99`. Sources: Slack discussion with Sebastian Weigand, the maintainer's follow-up, and four questions the maintainer answered afterwards ("question" below).

| Change | Source |
| --- | --- |
| Project opt-in through `Project.start(folder)`; creates `project.gta` if missing, opens an existing project otherwise; no parent-folder search | Sebastian, maintainer |
| `project.optimize` records; `Scheme.optimize` gets no new arguments and records nothing; listing, comparison, recompute and export are `Project` methods | Sebastian, maintainer, question |
| Results folder set per `Project` instance; two record collections in one notebook use two instances | Sebastian, maintainer |
| Removed: `output_folder=`, `record=` and `record_parameter_history=` on `optimize`, session settings, environment variables and their precedence rules | Sebastian, maintainer |
| `project.gta` YAML only; `pyglotaran never writes to it` replaced by creation when missing | Sebastian |
| Record folders named by start time instead of `001`, `002`, ... | Sebastian, maintainer, question |
| Lineage (`uid`, `parent`, `parent=`, `parent_data_changed`, lineage tree) deferred to v0.9; requirement 3 and journeys updated | maintainer |
| Parameter history written with `verbose=True`, no separate switch; cost history always, independent of `verbose` | Sebastian, maintainer, question |
| Record data summary holds `source_path` as an unchecked reference | Sebastian, question |
| Input data always exported, `input_data=False` removed; export bypasses the relative `source_path` of a minimal save through a serialization-context flag | Sebastian, maintainer |
| `arrays=False` replaced by `saving_options` (the `SavingOptions` of `Result.save`); `input_data` in `data_filter` has no effect on an export | maintainer |
| Referenced source files only with `include_source_files=True` (Slack: `include_source_data`, renamed to match the term), best effort; missing files warn and are listed | maintainer |
| Existing export: warning, nothing written; `overwrite=True` replaces | Sebastian, maintainer |
| Prerequisite 3 accepted for v0.8 | Sebastian, maintainer |
| New sections Terms and Not in v0.8; `Parameters.diff()` and `Scheme.diff()` listed as not required | maintainer |
| Implementation plan: lineage step removed, steps 5–13 and 15–17 updated; first implementation attempt noted in Status | — |

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
