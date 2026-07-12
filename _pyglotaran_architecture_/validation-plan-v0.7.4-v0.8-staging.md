# pyglotaran v0.7.4 → v0.8 staging validation plan

Status: planning baseline, 2026-07-11

## 1. Objective

Establish whether the v0.8 staging implementation preserves the scientific behavior of the
released v0.7.4 implementation for the validation scenarios that are expected to remain
equivalent, while identifying and documenting intentional API, schema, and output differences.

The comparison target is semantic behavior, not source compatibility or byte-identical files.
The final outcome should be a reproducible evidence package containing:

- exact source and dependency revisions for both sides;
- clean, independently reproducible environments;
- a scenario-by-scenario pass/fail/blocked matrix;
- normalized numerical and structural comparison reports;
- focused regression tests for every staging defect found and fixed; and
- a dated log explaining each iteration and remaining difference.

## 2. Baseline overview

Two orchestration worktrees are present under `temp/`:

| Baseline | Parent revision | pyglotaran | pyglotaran-extras | pyglotaran-examples | Environment |
|---|---|---|---|---|---|
| v0.7.4 / main | `78ffaf5a64eab8be330652d3c8a6eceb5d071d3f` | `8f26be01d5a6ce63ec2556469ac3facc2d2cee68` | `dcbe4baad5949768b65bf602d58018b5fe309f0a` | `5e157363ca6e776c3da7a6c4742a07930d205138` | Python `>=3.10`, `uv.lock` |
| v0.8 staging | `be1c861cfce21db94e1a360e882df4c8e942a40e` | `7efc9d1114a2455da8bc37fc4770a455ef2e437a` | `d57940be02751c670ee90f3bc09af7cd954a1d08` | `5a57fb5c47c9f0934ab573319bf929d35e690ed7` | Python `==3.10.*`, `uv.lock` |

The parent worktrees are clean on their local `main` branches. Their submodule directories are
currently empty/uninitialized, so submodule initialization is a prerequisite for all execution.
Do not change or advance the pinned commits while establishing the baseline.

The available scenario material is currently:

- v0.7: GFP sequential and target notebooks, plus linked-CLP simulation/fit material;
- staging: rewritten GFP notebooks, linked-CLP staging notebooks, and a redox example;
- both architecture reports: explicit notes on the v0.7/v0.8 execution and result contracts.

The staging parent documents `uv sync` and
`uv run pyglotaran-examples/scripts/run_examples_notebooks.py run-all` as its notebook workflow.
The v0.7 runner and the initialized `pyglotaran-examples` submodule still need to be inspected
before choosing the equivalent command.

## 3. Validation principles

1. **Freeze inputs before comparing outputs.** Use the same data files, coordinate ordering,
   initial values, fixed/free parameter choices, optimizer method, tolerances, weights, and random
   seeds wherever the scenario has a v0.7 counterpart.
2. **Compare by meaning and labels.** Normalize dimension names, dataset names, CLP labels,
   parameter labels, and result variables before comparing arrays. Never compare positional arrays
   when labels are available.
3. **Separate intentional differences from defects.** The v0.8 `Scheme`/`ModelLibrary`/
   `ExperimentModel`/`DataModel`/`Element` model, removed `Project`/CLI/module-level `optimize`,
   and changed persistence layout are expected migration differences. They still require working
   v0.8 equivalents, but not v0.7 API identity.
4. **Treat diagnostics as behavior.** Parameter uncertainties, solver success, residuals, fitted
   data, histories, SVD fields, and saved/reloaded results are part of validation, not optional
   presentation details.
5. **Make every defect reproducible before fixing it.** A staging change is accepted only when a
   focused test or fixture demonstrates the original failure and the corrected behavior.
6. **Keep the two environments isolated.** Run each baseline in its own `.venv` and process;
   never rely on an editable install or import path from the other worktree.

## 4. Scenario catalogue

Create a scenario matrix before running the full suite. Each row gets a stable ID, input paths,
the v0.7 command/notebook, the v0.8 equivalent, and a normalization/comparison adapter.

### Common scientific scenarios

These are the primary release-parity cases because they exist in both worktrees or have a clear
rewrite:

