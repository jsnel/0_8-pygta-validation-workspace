# Final main-versus-staging validation — 2026-09-06

All 23 selected notebooks passed on each branch, and the common examples meet their semantic acceptance contract. The case studies retain 11 fitted-data differences above `1e-6`, so this run does not establish unconditional scientific equivalence across all studies. The separate runtime benchmark is complete and remains report-only.

## Scope and provenance

The run preserves the current optimized source trees, parameter initialization, fixed/free settings, fit budgets and declared tolerances. It covers 11 common example notebooks per branch (14 result leaves, 15 public fit calls), plus all 12 selected case-study notebooks per branch (40 real fit calls) across six repositories. Dry runs and plotting execute as part of the case-study notebooks.

Reference core: `8f26be01d5a6ce63ec2556469ac3facc2d2cee68` (v0.7.4). Staging core: `f6a091eba4cd9663db7e5a71f625bd74457332c5`. Reference/staging examples: `23287837579b9ad150ca33cce2b34bba33ec1e0d` / `44e3747cf39f0482ed5c05578624577938159085`. The full revisions, pre-existing worktree changes, environment snapshots and commands are under `validation/runs/final-allfits-20260906-132646Z/`.

These are current-tree results evaluated against the existing scenario IDs and tolerances, not a rerun of every old revision in `validation/scenarios.yml`. The old pins were preserved. Both installed scientific stacks use NumPy 2.2.6, SciPy 1.15.3, Numba 0.63.1 and llvmlite 0.46.0. Staging's `uv.lock` still pins 2.0.1 / 1.14.1 / 0.60.0 / 0.43.0 respectively; a normal sync would change the environment tested here. Main's scientific dependency lock is aligned.

Reference execution uses the established plotting overlay under `temp/case-studies/TestCaseInitConc/reference/_plotting_dependencies`; staging uses its own extras package. All five numerical thread controls are set to one. No dependency, production notebook, model or core source was changed.

## Common examples

Both branches passed 11/11 notebooks. All 14 leaves are present and reloadable: 8 `PASS`, 6 documented `EXPECTED_DIFFERENCE`, zero `REGRESSION`, `BASELINE_FAILURE` or missing-artifact failures.

| Selected primary metric | Worst fitted-data normalized RMS | Tolerance |
|---|---:|---:|
| Spectral guidance | 2.4928654061006497e-7 | 1e-6 |
| Refined transient two-dataset analysis | 7.5917435074198285e-6 | 2e-5 |
| Weighted 3D analysis | 2.4462841311472268e-5 | 3e-5 |

Fresh paired outputs: `validation/runs/{main,staging}/final-20260906-131441Z/`. Full semantic report: [`v07-v08-final-20260906-131441Z.md`](../validation/comparisons/v07-v08-final-20260906-131441Z.md). Raw parameter/decomposition and derived default-metadata differences remain documented secondary evidence; none was forced into equality.

## Case studies and residual numerical differences

All 12 notebooks passed per branch and all 40 real-fit captures per branch are present and reloadable. Schema/load checks passed for 34 migrated schemes. The artifact audit verified 4,692 artifacts with zero missing files, hash mismatches or notebook-readability errors. Common source/result hashes were also checked against the runner manifests.

| Case study | Notebooks per branch | Fits meeting fitted-data tolerance | Fits with exact inputs | Worst fitted-data RMS |
|---|---:|---:|---:|---:|
| TestCaseInitConc | 1 | 1/1 | 1/1 | 2.52205e-8 |
| Streak PS1 protocol | 2 | 6/9 | 9/9 | 8.02692e-3 |
| TA PS1 protocol | 3 | 16/19 | 9/19 | 7.09790e-5 |
| 2023 publication | 2 | 1/2 | 2/2 | 4.31049e-2 |
| 2025 publication | 3 | 3/7 | 4/7 | 2.94023e-2 |
| PFID | 1 | 2/2 | 2/2 | 5.25548e-13 |
| Total | 12 | 29/40 | 27/40 | |

Twenty-one fits satisfy both exact-input and fitted-data requirements. All 40 retain the comparator's provisional `REVIEW_REQUIRED` classification because secondary arrays, parameter coverage or metadata also differ; this does not mean all 40 have differing fitted curves. There are zero missing-artifact classifications. Metrics are relative to reference fitted-curve RMS, not a percentage of experimental error or parameter uncertainty.

### Measured data versus guidance spectra (2026-09-09 review)

The 11 above-tolerance fit captures split into **7 with measured-data
differences** and **4 with guidance-only differences**. Of the latter, three
are standalone spectral fits and one is the final TA target fit, whose four
measured datasets all pass. The maxima in the table above combine these roles;
they must not be read as measured-data maxima.

