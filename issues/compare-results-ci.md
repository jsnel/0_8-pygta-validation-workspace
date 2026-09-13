# Restore compare-results with external semantic validation

Local implementation and fresh acceptance verification are complete. Remote CI
is not yet restored: the validator patch and refreshed gold standard must be
published and their immutable revisions selected before the workflow is landed.
No commits, pushes, or baseline publication were performed.

## Decision

Use one external validator with a backward-compatible legacy mode and an opt-in
semantic mode. Detect the persisted schema independently on each side: `data`
selects monolithic v0.7; `optimization_results` selects split v0.8. Reject unknown,
ambiguous, and empty layouts. No installed pyglotaran dependency or core changes
are needed. Canonicalize names, transpose named dimensions and reorder matching
coordinate labels; never drop extra coordinates to manufacture agreement.

Input values and dimension coordinates must agree exactly. Fitted data use RMS
of differences divided by reference RMS (epsilon floor for zero reference), with
finite arrays required. Tolerances are 1e-6 ordinarily, 2e-6 for spectral guidance,
2e-5 for transient two-dataset analysis and 3e-5 for weighted 3D. Parameters use
rtol=1e-4/atol=1e-8 and remain secondary alongside decompositions and metadata.
Missing result leaves, dataset files, declared split fields, parameter artifacts,
and empty contracts fail. Numeric disagreement in secondary evidence does not
excuse input or fitted-data failures. See `validation/scenarios.yml` and the
spectral-guidance issue for the explicit acceptance change.

## Root causes and evidence

The old validator recursively requests the gold-standard relative `.nc` paths.
A split result tree cannot satisfy those monolithic paths; increasing a numeric
tolerance cannot repair this. Parameter NaNs and non-identifiable decompositions
also make the old all-fields comparison unsuitable as the scientific gate.
The action declared `validation_name` but used `set_example_list`, accidentally
selecting the action root rather than the requested validator. The existing
consumer used floating `@main` rather than the validation submodule gitlink.
Additionally the legacy selector cloned its own gold branch and preferred the
home-directory current tree, ignoring the workflow's explicit checkout. Both
validator copies now honor explicit reference/current environment paths before
those local fallbacks, so a pinned workflow baseline is actually consumed.

The locally available historical gold-standard revision is
`5a55a79b9fd0379af673d664c52e83b064db52ce`. It also does not satisfy today's
14-leaf contract against fresh v0.7: the maintained two-dataset leaf is absent,
and spectral guidance differs by 2.7360190843979665e-6. The legacy blocklist hides
those scenarios. A current v0.7 baseline refresh is necessary; do not simply
raise all tolerances or omit a required scenario.

## Legacy reproduction

`validation/reproduce_legacy_validator.py` binds explicit result roots before
pytest collection and avoids upstream clone/fetch/reset operations. Against
historical gold `5a55a79b`, gold self-comparison and fresh v0.7 each pass **577
tests**. Against the same gold, fresh staging gives **5 failed, 8 passed,
3 skipped**: four parameter tests and the missing-file guard (24 missing monolithic NetCDF paths after the historical blocklist). Fresh main against staging reproduces **6 failed tests and 26 missing NetCDF paths**, recorded in `legacy-main-staging.txt`. This freshly
reproduces the main-pass/staging-fail mechanism; the historical six-failure count
is not claimed for these newer inputs. The missing monolithic files have split
counterparts, which the semantic adapter compares successfully.

Logs are `legacy-gold-self.txt`, `legacy-gold-main.txt`, and
`legacy-gold-staging.txt` in the evidence directory. Reproduce with:

```powershell
& temp/pyglotaran-staging-dev/.venv/Scripts/python.exe validation/reproduce_legacy_validator.py `
  --validator temp/pyglotaran-staging-dev/pyglotaran/validation/pyglotaran-examples/test_result_consistency.py `
  --reference-root validation/runs/gold-20260913-000749 `
  --current-root validation/runs/staging/ci-restore-20260913-000749/home/pyglotaran_examples_results_staging
