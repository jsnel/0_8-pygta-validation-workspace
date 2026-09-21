# Fresh validation and staging-to-main PR readiness — 2026-09-13

**Ready to start a draft PR. This run does not provide an unconditional merge sign-off.** All 23 selected notebooks passed on each branch. The 14 common example leaves meet the existing semantic contract. Four case-study fits still exceed the documented 0.1% engineering band, and the CI publication and result-integrity work below remains to be addressed or explicitly dispositioned.

## Fresh evidence

The complete paired run is under [`pr-readiness-20260913-093010Z`](../validation/runs/pr-readiness-20260913-093010Z/). It covers 11 common examples and 12 case-study notebooks per branch, with 15 example fit invocations and 40 captured case-study fits. Each runner used a new isolated output directory. Case-study comparisons use only real-fit captures declared by these manifests; copied historical result saves are excluded.

| Scope | Reference execution | Staging execution | Scientific comparison |
|---|---:|---:|---|
| Common examples | 11/11 | 11/11 | 8 PASS, 6 EXPECTED_DIFFERENCE; no regression, baseline failure, or missing leaf |
| Case studies | 12/12 | 12/12 | 40/40 captures each; 32/40 fitted-data comparisons within 1e-6 |

The [example comparison](../validation/runs/pr-readiness-20260913-093010Z/examples-comparison.md) retains the existing tolerances. Worst fitted-data normalized RMS is `2.4462851e-5` (0.0024463%) for weighted 3D; transient two-dataset analysis is `8.8193246e-6`; spectral guidance is `1.2572462e-6` against its declared `2e-6` tolerance. Documented representation, decomposition and identifiability differences remain secondary evidence.

All 28 staging example datasets persist both scale and weighted RMSE. No compatibility derivation is needed to supply missing values in these fresh saves.

## Case-study findings

| Case study | Fits within 1e-6 | Fits with exact inputs | Worst fitted-data normalized RMS |
|---|---:|---:|---:|
| Initial concentration | 1/1 | 1/1 | 2.53545e-8 |
| Streak protocol | 6/9 | 9/9 | 8.02698e-3 |
| TA protocol | 17/19 | 9/19 | 7.09790e-5 |
| 2023 publication | 1/2 | 2/2 | 4.31050e-2 |
| 2025 publication | 5/7 | 4/7 | 8.27077e-4 |
| PFID | 2/2 | 2/2 | 5.25548e-13 |
| **Total** | **32/40** | **27/40** | |

Twenty-two fits meet both exact-input and strict fitted-data criteria. Thirty-six of 40 fits are inside the separately documented 0.1% engineering band; this is a magnitude assessment, not a change to the comparator's `1e-6` threshold. All 40 retain provisional `REVIEW_REQUIRED` because secondary evidence also differs. No result is classified as missing. Function-evaluation counts match for all 40 pairs, which does not establish convergence or identical effective workloads.

The four fits above 0.1% reproduce the previously documented cases:

- Streak steps 1–2 fits 4, 5 and 6: **0.802698%, 0.352579%, 0.196888%**, with exact inputs and 7/7 evaluations. Both final notebook fits pass (`9.86359e-8` and `8.56931e-9`).
- The 2023 linked fit: **0.382369% maximum on measured data**, **4.310500% on guidance**, with exact inputs and 2/2 evaluations. Both branches report maximum evaluations exceeded. Its guide maximum must not be presented as the measured-data maximum.

Short budgets describe these endpoints; they do not prove the cause of the differences. Agreement after adequate convergence, a controlled common-parameter comparison, or an explicit scope/risk disposition remains outstanding.

Other strict-threshold exceedances are smaller but remain visible:

- TA target fit 2 is `7.09790e-5` with exact inputs. The final target maximum is `1.23395e-6` on `Ant1SADS` guidance; all four measured inputs are exact and their fitted outputs pass, with maximum `3.13554e-7`. Generated guide inputs differ, so downstream comparisons are not independent identical-input engine tests.
- The corrected MCL first target converges on `ftol` at 21/21 evaluations and agrees to `2.57190e-8` on measured data. Its PSII spectral fit now differs by `8.27077e-4` (0.0827077%), larger than the September 12 refresh, despite input drift of only `1.55625e-7`; both stop at 25 evaluations. The final guided target receives that differing guide and has maximum measured RMS `6.62769e-6` and guide RMS `5.23416e-4`. Both stop at 11 evaluations. Thus the historical statement that current MCL measured outputs all pass `1e-6` does not hold for this run. All remain within 0.1%; no new root cause is assigned.
- PFID agrees to `5.25548e-13`, but remains a one-evaluation comparison with the documented inactive/free-parameter accounting difference, not a demonstration of multi-step nonlinear convergence.

