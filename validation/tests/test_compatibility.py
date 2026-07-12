from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import yaml

from validation.compatibility.load_v07 import load_v07_result
from validation.compatibility.load_v08 import load_v08_result
from validation.compatibility.metrics import compare_arrays
from validation.compatibility.weights import reconstruct_weight


def _write_array(path: Path, array: xr.DataArray, name: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    array.to_dataset(name=name or array.name or "value").to_netcdf(path)


def _parameters(path: Path) -> None:
    pd.DataFrame({"label": ["p"], "value": [1.0]}).to_csv(path, index=False)


def test_loaders_project_monolithic_and_split_layouts_by_labels(tmp_path: Path) -> None:
    time = np.array([0.0, 1.0])
    spectral = np.array([400.0, 500.0])
    values = xr.DataArray(
        [[1.0, 2.0], [3.0, 4.0]],
        dims=("time", "spectral"),
        coords={"time": time, "spectral": spectral},
        name="data",
    )
    clp = xr.DataArray(
        [[1.0, 2.0], [3.0, 4.0]],
        dims=("spectral", "clp_label"),
        coords={"spectral": spectral, "clp_label": ["s1", "s2"]},
        name="clp",
    )
    main = tmp_path / "main"
    main.mkdir()
    _write_array(main / "dataset1.nc", values)
    _write_array(main / "dataset1.nc", values, "residual")
    dataset = xr.Dataset({"data": values, "residual": values, "fitted_data": values, "clp": clp, "matrix": clp})
    dataset.to_netcdf(main / "dataset1.nc")
    _parameters(main / "optimized_parameters.csv")
    (main / "scheme.yml").write_text("{}\n", encoding="utf-8")
    (main / "result.yml").write_text(
        yaml.safe_dump({"data": {"dataset1": "dataset1.nc"}, "optimized_parameters": "optimized_parameters.csv", "scheme": "scheme.yml"}),
        encoding="utf-8",
    )

    staging = tmp_path / "staging"
    dataset_root = staging / "optimization_results" / "dataset1"
    _write_array(dataset_root / "input_data.nc", values)
    _write_array(dataset_root / "residuals.nc", values, "residual")
    _write_array(dataset_root / "fitted_data.nc", values, "__xarray_dataarray_variable__")
    split_clp = clp.rename({"clp_label": "amplitude_label"}).transpose("amplitude_label", "spectral")
    _write_array(dataset_root / "fit_decomposition" / "clp.nc", split_clp, "__xarray_dataarray_variable__")
    _write_array(dataset_root / "fit_decomposition" / "matrix.nc", split_clp, "__xarray_dataarray_variable__")
    _parameters(staging / "optimized_parameters.csv")
    (staging / "scheme.yml").write_text("{}\n", encoding="utf-8")
    (staging / "result.yml").write_text(
        yaml.safe_dump(
            {
                "optimization_results": {
                    "dataset1": {
                        "input_data": "input_data.nc",
                        "residuals": "residuals.nc",
                        "fitted_data": "fitted_data.nc",
                        "fit_decomposition": {"clp": "clp.nc", "matrix": "matrix.nc"},
                        "meta": {},
                    }
                },
                "optimized_parameters": "optimized_parameters.csv",
                "scheme": "scheme.yml",
            }
        ),
        encoding="utf-8",
    )

    expected = load_v07_result(main, "fixture")
    current = load_v08_result(staging, "fixture")
    assert compare_arrays(expected.datasets["dataset1"].variables["data"], current.datasets["dataset1"].variables["data"], rtol=0, atol=0)["status"] == "pass"
    assert compare_arrays(expected.datasets["dataset1"].variables["clp"], current.datasets["dataset1"].variables["clp"], rtol=0, atol=0)["status"] == "pass"
    assert current.datasets["dataset1"].source_files["clp"].endswith("fit_decomposition\\clp.nc")


def test_weight_reconstruction_and_derived_weighted_rmse() -> None:
    residual = xr.DataArray(
        np.ones((2, 2)),
        dims=("time", "spectral"),
        coords={"time": [0, 1], "spectral": [100.0, 200.0]},
        name="residual",
        attrs={"model_dimension": "time", "global_dimension": "spectral"},
    )
    scheme = {
        "experiments": {
            "exp": {
                "datasets": {
                    "dataset1": {"weights": [{"global_interval": [100, 200], "value": 0.5}]}
                }
            }
        }
    }
    weight = reconstruct_weight(residual, scheme, "dataset1")
    assert weight is not None
    assert np.allclose(weight.values, 0.5)
    assert np.isclose(float(np.sqrt(np.mean((residual * weight).values**2))), 0.5)


def test_split_loader_reports_missing_fields(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    dataset_root = root / "optimization_results" / "dataset1"
    data = xr.DataArray(np.ones((2, 2)), dims=("time", "spectral"), name="data")
    _write_array(dataset_root / "input_data.nc", data)
    _parameters(root / "optimized_parameters.csv")
    (root / "result.yml").write_text(
        yaml.safe_dump(
            {
                "optimization_results": {"dataset1": {"input_data": "input_data.nc", "residuals": None}},
                "optimized_parameters": "optimized_parameters.csv",
            }
        ),
        encoding="utf-8",
    )
    view = load_v08_result(root, "missing")
    assert "missing:residuals" in view.datasets["dataset1"].unmapped_fields


def test_staging_translation_and_save_regressions_are_present() -> None:
    workspace = Path(__file__).parents[2]
    model = yaml.safe_load(
        (workspace / "temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/study_transient_absorption/models/scheme.yml").read_text(
            encoding="utf-8"
        )
    )
    weights = model["experiments"]["my_exp"]["datasets"]["dataset1"]["weights"]
    assert [rule["value"] for rule in weights] == [0.1, 0.1]
    notebook = json.loads(
        (workspace / "temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/study_transient_absorption/transient_absorption_target_analysis.ipynb").read_text(
            encoding="utf-8"
        )
    )
    target_sources = [line for cell in notebook["cells"] for line in cell.get("source", [])]
    assert "    maximum_number_function_evaluations=10,\n" in target_sources
    doas = json.loads(
        (workspace / "temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/ex_doas_beta/ex_doas_beta.ipynb").read_text(
            encoding="utf-8"
        )
    )
    doas_sources = [line for cell in doas["cells"] for line in cell.get("source", [])]
    assert 'result.save(results_folder, allow_overwrite=True)' in doas_sources
    constraints = json.loads(
        (workspace / "temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/ex_spectral_constraints/ex_spectral_constraints.ipynb").read_text(
            encoding="utf-8"
        )
    )
    constraint_sources = [line for cell in constraints["cells"] for line in cell.get("source", [])]
    assert any("no_penalties_first_run" in line and ".save(" in line for line in constraint_sources)
    assert any("no_penalties\"" in line and ".save(" in line for line in constraint_sources)
    assert any("with_penalties_first_run" in line and ".save(" in line for line in constraint_sources)
    assert any("with_penalties\"" in line and ".save(" in line for line in constraint_sources)
    guidance = json.loads(
        (workspace / "temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/ex_spectral_guidance/ex_spectral_guidance.ipynb").read_text(
            encoding="utf-8"
        )
    )
    guidance_sources = [line for cell in guidance["cells"] for line in cell.get("source", [])]
    assert "    parameters=parameters, datasets=experiment_data, maximum_number_function_evaluations=21\n" in guidance_sources
    two_datasets = json.loads(
        (workspace / "temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples/ex_two_datasets/ex_two_datasets.ipynb").read_text(
            encoding="utf-8"
        )
    )
    two_dataset_sources = [line for cell in two_datasets["cells"] for line in cell.get("source", [])]
    assert "    parameters, datasets=experiment_data, maximum_number_function_evaluations=17\n" in two_dataset_sources
