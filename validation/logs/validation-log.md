# Validation log

## 2026-07-11 — baseline setup and first comparison

- Initialized both orchestration worktrees at their recorded parent gitlinks and nested validation submodule pins.
- Created independent Python 3.10.19 environments with `uv sync`.
- Verified editable package versions: v0.7.4/main and v0.8.0.dev0/staging.
- Collected 577 tests from the pinned result-consistency suite in both environments.
- Executed all 11 pinned `pyglotaran-examples` notebooks in each environment through the root `validation/run_examples.py` runner: 11/11 passed on each side.
- Generated isolated result bundles under `validation/runs/` and compared the common leaf scenarios with `validation/compare_results.py`.
- Exact input-data arrays matched for every mapped dataset. Fitted-data arrays are often within the first-pass tolerance; residuals and optimized parameters differ in multiple scenarios and require scenario-level triage.
- Saved-result layouts differ materially: v0.7 stores rich per-dataset NetCDF files, while staging stores separate result components and uses a `_staging` output-folder suffix.
- `ex_doas_beta` staging currently does not save a result bundle because its `result.save(...)` line is commented out; this is recorded as a missing comparison artifact, not yet classified as a pyglotaran regression.
- The initial comparison is evidence for triage only; it is not a release-parity verdict.

### Test results

- v0.7.4 `pyglotaran-extras/tests`: 145 passed, 1 xfailed.
- v0.8 staging `pyglotaran/tests`: 424 passed, 9 xfailed.
- v0.8 staging `pyglotaran-extras/tests`: 133 passed, 2 failed, 10 errors. The failures are existing staging-support/test-API mismatches: schema fixture drift and fixtures calling the old `Scheme.optimize(parameters, ...)` signature.
- v0.7.4 pinned stored-reference validator: 577 passed after installing the validation-only `pytest-allclose==1.0.0` overlay.

### 2026-07-11 — impact-ranked comparison

Generated [v07-v08-detailed.md](../comparisons/v07-v08-detailed.md) and its JSON companion. The leading evidence is:

- the translated transient-absorption target scheme changes the `[720, 890]` weight from `0.2` in v0.7 to `0.1` in staging; its fitted-data normalized RMS difference is `2.785e-3` and its largest parameter-relative delta is `25.2%`;
- `rates.k3d2` in the two-dataset transient-absorption case changes from approximately `1.25e7` to `1.94e25` while fitted-data normalized RMS difference remains `1.383e-5` and chi-square is effectively unchanged;
- staging omits 15 `weighted_root_mean_square_error` dataset metadata values that exist in v0.7;
- `simultaneous_analysis_3d_weight` has a smaller normalized fitted-data difference (`2.446e-5`) and a `2.596e-5` relative scale delta;
- input data arrays are exact for every mapped dataset, so the dominant remaining work is model translation, parameter-pathology, diagnostics, and persistence comparison rather than data loading.

## 2026-07-12 — semantic parity remediation

- Added the manifest-driven scenario contract in `validation/scenarios.yml`: 14 declared leaves from the 11 common notebooks.
- Added the external `validation/compatibility/` layer for v0.7 monolithic and v0.8 split results. It canonicalizes dimension aliases, aligns coordinates by labels, maps scale metadata, derives weighted RMSE from persisted/default weights, and retains unmapped raw variables for review.
- Corrected the staging target notebook's optimizer budget from 11 to the v0.7-equivalent 10 function evaluations. Direct source and saved-result inspection showed that the declared target uses weight `0.1` on `[720, 890]` on both pinned branches; the `0.2` weight belongs to the separate CO/CO2 scheme, so no speculative target weight change was retained.
- Re-enabled staging DOAS result saving and preserved all four spectral-constraint leaves as separate result directories.
- Added four focused compatibility/translation tests: `4 passed`.
- Clean remediated notebook runs: v0.7.4 `11/11`, v0.8 staging `11/11`.
- Final semantic comparison: `8 PASS`, `6 EXPECTED_DIFFERENCE`, `0 REGRESSION`, `0 BASELINE_FAILURE`, `0 BLOCKED`; worst accepted fitted-data normalized RMS is `2.446e-5` in the documented weighted case.
- Remaining expected differences are limited to the weakly identified `rates.k3d2` path, non-identifiable/decomposition representations, and the documented weighted solver/scale drift. No broad pyglotaran core change was made.
- Reproducibility evidence is embedded in `comparisons/v07-v08-semantic.json`: Python/package versions, source-tree SHA-256 values, lockfile SHA-256 values, notebook source-tree SHA-256 values, and result-tree SHA-256 values.

## 2026-07-12 — main feature ports to staging