Complete fit diagnostics, termination reasons and per-dataset input/output metrics are in [case-summary.json](../validation/runs/pr-readiness-20260913-093010Z/case-summary.json) and the six [per-study comparisons](../validation/runs/pr-readiness-20260913-093010Z/comparisons/).

## Provenance and verification

| Component | Reference | Staging |
|---|---|---|
| Core HEAD | `8f26be01d5a6ce63ec2556469ac3facc2d2cee68` | `879c5bce399b7195b7ed2b0aece9234d803a74d9` |
| Examples HEAD | `23287837579b9ad150ca33cce2b34bba33ec1e0d` | `44e3747cf39f0482ed5c05578624577938159085` |
| NumPy / SciPy | 2.2.6 / 1.15.3 | 2.0.1 / 1.14.1 |
| Numba / llvmlite | 0.63.1 / 0.46.0 | 0.60.0 / 0.43.0 |

Core/example HEADs match the current scenario pins, but these are working-tree results: staging includes the pre-existing uncommitted persistence fix, tests and CI edits. Both branches retain pre-existing validator/workflow edits. Full orchestration/extras/case-study revisions, Git status and binary tracked diffs are preserved in `source-before.json`/`source-after.json` and their patches; case runners also preserve source patches and initial content hashes.

Staging now uses its locked scientific versions, unlike the September 6 equal-stack run. No dependencies were changed for this rerun. Branch differences therefore include dependency-stack effects; they cannot all be attributed to pyglotaran implementation alone. Reference case studies use the established plotting overlay recorded in the command sidecars. Numerical thread controls are one. Branch workers ran concurrently; no runtime-performance claim is made and no separate benchmark was rerun.

- Validation tests: **56 passed, 1 skipped** (`staging-tests.log`).
- Focused staging YAML/persistence tests: **7 passed** (`staging-persistence-tests-isolated-temp.log`). Workspace-local test temp paths initially caused two relative-versus-absolute path assertions; default pytest temp reuse was inaccessible. A fresh isolated system-temp directory resolves the invocation issue without source changes; failed attempt logs are retained.
- Migrated schema/strict-load checks: **34/34 pass** across six studies.
- Artifact audit: **3,761 files checked, zero missing/hash mismatches**. Native saved arrays are loaded by the semantic comparisons. Both complete example result-tree hashes also match their manifests.
- Source audit: no revision/status/tracked-diff changes during execution; all four installed core/extras source hashes still match the example manifests; validation-tooling hashes unchanged through final audit.

Audit details: [artifact-audit.json](../validation/runs/pr-readiness-20260913-093010Z/artifact-audit.json), [provenance-audit.json](../validation/runs/pr-readiness-20260913-093010Z/provenance-audit.json). Commands, environment snapshots, notebook logs, executed notebooks and source/result hashes are retained in the same run directory.

## What belongs in the draft PR checklist

1. Publish the semantic validator and refreshed reference baseline, update their pinned revisions/gitlinks, and exercise upstream CI. The local patch alone does not complete [CI restoration](compare-results-ci.md).
2. Resolve or explicitly disposition the four budget-truncated fits above 0.1%. Retain the smaller TA/MCL and generated-guide limitations in the validation section; do not claim unconditional case-study equivalence.
3. Address the known [accepted-optimizer-vector restoration issue](../validation/release-actions/02-result-integrity-and-model-contract.md). Static inspection of current `Optimization.run` still shows result construction after `least_squares` without restoring `ls_result.x`; passing notebooks do not close this issue.
4. Retain the Gaussian shift/dispersion result-center issue and native mixed kinetic/artifact normalization guidance as documented result/model-contract follow-ups. Current Gaussian dispersion reconstruction still omits shift application; no new impact bound or fix is established here.
5. Include the tested persistence fix in the reviewed commits, and record the actual scientific dependencies used by release CI. Keep PFID memory attribution as the existing report-only follow-up.

This task changed validation documentation and generated evidence only. It made no core, notebook, parameter-budget, tolerance, environment, branch, staging-index or commit changes.
