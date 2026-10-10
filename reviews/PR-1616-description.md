Merges `staging` into `main`: the rewrite of pyglotaran's modelling, optimization and result layers that will be released as 0.8.0. @joernweissenborn started the rewrite in December 2022; @s-weigand and @jsnel completed it with him.

`staging` is 178 commits ahead of `main` and 0 behind (merge base `e6ba6316`, #1610), so every change on `main` is already included. Please merge with **Create a merge commit** so the full history and the individual staging PRs stay reachable.

0.8 is a breaking release. v0.7 model files, scripts and saved results have to be ported; 0.8 has no loader for the v0.7 formats.

### v0.7.4 → 0.8 in one example

```python
# v0.7.4
from glotaran.io import load_dataset, load_model, load_parameters, save_result
from glotaran.optimization.optimize import optimize
from glotaran.project import Scheme

model = load_model("model.yml")
parameters = load_parameters("parameters.yml")
scheme = Scheme(model=model, parameters=parameters, data={"my_data": load_dataset("data.ascii")})
result = optimize(scheme)
sas = result.data["my_data"].species_associated_spectra
save_result(result, "my_result/result.yml")
```

```python
# 0.8
from glotaran.io import load_dataset, load_parameters, load_scheme

scheme = load_scheme("scheme.yml")
parameters = load_parameters("parameters.yml")
result = scheme.optimize(parameters, {"my_data": load_dataset("data.ascii")})
sas = result.optimization_results["my_data"].elements["sequential"].amplitudes
result.save("my_result")
```

<details>
<summary>The same model as a v0.7.4 <code>model.yml</code> and a 0.8 <code>scheme.yml</code> (getting started guide)</summary>

```yaml
# v0.7.4 model.yml
initial_concentration:
  input:
    compartments: [s1, s2, s3]
    parameters: [input.1, input.0, input.0]
k_matrix:
  k1:
    matrix:
      (s2, s1): kinetic.1
      (s3, s2): kinetic.2
      (s3, s3): kinetic.3
megacomplex:
  m1:
    type: decay
    k_matrix: [k1]
irf:
  irf1:
    type: gaussian
    center: irf.center
    width: irf.width
dataset:
  my_data:
    initial_concentration: input
    megacomplex: [m1]
    irf: irf1
```

```yaml
# 0.8 scheme.yml
library:
  sequential:
    type: kinetic
    rates:
      (s2, s1): kinetic.1
      (s3, s2): kinetic.2
      (s3, s3): kinetic.3
experiments:
  my_experiment:
    datasets:
      my_data:
        elements: [sequential]
        activations:
          irf:
            type: gaussian
            center: irf.center
            width: irf.width
            compartments:
              s1: input.1
```

</details>

### What changes for users

**Model specification**

- A scheme file (`load_scheme`) replaces the model file. It has a `library` of model elements and `experiments` that assign elements to datasets. The scheme holds no parameters, data or optimizer settings; these are arguments of `Scheme.optimize`.
- Megacomplexes become *elements*: `kinetic`, `spectral`, `baseline`, `clp-guide`, `coherent-artifact`, `damped-oscillation` and `pfid`. One `kinetic` element with `rates` replaces the `decay`, `decay-parallel` and `decay-sequential` megacomplexes, their `k_matrix` and `initial_concentration`. The IRF and the input compartments move to dataset `activations` (`instant`, `gaussian`, `multi-gaussian`). Kinetic elements can extend other kinetic elements (`extends`).
- Experiments replace dataset groups. An experiment sets the residual function, CLP linking (`clp_link_tolerance` and `clp_link_method`, previously on `Scheme`), `clp_relations`, `clp_penalties` and the dataset `scale`. CLP constraints are defined on elements.
- A dataset lists its `elements`, and optionally `global_elements` (full 2D models), `element_scale` and `weights`.
- Dataset, element and activation labels name the files of a saved result, so they cannot be empty, `.` or `..`, or contain `/`, `\` or `:`. A dataset label can be used in only one experiment.
- Model items, `Parameter`, `Scheme` and `Result` are pydantic v2 models. `glotaran.utils.json_schema.create_model_scheme_json_schema` writes a JSON schema for scheme files, optionally with the parameter labels of a parameters file, for validation and completion in editors.

**Optimization**

- `Scheme.optimize(parameters, datasets, ...)` replaces `optimize(Scheme(...))`. The optimizer settings (`optimization_method`, `ftol`, `gtol`, `xtol`, `maximum_number_function_evaluations`) are keyword arguments and are stored in `Result.optimizer_settings`.
- `glotaran.optimization` is rewritten (data, matrix, estimation, penalty and objective modules). The residual functions are still variable projection and NNLS.
- `clp_link_method` `forward` and `backward` link a coordinate with the nearest coordinate in that direction. v0.7.4 could pick a coordinate from the wrong position of the axis; `nearest`, the default, was not affected.

**Results**

- `Result.optimization_results[<dataset>]` replaces `Result.data[<dataset>]`. Each entry holds `input_data`, `residuals`, `fitted_data`, one dataset per element (`elements`) and per activation (`activations`), the `fit_decomposition` (CLPs and matrix) and metadata (RMSE, weighted RMSE, scale). For a kinetic element, `amplitudes` are the species-associated and `kinetic_amplitudes` the decay-associated amplitudes.
- Fit statistics and the parameter and cost histories are in `Result.optimization_info`.
- Results hold no singular value decompositions of data and residuals, and `add_svd` is gone. pyglotaran-extras computes them when plotting (`glotaran.io.prepare_dataset.add_svd_to_dataset`).
- `Result.save(folder)` writes `result.yml`, `scheme.yml`, parameter and history CSV files, and a folder per dataset with one netCDF file per result part. `SavingOptions` (e.g. `SAVING_OPTIONS_MINIMAL`) selects the parts; `load_result` reads the folder.
- The pyglotaran-extras plotting functions read the 0.7 result format. `pyglotaran_extras.compat.convert(result)` (pyglotaran-extras branch `staging_support`, released after this PR is merged) converts a 0.8 result for them.

**Projects**

- The v0.7 `Project` (model, parameter and data registries, generators, `project.optimize(model_name, parameters_name)`) is removed. The new opt-in `Project` (#1615) records each fit run through `project.optimize`, and lists, compares, recomputes and exports recorded fits. See `docs/source/user_documentation/project.md`.

**Removed**

- The command line interface and its `glotaran` command, the deprecations due in 0.8.0 (`glotaran.examples`, `glotaran.parameter.ParameterGroup`), the `folder` project-IO plugin, the model and parameter generators, `load_model`/`save_model`, `Result.markdown()`, `Result.recreate()`, `Result.verify()` and the `benchmark/` suite. The `attrs` and `click` dependencies are dropped.

**Plugins**

- Element plugins register under the entry point group `glotaran.plugins.elements` (was `glotaran.plugins.megacomplexes`) and implement `Element.calculate_matrix` and `Element.create_result`. Project-IO plugins have no `load_model`/`save_model`.

### What changes for contributors

- Tests are in `tests/` instead of next to the modules.
- Development uses uv: dependency groups and `uv.lock` replace the `dev`, `docs` and `test` extras and `requirements_pinned.txt`. hatchling replaces `setup.cfg` and `tox.ini`, `just` recipes (`just test`, `just lint`, `just docs`) replace the docs Makefile, and ruff lints and formats. See `CONTRIBUTING.md`.
- Documentation sources are Markdown (MyST).
- Supported Python versions are unchanged: 3.10 to 3.14.
- The integration tests run the examples of `pyglotaran-examples@staging_rewrite` and compare their results semantically (by labels and dimensions) with the pinned v0.7.4 gold standard, using the comparison and tolerances of the `validation` submodule (`cca4c5c`).

### Validation

- Unit tests: 566 passed, 9 xfailed with the review fixes (`staging_final_fixes` `3edaa514`). CI passes on Linux, macOS and Windows with Python 3.10 to 3.14, and so does the semantic comparison of the 11 integration examples with v0.7.4.
- Parity with v0.7.4 is tracked in [jsnel/0_8-pygta-validation-workspace](https://github.com/jsnel/0_8-pygta-validation-workspace). Rerun `20261005-023524` (with the review fixes): 11/11 example notebooks per version, and the 14 result leaves give 9 PASS and 5 EXPECTED_DIFFERENCE, with no regressions. Fitted data agree with v0.7.4 to a normalized RMS of 8.8e-6 for the two-dataset transient absorption analysis, 1.3e-6 for spectral guidance and at most 6e-10 for the other 12 leaves. The expected differences are documented: a non-identifiable rate (`rates.k3d2`), optimizer-path sensitivity of the guided spectral fit, and parameter and decomposition differences in three simulated multi-dataset examples whose fitted data pass. Matrices of datasets with a scale differ from v0.7.4 by that scale: v0.7.4 reports the matrix multiplied by the dataset scale, 0.8 the unscaled matrix.
- Case studies (staging `879c5bce`, 2026-09-13, before #1609 and #1615 were merged): 6 studies, 40 fits. 32 fits agree within the 1e-6 normalized RMS threshold and 36 within 0.1% of the v0.7.4 fitted data. The other 4 were stopped by their evaluation budget on both versions before converging.

### Not in this PR

Before the 0.8.0 release:

- Release pyglotaran-extras from its `staging_support` branch, which reads 0.8 results. Until then the `extras` extra (`pyglotaran-extras>=0.5`) installs v0.7.4, which reads only the 0.7 format.
- User documentation, written on `main`: the modelling, optimizing, overview, parameter, data IO and plotting pages contain only a heading, there is no migration guide for v0.7 model files, and kinetic normalization needs an example (coherent-artifact and oscillation compartments in an activation count in the normalization unless they are in `not_normalized_compartments`).

Open follow-ups:

- #1611: findings deferred from #1609 (PFID rate validation, Gaussian dispersion reporting with shifts, equal-area penalty edge cases).
- Rerun the 4 budget-truncated case-study fits with a budget that lets both versions converge.
- The PFID case study takes 1.9 times the v0.7.4 fit time and more peak memory (2026-09-13). Runtime has not been compared with identical dependency versions.

### For reviewers

- Greptile's six findings on this PR are fixed on staging by #XXXX (`staging_final_fixes`).
- The integration tests follow the pyglotaran-examples branch `staging_rewrite`; they are pinned to a commit of it at the end of this review.
- CodeRabbit skipped the review because of the file count. The diff is easier to read by package: `glotaran/model/` and `glotaran/project/scheme.py` (specification), `glotaran/builtin/elements/` and `glotaran/builtin/items/activation/` (elements), `glotaran/optimization/`, then `glotaran/project/` (results and projects). The getting started notebook shows the user workflow.
- The detailed descriptions are in the staging PRs, mainly #1562 (rewrite and result API), #1609 (main features ported to staging) and #1615 (Project API).

<!-- This PR description was co-authored by Opus 5.5 -->
