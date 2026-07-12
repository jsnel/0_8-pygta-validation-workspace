My overall judgment: v0.8 is a substantial architectural rewrite, not an incremental cleanup. The conceptual model is better and more extensible, but the implementation currently has more cross-cutting coupling and operational risk than the cleaner conceptual design suggests.

In short:

> v0.7 had a comparatively monolithic domain model wrapped around a reasonably well-separated provider pipeline.
> v0.8 has a better-composed domain model, but a less clean numerical/runtime implementation and a significantly weaker compatibility story.

I would regard v0.8 as the better long-term foundation—but not yet as architecturally “finished.”

## The fundamental changes

| Area | v0.7.x | v0.8.x | Significance |
|---|---|---|---|
| Domain root | One dynamic `Model` class | `ModelLibrary` + `ExperimentModel` + `DataModel` + `Element` | Fundamental decomposition of the domain model |
| Scientific extension unit | `Megacomplex` | `Element`, optionally contributing a `DataModel` mixin | More granular and composable |
| Workflow facade | Optional filesystem-oriented `Project`; direct `optimize(Scheme)` | No `Project`; `Scheme.optimize()` is the main workflow facade | Large public API and responsibility shift |
| Numerical entry point | `optimize()` → `Optimizer` → `OptimizationGroup` | `Scheme.optimize()` or direct `Optimization` | Numerical core exposed more explicitly |
| Runtime decomposition | `DataProvider`, `MatrixProvider`, `EstimationProvider` | `OptimizationData`, `OptimizationMatrix`, `OptimizationObjective`, `OptimizationEstimation` | Providers replaced by explicit numerical value/runtime objects |
| Dataset organization | Dataset models collected into dataset groups | Datasets live inside named experiments | Better representation of multi-experiment analysis |
| Configuration technology | Mostly attrs/dataclass-based declarative graph | Pydantic-based typed objects and discriminated unions | Much stricter schemas, but more dynamic-schema complexity |
| Results | One top-level `Result` containing enriched xarray datasets | Per-dataset `OptimizationResult`, run-level `OptimizationInfo`, top-level persisted `Result` | Better separation of numerical, diagnostic, and workflow output |
| Model reuse/composition | References inside one monolithic model | Named element library, `extends`, runtime resolution | Stronger reuse and declarative composition |
| Compatibility | Old schema with some deprecation machinery | Entirely new schema without explicit schema version or migration dispatcher | The largest regression/risk |

The largest conceptual change is that “the model” is no longer one object. In v0.8 it is an aggregate:

```text
ModelLibrary
    └── named Elements and model items

ExperimentModel
    └── one or more DataModels

DataModel
    └── references Elements and owns dataset-level configuration
```

That is much closer to the actual domain: reusable scientific components, dataset-specific composition, and experiment-level sharing are distinct concerns.

## What improved

### 1. Scientific components are more reusable and composable

Moving from `Megacomplex` to `Element` is more than terminology.

In v0.7, a megacomplex was simultaneously:

- a registered plugin type;
- a contributor to the dynamically generated `Model`;
- a source of matrix columns;
- a contributor to dataset-model fields;
- a result-finalization hook.

That made the extension point powerful but fairly coarse.

In v0.8, an element can contribute:

- matrix behavior through `calculate_matrix()`;
- optional dataset configuration through a `DataModel` mixin;
- element-specific result construction;
- reusable library identity and inheritance through `extends`.

That is a better separation. Scientific behavior is now more naturally expressed as independently reusable elements rather than as pieces of one generated monolithic model class.

### 2. `ModelLibrary` is a good addition

The library gives named scientific components a real ownership boundary. The old model dictionaries were technically similar, but the new library makes their semantics explicit:

- mapping keys define stable labels;
- elements can extend other elements;
- extension chains are resolved centrally;
- the original declaration can be retained for serialization;
- experiments and datasets refer to library objects by label.

This is a meaningful improvement for larger analyses and plugin-provided scientific models.

### 3. Experiments are now first-class

The old `DatasetGroup` was mostly a numerical grouping mechanism. The new `ExperimentModel` is a domain-level concept.

That makes several things clearer:

