# Cross-branch validation workspace

The two pinned orchestration repositories under `temp/` own their environments and
editable package installs. This folder contains only validation-side tooling and
generated run outputs.

The declared scenario contract is in validation/scenarios.yml. It expands the
11 notebooks into 14 stable result leaves, including the four spectral-constraint
variants. Results are compared through validation/compatibility/, which projects
the monolithic v0.7 and split v0.8 layouts into the same labeled semantic view.

The v0.7.4 lockfile does not include the fixture provider used by the pinned
result-consistency tests. Install the validation overlay once in that environment:

```powershell
uv pip install --python temp/pyglotaran-main-dev/.venv/Scripts/python.exe -r validation/requirements.txt
```

## Run all example notebooks

Use a copy of each `pyglotaran-examples` checkout as the input root. The runner
keeps the source checkout unchanged, writes executed notebooks and result files to
the output root, isolates `Path.home()` per run, and returns non-zero if any of the
11 pinned notebooks fails.

```powershell
New-Item -ItemType Directory -Force validation/runs/main, validation/runs/staging
Copy-Item temp/pyglotaran-main-dev/pyglotaran-examples validation/runs/main/examples -Recurse
Copy-Item temp/pyglotaran-staging-dev/pyglotaran-examples validation/runs/staging/examples -Recurse

& temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/run_examples.py `
  --examples-root validation/runs/main/examples `
  --output-root validation/runs/main/output `
  --label v0.7.4

& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/run_examples.py `
  --examples-root validation/runs/staging/examples `
  --output-root validation/runs/staging/output `
  --label v0.8-staging
```

Each output contains `manifest.json`, executed notebooks, and the isolated
`home/pyglotaran_examples_results*` result bundle(s). The staging rewrite currently
uses a `_staging` suffix. The upstream validation test can then be pointed at a
generated result directory with `COMPARE_RESULTS_LOCAL`.

To compare the generated v0.7 and v0.8 result layouts:

```powershell
& temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/compare_results.py `
  --main-root validation/runs/main/output-final/home/pyglotaran_examples_results `
  --staging-root validation/runs/staging/output-final/home/pyglotaran_examples_results_staging `
  --output validation/comparisons/v07-v08.json
```

The final parity report uses the manifest-driven comparator and includes the runner
manifests, source-tree hashes, lockfile hashes, and result-tree hashes:

~~~powershell
& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/compare_results.py --main-root validation/runs/main/output-remediated/home/pyglotaran_examples_results --staging-root validation/runs/staging/output-remediated-2/home/pyglotaran_examples_results_staging --output validation/comparisons/v07-v08-semantic.json
~~~

Run the compatibility and focused translation tests with:

~~~powershell
& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe -m pytest validation/tests -q --basetemp validation/runs/.pytest-tmp
~~~

The retained clean rerun produced 11/11 notebooks on each branch and 14/14
declared leaves. The semantic report currently contains 8 PASS leaves and 6
EXPECTED_DIFFERENCE leaves, with no missing-artifact or regression status.

For impact-ranked analysis with normalized RMS metrics, parameter labels, metadata,
and root-cause grouping:

```powershell
& temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/analyze_comparison.py `
  --main-root validation/runs/main/output-final/home/pyglotaran_examples_results `
  --staging-root validation/runs/staging/output-final/home/pyglotaran_examples_results_staging `
  --output validation/comparisons/v07-v08-detailed.json
```

## Benchmark fit runtime

The validation-side runtime benchmark measures the public optimizer call only. It
does not include notebook imports, setup cells, plotting, result conversion,
comparison, or persistence after the call. The current manifest contains 15 fit
invocations, including the two fluorescence fits and four spectral-constraint
fits. Each branch gets one untimed warm-up and five timed repetitions in fresh
processes; the warm-up is excluded from the sample mean and sample standard
deviation.

Run the benchmark from the v0.7.4 environment so it can launch both pinned
branch environments:

```powershell
& temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/benchmark_runtime.py run `
  --manifest validation/benchmarks.yml `
  --main-python temp/pyglotaran-main-dev/.venv/Scripts/python.exe `
  --staging-python temp/pyglotaran-staging-dev/.venv/Scripts/python.exe `
  --main-examples temp/pyglotaran-main-dev/pyglotaran-examples `
  --staging-examples temp/pyglotaran-staging-dev/pyglotaran-examples `
  --output validation/benchmarks/raw/v07-v08-runtime-normalized

& temp/pyglotaran-main-dev/.venv/Scripts/python.exe validation/benchmark_runtime.py report `
  --manifest validation/benchmarks.yml `
  --raw-root validation/benchmarks/raw/v07-v08-runtime-normalized `
  --output validation/benchmarks/v07-v08-runtime-normalized
```

The report writes `runtime.json`, `runtime.csv`, `runtime.png`, and
`runtime.svg`. It reports mean, sample standard deviation, median, absolute
delta, and staging-over-main percentage change for every fit. Differences in
function-evaluation counts are flagged as conditional workload comparisons;
the benchmark is report-only and does not fail parity validation.
