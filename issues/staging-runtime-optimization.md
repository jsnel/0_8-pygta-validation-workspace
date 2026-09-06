# v0.8 staging runtime optimization — handover

Status: **partially complete, correctness gate passed on the primary metric (fitted data)**.
Paused for token budget. This document is the pick-up point.

## User-approved contract decisions (do not re-litigate)

- **Tolerance parity, not bitwise**: optimized staging is accepted if the semantic
  comparison vs baseline staging passes existing scenario tolerances and the
  optimization converges successfully. Bitwise identity is NOT required.
- **Dependency bump approved**: staging env may move SciPy 1.14.1 → 1.15.x and align
  numpy/numba with the main (v0.7.4) stack. This is within `pyproject` (`scipy>=1.7.2`).

## What was changed

### Environment (the dominant lever)
`temp/pyglotaran-staging-dev/.venv`:
- numpy 2.0.1 → 2.2.6
- scipy 1.14.1 → 1.15.3
- numba 0.60.0 → 0.63.1 (llvmlite 0.43.0 → 0.46.0)

This matches the main/reference stack (numpy 2.2.6 / scipy 1.15.3 / numba 0.63.1) and
switches NNLS from SciPy 1.14's pure-Python `_nnls` to 1.15's Cython `_cython_nnls`.
Pre-bump freeze: `validation/runs/staging-env-before-bump.txt` (revert with
`uv pip install --python ...\.venv\Scripts\python.exe numpy==2.0.1 scipy==1.14.1 numba==0.60.0`).

### Code (staging core @ `51574847`, all value- or bit-exact)
Three files modified (uncommitted, `git diff` in the staging submodule):
1. `glotaran/optimization/objective.py` — `get_dataset_amplitudes`: vectorized the
   O(slices×labels) Python gather (was `estimated_amplitude_axes[i].index(label)` per
   element + per-element xarray ops) into per-index `np.take` fancy-indexing. Value-exact.
2. `glotaran/builtin/items/activation/gaussian.py` — `calculate_dispersion`: replaced the
   per-slice `parameters()` pydantic-object loop with a vectorized numpy polynomial
   evaluation. Verified **bitwise** identical (max abs diff 0.0) vs the original path.
3. `glotaran/builtin/elements/pfid/element.py` — `create_result`: replaced label-based
   `.sel()` + xarray `_binary_op` arithmetic with positional `np.take` + raw-array ops,
   one xarray construction. Dims/coords/values preserved (smoke-tested).

A `matrix.py` copy-removal edit was **reverted**: it changed FP association order, shifting
the optimizer trajectory (48 vs 16 evals) for only ~0.1 µs/call. Not worth the risk.

## Measured results (threads=1, fresh subprocess; public `Scheme.optimize` call only)

### Standard examples (original workload, 1 warmup + 5 reps)
| Case | baseline staging | optimized staging | main v0.7.4 | nfev |
|---|---|---|---|---|
| ex_two_datasets | 1.60 s | **1.21 s (−24%)** | 1.09 s | 17 (both) |
| ex_spectral_guidance | 3.62 s | **2.21 s (−39%)** | 3.74 s | staging 21 / main 23 |

Raw runs: `validation/benchmarks/raw/perf-baseline-20260906`,
`perf-optimized-20260906`, `perf-optimized-scipyonly-20260906`.
Aggregate: `python validation/perf_aggregate.py <raw_root>`.

### Controlled multi-step benchmark (perturbed +5%, matched budget)
`validation/benchmark_perturbed.py` inserts a prelude that scales free-parameter initial
values by `--perturb` and raises `--max-nfev`, so the fit does genuine multi-step work
(production notebooks untouched). two_datasets at +5%, matched 30-eval trajectory:
objective 2.20 s → 1.48 s (−33%), per-eval 8.4 → 5.7 µs.

### PFID (instrumented phase capture, `validation/profile_staging_objective.py`)
| call | baseline | optimized (all 3 edits) |
|---|---|---|
| dry-run #1 | 68.5 s (obj 10.7 + get_result 56.8) | 48.9 s (obj 10.6 + get_result 37.3) |
| real fit #1 | 61.1 s (obj 4.5 + get_result 55.7) | 40.0 s (obj 4.8 + get_result 34.2) |
| dry-run #2 (7 guide datasets) | 206.0 s (get_result 196.2) | 199.7 s (get_result 190.1) |
| real fit #2 | — (profile killed) | 187.0 s (get_result 178.2) |

