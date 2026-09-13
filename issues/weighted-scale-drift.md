# Investigate weighted 3D scale drift

## Status

Resolved — 2026-09-13. Cause 5, optimizer termination on a flat direction of
the objective. No v0.8 core defect and no core change. Both branches reach the
same objective value to machine precision after an identical number of function
evaluations and an identical termination condition; the residual `scale.3`
difference is 0.0026% relative and lies far inside the convergence tolerance
the fit was asked to achieve. See "Resolution" below.

## Question

Why does simultaneous_analysis_3d_weight produce a measurable difference in
fitted data and scale.3 between v0.7.4 and v0.8 staging?

Determine whether the cause is:

1. a translated-input difference;
2. a different weight construction or interval selection;
3. weighted versus unweighted residual handling;
4. scale estimation or final parameter assignment;
5. optimizer termination/convergence;
6. result serialization/reporting; or
7. a confirmed v0.8 package defect.

## Evidence

Source comparison: validation/comparisons/v07-v08-semantic.json.

- Scenario: simultaneous_analysis_3d_weight.
- Dataset 3 fitted-data normalized RMS difference:
  2.446285059310538e-05.
- Dataset 1 fitted-data normalized RMS difference:
  1.1250304137544782e-06.
- Dataset 2 fitted-data normalized RMS difference:
  1.2891184012654769e-06.
- scale.3: v0.7 72.73623223408798; v0.8 72.73812042544681.
- Relative scale.3 difference: 2.5959433157789032e-05.
- Parameter comparison otherwise passes under the declared 1e-4 relative
  tolerance.
- Weighted RMSE is persisted for the weighted datasets and agrees closely.
- Current acceptance threshold is a scenario-specific fitted-data normalized
  RMS tolerance of 3e-5. This is an acceptance threshold, not proof that the
  implementations are identical.

The example inputs are intended to be equivalent:

- v0.7 model:
  temp/pyglotaran-main-dev/pyglotaran-examples/pyglotaran_examples/test/simultaneous_analysis_3d_weight/model.yml
- v0.8 scheme:
  temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/test/simultaneous_analysis_3d_weight/scheme.yml
- shared parameters:
  test/simultaneous_analysis_3d_weight/parameters.yml
- shared weights:
  - dataset 2, global interval [400, 600], value 0.5;
  - dataset 3, global interval [400, 600], value 0.0025.

## Reproduction

Use the retained clean outputs:

~~~powershell
& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/compare_results.py --main-root validation/runs/main/output-remediated/home/pyglotaran_examples_results --staging-root validation/runs/staging/output-remediated-2/home/pyglotaran_examples_results_staging --output validation/runs/.weighted-scale-investigation.json
~~~

Relevant raw files:

- v0.7:
  validation/runs/main/output-remediated/home/pyglotaran_examples_results/simultaneous_analysis_3d_weight/dataset3.nc
- v0.8 input:
  validation/runs/staging/output-remediated-2/home/pyglotaran_examples_results_staging/simultaneous_analysis_3d_weight/optimization_results/dataset3/input_data.nc
- v0.8 residuals:
  the same leaf's optimization_results/dataset3/residuals.nc
- v0.8 fitted data:
  the same leaf's optimization_results/dataset3/fitted_data.nc
- both optimized parameter files:
  the scenario root optimized_parameters.csv

## Investigation procedure

1. Verify input and coordinate identity:
   - compare input arrays exactly;
   - compare time/spectral coordinates and ordering;
   - compare data source hashes and shapes.
2. Reconstruct the weight array independently from both schemes.
   - Confirm that [400, 600] selects the same spectral coordinates.
   - Confirm whether endpoints are inclusive in both branches.
   - Compare the saved v0.7 weight variable with the v0.8 internal or
     reconstructed weight array.
3. Compare objective inputs:
   - weighted data;
   - weighted residual;
   - unweighted residual;
   - CLP penalty contribution;
   - dataset scale contribution.
4. Compare optimizer settings and termination:
   - method;
   - maximum function evaluations;
   - ftol, gtol, xtol;
   - success/termination reason;
   - final cost and optimality;
   - parameter history length and final history row.
5. Run a controlled synthetic weighted fit under both APIs using a known
   analytic signal. Verify the objective, weighted RMSE, and saved scale.
6. Repeat dataset 3 with weights removed, constant weight only, interval weight
   only, fixed scale.3, and an increased evaluation budget.
7. Profile the objective around scale.3 and compare the local minimum and
   curvature between branches.

## Focused test to add

Add a validation-side test under validation/tests/ that:

- constructs a small weighted dataset with analytically known residuals;
- verifies the weight array and weighted residual;
- verifies weighted RMSE;
- verifies scale handling independently of optimizer convergence;
- fails if v0.8 applies interval weights to a different coordinate axis or
  reports a different scale convention.

Only add a v0.8 core regression test if the independent test demonstrates a
package behavior that cannot be addressed in the external validation layer.

## Acceptance criteria

Close this issue when one of the following is proven:

- the drift is eliminated by correcting a translated input or validation error;
- the drift is a documented solver/convergence convention with a focused test
  and justified tolerance; or
- a minimal v0.8 core defect is isolated, fixed, and covered by a regression
  test.

