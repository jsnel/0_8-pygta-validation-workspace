"""Translation keeps scale_list science in the native v0.8 scheme."""

from pathlib import Path

import pytest

from validation.case_studies.migrate import convert_model


def source_model():
    return {
        "megacomplex": {
            "kinetic": {"type": "decay", "k_matrix": ["rates"]},
            "spectral": {"type": "spectral", "shape": {"s1": "shape"}},
        },
        "k_matrix": {"rates": {"matrix": {"(s1, s1)": "k"}}},
        "shape": {"shape": {"type": "gaussian", "amplitude": 1, "location": 500, "width": 20}},
        "dataset": {"data": {
            "megacomplex": ["kinetic"], "global_megacomplex": ["spectral"],
            "global_megacomplex_scale": ["global_scale"],
            "single_amplitude_model": True, "scale_list": ["scale.a", "scale.b"],
        }},
        "parameter_penalties": [{"type": "equal", "source": "k", "target": "other",
                                  "parameter": 2, "weight": 3}],
    }


def test_port_preserves_pairing_scales_and_global_penalties():
    original = source_model()
    converted, _ = convert_model(original, Path("source.yml"))
    dataset = converted["experiments"]["default"]["datasets"]["data"]
    assert dataset["global_composition"] == "paired"
    assert dataset["global_elements"] == ["spectral"]
    assert dataset["global_element_scale"] == {"spectral": "global_scale"}
    assert dataset["scale_list"] == ["scale.a", "scale.b"]
    assert converted["parameter_penalties"] == original["parameter_penalties"]
    assert "global_megacomplex" in original["dataset"]["data"]


def test_pairing_without_global_model_is_rejected():
    original = source_model()
    original["dataset"]["data"].pop("global_megacomplex")
    with pytest.raises(ValueError, match="requires global megacomplexes"):
        convert_model(original, Path("source.yml"))
