"""Tests for transform_width_parameters helper function."""

from __future__ import annotations

import math

import numpy as np
import pytest

try:
    from pygta_local_extras.io import transform_width_parameters  # noqa: F401
except ImportError:
    pytest.skip("glotaran or related dependencies not available", allow_module_level=True)


class FakeParameter:
    """Fake parameter object for testing."""

    def __init__(self, value: float, minimum: float | None = None, maximum: float | None = None):
        self.value = value
        self.minimum = minimum
        self.maximum = maximum


class FakeParameterGroup:
    """Fake parameter group for testing."""

    def __init__(self, params: dict[str, FakeParameter]):
        self._params = params
        self.labels = list(params.keys())

    def __getitem__(self, key: str) -> FakeParameter:
        return self._params[key]


class FakeIrf:
    """Fake IRF object for testing."""

    def __init__(self, irf_type: str, convwidth: list, width: list):
        self.type = irf_type
        self.convwidth = convwidth
        self.width = width


class FakeModel:
    """Fake model object for testing."""

    def __init__(self, irfs: dict[str, FakeIrf]):
        self.irf = irfs


def test_transform_width_parameters_basic_shift():
    """Test basic width-to-convwidth transformation."""
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    # Create test parameters: convwidth=3, width=4
    # Effective width: sqrt(3^2 + 4^2) = 5
    # After mass=1: convwidth=4, width=sqrt(5^2 - 4^2) = sqrt(9) = 3
    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(3.0),
            "width": FakeParameter(4.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=["width"],
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)
    transformed = _transform_width_values(irf_config, params, mass=1.0)

    assert math.isclose(transformed["convwidth"], 4.0, abs_tol=1e-10)
    assert math.isclose(transformed["width"], 3.0, abs_tol=1e-10)

    # Verify effective width unchanged
    old_cwidth_eff = np.sqrt(3.0**2 + 4.0**2)
    new_cwidth_eff = np.sqrt(transformed["convwidth"] ** 2 + transformed["width"] ** 2)
    assert math.isclose(old_cwidth_eff, new_cwidth_eff, abs_tol=1e-10)


def test_transform_width_parameters_no_change():
    """Test transformation with mass=0 (no change)."""
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(3.0),
            "width": FakeParameter(4.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=["width"],
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)
    transformed = _transform_width_values(irf_config, params, mass=0.0)

    assert math.isclose(transformed["convwidth"], 3.0, abs_tol=1e-10)
    assert math.isclose(transformed["width"], 4.0, abs_tol=1e-10)


def test_transform_width_parameters_negative_mass():
    """Test transformation with negative mass (reverse shift)."""
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(4.0),
            "width": FakeParameter(3.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=["width"],
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)
    transformed = _transform_width_values(irf_config, params, mass=-1.0)

    assert math.isclose(transformed["convwidth"], 3.0, abs_tol=1e-10)
    assert math.isclose(transformed["width"], 4.0, abs_tol=1e-10)


def test_transform_width_parameters_multiple_widths():
    """Test transformation with multiple width parameters within a single IRF.

    For each IRF independently, all Gaussian width components receive the same
    Δw² shift, determined by that IRF's minimum convwidth:

        delta_w_sq = -(2 * minconvwidth * mass + mass**2)
        new_width_j = sqrt(width_j**2 + delta_w_sq)
        new_convwidth_i = sqrt(convwidth_i**2 - delta_w_sq)

    This is equivalent to the per-component formula when there is only one
    convwidth, so the expected values are the same as before.
    """
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    # Create widths with larger values to support mass=1.0 shift
    # width1=6 -> eff1 = sqrt(3^2 + 6^2) = sqrt(45) ≈ 6.708
    # width2=5 -> eff2 = sqrt(3^2 + 5^2) = sqrt(34) ≈ 5.831
    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(3.0),
            "width1": FakeParameter(6.0),
            "width2": FakeParameter(5.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=["width1", "width2"],
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)
    transformed = _transform_width_values(irf_config, params, mass=1.0)

    # All convwidths get the same shift
    assert math.isclose(transformed["convwidth"], 4.0, abs_tol=1e-10)

    # For width1: sqrt(45 - 16) ≈ sqrt(29) ≈ 5.385
    expected_width1 = np.sqrt(45.0 - 16.0)
    assert math.isclose(transformed["width1"], expected_width1, abs_tol=1e-10)

    # For width2: sqrt(34 - 16) = sqrt(18) ≈ 4.243
    expected_width2 = np.sqrt(34.0 - 16.0)
    assert math.isclose(transformed["width2"], expected_width2, abs_tol=1e-10)


def test_transform_width_parameters_nested_width_parameters():
    """Test transformation with nested width parameters."""
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _flatten_nested_params
    from pygta_local_extras.io.params_csv import _transform_width_values

    # Use larger widths to support mass=1.0 shift
    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(3.0),
            "width1": FakeParameter(6.0),
            "width2": FakeParameter(5.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=[["width1", "width2"]],  # Nested list
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)

    # Test flattening
    width_list = _flatten_nested_params(irf_config["test_irf"]["width"])
    assert width_list == ["width1", "width2"]

    transformed = _transform_width_values(irf_config, params, mass=1.0)

    assert math.isclose(transformed["convwidth"], 4.0, abs_tol=1e-10)
    # For width1: sqrt(45 - 16) ≈ sqrt(29) ≈ 5.385
    expected_width1 = np.sqrt(45.0 - 16.0)
    assert math.isclose(transformed["width1"], expected_width1, abs_tol=1e-10)
    # For width2: sqrt(34 - 16) = sqrt(18) ≈ 4.243
    expected_width2 = np.sqrt(34.0 - 16.0)
    assert math.isclose(transformed["width2"], expected_width2, abs_tol=1e-10)


