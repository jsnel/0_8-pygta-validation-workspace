# v0.7.4 reference versus v0.8 staging: release decision report

The numerical evidence below is historical. The later
[final validation run](../issues/final-validation-run.md) supplies fresh paired
results for all 23 notebooks per branch at optimized staging `f6a091eb`.

Evidence review: 6 September 2026. Workspace HEAD at review: `a58aeaf3397492df5a4feb7c56d0b81cf5b3131f`. This is a review of retained evidence, with no new scientific runs, tolerance edits, core changes, branch changes, or commits. Existing working changes and generated artifacts were preserved.

**Recommendation: accept v0.8 as sufficiently equivalent for the established common-example scope, with the explicitly accepted spectral-guidance exception. Do not yet claim repository-wide scientific equivalence or retire v0.7 unconditionally.** Several external publication/protocol fits still have substantial, unclassified fitted-data differences. Their successful execution is valuable migration evidence, but does not settle scientific parity. A release with a clearly limited support scope is defensible; promotion coupled to complete v0.7 retirement needs the blockers below resolved or explicitly dispositioned by the release owner.

## Decision basis and provenance

The authoritative common contract is [scenarios.yml](scenarios.yml): 11 notebooks, 14 saved result leaves, and 15 public fit calls. Fluorescence executes two fits but contributes one declared leaf; spectral constraints contribute four leaves from one notebook. The six external repositories in [cases.yml](case_studies/cases.yml) add 12 selected notebooks, not an exhaustive test of every possible model or public API.

| Component | Pinned reference | Pinned staging | Current reference | Current staging |
|---|---|---|---|---|
| Orchestration | `78ffaf5a64eab8be330652d3c8a6eceb5d071d3f` | `5889e031c866ae2ee23f95c1e1ee4b023cba7e38` | `0fa7b0fc1890d301fed138b73ee8aaaf33f35fcd` | `5b6314266a597520c9f178c804aa14f4e7af5a09` |
| Core | `8f26be01d5a6ce63ec2556469ac3facc2d2cee68` | `fb00101532deeb25782be67cdf18e9ecc2ea392a` | `8f26be01d5a6ce63ec2556469ac3facc2d2cee68` | `51574847bd5cd0e98a6c301f3d557d6d4ed85cd2` |
| Examples | `5e157363ca6e776c3da7a6c4742a07930d205138` | `7f7fd227bcfb74308523d2242ca811a68ba25214` | `409af6f4f5f1979b669a0729c0443600cf307b73` | `4eed89efe8466b4e051fad7be8fcbf37b4c2a0b7` |
| Extras checkout | `dcbe4baad5949768b65bf602d58018b5fe309f0a` | `d57940be02751c670ee90f3bc09af7cd954a1d08` | `96dbbbbc0cede1ecb932a202202cdf903a9894f8` | `700f9de482f317afa0339edc12314fd14699e459` |

Current revisions were checked with recursive submodule status. Current staging core is clean and includes `dea39145` (skip unresolved coefficient relations) and `51574847` (zero-free-parameter optimization). The old relation issue's “uncommitted” wording is historical, not the current core state. A revision alone does not describe a migrated case-study tree: retain its manifest, source patch, untracked-file inventory, and content hashes.

The accepted pinned evidence is [20260829-162539Z JSON](comparisons/v07-v08-20260829-162539Z.json), with [reference manifest](runs/main/20260829-162147Z/manifest.json) and [staging manifest](runs/staging/20260829-162539Z/manifest.json): 11/11 executions each, 14/14 leaves, 8 PASS, 6 EXPECTED_DIFFERENCE, no regression or missing-artifact failure. It follows kinetic-normalization and equal-area fixes and reproduces the July metrics. The reference/staging timestamps differ because earlier staging attempts failed; the successful pair is explicitly recorded in the [validation log](logs/validation-log.md). Intermediate failures remain preserved.

The latest paired current-tree evidence is [20260906-022046 JSON](comparisons/v07-v08-20260906-022046.json), [reference manifest](runs/main/20260906-022046/manifest.json), and [staging manifest](runs/staging/20260906-022046/manifest.json). Both execute 11/11 and supply 14/14 leaves: 8 PASS, 5 EXPECTED_DIFFERENCE, **1 REGRESSION; automated acceptable=false**. The preceding [015900 report](comparisons/v07-v08-20260906-015900.json) reproduces the same spectral result. These are not runs at the pinned contract revisions.

Successful current reference execution uses a pristine extras plotting overlay at `dcbe4baa`, because the current extras checkout has syntax incompatible with reference Python 3.10. It does not test current reference extras natively. The manifest records the actual imported source path/hash; the overlay has no local lockfile. Native numerical dependencies also differ: reference NumPy/SciPy/Numba `2.2.6/1.15.3/0.63.1`, staging `2.0.1/1.14.1/0.60.0`. See [consolidation provenance](../issues/notebook-compatibility-consolidation.md) and [spectral isolation](../issues/spectral-guidance-current-tree.md). Historical reports containing a copied contract must not be mistaken for proof that every executed source matched that contract.

## Scientific acceptance and the explicit exception

