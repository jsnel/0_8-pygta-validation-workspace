# Review: result recording and export specification

Status: review of [project-api-proposal.md](project-api-proposal.md), 2026-10-04.
Staging revision: `a9f62fa2` (`staging_rebased`). Code references are relative to
`temp/pyglotaran-staging-dev/pyglotaran`.

This review merges two independent reviews of the specification: one by Claude (code
reading) and one by Codex (code reading and focused runtime probes). Each finding
names its source: **both**, **Claude** or **Codex**. Findings marked *confirmed* were
checked in the staging code; the Codex probe results were re-checked by reading the
code paths involved.

## Verdict

Per-fit records with recompute, deliberate export, lineage by `uid`, atomic folder
allocation and no automatic deletion are sound choices. The specification is not yet
implementation-ready: several behaviours it relies on do not exist in staging
(recompute diagnostics, histories, complete input retention), and it promises more
recoverability and historical fidelity than the stored information supports.
Section [Recommended changes](#recommended-changes-to-the-specification) lists the
revisions in priority order.

## Decisions taken with the maintainer (2026-10-04)

Both reviews proposed changes to agreed behaviour, and disagreed on one point. The
maintainer decided:

| Topic | Decision |
|---|---|
| Input data in records | Records keep containing no data. The specification states the precondition explicitly: an old attempt can be recomputed only if the user preserved its input data. |
| Lineage across restarts | Add an explicit parent argument, `optimize(..., parent="017")` (record id or `uid`). Parameter files stay lineage-free. |
| Calls that fail before the optimizer exists | Not recorded. A record exists only once `Optimization` has been constructed. |
| Precedence of recording switches | Per-call > session > environment stays for the folder and the parameter history. An environment variable that disables recording overrides every other setting. |

## 1. Confirmed gaps in staging

### 1.1 Recompute through `dry_run` does not reconstruct the `Result` (both, confirmed)

`OptimizationInfo.from_least_squares_result` sets `success = result is not None`
(`glotaran/optimization/info.py:149`), and `Optimization.dry_run` passes `None`
(`glotaran/optimization/optimization.py:172`). A recomputed `Result` therefore has:

- `success: False`, `termination_reason: "Dry run."`, `number_of_function_evaluations: 1`;
- no chi-square, reduced chi-square, RMSE, degrees of freedom or optimality;
- no Jacobian and no covariance matrix;
- an empty optimization history.

Consequences:

- The specification compares recomputed "cost and RMSE"; only cost exists.
- "To export an older attempt, the user recomputes it first" makes every export of an
  older attempt contain a `result.yml` describing a failed one-evaluation run.

Required: recompute computes RMSE and the other summary statistics itself, and
attaches the recorded summary, standard errors and cost history as original-fit
information, kept separate from the reconstruction information (see 2.8). The
specification states which diagnostics are not recoverable (the covariance matrix
unless the Jacobian is recomputed at a cost of n_free + 1 evaluations).

### 1.2 `success` conflates completion with convergence (Codex, confirmed)

The same line sets `success=True` whenever `least_squares` returns. A Codex probe with
an evaluation budget returned SciPy `success=False`, status `0`, "maximum number of
function evaluations exceeded", and pyglotaran reported `success=True`. The record
needs an execution status (`success`, `failed`, `interrupted`) and, separately, the
optimizer's convergence status and message.

### 1.3 The cost history is empty for quiet and Levenberg-Marquardt fits (both, confirmed)

`OptimizationHistory` is parsed from SciPy's stdout, which is only produced with
`verbose=2` (`glotaran/optimization/optimization.py:122`). SciPy prints no iteration
progress for `method="lm"`. `optimization_history.csv` is therefore empty for every
fit with `verbose=False` and every Levenberg-Marquardt fit, and requirement 3 ("within
one fit") is not met for them. A Codex probe confirmed zero history rows for a quiet
fit.

### 1.4 The parameter history is not implemented (both, confirmed)

`_parameter_history.append` is called once, during construction
(`glotaran/optimization/optimization.py:95`). Making the history optional means
implementing it in `objective_function`, which is also called for finite-difference
Jacobian columns and rejected trial steps. The specification has to define:

- whether rows are accepted iterates or function evaluations, and how they align with
  the cost history;
- the coordinates of the values: `ParameterHistory.append` uses
  `get_label_value_and_bounds_arrays`, which stores `log(value)` for non-negative
  parameters (`glotaran/parameter/parameter.py:268-271`) (Codex);
- behaviour for each supported optimizer method.

### 1.5 Failed and interrupted fits store the last evaluated point (both, confirmed)

After an optimizer exception, staging evaluates the penalty at `self._parameters`
(`glotaran/optimization/optimization.py:143`). That is the last point `least_squares`
evaluated: possibly a Jacobian perturbation, a rejected trial step, or the point that
produced the error. If the exception came from the objective, this evaluation can raise
again outside the `except` block, regardless of `raise_exception`.

The specification has to define which checkpoint `optimized_parameters.csv` holds for
non-successful attempts: last evaluated, last accepted, or best-known. Recommended:
track the best-cost parameters in `objective_function` and store those, labelled as
such. Record writing goes in `try/finally`, and an error while recording must not mask
the original exception.

### 1.6 Prerequisite 1 must include the input arrays (Codex, confirmed)

`create_result_dataset` uses `data.model.data.copy()`
(`glotaran/optimization/objective.py:617`), a shallow xarray copy, so the result
shares arrays with the caller's dataset. `fitted_data` is computed on access as
`input_data - residuals` (`objective.py:199`). In a Codex probe, modifying one value in
the caller's dataset after the fit changed both `input_data` and `fitted_data` of the
earlier result. The acceptance test for step 1 must cover in-place mutation of the
caller's data, besides later scheme edits and later fits.

### 1.7 `Result.input_data` drops fit-relevant variables (Codex, confirmed)

The optimization result stores `input_data=result_dataset.data`, the signal
`DataArray` only (`glotaran/optimization/objective.py:703`, `:778`, `:955`). A `weight`
variable supplied in the input dataset is lost. Exporting "the fitted input data, as
passed to `optimize`" (step 10) requires retaining the complete normalized input
datasets, including `weight`.

### 1.8 Optional export parts conflict with `load_result` (Codex, confirmed)

The `input_data` validator raises `"Input data cannot be None."`
(`glotaran/optimization/objective.py:316`). An export without the input data either
fails to load or keeps a reference to an external file, which works on the author's
machine and fails for a recipient. The specification has to state:

- what `export(result)` includes by default;
- which option combinations are self-contained;
- which require the recipient to supply data, and how.

Test each supported combination after the original files have been removed.

### 1.9 The data hash definition misses `weight` and dimension order (both, confirmed)

`OptimizationData` reads a `weight` variable from the dataset
(`glotaran/optimization/data.py:70`) and transposes inputs to (model, global)
(`data.py:240-241`). "Dims, coordinates, values" does not say which variables count:

- hashing only `data` lets a change of weights pass the recompute check;
- hashing all variables makes the hash change for variables the fit never reads (for
  example a dataset taken from an earlier result);
- a transposed input gives the same fit and a different hash.

Recommended: hash exactly what the optimizer reads (`data`, `weight`, model and global
coordinates) after transposing to (model, global). See 2.2 for the rest of the hash
contract.

## 2. Design gaps that affect users

### 2.1 Recovering an old attempt (both)

Recompute requires regenerating the old input data by re-running the notebook. The
notebook may since use other measurements, preprocessing, calibration files, random
seeds or helper code; the hash detects this and cannot recover the old input.

Per the decision above, records keep containing no data. The specification must then:

- state the precondition: recomputing an old attempt requires that the user preserved
  its input data;
- describe how to regenerate data without re-running the fits. Re-running a whole
  notebook re-runs every fit in it, writes a new record for each, and takes 137 s per
  fit on the PFID case study. Script users have to extract the preprocessing code.

### 2.2 Hash contract and its strictness (both)

The confirmed reproducibility claim is "within a tolerance", and cross-machine bitwise
reproducibility is a non-goal, yet recompute hard-fails on any bit difference of the
input. Preprocessing that differs by one ULP between machines or numpy versions
(reductions, interpolation, baseline subtraction) breaks every recompute, and the only
way through is `allow_data_mismatch=True`. Users who pass it routinely lose the check.
(Claude)

The hash contract also has to define (Codex):

- variable names and the set of fit-relevant variables (1.9);
- dimension order, dtypes, byte order, NaN handling, coordinate types;
- whether equivalence is byte-level or canonical;
- which attributes, if any, affect execution;
- the hash algorithm and a canonicalization version stored in the record, so a later
  implementation change does not invalidate existing records.

Recommended (Claude): store a tolerant fingerprint next to the exact hash (shape,
coordinates, and sum, L2 norm, min and max per variable), so recompute can report
"bitwise different, numerically equal within X" separately from "different data".

### 2.3 Lineage after restarts and parent resolution (both)

Per the decision above, `optimize` gets an explicit `parent=` argument (record id or
`uid`) for continuing a lineage after a restart. Parameter files stay lineage-free.
Open points:

- **Resolving `parent=` by id**: ids are unique only within one base folder. The
  specification has to say which base folder is searched, and that the resolved `uid`
  is what gets recorded.
- **Parent data hashes**: `parent_data_changed` needs the parent's hashes. They are
  unavailable when the parent was fitted with recording off, into another base folder,
  or was deleted. Carry the hashes in memory alongside the `uid` for in-session
  lineage. When they cannot be found, record `parent_data_changed` as unknown; never
  report unknown as "nothing changed" (Codex).
- **Duplicate `uid`s**: copied record folders produce several records with the same
  `uid`. Define how lookup and listing treat them.
- **"Derived" parameters**: copies, edited values, toggled `vary`, renamed parameters
  and parameters assembled from several results do not share the same provenance.
  Define which operations keep the `uid`. A modified parent can be detected by
  comparing the initial parameters with the parent's optimized parameters; record
  that difference.
- **Recomputed results**: define which `uid` a recomputed `Result.optimized_parameters`
  carries, so that a fit seeded from it links to the original attempt.

### 2.4 Locating records: ids, paths and the working directory (both)

- The specification does not require `optimize` to show the record id or expose it on
  `Result`. Users need it for `recompute` and `compare_results`. (Claude)
- Records default to `<cwd>/results`. Scripts write wherever Python was started; the
  VS Code notebook working directory depends on `jupyter.notebookFileRoot`; after
  `os.chdir` or `%cd`, `list_results()` and `recompute("002")` no longer find earlier
  records. (both)

Recommended: return a durable record reference (path and `uid`) on `Result`, accept
paths and references in `recompute` and `compare_results`, and resolve the output
location once, at the start of the call (Codex).

### 2.5 Record lifecycle, write failures and durability (both)

- Atomic `mkdir` prevents allocation collisions. It does not prevent readers from
  seeing half-written records, or keep any information after a kernel death,
  out-of-memory kill, native crash or power loss. These are the main failure modes on
  large datasets, and none of them raises `KeyboardInterrupt`.
- Recommended: write `record.yml` before the optimization starts, with a `running`
  status. Publish the final metadata atomically (write to a temporary file, then
  rename). `list_results` reports records left in `running` as incomplete and skips
  damaged records with a warning, keeping access to healthy ones.
- Folder numbers then reflect allocation order. Document this.
- Write failures (permissions, full disk, unavailable network drive, read-only
  JupyterHub mounts, serialization errors) must produce a warning and must not discard
  the fit result. Define this before recording is on by default.

### 2.6 Which calls create a record

- Per the decision above, calls that fail before `Optimization` is constructed (model
  issues, missing dataset label) are not recorded. The wording "every `Scheme.optimize`
  call writes a record" changes accordingly.
- `optimize(dry_run=True)` and recompute calls must not create records (both). If
  recompute is implemented through `optimize`, each recompute otherwise adds a record.
- Fits that fail inside the optimizer or during result construction are recorded with
  nullable fields. The specification lists which fields can be empty per status
  (Codex).

### 2.7 Configuration (both)

- Per the decision above, an environment variable that disables recording overrides
  per-call and session settings, so CI and docs builds never write records. The
  specification needs concrete variable names and values; `GLOTARAN_OUTPUT_FOLDER`
  cannot express "off" or "history on".
- It is undefined whether `output_folder=` implies recording on.
- Session settings do not reach worker processes. Parallel fits with joblib, loky or
  multiprocessing (fit-landscape scans, parameter grids in pyglotaran-extras) write to
  the default `<cwd>/results` even when the notebook switched recording off. Only the
  environment variable propagates. pyglotaran-extras has to pass `record=False`, or
  core offers a context manager for sweeps. (Claude; Codex on context management)

### 2.8 Recompute provenance and the drift check (both)

A recomputed result describes a reconstruction, which can differ from the original
attempt (`allow_data_mismatch=True`, another library version). Exporting the original
`uid`, hashes, summary and version without marking them as such misdescribes the
artifact. Persist through export and reload (Codex):

- the original attempt reference;
- the actual input hashes and the mismatch information;
- the reconstruction version and time;
- the drift comparison.

The drift check is weak (both):

- Cost and RMSE are residual norms. Different residual arrays can have equal norms,
  and variable projection re-solves the CLPs, so a model change inside the CLP span
  barely changes the cost.
- The `1e-6` tolerance comes from the fitted-data normalized RMS in `scenarios.yml`,
  a different metric. That file also allows `2e-5` and `3e-5` for some cases, so
  cross-version recomputes will warn routinely.
- Define absolute tolerance near zero and handling of missing, NaN and infinite values
  (Codex).

Recommended (Claude): store a fitted-data fingerprint per dataset (L2 norm and the
top-k singular values, a few hundred bytes) and compare against it. Define in the
specification exactly what the check establishes.

### 2.9 Raw source export (both)

`source_path` does not reliably identify the source:

- in-memory data gets a fabricated `dataset_<n>.nc` (`glotaran/utils/io.py:62`);
- the attribute can point to an intermediate processed file;
- data combined from several files has no single source;
- the file may have changed since the fit, so the export copies its current contents.

Define behaviour for missing files, duplicate basenames, several source files and
relative paths. Call the option "referenced source files" unless provenance is
established. (Codex on naming and changed files)

### 2.10 Environment and notebook version (both)

The claim "input data + notebook + pyglotaran version" is not supported by what the
record stores:

- The record names the notebook but does not store its version. A content hash or
  modification time of the notebook or script file costs nothing.
- Every editable development install reports the same version string (`0.8.0.dev0`),
  which is the situation in this workspace.
- Record numpy, scipy and xarray versions, plugin identities and versions, and the
  source revision when available. These are the first things needed when a drift
  warning appears.

### 2.11 Identifying runs (both)

- Notebook detection works in VS Code and Jupyter Server. It does not work under
  nbclient, papermill, nbsphinx, myst-nb, Colab, Spyder or plain IPython. The
  validation runner uses nbclient (`validation/run_examples.py:26`), so every
  validation run lands in the fallback. Test detection in real VS Code and Jupyter
  sessions, support an unknown source, and offer an explicit override (Codex).
- When a relative path is impossible (for example a different Windows drive), `source`
  becomes an absolute path, which puts user names into shared exports. (Claude)
- All runs from one notebook share one `source`. The PFID case study used two model
  names; the listing has no model name or user label. Add optional names, notes and
  tags, and filters in `list_results`. (Codex)

### 2.12 Comparability in progression plots (Codex)

Changes to weights, penalties, scales, fitted ranges or constraints change the
objective while the input-data hash stays the same. A lower cost can then reflect
reduced weighting or fewer fitted points. `compare_results` should flag changes that
affect objective comparability, distinguish weighted and unweighted RMSE, and include
parameter bounds, expressions and fixed/free status. A data-change marker identifies a
data change; it does not establish the cause of a parameter jump.

### 2.13 The record format is a public API (Codex)

Core comparison and the pyglotaran-extras plots will read records. Required:

- a schema version, and rules for unsupported versions, missing fields and extensions;
- complete parameter serialization (fixed values, bounds, expressions, non-negative
  flags), beyond values and standard errors;
- dataset identity across experiments: results are merged by dataset label
  (`glotaran/optimization/optimization.py:142` has a TODO about duplicate labels), so
  per-dataset summaries can be ambiguous or lose one experiment's result.

## 3. Smaller issues

- **Number sorting** (Claude): `999` → `1000` sorts wrongly in `sorted()`, `ls` and
  most tools. Use a fixed 4-digit width or sort numerically in `list_results`.
- **Number reuse** (Claude): "largest + 1" reuses the number of a deleted last record;
  the `parent` id shown by `list_results` then points to another attempt.
- **Export numbering** (Claude): `exports/001` for record `002` (as in the API sketch)
  is confusing. Name exports after the record id.
- **Existing `results/` folders** (Claude): v0.7 `Project` directories and many
  example notebooks already use `results/`. `list_results` must identify records by
  `record.yml`.
- **Mutating results** (Claude): `result.optimized_parameters` modified in place
  (common when seeding the next fit) changes what a later `export(result)` writes.
  Prerequisite 1 covers inputs only.
- **Performance** (Codex): hashing reads all inputs, snapshots add memory, histories
  grow, and allocation scans a growing folder. Benchmark the default recording path
  and a large-case recompute (PFID). The PFID profile already shows expensive result
  construction and high memory use.

## 4. Evidence gaps (both)

- "Reproduces every result array exactly" was measured in one process from an
  in-memory `Result`, for fitted data and element arrays only. The file-based test
  gave 1.6e-16, and it is not stated whether `scheme.yml` was reloaded. Scheme
  round-trip through `model_dump(mode="json")` is untested for programmatically built
  schemes and plugin elements.
- Walk through these journeys before implementation sign-off (Codex):
  1. recover an old attempt after the notebook has changed;
  2. continue an attempt after a kernel restart (with `parent=`);
  3. interrupt a long fit and kill a kernel during a fit;
  4. switch output folders and change the working directory;
  5. load an export on a machine without the original files;
  6. migrate a v0.7 project with named results.

## 5. What holds up

- Minimal records with recompute, supported by the measured storage ratio (3.4 kB
  against 3.93 MB).
- Prerequisites 1–3 are real bugs, independently confirmed in
  `glotaran/project/scheme.py:52-116`. Prerequisite 1 needs the extension in 1.6.
- Atomic `mkdir`, lineage by `uid`, no automatic deletion, and plotting in
  pyglotaran-extras.

## Recommended changes to the specification

In priority order:

1. **Reconstruction semantics**: recompute computes the full summary, attaches the
   recorded diagnostics as original-fit information, and carries separate
   reconstruction provenance through export and reload (1.1, 2.8).
2. **Recovery precondition**: state that recompute requires preserved input data, and
   describe regenerating data without re-running fits (2.1).
3. **Complete input retention and data ownership**: snapshot input arrays, keep
   `weight` and other fit-relevant variables in `Result.input_data` (1.6, 1.7).
4. **Hash and drift contract**: hash the canonical optimizer inputs with a stored
   algorithm version, add a tolerant input fingerprint and a fitted-data fingerprint
   (1.9, 2.2, 2.8).
5. **Record lifecycle**: `running` status written first, atomic final write, warn on
   write failure, best-known parameters for failed and interrupted fits, execution
   status separate from convergence (1.2, 1.5, 2.5, 2.6).
6. **Export portability**: define defaults and self-contained combinations, test
   loading without the original files (1.8, 2.9).
7. **Lineage**: `parent=` with defined resolution, unknown `parent_data_changed` when
   hashes are unavailable, defined derivation rules (2.3).
8. **Locating and configuring**: record reference on `Result`, explicit paths in the
   API, environment "off" overriding all settings, concrete variable names, guidance
   for worker processes (2.4, 2.7).
9. **Histories**: define iterates or evaluations, coordinates, and behaviour for
   `verbose=False` and `lm` (1.3, 1.4).
10. **Record format**: schema version, complete parameter serialization, environment
    versions and notebook hash, run names and notes (2.10, 2.11, 2.13).
