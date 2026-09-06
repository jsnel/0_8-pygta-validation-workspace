"""Exercise coordinate-label gathering with changing linked matrix layouts."""
from types import SimpleNamespace

import numpy as np
import pytest
import xarray as xr


@pytest.mark.parametrize('coordinate', [False, True])
def test_amplitude_gather_reordered_linked_axes(coordinate):
    from glotaran.optimization.data import LinkedOptimizationData
    from glotaran.optimization.estimation import OptimizationEstimation
    from glotaran.optimization.objective import OptimizationObjective

    labels = np.array(['b', 'a'])
    axis = xr.DataArray(labels, dims='amplitude_label') if coordinate else labels
    axes = [['a', 'b'], ['unused', 'b', 'a'], ['b', 'a']]
    estimates = [OptimizationEstimation(np.array(v), np.zeros(1))
                 for v in ([10, 20], [999, 30, 40], [50, 60])]
    stub = SimpleNamespace(_data=object.__new__(LinkedOptimizationData),
                           get_global_indices=lambda label: [2, 0, 1])
    actual = OptimizationObjective.get_dataset_amplitudes(
        stub, 'dataset', axes, estimates, axis, 'spectral', np.array([500, 510, 520]))
    expected = xr.DataArray([[50, 60], [20, 10], [30, 40]],
                            dims=('spectral', 'amplitude_label'),
                            coords={'spectral': [500, 510, 520], 'amplitude_label': labels})
    xr.testing.assert_identical(actual, expected)
    # Repeated independent reconstruction must use current labels and estimates.
    estimates[0].clp[1] = 123
    again = OptimizationObjective.get_dataset_amplitudes(
        stub, 'dataset', axes, estimates, axis, 'spectral', np.array([500, 510, 520]))
    assert again.values[1, 0] == 123
    assert actual.values[1, 0] == 20
