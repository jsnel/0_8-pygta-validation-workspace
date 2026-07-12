# pyglotaran architecture comparison — v0.7.4 vs. v0.8.0

**Canonical comparison.** This self-contained document compares the released v0.7.4 architecture
(`main`) with the v0.8.0 rewrite (`staging`, after
[PR #1562](https://github.com/glotaran/pyglotaran/pull/1562)). Implementation code and tests are
the primary evidence. Claims marked **[verified]** were checked directly in code; recommendations
describe future work rather than current behavior.

## Table of contents

1. [TL;DR](#tldr)
2. [What fundamentally changed](#what-fundamentally-changed)
3. [What improved](#what-improved)
4. [What regressed](#what-regressed)
5. [Scientific parity vs. architectural compatibility](#scientific-parity-vs-architectural-compatibility)
6. [Cross-cutting risks](#cross-cutting-risks)
7. [What can still be improved](#what-can-still-be-improved)
8. [Biggest differences at a glance](#biggest-differences-at-a-glance)
9. [Evidence and scope](#evidence-and-scope)

---

## TL;DR

The rewrite is a genuine architectural improvement in its core decisions — the model
decomposition, the pydantic migration, and the structured result API are all the right
calls, and the numerical spine got *simpler*, not just different. But the migration is
unfinished in ways that matter: at least one silent numerical regression (non-negative
parameter standard errors), several diagnostics that quietly degraded, a completely
abandoned compatibility story, and a new god-module (`objective.py`) that is worse than
what it replaced.

**v0.8 is a better architecture with a worse finish, currently.**

---

## What fundamentally changed

Five decisions define the rewrite; everything else follows from them.

### 1. The monolithic `Model` was decomposed

v0.7 had one dynamically generated `Model` class holding label→item dictionaries for
everything (`Model.create_class_from_megacomplexes` in `glotaran/model/model.py`), with
`Project` as a folder-workflow facade on top. v0.8 splits this into:

- `ModelLibrary` — reusable element definitions, with a new `extends` inheritance
  mechanism (`glotaran/project/library.py`);
- `ExperimentModel` — a group of datasets optimized together, owning clp linking,
  relations, and penalties (`glotaran/model/experiment_model.py`);
- per-dataset dynamic `DataModel` classes (`glotaran/model/data_model.py`).

Multi-experiment optimization is now first-class rather than emulated through v0.7's
dataset groups.

### 2. attrs metaprogramming → pydantic v2

v0.7's `glotaran/model/item.py` was a homegrown schema framework: a custom `@item`
decorator, `ModelItemType[X]` annotations, converters, and `fill_item()`. v0.8 replaces
it with standard pydantic v2: discriminated unions on `type`, `extra="forbid"`, field
validators, and JSON-schema generation essentially for free
(`glotaran/utils/json_schema.py`). The "filling" concept survived as
`resolve_item_parameters` (`glotaran/model/item.py` in v0.8), now built on pydantic
field introspection.

### 3. `Megacomplex.finalize_data()` → `Element.create_result()`

v0.7 plugins *mutated* one large per-dataset `xr.Dataset` — and with `add_svd=True` even
mutated the scheme's input datasets in place. v0.8 plugins *construct* their own result
datasets, keyed by element label, with `element_uid` provenance for downstream plotting
(`glotaran/model/element.py`). This converts an in-place mutation protocol into a
value-returning contract. This is the change most worth defending.

### 4. Persistence became pydantic serialization itself

v0.7 used bespoke dataclass helpers (`file_loadable_field`, `asdict`/`fromdict` in
`glotaran/project/dataclass_helpers.py`) plus a separate `folder` plugin. v0.8 does
everything through `model_dump(mode="json", context={"save_folder": ...})`, with field
serializers writing sidecar files (`glotaran/project/result.py`,
`glotaran/optimization/objective.py`). One mechanism instead of three.

### 5. The convenience layer was amputated

`Project`, the CLI, the `glotaran.analysis` shims, and the `folder`/`legacy` IO plugins
are gone. The entry point collapsed from `optimize(scheme)` + `Project.optimize()` to a
single `Scheme.optimize()` (`glotaran/project/scheme.py`).

---

## What improved

- **The numerical core got leaner.** v0.7 had six provider classes in two parallel
  hierarchies (`{Data,Matrix,Estimation}Provider` × `Unlinked/Linked`) with internal
  caching. v0.8 has three composable value-like objects (`OptimizationData`,
  `OptimizationMatrix`, `OptimizationEstimation`) driven by one `OptimizationObjective`.
  The tests confirm the win: they exercise `OptimizationMatrix.combine/link/reduce` as
  plain functions over values rather than poking at provider caches
  (`tests/optimization/test_matrix.py`).
- **Validation is now enforced.** v0.7's `Model.validate()` was advisory, and
  `optimize()` never called it — a documented footgun in both v0.7 analyses. v0.8's
  `Optimization.__init__` collects issues and raises `GlotaranModelIssues` before any
  numerical work starts. **[verified]**
- **The result API is honest.** Three levels — `Result` / per-dataset
  `OptimizationResult` / `OptimizationInfo` — with typed fields, `fit_decomposition`,
  per-element datasets, and per-dataset metadata, versus v0.7's flat dataclass wrapping
  one kitchen-sink dataset per label. Minimal saving (`SAVING_OPTIONS_MINIMAL`) and
  referencing original input files instead of copying them are practical wins for large
  datasets.
- **Round-trip fidelity is designed in.** `exclude_unset` dumps,
  `ExtendableElement._original`, and the scheme round-trip test
  (`Scheme.from_dict(d).model_dump(exclude_unset=True) == d` in
  `tests/project/test_scheme.py`) make spec preservation a tested contract rather than an
  accident.
- **`extends` element inheritance** is a real new modeling capability (for example
  kinetic rate-matrix extension) with no v0.7 equivalent.
- **Dead weight was removed:** the deprecated CLI, `glotaran.analysis` shims, and the
  `folder`/`legacy` plugins.

---

## What regressed

Each item below was checked directly in code, not only taken from the documents.

### R1. Non-negative parameter standard errors are now wrong — **[verified]**

v0.7's `Optimizer` transformed the errors of log-space (`non_negative`) parameters back
to linear space: `standard_error = value * (exp(error) - 1)`
(`main:glotaran/optimization/optimizer.py:307-311`). v0.8's
`calculate_parameter_errors` (`glotaran/optimization/info.py:190`) assigns the raw
log-space error to every parameter. The log transform itself survived in
`Parameter.get_value_and_bounds_for_optimization`, so *optimization* is correct, but the
*reported uncertainty* for non-negative parameters is not.

**This is the most serious item on the list: silent, numerical, and user-facing.**

### R2. `ParameterHistory` records only the initial point — **[verified]**

v0.7 appended per objective evaluation. v0.8 appends once in `Optimization.__init__`
(`glotaran/optimization/optimization.py:93-94`) and never again. The saved
`parameter_history.csv` is now a stub.

### R3. `add_svd` is a dead flag — **[verified]**

Stored as `self._add_svd` in `Optimization.__init__`, never read; SVDs are
unconditionally computed in `objective.py`. The API promises control it does not have,
and every result pays SVD computation time.

### R4. The compatibility discipline was abandoned, not migrated

v0.7 had a rigorous deprecation framework: enforced removal deadlines
(`check_overdue`), YAML key shims, and tests that fail the build when cleanups are
overdue. v0.8 changes the entire spec vocabulary (`megacomplex` → `elements`,
`irf` → `activations`) with **no migration path**. The deprecation module still exists,
but nothing calls its YAML shims, and there is still no schema version field. A 0.7
user's specs and saved results are simply dead. For a scientific tool with published
tutorials, this is the highest-impact ecosystem regression.

### R5. `objective.py` is a new god-module

963 lines mixing residual construction, result reconstruction, the `OptimizationResult`
pydantic model, *and* its file-writing serializers
(`glotaran/optimization/objective.py`). v0.7, whatever its faults, kept numerics
(providers) and persistence (folder plugin) apart. Both v0.8 documents independently
flag this coupling.

### R6. New hazard class: import-time frozen unions

v0.7 resolved megacomplex types through the registry *at YAML load time*, so
late-registered plugins worked. v0.8's `ElementType` union is materialized when
`glotaran/project/library.py` is imported — an element class defined after
`glotaran.project` has been imported cannot be parsed into a `ModelLibrary`. This is the
price of pydantic validation, but it is currently undocumented and untested.

### R7. Loose ends that erode trust — **[verified]**

- `pyproject.toml` still declares the console script `glotaran = "glotaran.cli.main:main"`
  pointing at a deleted module (broken on install).
- `glotaran/testing/plugin_system.py` still patches a nonexistent `megacomplex` registry.
- `OptimizationInfo.success` means "SciPy returned an object", not SciPy's own
  convergence flag — carried over from v0.7 unfixed.
- `ChainMap` merging in `Optimization.run()` silently shadows duplicate dataset labels
  across experiments (the code's own TODO admits this).
- The full/global model branch bypasses constraints, relations, penalties, and result
  hooks without raising.

---

## Scientific parity vs. architectural compatibility

The rewrite's compatibility break must not be confused with a failure of scientific parity.
They are different questions:

- **Architectural/file compatibility** asks whether v0.7 public APIs, YAML specifications, saved
  results, and workflow conventions load directly in v0.8. They generally do not; the rewrite
  has no integrated schema migration layer.
- **Scientific parity** asks whether equivalent analyses reconstruct the same fitted data and
  preserve the intended weighting, linking, constraints, and parameter semantics after an
  explicit translation.

The validation workspace tests the second question externally rather than forcing v0.8 result
objects into the v0.7 layout. Its authoritative scenario and revision contract is
`validation/scenarios.yml`; generated reports capture the outcome of each fresh run. Fitted-data
agreement is the primary scientific metric. Raw parameters and CLP/matrix decompositions remain
secondary where the inverse problem is non-identifiable.

Thus v0.8 can demonstrate scientific parity for validated analyses while still having a serious
migration and persisted-schema gap. Neither finding cancels the other, and run-specific counts or
statuses intentionally do not form part of this architecture document.

## Cross-cutting risks

Four themes cut across the concrete regressions above:

- **Validation fragmentation.** Pydantic improves local schema validation, but there is no single
  public preflight that aggregates unresolved references, dataset dimensions, linking
  compatibility, matrix shapes, and unsupported full/global features before fitting.
- **Ownership and mutation.** `Scheme.optimize()` attaches data to nested models, callbacks mutate
  a shared parameter graph, matrix transforms mutate arrays, and serialization can mutate result
  metadata and options. Declarative-looking objects therefore do not imply immutable execution.
- **Parallel full/global architecture.** The full/global branch bypasses ordinary relations,
  constraints, penalties, and result hooks. New features can silently drift unless support is
  explicitly implemented or rejected.
- **Persistence inside the numerical layer.** `OptimizationResult` serialization and sidecar
  path handling live alongside objective calculation. This makes numerical and storage changes
  unnecessarily capable of breaking one another.

These are architectural consolidation targets, not evidence that the rewrite's domain
decomposition should be reversed.

---

## What can still be improved

In priority order, toward a releasable 0.8:

1. **Fix the standard-error transform** (small, self-contained, scientifically
   important) and re-instate per-iteration parameter history — or delete the artifact.
2. **Ship a spec migration.** Even a best-effort `glotaran migrate` script for 0.7 YAML
   (megacomplex→element, irf→activation, dataset→experiment restructuring), plus a
   `spec_version` field in scheme and result files. The pydantic move makes versioned
   schemas nearly free; not adding one now repeats the mistake that made this rewrite
   breaking.
3. **Split `objective.py`.** Move `OptimizationResult`/`FitDecomposition` and their
   serializers into their own module (or into `glotaran/project`), leaving the objective
   purely numerical.
4. **Resolve the duplicated `residual_function`** — it exists on both `ExperimentModel`
   and `DataModel` and different code paths consult different fields. Do this before
   adding any new solver.
5. **Make the global/full-model branch either equivalent or loud** — raise on
   unsupported constraints/penalties instead of silently ignoring them.
6. **Clean the stale surfaces:** the pyproject console script, the megacomplex testing
   helpers, the dead `add_svd` flag, the empty `cli`/`analysis` directories, and
   validate dataset-label uniqueness across experiments at `Scheme` construction.
7. **Decide the workflow-layer question deliberately.** Removing `Project` is defensible
   (it was scope creep), but users lose numbered runs and `Result.recreate`/`verify`.
   Either bless `pyglotaran-extras` as the workflow home in the documentation, or add
   one thin, tested helper in `glotaran/project`.

---

## Biggest differences at a glance

| Axis | v0.7.x (main) | v0.8.x (staging) | Verdict |
|---|---|---|---|
| Schema technology | Homegrown attrs framework | pydantic v2 | Clear win |
| Model shape | One dynamic `Model` + `Project` | Library / Experiment / DataModel | Clear win |
| Plugin result contract | `finalize_data` mutation | `create_result` construction | Clear win |
| Numerical core | 6 caching providers | 3 composable value objects | Win (simpler, better tested) |
| Validation | Advisory, skippable | Enforced pre-optimization | Win |
| Persistence | dataclass helpers + folder plugin | pydantic serde with context | Win in design; couples numerics to IO in `objective.py` |
| Compatibility | Enforced deprecation framework, shims | Hard break, no migration | Regression |
| Diagnostics fidelity | Correct log-space errors, full history | Both degraded | Regression (fixable, small) |
| Workflow / UX layer | `Project`, CLI | Nothing | Deliberate loss; needs a stated replacement story |

---

## Evidence and scope

This comparison describes architecture, responsibility boundaries, and known implementation
risks. It does not replace the version-specific guides, executable tests, or fresh validation
runs. Code paths and tests cited inline are the evidence for individual claims.

The comparison is intentionally tied to the named architectures—released v0.7.4 and the v0.8.0
rewrite—rather than to a generation date, authoring model, or transient validation report. If a
later v0.8 revision changes one of the verified behaviors, update the relevant claim and its code
reference as part of that change.
