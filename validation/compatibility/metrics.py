"""Numerical metrics used by the semantic comparison contract."""

from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from .normalize import align_arrays


def compare_arrays(expected: xr.DataArray, current: xr.DataArray, *, rtol: float, atol: float) -> dict[str, Any]:
    expected, current, transformations = align_arrays(expected, current)
    record: dict[str, Any] = {
        "expected_dims": list(expected.dims),
        "current_dims": list(current.dims),
        "expected_shape": list(expected.shape),
        "current_shape": list(current.shape),
        "transformations": transformations,
    }
    if expected.dims != current.dims or expected.shape != current.shape:
        record["status"] = "structural_mismatch"
        return record
    expected_values = np.asarray(expected.values)
    current_values = np.asarray(current.values)
    if expected_values.dtype.kind in "OUS" or current_values.dtype.kind in "OUS":
        equal = bool(np.array_equal(expected_values, current_values))
        record.update({"status": "pass" if equal else "different", "exact": equal})
        return record
    difference = np.abs(expected_values - current_values)
    expected_scale = float(np.sqrt(np.nanmean(np.square(expected_values)))) if expected_values.size else 0.0
    diff_rms = float(np.sqrt(np.nanmean(np.square(difference)))) if difference.size else 0.0
    record.update(
        {
            "status": "pass"
            if bool(np.allclose(expected_values, current_values, rtol=rtol, atol=atol, equal_nan=True))
            else "different",
            "max_abs": float(np.nanmax(difference)) if difference.size else 0.0,
            "rmse": diff_rms,
            "expected_rms": expected_scale,
            "normalized_rms": diff_rms / max(expected_scale, np.finfo(float).eps),
        }
    )
    return record


def weighted_root_mean_square_error(residual: xr.DataArray, weight: xr.DataArray | None) -> float | None:
    """Calculate pyglotaran's weighted RMSE convention from unweighted residuals."""

    if weight is None:
        return None
    weighted = residual * weight
    return float(np.sqrt(np.nanmean(np.square(weighted.values))))
