# Coherent-artifact and damped-oscillation amplitudes inflate the kinetic normalization sum

## Status

Root cause confirmed and reproduced. Fixed in the migration converter; the
underlying v0.8 core behavior is reported below as a separate, unresolved
design question.

## Finding

The v0.8 `KineticElement` normalizes its initial concentrations by the sum over
**every** entry of `activation.compartments`
(`glotaran/builtin/elements/kinetic/element.py:82-87`):

~~~python
normalization_sum = sum(
    float(value)
    for compartment, value in activation.compartments.items()
    if compartment not in activation.not_normalized_compartments
)
initial_concentrations[normalized_compartments] /= normalization_sum
~~~

The v0.8 `CoherentArtifactElement` *requires* its own element label to be a key
of `activation.compartments` and raises `GlotaranModelError` otherwise
(`glotaran/builtin/elements/coherent_artifact/element.py`), using
`activation.compartments[self.label]` as its amplitude. `DampedOscillationElement`
does the same for each oscillation label. The migration therefore has to add
those entries with value `1`.

In v0.7 those amplitudes did not exist: the normalization denominator was the
sum over the dataset's `initial_concentration` compartments only
(`InitialConcentration.normalized()`), which never contained artifact or
oscillation labels. Each added `<label>: 1` therefore inflates the v0.8
denominator by exactly 1.0 relative to v0.7 and shrinks every kinetic amplitude
in that dataset by the same factor.

## Relationship to staging commit `de2ae78e`

