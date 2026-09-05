# TestCaseInitConc reference execution blockers

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
