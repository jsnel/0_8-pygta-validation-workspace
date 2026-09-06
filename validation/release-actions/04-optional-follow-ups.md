# 4. Improvements that can follow the release

Companion to action 4 in the [release report](../release-decision-report.md). Written 6 September 2026 from existing evidence. These are separate improvements, not a requirement to make every v0.8 number identical to v0.7.

## A. Explain the unstable `rates.k3d2` parameter

**What it means:** two fits can draw almost the same curve while reporting very different values for one rate. If the data cannot distinguish a very fast reaction from an even faster one, the optimizer can move that rate enormously with little effect on the curve. This is called weak identification: the data provide little information about that value.

The historical transient two-dataset fit reports approximately `1.25e7` in v0.7 versus `1.94e25` in v0.8, while its curve difference `1.382765e-5` is inside the declared `2e-5` threshold. The issue brief treats weak identification as a likely explanation, not a proof excluding bugs. Some related parameter labels are also missing in staging output. The current-tree curve difference is much smaller, but that does not explain the historical rate instability.

**Recommendation:** hold other parameters fixed and vary this rate across a wide range, plotting how much the error changes. Also inspect bounds, log/positivity transforms and related parameter expressions. If the error barely changes, report the rate as poorly constrained rather than forcing the old value. If the transforms or final state are wrong, fix the demonstrated defect.

Look at the [issue brief](../../issues/rates-k3d2-identifiability.md), [reference model](../../temp/pyglotaran-main-dev/pyglotaran-examples/pyglotaran_examples/study_transient_absorption/models/model_2d_co_co2.yml), [staging scheme](../../temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/study_transient_absorption/models/scheme_2d_co_co2.yml), [staging parameter implementation](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/parameter/parameter.py), and [parameter collection/setter](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/parameter/parameters.py).

**Why optional:** the fit has an accepted scenario-specific contract. Escalate if a reproducible transform/bound defect appears or a release claim relies on the numerical rate being scientifically meaningful.

## B. Explain the small weighted-fit scale difference

**What it means:** some parts of a dataset count less heavily when choosing the best fit. Both versions produce close results, but the third dataset's scale is slightly different: `72.7362322` versus `72.7381204`, about 0.0026% relative difference. The curve difference `2.446285e-5` is inside the documented `3e-5` threshold.

We have a small test showing that the comparison code constructs weights and calculates weighted RMSE correctly. That is useful, but does not independently prove the entire native fitting process applies the same weights and estimates the same scale.

**Recommendation:** use a tiny synthetic dataset with known weights and scale. Compare both native objective calculations at fixed parameters before allowing optimization. Then vary one condition at a time: constant versus interval weights, fixed versus free scale, and stopping budget. This can separate a weighting error from harmless endpoint sensitivity.

Look at the [weighted-scale brief](../../issues/weighted-scale-drift.md), [weight reconstruction](../compatibility/weights.py), [current small test](../tests/test_compatibility.py), [native staging optimization data](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/data.py), and [native staging objective](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/objective.py).

**Why optional:** the existing result is accepted within its explicit tolerance. Escalate only if the independent calculation demonstrates an incorrect objective or weight application. Do not relax the threshold again just to avoid investigating it.

## C. Broaden uncertainty, history and save/load tests

**What it means:** the curve can be correct even if a reported error bar, optimization history or saved diagnostic is incomplete. The current study is strongest on calculated curves and model migration. It does not prove every reporting feature behaves identically.

This is a coverage gap, not a claim that every one of these features is broken. For example, a rate optimized in log space needs appropriate treatment when reporting uncertainty in the ordinary rate units. A saved result should also make its supported diagnostics available after reloading, without rerunning the fit.

**Recommendation:** add a few focused cases with known behavior: transformed and untransformed parameters, an identifiable simple fit, a budget-limited fit, and weighted/default-scale save/load round trips. Check the promised public meaning of each field rather than copying the old serialization layout. Keep these tests separate from the confirmed accepted-vector defect described in [action 2](02-result-integrity-and-model-contract.md).

Look at [optimization information and parameter errors](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/info.py), functions `calculate_parameter_errors` and `calculate_covariance_matrix_and_standard_errors`; [optimization history](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/optimization_history.py); [parameter history tests](../../temp/pyglotaran-staging-dev/pyglotaran/tests/parameter/test_parameter_history.py); [result save/load](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/project/result.py); and the [persistence brief](../../issues/weighted-rmse-persistence.md).

**Why optional:** broader coverage can follow release unless a promised feature is known to return incorrect information or is essential to users retiring v0.7. A demonstrated defect should be assessed on its impact, not left optional merely because it was found in this list.

## D. Reduce PFID runtime and memory use

**What it means:** the migrated PFID notebook took about 180 seconds and 5,144 MiB peak memory, versus 70 seconds and 3,328 MiB for reference in the five-run profile. This does not mean that each optimizer step is 2.57 times slower. Staging also performs two substantial dry runs and constructs more result arrays.

The instrumented evidence shows three objectives and 17 dataset SVD calculations in the larger staging fit. It does not identify the exact allocation responsible for the memory peak. Detailed instrumentation also slows execution, so its timings should not be treated as ordinary runtime measurements.

**Recommendation:** first measure the user workflow with and without repeated dry-run/result construction, where that is appropriate for the workflow. Next profile allocations around result construction. Optimize only the measured bottleneck, preserving the required output arrays and diagnostics. Compare the public optimizer call separately from whole-notebook time.

Look at the [PFID profile brief](../../issues/pfid-runtime-memory-profile.md), [memory profiler](../profile_notebook_memory.py), [public-fit benchmark](../benchmark_runtime.py), [benchmark procedure](../benchmarks/README.md), and [native result construction](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/objective.py), especially `create_multi_dataset_result`, `create_dataset_result`, and `add_svd_to_result_dataset`.

**Why optional:** performance is explicitly report-only in this study. It becomes a practical blocker if the intended users cannot run their analyses within available time or memory; that requires a user requirement, not just a slowdown percentage.

## E. Simplify how native models separate artifacts from populations

**What it means:** artifact amplitudes and starting kinetic populations currently share one list. That makes normalization easy to misunderstand. Corrected migrations already exclude the artifact entries, but a future API could make this automatic or put the two kinds of values in different places.

**Recommendation:** document the current correct usage first. Consider an API redesign later, preserving legitimate population contributions from other kinetic elements. See [action 2](02-result-integrity-and-model-contract.md), the [normalization brief](../../issues/kinetic-activation-normalization.md), [kinetic element](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/builtin/elements/kinetic/element.py), and [migration activation logic](../case_studies/migrate.py).

**Why optional:** a redesign is not required to run the already corrected models. Clear supported authoring instructions may be enough for this release.

## Suggested order after release

Start with the small independent weighted-fit check and the most-used diagnostic save/load tests. Then investigate `k3d2` if users interpret that rate scientifically. Prioritize PFID performance according to actual user hardware and workloads. Leave the broader activation API redesign until maintainers agree on the desired model-authoring behavior.
