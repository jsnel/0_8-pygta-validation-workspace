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


@pytest.mark.parametrize("irf_type", ["multi-multi-gaussian", "conv-multi-multi-gaussian", "norm-conv-multi-multi-gaussian"])
def test_grouped_irf_translation_preserves_nested_parameter_references(irf_type: str):
    from glotaran.project.scheme import Scheme

    original = source_model()
    original["dataset"]["data"].update(initial_concentration="initial", irf="irf")
    original["initial_concentration"] = {"initial": {"compartments": ["s1"], "parameters": [1]}}
    irf = {"type": irf_type, "center": [["center", "offset"]], "width": [["width", "width"]],
           "scale": [[1, "relative_scale"]], "normalize_area": True, "normarea": 1000}
    if irf_type != "multi-multi-gaussian":
        irf["convwidth"] = ["broadening.a", "broadening.b"]
    original["irf"] = {"irf": irf}
    converted, _ = convert_model(original, Path("source.yml"))
    activation = converted["experiments"]["default"]["datasets"]["data"]["activations"]["irf"]
    assert activation["center"] == [["center", "offset"]]
    assert activation["scale"] == [[1, "relative_scale"]]
    assert activation["normarea"] == 1000
    assert Scheme.from_dict(converted).experiments["default"].datasets["data"].activations["irf"].type == irf_type


def guide_source_model():
    return {
        "dataset_groups": {
            "linked": {"residual_function": "non_negative_least_squares", "link_clp": True},
            "unused": {"link_clp": True},
        },
        "megacomplex": {
            "kinetic": {"type": "decay", "k_matrix": ["rates"]},
            "guide": {"type": "spectral-model-clp-guide", "target": "s1",
                      "shape": {"s1": "guide_shape"}},
        },
        "k_matrix": {"rates": {"matrix": {"(s1, s1)": "k"}}},
        "shape": {"guide_shape": {
            "type": "skewed-gaussian-sum", "amplitude": ["a.1", "a.2"],
            "location": ["l.1", "l.2"], "width": ["w.1", "w.2"], "skewness": ["s.1", "s.2"],
        }},
        "dataset": {
            "data": {"group": "linked", "megacomplex": ["kinetic"],
                     "initial_concentration": "input", "irf": "irf"},
            "guide_data": {"group": "linked", "megacomplex": ["guide"],
                           "spectral_axis_inverted": True, "spectral_axis_scale": 1e7,
                           "scale": "scale.guide"},
        },
        "initial_concentration": {"input": {"compartments": ["s1"], "parameters": ["i.1"]}},
        "irf": {"irf": {"type": "gaussian", "center": "irf.c", "width": "irf.w"}},
        "weights": [{"datasets": ["guide_data"], "value": 5e3}],
    }


def test_spectral_model_clp_guide_translation_inlines_target_shape():
    from glotaran.project.scheme import Scheme

    original = guide_source_model()
    converted, log = convert_model(original, Path("source.yml"), clp_link_tolerance=0.0)
    assert converted["library"]["guide"] == {
        "type": "spectral-model-clp-guide",
        "target": "s1",
        "shapes": {"s1": original["shape"]["guide_shape"]},
    }
    experiment = converted["experiments"]["linked"]
    assert experiment["scale"] == {"guide_data": "scale.guide"}
    assert experiment["datasets"]["guide_data"]["weights"] == [{"value": 5e3}]
    assert experiment["datasets"]["guide_data"]["spectral_axis_scale"] == 1e7
    # v0.7 ignores dataset groups without datasets; staging cannot optimize them.
    assert set(converted["experiments"]) == {"linked"}
    assert log["empty_dataset_groups"] == ["unused"]
    guide = Scheme.from_dict(converted).experiments["linked"].datasets["guide_data"]
    assert guide.spectral_axis_inverted is True


def test_spectral_model_clp_guide_without_target_shape_is_rejected():
    original = guide_source_model()
    original["megacomplex"]["guide"]["target"] = "s2"
    with pytest.raises(ValueError, match="has no shape for s2"):
        convert_model(original, Path("source.yml"))