The primary metric is RMS(staging fitted data − reference fitted data) divided by max(RMS(reference fitted data), machine epsilon), after dimension/coordinate alignment. Inputs are compared exactly after canonicalization. Ordinary fit tolerance is `1e-6`; transient two-dataset tolerance is `2e-5`, weighted 3D tolerance `3e-5`; parameter tolerances are `rtol=1e-4`, `atol=1e-8`. These are engineering parity criteria, not confidence intervals or proof of parameter identifiability. See [metric implementation](compatibility/metrics.py), [common comparator](compare_results.py), and [case-study comparator](case_studies/compare.py).

**Accepted exception SG-20260906:** the user explicitly accepts current spectral-guidance fitted-data normalized RMS **`1.2572461877946428e-6` against the unchanged `1e-6` threshold**. The result exceeds the threshold by about 25.7%; the original threshold did not pass. The generated status remains REGRESSION and automated acceptable remains false. This report records a release-level exception only, without editing measurements, tolerances, or machine classifications.

Both branches intentionally use the same constrained model: `rates.k5`, `rates.k6`, and `scale.2` are fixed, leaving three free parameters instead of six. The shared parameter file hash is `59aa7dfb5957496c4c7fe05c6716fbb927c29b87b53aeeea30c1102f13528897`; raw input files also match. The difference is not a one-sided constraint or mistranslation. [Native paired probes](runs/spectral-isolation-20260906-final/summary.json) reproduce saved fitted arrays bit-for-bit. Restoring only pinned vary flags in memory reproduces `3.0325968790706684e-7`; this is diagnostic evidence, not a proposed model change.

Matching reference numerical runtime and compartment order gives bitwise objective, Jacobian, and full optimizer-trajectory equality. NNLS substitution and finite-difference experiments support numerical-path sensitivity. Increasing staging's budget does not remove its endpoint difference; its objective is lower than reference's, which also does not prove parity. Residual runtime effects are not assigned to a particular BLAS/NumPy instruction. The [opt-in trajectory test](tests/test_spectral_guidance_probe.py) passed once in the retained investigation; it validates the controlled configuration, not the native threshold. This exception does not waive any external case-study difference.

## Common examples: coverage and outcomes

All rows below executed in both pinned and current pairs. P = PASS; E = EXPECTED_DIFFERENCE; R = generated REGRESSION. Values are worst fitted-data normalized RMS, rounded for readability; the linked JSON reports retain full precision.

| Scenario / unique exercised feature | Pinned metric/status | Current metric/status |
|---|---:|---:|
| Fluorescence global and target analysis: sequential/target kinetic analysis and legacy result plotting; two fit invocations, one saved leaf | 1.4765553e-9 P | 1.4765553e-9 P |
| Transient absorption target: kinetic target model, IRF and interval weighting; corrected shared 10-evaluation budget | 4.9003075e-8 P | 4.9003075e-8 P |
| Transient absorption two datasets: linked CO/CO2 kinetics, dataset-specific rates/weights and derived parameters | 1.3827654e-5 E | 2.4996999e-8 E |
| Spectral constraints, no penalties first run | 2.2793562e-8 P | 2.2793562e-8 P |
| Spectral constraints, no penalties repeat | 2.2793378e-8 P | 2.2793378e-8 P |
| Spectral constraints, with penalties first run | 2.2793221e-8 P | 2.2793221e-8 P |
| Spectral constraints, with penalties repeat: together these four leaves cover CLP constraints and equal-area penalties, first/repeated fits, distinct saving | 2.2793227e-8 P | 2.2793227e-8 P |
| Spectral guidance: linked kinetic and spectral guide data, NNLS, CLP relations and equal-area penalty | 3.0325969e-7 E | **1.2572461877946428e-6 R; accepted exception** |
| Two datasets: shared three-species decay, different initial concentrations/scales, Gaussian IRF, equal-area penalties | 1.6255211e-10 P | 1.0790768e-10 P |
| DOAS beta target: damped oscillations (19 labels) combined with kinetic target components; restored saved-result coverage | 2.7284787e-9 P | 2.7284787e-9 P |
| Simultaneous 3d dispersion: three datasets, shared kinetics/NNLS, dataset scales/initial populations and dispersed IRFs | 3.8095646e-12 E | 3.8095646e-12 E |
| Simultaneous 3d no dispersion: corresponding nondispersed IRF control | 9.9675896e-9 E | 9.9528410e-9 E |
| Simultaneous 3d weighted: interval-weighted linked fit and scale estimation | 2.4462851e-5 E | 2.4462851e-5 E |
| Simultaneous 6d dispersion: six linked datasets and dispersed response | 1.0072452e-8 E | 1.0072452e-8 E |

Here “3d/6d” denotes dataset count, not three-/six-dimensional raw arrays. Scenario-to-notebook/model mappings are in [scenarios.yml](scenarios.yml) and the source paths recorded in the two runner manifests. Status/metric sources are the [pinned table](comparisons/v07-v08-20260829-162539Z.md) and [current table](comparisons/v07-v08-20260906-022046.md).

## External case studies: broader coverage, provisional scientific conclusions