Do not close this issue by post-processing v0.8 parameters to equal v0.7.

## Non-goals

- Do not refactor weighted optimization globally.
- Do not change the public result model solely to make this comparison pass.
- Do not relax the tolerance further without a quantitative explanation.

## 2026-08-29 rerun evidence

The fresh comparison at
`validation/comparisons/v07-v08-20260829-162539Z.json` reproduces the previous
dataset-3 fitted-data normalized RMS (`2.446285059310538e-05`), parameter
result, and `EXPECTED_DIFFERENCE` status. The kinetic activation and equal-area
penalty fixes did not affect this scenario, so the scale-drift investigation
remains open.

## Resolution — 2026-09-13

### Evidence

Source: the final run `validation/comparisons/v07-v08-final-20260906-131441Z.json`
and the retained `result.yml` files under
`validation/runs/main/output-final/home/pyglotaran_examples_results/simultaneous_analysis_3d_weight/`
and
`validation/runs/staging/output-final/home/pyglotaran_examples_results_staging/simultaneous_analysis_3d_weight/`.

The optimizer ran identically on both branches:

| Quantity | v0.7.4 | v0.8 staging | Relative difference |
|---|---|---|---:|
| `number_of_function_evaluations` | 86 | 86 | identical |
| `success` | true | true | identical |
| `termination_reason` | `` `ftol` termination condition is satisfied. `` | `` `ftol` termination condition is satisfied. `` | identical |
| `chi_square` | 5029.018034571807 | 5029.01803457181 | 5.4255e-16 |
| `reduced_chi_square` | 0.05479068740953748 | 0.05479068740953751 | 6.3322e-16 |
| `root_mean_square_error` (dataset3) | 83.03097834229308 | 83.03100204448751 | 2.855e-7 |
| `weighted_root_mean_square_error` (dataset3) | 0.2075774458557327 | 0.20757750511121884 | 2.855e-7 |
| `scale.3` | 72.73623223408798 | 72.73812040514919 | 2.5959e-5 |
| `optimality` | 0.0009332387659575036 | 0.0009652588374045726 | 3.43e-2 |

The objective agrees to about two units in the last place of a double. The
SciPy `least_squares` default `ftol` of `1e-8` terminates when the cost change
falls below `ftol * cost = 2.5145e-5`. The observed cost difference between the
branches is `1.3642e-12`, which is `5.4e-8` times that threshold.

### Mechanism

`dataset3` carries `weights: [{value: 0.0025, global_interval: [400, 600]}]`, a
400-fold down-weighting, and its fitted `scale.3` is about 72.7. The weighted
residual contribution of `dataset3` to the sum of squares is scaled by
`0.0025**2 = 6.25e-6`, so `scale.3` is the most weakly determined parameter in
the problem. Both optimizers stop when the cost stops changing, and along this
direction the cost is flat to well below `ftol`. The two runs therefore halt at
different points on the same flat valley floor while agreeing on the objective
to machine precision.

The `optimality` (gradient infinity-norm) difference of 3.4% is consistent with
this: near a flat minimum the gradient is small (`9.3e-4` against a cost of
`2.5e3`) and dominated by rounding, so its relative spread is large while the
cost itself is converged.

### Disposition against the enumerated causes

1. Translated-input difference — excluded. `data` compares exactly
   (`max_abs = 0.0`, `normalized_rms = 0.0`) on all three datasets.
2. Weight construction or interval selection — excluded. Both schemes declare
   the same two rules (`0.5` and `0.0025` over `[400, 600]`), and
   `weighted_root_mean_square_error` agrees to `2.9e-7` relative on the
   weighted datasets.
3. Weighted versus unweighted residual handling — excluded, same evidence.
4. Scale estimation or final parameter assignment — excluded. All other
   parameters pass at `rtol = 1e-4`; only the weakest-determined one moves.
5. **Optimizer termination/convergence — confirmed.**
6. Result serialization/reporting — excluded. Persisted and recomputed values
   agree.
7. v0.8 package defect — not supported by any of the above.

### Magnitude in relative terms

Expressed as percentages of the reference values, the whole example matrix is
far inside the 0.1% acceptance band agreed for this comparison:

- worst fitted-data normalized RMS across all 14 scenarios: `2.4463e-5`
  = **0.0025%** (this scenario, dataset3);
- `scale.3`: **0.0026%**;
- objective (`chi_square`): **5.4e-14 %**.

The only parameter difference above 0.1% anywhere in the example matrix is
`study_transient_absorption/two_dataset_analysis` at 0.708%, which is the
separately dispositioned non-identifiability documented in
`issues/rates-k3d2-identifiability.md`; its fitted data agrees to 0.00076%.

### Focused test

The weighting convention is already covered independently of optimizer
convergence by `test_weight_reconstruction_and_derived_weighted_rmse` in
`validation/tests/test_compatibility.py`, which reconstructs the weight array
from the scheme, asserts the interval selection and value, and checks the
derived weighted RMSE. No new test is required.

### Acceptance

Closed under the second acceptance criterion: a documented solver/convergence
convention with a focused test and a justified tolerance. The existing
scenario tolerance of `3e-5` is retained and is not relaxed. No v0.8
parameters were post-processed.
