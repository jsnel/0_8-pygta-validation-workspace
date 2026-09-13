# 1. Decide whether the remaining case-study differences matter

Companion to action 1 in the [release report](../release-decision-report.md). Written 6 September 2026 from existing evidence; no new fits were run.

## Update, 13 September 2026: the list is shorter and the common factor is clear

Two things have changed since this was written.

First, the MCL notebooks were re-run on 12 September with corrected inputs, and
their differences dropped to at most 0.00093% of the reference curve. They are
no longer in the problem set.

Second, applying a relative yardstick rather than the fixed `1e-6` threshold —
treating anything under 0.1% of the reference curve as acceptable — leaves
**four fits**, in two studies: the 2023 linked fit and streak fits 4, 5 and 6.

The common factor is that **every one of them was stopped early by its own
evaluation budget**, on both versions, before the optimizer had settled. The
software reports this explicitly as "The maximum number of function evaluations
is exceeded". How far each was from a finished answer is visible in its
optimality figure — roughly 90,000,000 for the 2023 linked fit, and 1494, 350
and 212 for the three streak fits. A finished fit has a figure near zero.

This matters because comparing two deliberately half-finished calculations
compares where each one happened to be paused, not what answer each would reach.
The 2023 linked fit is the clearest case: it was allowed just **two**
evaluations, and it produces the largest difference in the entire study.

The contrast with finished fits is stark. Where both versions are allowed to
run to completion, they agree to about fifteen decimal places on fit quality.
Within the streak study itself, the steps 3–4 fits do finish, and they agree to
`1.7e-8` and `8.6e-9` — while the unfinished steps 1–2 fits alongside them
differ by 0.2–0.8%. The same held for the MCL first fit: given a 200-evaluation
budget, both versions finished after 21 evaluations and agreed to `1.14e-8`.

**This narrows the recommendation below rather than replacing it.** The specific
next step is now to re-run these four fits with a budget large enough for both
versions to finish, and confirm they converge to the same answer, exactly as was
done for the MCL first fit. Until that is done these rows should be described as
budget-truncated intermediates, not as differences between the two engines. No
tolerance was changed and no acceptance is claimed on this basis alone.

## The issue in simple terms

Several notebooks finish successfully on both versions, but their calculated curves are not quite the same. A notebook finishing means that the software ran. It does not mean that both versions reached the same scientific answer.

We do not yet know whether these remaining differences come from an incorrectly translated model, a real engine defect, or two optimizers taking slightly different steps before the notebook stops them. Some later fits also receive different guide spectra from earlier fits. Comparing those later fits is like comparing two recipes after giving them slightly different ingredients.

**My recommendation is to investigate the first point where each analysis diverges, rather than require every saved array to match.** This is a gap in the evidence for retiring v0.7 across all these studies, not proof that v0.8 is scientifically wrong.

## Which results are involved?

The numbers below measure the size of the difference between fitted curves relative to the size of the reference fitted curve. They are not percentages of experimental error and do not measure parameter uncertainty. The case-study comparison uses `1e-6` as its fit threshold.

| Analysis | What the evidence says | Why it needs interpretation |
|---|---|---|
| 2023 publication, linked 25-dataset analysis | Difference `0.043105` (about 4.31% of reference curve RMS); both stop after two function evaluations; inputs match | Only two evaluations is a very short fit. We need to determine whether the same model produces the same curve at the same parameters, before blaming convergence. |
| 2025 publication, four MCL fits | Differences approximately `0.0003174`, `0.028941`, `0.018498`, `0.0294013` | The first target fit has exact inputs. Later spectral fits receive inputs differing by about 3.21% and 1.44%; final target guides also differ. One spectral fit uses 20 versus 25 evaluations. These are not four independent same-input engine comparisons. |
| Streak protocol, three intermediate fits | Differences `0.0080266`, `0.0053189`, `0.0019689`, each at seven evaluations on both sides | Inputs match, and the reported saved endpoints meet the fit threshold. Whether these intermediate models are themselves supported scientific outputs matters to the release decision. |
| TA protocol | Target2 `7.099525e-5`, spectral13 `2.826268e-6`, final target `1.234089e-6` | Some later inputs are spectra produced upstream. The final `freeSADS` guide itself differs by `2.826265e-6`. An upstream difference can explain part of a downstream difference without showing a new engine defect. |

