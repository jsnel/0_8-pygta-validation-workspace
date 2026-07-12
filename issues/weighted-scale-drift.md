# Investigate weighted 3D scale drift

## Status

Open. This is the highest-priority unresolved numerical difference in the
current example matrix. No 0.8 core change is justified until the same
objective and weight convention have been reproduced independently.

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