The paired August 30 four-repository run executed 20/20 notebooks and verified 3,693 artifacts; the corrected 2025 publication rerun executed 3/3 per branch. PFID and TestCaseInitConc each subsequently added one paired notebook. The September 6 consolidation ran **12 staging notebooks**, verified 2,896 artifacts with no errors, and exercised live simulation and plotting. It was not a fresh paired scientific comparison of all 12. See [consolidation verification](runs/case-studies/compat-20260906-022006/compatibility-verification.json) and [summary](runs/case-studies/compat-20260906-022006/summary.json).

All selected semantic case-study reports remain **REVIEW_REQUIRED**, including fits whose primary metric is below `1e-6`. Schema/load/dry-run success, notebook success, artifact integrity, and image production are distinct from scientific agreement. Some saved leaves duplicate instrumented captures of the same fit; do not count them as independent experiments. The appendix preserves every reported leaf and evaluation count.

| Case study / notebook coverage | Unique model features and evidence | Scientific disposition |
|---|---|---|
| Streak PS1 protocol, 2 notebooks (steps 1–2 and 3–4) | Global/target streak-camera sequence, wavelength dispersion, linked kinetics and initial populations; nine migrated schemes form a control unaffected by artifact-normalization migration | 10 reported leaves. Seven meet the primary threshold, including saved endpoints; three captured intermediates remain `8.0266167e-3`, `5.3189222e-3`, `1.9688793e-3`, each 7/7 evaluations. These are unresolved numerical/model differences, not established representation effects. |
| TA PS1 protocol, 3 notebooks (ideal target, global with DOAS, target) | Sequential global/target refinement, 670/700 excitation, coherent artifacts, damped oscillations, spectral guides, penalties and dataset scales | 24 reported leaves. Twenty meet the primary threshold; target2 `7.099525e-5`, spectral13 `2.826268e-6`, target14 and its saved duplicate `1.234089e-6` do not. Matching budgets alone do not explain these differences. |
| 2023 publication, 2 notebooks | Eight-dataset TA target plus linked 25-dataset streak/TA analysis; kinetic activation normalization with artifacts/oscillations and shared scales | TA target `7.2284038e-7` at 15/15; linked analysis `4.31050045e-2` at 2/2. Each has capture/save duplicates. Normalization correction improved the latter from 1.7079, but did not establish equivalence. |
| 2025 publication, 3 notebooks | 77 K MCL; 22-dataset whole-cell target with locally absent CLP relation labels and offset wavelength grids; room-temperature WT/dPSII/PB with simulation | Seven fits. Corrected whole-cell `2.4118191e-8`, RT pair `1.6640550e-8` and `1.6682774e-8`, all 1/1. Four MCL fits remain `3.1739868e-4`, `2.8940994e-2`, `1.8498158e-2`, `2.9401332e-2`; first spectral workload is 20/25, others 11/11, 25/25, 11/11. |
| PFID, 1 notebook | Native perturbed free-induction-decay element, paired global/guide-assisted target workflows, intentionally unlinked CLPs split into experiments, IRF-only nonkinetic datasets, legacy Project/plot consumers | Two reconstructed fits `1.6774187e-13`, `5.2554814e-13`; exact inputs. Zero active varying parameters, 1/1 evaluation: excellent reconstruction parity, no evidence of iterative PFID optimization convergence. |
| TestCaseInitConc, 1 authorized portable notebook | Two NNLS groups, eight measured datasets plus five active guides, state-specific initial concentrations, constraints/relations/penalties/weights, CLP-link tolerance 0.5 | All 13 inputs exact, worst fit `2.5354470e-8`, measured-only worst `8.7411015e-9`; 3/3 evaluations, 49 free parameters, 2,538 CLPs. Budget-limited, not converged. 120 shared parameters agree (max relative `1.4900372e-8`); 30 reference labels absent from staging and raw matrices differ. |

Sources: [streak](comparisons/case-studies/20260830-143435/pygta-protocol-streak-ps1/comparison.json), [TA protocol](comparisons/case-studies/20260830-143435/pygta-protocol-ta-ps1/comparison.json), [2023 publication](comparisons/case-studies/20260830-143435/pub-2023-05-van-stokkum-et-al/comparison.json), [corrected 2025 publication](comparisons/case-studies/20260830-182522/pub-2025-01-van-stokkum-et-al/comparison.json), [repaired PFID captured fits](comparisons/case-studies/20260831-224923/pfid/captured-fit-comparison.json), [InitConc](comparisons/case-studies/20260905-200057/TestCaseInitConc/comparison.json).

**Input-equivalence limitation in chained analyses:** direct inspection of the selected JSON reports finds exact input arrays in all 49 streak and 100 publication-2023 dataset comparisons (including duplicate leaves). TA protocol has 25 nonexact input comparisons out of 83, concentrated in downstream spectral/guide arrays; the final `freeSADS` guide differs by `2.8262653676791707e-6` normalized RMS. Publication-2025 has four nonexact input comparisons out of 64: the two MCL spectral-fit input arrays differ by `0.0320770296001555` and `0.014412140019951171`; the final target's `dataPSI1`/`dataPSII1` guides differ by `0.028940994028281396` and `0.01849815809106423`. These are consistent with propagation through branch-specific fitted spectra, not exact shared-input tests. The first MCL target and the whole-cell/RT inputs are exact. Investigate the earliest divergence and separately test identical guide inputs before attributing downstream discrepancies to a native optimizer defect. A small fitted-data metric in such a leaf does not satisfy the exact-input criterion. These counts describe reported dataset comparisons, not independent raw files.

