# Staging runtime optimization continuation — 2026-09-06

Status: **the new amplitude-label optimization is validated and retained, uncommitted**.
It preserves current staging outputs exactly. Fresh evidence root:
`validation/runs/runtime-continuation-20260906/`.

## Baseline and scope

Workspace started clean at `44def7a`; staging core started clean at `20020378`
(parent `51574847`). The previous agent's three core edits are already in that
commit. NumPy 2.2.6 / SciPy 1.15.3 / Numba 0.63.1 are installed. This continuation
does not change dependencies, production notebooks, models, parameter flags,
solver budgets, tolerances, or result content.

The current committed staging implementation is the oracle for this new change.
Its complete `glotaran` directory was copied into the ignored evidence directory
`baseline-core/` before editing. Fresh subprocesses select this copy using
`sys.path`, avoiding changes to the editable installation or production checkout.
Every probe records all Python source hashes, notebook hash, actual interpreter,
scientific package versions, thread settings, initial parameters, data dimensions,
dtypes, budgets, tolerances, evaluation counts, termination reasons and peak RSS.

The inherited dependency upgrade's comparison with pre-upgrade staging remains
a separate unresolved acceptance question: the old handover reports spectral
fitted-data RMS `1.10e-6`, exceeding the contractual `1e-6`. It must not be called
an accepted tolerance-equivalent upgrade based on that evidence.

## Bottleneck and change

`OptimizationObjective.get_dataset_amplitudes` receives an xarray coordinate.
`list(amplitude_axis)` produces scalar DataArrays. Each `list.index` comparison
then invokes xarray's equality, coordinate alignment and index construction.
The existing profile identifies hundreds of thousands of these comparisons;
the previous gather vectorization retained this overhead.

Convert the coordinate with `np.asarray(amplitude_axis).tolist()` once before
the gather. Ordinary Python string comparisons replace xarray equality. The
selection order and all numerical operations remain unchanged. There is no cache,
cross-fit state, solver change, extra dependency or workload special case.

Focused regression coverage includes ndarray and xarray coordinate inputs,
reordered global indices, differing per-slice amplitude layouts, and a second
reconstruction after mutating estimates to detect accidental reuse.

## Measurement method

`benchmark_staging_continuation.py` runs original notebook cells through the last
optimizer cell in a fresh process. Earlier setup/plotting remains outside timing;
later plotting is not executed. The public `Scheme.optimize` interval includes
validation, solving, complete reconstruction and parameter-error calculation.
Lightweight wrappers separately time initialization, objective calculation and
reconstruction. A 20 ms RSS sampler runs only during the public call. Neither
cProfile nor tracemalloc is enabled. RSS includes objects retained by prior cells;
it is not an isolated per-fit allocation measurement.

`run_staging_continuation.py` alternates branch order per repetition. PFID uses
one warmup plus three timed repetitions; standard examples use one plus five.
Snapshots are captured only in warmups, after the public-call timer stops.
`compare_staging_snapshots.py` recursively checks all native reconstructed fields,
coordinates, attributes, metadata, parameter tables and optimization information.

The first PFID baseline probe failed after its first optimize call because
pickling an entire Result encounters a dynamically generated model class.
`pfid-baseline-warmup/` is retained as failed evidence; it is excluded. The rerun
`pfid-baseline-warmup2/` stores plain result-field mappings and completed.

## Controlled-workload constraint

Both original PFID real calls have **zero free parameters**, nfev=1 and njev=0,
and terminate with `No free parameters to optimize.` These are meaningful public
optimizer/reconstruction workloads, but cannot perform 4–8 nonlinear steps by
perturbing free starting values. Changing fixed/free flags would change the
requested optimization problem and is outside the contract. This limitation is
reported rather than relabelling result reconstruction as nonlinear optimization.

Staging's `optimization_info.success` means that SciPy returned a result, even
when it exhausted its evaluation budget. The new probe also captures SciPy's
actual `success` and status; convergence claims use the actual termination.

The original two-dataset and spectral-guidance calls both exhaust their budgets
(17 and 21 evaluations). They must not be described as converged. Controlled
variants start from a copy of the fresh baseline optimized parameter table and
multiply only free, non-expression parameters: +5% for two datasets, +0.01% for
spectral guidance. Both use a diagnostic budget of 100 and unchanged solver
tolerances. Calibration gives four nonzero accepted steps in each case, with
7/5 and 16/5 function/Jacobian evaluations respectively, terminating on `xtol`.
The final zero-step termination row is not counted as a genuine step. Initial
tables are identical between branches; production files are unchanged.

Calibration ran during untimed full-suite validation, so its durations are not
used as benchmark evidence. The +0.01% two-dataset trial was rejected as too short
(only two accepted steps). Final controlled repetitions run separately.

## Inherited correctness concern found during audit

