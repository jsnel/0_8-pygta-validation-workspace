# Validation rerun handoff

Use this after patching the staging v0.8 submodule. Run from the workspace root
in PowerShell and use a new timestamped output directory every time.

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$mainOut = "validation/runs/main/$stamp"
$stageOut = "validation/runs/staging/$stamp"
$comparison = "validation/comparisons/v07-v08-$stamp.json"

& temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/run_examples.py `
  --examples-root temp/pyglotaran-main-dev/pyglotaran-examples `
  --output-root $mainOut `
  --label "v0.7.4-$stamp"
if ($LASTEXITCODE -ne 0) { throw "v0.7.4 examples failed" }

& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/run_examples.py `
  --examples-root temp/pyglotaran-staging-dev/pyglotaran-examples `
  --output-root $stageOut `
  --label "v0.8-staging-$stamp"
if ($LASTEXITCODE -ne 0) { throw "v0.8 staging examples failed" }

& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/compare_results.py `
  --main-root "$mainOut/home/pyglotaran_examples_results" `
  --staging-root "$stageOut/home/pyglotaran_examples_results_staging" `
  --output $comparison
if ($LASTEXITCODE -ne 0) { throw "Semantic comparison failed" }

& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe -m pytest validation/tests -q `
  --basetemp "validation/runs/test-$stamp"
```

Review the generated comparison report and both runner manifests. A healthy
rerun has 11/11 notebooks on each branch, 14 declared result leaves, zero
missing artifacts, and no `REGRESSION` or `BASELINE_FAILURE` statuses. Existing
`EXPECTED_DIFFERENCE` entries are acceptable only when their documented root
causes still apply. Do not compare a new run with old generated artifacts, and
do not commit `validation/runs/` or generated reports.

If the change affects optimizer budgets or runtime behavior, run the separate
[fit-runtime benchmark handoff](benchmarks/README.md) afterward.
