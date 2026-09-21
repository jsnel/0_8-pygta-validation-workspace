# Investigate rates.k3d2 identifiability and reporting

## Status

Resolved for the maintained two-dataset example. The old example exposed an
unnecessary `rates.k3d2` path and did not represent the supplied OC/COC target
model. Both pinned example notebooks now use the refined target model with
coherent-artifact elements and explicit CLP relations. No pyglotaran core or
serialization fix was required.

## 2026-09-22 notebook alignment

The staging two-dataset notebook now follows main's nine-cell workflow and
uses `dataset1`/`dataset2` throughout, including the staging scheme keys.
Earlier references below to `oc_tol_data`/`coc_tol_data` are historical.
Staging retains scheme loading/optimization, native saving, and extras plotting
conversion. Exercises, dry-run diagnostics, file/parameter displays, extra
plots, and rate inspection were removed. Numerical model settings, parameters,
the 11-evaluation budget, and existing local kernel metadata are preserved.

Focused execution passed at
`validation/runs/two-dataset-cleanup-focused-20260922-001548/`.
Fresh full runs at `validation/runs/{main,staging}/two-dataset-cleanup-20260921-221632/`
passed 11/11 notebooks each. The comparison at
`validation/comparisons/two-dataset-cleanup-20260921-221632.json` accepts all
14 leaves (8 PASS, 6 EXPECTED_DIFFERENCE), with no missing artifacts or
regressions. This scenario's worst fitted-data normalized RMS remains
`8.81932458660469e-6`, below `2e-5`; documented secondary differences remain.
Both manifests and source, lockfile, and result-tree hashes were verified.

Actual core revisions: main `e6ba6316f6bc7365211a841fc417c4a98f65860f`,
staging `c71ebad0552c9fa8d0bfdc9a2d8f45e41a696f4a`.
Examples revisions: main `4a3268efbab28c190ab8348faedf51fe1b04faa2`,
staging `44e3747cf39f0482ed5c05578624577938159085` plus this working-tree edit.
These are current-tree results; revisions differ from the pinned contract.

Validation tests: 62 passed, 1 skipped after updating the benchmark's staging
fit-cell selector from `3` to `4`. The first run caught that stale selector
(61 passed, 1 failed, 1 skipped). No fit-runtime benchmark was run: the public
fit workload and budget are unchanged, and removed diagnostics are outside
its timing scope. No core edits or commits.

## Question

Is the rates.k3d2 discrepancy in the two-dataset transient-absorption scenario
caused by genuine non-identifiability, a different parameter transformation or
bound path, optimizer termination, or v0.8 result serialization/final-state
assignment?

Distinguish a scientifically unidentifiable parameter from a package defect.
Never force the staging value to the v0.7 value.

## Historical evidence

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

## Resolution evidence

The refined OC/COC model was applied to both example notebooks and executed in
fresh isolated environments:

- v0.7 and v0.8 use the meaningful dataset labels `oc_tol_data` and
  `coc_tol_data`.
- Both models contain fast and slow kinetic elements, coherent-artifact
  elements, weights, and the two wavelength-bounded CLP relations.
- Neither fresh optimized-parameter table contains `rates.k3d2`.
- The paired focused comparison has worst fitted-data normalized RMS
  `8.81932458660469e-06`, within the scenario tolerance of `2e-5`.
- The largest remaining shared-parameter difference is `0.008214203879398103`
  relative at `mc_scale.1`; this is bounded optimizer/scale drift in the
  refined model, not the historical unbounded `rates.k3d2` path.

Focused artifacts are retained under
`validation/runs/k3d2-fix-focused/`, with the final one-scenario comparison
report at `validation/comparisons/k3d2-fix-focused-final.json`. The initial
all-scenarios comparison command
also reports missing leaves because it intentionally contains only this
scenario; those baseline failures do not describe the two-dataset result.

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

## Historical investigation procedure (superseded)

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

## Focused tests considered

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

## Historical acceptance criteria

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

## Historical 2026-08-29 rerun evidence

The fresh comparison at
`validation/comparisons/v07-v08-20260829-162539Z.json` reproduces the previous
fitted-data metric (`1.3827653525142653e-05` worst normalized RMS), parameter
difference, and `EXPECTED_DIFFERENCE` status. The kinetic activation and
equal-area penalty fixes did not affect this scenario, so this investigation
did not change the historical classification. It is superseded by the refined
OC/COC model evidence above.
