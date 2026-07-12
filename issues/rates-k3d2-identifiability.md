# Investigate rates.k3d2 identifiability and reporting

## Status

Open. Fitted-data agreement is acceptable under the documented ill-conditioned
threshold, but the parameter value is not reproducible and staging omits
related derived parameters. This is a possible optimization or result-reporting
defect, not a confirmed bug.

## Question

Is the rates.k3d2 discrepancy in the two-dataset transient-absorption scenario
caused by genuine non-identifiability, a different parameter transformation or
bound path, optimizer termination, or v0.8 result serialization/final-state
assignment?

Distinguish a scientifically unidentifiable parameter from a package defect.
Never force the staging value to the v0.7 value.

## Evidence

Source comparison: validation/comparisons/v07-v08-semantic.json.

- Scenario: study_transient_absorption/two_dataset_analysis.
- Dataset 1 fitted-data normalized RMS difference:
  1.3827653525142653e-05.
- Dataset 2 fitted-data normalized RMS difference:
  9.614891077393131e-06.
- Current scenario acceptance threshold: 2e-5, explicitly marked
  EXPECTED_DIFFERENCE.
- v0.7 rates.k3d2: 12499262.93414546.
- v0.8 rates.k3d2: 1.9365541471650807e25.
- Maximum relative parameter difference:
  1.5493346746669407e18.
- Staging also lacks b.1, b.2, and rates.k1sum in the persisted optimized
  parameter table, although these are present or derivable in v0.7.
- Weighted RMSE values and residual diagnostics are close.

The pattern indicates a weakly constrained parameter path, but does not
exclude defects in bounds, positivity/log transforms, relation expansion,
optimizer final-state handling, or persistence.

## Reproduction

Use the retained clean outputs:

~~~powershell
& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/compare_results.py --main-root validation/runs/main/output-remediated/home/pyglotaran_examples_results --staging-root validation/runs/staging/output-remediated-2/home/pyglotaran_examples_results_staging --output validation/runs/.k3d2-investigation.json
~~~

Raw parameter files:

- v0.7:
  validation/runs/main/output-remediated/home/pyglotaran_examples_results/study_transient_absorption/two_dataset_analysis/optimized_parameters.csv
- v0.8:
  validation/runs/staging/output-remediated-2/home/pyglotaran_examples_results_staging/study_transient_absorption/two_dataset_analysis/optimized_parameters.csv

Relevant inputs:

- v0.7 notebook:
  temp/pyglotaran-main-dev/pyglotaran-examples/pyglotaran_examples/study_transient_absorption/transient_absorption_two_dataset_analysis.ipynb
- v0.8 notebook:
  temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/study_transient_absorption/transient_absorption_two_dataset_analysis.ipynb
- v0.7 model and parameters:
  study_transient_absorption/models/model_2d_co_co2.yml and
  parameters_2d_co_co2.yml
- v0.8 scheme and parameters:
  study_transient_absorption/models/scheme_2d_co_co2.yml and
  parameters_2d_co_co2.yml

## Investigation procedure

1. Normalize both schemes and verify:
   - parameter labels;
   - initial values;
   - bounds and non-negative flags;
   - fixed/free status;
   - relations and derived expressions;
   - dataset-specific weights and scales;
   - optimizer method and termination settings.
2. Verify that rates.k3d2 exists in both normalized models and is truly free,
   rather than derived or omitted.
3. Inspect optimization histories:
   - parameter trajectory;
   - objective/cost trajectory;
   - final-state assignment;
   - number of evaluations;
   - solver success and termination reason.
4. Profile the objective while varying rates.k3d2 across many orders of
   magnitude with all other parameters fixed at the final solution.
   Plot objective, fitted-data RMS, and residual changes. Identify whether the
   objective is flat, monotonic, or has a finite minimum.
5. Repeat the fit with explicit finite upper bounds, a logarithmic
   parameterization, rates.k3d2 fixed, multiple initial values, and increased
   function-evaluation limits.
6. Compare parameter uncertainty/covariance behavior. A huge value with a
   flat profile and unbounded uncertainty supports non-identifiability.
7. Check whether v0.8 persists all derived relation parameters consistently.
   If b.1, b.2, and rates.k1sum are intentionally omitted by the v0.8 schema,
   implement reconstruction in validation compatibility first.

## Focused tests to add

Add validation-side tests that:

- verify normalized v0.7/v0.8 parameter topology and relation expansion;
- evaluate the objective profile for rates.k3d2;
- verify that a persisted optimized-parameter table represents the final
  optimizer state;
- verify reconstruction of fixed/derived parameters without changing raw
  artifacts.

Add a v0.8 core regression test only if the profile or final-state test proves
that staging reports a different identifiable solution or loses the actual
optimizer final state.

## Acceptance criteria

Classify as EXPECTED_DIFFERENCE if the objective profile is flat or practically
indistinguishable over the reported range, fitted data and scientifically
relevant derived outputs remain equivalent, and the instability is documented
and covered by a test.

Classify as a v0.8 defect if the parameter is identifiable under a stable
profile, v0.8 follows a different path despite equivalent inputs and settings,
or v0.8 serializes a value different from the optimizer final state.

## Non-goals

- Do not clamp or overwrite rates.k3d2 after optimization.
- Do not add a global bound solely to reproduce v0.7.
- Do not treat matching one scalar parameter as more important than the
  reconstructed fitted data without identifiability evidence.
