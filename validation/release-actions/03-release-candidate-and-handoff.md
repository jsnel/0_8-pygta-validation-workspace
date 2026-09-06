# 3. Ensure the evidence applies to the version you actually release

Companion to action 3 in the [release report](../release-decision-report.md). Written 6 September 2026. This document proposes a handoff; it does not change branches, commit anything or run tests.

## The issue in simple terms

The study contains good results from several dates, but the code changed between those dates. A successful test of an August version does not automatically prove that every part of the September version works.

There is also more than one component: core pyglotaran, examples, extras/plotting, and the compatibility helpers used by migrated notebooks. They must work together. A “release candidate” simply means writing down exactly which version of each component you intend to ship, so a successful check has a clear meaning.

**This is mainly a release-preparation task, not a newly discovered scientific defect.** It should not force another full research campaign if the candidate is unchanged and existing evidence already covers it.

## What changed, and why it matters

| Evidence | What it covers | What it does not establish |
|---|---|---|
| Accepted August 29 common comparison | Staging core `fb001015`, examples `7f7fd227`, extras `d57940be`; 8 PASS and 6 EXPECTED_DIFFERENCE | All behavior of the later staging candidate |
| September 6 common comparison | Staging core `51574847`, examples `4eed89ef`, extras `700f9de4`; all common notebooks run, with accepted spectral exception | Complete current extras/core test-suite coverage or external case-study scientific acceptance |
| September 6 consolidated case-study execution | All 12 staging notebooks run with shared compatibility helpers | A fresh paired scientific comparison of all those notebooks |
| Historical extras test run | 133 passed, 2 failed, 10 errors in the initial staging test run; reported API/fixture mismatches | Whether those same tests still fail now, or whether their failures affect users |

The current reference extras checkout also has Python syntax its reference Python 3.10 cannot import. The successful reference rerun used a preserved older plotting copy. This is documented, and does not invalidate the numerical evidence, but the environment must remain reproducible. See [consolidation provenance](../../issues/notebook-compatibility-consolidation.md) and [test history](../logs/validation-log.md).

Full commit IDs and source-tree distinctions are in the [release report](../release-decision-report.md). The common comparison contract remains pinned to the earlier baseline; the report's exception does not silently update it.

## Where to look

- [Common scenario contract](../scenarios.yml): declared source revisions, result leaves and tolerances. Keep the historical baseline distinguishable from the final candidate.
- [Common runner](../run_examples.py): notebook execution and source/environment/artifact manifests. Inspect the actual imported source paths, not just displayed package version strings.
- [Common comparator](../compare_results.py): the machine acceptance result remains false for current spectral guidance; release documentation supplies the explicit exception.
- [Full rerun handoff](../AGENT_RERUN.md): the standard checks after code/input changes. The documented reference plotting overlay must be accounted for when using the current reference checkout.
- [Staging core tests](../../temp/pyglotaran-staging-dev/pyglotaran/tests) and [staging extras tests](../../temp/pyglotaran-staging-dev/pyglotaran-extras/tests): distinguish broken test fixtures from real missing v0.8 support. Do not assume that an old failure remains present or has gone away.
- [Compatibility package README](../notebook_compat/README.md) and [package source](../notebook_compat/pyglotaran_compat): decide how users of migrated notebooks will install these helpers.
- [Case-study packaging tool](../case_studies/package.py): retained artifact packaging and verification machinery.
- [Root ignore rules](../../.gitignore): much of the scientific evidence under runs/comparisons/benchmarks is deliberately not committed.

## My recommended handoff

1. **Name the candidate.** Record the actual core/examples/extras commits and any local changes included. Record the supported Python/dependency environment and required compatibility package. A branch name alone can move and is insufficient.
2. **Match existing evidence to that candidate.** Reuse checks that apply. If a fix changes optimizer/result behavior, run its focused test and the common rerun; rerun affected case studies as needed. Do not replay unrelated expensive studies merely because the report is new.
3. **Resolve the extras test question.** Inspect the historical failing tests against the candidate. Fix obsolete test calls if they no longer express the supported API; fix production behavior if a supported operation is broken. Obtain an appropriate clean result or document a precise exclusion. The current notebook successes already give useful plotting evidence.
4. **Write the user migration instructions.** Explain model translation, result layout/accessor changes, required notebook helpers and supported limitations. State the accepted spectral-guidance exception exactly. Do not describe the original `1e-6` threshold as passed.
5. **Preserve the evidence before retirement.** Store the cited JSON reports, manifests, source patches, dependency details and needed result artifacts somewhere durable. Verify the package using hashes. Keep the v0.7 reference reproducible for old publications even if active support ends.
6. **Promote the reviewed candidate.** After the decision, perform the normal reviewed merge/tag/release process across the appropriate repositories. That is a later authorized action, not something this documentation task performs.

## Does this have to be a blocker?

**Yes for identifying what is being released; no for requiring every historical test to be rerun without a reason.** The minimum is a traceable candidate, relevant checks, a usable migration path and retained evidence.

The old extras failures alone are not proof of a present release blocker. They are an unresolved question in the accumulated record. You can downgrade that concern if current candidate evidence shows that the supported API works and the historical failures were obsolete tests. Likewise, ending v0.7 maintenance does not require deleting the reference environment or losing the ability to reproduce old work.

This action is complete when another maintainer can answer: “Which exact version was approved, what checks support it, what exceptions were accepted, and how can we reproduce or investigate a problem later?”
