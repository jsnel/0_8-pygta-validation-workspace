# 0_8-pygta-validation-workspace

This workspace establishes scientific parity evidence between pinned
pyglotaran v0.7.4 and the v0.8 staging branch. The reference branch is
`temp/pyglotaran-main-dev`; the staging branch is
`temp/pyglotaran-staging-dev`. Their environments and editable package
installations are independent.

## Current baseline

The [fresh September 13 PR-readiness run](issues/pr-readiness-20260913.md) passes
all 23 selected notebooks per branch and accepts all 14 common example leaves
(8 PASS, 6 EXPECTED_DIFFERENCE). All 40 case-study fits are captured: 32 meet
`1e-6`, and 36 fall within the documented 0.1% engineering band. Four
budget-truncated fits remain above that band. Staging uses its locked scientific
stack, which differs from reference. This supports drafting the staging-to-main
PR with explicit CI and result-integrity follow-ups; it is not an unconditional
merge sign-off. Historical run summaries below retain their original scope.

The [September 13 CI restoration](issues/compare-results-ci.md) rerun passes
11/11 common notebooks per branch and accepts all 14 leaves (8 PASS, 6 documented
EXPECTED_DIFFERENCE). It explicitly revises spectral guidance alone to 2e-6
for reproduced optimizer-path drift, with the previous failing report retained.
A refreshed v0.7 gold-standard candidate and version-aware validator patch are
ready locally; remote CI still requires their publication and revision updates.


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
- [weighted scale drift](issues/weighted-scale-drift.md) — resolved 2026-09-13;
- [weighted-RMSE persistence](issues/weighted-rmse-persistence.md) — resolved
  2026-09-13;
- [PFID runtime and memory](issues/pfid-runtime-memory-profile.md) — runtime
  superseded 2026-09-13, memory attribution still open.

Do not force raw v0.8 parameters or decompositions to equal v0.7 values when
the parameter is non-identifiable. Classify those differences using reconstructed
fits and documented root causes.

## 2026-09-13 relative-magnitude assessment

Numerical differences are judged as a fraction of the reference magnitude, with
0.1% as the acceptance band. On that basis:

- All 14 common example leaves pass. Worst fitted-data normalized RMS is
  `2.4463e-5` = **0.0025%** (`simultaneous_analysis_3d_weight`, dataset3). The
  only parameter difference above 0.1% is the documented `rates.k3d2`
  non-identifiability at 0.708%, whose fitted data agrees to 0.00076%.
- [Weighted 3D scale drift](issues/weighted-scale-drift.md) is closed: both
  branches take 86 function evaluations, terminate on the same `ftol`
  condition, and agree on `chi_square` to `5.4e-16`. The `scale.3` difference
  of 0.0026% is movement along a flat direction of a dataset weighted `0.0025`.
- Of the 49 case-study fits with a non-zero difference, 8 exceed 0.1%; the
  2026-09-12 MCL refresh supersedes three, leaving 4 unique fits. Every one of
  them terminated on *maximum function evaluations* on at least one branch, so
  they compare truncated intermediates rather than converged solutions.
  Converged fits in the same studies agree to `1e-8` or better.

This is an engineering parity band, not a claim about experimental
uncertainty, and it does not by itself establish repository-wide scientific
equivalence.
