# v0.7.4–v0.8 staging parity remediation plan

## Summary

Bring the v0.8 staging validation results into scientifically meaningful agreement with v0.7.4 by:

1. restoring complete result coverage;
2. correcting translated example inputs;
3. expanding an external compatibility layer that projects both result formats into a v0.7-compatible semantic view;
4. fixing metadata and weighted-result reporting;
5. investigating numerical differences in increasing order of difficulty; and
6. making only narrowly scoped pyglotaran changes when a confirmed package defect cannot be addressed in validation tooling.

The compatibility layer must live under `validation/` and must not require broad changes to the pyglotaran API, result model, or persistence architecture.

## Current baseline and observations

Pinned environments:

- v0.7.4 parent: `temp/pyglotaran-main-dev`
- v0.8 staging parent: `temp/pyglotaran-staging-dev`
- Both use Python 3.10 and independent `.venv` environments.
- All 11 pinned validation notebooks currently execute successfully on both branches.
- v0.7 core validation: 577 tests passed after installing `validation/requirements.txt`.
- v0.8 core tests: 424 passed, 9 expected failures.
- v0.8 extras tests: 133 passed, 2 failures, 10 errors. These currently reflect stale v0.7-style fixtures/API usage, especially calls expecting `Scheme.optimize(datasets=...)`; classify and port these tests separately rather than changing the v0.8 API solely for them.

Existing reports:

- `validation/comparisons/v07-v08-detailed.md`
- `validation/comparisons/v07-v08-detailed.json`
- `validation/README.md`
- `validation/logs/validation-log.md`

Current impact ranking:

| Priority | Scenario/root cause | Evidence |
|---:|---|---|
| 1 | Transient-absorption target input mismatch | Global interval `[720, 890]` uses weight `0.2` in v0.7 and `0.1` in staging; fitted-data normalized RMS difference `2.785e-3`; maximum parameter-relative difference `25.2%`. |
| 2 | Unbounded `rates.k3d2` path | Approximately `1.25e7` in v0.7 versus `1.94e25` in staging, while fitted-data normalized RMS difference is only `1.383e-5` and chi-square is effectively equal. |
| 3 | Missing or collapsed result artifacts | Staging does not save `ex_doas_beta`; spectral-constraint outputs do not preserve the four v0.7 leaf variants. |
| 4 | Missing weighted-RMSE metadata | `weighted_root_mean_square_error` is absent from 15 staging dataset metadata entries. |
| 5 | Spectral-guidance decomposition differences | `rates.k2` differs by `3.679e-3` relative, but fitted-data normalized RMS is only `2.519e-7`; CLP and matrix differences are much larger than reconstructed-fit differences. |
| 6 | Weighted scale drift | `simultaneous_analysis_3d_weight` has fitted-data normalized RMS difference `2.446e-5`; `scale.3` differs by `2.596e-5`; chi-square is effectively equal. |
| 7 | Result-schema differences | v0.8 splits results across files and uses names such as `amplitude_label`/`amplitude` where v0.7 uses `clp_label`/`clp`. |

Common comparison currently covers nine leaf scenarios. Missing artifacts are:

- missing in v0.7: `ex_spectral_constraints`;
- missing in staging: `ex_doas_beta/target_analysis`;
- missing as separate staging leaves:
  - `ex_spectral_constraints/no_penalties`;
  - `ex_spectral_constraints/no_penalties_first_run`;
  - `ex_spectral_constraints/with_penalties`;
  - `ex_spectral_constraints/with_penalties_first_run`.

## Ordered implementation plan

### 1. Freeze the baseline and establish the scenario matrix

Record the exact parent, submodule, lockfile, Python, and package revisions for both environments.

For every scenario, record:

- stable scenario ID;
- v0.7 notebook or script;
- v0.8 equivalent notebook or script;
- data files and hashes;
- model/scheme files and hashes;
- initial parameters and fixed/free parameters;
- weights, constraints, relations, optimizer, tolerances, and random seed;
- expected output leaves;
- comparison adapter and acceptance tolerances.

Run both branches from clean copies using:

```powershell
temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/run_examples.py ...
temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/run_examples.py ...
```

Preserve raw outputs as immutable evidence. Do not compare regenerated outputs against previously generated artifacts without recording the new source manifest.

### 2. Restore complete result coverage

Fix the staging example and validation fixture issues before investigating numerical behavior.

Required changes:

- Re-enable and verify result saving in the staging `ex_doas_beta` notebook.
- Preserve the four spectral-constraint result variants as separate, stable scenario leaves.
- Add a manifest entry for every expected output leaf.
- Make missing result files a hard comparison failure for declared common scenarios.
- Keep staging-only scenarios explicitly marked as staging-only rather than comparing them to nonexistent v0.7 results.
- Verify every saved result can be reloaded in the originating environment.

This work belongs primarily in the staging example/validation layers, not in pyglotaran core.

Acceptance gate:

- every declared common scenario produces all expected result artifacts;
- no result is silently omitted because a notebook save call was commented out;
- each result leaf has a stable scenario ID.

### 3. Correct translated input equivalence

Before diagnosing optimizer behavior, compare normalized v0.7 model inputs with v0.8 schemes.

For `study_transient_absorption/target_analysis`, correct the staging translation so the global interval `[720, 890]` uses the v0.7-equivalent weight `0.2`, unless a deliberate scientific change is documented.

Compare and record:

- data paths and file hashes;
- coordinate order and ranges;
- model topology;
- dataset labels;
- weights;
- initial values;
- parameter bounds;
- fixed/free status;
- relations and constraints;
- optimizer method and tolerances;
- residual and penalty settings.

Add a translation test that fails when the normalized v0.7 and v0.8 specifications differ unexpectedly.

Rerun the target scenario only after this input-equivalence test passes.

### 4. Expand the external compatibility layer

Create a validation-side compatibility package, for example:

```text
validation/
  compatibility/
    __init__.py
    schema.py
    load_v07.py
    load_v08.py
    normalize.py
    metrics.py
    compare.py
    tests/
```

The layer must expose a stable semantic result model containing:

- scenario and baseline provenance;
- dataset labels;
- labeled input, fitted-data, residual, CLP, matrix, and decomposition arrays;
- optimized parameters keyed by parameter label;
- parameter uncertainties and bounds where available;
- objective and RMSE diagnostics;
- weighted diagnostics;
- result metadata;
- structural annotations describing transformations or missing fields.

The adapter must:

- read the monolithic v0.7 result layout;
- read the split v0.8 result layout;
- canonicalize `amplitude_label` to `clp_label` and `amplitude` to `clp`;
- transpose arrays by named dimensions, never by positional assumption;
- align datasets and parameters by labels;
- map `scale` and `dataset_scale` into one canonical diagnostic field;
- map equivalent metadata names;
- preserve raw values and record every transformation;
- distinguish schema-only differences from numerical differences;
- never silently drop a result variable.

If staging lacks weighted RMSE but contains sufficient data, residual, and weight information, compute it in the compatibility layer and mark it as derived. If weights are unavailable, report the field as unavailable rather than substituting unweighted RMSE.

The primary compatibility contract is a semantic v0.7-compatible comparison view, not byte-identical files. An optional legacy-layout export may be added later, but it is not required for the first parity pass.

Add fixture tests covering:

- v0.7 monolithic results;
- v0.8 split results;
- dimension aliases;
- dataset/file reconstruction;
- label reordering;
- scale metadata;
- derived weighted RMSE;
- missing-field reporting;
- structural-only differences.

### 5. Establish comparison metrics and acceptance thresholds

Use fitted-data agreement as the primary scientific metric. Use residuals, parameters, CLPs, matrices, and metadata as secondary evidence.

Default thresholds:

- input arrays: exact after coordinate canonicalization;
- fitted data and residuals: normalized RMS `≤ 1e-6` for ordinary scenarios and `≤ 1e-5` for weighted/ill-conditioned scenarios;
- identified parameters: relative difference `≤ 1e-4`, with an absolute tolerance for values near zero;
- scalar diagnostics: relative difference `≤ 1e-4` unless derived from differently scaled conventions;
- CLP/matrix arrays: compare by labels and reconstruction impact; do not reject solely on raw decomposition differences when the reconstructed fitted data agrees;
- near-zero residuals: report absolute differences and avoid misleading relative-ratio failures.

Every comparison must classify differences as:

- `PASS`;
- `EXPECTED_DIFFERENCE`;
- `REGRESSION`;
- `BASELINE_FAILURE`; or
- `BLOCKED`.

### 6. Resolve missing weighted diagnostics

First determine whether the missing staging weighted-RMSE fields are only a persistence/reporting omission.

Use the compatibility layer to:

1. locate the original weights;
2. recompute weighted RMSE independently;
3. compare it to v0.7;
4. compare the derived value with any staging internal diagnostic;
5. verify save/load preservation.

If the numerical value is correct but absent from persisted metadata, keep the external derived field as the compatibility solution and add a focused staging persistence test.

Only modify pyglotaran core if the calculation itself is incorrect. Any core change must be limited to emitting or preserving the already-defined diagnostic and must include a focused regression test.

### 7. Diagnose and fix weighted/scale behavior

Use `simultaneous_analysis_3d_weight` as the controlled weighted-analysis case.

Trace separately:

- input weight construction;
- objective weighting;
- residual unweighting;
- scale estimation;
- result metadata serialization;
- final parameter assignment.

Add a synthetic weighted-fit test with analytically known weights and scale behavior. The test must verify that changing weights changes the objective as intended and that saved diagnostics use the same convention as v0.7.

Then rerun:

- `simultaneous_analysis_3d_weight`;
- other weighted scenarios;
- the full common matrix.

The current `2.446e-5` fitted-data normalized RMS and `2.596e-5` scale difference should be reduced to the weighted acceptance threshold or explicitly explained as a documented convention difference.

