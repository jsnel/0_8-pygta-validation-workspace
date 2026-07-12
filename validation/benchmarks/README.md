# Fit-runtime benchmark handoff

Use this when you want a fresh runtime comparison after changing the staging
submodule. It measures only the public optimizer call, not notebook setup,
plotting, saving, or result comparison.

Run from the workspace root in PowerShell:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$raw = "validation/benchmarks/raw/v07-v08-runtime-$stamp"
$report = "validation/benchmarks/v07-v08-runtime-$stamp"

& temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/benchmark_runtime.py run `
  --manifest validation/benchmarks.yml `
  --main-python temp/pyglotaran-main-dev/.venv/Scripts/python.exe `
  --staging-python temp/pyglotaran-staging-dev/.venv/Scripts/python.exe `
  --main-examples temp/pyglotaran-main-dev/pyglotaran-examples `
  --staging-examples temp/pyglotaran-staging-dev/pyglotaran-examples `
  --output $raw
if ($LASTEXITCODE -ne 0) { throw "Benchmark workers failed" }

& temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/benchmark_runtime.py report `
  --manifest validation/benchmarks.yml `
  --raw-root $raw `
  --output $report
```

Expected result: 12 successful workers, 150 timed samples, 15 fit summaries,
and `REPORT_ONLY` in `$report/runtime.json`. The report contains JSON, CSV,
PNG, and SVG files. Raw runs and generated reports are intentionally ignored by
Git; keep the manifest hash and pinned source metadata from the report when
recording an investigation.