The earlier Gaussian dispersion vectorization omits `self.shift`, while the
original `parameters(axis)` path subtracts the per-slice shifts before applying
dispersion. A focused reproduction in `inherited-gaussian-shift.txt` uses center
1, width 10, shifts `[0.5, 1]`, dispersion center 100, coefficient 2 and axis
`[0, 100]`. Current `calculate_dispersion` gives `[[-1, 1]]`; the original
parameter path gives `[[-1.5, 0]]`.

This is an inherited output-compatibility defect in `20020378`, not caused by
the new amplitude-label conversion. It needs a separate correctness fix and
coverage for simultaneous shift and dispersion. This continuation preserves
the requested current-staging oracle and does not silently alter those values.

## Original-workload timings

Public optimizer-call seconds, excluding warmups. Baseline is `20020378` with
the already upgraded installed dependencies; optimized adds only the label
conversion. These are additional gains, not a remeasurement of the dependency
upgrade against the older SciPy environment.

| Call | Baseline mean ± SD | Optimized mean ± SD | Baseline median [min, max] | Optimized median [min, max] |
|---|---:|---:|---:|---:|
| PFID scheme 1 dry run | 17.698 ± 9.717 | 10.816 ± 5.613 | 12.119 [12.057, 28.918] | 7.618 [7.533, 17.297] |
| PFID scheme 1 real | 15.553 ± 8.748 | 8.959 ± 4.868 | 10.512 [10.493, 25.654] | 6.152 [6.145, 14.581] |
| PFID scheme 2 dry run | 40.209 ± 5.984 | 12.318 ± 5.973 | 37.017 [36.498, 47.112] | 8.926 [8.813, 19.215] |
| PFID scheme 2 real | 37.173 ± 0.503 | 12.312 ± 5.997 | 37.417 [36.594, 37.508] | 8.866 [8.834, 19.236] |
| ex_two_datasets | 1.100 ± 0.021 | 1.096 ± 0.013 | 1.107 [1.078, 1.121] | 1.100 [1.082, 1.112] |
| ex_spectral_guidance | 1.934 ± 0.013 | 1.810 ± 0.013 | 1.937 [1.913, 1.947] | 1.808 [1.791, 1.826] |

PFID real-call means decrease by 42% and 67%; spectral guidance decreases by
6.4%. There is no convincing overall two-dataset speedup above timing variation.
PFID variability is substantial and all samples are retained; medians and ranges
are reported to avoid false precision. Snapshot-bearing warmup durations are
not used for these estimates. No timing claim uses notebook wall time.

| Original call | nfev / njev / free parameters (both) | Reconstruction mean, baseline → optimized (s) | Max sampled RSS, baseline → optimized (GiB) |
|---|---|---:|---:|
| PFID scheme 1 dry run | 1 / N/A / 0 | 12.149 → 5.281 | 1.257 → 1.271 |
| PFID scheme 1 real | 1 / 0 / 0 | 12.009 → 5.322 | 1.952 → 1.958 |
| PFID scheme 2 dry run | 1 / N/A / 0 | 34.580 → 6.593 | 3.881 → 3.883 |
| PFID scheme 2 real | 1 / 0 / 0 | 33.175 → 6.756 | 4.624 → 4.625 |
| ex_two_datasets | 17 / 12 / 10 | 0.031 → 0.020 | 0.245 → 0.245 |
| ex_spectral_guidance | 21 / 9 / 3 | 0.175 → 0.040 | 0.198 → 0.198 |

There is no meaningful memory reduction. This is process RSS sampled during
each optimizer call, not tracemalloc, process-tree RSS or allocation provenance;
it should not be directly equated with the older whole-notebook memory profile.
Setup, plotting, saving, conversion and comparison are outside public-call timing.
Initialization, objective and reconstruction distributions are separately available
in `timing-summary-final.json`; these phases are not substituted for public-call time.

## Controlled timings

One warmup and three timed fresh-process repetitions per branch. Both cases
have four nonzero accepted steps and true SciPy convergence in every sample.

| Case | nfev / njev / free | Baseline mean ± SD (s) | Optimized mean ± SD (s) | Baseline median [min, max] | Optimized median [min, max] |
|---|---|---:|---:|---:|---:|
| two datasets, endpoint +5% | 7 / 5 / 10 | 1.253 ± 0.040 | 1.240 ± 0.038 | 1.242 [1.219, 1.297] | 1.237 [1.203, 1.279] |
| spectral guidance, endpoint +0.01% | 16 / 5 / 3 | 1.520 ± 0.013 | 1.380 ± 0.010 | 1.514 [1.511, 1.535] | 1.375 [1.373, 1.392] |

Spectral guidance improves by 9.2%; the two-dataset difference remains within
timing variation. Max RSS is approximately 0.198/0.199 GiB for controlled spectral
guidance and 0.245/0.246 GiB for controlled two datasets. Controlled PFID nonlinear
steps are impossible under the fixed/free-parameter contract, as explained above.

## Correctness and final reference comparison

- `pfid-exact.json`: all four native PFID snapshots exactly match, including all
  reconstructed result fields, dimensions, coordinates, attributes, metadata,
  parameter tables and optimizer histories.