Here “measured” means the experimental time-by-wavelength matrices, including
their existing preprocessing. “Guide” means an extracted SAS/SADS supplied as
a constraint or fitted separately to construct a guide. Classification was
checked against the captured reference notebooks' dataset mappings and guide
creation/loading cells, with array dimensions as corroboration, not the sole
criterion. These are dataset roles, not claims about the original experimental
provenance of every spectrum. Each value below is the maximum of the existing
per-dataset fitted-data normalized RMS values within that role; no arrays were
pooled or tolerances changed. A dash means that role is absent.

| Residual fit capture | Measured-data maximum (dataset) | Guide maximum (dataset) | Above `1e-6` in |
|---|---|---|---|
| Streak steps 1–2, fit 4 | `8.0269184e-3` (`CF9212WLtr1`) | — | Measured only |
| Streak steps 1–2, fit 5 | `3.5257849e-3` (`CF9212WLtr1`) | — | Measured only |
| Streak steps 1–2, fit 6 | `1.9688809e-3` (`CF9212WLtr1`) | — | Measured only |
| TA step 3, target fit 2 | `7.0978961e-5` (`670TR1`) | — | Measured only |
| TA step 3, spectral fit 13 | — | `1.1714565e-6` (`dataset`, free spectrum) | Guide only |
| TA step 3, final target fit 14 | `3.1373299e-7` (`670TR1`) | `1.2457040e-6` (`Ant1SADS`) | Guide only |
| 2023 linked fit | `3.8236963e-3` (`Syn7335WLtr2`) | `4.3104925e-2` (`WLRCSAS`) | Both |
| 2025 MCL initial target fit 1 | `3.1740110e-4` (`super2ns`) | — | Measured only |
| 2025 MCL spectral fit 2 | — | `2.8941735e-2` (`dataset`, PSI1) | Guide only |
| 2025 MCL spectral fit 3 | — | `1.8507978e-2` (`dataset`, PSII1) | Guide only |
| 2025 MCL final target fit 4 | `2.1837432e-4` (`super2ns`) | `2.9402274e-2` (`dataPSI1`) | Both |

**Measured-data investigation takes priority.** Streak fits 4–6 contain only
the three measured `CF9212WLtr1/2/4` matrices; TA target fit 2 contains only
`670TR1/2` and `700TR1/2`; the initial MCL target contains only `super1ns/2ns`.
All these inputs are exact across branches. Their differences cannot be
attributed to differing guidance inputs in those fits. Matching evaluation
counts do not prove matching optimizer trajectories or convergence. The next
diagnostic is a common-parameter objective/reconstruction comparison followed
by trajectory comparison at the earliest divergent fit. Final streak measured
fits already pass, so distinguish intermediate behavior from final outcomes.

The 2023 linked fit contains **25 measured matrices and 17 guides**, all with
exact inputs. All 25 measured comparisons and all 17 guide comparisons exceed
`1e-6`. Its measured maximum is about 0.382% of reference fitted-signal RMS,
whereas the previously quoted 4.31% is a guide maximum. This is still a
measured-data discrepancy. Identical guide inputs exclude propagation of
different upstream guides here, but do not exclude differences in how the
joint objective handles guidance, weights or linked spectra. Compare measured
and guide objective contributions separately at common parameters before
attributing the discrepancy to its two-evaluation budget.

**Guide construction and downstream influence require separate analysis.**
In TA fit 13 the free-spectrum input already differs by `8.4582054e-8`.
In the final TA fit the largest guide *input* difference is `freeSADS`
(`1.1714570e-6`), but the largest guide *fitted-output* difference is
`Ant1SADS` (`1.2457040e-6`); `freeSADS` fitted output itself passes at
`5.2835941e-7`. Thus the final exceedance is not simply the free-guide input
metric being repeated. All four measured inputs are exact and their fitted
outputs pass, despite differing guides. Controlled identical-guide fits would
separate propagated input effects from solver/reconstruction effects; the
present evidence does not establish either as the root cause.

MCL spectral fits 2 and 3 fit PSI1/PSII1 guides extracted from the initial
target's species spectra, not fresh experimental matrices. Their inputs
already differ by `3.2077644e-2` and `1.4412083e-2`; fit 2 also has 20 versus
25 evaluations. These are not identical-input engine comparisons. The much
larger component-spectrum drift than reconstructed measured-data drift is
consistent with sensitivity of the decomposition, but does not by itself
prove non-identifiability. In the final MCL target, measured inputs remain
exact while PSI1/PSII1 guide inputs differ by `2.8941735e-2` and
`1.8507978e-2`. Both measured fitted outputs still exceed tolerance
(`1.6800592e-4`, `2.1837432e-4`), but the 2.94% headline belongs to a guide;
the measured maximum is about 0.0218%. Investigate the initial measured-data
divergence first, then repeat guide generation and the final fit with common
guides to isolate propagation.