- which datasets share CLPs;
- which residual algorithm applies;
- what constitutes one experiment;
- how several experiments participate in one outer optimization;
- where experiment-wide configuration belongs.

This is a better abstraction than treating grouping primarily as an optimizer implementation detail.

### 4. The numerical concepts are more explicit

`OptimizationData`, `OptimizationMatrix`, and `OptimizationEstimation` are good names and potentially good architectural boundaries. They describe concrete numerical artifacts:

- prepared and oriented data;
- a matrix plus its CLP-axis labels;
- one conditional-linear estimation;
- the objective that coordinates them.

This can make the numerical core easier to test directly than a hierarchy of linked/unlinked provider subclasses.

The v0.8 tests apparently construct `Optimization` directly, below `Scheme`. That is good evidence that the engine remains separable from the workflow layer.

### 5. Results have better conceptual layering

The distinction between:

- per-dataset `OptimizationResult`;
- run-level `OptimizationInfo`;
- workflow/persistence-level `project.Result`;

is a significant improvement.

In v0.7, `Result` was a rather broad aggregate containing both optimization metadata and enriched xarray datasets. The new structure has a better chance of keeping:

- scientific output,
- solver diagnostics,
- provenance,
- and persistence

from becoming one undifferentiated object.

The implementation has not fully achieved that separation yet, but the model is better.

### 6. Pydantic improves configuration contracts

The switch provides:

- forbidden unknown fields;
- discriminated unions;
- generated JSON Schema;
- better typed parsing;
- structured serialization hooks;
- earlier configuration errors.

For YAML-driven applications and editors, this is materially useful.

## What regressed

### 1. Compatibility and migration regressed severely

This is the most important issue.

v0.8 changes nearly every persistent identity:

- `Model` disappears;
- `Megacomplex` becomes `Element`;
- datasets are reorganized into experiments;
- model fields and nesting change;
- plugin type identities change;
- result structure and serialization change;
- public entry points change;
- the `Project` class and module-level `optimize()` disappear.

Yet the v0.8 architecture report identifies:

- no explicit schema-version field;
- no migration dispatcher;
- no enforced producer version;
- Pydantic `extra="forbid"`;
- saved defaults that may silently change meaning;
- class/module identities embedded in persisted data.

That combination is dangerous. It makes the new architecture internally stricter while making cross-version compatibility less manageable.

For a scientific package, reproducibility includes the ability to identify and interpret old model and result files. This deserves to be treated as a first-class architecture concern, not as deferred serializer work.

### 2. The clean provider separation was lost

v0.7 had a relatively understandable runtime split:

```text
DataProvider
MatrixProvider
EstimationProvider
OptimizationGroup
Optimizer
```

Those responsibilities were imperfect, but their direction was clear.

In v0.8, much of that orchestration has accumulated in `OptimizationObjective` and especially `objective.py`. According to the report, that file participates in:

- objective calculation;
- linked/unlinked behavior;
- full/global behavior;
- result reconstruction;
- metadata construction;
- Pydantic result serialization;
- sidecar saving and loading;
- path enumeration.

That is a regression. A numerical objective should not know the result-bundle file layout.

The report’s own recommendation—do not enlarge the `objective.py` pattern—is correct but understated. This should be actively decomposed.

### 3. Validation became more fragmented

v0.7 had an explicit `Model.validate()` / `Scheme.validate()` mechanism, although optimization did not always invoke it automatically.

v0.8 improves construction-time validation through Pydantic, but there is no single public validation pass that answers:

> “Can this scheme, with these data and parameters, execute successfully?”

Instead, validation occurs during:

- Pydantic parsing;
- library extension resolution;
- runtime element resolution;
- recursive model-item validation;
- data preparation;
- matrix construction;
- conditional solving;
- SciPy evaluation.

Some distribution is unavoidable because data-dependent checks require runtime data. But the loss of an explicit preflight API is a regression in usability and diagnosability.

A scientific user should be able to request a complete, structured validation report without starting optimization.

### 4. Runtime mutability is more pervasive than the object model implies

The v0.8 design looks more declarative, but the implementation still mutates broadly:

- `Scheme.optimize()` attaches data into nested `DataModel`s;
- dataset I/O updates xarray attributes;
- one private `Parameters` object is mutated by solver callbacks;
- standard-error calculation mutates parameters;
- matrix weighting, scaling, and reduction mutate arrays;
- matrix slicing can expose views into parent arrays;
- result creation and serialization mutate metadata.

This undermines:

- repeatability;
- safe reuse;
- concurrency;
- reasoning about ownership;
- future parallel evaluation.

v0.7 also had mutable providers and parameters, but mutation was more clearly confined to runtime provider objects. In v0.8, mutable state crosses declarative, numerical, result, and persistence boundaries.

### 5. The public API has become less obvious

Removing `Project` is defensible. Removing the monolithic `Model` is architecturally sensible. But simultaneously removing the simple module-level `optimize()` leaves two audiences sharing less obvious APIs:

- normal users should call `Scheme.optimize()`;
- numerical/core users construct `Optimization`.

That can work, but the root/subpackage import story is currently austere, and the documentation reportedly still uses historical concepts. The result is a conceptual mismatch between:

- old documentation;
- changelog terminology;
- package names such as `project`;
- serializer names such as `ProjectIoInterface`;
- current runtime APIs.

This is partly documentation debt, but terminology and import surfaces are architectural concerns when a public API has been rewritten.

### 6. Several runtime correctness contracts are weaker

The v0.8 report exposes several concerning implementation details:

- final parameters rely on the last objective callback rather than explicitly applying `solver_result.x`;
- `OptimizationInfo.success` does not necessarily reflect `solver_result.success`;
- `cost` and chi-square metrics may be based on different residual evaluations;
- parameter history is not recorded as its name suggests;
- optimization history is reconstructed from parsed SciPy stdout;
- `add_svd` is stored but apparently ineffective;
- duplicate dataset labels can be silently shadowed;
- CLP union ordering is set-dependent;
- residual configuration has two sources of truth;
- linked group identifiers concatenate labels without a separator.

These are not merely aesthetic problems. They affect determinism, reporting correctness, extension safety, and reproducibility.

### 7. Full/global models remain a parallel architecture

This problem exists in both versions, but it appears more visible and arguably more entrenched in v0.8.

The full/global branch reportedly bypasses:

- ordinary CLP relations;
- constraints;
- penalties;
- normal element result hooks;
- normal data-model result hooks.

That means every new feature must answer two questions:

1. How does it behave in the ordinary pipeline?
2. Has someone separately implemented it in the full/global pipeline?

This is a classic source of feature drift. It should be treated as an architectural debt item, not just a testing concern.

## The biggest differences, ranked

### 1. Composition replaced the monolithic model

This is the most important positive change.

`ModelLibrary + ExperimentModel + DataModel + Element` is a richer and more accurate domain model than `Model + DatasetModel + Megacomplex`.

### 2. The workflow API was inverted

v0.7:

```text
optional Project
    → Scheme
    → optimize()
```

v0.8:

```text
Scheme.optimize()
    → Optimization
```

The filesystem-oriented `Project` abstraction is gone, and `Scheme` now owns more workflow responsibility.

### 3. The runtime pipeline shifted from service/provider objects to numerical objects

v0.7 emphasized orchestrating provider services.
v0.8 emphasizes data, matrix, estimation, and objective objects.

This is a promising direction, but the objective currently owns too much.

### 4. The new schema system is stricter but more dynamic

Pydantic and discriminated unions improve parsing, but dynamic `DataModel` mixins, plugin-dependent unions, import-time materialization, cached JSON Schema, and set-dependent base ordering introduce nondeterminism and lifecycle sensitivity.

### 5. The persistence surface became more sophisticated without acquiring versioning

The result bundle is more structured, but it is also more coupled and more fragile. Persistence now badly needs an explicit schema architecture.

## What I would improve next

My priorities would be:

### 1. Add explicit persisted schema versions and migration

At minimum:

- `scheme_schema_version`;
- `result_schema_version`;
- producer package version retained exactly as saved;
- ordered migration functions between schema versions;
- a dedicated v0.7 importer or conversion tool;
- compatibility fixtures committed as immutable test data.

