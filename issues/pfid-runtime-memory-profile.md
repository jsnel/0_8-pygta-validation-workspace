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