Evidence: the four affected repositories' `fresh-captures.json` files under
`validation/comparisons/case-studies/final-allfits-20260906-132646Z/`, and their
paired captured worktrees under
`validation/runs/case-studies/final-allfits-20260906-132646Z/`. In particular,
the 2023 notebook explicitly defines `STREAK_CLP_GUIDE_DATASETS` and
`TA_CLP_GUIDE_DATASETS`; the MCL notebook creates guides using
`create_clp_guide_dataset`; the TA notebook loads the spectral inputs and
target guides from `guide/`. This review reuses the same paired final-run
evidence and source revisions recorded above. No fits were rerun, numerical
acceptance statuses changed, or root causes declared resolved.

### Original fit-level evidence

The remaining primary differences, retaining the original combined maxima, are:

- **Streak:** intermediate fits 4, 5 and 6 in steps 1–2 have RMS `0.0080269184`, `0.0035257849` and `0.0019688809`, with exact inputs and 7/7 evaluations. The final fit of that notebook is within tolerance at `4.89914e-8`; the final steps 3–4 fit is `8.56931e-9`.
- **TA:** target fit 2 is `7.0978961e-5` with exact inputs and 9/9 evaluations. Spectral fit 13 and final target fit 14 are `1.1714565e-6` and `1.2457040e-6` at 25/25 and 7/7 evaluations. Ten downstream fits receive slightly different generated inputs. In the final target, the `freeSADS` guide differs by `1.1714570e-6`; these downstream results cannot be treated as independent identical-input engine comparisons.
- **2023 publication:** the linked 25-dataset fit remains `0.0431049251` with exact inputs and 2/2 evaluations. A short budget is relevant context, not a demonstrated explanation. The other TA target fit passes at `7.22840e-7`.
- **2025 publication:** all four MCL fits exceed tolerance: `0.0003174011`, `0.0289417355`, `0.0185079781` and `0.0294022741`. The first has exact inputs; the next two receive inputs differing by `0.0320776435` and `0.0144120827`, and the final guided target receives guides differing by `0.0289417355`. The first spectral fit also uses 20 versus 25 evaluations, the only case-study evaluation-count mismatch. Whole-cell and both room-temperature fits pass (`2.41182e-8` or better), with exact inputs.

TestCaseInitConc has 13 exact datasets and matching three-evaluation endpoints. PFID's two fits have RMS `1.67742e-13` and `5.25548e-13`, exact inputs and 1/1 evaluations. These do not demonstrate a multi-step nonlinear optimization: staging PFID has zero free parameters and reports `No free parameters to optimize`; reference reports one free parameter and `gtol` termination after one evaluation. TestCaseInitConc stops at its budget. Reference's sole varying PFID label is `alpha.1`; its model references are commented out. This inactive-parameter accounting difference is retained as secondary evidence rather than treated as a changed scientific workload.

The next scientific work is to explain or explicitly disposition the above differences, starting with same-parameter evaluation of the earliest divergent fit in each chain and controlled identical-guide comparisons downstream. No root cause or acceptance exception is inferred solely from small budgets.

Complete fit-by-fit evidence: [`case-summary.md`](../validation/runs/final-allfits-20260906-132646Z/case-summary.md). Per-repository `fresh-captures.json`/`.md` reports are under `validation/comparisons/case-studies/final-allfits-20260906-132646Z/`. The independently checked artifact manifest and verification are under `validation/runs/case-studies/final-allfits-20260906-132646Z/`.

## Capture completeness correction

The initial case-study batch exposed a validation-runner collision: the streak steps 1–2 and steps 3–4 notebooks both captured their first `target_result1` to `streak/case-study-results/fit-001-target_result1/result.yaml`. The second notebook overwrote the first notebook's captured intermediate result.

`validation/case_studies/run_case_study.py` now namespaces captures by notebook stem, removing the staging `_v08` suffix so branch labels still match. This changes only validation-side save paths. The default standalone instrumentation API is preserved. A regression test covers two notebooks with the same result variable and fit index. The full validation suite passes: 37 passed, 1 skipped; focused staging optimizer/activation/PFID tests pass: 35 passed.

The first case-study batch is retained under `validation/runs/case-studies/final-20260906-131441Z/` as superseded evidence. All case studies were restarted under `validation/runs/case-studies/final-allfits-20260906-132646Z/`. Final comparisons use only real-fit captures declared by these fresh runner manifests, excluding historical and duplicate native saves copied with sources.

## Known residual implementation issue

