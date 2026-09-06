# 0_8-pygta-validation-workspace

This workspace establishes scientific parity evidence between pinned
pyglotaran v0.7.4 and the v0.8 staging branch. The reference branch is
`temp/pyglotaran-main-dev`; the staging branch is
`temp/pyglotaran-staging-dev`. Their environments and editable package
installations are independent.

## Current baseline

The [final current-tree validation](issues/final-validation-run.md) executes all
23 selected notebooks per branch successfully. Common examples have 8 `PASS`,
6 `EXPECTED_DIFFERENCE` and no regressions. All 40 case-study fits per branch
are captured; 11 fitted-data comparisons still exceed `1e-6`, so broad
case-study equivalence remains unproven. The report records exact revisions,
environment caveats and fresh artifact verification.

- 11 common validation notebooks run successfully on both branches.
- The scenario contract contains 14 comparable result leaves.
- The runtime benchmark covers 15 public fit invocations.
- The last accepted baseline semantic comparison has 8 `PASS`, 6 documented
  `EXPECTED_DIFFERENCE`, 0 regressions, and 0 missing-artifact failures.
- The final runtime benchmark has 150 timed samples. Function-evaluation counts
  match for 14/15 fits; spectral guidance uses 23 reference versus 21 staging
  evaluations. Runtime output is report-only.

The September 6 consolidation rerun on the current checkouts still executes
11/11 notebooks per branch, but reports one spectral-guidance `REGRESSION`
(`1.257e-6` fitted-data RMS against `1e-6`). The current source revisions differ
from the pinned contract. See the
[consolidation evidence](issues/notebook-compatibility-consolidation.md) for
the reports and exact revisions; this rerun is not an accepted parity baseline.

The later [runtime-optimization continuation](issues/staging-runtime-optimization-continuation.md)
passes all 14 leaves against fresh baseline staging and restores the current-tree
reference comparison to 8 `PASS`, 6 `EXPECTED_DIFFERENCE`, and zero regressions.
It reduces PFID reconstruction overhead while preserving current staging results
exactly. These measurements use the already upgraded installed scientific stack;
its dependency lock mismatch and inherited correctness concerns remain documented.

Pinned commits, scenario mappings, and comparison tolerances are maintained in
[`validation/scenarios.yml`](validation/scenarios.yml). The detailed comparison
layer is external to pyglotaran under `validation/compatibility/`.

Live notebook adapters are consolidated in the installable
[`pyglotaran_compat` package](validation/notebook_compat/README.md). Migrated
case-study notebooks import this shared implementation instead of embedding it.

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
