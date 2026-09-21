# September 19 ST no-single update

The active `testcaseSTsingle` entry is now
`20260919STno_single_State1_2_6comp_per_day2Olli_shifted.ipynb` from reference
commit `3a574b86d93dfde88b8249353f234fb814680ba0`. The earlier
[September 17 evidence](testcase-stsingle.md) remains historical evidence for
different notebook/model/parameter inputs.

The author-provided notebook uses
`models/20260915STno_single_State1_2_6comp_day1_Olli.yml` and
`models/20260919STsingle_State1_2_6comp_day1_Olli11_02.csv`. Its three-evaluation
budget is preserved. The four active datasets remain `dataSt1_1`, `dataSt1_2`,
`dataSt2_1`, and `dataSt2_2`. Neither the model nor parameter semantics are
inferred from the file names.

## Deferred author notebooks

The following reference notebooks require the single-amplitude feature on
`ism200/scale_list` and are excluded from the active validation selection:

- `20260915STsingle_State1_2_6comp_per_day2Olli_shifted.ipynb`
- `20260919STsingle_State1_2_6comp_per_day2Olli_shifted.ipynb`

No feature-branch switch or port of these updated notebooks is part of this
work. Their author-run copies directly under `temp/case-studies/testcaseSTsingle/`
are read-only debugging references. The entire reference worktree is also
preserved. Historical staging notebooks are not deleted or regenerated as part
of selecting the new active notebook.

## Runtime and reporting scope

Reference core: `cf48eae1e1ac8e1ad6f40ba358a4ec20ce6494ab`.
Staging core: `c71ebad0552c9fa8d0bfdc9a2d8f45e41a696f4a`.
Reference extras: `b72a21e07decc638dbf62ecdb7189a3e4693a320`.
Staging extras: `700f9de482f317afa0339edc12314fd14699e459`.
These are current-tree measurements rather than a claim that the older common
scenario revision pins were used.

The established `.venv-stsingle` staging interpreter supplies SciPy 1.15.3
without changing the normal staging environment or lock. The prior ST
migration's explicit experiment/dataset NNLS settings and native result saving
are retained where applicable.

The workspace-root `pygta-local-extras` package is installed editable in both
main and staging environments with `--no-deps`. The dedicated ST environment
inherits staging's installation. Installation used `uv pip install --offline
--no-build-isolation --python <environment>/Scripts/python.exe --no-deps -e
./pygta-local-extras` because build isolation otherwise tried to fetch setuptools.
No dependencies were upgraded. Final runs execute every reporting cell.

The newer author kinetic-diagram API is absent from staging extras. The generated
`_reporting/kinetic_scheme.py` runs the author's diagram/style source in the main
environment, using the **staging optimized parameters** and legacy model; it does
not refit. The newer amplitude-table formatter is copied byte-for-byte from main
extras into `_reporting/a_matrix.py` and runs against the staging compatibility
result. Neither installed extras checkout nor pyglotaran core is modified.
Both global results lack A-matrix variables, so the author's initial-concentration
table is empty and selected amplitude entries are zero in both notebooks; these
are reporting limitations, not fitted concentration estimates.

Earlier missing-helper failures and a guarded reference trial are retained as
historical artifacts. They are superseded by the final `reference-full` and
`staging-full` runs with the local package installed and no skipped cells.

Initial read-only source hashes, including all three top-level author notebooks,
are in `validation/runs/st-no-single-20260919-225511/read-only-source-hashes.json`.

## Verification

Fresh common validation completed at `20260919-230004`: 11/11 notebooks on each
branch, 8 PASS and 6 documented EXPECTED_DIFFERENCE leaves, no regressions or
baseline failures. Evidence: `validation/runs/{main,staging}/20260919-230004/manifest.json`
and `validation/comparisons/v07-v08-20260919-230004.json`.

The complete validation-side suite passes: **62 passed, one skipped**. Both
available staging schemas (active no-single and historical ST) pass loading and
parameter-aware validation. Reports are under
`validation/runs/st-no-single-20260919-225511/`: `tests-final.log`,
`schema-final.json`, and the two `*-environment-final.json` snapshots (used
because these uv environments do not contain pip).

No common optimizer implementation or default runtime changed. The separate
runtime benchmark was not repeated and no performance claim is made for this
new three-evaluation case. The author budget is preserved and does not establish
optimizer convergence.

## Reproduce the staging port

From the workspace root:

```powershell
& temp/pyglotaran-staging-dev/.venv-stsingle/Scripts/python.exe -m validation.case_studies.prepare_stsingle --reference-root temp/case-studies/testcaseSTsingle/reference --staging-root temp/case-studies/testcaseSTsingle/staging
```

Open the generated `staging/20260919STno_single_State1_2_6comp_per_day2Olli_shifted.ipynb`
with the `.venv-stsingle` interpreter. Keep `_reporting/` beside the notebook;
the kinetic renderer also requires the workspace main interpreter and extras.
The legacy model, latest parameter CSV, and four ASCII datasets are already
present in staging and all six files match reference byte-for-byte
(`input-integrity.json`). For validation, use `run_case_study.py` with
`--capture-fit-results` and a fresh `--output-root`; compare those captured fit
leaves, not the supplied historical `results/` directory.

## Final ST results

Evidence root: `validation/runs/st-no-single-20260919-225511/`.
Both `reference-full/manifest.json` and `staging-full/manifest.json` report
**PASSED**, with one captured fit, eight inline figures, and no skipped cells.
The staging case checkout is based on `df381a0b663f50fca812bbf91a8631f46f37d113`;
the generated notebook, model, and `_reporting/` files remain uncommitted.
The kinetic diagram and private SAS report were visually inspected. The latter
retains the author's blank panels for inactive datasets.

`comparison.json` / `comparison.md` remain **REVIEW_REQUIRED**: the largest raw
serialized fitted-data normalized RMS is `0.08955308323252424`.
`reconstruction-audit.json` separately reconstructs reference fitted data from
its labeled global matrix, CLPs, and local matrix; the comparison to staging is:

| Dataset | Reconstructed reference vs staging normalized RMS |
|---|---:|
| dataSt1_1 | 9.003678e-9 |
| dataSt1_2 | 1.236851e-8 |
| dataSt2_1 | 6.843467e-9 |
| dataSt2_2 | 6.907967e-9 |

All are below the ordinary `1e-6` scientific threshold. The reference residual
reordering proof agrees to at worst `4.65e-15` normalized RMS, reproducing the
previously documented v0.7 global residual reshape defect. This is diagnostic
evidence only: no stored reference arrays or comparison tolerances were changed.

Both fits used three function and three Jacobian evaluations, 27 free parameters,
and stopped at the evaluation limit; the serialized `success: true` does not
mean convergence. Chi-square is `37290153579.18822` reference versus
`37290152955.04969` staging. The 72 shared parameter values differ by at most
`1.213e-5` relatively (within the `1e-4` default tolerance); staging omits unused
reference parameter rows. Global CLP metadata still counts 148 versus 48, with
corresponding degrees-of-freedom and reduced-statistic differences. These
secondary serialization/metadata differences remain visible in the raw report.

`artifact-integrity.json` verifies 95 generated artifact hashes and confirms all
30 protected reference/author files remain unchanged. `input-integrity.json`
confirms all six supplied scientific input files match exactly. Tests and common
validation evidence above were reviewed; generated evidence is retained and
nothing was committed.