| ID | Scenario | Required coverage |
|---|---|---|
| `GFP-sequential` | GFP sequential analysis | data loading, kinetic model, nonlinear fit, spectra/CLPs, residuals, result rendering |
| `GFP-target` | GFP target analysis | target/branched model behavior, shared parameters, result decomposition |
| `CLP-unlinked` | Simulated linked-CLP example with linking disabled | forward simulation, independent per-dataset estimation |
| `CLP-linked` | Simulated linked-CLP example with linking enabled | global-axis alignment, shared CLPs, scales, multi-dataset result assembly |

### Cross-cutting contract scenarios

Run focused tests or small scripts for behavior that notebooks may not expose reliably:

- simulation-to-fit recovery with known synthetic parameters;
- weighted and unweighted fits;
- index-independent and index-dependent matrices;
- constraints, relations, and CLP penalties;
- ordinary/local and full/global model branches;
- failure/invalid-model handling and solver success reporting;
- parameter bounds, expressions, non-negative parameters, and standard errors;
- result save/load round trips, minimal saves, and source-path handling;
- `pyglotaran-extras` plotting/result-consumption compatibility.

### Staging-only scenarios

Run and report these separately rather than treating the lack of a v0.7 counterpart as a
regression:

- rewritten GFP forms that exercise new v0.8 model composition;
- the staging redox example;
- any new element, experiment, schema, or persistence feature with no v0.7 representation.

## 5. Execution phases and gates

### Phase 0 — Establish and record the baseline

1. Verify both parent worktrees are clean and record `git status`, parent revision, submodule
   revision, Python version, OS, `uv` version, and lockfile hash.
2. Initialize/update submodules to the already recorded parent pins. If network access is needed,
   do this as an explicit setup action and record the resulting status; do not silently fetch a
   different branch or commit.
3. Create one environment per parent worktree from its lockfile. Verify imports resolve to the
   intended local `pyglotaran`, `pyglotaran-extras`, and examples paths.
4. Run a smoke command that prints package versions and import locations.

**Gate:** both environments install successfully, import the pinned code, and can execute a
minimal synthetic fit.

### Phase 1 — Inventory tests and examples

1. Enumerate package tests, extras tests, example notebooks, scripts, model files, data files, and
   existing reference result artifacts in each checkout.
2. Map each v0.7 scenario to either a v0.8 rewrite or an explicit `not comparable` reason.
3. Identify notebook side effects and hidden state. Convert any required notebook run into a
   deterministic script/papermill invocation with explicit input/output folders.
4. Define the comparison schema before producing results.

**Gate:** every common scenario has an executable pair or an approved translation record.

### Phase 2 — Verify package-level behavior

Run the native test suites independently in each environment, first by package and then in full.
Record the exact commands and summarized results. Use failures to distinguish baseline problems,
environment problems, and expected API rewrites before inspecting scientific parity.

Minimum order:

1. `pyglotaran` unit/integration tests;
2. `pyglotaran-extras` tests;
3. example repository tests or notebook-runner checks;
4. focused tests for any scenario-specific helper.

**Gate:** baseline failures are classified. A clean validation report must not hide pre-existing
failures behind a single aggregate exit code.

### Phase 3 — Run the common scenarios

For each scenario, run v0.7 first and store an immutable raw result bundle. Then run the translated
v0.8 equivalent with the same data and scientific settings. Preserve notebook outputs only as
diagnostic artifacts; use normalized machine-readable summaries as the comparison input.

Each run should capture at least:

- source/environment manifest and scenario ID;
- input file hashes and model/parameter specification hashes;
- solver method, tolerances, seed, start values, and run duration;
- success/status/message and exception traceback if applicable;
- optimized nonlinear parameters and standard errors;
- residual norm, RMSE/chi-square-related metrics, degrees of freedom, and penalty terms;
- fitted data and residual arrays in labeled coordinates;
- CLPs/spectra/concentration/decomposition arrays where scientifically meaningful;
- result metadata, dimensions, variables, and serialization round-trip status.

### Phase 4 — Normalize and compare

Use a comparison adapter per scenario. The adapter must state any transformations explicitly, for
example API field renaming, dimension transposition, result decomposition reshaping, or sign/scale
ambiguity. It must never silently discard a field.

Classify each observation as:

- **PASS:** executable and within the declared structural and numerical tolerances;
- **EXPECTED DIFFERENCE:** known API/schema/layout or documented algorithmic difference with no
  scientific regression;