```

## Fresh verification

Evidence directory: `validation/comparisons/ci-restore-20260913-000749/`.
Runs: `validation/runs/{main,staging}/ci-restore-20260913-000749/`.
Both runner manifests record 11/11 successful notebooks, zero failures, source,
lockfile and result-tree hashes. All 14 leaves are present. `main-staging.json`
retains the initial 1e-6 guidance failure; `main-staging-accepted.json` records
8 PASS, 6 EXPECTED_DIFFERENCE, zero regressions and zero baseline failures.
`action-package.json` verifies the standalone action payload on the same fresh
pair. `gold-main.json` records historical-baseline incompatibility.

Reference core: `8f26be01d5a6ce63ec2556469ac3facc2d2cee68`.
Staging core: `879c5bce399b7195b7ed2b0aece9234d803a74d9`.
Reference examples: `23287837579b9ad150ca33cce2b34bba33ec1e0d`.
Staging examples: `44e3747cf39f0482ed5c05578624577938159085`.
The scenario revision contract was refreshed to these measured checkouts.
This is Windows evidence using the existing isolated environments, not a claim
that Linux CI or newly installed dependency versions have been exercised.

Tests: `python -m pytest validation/tests -q` gives 56 passed, one opt-in
spectral probe skipped. Standalone `semantic/tests` gives 19 passed. Coverage
includes all three version pairings, missing secondary files, changed exact
input, fit drift, NaNs, changed/extra coordinates, secondary-only differences,
empty contracts and scenario-specific tolerance behavior. Runtime benchmarks
were not rerun because no optimizer or benchmark workload changed.

## Changed files

Root: `validation/compare_results.py`, `validation/compatibility/{load_result,
metrics,normalize}.py`, `validation/scenarios.yml`,
`validation/tests/test_ci_semantic.py`, `validation/reproduce_legacy_validator.py`,
this brief, the spectral-guidance brief, README, changelog and validation log.
Both pyglotaran checkouts: `.github/workflows/integration-tests.yml`.
Both nested validator checkouts: `action.yml` and
`pyglotaran-examples/test_result_consistency.py` (explicit root selection).
Staging validator additionally: `requirements.txt` and standalone `semantic/`
with adapters, manifest, README and tests. Existing unrelated workspace edits
were preserved; no generated artifact was staged.

## Publication handoff

1. Publish the standalone `semantic/` directory, its tests, requirements and
   fixed `action.yml` from the staging validator checkout to
   `glotaran/pyglotaran-validation`. These are uncommitted nested-repository
   edits, not root-workspace files. Current validator HEAD is
   `ae5af096a186833c181871f7b0435d40858e3a98`; it does **not** contain this patch.
2. Review `gold-standard-candidate.zip` and its `.sha256` file in the evidence
   directory. The bundle contains fresh v0.7 results, runner manifest, scenario
   contract, and source revision text files. Publish a new comparison-results
   commit without discarding historical evidence; replace the workflow gold
   reference with that new full commit SHA.
3. Update the pyglotaran validation gitlink to the published validator commit.
   The workflow checks out that gitlink and invokes the local action, eliminating
   floating `@main`. The existing gitlink is insufficient until updated; do not
   land only the workflow diff. Stage gitlinks only when committing is requested.
4. Align/pin example action and source revisions with the measured example
   contract. The existing floating example branches are a remaining upstream
   reproducibility dependency. Exercise Linux CI against the published baseline
   and upload JSON/Markdown evidence on failures as well as successes.

The root `validation/` adapter is the maintained development source; the nested
validator `semantic/` payload is its export for upstream review. Keep the two
copies synchronized when revising this patch.

## Two-path fallback

If maintainers cannot move v0.7 CI to the current contract immediately, retain
its pinned legacy validator and historical gold SHA. Give staging the shared
validator's semantic mode with the refreshed v0.7 gold SHA and explicit contract.
Alternatively add a v0.8 native regression job against a separately reviewed
v0.8 baseline, while retaining a v0.7-to-v0.8 semantic parity job on the common
14 leaves. Require both jobs for staging. A native v0.8 self-comparison alone
cannot establish cross-version scientific parity.