This is a narrow regression of `de2ae78e` ("Fix kinetic activation
normalization across elements", 2026-08-29), not a longstanding difference.
Before that commit the denominator was `np.sum(initial_concentrations[...])`,
the sum over the *calling element's own* compartments, which was wrong whenever
a dataset's initial concentration spanned several kinetic elements. The commit
correctly widened it to the whole activation, and its regression test
`test_initial_concentration_is_normalized_across_activation_compartments`
pins exactly that intent: a compartment `outside`, belonging to no element in
the data model, must still count towards the denominator (`1/(1+3) = 0.25`).

The gap is that `activation.compartments` is also the namespace v0.8 uses for
coherent-artifact and damped-oscillation amplitudes, so the widened sum cannot
tell "kinetic compartment owned by another element" (must be counted) from
"artifact amplitude" (must not be). Both intents are correct; only the
discrimination is missing.

## Reproduction

Case study `pub-2023-05-van_Stokkum_et_al`, notebook
`20230522PSI_TA_Scy6803target/20230521PSI_TA_Scy6803.ipynb`, eight linked
datasets, `maximum_number_function_evaluations=15`.

Normalization denominators at the shared starting parameters:

| dataset | extra activation entries | v0.7 sum | v0.8 sum | inflation |
|---|---|---|---|---|
| 670TR1 | `osc1: 1`, `artifact670: 1` | 1.028 | 3.028 | 2.945525 |
| 670TR2 | none | 1.028 | 1.028 | 1.0 |
| 700TR1 | `artifact700: 1` | 1.000 | 2.000 | 2.0 |
| 700TR2 | none | 1.000 | 1.000 | 1.0 |

`scale.670` (dataset 670TR1) is fixed at 1, so the estimated CLPs absorb the
670TR1 inflation and every free `scale.*` parameter absorbs the rest. Measured
CLP inflation staging/reference across all species: 2.9465 (predicted 2.945525;
the residual 0.03 % is the not-yet-converged IRF difference).

Cost trajectories:

| nfev | v0.7.4 reference | v0.8 as migrated | v0.8 with the fix |
|---|---|---|---|
| 1 | 869.51 | 30162.0 | — |
| 3 | 780.28 | 2020.2 | 780.2826936484729 |
| 15 | 778.42 | 778.29 | 778.4181898707781 |

The final costs nearly agree because the discrepancy is exactly a
reparameterization: the model is bilinear in the CLPs and the free dataset
scales, so both branches descend towards the same minimum from very different
starting points.

Optimized parameters, as migrated versus v0.7.4:

| parameter | v0.7.4 | v0.8 as migrated | ratio |
|---|---|---|---|
| `scale.670TR2` | 0.976034471 | 0.331347629 | 0.3395 |
| `scale.700` | 0.694305551 | 0.471376997 | 0.6789 |
| `scale.700TR2` | 0.701242023 | 0.238052385 | 0.3395 |
| `scale.Red1SADS` | 67.2126972 | 22.8095138 | 0.3394 |
| `scale.Red2SADS` | 108.921464 | 36.9671797 | 0.3394 |
| `scale.WLRCSADS` | 83.1294096 | 28.2272576 | 0.3396 |
| `scale.WLRP1SADS` | 1036.15138 | 351.769925 | 0.3395 |

`pyglotaran_extras.plotting.plot_traces.plot_data_and_fits` divides both data
and fitted data by `dataset_scale` (`divide_by_scale=True` by default), so the
drifted scales are what makes the migrated `plot_fitted_traces` figure disagree
visibly with the publication figure even though the native
`fitted_data`/`residual` arrays agree with v0.7 to plotting precision.

## Remediation

`validation/case_studies/migrate.py` now adds every coherent-artifact element
label and every damped-oscillation label it injects into
`activations.<name>.compartments` to
`activations.<name>.not_normalized_compartments` as well. That reproduces the
v0.7 denominator exactly without touching the kinetic compartment mask, and
without any pyglotaran core change.

Verified by rerunning the case study with the corrected activation: every
parameter matches v0.7.4 to at most `2.945e-06` relative deviation (worst:
`scale.WLRCSADS`), against factor-of-three deviations before the fix.

Regression test:
`validation/tests/test_case_studies.py::test_convert_model_excludes_non_kinetic_amplitudes_from_normalization`.

## Affected migrated models

Detected by scanning every `*_v08.yml` under `temp/case-studies/*/staging` for
activation compartments that are neither a compartment of a kinetic element in
the same data model nor already excluded from normalization:

- `pub-2023-05-van-stokkum-et-al/.../20230521model_PSI_TA_SCy6803WL_v08.yml`
  — `670TR1` (`osc1`, `artifact670`), `700TR1` (`artifact700`).
- `pub-2025-01-van-stokkum-et-al/77K_target_cells/models/20250415streak_DG_WT_target_DA_FRL_PSIIdifferent_v08.yml`
  — `DA410`, `DA610`, `FRL410`, `FRL610`, `DA410DG`, `DA610DG`, `FRL410DG`,
  `FRL610DG`, each with its own `*artefact` label.
- `pygta-protocol-ta-ps1/PSI_TA_Scy6803GTA/models/*_v08.yml` — ten models,
  `670TR1` (`osc1`, `artifact670`) and/or `700TR1` (`artifact700`).

Not affected, despite matching the scan heuristic:
`pub-2025-01-van-stokkum-et-al/RT_target_WT_dPSII_cells_PB/models/20250125_580_WTideal_v08.yml`,
dataset `WT580_data`. Its `PC650free`/`PC640free` entries are compartments of
the `mcfreerod` kinetic element, which is not in that dataset's `elements`.
v0.7 also counted them, because `InitialConcentration.normalized()` sums over
all listed compartments regardless of which k-matrix uses them. Both branches
agree, so these must stay in the denominator.

That distinction is the reason the fix belongs on the injected labels only and
must not be generalized to "sum only this element's own compartments".

## Open question for pyglotaran v0.8 core

A natively authored v0.8 model has the same footgun: the coherent-artifact
element forces its label into `activation.compartments`, and unless the author
separately knows to repeat that label under `not_normalized_compartments`, all
kinetic amplitudes in that dataset are silently divided by an extra `1 +
n_artifacts + n_oscillations`. Nothing warns.

Options, none applied here:

1. Exclude, in the normalization sum, any activation compartment that is the
   label of a non-kinetic element of the data model or an oscillation of one.
   Both are reachable from `model.elements` at `calculate_matrix` time.
2. Default `not_normalized_compartments` to those labels while leaving it
   overridable.
3. Move artifact and oscillation amplitudes out of `activation.compartments`
   into the element or data model, so the two concerns stop sharing a namespace.

Option 1 or 2 keeps `de2ae78e`'s intent and its `outside` regression test
intact, and preserves the v0.7 denominator in the `mcfreerod` case above,
because those labels are kinetic compartments of *some* element and would still
be summed. Deciding this is a v0.8 API question and is deliberately left to the
core maintainers; the migration layer is correct either way.

## Re-migration and paired rerun

Completed under timestamp `20260830-143435`. All four case studies were
re-migrated with the corrected converter and re-run end to end; the package
verifies at 3693 artifacts with zero errors.

- 20/20 notebooks passed (8/8 reference+staging run sets, exit code 0).
- Structural comparison of every regenerated scheme against its pre-fix version
  shows 29 differences, all of them `not_normalized_compartments` additions or
  extensions. The remaining textual churn is YAML anchor expansion, because the
  converter now builds a fresh exclusion list per activation instead of
  aliasing the shared `exclude_from_normalize` list.
- `pygta-protocol-streak-ps1` has no coherent-artifact or damped-oscillation
  element and serves as the control: its nine schemes are structurally
  identical to their committed versions (0 differences).
- `pub-2023-05` `20230522PSI_TA_Scy6803target`: every optimized parameter now
  matches v0.7.4 to at most `2.945e-06` relative, versus factor-of-three
  deviations before.
- `pub-2023-05` linked 25-dataset analysis: worst fitted-data normalized RMS
  improved from `1.7079` to `4.3105e-02`, a factor of 40.

### The primary metric was blind to this defect

The `results/20230520` leaf reports `7.2284e-07` both before and after the fix.
That is expected: the inflation is exactly compensable by the free dataset
scales, so at the end of a converged fit the *fitted data* agrees while the
*parameters* are off by an integer factor. Only the parameter comparison, the
initial cost, and the scale-divided trace plot expose it. Any future case study
whose fitted data passes while its scales drift by a near-integer ratio should
be checked against this issue.

## Not explained by this defect

`pub-2025-01` `77K_target_cells/case-study-results/fit-001-target_result1`
still reports a worst fitted-data normalized RMS of `0.2673076675046294`, with
`0.0` input difference on all 22 datasets. The fix moved its single-evaluation
cost only from `449930.0` to `449440.0`, against a v0.7.4 reference cost of
`512450.0`, and the reported optimality differs by four orders of magnitude
(`3.3` reference versus `53100` staging). Because the notebook budget is one
function evaluation, no parameter compensation is possible, so this is a
genuine model-evaluation difference at the shared starting parameters and a
separate open investigation. Differences are spread across all 22 datasets,
worst on the guidance datasets `dataPSII2DG` (`0.267`) and `dataPSII1`
(`0.148`).
