# PFID runtime and memory profile

## Question

Why does the migrated PFID notebook take longer and use more memory in v0.8 staging than in the pinned v0.7.4 reference?

## Evidence

The five-run process-tree profile is in `validation/benchmarks/memory-profile/summary.csv`.

- v0.7.4 reference: mean duration `69.94 s`; mean peak RSS `3327.7 MiB`.
- v0.8 staging: mean duration `180.05 s`; mean peak RSS `5143.5 MiB`.
- Staging is `2.57x` the reference duration and uses `1815.8 MiB` more peak RSS (`54.6%`).

The low-overhead public fit records are in `validation/benchmarks/memory-profile-phase-timing/runs/staging/run-01/fit-calls.json`. The staging notebook performs two dry runs and two real fits. Each recorded fit used one function evaluation. The two real fits took about `20 s` and `60 s`; the dry runs took about `22 s` and `59 s` in that diagnostic run.

The structural phase capture is in `validation/benchmarks/memory-profile-phase-coarse-fixed/runs/staging/run-01/fit-calls.json`. It is not valid for absolute wall-clock comparison because wrapping frequent internals adds substantial observer overhead. It does establish that the second model creates three linked optimization objectives and reconstructs results for seven guide datasets plus the measured datasets, with 17 dataset SVD operations.

## Current explanation

The staging orchestration explicitly validates the models with dry runs before the real fits. Those dry runs calculate objectives and construct result data, so they add roughly half of the staging duration. The remaining gap is concentrated in staging result reconstruction for the larger multi-objective fit. `OptimizationObjective.create_multi_dataset_result()` copies each model dataset, builds residual and fitted-data arrays, creates element and data-model result datasets, and adds SVD data for every dataset. The reference path creates result data through its optimization groups after the optimizer call and does not split this model into the same three objective instances.

Peak RSS is consistent with staging retaining and reconstructing more result arrays across those objectives. The profile establishes the peak difference and the workload shapes; it does not claim an exact per-array allocation breakdown.

## Disposition

Investigation evidence is complete enough to explain the observed runtime and peak-RSS differences. No staging core change is proposed from this profile alone. A separate memory-profiler run is required before attributing the RSS delta to one specific allocation site.

## 2026-09-13 rerun after the staging optimizations

The figures above were measured on 2026-09-01. The staging optimizations landed
on 2026-09-12 in `f601c1a4` ("AI guided optimizations on staging") and
`5dd45d5f` ("Avoid mutating shared optimization matrices"), so the profile
predated them. The profile was rerun on the current staging tree
(`879c5bce`, which contains both) with the same five-repetition protocol.

New artifacts: `validation/benchmarks/memory-profile-postopt/`.

### Result

| Branch | Metric | 2026-09-01 | 2026-09-13 | Change |
|---|---|---:|---:|---:|
| main (v0.7.4) | mean duration | 69.94 s | 71.16 s | +1.8% |
| main (v0.7.4) | mean peak RSS | 3327.7 MiB | 3310.3 MiB | −0.5% |
| staging (v0.8) | mean duration | 180.05 s | 137.32 s | **−23.7%** |
| staging (v0.8) | mean peak RSS | 5143.5 MiB | 5130.8 MiB | −0.2% |
| staging (v0.8) | mean sampled RSS | 3428.2 MiB | 2949.2 MiB | **−14.0%** |

The staging-to-reference duration ratio improves from **2.57x to 1.93x**. The
peak-RSS gap is essentially unchanged at **+1820 MiB (55.0%)**, previously
+1815.8 MiB (54.6%).

### Where the time went

Public fit records for the four optimizer calls, comparing the pre-optimization
low-overhead capture in
`validation/benchmarks/memory-profile-phase-timing/runs/staging/run-01/fit-calls.json`
with `validation/benchmarks/memory-profile-postopt/runs/staging/run-01/fit-calls.json`:

| Call | 2026-09-01 | 2026-09-13 |
|---|---:|---:|
| model 1 dry run | 22.38 s | 19.34 s |
| model 1 real fit | 20.02 s | 16.16 s |
| model 2 dry run | 58.66 s | 23.24 s |
| model 2 real fit | 60.06 s | 23.26 s |
| total in fits | 161.1 s | 82.0 s |

All four calls still use one function evaluation, so the workload is unchanged.
The gain is concentrated in the second model — the three-objective linked fit
over eight datasets — which is exactly where the earlier phase capture put the
cost (`create_multi_dataset_result` accounted for 49.98 s and 51.75 s of those
two calls). Both dry runs remain, and they still account for roughly half of
the staging duration.

### Revised disposition

The runtime finding is superseded: staging is now **1.93x** the reference
duration for this notebook, not 2.57x. The memory finding stands unchanged —
the optimizations were compute-side and did not reduce peak RSS, so the +55%
peak-RSS gap and the pending attribution to a specific allocation site remain
open. Mean sampled RSS did fall 14%, which is consistent with fewer retained
intermediate arrays during result construction without a lower high-water mark.

### Provenance caveat

The reference notebook hash is unchanged between the two runs. The staging
notebook hash differs, consistent with the shared-helper consolidation recorded
in `issues/notebook-compatibility-consolidation.md`. The fit-call structure is
identical across both runs (two dry runs and two real fits, one evaluation
each), and the per-call timings above localize the improvement to the fits
themselves rather than to notebook scaffolding, but this run is not a
byte-identical replay of the 2026-09-01 staging notebook. The new run also
passed `--record-fit-calls`, whose hook overhead makes the staging duration
slightly conservative.
