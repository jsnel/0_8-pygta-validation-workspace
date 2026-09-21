"""Guard completeness of native result snapshot comparisons."""
import pandas as pd
import xarray as xr

from validation.compare_staging_snapshots import HistoryState, compare


def test_snapshot_comparison_detects_metadata_and_coordinate_changes():
    left = xr.DataArray([1., 2.], dims='time', coords={'time': [0., 1.]}, attrs={'scale': 1.})
    right = left.copy(deep=True)
    right.attrs['scale'] = 2.
    differences = []
    compare({'result': left}, {'result': right}, '', differences)
    assert differences and differences[0]['path'] == '/result'
    right = left.assign_coords(time=[0., 2.])
    differences = []
    compare(left, right, 'result', differences)
    assert differences


def test_snapshot_comparison_checks_history_content_and_missing_fields():
    left, right = HistoryState(), HistoryState()
    left._df = pd.DataFrame({'cost': [3., 2.]})
    right._df = left._df.copy()
    differences = []
    compare(left, right, 'history', differences)
    assert not differences
    right._df.loc[1, 'cost'] = 1.
    compare(left, right, 'history', differences)
    assert differences
    differences = []
    compare({'residual': 0., 'fit': 1.}, {'fit': 1.}, 'result', differences)
    assert differences


def test_snapshot_optimization_history_roundtrip():
    import io
    import pickle

    from glotaran.optimization.optimization_history import OptimizationHistory
    from validation.compare_staging_snapshots import SnapshotUnpickler

    history = OptimizationHistory([{'iteration': 0, 'nfev': 1, 'cost': 3.},
                                   {'iteration': 1, 'nfev': 2, 'cost': 2.}])
    loaded = SnapshotUnpickler(io.BytesIO(pickle.dumps(history))).load()
    pd.testing.assert_frame_equal(history.data, loaded, check_exact=True)