### 8. Reassess transient-absorption target after input correction

Once the weight mismatch is fixed, rerun `study_transient_absorption/target_analysis`.

If the difference remains material, compare in this order:

1. translated model topology;
2. IRF and dispersion parameter mapping;
3. initial values and bounds;
4. free/fixed parameter status;
5. relations and constraints;
6. residual and penalty construction;
7. ordinary versus full/global execution path;
8. optimizer termination and final-state assignment.

Do not change optimizer behavior until the translated scheme and objective have been proven equivalent.

If a package defect is confirmed, add the smallest possible v0.8 fix and a focused regression test. Avoid broad refactoring of `ModelLibrary`, `Scheme`, `Optimization`, or persistence during this pass.

### 9. Resolve spectral-guidance decomposition differences

For `ex_spectral_guidance`, compare:

- parameter labels and initial values;
- CLP labels and coordinate ordering;
- sign and scale conventions;
- matrix reconstruction;
- shared versus dataset-specific parameters;
- final fitted-data reconstruction.

Because the current fitted-data normalized RMS is only `2.519e-7`, first determine whether the CLP/matrix differences are caused by non-identifiability or a representation convention.

If the reconstructed fit is equivalent:

- normalize labels, signs, and scales in the compatibility layer;
- report raw decomposition differences as expected representation differences;
- retain a reconstruction-equivalence test.

If the decomposition is scientifically meaningful and should be deterministic, add a focused staging test and fix the smallest deterministic ordering or normalization defect.

### 10. Investigate the unbounded `rates.k3d2` result

Treat the `rates.k3d2` discrepancy separately from fit quality.

Required investigation:

- verify identical bounds and initial values;
- inspect parameter transformations and positivity handling;
- compare optimizer termination messages and success flags;
- compare parameter histories;
- profile the objective while varying `rates.k3d2`;
- determine whether the parameter is identifiable from the available datasets;
- verify whether serialization or final-state assignment changes the reported value.

Possible outcomes:

1. If the parameter is identifiable and staging follows a different path, reproduce and fix the optimizer/parameter-transformation defect.
2. If it is genuinely unidentifiable, prevent misleading parity conclusions by documenting the instability and comparing scientifically meaningful fitted data and derived outputs.
3. If v0.7 compatibility requires a bound or parameterization, encode that explicitly in the v0.8 translation layer rather than silently altering pyglotaran’s global behavior.
4. If a package bug is confirmed, add a minimal fix and focused regression test.

Do not force the staging result to equal the v0.7 parameter through post-processing; that would conceal a real reproducibility problem.

### 11. Audit known v0.8 contract risks only when evidence connects them

After the scenario-specific issues are reduced, inspect these architecture-documented risks with focused tests:

- non-negative parameter standard errors being left in log space;
- `ParameterHistory` retaining only the initial point;
- `add_svd` being ignored;
- solver success not reflecting actual solver status;
- full/global paths bypassing relations, constraints, penalties, or result hooks;
- persistence schema lacking version/migration metadata;
- label collisions and ordering instability;
- result metadata mutability;
- stale extras tests and CLI entry points.

Fix only defects that affect an in-scope validation contract. Keep migration, schema normalization, and v0.7 projections in `validation/compatibility/`.

### 12. Iterate and log every change

For each iteration append to `validation/logs/validation-log.md`:

- date and iteration ID;
- source revisions;
- affected scenario IDs;
- observed metrics;
- root-cause hypothesis;
- classification;
- files or branches changed;
- focused test result;
- affected-suite result;
- full-matrix result;
- remaining differences.

After each fix, rerun in this order:

1. focused compatibility or regression test;
2. affected notebook/scenario;
3. affected package or extras suite;
4. complete common scenario matrix.

## Final acceptance criteria

The work is complete when:

- all declared common scenarios produce complete result artifacts;
- all translated inputs have normalized equivalence records;
- the external compatibility layer compares v0.7 and v0.8 results without modifying raw artifacts;
- fitted-data and residual differences meet declared scenario thresholds;
- parameter differences are either within tolerance or explained by a tested identifiability issue;
- weighted RMSE and scale diagnostics are comparable;
- schema/layout differences are classified as expected rather than reported as false regressions;
- every confirmed staging defect has a focused regression test;
- no broad pyglotaran architectural change was introduced solely to support comparison;
- staging-only examples have independent pass criteria;
- the final clean rerun is reproducible from the pinned commits and manifests; and
- the remaining differences are reduced to a small number of documented root causes.

## Assumptions

- The comparison target is semantic scientific equivalence, not byte-identical serialization.
- The compatibility layer is external to pyglotaran and is the preferred place for schema, label, layout, and metadata translation.
- Small, evidence-backed v0.8 correctness fixes are allowed; broad API or architecture refactors are out of scope.
- The v0.7.4 pinned environment remains the reference baseline.
- Ill-conditioned parameters must not be silently overwritten merely to make reports match.
