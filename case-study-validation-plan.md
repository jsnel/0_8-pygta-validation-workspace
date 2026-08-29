# External Case-Study Visual-Evidence Preparation Plan

Prepare reproducible v0.7.4 reference and v0.8 staging evidence for three
external case-study repositories. The deliverable is a package for subsequent
side-by-side human inspection. This work stops before subjective plot review,
acceptance of scientific parity, or final classification of numerical
differences.

## Authority and required reading

Apply these sources in order:

1. `AGENTS.md` for workspace-wide policy and scientific comparison rules.
2. This plan for case-study scope, checkpoints, and stopping conditions.
3. `validation/README.md` and `validation/AGENT_RERUN.md` for existing runner,
   manifest, comparison, and regression-check conventions.
4. `skills/pyglotaran-v07-to-v08-migration/SKILL.md` and
   `skills/pyglotaran-v07-to-v08-migration/references/model-spec-mapping.md`
   before changing any staging model or caller.

Do not modify pyglotaran core, commit changes, delete unrelated work, overwrite
source notebooks, or transform results merely to force numerical agreement.

## Repositories

- `https://github.com/ism200/pygta-protocol-streak-PS1`
- `https://github.com/ism200/pygta-protocol-TA-PS1`
- `https://github.com/glotaran/pub-2023-05-van_Stokkum_et_al`

Use a stable slug for each repository and keep its checkouts under:

```text
temp/case-studies/<slug>/reference
temp/case-studies/<slug>/staging
```

Pin one source commit per repository. Both checkouts must start at that exact
commit, including submodule and Git LFS state where applicable. Keep the
reference checkout unchanged. Record the staging diff and its hash because the
migration will intentionally leave the staging checkout dirty and uncommitted.

## Evidence layout

Every execution uses one new UTC timestamp and writes only beneath:

```text
validation/runs/case-studies/<timestamp>/<slug>/reference
validation/runs/case-studies/<timestamp>/<slug>/staging
validation/comparisons/case-studies/<timestamp>/<slug>
```

The timestamp root contains `visual-review-manifest.json` and a concise
`visual-review-manifest.md`. Do not reuse artifacts from an older run in a new
comparison.

If case-study metadata or adapters are needed, keep them isolated under
`validation/case_studies/`. Do not add these external cases to
`validation/scenarios.yml` during this evidence-preparation goal: that file is
the authoritative 11-notebook/14-leaf baseline contract. Existing tools may be
extended only through a backward-compatible optional manifest or adapter, with
the existing default behavior and tests preserved.

## Checkpoints

### 1. Establish a clean baseline

- Inspect root and nested repository status and preserve unrelated user work.
- Record the pinned pyglotaran reference and staging revisions and the Python
  executables used.
- Record package versions, lockfile or environment hashes, dependency overlays,
  platform, and relevant thread/BLAS environment settings.
- Verify the current validation-side focused tests before changing shared
  validation tooling.

### 2. Pin and inventory each case study

- Resolve and record the remote URL, default branch or tag, full source commit,
  submodule commits, and Git LFS state.
- Create the reference and staging checkouts from the same source commit and
  verify matching tracked-tree hashes before migration.
- Inventory notebooks, scripts, model and parameter files, datasets and their
  hashes, dependency declarations, custom plugins, analysis entry points, fit
  calls and budgets, random seeds, plotting calls, saved results, and expected
  outputs.
- Select the relevant executable notebooks or scripts with a short rationale.
  Do not assume every notebook is part of the scientific analysis.
- Detect missing/private data, unavailable dependency pins, network downloads,
  interactive-only steps, and unsupported plugins before migration.

The inventory is saved in machine-readable and human-readable form under the
fresh timestamp root.

### 3. Execute the untouched v0.7.4 reference

- Use the pinned v0.7.4 environment and the original case-study files.
- Execute from an isolated copy beneath the reference output directory so the
  checkout and source notebooks remain unchanged.
- Capture the exact command, working directory, start/end time, exit code,
  stdout, stderr, environment metadata, and input/output hashes.
- Save the executed notebook copy, all file-based plots/results, and inline
  image outputs extracted from the executed notebook.
- If the original analysis cannot run, preserve the failure log and classify
  the repository as `BLOCKED_REFERENCE`; do not migrate around an unknown
  reference behavior.

### 4. Migrate only the staging checkout

- Preserve every original v0.7 file. Add clearly named v0.8 scheme and caller
  files or migrated notebook copies; do not rewrite the legacy inputs in place.
- Inventory and map every legacy dataset group, element, scale, activation,
  constraint, relation, penalty, weight, and optimizer option.
- Use v0.8 `library` and `experiments`, `load_scheme`, and
  `scheme.optimize(parameters=..., datasets=...)` according to the migration
  skill.
