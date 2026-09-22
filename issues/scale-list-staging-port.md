# scale_list staging port — September 22

## Scope and source contract

Requested source: `ism200/pyglotaran` scale_list at
`84d838991e1d0280954350796037763d4bd612aa`. Current upstream main is
`e6ba6316f6bc7365211a841fc417c4a98f65860f`; the port branch is
`codex/port-scale-list`, based on upstream staging
`afce5d503066ed7f3acf4eae0958db0e20bdc326`.

Main and the feature branch have parallel historical commit identities; an
endpoint tree diff defines the relevant delta. A triple-dot comparison includes
large unrelated historical differences. Detailed architecture and migration notes
live in core `devdocs/scale-list-port/`. The initial plan was committed before
implementation as `ded0463b`.

## Evidence in progress

Fresh common reference execution: `validation/runs/main/scale-list-20260922-015900/`
completed 11/11 notebooks. Port and benchmark validation are pending integration.
No previous generated staging results will be reused for acceptance.

Evidence root: `validation/runs/scale-list-port-20260922-015900/`.
Source-feature selected tests at the exact pinned commit: 11 passed, two known
spline-knot resolution failures, 116 deselected. Both failures attempt to resolve
numeric knot coordinates as parameter objects. They are prototype defects, not
acceptance requirements for the port.

`validation/scale_list_port.py` constructs analytic Gaussian-convolved decays and
spectra independently of either engine, fits paired and linked/unlinked scaled
models, and records fitted data and CLP counts. The preliminary comparison gives
identical fitted data for both scale-list cases and 3.33e-16 normalized RMS for
paired composition, with identical rates/evaluation counts. Final evidence will
be regenerated after integration commits. This covers fixed scales; an additional
free-scale recovery test is required because cached numeric scales can otherwise
silently prevent scale parameters from participating in optimization.

The v0.7 full-model result is also retained raw. Its comparison uses a separately
reported named-dimension reconstruction to expose, rather than hide, the known
v0.7 residual reshape defect.

## Workspace changes

The external case-study converter now preserves source global megacomplexes,
paired composition, scale lists, global parameter penalties and optimizer settings.
Focused converter/ST regression checks pass 24 tests. Author notebooks and supplied
reference data remain unchanged. Existing deferred notebook selection is unchanged
until a separately evidenced execution justifies enabling it.

## Status

Implementation and full verification are ongoing. This brief is not final parity
acceptance or merge approval.
