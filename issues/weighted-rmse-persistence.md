# Investigate weighted RMSE and default-scale persistence

## Status

Open. The compatibility layer makes the semantic comparison complete, but some
v0.8 split result leaves omit metadata that v0.7 persists. Determine whether
this is an intentional schema change or a v0.8 persistence/reporting bug.

## Question

Should v0.8 persist weighted_root_mean_square_error and default dataset_scale
in every dataset result, or is deriving these values in the external
compatibility layer the intended contract?

This concerns result completeness and downstream API behavior. It does not
currently indicate incorrect weighted-RMSE mathematics.

## Evidence

Source comparison: validation/comparisons/v07-v08-semantic.json.

- v0.7 stores dataset-level weighted_root_mean_square_error in monolithic
  NetCDF attributes.
- Several v0.8 split result leaves omit that field when no explicit weight is
  persisted, even though the effective default weight is one.
- Several v0.8 split result leaves omit default dataset_scale equal to 1.
- The compatibility layer derives weighted RMSE from saved residuals and
  explicit/reconstructed weights.
- When no explicit weight exists, the compatibility layer derives it from the
  default unit weight and marks the value as derived.
- It derives default scale 1.0 when v0.8 omits it.
- Derived values agree with v0.7 within comparison tolerances.
- Explicit weighted datasets, including transient-absorption target and 3D
  weighted cases, persist weighted RMSE values that agree closely.

Relevant compatibility code:

- validation/compatibility/load_v08.py
- validation/compatibility/weights.py
- validation/compatibility/metrics.py

Relevant v0.8 persistence code:

- temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/objective.py
- temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/result.py
- temp/pyglotaran-staging-dev/pyglotaran/glotaran/io

## Reproduction

Run the focused compatibility tests:

~~~powershell
& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe -m pytest validation/tests -q --basetemp validation/runs/.pytest-tmp
~~~

Inspect split result metadata under:

validation/runs/staging/output-remediated-2/home/pyglotaran_examples_results_staging

Compare with corresponding v0.7 NetCDF attributes under:

validation/runs/main/output-remediated/home/pyglotaran_examples_results

To inspect the full semantic metadata classification:

~~~powershell
& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/compare_results.py --main-root validation/runs/main/output-remediated/home/pyglotaran_examples_results --staging-root validation/runs/staging/output-remediated-2/home/pyglotaran_examples_results_staging --output validation/runs/.metadata-investigation.json
~~~

## Investigation procedure

1. Trace the v0.8 result lifecycle:
   - weighted residual calculation;
   - weighted RMSE calculation;
   - per-dataset metadata construction;
   - split result conversion;
   - YAML/NetCDF serialization;
   - reload behavior.
2. Determine whether omission is caused by:
   - deliberate None/default suppression;
   - metadata present in memory but lost on save;
   - split-file serialization losing attributes; or
   - default scale not being represented in the v0.8 schema.
3. Verify save/load round trips for no explicit weights, constant weights,
   interval weights, scale equal to one, and scale different from one.
4. Compare persisted values with independently recomputed values. The
   compatibility implementation must remain an independent check, not become
   the source of truth for a core fix.
5. Check downstream consumers and documentation for whether these metadata
   fields are promised as stable public result fields.

## Focused tests to add

First add or extend validation-side tests for:

- v0.8 save/load preservation of weighted RMSE;
- default-scale normalization;
- derived compatibility values when fields are genuinely unavailable;
- distinction between persisted and derived metadata.

Add a v0.8 core persistence regression test only if the public result contract
requires the fields and the save/load trace demonstrates a loss in core code.

## Acceptance criteria

Close as an intentional schema difference if v0.8 documentation explicitly
defines omission of default values, save/load preserves all non-default
diagnostics, and compatibility derivation is complete, tested, and marked as
derived.

Fix v0.8 core persistence if the public result contract promises these fields,
they are present before save but lost after save/reload, or downstream result
consumers cannot obtain the diagnostics without re-executing the fit.

## Non-goals

- Do not copy the v0.7 monolithic file layout into v0.8.
- Do not silently label derived values as persisted.
- Do not change weighted-RMSE mathematics while investigating persistence.