- Preserve dataset labels, parameter labels and expressions, fit budgets, and
  numerical intent unless a change is explicitly justified in the migration
  log.
- Stop with `BLOCKED_MIGRATION` for unsupported custom plugins, ambiguous
  multiple k-matrices, intentional unlinked-CLP behavior without an equivalent,
  missing data, or any field whose semantics cannot be established. Never drop
  such behavior silently.
- Save the full staging diff plus file hashes in the evidence package.

### 5. Validate each migrated analysis

For every migrated scheme exercised by the selected analysis, use the pinned
v0.8 staging environment to perform and log:

1. parameter-aware schema generation when practical;
2. scheme loading;
3. `dry_run=True` optimization with the exact dataset labels;
4. at least one real fit using the reference initialization and comparable fit
   controls.

Loading proves schema validity only. The dry run proves structural optimization
setup, and the real fit supplies behavioral evidence. A failure at any stage is
packaged as `BLOCKED_STAGING` with the narrowest demonstrated cause.

### 6. Execute the migrated staging analysis

- Execute an isolated copy of each selected migrated notebook or script beneath
  the fresh staging output directory with a headless plotting backend.
- Do not overwrite either the original v0.7 notebook or the migrated source
  notebook.
- Capture the same commands, logs, metadata, hashes, executed notebook copies,
  file-based outputs, and extracted inline images as for the reference run.
- Confirm that reference and staging runs used matching case-study data,
  parameter initialization, fit budgets, and relevant analysis settings. Record
  every justified mismatch explicitly.

### 7. Produce automated comparison evidence

- Reuse the existing loaders, compatibility projection, label-aware comparison,
  and normalized-RMS calculations where their assumptions fit the case study.
- Add only small case-study-specific adapters or optional metadata needed to
  expose stable semantic arrays. Keep native v0.8 artifacts alongside any
  compatibility projection.
- Compare canonicalized inputs exactly. Compare fitted data first, followed by
  residuals, parameters, CLP/matrix decompositions, optimization diagnostics,
  and result metadata where available.
- Report metrics, shapes, labels, tolerances, missing artifacts, fit success,
  and function-evaluation counts. Automated output may use `PASS`,
  `REVIEW_REQUIRED`, `MISSING_ARTIFACT`, or a `BLOCKED_*` status.
- Do not assign `EXPECTED_DIFFERENCE`, `REGRESSION`, scientific parity, or a
  root-cause classification during this goal. Those require the subsequent
  human/scientific review.

### 8. Verify the package and protect the established baseline

- Check that every manifest path exists, every listed artifact hash matches,
  and every executed notebook is readable.
- Run focused tests for new adapters or runner behavior.
- If an existing shared runner, comparator, compatibility module, or staging
  input was changed, run the complete procedure in
  `validation/AGENT_RERUN.md` and confirm the established 11/11 notebooks and
  14/14 result leaves still have no new failure status.
- Do not run the runtime benchmark unless optimizer/runtime behavior or its
  instrumentation was changed; if run, keep it report-only.

### 9. Create the visual-review handoff

For each case study, both visual-review manifests list:

- repository URL, slug, pinned source revision, submodules, and staging diff
  hash;
- reference and staging pyglotaran revisions, Python executables, dependency and
  environment hashes;
- selected analysis entry points and the rationale for selection;
- executed notebook paths, extracted inline-image paths, generated plot/result
  paths, stdout/stderr logs, and command-log paths;
- migration validation outcomes for load, dry run, and real fit;
- automated comparison report path and provisional status;
- known mismatches, missing artifacts, and blockers without subjective or final
  scientific classification;
- changed source and validation-side files plus tests and commands run.

Update `validation/logs/validation-log.md` with the provisional evidence
handoff. Update `changelog.md` only if trackable validation tooling changed.
Do not update baseline acceptance claims in `README.md` or
`validation_plan.md` during this pre-review goal.

## Stopping condition

A repository is `READY_FOR_VISUAL_REVIEW` when its pinned reference and staging
runs are reproducible, its executed notebooks and plots are packaged for
side-by-side inspection, load/dry-run/real-fit evidence is present, and its
automated comparison report is linked from the manifest.

A repository may instead stop at a demonstrated `BLOCKED_*` status when the
manifest contains the failing command, complete log, preserved partial
artifacts, and the narrowest evidence-backed blocker.

The overall goal is complete when all three repositories are either
`READY_FOR_VISUAL_REVIEW` or have a clearly documented `BLOCKED_*` package,
the manifest has passed its path/hash checks, and any required regression tests
have completed. Stop before opening plots for subjective comparison, declaring
scientific parity, assigning final difference classes, or committing changes.
