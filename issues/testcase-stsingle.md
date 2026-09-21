# ST single spectral-temporal case study

**Completed 2026-09-17:** both notebooks execute fully, with one captured fit
and four inline figures each. Use the dedicated staging interpreter below.
All four staging fitted datasets agree with the reference's labeled
matrix/CLP reconstruction to at most `4.0957218676376545e-16` normalized RMS.
Raw serialized parity remains `REVIEW_REQUIRED`; the reference residual reshape
and secondary metadata differences are retained explicitly.

The user-selected notebook is
`20260915STsingle_State1_2_6comp_per_day2Olli_shifted.ipynb` under
`temp/case-studies/testcaseSTsingle/{reference,staging}`. The staging notebook
retains the requested basename. The case is registered separately in
`validation/case_studies/cases.yml`; the common 14-leaf contract is unchanged.

## Scope and scientific contract

The notebook performs one fit over four active datasets (`dataSt1_1`,
`dataSt1_2`, `dataSt2_1`, `dataSt2_2`) with one function evaluation. This tests
the initial evaluation and result reconstruction, not convergence. Preserve
the input data, parameters, spectral cropping, local spectral element scales,
global kinetic element scales, initial concentrations, IRFs and NNLS behavior.
Commented-out datasets and guides are not active inputs.

Unlike the previous temporal-local examples, this model uses local spectral
elements and global kinetic elements. Generic migration rejects the legacy
`global_megacomplex` field. The external translation must retain that distinction,
including the inverted spectral axis and its `1e7` scale. Unused empty dataset
groups must be omitted: staging loads them but optimization raises
`StopIteration` when attempting to construct an objective without a dataset.

## Fresh common validation, 2026-09-16

Both branches passed 11/11 common notebooks. All 14 declared result leaves are
present and accepted: 8 PASS, 6 documented EXPECTED_DIFFERENCE, no REGRESSION
or BASELINE_FAILURE. No tolerances were changed.

- Runs: `validation/runs/{main,staging}/stsingle-20260916-213552/`.
- Report: `validation/comparisons/stsingle-common-20260916-213552.json`.
- Existing validation tests: 56 passed, one opt-in test skipped.
- Staging emitted a Windows ZeroMQ socket assertion but continued; its final
  manifest records zero failures and the semantic comparison verifies all leaves.

Core revisions tested are reference `33c602cd2dcd07068391113d506df5cd2431a7b3`
and staging `c71ebad0552c9fa8d0bfdc9a2d8f45e41a696f4a`. These differ from the
historical scenario pins; this is explicitly current-tree evidence. Both core
worktrees were clean. The case-study checkout HEAD on both sides was
`4ff877d80152a8aab7675dcdcaad774d2a2af015`. No commits or branch changes were made.

## ST reference evidence

The unmodified reference notebook passed in
`validation/runs/case-studies/stsingle-20260916-213552/reference/` with one
captured fit and four inline figures. Comparisons use fresh `case-study-results`
captures, not the results supplied with the repository. Pip is absent from the
environments; separate `reference-environment.json` and
`staging-environment.json` distribution snapshots accompany this run.

## SciPy NNLS dependency isolation

The original staging SciPy 1.14.1 fails with `Matrix is singular` during a
numerical-Jacobian perturbation for `dataSt2_1`. All four initial matrices solve;
the failing perturbed matrix is finite and has shape `(141780, 49)`, with
numerical rank 28 under the usual SVD size-scaled epsilon threshold
(`matrix-rank.json`). A standalone
diagnostic captures the matrix before NNLS and tests the identical array:

| Runtime | Outcome |
|---|---|
| Staging NumPy 2.0.1, SciPy 1.14.1 | Singular-matrix exception |
| Reference NumPy 2.2.6, SciPy 1.15.3 | Solves, residual norm 214249.1693006927 |
| Staging NumPy 2.0.1, isolated SciPy 1.15.3 | Same successful residual norm |

Evidence is under `validation/runs/case-studies/stsingle-20260916-213552/nnls-probe/`,
including `matrix-11.npz` and the `solve-failing-*` and
`solve-staging-overlay-1.15.3.json` records. This isolates the failure to the
SciPy version for this matrix. No NNLS-to-unconstrained-solver substitution is
part of the delivered notebook.

The dedicated Windows interpreter is
`temp/pyglotaran-staging-dev/.venv-stsingle/Scripts/python.exe`.
It uses staging's installed packages and editable source through
`Lib/site-packages/staging_dependencies.pth`, with a local SciPy 1.15.3 copied
from the existing reference installation (`scipy`, `scipy.libs`, and its
distribution metadata). The original staging `.venv` and dependency lock remain
unchanged. This environment intentionally differs from the common-run runtime
only in SciPy; its distribution snapshot is `staging-stsingle-environment.json`.
Select this interpreter as the staging notebook's VS Code kernel.

To recreate the dedicated environment at a new destination, use the existing
installed SciPy package without downloading or upgrading the staging lock:

```powershell
uv --cache-dir temp/uv-cache-stsingle venv `
  --python temp/pyglotaran-staging-dev/.venv/Scripts/python.exe `
  temp/pyglotaran-staging-dev/.venv-stsingle
$target = 'temp/pyglotaran-staging-dev/.venv-stsingle/Lib/site-packages'
$parentSite = (Resolve-Path 'temp/pyglotaran-staging-dev/.venv/Lib/site-packages').Path.Replace('\', '/')
"import site; site.addsitedir('$parentSite')" | Set-Content "$target/staging_dependencies.pth"
Get-ChildItem temp/pyglotaran-main-dev/.venv/Lib/site-packages -Directory -Filter 'scipy*' |
  Copy-Item -Destination $target -Recurse
```

This local overlay shares the staging environment's other packages; it is not a
self-contained portable environment. Recheck the recorded SciPy version if the
reference installation changes.

Regenerate the translated inputs with:

```powershell
& temp/pyglotaran-staging-dev/.venv-stsingle/Scripts/python.exe `
  -m validation.case_studies.prepare_stsingle `
  --reference-root temp/case-studies/testcaseSTsingle/reference `
  --staging-root temp/case-studies/testcaseSTsingle/staging
```

The generator writes the requested notebook basename and a separate `_v08.yml`
model, and clears stale notebook outputs. Source data and parameter CSVs already
present in staging are required; it does not copy or alter them.

## Result reconstruction findings

Staging has independent experiment- and dataset-level `residual_function`
settings. `OptimizationObjective.calculate_global_penalty()` reads the
experiment setting, while `create_global_result()` reads the dataset setting.
Leaving the latter at its default produced unconstrained saved results after
an NNLS fit, despite matching optimizer chi-square. The ST translator explicitly
sets both to the reference group's NNLS solver. No core code was changed.

The live plotting adapter now preserves existing `clp_label` and
`global_clp_label` dimensions instead of unconditionally renaming
`amplitude_label`. The notebook saves `result_native` to a fresh timestamped
directory with an explicit `result.yml`; supplied result folders are preserved.

The provisional comparison before the dataset solver fix is retained at
`validation/comparisons/case-studies/stsingle-20260917-065640/comparison.json`.
It has exact inputs but up to 0.101379 normalized-RMS fitted-data disagreement;
it is not an accepted parity result.

## Final evidence, 2026-09-17

- Fresh reference: `validation/runs/case-studies/stsingle-20260917-065640/reference/`.
- Final staging: `validation/runs/case-studies/stsingle-20260917-070313/staging/`.
- Raw comparison: `validation/comparisons/case-studies/stsingle-20260917-070313/comparison.json`.
- Reconstruction diagnostic: the same directory's `reconstruction-audit.json`.
- Final parameter-aware schema/load report: `validation/comparisons/stsingle-schema-20260917-070313.json`.
- Artifact audit: `validation/runs/case-studies/stsingle-20260917-070313/artifact-audit.json`;
  87 artifacts checked, no missing files or hash mismatches, and both source
  notebooks match their execution snapshots. All six supplied input files match
  byte-for-byte across branches. The final 25-panel logarithmic trace figure
  was visually inspected; four inline figures were captured per notebook.

The v0.7 full-model path in `optimization/estimation_provider.py::get_result`
reshapes its flat residual directly to `(model_axis, global_axis)` even though
the full matrix/data vector uses the opposite flattening order. Transposing a
one-dimensional array first does not reorder it. This causes the stored
`fitted_data = data - residual` to differ from the model's own labeled
`global_matrix @ clp @ matrix.T` prediction. Staging uses the appropriate
reshape/transpose. The unchanged raw comparison therefore differs by up to
`0.10210738028128313` normalized RMS. The supplemental diagnostic records both
the raw discrepancy and independent model reconstruction; it does not replace
the baseline arrays or relax the `1e-6` tolerance.

Secondary differences remain: staging counts 48 CLPs by summing the two axes,
while reference counts 148 by their products. This changes degrees of freedom
and reported RMSE despite matching chi-square. Staging also omits inactive
parameter labels, and individual CLPs are non-identifiable in the rank-deficient
model. Both branches use one function and one Jacobian evaluation and terminate
at the evaluation limit; their success flags do not imply convergence.

Final common regression check on the unchanged ordinary environments:
`validation/runs/{main,staging}/20260917-065713/`; 11/11 notebooks each,
14/14 leaves, 8 PASS and 6 documented EXPECTED_DIFFERENCE. Report:
`validation/comparisons/v07-v08-20260917-065713.json`.
The final dedicated ST runtime's validation suite passes 62 tests with one
opt-in skip (`validation/runs/stsingle-tests-handoff-20260917.log`). The
independent residual reshape diagnostic agrees with data minus reconstructed
fit to below `2.9e-15` normalized RMS. No benchmark is claimed:
this task changes validation translation and an isolated ST dependency, not
the existing common benchmark workload or installed core implementations.

Trackable implementation: `validation/case_studies/{cases.yml,prepare_stsingle.py,
validate_schemas.py,audit_stsingle.py}`, shared notebook compatibility, and
focused tests. The generated staging notebook/model live in the ignored
case-study checkout and remain uncommitted. No core edits, commits, branch
switches, dependency-lock edits, or reference-artifact rewrites were made.