- **REGRESSION:** v0.8 fails, changes the scientific result beyond tolerance, or loses a v0.7
  contract that is in scope;
- **BASELINE FAILURE:** v0.7 itself fails or its stored artifact is not reproducible;
- **BLOCKED:** missing submodule, dependency, data, or required translation.

Recommended comparison tiers:

1. execution: no unexpected exception, expected solver status, no NaN/Inf;
2. structure: labels, dimensions, coordinates, variables, and result presence;
3. fit quality: residual/fitted-data arrays and objective metrics;
4. parameter recovery: nonlinear parameters and meaningful uncertainties;
5. scientific decomposition: CLPs, spectra, kinetics, activations, and other domain outputs;
6. persistence: save/load and re-optimization behavior.

Declare tolerances per tier and scenario. Use absolute and relative tolerances appropriate to the
data scale, and include a maximum absolute difference and a summary statistic. Do not use one
global tolerance for all parameters and arrays.

### Phase 5 — Triage and iterate on staging

For every regression:

1. reduce it to the smallest deterministic case;
2. determine whether it is a translation defect, an environment/numerical nondeterminism issue,
   an intentional v0.8 change, or a staging implementation defect;
3. add or update a focused staging test;
4. make the smallest scoped staging change;
5. rerun the focused test, affected scenario, and relevant native suite;
6. rerun the full common matrix after a group of related fixes; and
7. append the iteration record to the validation log.

Known v0.8 risk areas to check early, based on the architecture reports, are non-negative
parameter standard errors, parameter-history recording, `add_svd` semantics, final solver-state
assignment, result success reporting, label ordering/collisions, residual selector consistency,
full/global parity, and numerical/persistence coupling.

### Phase 6 — Final release-readiness run

Repeat the complete process from the recorded commits in clean environments. Confirm that:

- all common scenarios are PASS or explicitly accepted EXPECTED DIFFERENCE;
- no unexplained REGRESSION or BLOCKED item remains;
- every fixed regression has a permanent test;
- staging-only scenarios pass their own acceptance criteria;
- save/load artifacts can be reloaded in the intended environment;
- plots and extras consume the new result shape correctly; and
- the final report names residual scientific differences and their disposition.

## 6. Comparison contract

The default contract for a common scenario is:

- identical input data after canonical coordinate ordering;
- equivalent model semantics after v0.7-to-v0.8 translation;
- successful execution in both versions;
- equivalent fitted-data and residual arrays within the scenario tolerance;
- equivalent scientifically meaningful parameters/CLPs within parameter-specific tolerances;
- no unexplained loss of result variables or dimensions;
- diagnostics either equivalent or explicitly listed as an intentional change; and
- successful persistence round-trip where persistence is in scope.

The following are not parity failures by themselves:

- renamed classes, fields, or YAML keys required by the rewrite;
- changed result directory/file layout when the normalized content is equivalent;
- different optimizer iteration histories if final results and stated diagnostics are valid;
- harmless floating-point differences within tolerance;
- different internal object graphs or plugin registration paths.

Sign, scale, or ordering ambiguities must be resolved by labels and a documented canonicalization,
not by manually accepting a visually similar plot.

## 7. Reproducibility and logging

Keep the following artifacts under a dedicated validation output directory outside the source
trees, with the source manifests committed or archived alongside the final report:

```text
validation/
  manifests/
    v07-environment.json
    v08-environment.json
    scenario-matrix.yaml
  raw/
    <scenario>/<baseline>/...
  normalized/
    <scenario>/<baseline>.json
  comparisons/
    <scenario>.json
    summary.md
  logs/
    validation-log.md
```

Each log entry should contain: date/time, iteration ID, source revisions, scenario IDs, command,
hypothesis, observed difference, classification, code/test changes, focused result, full-matrix
result, and remaining follow-up. Append entries; do not rewrite history when a later iteration
changes the conclusion.

## 8. Definition of done

Validation is complete when a clean rerun demonstrates that the v0.8 staging branch is scientifically
equivalent to v0.7.4 for all in-scope common scenarios, all intentional differences are documented,
all staging regressions have focused tests and fixes, the staging-only examples meet their own
criteria, and the final manifests/results are sufficient for another developer to reproduce the
claim without relying on an interactive notebook state.
