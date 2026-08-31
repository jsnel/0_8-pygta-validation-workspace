# Inactive parameters in the reported free-parameter count

## Status

Explained. The parameter-count difference is expected, and the PFID
zero-active-parameter failure is resolved by treating it as a successful model
evaluation rather than invoking SciPy with an empty parameter vector.

## Finding

In `pub-2025-01-van-stokkum-et-al`, the first MCL analysis
`fit-001-target_result1` reports 28 free parameters on v0.7.4 and 26 parameters
on v0.8. The two extra v0.7 parameters are `scale.PSI1` and `scale.PSII1`.
Both are marked varying in
`77K_target_MCL/models/20241120streak_target_77K_supercomplex.csv`, but the
first `20241110streak_target_77K_supercomplex` model fits only `super1ns` and
`super2ns` and does not reference either scale.

v0.7 constructs the SciPy optimizer vector from every varying parameter in the
supplied parameter table. v0.8 first resolves the active experiment and builds
its optimizer vector only from parameters referenced by that experiment. Thus
v0.7 reports 28 variables and 170856 degrees of freedom, while v0.8 reports 26
variables and 170858 degrees of freedom.

The v0.7 optimized values of the two inactive scales (approximately 29.1 and
436.7, with zero reported standard error) are movement in unconstrained, flat
optimizer directions. They do not affect the residual and are not meaningful
parameter estimates.

Later in the notebook, the `20250201streak_target_77K_supercomplex` model adds
the `dataPSI1` and `dataPSII1` guide datasets and references `scale.PSI1` and
`scale.PSII1`. Both parameters are then active, and the reported parameter
counts agree at 28.

## Evidence

- Paired run: `validation/runs/case-studies/20260830-182522/`.
- Comparison report:
  `validation/comparisons/case-studies/20260830-182522/pub-2025-01-van-stokkum-et-al/comparison.json`.
- Reference result:
  `reference/worktree/77K_target_MCL/case-study-results/fit-001-target_result1/result.yaml`.
- Staging result:
  `staging/worktree/77K_target_MCL/case-study-results/fit-001-target_result1/result.yaml`.

## Disposition

Treat the first fit's two-count difference, and its corresponding two-count
degrees-of-freedom difference, as expected metadata. Do not add unused
parameters to the v0.8 optimizer merely to reproduce the v0.7 count. This note
explains the count only; fitted-data agreement remains the primary scientific
parity metric.

## PFID zero-active-parameter edge case

The PFID case study at `validation/runs/case-studies/20260830-235141/`
exposes the limiting form of the same behavior. Both supplied parameter tables
mark only `alpha.1` as varying, but neither active legacy model references
`alpha.1`; the PFID `alpha` fields are commented out. v0.7 therefore sends one
flat direction to SciPy and reports success after one evaluation with the
`gtol` condition. v0.8 resolves zero active varying parameters, constructs the
same initial model result, and then reports `success: false` because SciPy's
zero-column path raises `zero-size array to reduction operation maximum which
has no identity`.

This diagnostic difference does not change the reconstructed result. Across
the two PFID fits, all input arrays match exactly and the worst fitted-data
normalized RMS is `5.255481356856353e-13`. Function-evaluation counts remain
`1/1`.

The staging optimizer now handles this state explicitly. When model resolution
leaves no active varying parameters, it evaluates the model once without
calling `scipy.optimize.least_squares` and returns a successful result with:

- termination reason `No free parameters to optimize.`;
- zero parameters and zero Jacobian evaluations;
- a Jacobian with zero columns and a `0 x 0` covariance matrix; and
- the same fit, cost, and degrees-of-freedom metadata produced from the model
  evaluation.

A regression test reproduces the PFID shape precisely: all referenced
parameters are fixed while the sole varying parameter is unused and therefore
removed during model resolution. The complete optimizer test directory passes
(`55 passed`).

The repaired staging notebook run is at
`validation/runs/case-studies/20260831-224923/pfid/staging/`. Both real fits now
report `success: true`, one function evaluation, zero free parameters, and the
explicit termination reason above. The captured-fit comparison is at
`validation/comparisons/case-studies/20260831-224923/pfid/captured-fit-comparison.json`.
Comparing these results with the original v0.7 evidence produces the same
fitted-data normalized RMS values as before: `1.67741866882088e-13` and
`5.255481356856353e-13`.

Do not reactivate an unrelated parameter. Doing so would either turn the
validated reconstruction into a truncated optimization at `max_nfev=1` or
allow the already validated parameter set to move if the evaluation budget is
increased.