PFID's repaired August 31 comparison explicitly reuses the August 30 reference against new staging results. It is a documented targeted repair comparison, not a fresh paired rerun. TestCaseInitConc is the authorized portable subset: corrected shared parameter CSV, unsupported `x_scale='jac'` omitted on both sides, private helpers replaced with public plots, unused sixth guide/empty group and trailing older analyses excluded. It does not validate the original notebook unchanged. See [InitConc brief](../issues/testcase-init-conc-reference.md).

External source bases are streak `dcad534e0f6c809c9b7aa03c646ea1796192a0b7`, TA protocol `d7612bc9a7f79812c4ad7c5cfcef0ccaecda0c59`, 2023 publication `6bf9c260deaa014ce9cf5327c5c8e521ce9883a2`, and 2025 publication `9edbe177bf4671b735fba31ebc9b2b3df1885316`. InitConc reference is `720541a42ad520a2169fd81aca93cf5f69a87354`, with staging revision `3512a246a9f27babcd7e2cbc61d26b66b582da7b` recorded for the runnable handoff. Exact run-specific revisions and patches are indexed in the provenance appendix; these studies must not be labeled the common pinned baseline.

## Remaining differences and what they mean

| Category | Finding and disposition |
|---|---|
| Representation / persistence | v0.7 monolithic NetCDF versus v0.8 split results; dimension aliases, label order, CLP naming, legacy species colors, omitted default scale/weighted RMSE. External loaders retain raw evidence and mark derived fields. This supports compatible scientific consumption, not identical persistence/API schemas. [Persistence brief](../issues/weighted-rmse-persistence.md) remains open. |
| Parameter/decomposition ambiguity | Common 3d/6d fits agree while raw matrices/CLPs or parameters differ. The historical two-dataset example exposed an unnecessary `rates.k3d2` path; the maintained refined OC/COC model removes it along with `b.1`, `b.2`, and `rates.k1sum`. Fresh focused paired results contain no `rates.k3d2` and have worst fitted-data normalized RMS `8.8193e-6` under `2e-5`. Remaining raw scale differences are bounded optimizer/representation evidence. [Identifiability brief](../issues/rates-k3d2-identifiability.md) is resolved for the maintained example. |
| Numerical optimization | Weighted 3D reproduces `2.446285059310538e-5`, within its `3e-5` contract; scale.3 differs relatively by `2.5959433e-5`. [Weighted-scale brief](../issues/weighted-scale-drift.md) remains open. Existing synthetic weight/RMSE test verifies reconstruction, not the complete native optimizer or scale estimation in both engines. |
| Confirmed migration defects, repaired | Artifact/oscillation activation entries inflated kinetic normalization and distorted scales even when fitted data passed. The converter excludes only injected nonkinetic amplitudes; it must retain kinetic compartments belonging to other elements. Whole-cell CLP tolerance must be 2.1 rather than default 0.1. After repair, cost `512450.708544407` and 1,886 CLPs match, and Fig. 7 is pixel-identical. [Normalization](../issues/kinetic-activation-normalization.md), [CLP tolerance](../issues/case-study-clp-link-tolerance.md). |
| Confirmed behavioral defects, repaired | Absent local relation labels are skipped as in v0.7; zero active free parameters produce successful single model evaluation instead of SciPy failure. [Relation brief](../issues/clp-relation-missing-label.md), [inactive-parameter brief](../issues/inactive-free-parameter-count.md). Inactive v0.7 scales explain the original MCL 28-versus-26 parameter count; the reference notebook now uses a first-fit parameter table without those scales so fresh comparison runs are 26 versus 26. They do not explain the historical MCL fitted-data differences. |
| Confirmed current result-state defect | Staging result construction retains the last finite-difference parameter vector instead of restoring the accepted optimizer vector. Spectral fit effect is `9.5191e-10` normalized RMS, too small to explain the accepted threshold exception. It is pre-serialization state handling. Its broader impact remains unbounded; a focused fix/test or explicit separate release disposition is needed. [Isolation brief](../issues/spectral-guidance-current-tree.md). |
| Native model-authoring limitation | Artifact/oscillation amplitudes share the activation namespace with kinetic populations. Migrated models exclude them correctly, but native authors can silently change normalization unless exclusions are explicit. Resolve/document the supported API contract; architectural redesign is optional. [Normalization brief](../issues/kinetic-activation-normalization.md). |
| Unresolved scientific scope | Linked 25-dataset, MCL and listed protocol fits exceed `1e-6`. Limited evaluation budgets and different optimizer paths are plausible contributors, not validated root causes. Do not dismiss these as harmless representations, infer convergence from success flags, or extend SG-20260906 to them. |

The normalization defect demonstrates why fitted-data agreement alone is insufficient: scale compensation can hide scientifically meaningful parameter errors. Conversely, strict elementwise residual mismatches near zero and raw decomposition shape differences do not alone prove incorrect predictions. Assess parameters, reconstruction, costs, labels, workload, and termination together.

## Tests and performance evidence

Historical test records are in [validation-log.md](logs/validation-log.md) and [changelog.md](../changelog.md); they are not fresh current-HEAD CI certificates.

