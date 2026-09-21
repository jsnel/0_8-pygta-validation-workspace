# Investigate weighted RMSE and default-scale persistence

## Status

Resolved — 2026-09-13. The omission was unintentional, and v0.8 core now
persists both fields in every dataset result. Confirmed as a persistence bug
rather than a schema decision: v0.7 writes both unconditionally, and the two
values are scalars. See "Resolution" below.

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

## 2026-08-29 rerun evidence

The fresh comparison at
`validation/comparisons/v07-v08-20260829-162539Z.json` again derives omitted
default weighted-RMSE and scale metadata through the compatibility layer while
all declared leaves remain complete. The recent optimizer fixes did not change
the persistence behavior, so this investigation remains open.

## Resolution — 2026-09-13

### Scope of the omission

Census over the 28 dataset leaves of the final example run
(`validation/comparisons/v07-v08-final-20260906-131441Z.json`, field
`datasets[].metadata.*.staging_source`):

| Field | Persisted by v0.8 | Derived by the compatibility layer |
|---|---:|---:|
| `root_mean_square_error` | 28 | 0 |
| `dataset_scale` | 12 | 16 (`derived_default_scale`) |
| `weighted_root_mean_square_error` | 8 | 20 (`derived_from_default_weight`) |

`scale` was omitted exactly when it equalled 1, and
`weighted_root_mean_square_error` exactly when the dataset carried no weight.

### Root cause

Two independent mechanisms, both in `glotaran/optimization/objective.py`:

1. `OptimizationObjective.create_result_metadata` set
   `weighted_root_mean_square_error=None` whenever the result dataset had no
   `weighted_residual` variable. `OptimizationData.unweight_result_dataset`
   returns early when `self.weight is None`, so that variable never exists for
   an unweighted dataset.
2. `OptimizationResultMetaData` declares `scale: float = 1` and
   `weighted_root_mean_square_error: float | None = None`. The result is saved
   through `model_dump(exclude_unset=True, exclude_defaults=True, ...)` in
   `glotaran/builtin/io/yml/yml.py`, and the same `exclude_defaults=True` dump
   feeds the dataset attributes in `OptimizationResult.fitted_data` and
   `OptimizationResult.inject_meta_data_into_datasets`. Any value equal to its
   field default was therefore dropped on the way to disk.

### v0.7 reference contract

`glotaran/optimization/optimization_group.py:179` in the pinned v0.7.4 tree
writes both unconditionally, and falls back to the unweighted value:

~~~python
result_dataset.attrs["weighted_root_mean_square_error"] = (
    np.sqrt((result_dataset.weighted_residual**2).sum() / size).data
    if "weighted_residual" in result_dataset
    else result_dataset.attrs["root_mean_square_error"]
)

result_dataset.attrs["dataset_scale"] = (
    1 if dataset_model.scale is None else dataset_model.scale.value
)
~~~

The fix restores this contract rather than inventing a new convention.

### Change

`temp/pyglotaran-staging-dev/pyglotaran`, commit-ready on the staging branch:

- `create_result_metadata` now computes the weighted RMSE from
  `weighted_residual` when present and from `residual` otherwise. For an
  unweighted dataset the effective weight is one, so the weighted and
  unweighted values coincide, exactly as in v0.7.
- `OptimizationResultMetaData` gained a `model_serializer(mode="wrap")` that
  re-inserts `scale` and `weighted_root_mean_square_error` after the default
  pydantic dump, so `exclude_defaults=True` can no longer drop them.

The fields stay optional for validation, so results saved by earlier v0.8 dev
builds still load.

### Size cost

Two float scalars per dataset leaf. For the
`sequential_spectral_decay` reference result the saved `result.yml` grows from
about 1.35 kB to 1.43 kB against 3.93 MB of total saved artifacts. No array
whose size scales with the data is persisted; the weight array itself is
deliberately not added.

### Verification

- Focused core tests: `tests/optimization/test_objective.py` and
  `tests/builtin/io/yml/test_yml.py` — 28 passed.
- Full core suite: 455 passed, 9 xfailed.
- Validation suite: 56 passed, 1 skipped.
- `ruff check` and `ruff format --check` clean on both changed files.
- End-to-end rerun of `simultaneous_analysis_3d_weight`, the scenario that
  previously omitted both fields on `dataset1`:

  | Dataset | `scale` | `weighted_root_mean_square_error` | `root_mean_square_error` |
  |---|---:|---:|---:|
  | dataset1 | 1.0 | 0.2537817152762107 | 0.2537817152762107 |
  | dataset2 | 0.8800495567943826 | 0.23786547830205468 | 0.4757309566041094 |
  | dataset3 | 72.73812042544681 | 0.20757750511045608 | 83.03100204418243 |

  The corresponding v0.7.4 attributes for `dataset1` are
  `dataset_scale=1.0` and
  `weighted_root_mean_square_error=root_mean_square_error=0.2537816922132262`,
  so the restored v0.8 values agree with the reference in both structure and
  magnitude.

- The fit itself is unchanged by this commit: 86 function evaluations,
  `` `ftol` `` termination, final cost `2.5145e+03`, first-order optimality
  `9.65e-04`, identical to the recorded staging run.

### Test updated

`tests/builtin/io/yml/test_yml.py::test_result_round_tripping` previously
asserted `weighted_root_mean_square_error is None` after a round trip, which
codified the omission. It now asserts the intended contract: the weighted RMSE
equals the unweighted RMSE for an unweighted fit, the scale is 1, and both keys
are present in the written `result.yml`.

### Compatibility layer

`validation/compatibility/load_v08.py` keeps its derivation path. It is
defensive and simply stops firing once a result carries the fields, so old
saved runs remain comparable while new runs report `staging_source:
"persisted"`. Derived values remain marked as derived.

### Note on NetCDF attributes

`fitted_data.nc`, `residuals.nc`, `input_data.nc` and the `fit_decomposition`
leaves are written with empty attributes, both before and after this change,
because `inject_meta_data_into_datasets` is an after-validator that runs on
load rather than before save. The metadata is present in `result.yml`, in the
`elements/` and `activations/` leaves, and on every in-memory dataset after
loading. Changing the on-disk attribute behaviour of the remaining leaves is a
separate question and was not in scope here.