The previously documented Gaussian shift/dispersion discrepancy reproduces in the current core: center 1, shifts `[0.5, 1]`, dispersion center 100, coefficient 2, axis `[0, 100]` gives `[-1, 1]` through `calculate_dispersion` versus `[-1.5, 0]` through the original parameter path. The former is used by activation result reconstruction. This is evidence about reported activation centers, not proof that an in-scope fitted curve is wrong. The probe is retained at `validation/runs/final-20260906-131441Z/gaussian-shift-probe.json`.

No core fix or unconditional scientific-equivalence claim is included in this rerun. Budget-limited fits must not be called converged merely because a saved `success` flag is true.

## Runtime benchmark

The first full benchmark attempt is retained under `validation/benchmarks/raw/final-20260906-131441Z/` and excluded from performance claims. Its staging two-dataset worker incorrectly counted the newly added `dry_run=True` call as the declared real fit, then rejected the real fit as an unexpected second invocation. This was a benchmark instrumentation failure, not a notebook or optimizer execution failure.

The staging hook now executes dry runs without timing or numbering them among the 15 real fits. A regression assertion verifies the dry run executes, emits no timed sample, and leaves the subsequent real fit numbered one. The affected native worker passes and records the real fit's 11 function evaluations. The validation suite still passes: 37 passed, 1 skipped. A fresh complete one-warmup/five-repetition benchmark completed under `validation/benchmarks/raw/final-real-fits-20260906-1915Z/`: 12 successful workers, 150 timed samples, 15 summaries, `REPORT_ONLY`. Branch order alternated and all numerical thread controls were one. Notebook setup, plotting, saving, comparison and dry runs are outside timing.

Function-evaluation counts match across all repetitions for 14/15 fits. Spectral guidance uses 23 reference versus 21 staging evaluations; its observed staging/reference time ratio of `0.589` is not an implementation-only speedup. For the other fits, mean-time ratios range from `0.850` to `1.630`. Examples:

| Real fit | Reference mean seconds | Staging mean seconds | Staging/reference |
|---|---:|---:|---:|
| Transient absorption target | 5.0895 | 4.3259 | 0.850 |
| Refined transient two datasets | 10.6438 | 9.6436 | 0.906 |
| Fluorescence target | 0.2889 | 0.4711 | 1.630 |
| Example two datasets | 1.1161 | 1.6537 | 1.482 |
| Weighted 3D | 1.4350 | 2.0910 | 1.457 |

These are observed current-reference/current-staging public-call times, not a remeasurement of the optimization patch against its parent or a release gate. The full JSON retains sample standard deviations, medians, ranges, individual samples and workload warnings. No overall speedup is claimed.

Report: [`runtime.json`](../validation/benchmarks/final-real-fits-20260906-1915Z/runtime.json), [`runtime.csv`](../validation/benchmarks/final-real-fits-20260906-1915Z/runtime.csv). PNG/SVG plots accompany them. Benchmark manifest SHA-256: `521afa93e626f61ec046b8387be025e8a857d2df0a5202b6d686ffdd2ed39c77`.

## Handoff and verification

The validation-only changes are the notebook-specific capture paths in `validation/case_studies/run_case_study.py`, dry-run exclusion in `validation/benchmark_hooks.py`, their tests, and the clarified benchmark manifest comment/documentation. The root overview, investigation index and historical release report point to this evidence.

Tests: 37 passed, 1 skipped in `tests-benchmarkfix.log`; focused staging core tests: 35 passed in the initial final-run directory's `tests-core.log`. `git diff --check --ignore-submodules=all` passes. Exact validation-tool hashes are recorded in `validation-tooling.json`. `final-source-state.json` confirms all nested checkout revisions and Git statuses match the pre-run snapshot. These sidecars live under `validation/runs/final-allfits-20260906-132646Z/`.

No commit was made. The pre-existing deletion of `testcase-init-conc-validation-prompt.md` and all migrated case-study changes were preserved. Failed/superseded attempts and generated scientific evidence remain on disk and are not staged.

## 2026-09-12 — MCL evidence refreshed

The fresh corrected MCL notebook pair supersedes the historical MCL rows above
for current-input conclusions, without changing the other case-study evidence.
Both complete notebooks pass with four captured fits per branch. First target
measured-data RMS is `2.83278e-8`; final target measured-data maximum is
`7.55223e-8`. Remaining exceedances are guidance-only: standalone PSII guide
`9.34540e-6`, final PSI/PSII guides `1.23848e-6` / `5.86775e-6`.
A separate 200-budget first-fit pair reaches `ftol` at 21/21 evaluations and
matches fitted data at `1.14330e-8`. The large concentration amplitude difference
is the dataset-scale export convention; all-nine-species profiles agree after
that convention is aligned. [Fresh report and rate table](../validation/comparisons/case-studies/20260912-110000Z-mcl-refresh/mcl-refresh-summary.md).
No global acceptance count is recomputed by mixing this focused rerun with
historical runs. Source cores remain `8f26be01` / `f6a091eb`.
