# Spectral guidance: current-tree regression isolation

## Finding

The trigger is a change to the example's optimization problem, amplified by
floating-point sensitivity of the nonlinear fit. Both current example commits
fix `rates.k5`, `rates.k6`, and `scale.2`; the pinned examples let all three vary.
This reduces six free parameters to three. It is not a cross-version translation
error: the same constraint change was made on both branches.

With current core code, current installed dependencies, and unchanged notebook
budgets, restoring **only these three vary flags in memory** reproduces the
accepted spectral-guidance fitted-data normalized RMS exactly:
`3.0325968790706684e-7`. Keeping the flags fixed reproduces the current failure
exactly: `1.2572461877946428e-6`. No source checkout was reset or edited.

The mechanism is optimizer-path sensitivity to compartment ordering and the
numerical runtime, including the NNLS implementation. It is not evidence that
the constrained staging fit has a worse objective: its objective is lower than
the reference's. This does not justify reclassifying the scenario or increasing
the `1e-6` tolerance.

## Source and environment contract

| Component | Reference | Staging |
|---|---|---|
| Current core | `8f26be01d5a6ce63ec2556469ac3facc2d2cee68` | `51574847bd5cd0e98a6c301f3d557d6d4ed85cd2` |
| Current examples | `409af6f4f5f1979b669a0729c0443600cf307b73` | `4eed89efe8466b4e051fad7be8fcbf37b4c2a0b7` |
| Pinned examples | `5e157363ca6e776c3da7a6c4742a07930d205138` | `7f7fd227bcfb74308523d2242ca811a68ba25214` |
| NumPy / SciPy / Numba | `2.2.6 / 1.15.3 / 0.63.1` | `2.0.1 / 1.14.1 / 0.60.0` |
| Current free parameters | `rates.k1`, `rates.k2`, `rates.k4` | Same |
| Notebook evaluation budget | 23 | 21 |

Reference example commit `409af6f4` is titled "Constrain example model
parameters"; staging commit `4eed89e` is titled "Stabilize example model
parameters". Their spectral parameter-file diffs both introduce the three
`vary: False` changes. The actual current parameter-file SHA256 is identical on
both branches: `59aa7dfb5957496c4c7fe05c6716fbb927c29b87b53aeeea30c1102f13528897`.
The two raw ASCII data files are also identical across branches.

Historical reports corroborate the trigger: `20260829-162539Z` passes this
scenario at `3.0325968790706684e-7`; `20260829-224641`, after the example changes,
reports precisely the September 6 regression. A pinned-example run recorded in
`20260830-110309` again passes at the original value. These are historical
corroboration, not substitutes for the fresh paired probes below.

## Controlled experiments

Fresh final paired probes: `validation/runs/spectral-isolation-20260906-final/`.
Each variant contains arrays, all evaluated parameter/residual vectors, the
first linked NNLS matrix per objective call, and a JSON report with package
versions/paths, source revisions, parameter labels and input/script hashes.

| Experiment | Dataset1 fitted-data normalized RMS | Dataset2 RMS |
|---|---:|---:|
| Current flags, native environments, original budgets | `1.2572461877946428e-6` | `4.274172527076239e-10` |
| Restore only pinned vary flags, native environments, original budgets | `3.0325968790706684e-7` | `9.606064124298116e-11` |

The native probe's reconstructed fitted arrays are bit-for-bit identical to
the supplied `20260906-015900` saved results on both branches. The probe mirrors
native result-construction parameter state, rather than comparing only SciPy's
cached `fun` vector. Pinned-flag staging reaches its 21-evaluation budget;
passing fit agreement is not a claim of converged optimization.

Additional process-local interventions are retained under
`validation/runs/spectral-isolation-20260906/`:

- At the same initial parameters, full native objectives differ by only
  `6.5484e-11` maximum, relative norm `2.4274e-13`. The initial finite-difference
  Jacobians differ by relative norm `2.1519e-6`, maximum `0.0197443`. Their first
  log-parameter perturbation is the same, approximately `-2.32555e-8`.
- Reference orders compartments `[s1,s2,s3,s4,s5,s6]`; staging derives
  `[s4,s1,s3,s2,s5,s6]` from rate insertion order. After permuting reduced
  columns `(0,2,1,3)`, initial linked matrices differ by at most `2.22e-16`.
  Their conditioning is modest (initial condition number about 31), so this is
  not evidence for an ill-conditioned NNLS matrix itself.
- Giving staging the reference runtime **and** reference compartment order
  produces bit-for-bit identical initial objective, numerical Jacobian,
  accepted parameter vector, objective residual, and every optimizer evaluation.
  Both stop at 23 evaluations with cost `4902523.943208598`.
