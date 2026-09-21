from __future__ import annotations

import numpy as np
from pygta_local_extras.io import ascii_trace_folder_to_dataset_IRF
from pygta_local_extras.io import irf_dataset_coarsen


def test_ascii_trace_folder_to_dataset_irf_loads_wavelength_explicit_files(tmp_path) -> None:
    trace_660 = "\n".join(str(value) for value in range(2048)) + "\n9999\n"
    trace_680 = "\n".join(str(value + 1000) for value in range(2048)) + "\n9999\n"
    (tmp_path / "2433closed660.txt").write_text(trace_660)
    (tmp_path / "2433closed680.txt").write_text(trace_680)
    (tmp_path / "2433closedirf_680.txt").write_text("\n".join("1" for _ in range(2048)))

    dataset = ascii_trace_folder_to_dataset_IRF(
        tmp_path,
        file_pattern="2433closed[0-9][0-9][0-9].txt",
    )

    assert dataset.data.shape == (2048, 2)
    np.testing.assert_array_equal(dataset.spectral.values, np.array([660.0, 680.0]))
    np.testing.assert_array_equal(dataset.time.values[:5], np.array([0.0, 4.0, 8.0, 12.0, 16.0]))
    assert dataset.time.attrs["units"] == "ps"
    assert dataset.data.values[-1, 0] == 2047
    assert dataset.data.values[-1, 1] == 3047


def test_ascii_trace_folder_to_dataset_irf_loads_single_irf_trace(tmp_path) -> None:
    irf_trace = "\n".join(str(2000 - value) for value in range(2048))
    (tmp_path / "2433closedirf_680.txt").write_text(irf_trace)

    dataset = ascii_trace_folder_to_dataset_IRF(
        tmp_path,
        file_pattern="2433closedirf_680.txt",
    )

    assert dataset.data.shape == (2048, 1)
    np.testing.assert_array_equal(dataset.spectral.values, np.array([680.0]))
    assert dataset.data.values[0, 0] == 2000
    assert dataset.data.values[-1, 0] == -47


def test_ascii_trace_folder_to_dataset_irf_loads_multi_trace_range_files(tmp_path) -> None:
    header = "\n".join(f"# header {index}" for index in range(10))
    rows_660_700 = "\n".join(
        " ".join(str(value + column * 100) for column in range(5)) for value in range(7500)
    )
    rows_710_750 = "\n".join(
        " ".join(str(value + 1000 + column * 100) for column in range(5)) for value in range(7500)
    )

    (tmp_path / "2433closed660-700.txt").write_text(f"{header}\n{rows_660_700}\n")
    (tmp_path / "2433closed710-750.txt").write_text(f"{header}\n{rows_710_750}\n")

    dataset = ascii_trace_folder_to_dataset_IRF(
        tmp_path,
        file_pattern="2433closed*-*.txt",
        channel_count=7500,
        timestep_ps=4.0,
    )

    assert dataset.data.shape == (7500, 10)
    np.testing.assert_array_equal(dataset.spectral.values, np.arange(660.0, 760.0, 10.0))
    assert dataset.time.values[-1] == 29996.0
    assert dataset.data.values[0, 0] == 0.0
    assert dataset.data.values[0, 4] == 400.0
    assert dataset.data.values[0, 5] == 1000.0
    assert dataset.data.values[-1, 9] == 8899.0


def test_irf_dataset_coarsen_shifts_to_100_ps_and_coarsens_late_times(tmp_path) -> None:
    trace_660 = "\n".join("0" if value < 10 else "10" for value in range(64))
    trace_680 = "\n".join("0" if value < 14 else "20" for value in range(64))
    (tmp_path / "2433closed660.txt").write_text(trace_660)
    (tmp_path / "2433closed680.txt").write_text(trace_680)

    raw_dataset = ascii_trace_folder_to_dataset_IRF(
        tmp_path,
        file_pattern="2433closed[0-9][0-9][0-9].txt",
        channel_count=64,
        timestep_ps=4.0,
    )
    coarsened = irf_dataset_coarsen(
        raw_dataset,
        logtimestart=120.0,
        number_of_log_time_points=6,
    )

    assert "weight" in coarsened
    assert coarsened.data.shape[0] < raw_dataset.data.shape[0]
    assert coarsened.time.attrs["units"] == "ps"
    assert np.all(coarsened.weight.values >= 1.0)
    np.testing.assert_array_equal(
        coarsened.time.values[coarsened.time.values < 120.0],
        np.arange(0.0, 120.0, 4.0),
    )

    for spectral_index in range(coarsened.sizes["spectral"]):
        column = coarsened.data.values[:, spectral_index]
        above_half_max = np.where(column >= 0.5 * float(np.nanmax(column)))[0]
        assert above_half_max.size > 0
        assert coarsened.time.values[int(above_half_max[0])] == 100.0