| Evidence | Recorded outcome / limit |
|---|---|
| July reference stored-result validator | 577 passed; validates reference fixtures, not 577 cross-version scenarios |
| July staging full core suite after feature ports | 448 passed, 9 xfailed; matrix ordering, PFID, ASCII NumPy scalars, pandas 3, SVD/simulation ports covered |
| July parameter IO matrix | 80 passed each on Python 3.10/pandas 2 and Python 3.11/pandas 3 |
| August 29 core kinetic/optimization fixes | 73 passed; validation-side suite 12 passed |
| Local missing-label relation regression | 2 passed |
| Zero-active-parameter optimizer repair | 55 optimizer tests passed |
| InitConc addition | 26 validation tests passed |
| September 6 shared compatibility extraction | 31 staging tests; four applicable reference adapter tests passed; all 14 common leaves directly converted without changing reconstructed fits; seeded simulation exactly matches native simulation |
| September 6 spectral diagnostic | 1 opt-in integration test passed in 11.23 s; paired metrics asserted; ordinary suite skips it without explicit environment opt-in |

Inspect [compatibility tests](tests/test_compatibility.py), [case-study migration/capture tests](tests/test_case_studies.py), [adapter tests](tests/test_notebook_compat.py), and [benchmark tests](tests/test_benchmark_runtime.py). Coverage includes label alignment, missing fields, weights, saving, nonkinetic normalization, PFID/unlinked CLPs, CLP tolerance, inert selectors, capture excluding dry runs, and empty-result rejection. It does not establish all parameter uncertainty/history semantics or native save/load defaults. Initial staging extras tests had 2 failures and 10 errors (133 passed); the retained record does not establish a later complete clean current extras suite. Adapter success is not a replacement for that release check.

The [August 29 runtime report](benchmarks/v07-v08-runtime-20260829-162539Z/runtime.json) and [CSV](benchmarks/v07-v08-runtime-20260829-162539Z/runtime.csv) contain 12 successful workers, 150 timed samples, 15 summaries, matching function-evaluation counts, no workload warnings, REPORT_ONLY. One warm-up plus five timed repetitions per branch, fresh processes, one thread and alternating branch order measure only the public optimizer call, excluding notebook setup/plots/saving/conversion. This API boundary may include native result construction. Ratios range from 0.696x (repeated penalties) to 2.531x (two datasets). Spectral guidance is 1.656x; weighted 3D 1.695x; transient target 0.727x. This is baseline/environment evidence, not a claim that current staging has identical performance or that all differences are core-algorithm costs.

The separate [PFID profile](../issues/pfid-runtime-memory-profile.md) measures whole-notebook process trees: five-run means 69.94 s / 3327.7 MiB reference versus 180.05 s / 5143.5 MiB staging, 2.57x time and +54.6% peak RSS. Two staging dry runs add substantial work; larger result reconstruction spans three objectives and 17 SVD operations. Instrumented coarse phase timings have observer overhead and are unsuitable for absolute timing; exact peak allocation remains unassigned. Performance is an optional investigation under the report-only policy, not a scientific release gate.

## Evidence limits and preservation

This review inspected existing manifests, JSON/Markdown comparisons, tests, source models, issue briefs and Git state. It did not rerun fits or tests, regenerate comparisons, visually rejudge every figure, or rehash every large output bundle. Existing verification records support artifact integrity at their recorded times. Early case-study manifests report unavailable `pip freeze`/`pip list` because pip was absent; use actual source/patch hashes and later environment capture, not invented dependency completeness.

The repository's README/active plan and issue briefs contain historical acceptance/open-state statements. For this decision, use the dated evidence chain above: original baseline accepted; current machine gate failed; current spectral result explicitly excepted here; external scientific classifications still provisional. No uncertainty intervals, convergence guarantees, all-platform performance claims, or universal v0.7 API replacement are established.

Generated evidence is ignored by Git. Preserve/export the cited reports, manifests, source patches and artifacts in a durable release evidence bundle with verification before deleting environments or retiring v0.7 support. Keeping this report alone would lose much of the reproducibility evidence.

## Appendix: complete retained case-study leaf and provenance ledger

The following tables are transcribed from the selected existing reports, not recomputed fits. They retain duplicate capture/save leaves, original REVIEW_REQUIRED labels, full metrics and workload counts. The main assessment above distinguishes primary agreement from those provisional labels.

### 20260830-143435/pygta-protocol-streak-ps1/comparison.md

Source: [retained report](comparisons/case-studies/20260830-143435/pygta-protocol-streak-ps1/comparison.md).

| Result leaf | Status | Worst fitted-data normalized RMS | Function evaluations (v0.7/v0.8) |
|---|---|---:|---|
| streak/case-study-results/fit-001-target_result1 | **REVIEW_REQUIRED** | 1.46611070807051e-08 | 7/7 |
| streak/case-study-results/fit-002-target_result | **REVIEW_REQUIRED** | 8.569312293115362e-09 | 1/1 |
| streak/case-study-results/fit-002-target_result2 | **REVIEW_REQUIRED** | 2.472294162991144e-08 | 7/7 |
| streak/case-study-results/fit-003-target_result3 | **REVIEW_REQUIRED** | 1.4697702104480536e-08 | 7/7 |
| streak/case-study-results/fit-004-target_result | **REVIEW_REQUIRED** | 0.008026616676934727 | 7/7 |
| streak/case-study-results/fit-005-target_result | **REVIEW_REQUIRED** | 0.0053189222482672915 | 7/7 |
| streak/case-study-results/fit-006-target_result | **REVIEW_REQUIRED** | 0.001968879341905498 | 7/7 |
| streak/case-study-results/fit-007-target_result | **REVIEW_REQUIRED** | 1.0054614520639463e-07 | 7/7 |
| streak/results/20230912targetWL_disp | **REVIEW_REQUIRED** | 1.0054614520639463e-07 | 7/7 |
| streak/results/20230915target_disp | **REVIEW_REQUIRED** | 8.569312293115362e-09 | 1/1 |

