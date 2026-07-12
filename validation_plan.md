# Active v0.7.4–v0.8 staging parity plan

The completed setup and current baseline are summarized in
[`README.md`](README.md). This document tracks only the remaining scientific
investigations and the procedure for accepting future changes.

## Scope and constraints

- Reference: pinned pyglotaran v0.7.4 under `temp/pyglotaran-main-dev`.
- Candidate: pinned v0.8 staging under `temp/pyglotaran-staging-dev`.
- Scope: 11 common notebooks, 14 result leaves, and 15 fit invocations.
- Compatibility and translation logic belongs under `validation/`.
- A pyglotaran core change is allowed only when a focused investigation proves
  a package defect and a validation-side solution is insufficient.
- Do not force raw parameters, decompositions, or serialized layouts to match
  when the scientific fit is equivalent or the quantity is non-identifiable.

## Current acceptance state

The latest clean validation has 11/11 notebooks passing on each branch. The
semantic comparison has 8 `PASS` and 6 documented `EXPECTED_DIFFERENCE` leaves,
with no missing artifacts or regressions. The normalized runtime benchmark has
matching function-evaluation counts across all 15 fit calls and remains
report-only.

Authoritative inputs and tolerances are in
[`validation/scenarios.yml`](validation/scenarios.yml). Rerun procedures are in
[`validation/AGENT_RERUN.md`](validation/AGENT_RERUN.md) and
[`validation/benchmarks/README.md`](validation/benchmarks/README.md).

## Remaining investigations

### 1. `rates.k3d2` identifiability

Use [`issues/rates-k3d2-identifiability.md`](issues/rates-k3d2-identifiability.md)
as the working brief. Verify bounds, initial values, parameter transforms,
termination status, parameter history, and objective sensitivity. Decide
whether the parameter is identifiable. If it is not, retain fitted-data and
derived-output comparisons as primary evidence and document the instability. If
it is identifiable and staging follows a different path, add the smallest fix
and a focused regression test.

### 2. Weighted scale and RMSE behavior

Use [`issues/weighted-scale-drift.md`](issues/weighted-scale-drift.md) and
[`issues/weighted-rmse-persistence.md`](issues/weighted-rmse-persistence.md).
Trace weight construction, objective weighting, residual unweighting, scale
estimation, metadata persistence, and reload behavior. Maintain an independent
synthetic weighted-fit test. Classify a remaining difference as a documented
convention only after the numerical and persistence paths are verified.

### 3. Spectral-guidance decomposition

For `ex_spectral_guidance`, compare labels, coordinate ordering, signs, scales,
matrix reconstruction, and shared parameters. The reconstructed fitted data
already agrees within tolerance. Determine whether the raw CLP/matrix and
parameter differences are non-identifiability or a deterministic ordering or
normalization defect. Keep representation-only differences in the compatibility
layer and add a reconstruction-equivalence test.

### 4. Evidence-linked architecture risks

Audit the known v0.8 risks only when an in-scope scenario provides evidence:

- parameter standard errors remaining in transformed/log space;
- incomplete `ParameterHistory`;
- ignored `add_svd` behavior;
- incorrect solver success or termination reporting;
- bypassed relations, constraints, penalties, or result hooks;
- persistence schema/version and label-order instability.

Each confirmed defect needs a minimal regression test. Avoid broad refactors of
`ModelLibrary`, `Scheme`, `Optimization`, or persistence architecture.

## Investigation loop

For each change:

1. Record the exact source revisions and affected scenario IDs.
2. Compare normalized inputs before interpreting numerical output.
3. Run the focused test and affected scenario.
4. Run the complete procedure in `validation/AGENT_RERUN.md`.
5. Run the runtime benchmark when optimizer workload or runtime changes.
6. Append evidence, metrics, classification, tests, and remaining uncertainty
   to `validation/logs/validation-log.md` and the relevant issue brief.

Never compare a regenerated result against an old generated artifact without
recording the new runner manifest and source-tree hashes.

## Final acceptance criteria

The parity work is complete when:

- all 14 declared leaves have complete, reloadable artifacts;
- translated inputs have normalized equivalence evidence;
- the external compatibility layer preserves raw artifacts and records every
  transformation;
- fitted-data, residual, parameter, and diagnostic differences meet their
  declared tolerances or have tested root causes;
- every confirmed staging defect has a focused regression test;
- remaining expected differences are documented in `issues/` and the comparison
  report;
- no broad pyglotaran change was introduced solely for comparison support; and
- a fresh rerun from the pinned manifests reproduces the accepted state.
