# 0_8-pygta-validation-workspace

This workspace establishes scientific parity evidence between pinned
pyglotaran v0.7.4 and the v0.8 staging branch. The reference branch is
`temp/pyglotaran-main-dev`; the staging branch is
`temp/pyglotaran-staging-dev`. Their environments and editable package
installations are independent.

## Current baseline

- 11 common validation notebooks run successfully on both branches.
- The scenario contract contains 14 comparable result leaves.
- The runtime benchmark covers 15 public fit invocations.
- The latest semantic comparison is acceptable: 8 `PASS`, 6 documented
  `EXPECTED_DIFFERENCE`, 0 regressions, and 0 missing-artifact failures.
- The latest normalized runtime benchmark has 150 timed samples with matching
  function-evaluation counts across branches. Runtime output is report-only.

Pinned commits, scenario mappings, and comparison tolerances are maintained in
[`validation/scenarios.yml`](validation/scenarios.yml). The detailed comparison
layer is external to pyglotaran under `validation/compatibility/`.

## Completed setup

The initial parity infrastructure is in place:

- manifest-driven execution and result coverage for all common notebooks;
- external loaders and semantic normalization for monolithic v0.7 and split v0.8
  result layouts;
- label-aware array comparison, derived weighted-RMSE support, and scenario-level
  expected-difference classifications;
- corrected staging example inputs and result-saving coverage;
- focused compatibility/translation tests;
- validation-side fit-runtime benchmarking with reproducible manifests and plots.

These changes are documented in [`changelog.md`](changelog.md). Generated
reports and run outputs are intentionally excluded by [`.gitignore`](.gitignore).

## Agent handoffs

- [Agent operating instructions](AGENTS.md)
- [Rerun the v0.7.4/v0.8 validation](validation/AGENT_RERUN.md)
- [Rerun the fit-runtime benchmarks](validation/benchmarks/README.md)
- [Full validation documentation](validation/README.md)

## Remaining investigations

The active plan is [`validation_plan.md`](validation_plan.md). Current issue
briefs cover:

- [`rates.k3d2` identifiability](issues/rates-k3d2-identifiability.md);
- [weighted scale drift](issues/weighted-scale-drift.md);
- [weighted-RMSE persistence](issues/weighted-rmse-persistence.md).

Do not force raw v0.8 parameters or decompositions to equal v0.7 values when
the parameter is non-identifiable. Classify those differences using reconstructed
fits and documented root causes.