PFID is **result-construction-bound**, not objective-bound. The amplitude/dispersion
vectorizations cut calls #1/#2 get_result by ~35%. The multi-dataset call (#2, 7 guide
datasets) get_result is still ~190 s and was NOT reduced by the PFID element rewrite —
the residual hotspot is elsewhere.

## Correctness (staging-self, tolerance gate)

Report: `validation/comparisons/staging-self-20260906-perf.json`.
Comparator: `validation/compare_staging_self.py` (loads both trees via the v0.8
compatibility loader, applies `scenarios.yml` tolerances).
- 11/11 optimized notebooks passed (`validation/runs/staging-optimized/20260906-perf`).
- **fitted_data normalized-RMS passes the scenario gate for all 13 comparable scenarios**;
  worst is ex_spectral_guidance dataset1 = 1.10e-6 (≈ the 1e-6 default gate; that scenario
  has documented non-identifiable representation freedom). All others 1e-9…1e-16.
- `study_transient_absorption/two_dataset_analysis` flagged "missing" by the self-comparator —
  a **loader artifact** (its datasets are stored in a different layout), not a real difference.
- ex_spectral_guidance parameters differ (max_rel ~9e-3) — consistent with the documented
  non-identifiability; fitted data is the gate.

## Open items / next steps

1. **PFID multi-dataset get_result (~190 s)** is the big remaining cost. cProfile earlier
   pointed at xarray `array_eq`/`_binary_op`/`xindexes` inside `create_multi_dataset_result`
   → `create_dataset_result` (`get_dataset_residual`, `unweight_result_dataset`,
   `add_svd_to_result_dataset`) and the residual `create_data_model_results` path. Profile
   call #2 specifically (`validation/runs/profile-pfid-optimized-02/profile.txt`) and
   vectorize the residual gather the same way as the amplitudes.
2. **PFID correctness comparison** — the self-comparator only covers the 11 standard
   examples. PFID (a case-study notebook) needs its own baseline-vs-optimized result
   comparison (run the notebook pre- and post-edit, compare `result*.nc`/`*.csv`).
3. **PFID memory** — measure peak RSS (baseline was 5.1 GiB vs main 3.3 GiB) with
   `validation/profile_notebook_memory.py` to see if the env bump / vectorizations moved it.
4. **Main-vs-staging final comparison** — required because the change is substantial
   (runtime realignment). Run `validation/AGENT_RERUN.md` fully and check whether the
   pre-existing ex_spectral_guidance REGRESSION (1.257e-6) changes now that staging uses
   the same Cython NNLS as main. Do NOT silently reclassify it; report transparently.
5. **Controlled benchmarks for spectral_guidance and PFID** (the perturbed multi-step
   variant) — only two_datasets was done.
6. **Cleanup**: delete `temp/pyglotaran-staging-baseline-core` (a throwaway worktree
   created for a baseline controlled run; its `.venv-baseline` install failed and is
   unused). The `validation/perf_aggregate.py`, `compare_staging_self.py`,
   `benchmark_perturbed.py`, `profile_staging_objective.py` helpers are diagnostic
   instruments — keep or remove per repo convention (they are not committed).

## Notes / risks

- spectral_guidance nfev differs (staging 21 vs main 23) — the known current-tree
  divergence, unchanged by this work.
- The numba kernels (`@nb.jit(parallel=True)`) give no speedup on these small matrices
  (verified: threads=0 ≈ threads=1). Adding `cache=True` would only cut per-process JIT
  (~1.3 s), not steady-state — low priority.
- `Optimization.run()` does a redundant final `calculate()` and (per
  `issues/spectral-guidance-current-tree.md`) leaves the parameters at the last evaluation
  instead of restoring `ls_result.x`. Fixing that is a correctness concern, out of scope
  here, and would change outputs slightly — flag for a separate focused fix.
