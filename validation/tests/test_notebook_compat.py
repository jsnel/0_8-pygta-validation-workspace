from pathlib import Path
from types import SimpleNamespace

import nbformat
import pytest
import xarray as xr

from pyglotaran_compat import DataStore, convert_result, simulate
from validation.case_studies.consolidate import consolidate


def test_store_loads_paths_and_protects_existing_names(tmp_path: Path):
    path = tmp_path / "data.nc"
    data = xr.Dataset({"data": ("time", [1.0, 2.0])})
    data.to_netcdf(path)
    store = DataStore()
    store.import_data(path, "sample")
    xr.testing.assert_equal(store.load_data("sample"), data)
    with pytest.raises(ValueError, match="already exists"):
        store.import_data(data, "sample")
    store.import_data(data, "sample", allow_overwrite=True)
    assert store.load_data("sample") is data


def test_simulation_dispatch_preserves_arguments(monkeypatch):
    calls = []
    monkeypatch.setattr("glotaran.simulation.simulate", lambda *a, **k: calls.append((a, k)))
    model = object()
    parameters, coordinates = object(), {"time": [0, 1]}
    simulate(model, "sample", parameters, coordinates, noise_seed=42)
    assert calls[-1] == ((model, "sample", parameters, coordinates), {"noise_seed": 42})
    scheme = SimpleNamespace(experiments={"e": SimpleNamespace(datasets={"sample": model})}, library={})
    simulate(scheme, "sample", parameters, coordinates, noise_seed=42)
    assert calls[-1] == ((model, scheme.library, parameters, coordinates), {"noise_seed": 42})


def test_legacy_result_passes_through():
    result = SimpleNamespace(data={})
    assert convert_result(result, None) is result


def test_conversion_preserves_fit_and_reconstructs_overlapping_weights(monkeypatch):
    values = xr.DataArray([[10.0, 20.0], [30.0, 40.0]], dims=("time", "spectral"),
                          coords={"time": [0.0, 1.0], "spectral": [400.0, 500.0]})
    residual = xr.ones_like(values)
    amplitudes = xr.DataArray([[1.0], [2.0]], dims=("spectral", "amplitude_label"),
                              coords={"spectral": [400.0, 500.0], "amplitude_label": ["a"]})
    native = SimpleNamespace(optimization_results={"sample": SimpleNamespace(
        input_data=values, residuals=residual, elements={},
        meta=SimpleNamespace(global_dimension="spectral", model_dimension="time", scale=2.0),
        fit_decomposition=SimpleNamespace(clp=amplitudes, matrix=amplitudes),
    )})
    view = SimpleNamespace(data={"sample": values.to_dataset(name="data")})
    monkeypatch.setattr("pyglotaran_extras.compat.convert", lambda result: view)
    weights = [SimpleNamespace(global_interval=(400, 500), model_interval=None, value=2),
               SimpleNamespace(global_interval=None, model_interval=(1, 1), value=3)]
    scheme = SimpleNamespace(experiments={"e": SimpleNamespace(
        datasets={"sample": SimpleNamespace(weights=weights)})})
    converted = convert_result(native, scheme).data["sample"]
    xr.testing.assert_equal(converted.fitted_data, (values - residual).rename("fitted_data"))
    assert converted.weight.values.tolist() == [[2.0, 2.0], [6.0, 6.0]]
    assert converted.weighted_residual.values.tolist() == [[2.0, 2.0], [6.0, 6.0]]
    assert converted.clp_label.values.tolist() == ["a"]
    assert converted.attrs["dataset_scale"] == 2.0
    xr.testing.assert_identical(native.optimization_results["sample"].input_data, values)


def test_consolidation_preserves_analysis_and_is_idempotent(tmp_path: Path):
    path = tmp_path / "example_v08.ipynb"
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(
        "def _case_study_simulate(*args):\n    pass\n\nanswer = 42\n"
    )]), path)
    assert consolidate(path)
    source = nbformat.read(path, as_version=4).cells[0].source
    assert "from pyglotaran_compat import" in source
    assert "answer = 42" in source
    assert "def _case_study" not in source
    assert not consolidate(path)
