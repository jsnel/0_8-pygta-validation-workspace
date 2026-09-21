from __future__ import annotations

from typing import TypeAlias
from typing import TypeVar

import numpy as np
import xarray as xr

RangeBound: TypeAlias = float | int | None
NumericRange: TypeAlias = tuple[RangeBound, RangeBound]
XarrayLike = TypeVar("XarrayLike", xr.DataArray, xr.Dataset)


def slice_time_range(data: XarrayLike, time_range: NumericRange | None = None) -> XarrayLike:
    """Slice an xarray object along the time dimension."""
    if time_range is None:
        return data

    start_time, end_time = _resolve_range(data, "time", time_range)
    return data.sel(time=slice(start_time, end_time))


slice_data_by_time_range = slice_time_range


def slice_spectral_range(
    data: XarrayLike,
    spectral_range: NumericRange | None = None,
    exclude_spectral_range: NumericRange | None = None,
) -> XarrayLike:
    """Slice an xarray object along the spectral dimension."""
    result = data

    if spectral_range is not None:
        start_wavelength, end_wavelength = _resolve_range(data, "spectral", spectral_range)
        spectral_coord = result.coords["spectral"]
        result = result.sel(
            spectral=(spectral_coord >= start_wavelength) & (spectral_coord <= end_wavelength)
        )

    if exclude_spectral_range is not None:
        exclude_start, exclude_end = _resolve_range(result, "spectral", exclude_spectral_range)
        spectral_coord = result.coords["spectral"]
        result = result.sel(
            spectral=(spectral_coord < exclude_start) | (spectral_coord > exclude_end)
        )

    return result


slice_data_by_spectral_range = slice_spectral_range


def slice_by_ranges(
    data: XarrayLike,
    time_range: NumericRange | None = None,
    spectral_range: NumericRange | None = None,
    exclude_spectral_range: NumericRange | None = None,
) -> XarrayLike:
    """Apply time and spectral slicing in one step."""
    result = slice_time_range(data, time_range)
    return slice_spectral_range(result, spectral_range, exclude_spectral_range)


def _resolve_range(
    data: XarrayLike, coordinate_name: str, value_range: NumericRange
) -> tuple[float, float]:
    coordinate_values = np.asarray(data.coords[coordinate_name].values, dtype=float)
    start_value, end_value = value_range

    if start_value is None:
        start_value = float(coordinate_values.min())
    if end_value is None:
        end_value = float(coordinate_values.max())

    return float(start_value), float(end_value)