- Changing only order does not fix parity: under staging's runtime it produces
  a different endpoint. Changing only runtime also changes the endpoint.
  Therefore sorting labels is not an independently validated production fix.
- Loading only SciPy 1.14's Python NNLS implementation into the reference
  runtime reproduces every objective evaluation of reference-order staging
  using its native runtime. This directly demonstrates an NNLS contribution.
  The native-order staging experiment with that NNLS substitution does not
  reproduce the native staging path exactly; remaining numerical-runtime
  effects are not attributed to a specific NumPy/Numba/BLAS instruction.
- Increasing staging's budget to 23 (and the direct probe budget to 100) leaves
  its native endpoint unchanged: it terminates at 20 on `ftol` and `xtol`.
- A diagnostic `diff_step=1e-5` reduces initial cross-engine Jacobian relative
  difference to `8.33e-10`; paired optimizer-vector fitted-data difference is
  about `3.14e-7`. Both endpoints move, including reference. This supports
  derivative sensitivity but is not an approved tolerance or optimizer change.

The locally installed SciPy 1.14 `_nnls.py` solves active-set normal equations;
1.15 dispatches to `_cython_nnls`. Both core wrappers call SciPy `nnls` and form
`data - matrix @ clp`. No online release-note assumptions are needed for this
observed implementation difference.

## Guidance, penalties, comparison, and result construction

The unit guidance matrix targeting `s5` is the same on both branches. The
reference `[0,1000]` relation/penalty intervals cover the entire actual spectral
axis (`660.006` to `779.771`); staging's omitted intervals are equivalent here.
The native objective has 11,265 entries, including one equal-area penalty.

Fixed-parameter probes at initialization and both saved optima agree within
`8.01e-11` maximum over the whole objective. Corresponding penalty values agree
at approximately `0.30457209`, `4.26869755`, and `4.12401501`.
Evidence: `validation/runs/spectral-probe-20260906/`.

Both saved fits equal input minus residual exactly. Semantic dimension/coordinate
alignment requires no reordering for fitted data. The comparator correctly
applies the scenario normalized-RMS gate despite the looser elementwise
variable status being `pass`. The two supplied September 6 reports agree.

There is a **secondary result-construction defect**: current staging
`Optimization.run()` constructs results from mutable parameters left by the
last objective evaluation, without restoring `ls_result.x`. Reference
`Optimizer.create_result()` restores that vector. In the current staging run,
the saved log `rates.k4` is `-1.3906649676871297`, while the accepted value is
`-1.390664946964607`. The resulting dataset1 effect is only `9.5191e-10`
normalized RMS. Evaluating the accepted vector still exceeds the gate at
approximately `1.25776768e-6`; this defect does not cause the regression.
It is pre-serialization state handling, not NetCDF corruption.

## Reproduction and validation

`validation/spectral_guidance_probe.py` is an explicitly scenario-specific
standalone diagnostic. It uses private native objective APIs and process-local
patches; it never modifies installed packages, source models, or notebooks.
Run with each branch's Python and a fresh `--output` directory. Options:

- `--branch main --max-nfev 23` or `--branch staging --max-nfev 21` for native.
- Add `--pinned-vary` to restore the three historical vary flags in memory.
- For reference-equivalent staging, add `--canonical-compartments` and
  `--numeric-site temp/pyglotaran-main-dev/.venv/Lib/site-packages`.
- `--nnls-v14` loads the staging environment's Python NNLS implementation only.
- `--diff-step 1e-5` is a diagnostic derivative experiment.

The focused integration test is
`validation/tests/test_spectral_guidance_probe.py`. Set
`PYGLOTARAN_RUN_SPECTRAL_PROBE=1` and run it with pytest, using a fresh
workspace-local `--basetemp`. It launches both engines and asserts exact native
objective, Jacobian, accepted-vector and entire optimizer-trajectory parity
under the common reference runtime/order. It skips by default because it needs
both local environments. It does not bless the native current-tree regression.

Executed with explicit opt-in: **1 passed in 11.23 s**, artifacts under
`validation/runs/spectral-test-20260906/`. Fresh paired metric assertions also
passed; machine-readable summary:
`validation/runs/spectral-isolation-20260906-final/summary.json`.

No core or staging input was changed, so no full notebook rerun or runtime
benchmark was needed for these diagnostic-only edits. The accepted baseline
and current regression classification remain unchanged. Restoring the pinned
scenario is the minimal way to validate the existing contract; retaining the
new constrained problem requires explicit new scientific acceptance evidence.
The smaller accepted-vector restoration defect warrants its own focused fix
and result-state regression test.
