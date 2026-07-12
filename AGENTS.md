# Agent instructions

## Mission

Maintain scientifically defensible parity evidence between the pinned
pyglotaran v0.7.4 reference and v0.8 staging. Keep compatibility, translation,
comparison, and benchmark logic primarily under `validation/`. Do not make broad
changes to pyglotaran core just to make serialized results look alike.

## Read first

1. `README.md` for the current baseline and completed setup.
2. `validation/scenarios.yml` for pinned revisions, scenario IDs, result leaves,
   and tolerances.
3. `validation/AGENT_RERUN.md` for a complete validation rerun.
4. `validation/benchmarks/README.md` for fit-runtime measurements.
5. The relevant file under `issues/` before investigating a known difference.

## Repository map

- `temp/pyglotaran-main-dev`: v0.7.4 reference checkout and environment.
- `temp/pyglotaran-staging-dev`: v0.8 staging checkout and environment.
- `validation/run_examples.py`: isolated 11-notebook executor.
- `validation/compare_results.py`: manifest-driven semantic comparison entry
  point.
- `validation/compatibility/`: external v0.7-compatible result projection.
- `validation/benchmark_runtime.py`: fit-call-only runtime benchmark.
- `validation/tests/`: validation-side compatibility and regression tests.
- `issues/`: investigation briefs; add evidence and root-cause updates there.

The two `temp/` trees are separate Git repositories/submodules. A source change
inside one of them is not a root-workspace change: record the submodule state and
commit it in the appropriate checkout when that is explicitly requested.

## Source of truth

- Treat `validation/scenarios.yml` as the authoritative scenario and revision
  contract. Do not compare new outputs with old generated outputs.
- Use fresh timestamped output directories for every rerun. Runner manifests
  record source-tree, package, lockfile, notebook, and result hashes.
- The v0.7.4 branch is the numerical and behavioral reference. v0.8 result
  layouts are translated externally rather than rewritten to the v0.7 format.
- Current scope is 11 notebooks, 14 result leaves, and 15 fit invocations.

## Standard workflow

After changing staging inputs or code:

1. Inspect `git status` and preserve unrelated user changes.
2. Run the focused test or scenario affected by the change.
3. Run the complete procedure in `validation/AGENT_RERUN.md`.
4. Review both runner manifests and the generated semantic report.
5. If runtime behavior changed, run the benchmark handoff separately.
6. Update the relevant issue brief, `validation/logs/validation-log.md`, and
   `changelog.md` with revisions, evidence, tests, and remaining differences.

The normal validation acceptance state is 11/11 notebooks per branch, 14/14
declared leaves, no missing artifacts, and no `REGRESSION` or
`BASELINE_FAILURE`. Existing `EXPECTED_DIFFERENCE` entries are acceptable only
when their documented root causes still hold.

## Comparison rules

- Compare semantic arrays by labels and named dimensions.
- Treat input data as exact after canonicalization.
- Use fitted-data agreement as the primary scientific metric; residuals,
  parameters, CLP/matrix decompositions, and metadata are secondary evidence.
- Ordinary fitted-data normalized-RMS tolerance is `1e-6`; the transient
  two-dataset case uses `2e-5`; the weighted 3D case uses `3e-5`.
- Parameters use default `rtol=1e-4`, `atol=1e-8`.
- Non-identifiable parameters and decompositions must be documented, not forced
  into equality by post-processing.

## Runtime benchmark rules

- The benchmark times only the public optimizer call. It excludes notebook
  setup, plotting, saving, conversion, and result comparison.
- It runs one warm-up and five timed repetitions in fresh processes, with one
  thread by default and alternating branch order.
- It is report-only. A slowdown is evidence for investigation, not a release
  gate.
- Workload metadata, especially function-evaluation counts, must match before a
  runtime difference is treated as an implementation-performance comparison.

## Generated files and commits

Do not stage generated contents of `validation/runs/`,
`validation/comparisons/`, or `validation/benchmarks/`. They are ignored by the
root `.gitignore`; the benchmark README and validation manifests remain
trackable. Do not delete generated evidence merely to obtain a clean status.

Do not commit unless the user explicitly asks. When preparing a handoff, report
the files changed, tests run, source revisions, generated report locations, and
any unresolved differences.