def test_apply_transformed_values_updates_parameter_object_in_place():
    """Transformed values should be materialized on returned parameter object."""
    from pygta_local_extras.io.params_csv import _apply_transformed_values

    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(3.0),
            "width": FakeParameter(4.0),
        }
    )

    transformed = {
        "convwidth": 4.0,
        "width": 3.0,
    }

    updated = _apply_transformed_values(params, transformed)

    assert updated is params
    assert math.isclose(params["convwidth"].value, 4.0, abs_tol=1e-12)
    assert math.isclose(params["width"].value, 3.0, abs_tol=1e-12)


def test_transform_width_parameters_mass_too_large():
    """Test error when mass would result in negative width for an IRF.

    With the per-IRF algorithm, when mass is too large for a specific IRF's
    minconvwidth, that entire IRF (all its convwidth AND width params) is skipped
    and a UserWarning is issued. Neither the convwidth nor width parameters
    should appear in the result dict.
    """
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(3.0),
            "width": FakeParameter(4.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=["width"],
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)

    # Effective width at minconvwidth is sqrt(3^2 + 4^2) = 5,
    # so max_allowed_mass = 5 - 3 = 2.
    # mass=3 exceeds this limit -> the entire IRF is skipped.
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = _transform_width_values(irf_config, params, mass=3.0)

        # A UserWarning must have been issued
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "could not be transformed" in str(w[0].message).lower()

        # Both convwidth AND width are absent: the whole IRF was skipped
        assert "convwidth" not in result
        assert "width" not in result


def test_transform_width_parameters_edge_case_zero_width():
    """Test transformation resulting in zero width."""
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(3.0),
            "width": FakeParameter(4.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=["width"],
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)

    # Effective width is 5, mass=2 gives convwidth=5, width=0
    transformed = _transform_width_values(irf_config, params, mass=2.0)

    assert math.isclose(transformed["convwidth"], 5.0, abs_tol=1e-10)
    assert math.isclose(transformed["width"], 0.0, abs_tol=1e-10)


def test_transform_width_parameters_skips_near_zero_convwidth_stability():
    """Skip an IRF when mass is too large relative to min convwidth."""
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(0.02),
            "width": FakeParameter(4.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=["width"],
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)

    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = _transform_width_values(irf_config, params, mass=1.0)

        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "could not be transformed" in str(w[0].message).lower()
        assert "exceeds limit" in str(w[0].message).lower()
        assert "convwidth" not in result
        assert "width" not in result


def test_transform_width_parameters_quadrature_invariant():
    """Test that quadrature relationship is preserved."""
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    test_cases = [
        (1.0, 4.0, 0.5),  # convwidth, width, mass
        (2.0, 3.0, 0.2),  # smaller mass
        (5.0, 4.0, 0.5),  # larger mass for larger effective width
        (3.0, 6.0, 1.0),  # larger widths support bigger mass
    ]

    for convwidth, width, mass in test_cases:
        params = FakeParameterGroup(
            {
                "convwidth": FakeParameter(convwidth),
                "width": FakeParameter(width),
            }
        )

        model = FakeModel(
            {
                "test_irf": FakeIrf(
                    "conv-multi-multi-gaussian",
                    convwidth=["convwidth"],
                    width=["width"],
                )
            }
        )

        irf_config = _find_conv_multi_multi_gaussian_irfs(model)
        original_eff = np.sqrt(convwidth**2 + width**2)

        transformed = _transform_width_values(irf_config, params, mass=mass)

        new_eff = np.sqrt(transformed["convwidth"] ** 2 + transformed["width"] ** 2)

        assert math.isclose(original_eff, new_eff, abs_tol=1e-10), (
            f"Quadrature invariant violated for ({convwidth}, {width}, {mass}): "
            f"original={original_eff}, new={new_eff}"
        )


def test_transform_width_parameters_export_available():
    """Test that transform_width_parameters is exported from io module."""
    from pygta_local_extras import io

    assert hasattr(io, "transform_width_parameters")
    assert callable(io.transform_width_parameters)


def test_transform_width_parameters_stability_guard_parameter():
    """Test that apply_stability_guard parameter controls stability behavior."""
    from pygta_local_extras.io.params_csv import _find_conv_multi_multi_gaussian_irfs
    from pygta_local_extras.io.params_csv import _transform_width_values

    # Create test parameters with small convwidth (0.02)
    params = FakeParameterGroup(
        {
            "convwidth": FakeParameter(0.02),
            "width": FakeParameter(4.0),
        }
    )

    model = FakeModel(
        {
            "test_irf": FakeIrf(
                "conv-multi-multi-gaussian",
                convwidth=["convwidth"],
                width=["width"],
            )
        }
    )

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)

    import warnings

    # Test 1: With default max_mass_to_minconvwidth_ratio=None, should succeed
    result = _transform_width_values(
        irf_config, params, mass=1.0, max_mass_to_minconvwidth_ratio=None
    )
    assert "convwidth" in result
    assert "width" in result
    assert len(result) > 0

    # Test 2: With max_mass_to_minconvwidth_ratio=1.0, should skip due to high ratio
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = _transform_width_values(
            irf_config, params, mass=1.0, max_mass_to_minconvwidth_ratio=1.0
        )
        # Check that warning was raised
        assert len(w) >= 1
        # Parameters should be skipped (result is empty)
        assert len(result) == 0
        # Check that the warning message indicates IRF was skipped
        assert any("could not be transformed" in str(warning.message).lower() for warning in w)
