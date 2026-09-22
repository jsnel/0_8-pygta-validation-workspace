# scale_list staging port — September 22

## Delivery and revision contract

The native port is on core branch `codex/port-scale-list` in
`temp/pyglotaran-staging-dev/pyglotaran`, based on upstream staging
`afce5d503066ed7f3acf4eae0958db0e20bdc326`. The tested runtime checkpoint is
`d38d973bc48501e9ba0a23e893acc8cb5293e1d8`. Later documentation-only commits
retain that implementation. The staging orchestration has a branch of the same
name; workspace evidence is on `codex/port-scale-list-validation`.

Requested source: `ism200/pyglotaran` scale_list at
`84d838991e1d0280954350796037763d4bd612aa`. Current upstream main/reference core:
`e6ba6316f6bc7365211a841fc417c4a98f65860f`. The initial plan was committed before
implementation as `ded0463b`, followed by separate IO, parameter, optimizer,
scaling, IRF, uncertainty, and integration checkpoints. GPT 5.6 Luna xhigh agents
performed the independent source, staging architecture, and auxiliary audits.

Main and the source branch have parallel historical commit identities; their
endpoint tree diff defines the relevant delta. A triple-dot comparison includes
large unrelated historical differences. See the core documents:

- [Endpoint delta](../temp/pyglotaran-staging-dev/pyglotaran/devdocs/scale-list-port/DELTA.md)
- [Committed port plan](../temp/pyglotaran-staging-dev/pyglotaran/devdocs/scale-list-port/PLAN.md)
- [Native API and migration guide](../temp/pyglotaran-staging-dev/pyglotaran/devdocs/scale-list-port/USAGE.md)
- [Scientific evidence and limits](../temp/pyglotaran-staging-dev/pyglotaran/devdocs/scale-list-port/EVIDENCE.md)

## Implemented scope

The port includes dynamic per-global-coordinate scales, scalar/vector composition,
paired single-amplitude global models, grouped/convolved and normalized Gaussian
IRFs, spline/skewed-Gaussian width dispersion, coherent orders four/five, consistent
initial-concentration normalization/reporting, relative equal-area and global
parameter penalties, final-area diagnostics, optimizer `x_scale`, opt-in CLP
uncertainty, table input checks/T-values, initial-bound diagnostics, and ITEX IMG IO.

Staging elements, objectives, typed results and saving options remain the native
architecture. External translation under `validation/` maps v0.7 dictionaries,
including grouped IRFs and fit controls. Author notebooks/data and the main
reference checkout remain unchanged. Deferred author single-amplitude case-study
notebooks have not been promoted to the common acceptance suite by this work.

## Fresh regression evidence

- Complete staging suite: **534 passed, 9 xfailed**;
  `validation/runs/scale-list-core-20260922-023751.log`.
- Validation-side suite: **67 passed, 1 skipped**;
  `validation/runs/scale-list-validation-20260922-023013.log`. The skip is the
  existing opt-in spectral-guidance trajectory probe.
- Ruff check and format check pass all 47 changed Python files.
- Dedicated uncertainty tests: **10 passed**, covering noisy unlinked/linked/
  paired fits, transformed optimizer coordinates, native Scheme keyword overrides,
  finite/nonzero errors, persistence, NNLS rejection, and exception restoration.
- Both common runners pass **11/11** notebooks. All **14 leaves** are accepted:
  **8 PASS, 6 EXPECTED_DIFFERENCE**, no REGRESSION, BASELINE_FAILURE or missing artifacts.

Final common artifacts:

- `validation/runs/main/scale-list-20260922-015900/manifest.json`
- `validation/runs/staging/scale-list-20260922-023731/manifest.json`
- `validation/comparisons/v07-v08-scale-list-20260922-023731.json`
- `validation/runs/scale-list-port-20260922-015900/manifest-verification.json`

Source, lockfile, examples and result-tree hashes were recomputed against both
runner manifests with zero mismatches. Core tree SHA-256 values:

- Main: `2ff4fef517dfbe5bb2d101d80257ea2aa1441f275de635cabc67253cf7e10159`.
- Staging: `1458b85acf9c4eceec5bfdba21667451e4f9afcf1a5de0bf7f77423a4cab2927`.

The current-tree revisions intentionally differ from historical initial pins in
`validation/scenarios.yml`; the user requested comparison with current main and
porting onto current staging. Scenario IDs, leaves, tolerances and classifications
were not changed. Main examples are `4a3268efbab28c190ab8348faedf51fe1b04faa2`;
staging examples are `ddfa63633eac47cf0e180d869bd06993d735cfc2`. Extras remain
`b72a21e07decc638dbf62ecdb7189a3e4693a320` and
`700f9de482f317afa0339edc12314fd14699e459` respectively.

## New-feature source parity

`validation/scale_list_port.py` constructs analytic Gaussian-convolved decays and
spectra independently of either engine, fits paired and linked/unlinked scaled
models, and records source revision, cleanliness, installed versions and harness
hash. Both captured code trees are clean.

The final report is
`validation/runs/scale-list-port-20260922-015900/synthetic-comparison-20260922-023731.json`.
Both scale-list cases match exactly. Paired fitted-data normalized RMS is
**3.326e-16**. Fitted rates and function-evaluation counts match; paired/linked/
unlinked CLP counts are **2/34/68**. Raw source paired fitted data is retained and
also agrees with its named-dimension reconstruction to 3.326e-16 in this fixture.
This does not reproduce the historical ST residual-reshape defect.

Fixed scales are used in the cross-version fixture. Independent free-scale
recovery with a fixed linked reference recovers `[2, 3, 4]`, guarding against
caching scale values and silently removing them from nonlinear optimization.

Selected tests in the exact source endpoint give **11 passed, 2 failed** (116
deselected). Both failures are the prototype treating numeric spline knot
coordinates as parameter objects. Native tests verify the corrected behavior.
Exploratory failures and earlier runs are retained, not reused as final evidence.

## Runtime measurement

The standard one-thread, one-warm-up/five-repetition alternating-branch benchmark
is running. Final report metadata and workload qualifications will be added here.

## Remaining scientific qualifications

The same six expected differences retain their documented causes. Spectral-guidance
normalized RMS is 1.25777e-6 (tolerance 2e-6); the transient two-dataset case is
8.81932e-6 (tolerance 2e-5), with its refined rate path and parameter drift. Secondary
3D/6D decompositions remain non-identifiable. The weighted 3D fitted-data RMS is
1.60659e-10; no acceptance tolerance was relaxed.

Source/main uses NumPy/SciPy/xarray 2.2.6/1.15.3/2025.6.1; staging uses
2.0.1/1.14.1/2024.7.0. No scientific dependency upgrade was performed. Runtime
comparisons therefore include environment differences. CLP uncertainties are
local linearized estimates for variable projection, not convergence or
identifiability guarantees. Paired/global CLP penalties remain outside the
pre-existing global objective; obsolete v0.7 KMatrix markdown formatting is not
reintroduced. Positional scale/IRF lists must follow data coordinate order.

All generated runs/comparisons/benchmarks remain ignored. Delivery branches are
local; no push, merge or PR publication is part of this handoff.