- `two-exact.json` and `spectral-exact.json`: original standard snapshots exactly
  match. Both controlled snapshot reports also exactly match.
- `workload-audit.json`: notebook hashes, installed scientific versions, initial
  parameters, dimensions/dtypes, solver/budget/tolerances, counts and termination
  match across every timed pair and controlled repetition.
- Fresh `full-baseline/`, `full-optimized/`, and `full-main/` manifests each show
  **11/11 notebooks passed**. Baseline source provenance confirms the preserved
  copy was loaded; the optimized runner records the edited source tree.
- `staging-self.json`: **14/14 leaves PASS**, no missing artifacts; all 28 compared
  fitted arrays have normalized RMS **0.0**. This fresh matched-input run resolves
  the old self-comparison's dataset-name mismatch for the current source trees.
- `main-staging.json`: **8 PASS, 6 EXPECTED_DIFFERENCE, 0 REGRESSION,
  0 BASELINE_FAILURE**. Spectral-guidance dataset1 fitted-data normalized RMS is
  `2.4928654061006497e-7`, below `1e-6`; the documented decomposition/parameter
  differences remain. No tolerance or classification was changed.

The final reference result passes on the current installed stack, but does not
retroactively validate the pre-upgrade-versus-post-upgrade staging comparison.
Original standard-example budget exhaustion remains unchanged and is distinct
from semantic parity. The controlled examples demonstrate successful convergence.

## Tests, revisions and reproduction

- Validation suite: **36 passed, 1 skipped** (`test-validation-final.log`).
- Focused staging objective, Gaussian activation and PFID element tests:
  **35 passed** (`test-core.log`).
- `git diff --check` passed for root and edited staging core.
- Native snapshot comparison originally reported a pandas storage-manager
  identity difference in optimizer histories. The reader now restores the actual
  DataFrame state and compares every cell, axis and metadata; a round-trip test
  verifies this. No history field is excluded from equality checks.
- `python -m pip freeze` was unavailable because pip is not installed in staging;
  `package-versions.txt` records the installed distribution versions via
  `importlib.metadata` instead. No dependency was installed for the probes.

Reference core: `8f26be01d5a6ce63ec2556469ac3facc2d2cee68`;
staging core: `20020378e3b18e4d46020135bbf6959eacc9eb18` plus the uncommitted change.
Current reference/staging examples: `23287837579b9ad150ca33cce2b34bba33ec1e0d` /
`44e3747cf39f0482ed5c05578624577938159085`. Full orchestration revisions and
worktree states are in `revisions.json`; notebook/source hashes are in individual
`measurements.json` files, and manifest/lock hashes are in `contracts.json`.
Python is 3.10.19 on Windows, Intel64 Family 6 Model 183 Stepping 1; all four
OMP/MKL/OpenBLAS/Numba thread controls are fixed to one per worker.

The installed staging stack differs from its existing `uv.lock`, which still
contains NumPy 2.0.1 / SciPy 1.14.1 / Numba 0.60.0 / llvmlite 0.43.0. A normal
sync may restore those versions. The installed stack measured here is NumPy
2.2.6 / SciPy 1.15.3 / Numba 0.63.1 / llvmlite 0.46.0. Lock alignment and acceptance
of the inherited dependency upgrade remain follow-up work, not silently included
in this code-only performance change.

Run a probe with the staging interpreter and
`validation/benchmark_staging_continuation.py --notebook <path> --core <source-root>
--output <new-directory> --save-results`. The paired driver takes `--case pfid`,
`--case two` or `--case spectral`. For controlled runs add `--initial-snapshot
<baseline-result-1.pkl> --perturb 1.05 --max-nfev 100` (spectral uses `1.0001`).
Each `jobs.json` records exact commands. Snapshot files are trusted local pickle
artifacts and must not be loaded from untrusted sources.

## Rejected ideas and remaining risks

- Residual gathering and SVD rewrites were not pursued: the supplied profile and
  focused experiment identify amplitude-label equality as the avoidable cost.
  Broader arithmetic changes would add risk without being necessary for this gain.
- No cache, parameter-dependent reuse, buffer sharing, solver replacement or
  matrix-reassociation edit is introduced. The earlier matrix-copy removal was
  already rejected for changing optimizer trajectories; it remains reverted.
- The tiny two-dataset controlled perturbation was rejected for doing too few
  genuine steps. Changing PFID fixed/free flags merely to manufacture iterations
  was rejected as a change to the optimization problem.
- No overall two-dataset speedup or memory improvement is claimed. PFID timing
  variance and existing numerical sensitivity remain material limits.
- The inherited Gaussian shift defect, unreconciled dependency lock and original
  example non-convergence remain explicitly documented; they are not hidden by
  the passing current-staging comparison.

Changed production file: staging core `glotaran/optimization/objective.py`.
Validation-side additions are the probe, paired driver, snapshot comparator,
summary helper and their focused tests. This report, original handover, issue
index, root README, validation log and changelog document the result. Generated
evidence remains ignored; no evidence or throwaway worktree was deleted and no
commit was made.
