from __future__ import annotations

import numpy as np
import pytest
from pygta_local_extras.io import ascii_folder_to_datasets_weight_coarsen_poisson

EXPECTED_GROUPS = {
    "datasetsnolhcb9": {"opennolhcb9", "closenolhcb9"},
    "datasetsnolhcb16": {"opennolhcb16", "closenolhcb16"},
    "datasetscol0": {"opencol0", "closecol0"},
    "datasetskolhcII17": {"openkolhcII17", "closekolhcII17"},
    "datasetskolhcII36": {"openkolhcII36", "closekolhcII36"},
}


def _write_time_explicit_ascii(filepath, offset: float) -> None:
    times = np.array([0.0, 1000.0, 2000.0, 3000.0, 4000.0], dtype=float)
    spectral = np.array([500.0, 600.0], dtype=float)
    values = np.array(
        [
            [20.0 + offset, 25.0 + offset, 35.0 + offset, 40.0 + offset, 50.0 + offset],
            [30.0 + offset, 40.0 + offset, 60.0 + offset, 70.0 + offset, 80.0 + offset],
        ]
    )

    lines = [
        f"# Filename: {filepath}",
        "# Delimiter: Tab",
        "Time explicit",
        "Intervalnr 5",
        "\t".join(f"{value:.6g}" for value in times),
    ]
    for spectral_value, row in zip(spectral, values, strict=True):
        row_values = "\t".join(f"{value:.6g}" for value in row)
        lines.append(f"{spectral_value:.6g}\t{row_values}")

    filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_ascii_folder_to_datasets_weight_coarsen_poisson_builds_expected_groups(tmp_path) -> None:
    all_keys = sorted({key for keys in EXPECTED_GROUPS.values() for key in keys})
    for index, dataset_key in enumerate(all_keys):
        _write_time_explicit_ascii(tmp_path / f"{dataset_key}sim0.ascii", offset=float(index))

    grouped = ascii_folder_to_datasets_weight_coarsen_poisson(
        tmp_path,
        logtimestart=2000.0,
        number_of_log_time_points=5,
        minimum_counts=5.0,
        time_start=None,
        time_end=None,
    )

    assert set(grouped) == set(EXPECTED_GROUPS)
    for group_name, expected_keys in EXPECTED_GROUPS.items():
        assert set(grouped[group_name]) == expected_keys
        for dataset in grouped[group_name].values():
            assert "data" in dataset
            assert "weight" in dataset
            assert dataset.sizes["time"] >= 3
            assert dataset.sizes["spectral"] == 2
            assert np.all(np.isfinite(dataset.weight.values))


def test_ascii_folder_to_datasets_weight_coarsen_poisson_raises_on_missing_required_files(
    tmp_path,
) -> None:
    all_keys = sorted({key for keys in EXPECTED_GROUPS.values() for key in keys})
    for index, dataset_key in enumerate(all_keys[:-1]):
        _write_time_explicit_ascii(tmp_path / f"{dataset_key}sim0.ascii", offset=float(index))

    with pytest.raises(ValueError, match="Missing required simulated datasets"):
        ascii_folder_to_datasets_weight_coarsen_poisson(
            tmp_path,
            logtimestart=2000.0,
            number_of_log_time_points=5,
            minimum_counts=5.0,
            time_start=None,
            time_end=None,
        )
