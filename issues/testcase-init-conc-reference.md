# TestCaseInitConc reference execution blockers

## Resolved handoff — 2026-09-05, run 20260905-200057

The user authorized dropping development-only incompatibilities and optional
private helpers. Both new `_validation` notebooks now execute successfully;
the staging copy ends in `_validation_v08.ipynb`. Original notebooks and supplied
results remain preserved. The generator is
`validation/case_studies/prepare_init_conc.py`.

- Removed unsupported `x_scale='jac'` from the runnable copy on both branches;
  used the public optimizer defaults, 3 evaluations, and CLP link tolerance 0.5.
- Used byte-identical copies of the user's corrected reference parameter CSV.
  All 11 data/guide files match. Eight measured datasets and five active guides
  yield 13 compared datasets; supplied `data_guide_s3g3` has no model definition.
- Omitted the unused empty `default` dataset group from staging. Kept both active
  NNLS groups, kinetic models, scales, activations, constraints, relations,
  penalties, weights, and parameter expressions.
- Replaced the private plotting cells with public extras concentration, SAS,
  DAS and normalized-DAS functions: State 1 and State 2 each have a 4-by-4 figure.
  Dispersed concentration plots select 700 nm and use symlog with threshold 100 ps.
  Optional kinetic diagrams, private initial-concentration tables, stop cells,
  and trailing older analyses are outside this runnable copy.
- The reference extras checkout is now `96dbbbbc0cede1ecb932a202202cdf903a9894f8`.
  Its `inspect/a_matrix.py` uses multiline f-strings incompatible with Python 3.10.
  A pristine plotting dependency copy at baseline commit
  `dcbe4baad5949768b65bf602d58018b5fe309f0a` lives under reference
  `_plotting_dependencies`; the notebook explicitly imports from it. The user's
  extras checkout was not edited. Staging extras uses
  `700f9de482f317afa0339edc12314fd14699e459`.

Fresh comparison:
`validation/comparisons/case-studies/20260905-200057/TestCaseInitConc/comparison.json`.
Both notebooks passed; staging schema/load/dry-run/real-fit checks passed.
There are 4 inline images and 4 saved plot files per branch. Inputs agree exactly
for all 13 datasets. Worst fitted-data normalized RMS is `2.53544703805126e-8`
(guide s4g3), below `1e-6`; worst measured-data value is `8.741101474131398e-9`.
Both branches report 3 function and 3 Jacobian evaluations, 49 free parameters,
2538 CLPs and 607886 data residuals. Both terminate at the function-evaluation
limit; their serialized success flags do not establish convergence.

Provisional status is `REVIEW_REQUIRED`: shared parameter values agree closely
(120 labels; maximum relative difference `1.4900371567697233e-8`), but staging
does not persist 30 additional reference labels. Raw matrices differ, including
dataset-scale-related magnitudes and the weighted-guide matrix shape. Some
metadata are absent in staging, and strict elementwise residual checks differ.
These secondary observations remain in the report without forced equality or
final scientific classification. Figures use each version's compatibility
representation; equal y-axis amplitudes are not an acceptance assertion.

Runtime/source provenance: reference pyglotaran `8f26be01d5a6ce63ec2556469ac3facc2d2cee68`,
staging `51574847bd5cd0e98a6c301f3d557d6d4ed85cd2`. The staging case repository is
now `3512a246a9f27babcd7e2cbc61d26b66b582da7b`; its tracked tree differs from the
reference commit. Input content hashes, matching parameter copies, and both
source patches establish the actual inputs used. No checkout revision was reset.

All 26 validation tests pass. Only the isolated case-study adapter, configuration,
and documentation changed at workspace level; no common scenario, shared
comparison implementation, optimizer, or core input was changed. No runtime
benchmark or common-notebook rerun was needed for this isolated addition.

The earlier blockers and failed evidence below are retained as history.

## 2026-09-05 evidence

Status: `BLOCKED_REFERENCE`. No fresh fit or numerical comparison is available.
The original notebooks, parameter/model inputs, and supplied results are unchanged.

- Reference repository: `720541a42ad520a2169fd81aca93cf5f69a87354`.
- Staging repository: `6e55cad626ea044f4ff09ae8cc275481e4417364`.
- Both tracked trees: `59a8a437a42fc884e78364497f353e81fdf94974`.
- Reference pyglotaran: `8f26be01d5a6ce63ec2556469ac3facc2d2cee68` (0.7.4).
- Available staging pyglotaran: `51574847bd5cd0e98a6c301f3d557d6d4ed85cd2`;
  this differs from the common baseline pin and was not changed for this task.

The isolated unmodified execution fails in notebook cell 8 (zero-based), loading
the supplied parameter CSV: `Parameter.__init__() got an unexpected keyword
argument 't-value'`. No optimizer call was reached. Full traceback, executed
notebook, command, environment, source diff, and artifact hashes are under
`validation/runs/case-studies/20260905-initconc-02/`.

Static inspection also establishes later obstacles:

- Cell 10 passes `x_scale='jac'` to `Scheme`; pinned v0.7.4 has no such argument.
  Dropping it without establishing the intended optimizer scaling is not a
  scientifically justified migration.
- Cells 23/24/33/36 import `pygta_local_extras`, absent from the supplied repository
  and reference environment. The custom initial-concentration and plotting
  helpers need their actual implementation, not an invented replacement.
- Cells 39/46/56 contain bare `stop` expressions.
- Cell 44 has invalid nested string quoting. Instrumented execution in
  `20260905-initconc-01` failed during AST parsing before kernel execution.
- Cell 67 loads absent `20260709target_State1_3comp.yml` and `.csv` files;
  the notebook includes a second fit in this older section. The first target fit
  uses 14 datasets, two groups, and a three-evaluation budget.

The migration skill and case-study plan require establishing a runnable reference
before migrating around unknown behavior. Migration and comparison remain pending.
Resolve the intended reference environment/scaling and provide the local extras;
select whether the trailing older analysis is in scope. A clearly named runnable
copy can then remove report-only CSV columns and isolate the intended analysis,
while preserving the original files and recording each adjustment.

Validation-side tests: `16 passed` using
`python -m pytest validation/tests/test_case_studies.py -q --basetemp validation/runs/test-initconc-before`.
An initial test attempt without a workspace-local base directory encountered
Windows temp-directory permissions; the local-directory rerun passed.
No shared runner/comparator, pyglotaran core, or baseline staging input changed.
The common 11-notebook rerun and runtime benchmark therefore were not required.
