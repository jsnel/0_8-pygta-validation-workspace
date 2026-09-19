from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest
from pygta_local_extras.io.tabular import load_dataset_from_csv


@pytest.fixture
def write_csv(tmp_path: Path):
    def _write_csv(name: str, content: str) -> Path:
        file_path = tmp_path / name
        file_path.write_text(content, encoding="utf-8")
        return file_path

    return _write_csv


def test_load_dataset_from_wavelength_explicit_csv(write_csv) -> None:
    csv_path = write_csv(
        "wavelength_explicit.csv",
        ",500,600\n0,,\n1,1,\n2,3,4\n",
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        dataset = load_dataset_from_csv(csv_path, ordering="wavelength_explicit")

    np.testing.assert_allclose(dataset.coords["time"].values, [1.0, 2.0])
    np.testing.assert_allclose(dataset.coords["spectral"].values, [500.0, 600.0])
    np.testing.assert_allclose(dataset["data"].values, [[1.0, 0.0], [3.0, 4.0]])
    assert len(captured) == 2


def test_load_dataset_from_time_explicit_csv(write_csv) -> None:
    csv_path = write_csv(
        "time_explicit.csv",
        ",500,600\n0,,\n550,1,2\n600,3,4\n",
    )

    dataset = load_dataset_from_csv(csv_path, ordering="time_explicit", silence_warnings=True)

    np.testing.assert_allclose(dataset.coords["time"].values, [500.0, 600.0])
    np.testing.assert_allclose(dataset.coords["spectral"].values, [550.0, 600.0])
    np.testing.assert_allclose(dataset["data"].values, [[1.0, 3.0], [2.0, 4.0]])


def test_invalid_ordering_raises_value_error(write_csv) -> None:
    csv_path = write_csv("invalid.csv", ",500\n1,2\n")

    with pytest.raises(ValueError):
        load_dataset_from_csv(csv_path, ordering="bad_ordering")