Sources: [25-dataset publication report](../comparisons/case-studies/20260830-143435/pub-2023-05-van-stokkum-et-al/comparison.json), [MCL report](../comparisons/case-studies/20260830-182522/pub-2025-01-van-stokkum-et-al/comparison.json), [streak report](../comparisons/case-studies/20260830-143435/pygta-protocol-streak-ps1/comparison.json), [TA report](../comparisons/case-studies/20260830-143435/pygta-protocol-ta-ps1/comparison.json). These are historical paired case-study results, not fresh comparisons at current HEAD. September 6 execution of the consolidated notebooks did not replace these scientific comparisons.

## Where to look in the code and notebooks

Start with the analysis and its model, then inspect the engine only if the inputs really are equivalent:

- [25-dataset staging notebook](../../temp/case-studies/pub-2023-05-van-stokkum-et-al/staging/20230522target_linking25streak_and_TA_datasets/20230522PSI_TA_streak_v08.ipynb): inspect the fit budget, starting parameters, dataset scales and model loaded by the fit. Compare with the [reference notebook](../../temp/case-studies/pub-2023-05-van-stokkum-et-al/reference/20230522target_linking25streak_and_TA_datasets/20230522PSI_TA_streak.ipynb).
- [MCL staging notebook](../../temp/case-studies/pub-2025-01-van-stokkum-et-al/staging/77K_target_MCL/20250201streak_target_supercomplex_v08.ipynb): follow the first target result into the two spectral fits and then the final guided target. That order matters.
- [Streak steps 1–2](../../temp/case-studies/pygta-protocol-streak-ps1/staging/streak/Step_1_and_2_PSI_CF9212_streak_global_target_dispWL_v08.ipynb) and [steps 3–4](../../temp/case-studies/pygta-protocol-streak-ps1/staging/streak/Step_3_and_4_PSI_CF9212_streak_global_target_disp_v08.ipynb): identify which intermediate models are intended scientific outputs.
- [TA target notebook](../../temp/case-studies/pygta-protocol-ta-ps1/staging/PSI_TA_Scy6803GTA/step_3_target_PSI_TA_SCy6803_v08.ipynb): follow guide arrays as they are fitted and reused.
- [Migration converter](../case_studies/migrate.py), functions `activation`, `convert_model`, `notebook_clp_link_tolerances`: initial-population normalization and wavelength-linking tolerance can change the actual model. Both have caused genuine differences already; see [normalization investigation](../../issues/kinetic-activation-normalization.md) and [linking-tolerance investigation](../../issues/case-study-clp-link-tolerance.md).
- [Staging objective](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/objective.py), `calculate`, and [optimization controller](../../temp/pyglotaran-staging-dev/pyglotaran/glotaran/optimization/optimization.py), `run`: the curve/residual calculation and stopping conditions.
- [Case-study comparator](../case_studies/compare.py): inspect each dataset's `data` comparison as well as `fitted_data`. A good fitted-data metric does not override different inputs.

These notebook links point to current source copies for navigation. Use the report-linked runner manifests and patches when reproducing the historical inputs.

## How I would resolve it

1. Select the earliest differing fit in each chain. Verify the same starting parameters, fixed/free settings, weights, normalization and linking tolerance.
2. Evaluate both engines at those same parameters without letting either optimizer move. If the curves or objective differ meaningfully, investigate translation or engine calculation first.
3. If that calculation agrees, compare the optimization paths. For short-budget fits, test whether more evaluations reduce the difference, using a separately recorded diagnostic rather than overwriting the original evidence.
4. For downstream guide fits, perform an additional controlled comparison with identical guides. Keep the original end-to-end comparison too: it represents the actual user workflow.
5. Record either a demonstrated fix, a scientifically acceptable numerical difference, or an explicit exclusion from the supported release scope.

## Does it really have to block release?

**It need not block a release limited to the accepted common examples.** It should block an unconditional claim that every case study is equivalent until the differences are explained or accepted. You may decide that budget-limited intermediate models are not release requirements, or that the changed curves do not affect the intended scientific conclusions. That is a reasonable scientific decision, but it should identify the exact results being accepted and why.

The spectral-guidance difference is already accepted separately: `1.2572461877946428e-6` against `1e-6`, with the same constrained model on both branches. Nothing here asks you to revisit that acceptance or to change its threshold.
