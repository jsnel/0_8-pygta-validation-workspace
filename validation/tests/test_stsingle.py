from __future__ import annotations

from pathlib import Path

import nbformat
import numpy as np
import pytest
import xarray as xr
import yaml

from validation.case_studies.prepare_stsingle import MODEL_NAME
from validation.case_studies.prepare_stsingle import NOTEBOOK_NAME
from validation.case_studies.prepare_stsingle import prepare
from validation.case_studies.prepare_stsingle import _translate_model
from validation.case_studies.prepare_stsingle import _rewrite_native_result_save
from validation.case_studies.audit_stsingle import reconstruct_fit
from validation.case_studies.audit_stsingle import residual_reorder_proof


def test_st_translation_preserves_separate_global_and_local_models(tmp_path: Path) -> None:
    root = tmp_path / "case"
    models = root / "models"
    models.mkdir(parents=True)
    source = models / "st.yml"
    destination = models / "st_v08.yml"
    source.write_text(
        yaml.safe_dump(
            {
                "default_megacomplex": "decay",
                "dataset_groups": {
                    "streak": {
                        "residual_function": "non_negative_least_squares",
                        "link_clp": True,
                    }
                },
                "dataset": {
                    "trace": {
                        "group": "streak",
                        "megacomplex": ["spectral"],
                        "megacomplex_scale": ["local.scale"],
                        "global_megacomplex": ["kinetic"],
                        "global_megacomplex_scale": ["global.scale"],
                        "initial_concentration": "input",
                        "irf": "irf",
                        "scale": "dataset.scale",
                        "spectral_axis_inverted": True,
                        "spectral_axis_scale": 1.0e7,
                    }
                },
                "megacomplex": {
                    "kinetic": {"type": "decay", "k_matrix": ["rates"]},
                    "spectral": {
                        "type": "spectral",
                        "shape": {"s1": "shape"},
                    },
                },
                "shape": {
                    "shape": {
                        "type": "skewed-gaussian",
                        "amplitude": "shape.amplitude",
                        "location": "shape.location",
                        "width": "shape.width",
                        "skewness": "shape.skewness",
                    }
                },
                "k_matrix": {"rates": {"matrix": {"(s1, s1)": "rate.1"}}},
                "initial_concentration": {
                    "input": {"compartments": ["s1"], "parameters": ["input.1"]}
                },
                "irf": {
                    "irf": {
                        "type": "gaussian",
                        "center": "irf.center",
                        "width": "irf.width",
                        "backsweep": True,
                        "backsweep_period": "irf.period",
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    _translate_model(source, destination)
    translated = yaml.safe_load(destination.read_text(encoding="utf-8"))
    dataset = translated["experiments"]["streak"]["datasets"]["trace"]

    assert dataset["elements"] == ["spectral"]
    assert dataset["element_scale"] == {"spectral": "local.scale"}
    assert dataset["global_elements"] == ["kinetic"]
    assert dataset["global_element_scale"] == {"kinetic": "global.scale"}
    assert dataset["spectral_axis_inverted"] is True
    assert dataset["spectral_axis_scale"] == 1.0e7
    assert dataset["activations"]["irf"]["backsweep"] == "irf.period"
    assert dataset["activations"]["irf"]["center"] == "irf.center"
    assert dataset["activations"]["irf"]["width"] == "irf.width"
    assert translated["experiments"]["streak"]["scale"] == {"trace": "dataset.scale"}
    assert translated["experiments"]["streak"]["residual_function"] == (
        "non_negative_least_squares"
    )
    assert dataset["residual_function"] == "non_negative_least_squares"


def test_st_save_rewrite_preserves_native_result_reference() -> None:
    rewritten = _rewrite_native_result_save(
        "result_native = captured_native\nresult.save('results/supplied')"
    )

    assert "result_native = captured_native" in rewritten
    assert "result_native = result" not in rewritten
    assert "result_native.save(_native_result_dir / 'result.yml')" in rewritten
    assert "mkdtemp" in rewritten


def test_st_audit_reconstructs_by_named_clp_dimensions() -> None:
    matrix = xr.DataArray(
        [[1.0, 2.0], [3.0, 4.0]],
        dims=("spectral", "clp_label"),
        coords={"spectral": [650.0, 651.0], "clp_label": ["s1", "s2"]},
    )
    global_matrix = xr.DataArray(
        [[5.0, 6.0], [7.0, 8.0]],
        dims=("time", "global_clp_label"),
        coords={"time": [1.0, 2.0], "global_clp_label": ["s1", "s2"]},
    )
    clp = xr.DataArray(
        np.eye(2),
        dims=("global_clp_label", "clp_label"),
        coords={"global_clp_label": ["s1", "s2"], "clp_label": ["s1", "s2"]},
    )

    fitted = reconstruct_fit(matrix, clp, global_matrix)
    assert fitted.dims == ("time", "spectral")
    assert fitted.values.tolist() == [[17.0, 39.0], [23.0, 53.0]]
    data = fitted + xr.DataArray(
        [[0.1, -0.2], [0.3, -0.4]], dims=fitted.dims, coords=fitted.coords
    )
    residual = data - fitted
    # Reproduce the reference bug: reshape the time-major flat vector directly
    # into spectral-major dimensions, instead of reshaping then transposing.
    stored = xr.DataArray(
        residual.values.reshape(data.sizes["spectral"], data.sizes["time"]),
        dims=("spectral", "time"),
        coords={"spectral": data.spectral, "time": data.time},
    )
    assert not np.allclose(stored.transpose("time", "spectral"), residual)
    proof = residual_reorder_proof(stored, data, fitted)
    assert proof["status"] == "pass"


def test_st_prepare_points_translated_notebook_at_generated_model(tmp_path: Path) -> None:
    reference_root = Path("temp/case-studies/testcaseSTsingle/reference")
    if not (reference_root / "models" / MODEL_NAME).is_file():
        pytest.skip("ST case-study inputs are not available in this checkout")
    if not (reference_root / NOTEBOOK_NAME).is_file():
        pytest.skip("ST reference notebook is not available in this checkout")

    staging_root = tmp_path / "staging"
    prepared = prepare(reference_root, staging_root)
    translated = nbformat.read(prepared["notebook"], as_version=4)
    code = "\n".join(cell.source for cell in translated.cells if cell.cell_type == "code")

    assert "load_scheme('models/20260915STsingle_State1_2_6comp_day1_Olli_v08.yml')" in code
    assert "load_model('models/20260915STsingle_State1_2_6comp_day1_Olli.yml')" not in code
    assert "maximum_number_function_evaluations=1" in code