### 20260830-143435/pygta-protocol-ta-ps1/comparison.md

Source: [retained report](comparisons/case-studies/20260830-143435/pygta-protocol-ta-ps1/comparison.md).

| Result leaf | Status | Worst fitted-data normalized RMS | Function evaluations (v0.7/v0.8) |
|---|---|---:|---|
| PSI_TA_Scy6803GTA/case-study-results/fit-001-global_result_670 | **REVIEW_REQUIRED** | 6.136202050112199e-09 | 15/15 |
| PSI_TA_Scy6803GTA/case-study-results/fit-001-target_result | **REVIEW_REQUIRED** | 5.475074634536068e-09 | 6/6 |
| PSI_TA_Scy6803GTA/case-study-results/fit-001-target_result1 | **REVIEW_REQUIRED** | 9.129994194140179e-08 | 9/9 |
| PSI_TA_Scy6803GTA/case-study-results/fit-002-global_result670 | **REVIEW_REQUIRED** | 5.136741710207942e-09 | 15/15 |
| PSI_TA_Scy6803GTA/case-study-results/fit-002-target_result2 | **REVIEW_REQUIRED** | 7.099524957050426e-05 | 9/9 |
| PSI_TA_Scy6803GTA/case-study-results/fit-003-global_result700 | **REVIEW_REQUIRED** | 7.578116376625394e-09 | 15/15 |
| PSI_TA_Scy6803GTA/case-study-results/fit-003-target_result3 | **REVIEW_REQUIRED** | 1.8606491484469807e-08 | 9/9 |
| PSI_TA_Scy6803GTA/case-study-results/fit-004-global_result_670_700 | **REVIEW_REQUIRED** | 1.2031393176746543e-08 | 5/5 |
| PSI_TA_Scy6803GTA/case-study-results/fit-004-target_result3 | **REVIEW_REQUIRED** | 1.853248906346232e-08 | 9/9 |
| PSI_TA_Scy6803GTA/case-study-results/fit-005-target_result3 | **REVIEW_REQUIRED** | 4.484927119083923e-09 | 9/9 |
| PSI_TA_Scy6803GTA/case-study-results/fit-006-target_result4 | **REVIEW_REQUIRED** | 1.1152680234560469e-07 | 9/9 |
| PSI_TA_Scy6803GTA/case-study-results/fit-007-spectral_result | **REVIEW_REQUIRED** | 1.680558302679072e-08 | 18/18 |
| PSI_TA_Scy6803GTA/case-study-results/fit-008-spectral_result | **REVIEW_REQUIRED** | 6.562587442932342e-09 | 16/16 |
| PSI_TA_Scy6803GTA/case-study-results/fit-009-target_result5 | **REVIEW_REQUIRED** | 1.1889345643608973e-07 | 7/7 |
| PSI_TA_Scy6803GTA/case-study-results/fit-010-spectral_result | **REVIEW_REQUIRED** | 1.6435469228787983e-07 | 25/25 |
| PSI_TA_Scy6803GTA/case-study-results/fit-011-spectral_result | **REVIEW_REQUIRED** | 8.489720092453577e-08 | 23/23 |
| PSI_TA_Scy6803GTA/case-study-results/fit-012-spectral_result | **REVIEW_REQUIRED** | 3.190463103495648e-08 | 9/9 |
| PSI_TA_Scy6803GTA/case-study-results/fit-013-spectral_result | **REVIEW_REQUIRED** | 2.826267835719005e-06 | 25/25 |
| PSI_TA_Scy6803GTA/case-study-results/fit-014-target_result | **REVIEW_REQUIRED** | 1.2340890859196843e-06 | 7/7 |
| PSI_TA_Scy6803GTA/results/global670 | **REVIEW_REQUIRED** | 5.136741710207942e-09 | 15/15 |
| PSI_TA_Scy6803GTA/results/global670and700 | **REVIEW_REQUIRED** | 1.2031393176746543e-08 | 5/5 |
| PSI_TA_Scy6803GTA/results/global700 | **REVIEW_REQUIRED** | 7.578116376625394e-09 | 15/15 |
| PSI_TA_Scy6803GTA/results/ideal | **REVIEW_REQUIRED** | 5.475074634536068e-09 | 6/6 |
| PSI_TA_Scy6803GTA/results/target670and700 | **REVIEW_REQUIRED** | 1.2340890859196843e-06 | 7/7 |

### 20260830-143435/pub-2023-05-van-stokkum-et-al/comparison.md