Do not use the package version as the schema version. They evolve at different rates.

### 2. Split numerical result construction from persistence

A desirable direction would be:

```text
OptimizationObjective
    → NumericalEvaluation

ResultAssembler
    → OptimizationResult

ResultSerializer
    → manifest and sidecar files
```

`objective.py` should contain no filesystem serialization logic.

### 3. Introduce an explicit validation/preflight API

For example:

```python
report = scheme.validate(parameters=parameters, datasets=datasets)
report.raise_for_errors()
```

The report should aggregate:

- unresolved labels;
- missing parameters;
- duplicate dataset identities;
- element compatibility;
- dimensions;
- linking compatibility;
- matrix shapes;
- unsupported full/global features;
- residual solver compatibility.

It should distinguish static validation from checks requiring data or a trial matrix evaluation.

### 4. Make ownership and mutation explicit

I would aim for:

- `Scheme.optimize()` not mutating the scheme;
- prepared data copied into runtime-owned objects;
- matrix transforms returning new matrices or clearly named in-place operations;
- parameter evaluation state owned only by `Optimization`;
- standard-error calculation returning updated result parameters rather than mutating shared objects;
- result serialization not mutating results or saving-option defaults.

A simple target invariant would be:

> Running the same `Scheme` twice must not depend on whether it was previously optimized or saved.

### 5. Unify the ordinary and full/global pipelines

Ideally, full/global operation should be expressed as a different matrix construction strategy feeding the same downstream stages:

```text
matrix construction
    → relation/constraint reduction
    → weighting
    → CLP estimation
    → penalties
    → result hooks
```

If a feature genuinely cannot apply to full/global models, the system should reject it explicitly during validation.

### 6. Stabilize plugin and schema construction

Replace set-dependent construction with deterministic ordering and explicit conflict rules.

The following should not depend on import order:

- `DataModel` mixin order;
- typed union order;
- JSON Schema contents;
- CLP column union order;
- short-name plugin conflict resolution.

A schema registry should either support invalidation when plugins are added or be frozen explicitly at application startup.

### 7. Fix numerical/reporting semantics before adding more solvers

In particular:

- assign `solver_result.x` explicitly;
- define `success` from the solver’s actual success state;
- compute all final statistics from one explicit final evaluation;
- record parameter history consistently;
- stop parsing stdout for structured optimizer history;
- make `add_svd` effective or remove it;
- consolidate the residual-function setting into one source.

## Bottom line

I think the v0.8 domain architecture is clearly better than v0.7:

- more composable;
- more faithful to the scientific domain;
- better structured for reusable model elements;
- better suited to multiple experiments;
- better typed;
- better positioned for editor/schema tooling.

But v0.7’s runtime architecture was, in one important sense, cleaner: the data, matrix, and estimation responsibilities were visibly separated into providers, while v0.8 has concentrated too much orchestration, result construction, and persistence inside the objective layer.

So my concise verdict is:

> v0.8 improves the architecture of modeling, composition, and extension, but regresses the architecture of compatibility, validation, mutation control, and separation between numerics and persistence.

The highest-value next work is not another large redesign. It is consolidating the new foundation:

1. versioned migration;
2. objective/result/serialization separation;
3. deterministic schema/plugin construction;
4. non-mutating execution boundaries;
5. unified validation;
6. unified ordinary/full-global execution.

Those changes would turn v0.8 from a promising rewrite into a substantially stronger architecture than v0.7 across the board.

Compared reports: [v0.7 GPT analysis](</C:/src/pyglotaran/_pyglotaran_architecture_/v0.7.4/architecture-per-gpt-5.6.md>), [v0.7 Fable/GPT synthesis](</C:/src/pyglotaran/_pyglotaran_architecture_/v0.7.4/architecture-fable-5-combined-with-gpt-5.6.md>), [v0.7 GPT/Fable synthesis](</C:/src/pyglotaran/_pyglotaran_architecture_/v0.7.4/architecture-gpt-5.6-combined-with-fable.md>), and [v0.8 architecture](</C:/src/pyglotaran/_pyglotaran_architecture_/v0.8.0/architecture-gpt-5.6-sol-max.md>).