- Created staging branch `feature/port-main-features-to-staging` from `7efc9d1114a2455da8bc37fc4770a455ef2e437a` and produced five individual commits: matrix ordering `4b48f373`, PFID `f33ac3c0`, ASCII NumPy scalars `b6be5f86`, pandas 3 compatibility `fc542d27`, and SVD/simulation dimension ordering `468c4cd5`.
- Each feature commit includes its implementation, focused regression tests, and its own v0.8 `changelog.md` entry.
- Focused PFID/model/parameter tests passed (`11 passed`); ASCII tests passed (`3 passed`); SVD/simulation tests passed (`10 passed`). Parameter and pandas IO coverage passed in both Python 3.10/pandas 2 (`80 passed`) and isolated Python 3.11/pandas 3.0.1 (`80 passed`).
- Full staging suite: `448 passed, 9 xfailed`.
- Restored the previously documented staging-example parity inputs in the checked-out examples tree: target budget 10, spectral-guidance budget 21, two-dataset budget 17, DOAS saving, and four separately saved spectral-constraint leaves.
- Corrected the staging orchestration contract pin to the checked-out revision `be1c861cfce21db94e1a360e882df4c8e942a40e`.
- Fresh notebook evidence under `validation/runs/{main,staging}/20260712-175136`: v0.7.4 `11/11`, staging `11/11`.
- Semantic report `validation/comparisons/v07-v08-20260712-175136.json`: `8 PASS`, `6 EXPECTED_DIFFERENCE`, zero `REGRESSION`, zero `BASELINE_FAILURE`, all 14 declared leaves present, acceptable `true`.
- Validation-side regression tests: `10 passed`.
- Runtime report `validation/benchmarks/v07-v08-runtime-20260712-175136/runtime.json`: `REPORT_ONLY`, 12 successful workers, 150 samples, 15 summaries, all function-evaluation workloads matched, and no warnings.

## 2026-08-28 — external case-study visual-review evidence

- Pinned paired reference/staging bases for `pygta-protocol-streak-PS1` (`dcad534e0f6c809c9b7aa03c646ea1796192a0b7`), `pygta-protocol-TA-PS1` (`d7612bc9a7f79812c4ad7c5cfcef0ccaecda0c59`), and `pub-2023-05-van_Stokkum_et_al` (`6bf9c260deaa014ce9cf5327c5c8e521ce9883a2`). The initial tracked trees match, with no submodules or Git LFS files.
- Preserved all reference and original v0.7 files. Added isolated `_v08` scheme/notebook copies in staging and committed them on each repository's `staging` branch: `f186361713a74fc7c6605b0f4a442d1e1c7947eb`, `f837892b1bbf3c31e068ae79fa44ea6653fe676b`, and `e253a7ea226a069823d94568dface2b7b66cfaf4` respectively.
- Generated parameter-aware schemas where statically paired parameters were available and strictly loaded all 25 migrated schemes. The two spectral guide schemes are recorded as `NOT_PRACTICAL` for parameter-aware schema generation but loaded successfully.
- Final isolated run `validation/runs/case-studies/20260828-203340Z`: 7/7 untouched v0.7.4 reference notebooks and 7/7 committed v0.8 staging notebooks passed. The migrated notebooks recorded 30 load/dry-run validations and 30 real fits.
- Extracted paired inline plot evidence: streak 44/44, transient absorption 81/81, and publication 58/58 reference/staging images. The notebooks generated no file-based plots; manifests record empty file-plot lists. Native reloadable result artifacts and hashes are retained alongside executed notebooks, logs, commands, dependency metadata, and base-to-staging patches.
- Provisional semantic reports under `validation/comparisons/case-studies/20260828-203340Z/` contain 9/9 result leaves with no missing artifacts and matching function-evaluation counts. All three repositories remain `REVIEW_REQUIRED` at the comparison layer; notably, the linked publication result has worst fitted-data normalized RMS `1.7078610902271951`. No scientific parity, expected-difference/regression label, root cause, or subjective visual decision was assigned.
- The top-level and per-repository manifests classify all three repositories `READY_FOR_VISUAL_REVIEW`. `validation/runs/case-studies/20260828-203340Z/verification.json` passed 1,302 artifact path, hash, and executed-notebook readability checks with no errors.
- Validation-side tests: `12 passed in 1.90s`. Runtime benchmarking was not run because optimizer/runtime behavior and benchmark instrumentation were unchanged.

## 2026-08-29 — post-penalty-fix baseline rerun

- Validated reference revisions `78ffaf5a` / `8f26be01` / `5e157363` / `dcbe4baa` against staging orchestration `5889e03d`, core `fb001015`, examples `7f7fd227`, and extras `d57940be`. The staging core includes kinetic activation normalization and restored v0.7 signed/nearest-sample equal-area semantics.
- The first staging reruns exposed two result-path regressions in the equal-area implementation: xarray scalar slice indices and an unexpanded index-independent matrix during result metadata construction. Focused fixes were committed as core commits `af9d5d5d` and `fb001015`; the latter is pinned by staging orchestration commit `5889e03d`.
- Accepted notebook artifacts: reference `validation/runs/main/20260829-162147Z` and staging `validation/runs/staging/20260829-162539Z`, each 11/11 notebooks passed. Failed intermediate staging evidence remains under `validation/runs/staging/20260829-161618Z` and `validation/runs/staging/20260829-162147Z`.
- Semantic report `validation/comparisons/v07-v08-20260829-162539Z.json`: all 14 leaves present; `8 PASS`, `6 EXPECTED_DIFFERENCE`, zero `REGRESSION`, zero `BASELINE_FAILURE`, acceptable `true`.
- Scenario statuses and fitted-data metrics are unchanged from `v07-v08-20260712-175136.json`. The `rates.k3d2`, spectral-guidance decomposition, weighted 3D scale, weighted-RMSE persistence, and representation investigations therefore remain open; none was resolved by these fixes.
- Core optimization/kinetic regression tests: `73 passed`. Validation-side regression tests: `12 passed`.
- Runtime report `validation/benchmarks/v07-v08-runtime-20260829-162539Z/runtime.json`: `REPORT_ONLY`, 12 successful workers, 150 samples, 15 summaries, all function-evaluation workloads matched, and no workload warnings.
