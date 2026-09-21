from __future__ import annotations

import numpy as np
from pygta_local_extras.io import apply_factor
from pygta_local_extras.io import csv_to_dataset_weight_coarsen_poisson


def test_csv_to_dataset_weight_coarsen_poisson_builds_weights_from_counts(tmp_path) -> None:
    csv_text = "\n".join(
        [
            "factor,2,4",
            "wavelength,500,600",
            "0,10,20",
            "1,20,40",
            "2,30,60",
            "3,40,80",
            "4,50,100",
        ]
    )
    filepath = tmp_path / "counts.csv"
    filepath.write_text(csv_text)

    dataset = csv_to_dataset_weight_coarsen_poisson(
        filepath,
        time_start=None,
        time_end=None,
        logtimestart=2000.0,
        number_of_log_time_points=5,
        minimum_counts=5.0,
    )

    np.testing.assert_array_equal(dataset.time.values, np.array([0.0, 1000.0, 3000.0]))
    normalized_factors = np.array([2.0, 4.0]) / np.sqrt(20.0)
    np.testing.assert_allclose(dataset.factor.values, normalized_factors)

    expected_data = (
        np.array(
            [
                [50.0, 100.0],
                [40.0, 80.0],
                [20.0, 40.0],
            ]
        )
        * normalized_factors[np.newaxis, :]
    )
    np.testing.assert_allclose(dataset.data.values, expected_data)

    expected_weight = (
        np.array(
            [
                [1.0 / np.sqrt(50.0), 1.0 / np.sqrt(100.0)],
                [1.0 / np.sqrt(40.0), 1.0 / np.sqrt(80.0)],
                [1.0 / np.sqrt(60.0) / 3.0, 1.0 / np.sqrt(120.0) / 3.0],
            ]
        )
        / normalized_factors[np.newaxis, :]
    )
    np.testing.assert_allclose(dataset.weight.values, expected_weight)


def test_apply_factor_scales_data_and_weight_with_normalized_factors(tmp_path) -> None:
    csv_text = "\n".join(
        [
            "factor,2,4",
            "wavelength,500,600",
            "0,10,20",
            "1,20,40",
            "2,30,60",
            "3,40,80",
            "4,50,100",
        ]
    )
    filepath = tmp_path / "counts.csv"
    filepath.write_text(csv_text)

    dataset = csv_to_dataset_weight_coarsen_poisson(
        filepath,
        time_start=None,
        time_end=None,
        logtimestart=2000.0,
        number_of_log_time_points=5,
        minimum_counts=5.0,
    )
    scaled = apply_factor(dataset)

    normalized_factors = np.array([2.0, 4.0]) / np.sqrt(20.0)
    np.testing.assert_allclose(scaled.factor.values, normalized_factors)
    np.testing.assert_allclose(
        scaled.data.values, dataset.data.values * normalized_factors[np.newaxis, :]
    )
    np.testing.assert_allclose(
        scaled.weight.values,
        dataset.weight.values / normalized_factors[np.newaxis, :],
    )


def test_csv_to_dataset_weight_coarsen_poisson_can_skip_factor_application(tmp_path) -> None:
    csv_text = "\n".join(
        [
            "factor,2,4",
            "wavelength,500,600",
            "0,10,20",
            "1,20,40",
            "2,30,60",
            "3,40,80",
            "4,50,100",
        ]
    )
    filepath = tmp_path / "counts.csv"
    filepath.write_text(csv_text)

    dataset = csv_to_dataset_weight_coarsen_poisson(
        filepath,
        time_start=None,
        time_end=None,
        logtimestart=2000.0,
        number_of_log_time_points=5,
        minimum_counts=5.0,
        apply_factor=False,
    )

    np.testing.assert_array_equal(dataset.time.values, np.array([0.0, 1000.0, 3000.0]))
    np.testing.assert_allclose(dataset.factor.values, np.array([2.0, 4.0]))
    np.testing.assert_allclose(
        dataset.data.values,
        np.array(
            [
                [50.0, 100.0],
                [40.0, 80.0],
                [20.0, 40.0],
            ]
        ),
    )
    np.testing.assert_allclose(
        dataset.weight.values,
        np.array(
            [
                [1.0 / np.sqrt(50.0), 1.0 / np.sqrt(100.0)],
                [1.0 / np.sqrt(40.0), 1.0 / np.sqrt(80.0)],
                [1.0 / np.sqrt(60.0) / 3.0, 1.0 / np.sqrt(120.0) / 3.0],
            ]
        ),
    )