Source: [retained report](comparisons/case-studies/20260830-143435/pub-2023-05-van-stokkum-et-al/comparison.md).

| Result leaf | Status | Worst fitted-data normalized RMS | Function evaluations (v0.7/v0.8) |
|---|---|---:|---|
| 20230522PSI_TA_Scy6803target/case-study-results/fit-001-target_result | **REVIEW_REQUIRED** | 7.228403770652428e-07 | 15/15 |
| 20230522PSI_TA_Scy6803target/results/20230520 | **REVIEW_REQUIRED** | 7.228403770652428e-07 | 15/15 |
| 20230522target_linking25streak_and_TA_datasets/case-study-results/fit-001-target_result | **REVIEW_REQUIRED** | 0.04310500449292203 | 2/2 |
| 20230522target_linking25streak_and_TA_datasets/results/20230523 | **REVIEW_REQUIRED** | 0.04310500449292203 | 2/2 |

### 20260830-182522/pub-2025-01-van-stokkum-et-al/comparison.md

Source: [retained report](comparisons/case-studies/20260830-182522/pub-2025-01-van-stokkum-et-al/comparison.md).

| Result leaf | Status | Worst fitted-data normalized RMS | Function evaluations (v0.7/v0.8) |
|---|---|---:|---|
| 77K_target_MCL/case-study-results/fit-001-target_result1 | **REVIEW_REQUIRED** | 0.00031739867806329056 | 11/11 |
| 77K_target_MCL/case-study-results/fit-002-spectral_result | **REVIEW_REQUIRED** | 0.02894099402887574 | 20/25 |
| 77K_target_MCL/case-study-results/fit-003-spectral_result | **REVIEW_REQUIRED** | 0.01849815809487486 | 25/25 |
| 77K_target_MCL/case-study-results/fit-004-target_result1 | **REVIEW_REQUIRED** | 0.029401332293921754 | 11/11 |
| 77K_target_cells/case-study-results/fit-001-target_result1 | **REVIEW_REQUIRED** | 2.411819127175127e-08 | 1/1 |
| RT_target_WT_dPSII_cells_PB/case-study-results/fit-001-dPSII_PBS580_target_result | **REVIEW_REQUIRED** | 1.6640550348483673e-08 | 1/1 |
| RT_target_WT_dPSII_cells_PB/case-study-results/fit-002-dPSII_PBS580_target_result_noso | **REVIEW_REQUIRED** | 1.6682773680106e-08 | 1/1 |

### 20260831-224923/pfid/captured-fit-comparison.md

Source: [retained report](comparisons/case-studies/20260831-224923/pfid/captured-fit-comparison.md).

| Result leaf | Status | Worst fitted-data normalized RMS | Function evaluations (v0.7/v0.8) |
|---|---|---:|---|
| fit-001-result1 | **REVIEW_REQUIRED** | 1.67741866882088e-13 | 1/1 |
| fit-002-result | **REVIEW_REQUIRED** | 5.255481356856353e-13 | 1/1 |

### 20260905-200057/TestCaseInitConc/comparison.md

Source: [retained report](comparisons/case-studies/20260905-200057/TestCaseInitConc/comparison.md).

| Result leaf | Status | Worst fitted-data normalized RMS | Function evaluations (v0.7/v0.8) |
|---|---|---:|---|
| fit-001-result | **REVIEW_REQUIRED** | 2.53544703805126e-08 | 3/3 |

### Run-specific source revisions

Manifest links preserve source patches and hashes alongside revisions. A dirty source tree is not described by its commit alone.

