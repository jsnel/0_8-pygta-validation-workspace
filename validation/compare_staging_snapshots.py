"""Strict recursive comparison of trusted local continuation probe snapshots.

Checks all reconstructed result fields, coordinates and metadata, parameters,
and optimizer information. Timing-bearing optimizer transcript is reported
separately; it cannot establish scientific equality.
"""
import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


class HistoryState:
    """Plain state for history wrappers whose __getattr__ prevents unpickling."""


class SnapshotUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) == ('glotaran.optimization.optimization_history', 'OptimizationHistory'):
            # This wrapper delegates __getstate__ to its underlying DataFrame.
            # Restore that state as a DataFrame, including its axes and metadata.
            return pd.DataFrame
        if (module, name) in {
            ('glotaran.parameter.parameter_history', 'ParameterHistory'),
        }:
            return HistoryState
        return super().find_class(module, name)


def read_snapshot(path):
    with Path(path).open('rb') as stream:
        return SnapshotUnpickler(stream).load()


def compare(left, right, path, differences):
    try:
        if isinstance(left, (xr.Dataset, xr.DataArray)):
            xr.testing.assert_identical(left, right)
        elif isinstance(left, pd.DataFrame):
            pd.testing.assert_frame_equal(left, right, check_exact=True)
        elif isinstance(left, np.ndarray):
            np.testing.assert_array_equal(left, right)
        elif isinstance(left, dict):
            assert left.keys() == right.keys(), 'dictionary keys differ'
            for key in left:
                compare(left[key], right[key], f'{path}/{key}', differences)
        elif isinstance(left, (tuple, list)):
            assert len(left) == len(right), 'length differs'
            for i, (a,b) in enumerate(zip(left, right)):
                compare(a, b, f'{path}/{i}', differences)
        elif hasattr(left, 'model_dump'):
            compare(left.model_dump(), right.model_dump(), path, differences)
        elif isinstance(left, HistoryState):
            compare(vars(left), vars(right), path, differences)
        elif isinstance(left, float) and np.isnan(left):
            assert np.isnan(right)
        else:
            assert left == right, 'values differ'
    except (AssertionError, ValueError, TypeError) as error:
        differences.append(dict(path=path, error=str(error)[:1500]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('optimized', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.baseline.glob('result-*.pkl'))
    assert files and {p.name for p in files} == {p.name for p in args.optimized.glob('result-*.pkl')}
    records = []
    for file in files:
        left = read_snapshot(file)
        right = read_snapshot(args.optimized / file.name)
        differences = []
        compare(left, right, file.name, differences)
        records.append(dict(file=file.name, exact=not differences, differences=differences))
    args.output.write_text(json.dumps(records, indent=2))
    print(json.dumps(records, indent=2))
    return int(any(not r['exact'] for r in records))


if __name__ == '__main__':
    raise SystemExit(main())
