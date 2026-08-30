# Inactive parameters in the reported free-parameter count

## Status

Explained; this is an expected v0.7/v0.8 optimizer-input difference, not a
case-study migration defect.

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