| Run / case / branch | Source revision | Base revision | Source status |
|---|---|---|---|
| [20260830-143435/pub-2023-05-van-stokkum-et-al/reference](runs/case-studies/20260830-143435/pub-2023-05-van-stokkum-et-al/reference/manifest.json) | 6bf9c260deaa014ce9cf5327c5c8e521ce9883a2 | 6bf9c260deaa014ce9cf5327c5c8e521ce9883a2 | 1 changed/untracked entries; see manifest |
| [20260830-143435/pub-2023-05-van-stokkum-et-al/staging](runs/case-studies/20260830-143435/pub-2023-05-van-stokkum-et-al/staging/manifest.json) | e253a7ea226a069823d94568dface2b7b66cfaf4 | 6bf9c260deaa014ce9cf5327c5c8e521ce9883a2 | 5 changed/untracked entries; see manifest |
| [20260830-143435/pub-2025-01-van-stokkum-et-al/reference](runs/case-studies/20260830-143435/pub-2025-01-van-stokkum-et-al/reference/manifest.json) | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | clean |
| [20260830-143435/pub-2025-01-van-stokkum-et-al/staging](runs/case-studies/20260830-143435/pub-2025-01-van-stokkum-et-al/staging/manifest.json) | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | 10 changed/untracked entries; see manifest |
| [20260830-143435/pygta-protocol-streak-ps1/reference](runs/case-studies/20260830-143435/pygta-protocol-streak-ps1/reference/manifest.json) | dcad534e0f6c809c9b7aa03c646ea1796192a0b7 | dcad534e0f6c809c9b7aa03c646ea1796192a0b7 | clean |
| [20260830-143435/pygta-protocol-streak-ps1/staging](runs/case-studies/20260830-143435/pygta-protocol-streak-ps1/staging/manifest.json) | f186361713a74fc7c6605b0f4a442d1e1c7947eb | dcad534e0f6c809c9b7aa03c646ea1796192a0b7 | 11 changed/untracked entries; see manifest |
| [20260830-143435/pygta-protocol-ta-ps1/reference](runs/case-studies/20260830-143435/pygta-protocol-ta-ps1/reference/manifest.json) | d7612bc9a7f79812c4ad7c5cfcef0ccaecda0c59 | d7612bc9a7f79812c4ad7c5cfcef0ccaecda0c59 | clean |
| [20260830-143435/pygta-protocol-ta-ps1/staging](runs/case-studies/20260830-143435/pygta-protocol-ta-ps1/staging/manifest.json) | f837892b1bbf3c31e068ae79fa44ea6653fe676b | d7612bc9a7f79812c4ad7c5cfcef0ccaecda0c59 | 14 changed/untracked entries; see manifest |
| [20260830-182522/pub-2025-01-van-stokkum-et-al/reference](runs/case-studies/20260830-182522/pub-2025-01-van-stokkum-et-al/reference/manifest.json) | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | clean |
| [20260830-182522/pub-2025-01-van-stokkum-et-al/staging](runs/case-studies/20260830-182522/pub-2025-01-van-stokkum-et-al/staging/manifest.json) | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | 10 changed/untracked entries; see manifest |
| [20260830-182522/pub-2025-01-van-stokkum-et-al/staging-target-check](runs/case-studies/20260830-182522/pub-2025-01-van-stokkum-et-al/staging-target-check/manifest.json) | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | 9edbe177bf4671b735fba31ebc9b2b3df1885316 | 10 changed/untracked entries; see manifest |
| [20260830-235141/pfid/reference](runs/case-studies/20260830-235141/pfid/reference/manifest.json) | 39976053cb29eebfdb25a2625b4b62249ab57314 | 39976053cb29eebfdb25a2625b4b62249ab57314 | clean |
| [20260830-235141/pfid/staging](runs/case-studies/20260830-235141/pfid/staging/manifest.json) | 52082fb4e705117a0438c45bb3ff3dcb844c16d9 | 52082fb4e705117a0438c45bb3ff3dcb844c16d9 | 3 changed/untracked entries; see manifest |
| [20260831-224923/pfid/staging](runs/case-studies/20260831-224923/pfid/staging/manifest.json) | 52082fb4e705117a0438c45bb3ff3dcb844c16d9 | 52082fb4e705117a0438c45bb3ff3dcb844c16d9 | 4 changed/untracked entries; see manifest |
| [20260905-200057/TestCaseInitConc/reference](runs/case-studies/20260905-200057/TestCaseInitConc/reference/manifest.json) | 720541a42ad520a2169fd81aca93cf5f69a87354 | 720541a42ad520a2169fd81aca93cf5f69a87354 | 25 changed/untracked entries; see manifest |
| [20260905-200057/TestCaseInitConc/staging](runs/case-studies/20260905-200057/TestCaseInitConc/staging/manifest.json) | 3512a246a9f27babcd7e2cbc61d26b66b582da7b | 3512a246a9f27babcd7e2cbc61d26b66b582da7b | 5 changed/untracked entries; see manifest |

## Prioritized promotion and retirement actions

Plain-language companion documents explain each item's evidence, relevant code, recommended solution and whether it needs to block release:

- [1. Remaining case-study differences](release-actions/01-case-study-differences.md)
- [2. Result integrity and model/result contracts](release-actions/02-result-integrity-and-model-contract.md)
- [3. Release candidate and promotion handoff](release-actions/03-release-candidate-and-handoff.md)
- [4. Optional follow-ups](release-actions/04-optional-follow-ups.md)

1. **Blocker for unconditional v0.7 retirement:** disposition the linked 25-dataset fit, four MCL fits and listed protocol intermediates. Start with same-parameter objective/input/CLP-link/normalization checks, then optimizer trajectories and evaluation budgets; use new paired runs only where needed. Fix demonstrated defects, or obtain explicit scientific acceptance/scope exclusions for each unresolved difference. SG-20260906 is already accepted and needs no tolerance adjustment or model rollback.
2. **Blocker for release integrity:** restore accepted optimizer parameters before result construction and add a focused regression, or obtain a separate documented release-owner disposition with bounded impact. The tiny spectral effect does not bound all models. Document correct native artifact/oscillation normalization and the supported metadata/compatibility contract.
3. **Blocker for promotion handoff:** identify the immutable release candidate across core/examples/extras and shipped adapters; reconcile historical extras failures against that candidate. After any release fixes, run the focused checks and [full common handoff](AGENT_RERUN.md), retaining SG-20260906 as an explicit exception, plus affected paired case studies. Archive a hash-verified evidence bundle and migration instructions; only then perform the separately authorized staging-to-main promotion/tag and retire v0.7 while preserving its reproducible reference. No branch/commit action is taken by this report.
4. **Optional follow-ups:** investigate the weighted scale mechanism; broaden uncertainty/history and persistence round-trip coverage; optimize PFID memory/runtime and benchmark the final candidate if runtime changes; consider separating nonkinetic amplitudes from kinetic activation in the API. These do not require forcing parameters or serialized layouts into equality.
