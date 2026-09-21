from __future__ import annotations

import numpy as np
import pytest
import xarray as xr
from pygta_local_extras.selection.ranges import slice_by_ranges
from pygta_local_extras.selection.ranges import slice_spectral_range
from pygta_local_extras.selection.ranges import slice_time_range


@pytest.fixture
def data() -> xr.DataArray:
    return xr.DataArray(
        np.arange(12, dtype=float).reshape(4, 3),
        dims=["time", "spectral"],
        coords={
            "time": [-1.0, 0.0, 1.0, 2.0],
            "spectral": [500.0, 550.0, 600.0],
        },
    )


def test_slice_time_range_supports_open_ended_ranges(data: xr.DataArray) -> None:
    result = slice_time_range(data, (0.0, None))

    np.testing.assert_allclose(result.coords["time"].values, [0.0, 1.0, 2.0])


def test_slice_spectral_range_can_exclude_band(data: xr.DataArray) -> None:
    result = slice_spectral_range(data, (500.0, 600.0), (540.0, 560.0))

    np.testing.assert_allclose(result.coords["spectral"].values, [500.0, 600.0])


def test_slice_by_ranges_works_for_dataset_inputs(data: xr.DataArray) -> None:
    dataset = data.to_dataset(name="data")
    result = slice_by_ranges(dataset, (-1.0, 1.0), (550.0, None))

    np.testing.assert_allclose(result.coords["time"].values, [-1.0, 0.0, 1.0])
    np.testing.assert_allclose(result.coords["spectral"].values, [550.0, 600.0])
