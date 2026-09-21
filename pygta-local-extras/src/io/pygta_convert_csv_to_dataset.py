import re
import warnings
from io import StringIO
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import xarray as xr


def _read_factor_wavelength_data(
    filepath,
    replace_nan_with_zeros: bool,
    silence_warnings: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Read factor/wavelength/count data from the weighted CSV layout."""
    raw = pd.read_csv(filepath, header=None, delimiter=",", skipinitialspace=True)

    if raw.shape[0] < 3 or raw.shape[1] < 2:
        raise ValueError("CSV file does not match the expected factor/wavelength/data layout.")

    factors = pd.to_numeric(raw.iloc[0, 1:], errors="coerce").to_numpy(dtype=float)
    wavelengths = pd.to_numeric(raw.iloc[1, 1:], errors="coerce").to_numpy(dtype=float)
    timepoints = pd.to_numeric(raw.iloc[2:, 0], errors="coerce").to_numpy(dtype=float)
    data_values = raw.iloc[2:, 1:].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)

    invalid_factor = np.isnan(factors)
    invalid_wavelength = np.isnan(wavelengths)
    if invalid_factor.any() or invalid_wavelength.any():
        raise ValueError("Factor row or wavelength row contains non-numeric values.")

    valid_time = ~np.isnan(timepoints)
    if not np.all(valid_time):
        if not silence_warnings:
            warnings.warn("Rows with non-numeric time values were removed.", stacklevel=2)
        timepoints = timepoints[valid_time]
        data_values = data_values[valid_time]

    if np.isnan(data_values).any():
        if replace_nan_with_zeros:
            if not silence_warnings:
                warnings.warn("NaN values detected and replaced with zeros.", stacklevel=2)
            data_values = np.nan_to_num(data_values)
        elif not silence_warnings:
            warnings.warn("NaN values detected but not replaced.", stacklevel=2)

    if wavelengths.size != data_values.shape[1]:
        raise ValueError("Number of wavelengths does not match number of data columns.")

    return factors, wavelengths, timepoints, data_values


def _normalize_factors(factors: np.ndarray) -> np.ndarray:
    """Normalize factor row to unit L2 norm, matching the legacy loader."""
    factor_norm = float(np.linalg.norm(factors))
    if factor_norm == 0:
        raise ValueError("Factor row has zero L2 norm, cannot normalize factors.")
    return factors / factor_norm


def _infer_wavelengths_from_filename(
    filename: str,
    n_columns: int,
    wavelength_regex: str,
) -> list[float]:
    """Infer wavelength values from filename for single- and multi-trace files."""
    if n_columns == 1:
        wavelength_pattern = re.compile(wavelength_regex)
        match = wavelength_pattern.search(filename)
        if match is None:
            raise ValueError(
                f"Could not extract a wavelength from filename {filename!r} "
                f"using regex {wavelength_regex!r}."
            )
        return [float(match.group(1))]

    range_match = re.search(r"(?<!\d)(\d{3})-(\d{3})(?!\d)", filename)
    if range_match is not None:
        start_wavelength = float(range_match.group(1))
        end_wavelength = float(range_match.group(2))
        if n_columns == 1:
            return [start_wavelength]
        step = (end_wavelength - start_wavelength) / (n_columns - 1)
        return [start_wavelength + step * index for index in range(n_columns)]

    explicit_wavelengths = [
        float(match.group(1)) for match in re.finditer(r"(?<!\d)(\d{3})(?!\d)", filename)
    ]
    if len(explicit_wavelengths) >= n_columns:
        return explicit_wavelengths[:n_columns]

    raise ValueError(
        f"Could not infer wavelength columns from filename {filename!r} for {n_columns} traces."
    )


def _shift_to_half_max(
    dataset: xr.Dataset,
    bin_width: float | None = None,
    target_ps: float = 100.0,
) -> xr.Dataset:
    """Shift the ``data`` variable per wavelength so the rising edge sits at ``target_ps``.

    For each spectral column the first time bin whose value reaches 50 % of the
    column maximum is found.  The column is then shifted by an integer number of
    bins (no interpolation) so that the 50 % point aligns with the bin whose
    time coordinate is closest to ``target_ps``.  Vacated edge bins are filled
    with zeros.  The ``weight`` variable (if present) is left unchanged because
    its values are constant in time.

    Parameters
    ----------
    dataset : xr.Dataset
        Dataset with a ``data(time, spectral)`` variable.  Time axis must be
        sorted ascending and already converted to ps.
    bin_width : float | None
        Width of one time bin in ps. If ``None`` the value is inferred from the
        existing time coordinate. Used to reconstruct the final uniform time
        axis after the shift.
    target_ps : float
        Target time in ps for the 50 % rising-edge point.  Default is 100.0 ps.

    Returns
    -------
    xr.Dataset
        Dataset with the same coordinates and variables but with ``data``
        shifted per spectral column.
    """
    time_values = np.asarray(dataset.time.values, dtype=float)
    if time_values.ndim != 1 or time_values.size < 2:
        raise ValueError("Need at least two time points to infer shift bin width.")

    if bin_width is None:
        time_diffs = np.diff(time_values)
        if np.any(~np.isfinite(time_diffs)):
            raise ValueError("Time axis contains non-finite values, cannot infer bin width.")
        bin_width = float(np.median(time_diffs))
        if bin_width <= 0:
            raise ValueError("Inferred bin width must be positive.")

    target_bin = int(np.searchsorted(time_values, target_ps))
    data_arr = dataset["data"].values.copy()  # (n_time, n_spectral)
    n_spectral = data_arr.shape[1]

    for i in range(n_spectral):
        col = data_arr[:, i]
        max_val = float(np.nanmax(col))
        if max_val <= 0:
            continue
        above = np.where(col >= 0.5 * max_val)[0]
        if above.size == 0:
            continue
        found_bin = int(above[0])
        shift = target_bin - found_bin
        if shift == 0:
            continue
        rolled = np.roll(col, shift)
        if shift > 0:
            rolled[:shift] = 0.0
        else:
            rolled[shift:] = 0.0
        data_arr[:, i] = rolled

    n_time = data_arr.shape[0]
    new_time = target_ps + (np.arange(n_time) - target_bin) * float(bin_width)
    shifted = dataset.assign_coords(time=new_time).assign(
        {"data": (("time", "spectral"), data_arr)}
    )
    shifted.time.attrs.update(dataset.time.attrs)
    return shifted


def csv_to_dataset(
    filepath,
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    index_col: int | None = 0,
    header: int | None = 0,
    ordering: Literal["time_explicit", "wavelength_explicit"] = "time_explicit",
):
    """
    Load a regular formatted CSV file into an xarray dataset.

    Optionally replace NaN values with zeros and handle a missing index column
    by allowing specification or defaulting to the first column.
    Supports 'time_explicit' and 'wavelength_explicit' orderings.
    Handles padded first row in time-explicit format.

    Parameters:
    - filepath: str, path to the CSV file.
    - replace_nan_with_zeros: bool, if True, replace NaN values with zeros.
    - silence_warnings: bool, if True, do not print warnings.
        - index_col: int or None, column to use as the row labels of the
            DataFrame. If None, defaults to the first column.
    - ordering: str, either 'time_explicit' or 'wavelength_explicit' to specify the CSV format.

    Returns:
    - dataset: xarray.Dataset, dataset constructed from the CSV file.

    Note: Works for properly formatted comma-separated CSV files, including
    those with a padded first row.
    """
    # Load the CSV file into a pandas DataFrame
    df = pd.read_csv(
        filepath, index_col=index_col, header=header, delimiter=",", skipinitialspace=True
    )

    # Check for NaN values and replace them if requested
    if df.isnull().values.any():
        if replace_nan_with_zeros:
            if not silence_warnings:
                warnings.warn("NaN values detected and replaced with zeros.", stacklevel=2)
            df.fillna(0, inplace=True)
        else:
            if not silence_warnings:
                warnings.warn("NaN values detected but not replaced.", stacklevel=2)

    # Process based on the ordering type
    if ordering == "time_explicit":
        df = df.T
        # Check for padded first row (column after transposition)
        if df.columns[0] == 0 or pd.isna(df.columns[0]):
            df = df.iloc[:, 1:]  # Remove the first column if it's padded
            if not silence_warnings:
                warnings.warn("Padded first row detected and removed.", stacklevel=2)
    elif ordering == "wavelength_explicit":
        # Check for padded first column
        if df.index[0] == 0 or pd.isna(df.index[0]):
            df = df.iloc[1:, :]  # Remove the first row if it's padded
            if not silence_warnings:
                warnings.warn("Padded first column detected and removed.", stacklevel=2)
    else:
        raise ValueError(
            "Invalid ordering type. Must be 'time_explicit' or 'wavelength_explicit'."
        )

    # Convert index and columns to numeric, ignoring any non-numeric values
    df.index = pd.to_numeric(df.index, errors="coerce")
    df.columns = pd.to_numeric(df.columns, errors="coerce")

    # Remove any rows or columns that couldn't be converted to numeric
    df = df.loc[df.index.notnull(), df.columns.notnull()]

    timepoints = np.array(df.index.values).astype(float)
    wavelengths = np.array(df.columns.values).astype(float)
    return xr.DataArray(
        df.values,
        dims=["time", "spectral"],
        coords={"time": timepoints, "spectral": wavelengths},
    ).to_dataset(name="data")


def csv_to_dataset_weight(
    filepath,
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    time_start: float | None = 7000,
    time_end: float | None = 23000,
    overall_weight: float | None = None,
    shift: bool = False,
    bin_width: float | None = None,
    target_ps: float = 100.0,
):
    """
    Load a CSV file with per-wavelength scaling factors into an xarray dataset.

    Expected file layout:
    - row 1: ``factor,<f1>,<f2>,...,<f15>``
    - row 2: ``wavelength,<wl1>,<wl2>,...,<wl15>``
    - row 3+: ``<time>,<d1>,<d2>,...,<d15>``

    The factor row is normalized to unit L2 norm (sum of squares equals 1):

    ``f_norm = f * (1 / sqrt(sum(f**2)))``

    The data columns are multiplied by their corresponding normalized factor and a
    weight variable is added with values ``1 / f_norm`` for the full trace at each
    wavelength.

    Parameters:
    - filepath: str, path to the CSV file.
    - replace_nan_with_zeros: bool, if True, replace NaN values with zeros.
    - silence_warnings: bool, if True, do not print warnings.
    - shift: bool, if True, shift each spectral column in ``data`` so the 50 %
      rising-edge point lands at ``target_ps`` (default False).
        - bin_width: float | None, width of one time bin in ps. If None, infer it
            from the time axis.
    - target_ps: float, target time in ps for the 50 % rising-edge point (default 100.0).

    Returns:
    - dataset: xarray.Dataset, dataset containing ``data`` and ``weight``.
    """
    factors, wavelengths, timepoints, data_values = _read_factor_wavelength_data(
        filepath,
        replace_nan_with_zeros=replace_nan_with_zeros,
        silence_warnings=silence_warnings,
    )
    factors = _normalize_factors(factors)

    if np.any(factors == 0):
        raise ValueError("Factor row contains zero values, cannot create reciprocal weights.")

    scaled_data = data_values * factors[np.newaxis, :]

    dataset = xr.Dataset(
        data_vars={
            "data": (("time", "spectral"), scaled_data),
        },
        coords={"time": timepoints, "spectral": wavelengths},
    )
    # Reverse the time axis, convert it to ps, and keep time leading.
    dataset = (
        dataset.assign_coords(time=dataset.time[::-1] * 1000).sortby("time").transpose("time", ...)
    )
    # Update metadata
    dataset.time.attrs.update({"units": "ps"})
    if shift:
        dataset = _shift_to_half_max(dataset, bin_width, target_ps)
    if time_start is not None or time_end is not None:
        dataset = dataset.sel(time=slice(time_start, time_end))
    weight_values = np.broadcast_to(
        1.0 / factors[np.newaxis, :], (dataset.sizes["time"], len(wavelengths))
    ).copy()
    if overall_weight is not None:
        weight_values = weight_values * overall_weight
    return dataset.assign({"weight": (("time", "spectral"), weight_values)})


def csv_to_dataset_IRF(
    filepath,
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    time_start: float | None = 7000,
    time_end: float | None = 23000,
    shift: bool = False,
    bin_width: float | None = None,
    target_ps: float = 100.0,
):
    """
    Load an IRF CSV file into an xarray dataset.

    Expected file layout:
    - row 1: labels (non-numeric metadata)
    - row 2: ``wavelength,<wl1>,<wl2>,<wl3>,<wl4>``
    - row 3+: ``<time>,<irf1>,<irf2>,<irf3>,<irf4>``

    Parameters:
    - filepath: str, path to the CSV file.
    - replace_nan_with_zeros: bool, if True, replace NaN values with zeros.
    - silence_warnings: bool, if True, do not print warnings.
    - shift: bool, if True, shift each spectral column in ``data`` so the 50 %
      rising-edge point lands at ``target_ps`` (default False).
        - bin_width: float | None, width of one time bin in ps. If None, infer it
            from the time axis.
    - target_ps: float, target time in ps for the 50 % rising-edge point (default 100.0).

    Returns:
    - dataset: xarray.Dataset with ``data(time, spectral)``.
    """
    raw = pd.read_csv(filepath, header=None, delimiter=",", skipinitialspace=True)

    if raw.shape[0] < 3 or raw.shape[1] < 5:
        raise ValueError("CSV file does not match the expected IRF layout.")

    wavelengths = pd.to_numeric(raw.iloc[1, 1:], errors="coerce").to_numpy(dtype=float)
    timepoints = pd.to_numeric(raw.iloc[2:, 0], errors="coerce").to_numpy(dtype=float)
    data_values = raw.iloc[2:, 1:].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)

    if np.isnan(wavelengths).any():
        raise ValueError("Wavelength row contains non-numeric values.")

    if wavelengths.size != data_values.shape[1]:
        raise ValueError("Number of wavelengths does not match number of IRF columns.")

    valid_time = ~np.isnan(timepoints)
    if not np.all(valid_time):
        if not silence_warnings:
            warnings.warn("Rows with non-numeric time values were removed.", stacklevel=2)
        timepoints = timepoints[valid_time]
        data_values = data_values[valid_time]

    if np.isnan(data_values).any():
        if replace_nan_with_zeros:
            if not silence_warnings:
                warnings.warn("NaN values detected and replaced with zeros.", stacklevel=2)
            data_values = np.nan_to_num(data_values)
        elif not silence_warnings:
            warnings.warn("NaN values detected but not replaced.", stacklevel=2)

    dataset = xr.DataArray(
        data_values,
        dims=["time", "spectral"],
        coords={"time": timepoints, "spectral": wavelengths},
    ).to_dataset(name="data")
    # Reverse the time axis, convert it to ps, and keep time leading.
    dataset = (
        dataset.assign_coords(time=dataset.time[::-1] * 1000).sortby("time").transpose("time", ...)
    )
    # Update metadata
    dataset.time.attrs.update({"units": "ps"})
    if shift:
        dataset = _shift_to_half_max(dataset, bin_width, target_ps)
    if time_start is not None or time_end is not None:
        dataset = dataset.sel(time=slice(time_start, time_end))
    return dataset


def ascii_trace_folder_to_dataset_IRF(
    folderpath,
    file_pattern: str = "*.txt",
    wavelength_regex: str = r"(\d+(?:\.\d+)?)\D*\.txt$",
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    channel_count: int = 2048,
    timestep_ps: float = 4.0,
    time_start: float | None = None,
    time_end: float | None = None,
    shift: bool = False,
    bin_width: float | None = None,
    target_ps: float = 100.0,
):
    """Load wavelength-explicit ASCII trace files from a folder into an IRF-like dataset.

    Each matching text file may contain either a single photon-count trace column or
    multiple trace columns. For multi-trace files, a 10-line text header can be
    present and is auto-detected when line 1 starts with ``#``. Only the first
    ``channel_count`` data rows are used.

    For single-trace files, the wavelength is extracted with ``wavelength_regex``.
    For multi-trace files, wavelengths are inferred from the filename, supporting
    patterns such as ``660-700`` (expanded to equal steps over the trace columns).

    This helper is intended for folder layouts where each wavelength trace is stored in
    a separate file, analogous to the dataset returned by ``csv_to_dataset_IRF``.
    If a folder contains both measurement traces and a separate IRF trace, call this
    function twice with different ``file_pattern`` values so each dataset is loaded
    separately.

    Parameters
    ----------
    folderpath : str or pathlib.Path
        Folder containing the text trace files.
    file_pattern : str
        Glob pattern used to select the files to load.
    wavelength_regex : str
        Regular expression used to extract the wavelength from each filename. The first
        capture group is converted to float.
    replace_nan_with_zeros : bool
        If True, replace NaN values with zeros.
    silence_warnings : bool
        If True, suppress warnings.
    channel_count : int
        Number of time channels to read from each file.
    timestep_ps : float
        Width of one channel in ps.
    time_start : float or None
        Lower bound for time selection in ps applied after loading.
    time_end : float or None
        Upper bound for time selection in ps applied after loading.
    shift : bool
        If True, shift each spectral column in ``data`` so the 50 % rising-edge point
        lands at ``target_ps``.
    bin_width : float | None
        Width of one time bin in ps. If None, defaults to ``timestep_ps``.
    target_ps : float
        Target time in ps for the 50 % rising-edge point.

    Returns
    -------
    xarray.Dataset
        Dataset with ``data(time, spectral)`` analogous to ``csv_to_dataset_IRF``.
    """
    folder = Path(folderpath)
    filepaths = sorted(folder.glob(file_pattern))

    if not filepaths:
        raise ValueError(
            f"No files matching pattern {file_pattern!r} found in folder {folder.as_posix()!r}."
        )

    traces_by_wavelength: dict[float, np.ndarray] = {}

    for filepath in filepaths:
        first_line = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
        has_header = first_line.lstrip().startswith("#")
        skiprows = 10 if has_header else 0

        raw = pd.read_csv(
            filepath,
            header=None,
            sep=r"\s+",
            skiprows=skiprows,
            nrows=channel_count,
        )
        if raw.shape[0] < channel_count:
            raise ValueError(
                f"File {filepath.name!r} contains only {raw.shape[0]} rows, expected at least "
                f"{channel_count}."
            )

        data_values = raw.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        if np.isnan(data_values).any():
            if replace_nan_with_zeros:
                if not silence_warnings:
                    warnings.warn(
                        f"NaN values detected in {filepath.name!r} and replaced with zeros.",
                        stacklevel=2,
                    )
                data_values = np.nan_to_num(data_values)
            elif not silence_warnings:
                warnings.warn(
                    f"NaN values detected in {filepath.name!r} but not replaced.",
                    stacklevel=2,
                )

        file_wavelengths = _infer_wavelengths_from_filename(
            filepath.name,
            data_values.shape[1],
            wavelength_regex,
        )
        if len(file_wavelengths) != data_values.shape[1]:
            raise ValueError(
                f"Inferred {len(file_wavelengths)} wavelengths but found "
                f"{data_values.shape[1]} trace columns in {filepath.name!r}."
            )

        for column_index, wavelength in enumerate(file_wavelengths):
            if wavelength in traces_by_wavelength:
                raise ValueError(
                    f"Duplicate wavelength {wavelength} detected in {filepath.name!r}."
                )
            traces_by_wavelength[wavelength] = data_values[:, column_index]

    wavelengths = np.array(sorted(traces_by_wavelength), dtype=float)
    data_values = np.column_stack([traces_by_wavelength[wavelength] for wavelength in wavelengths])
    timepoints = np.arange(channel_count, dtype=float) * timestep_ps

    dataset = xr.DataArray(
        data_values,
        dims=["time", "spectral"],
        coords={"time": timepoints, "spectral": wavelengths},
    ).to_dataset(name="data")
    dataset.time.attrs.update({"units": "ps"})
    if shift:
        dataset = _shift_to_half_max(
            dataset, timestep_ps if bin_width is None else bin_width, target_ps
        )
    if time_start is not None or time_end is not None:
        dataset = dataset.sel(time=slice(time_start, time_end))
    return dataset


def _coarsen_dataset_logarithmic(
    dataset: xr.Dataset,
    logtimestart: float,
    number_of_log_time_points: int,
) -> xr.Dataset:
    """Coarsen a dataset on the time axis using the standard odd-block schedule."""
    time_all = dataset.time.values
    spectral_vals = dataset.spectral.values

    mask_early = time_all < logtimestart
    mask_late = ~mask_early

    early_times = time_all[mask_early]
    late_times = time_all[mask_late]
    late_data = dataset["data"].values[mask_late]
    late_count = len(late_times)

    group_sizes = [
        3,
        5,
        7,
        9,
        11,
        13,
        15,
        17,
        19,
        21,
        23,
        25,
        27,
        29,
        31,
        33,
        35,
        37,
        39,
        41,
    ]
    n_per_stage = max(1, round(number_of_log_time_points / len(group_sizes)))

    block_sizes: list[int] = []
    for group_size in group_sizes:
        block_sizes.extend([group_size] * n_per_stage)

    coarse_times: list[float] = []
    coarse_data: list[np.ndarray] = []
    coarse_group_sizes: list[int] = []

    idx = 0
    for block_size in block_sizes:
        if idx + block_size > late_count:
            break
        mid = block_size // 2
        coarse_times.append(late_times[idx + mid])
        coarse_data.append(late_data[idx : idx + block_size].mean(axis=0))
        coarse_group_sizes.append(block_size)
        idx += block_size

    if idx < late_count:
        remainder = late_times[idx:]
        remainder_count = len(remainder)
        coarse_times.append(remainder[remainder_count // 2])
        coarse_data.append(late_data[idx:].mean(axis=0))
        coarse_group_sizes.append(remainder_count)

    early_data = dataset["data"].values[mask_early]
    parts_time = [early_times]
    parts_data = [early_data]

    if coarse_times:
        parts_time.append(np.array(coarse_times))
        parts_data.append(np.array(coarse_data))

    new_times = np.concatenate(parts_time)
    new_data = (
        np.concatenate(parts_data, axis=0)
        if any(part.size for part in parts_data)
        else np.empty((0, len(spectral_vals)))
    )

    data_vars: dict[str, tuple[tuple[str, str], np.ndarray]] = {
        "data": (("time", "spectral"), new_data),
    }

    if "weight" in dataset:
        base_weight_1d = dataset["weight"].values[0, :]
        all_group_sizes = np.concatenate(
            [
                np.ones(len(early_times), dtype=float),
                (
                    np.array(coarse_group_sizes, dtype=float)
                    if coarse_group_sizes
                    else np.empty(0, dtype=float)
                ),
            ]
        )
        new_weight = base_weight_1d[np.newaxis, :] * all_group_sizes[:, np.newaxis]
        data_vars["weight"] = (("time", "spectral"), new_weight)

    new_dataset = xr.Dataset(
        data_vars=data_vars,
        coords={"time": new_times, "spectral": spectral_vals},
    )
    new_dataset.time.attrs.update(dataset.time.attrs)
    return new_dataset


def _coarsen_dataset_logarithmic_poisson(
    dataset: xr.Dataset,
    logtimestart: float,
    number_of_log_time_points: int,
    minimum_counts: float,
) -> xr.Dataset:
    """Coarsen count data and compute Poisson weights from coarsened count sums."""
    time_all = dataset.time.values
    spectral_vals = dataset.spectral.values

    mask_early = time_all < logtimestart
    mask_late = ~mask_early

    early_times = time_all[mask_early]
    late_times = time_all[mask_late]
    early_data = dataset["data"].values[mask_early]
    late_data = dataset["data"].values[mask_late]
    late_count = len(late_times)

    group_sizes = [
        3,
        5,
        7,
        9,
        11,
        13,
        15,
        17,
        19,
        21,
        23,
        25,
        27,
        29,
        31,
        33,
        35,
        37,
        39,
        41,
    ]
    n_per_stage = max(1, round(number_of_log_time_points / len(group_sizes)))

    block_sizes: list[int] = []
    for group_size in group_sizes:
        block_sizes.extend([group_size] * n_per_stage)

    coarse_times: list[float] = []
    coarse_data: list[np.ndarray] = []
    coarse_weight: list[np.ndarray] = []

    idx = 0
    for block_size in block_sizes:
        if idx + block_size > late_count:
            break
        block = late_data[idx : idx + block_size]
        block_sum = block.sum(axis=0)
        mid = block_size // 2
        coarse_times.append(late_times[idx + mid])
        coarse_data.append(block_sum / block_size)
        coarse_weight.append(1.0 / np.sqrt(np.maximum(block_sum, minimum_counts)))
        idx += block_size

    if idx < late_count:
        block = late_data[idx:]
        block_size = block.shape[0]
        block_sum = block.sum(axis=0)
        coarse_times.append(late_times[idx + (block_size // 2)])
        coarse_data.append(block_sum / block_size)
        coarse_weight.append(1.0 / np.sqrt(np.maximum(block_sum, minimum_counts)))

    early_weight = 1.0 / np.sqrt(np.maximum(early_data, minimum_counts))

    parts_time = [early_times]
    parts_data = [early_data]
    parts_weight = [early_weight]
    if coarse_times:
        parts_time.append(np.array(coarse_times))
        parts_data.append(np.array(coarse_data))
        parts_weight.append(np.array(coarse_weight))

    new_times = np.concatenate(parts_time)
    new_data = (
        np.concatenate(parts_data, axis=0)
        if any(part.size for part in parts_data)
        else np.empty((0, len(spectral_vals)))
    )
    new_weight = (
        np.concatenate(parts_weight, axis=0)
        if any(part.size for part in parts_weight)
        else np.empty((0, len(spectral_vals)))
    )

    new_dataset = xr.Dataset(
        data_vars={
            "data": (("time", "spectral"), new_data),
            "weight": (("time", "spectral"), new_weight),
        },
        coords={"time": new_times, "spectral": spectral_vals},
    )
    if "factor" in dataset:
        new_dataset = new_dataset.assign({"factor": (("spectral",), dataset["factor"].values)})
    new_dataset.time.attrs.update(dataset.time.attrs)
    return new_dataset


def apply_factor(
    dataset: xr.Dataset,
    factors: np.ndarray | None = None,
    normalize_factors: bool = True,
    overall_weight: float | None = None,
) -> xr.Dataset:
    """Apply per-wavelength factors to data and weight at the end of processing.

    The same factor is multiplied into both ``data`` and ``weight`` along the
    spectral dimension. If ``factors`` is omitted, ``dataset['factor']`` is used.
    """
    if "data" not in dataset or "weight" not in dataset:
        raise ValueError("Dataset must contain both 'data' and 'weight' variables.")

    if factors is None:
        if "factor" not in dataset:
            raise ValueError(
                "No factors provided and dataset does not contain a 'factor' variable."
            )
        factor_values = np.asarray(dataset["factor"].values, dtype=float)
    else:
        factor_values = np.asarray(factors, dtype=float)

    if factor_values.ndim != 1:
        raise ValueError("Factors must be a one-dimensional array.")
    if factor_values.shape[0] != dataset.sizes["spectral"]:
        raise ValueError("Number of factors must match the spectral dimension size.")

    if normalize_factors:
        factor_values = _normalize_factors(factor_values)

    scaled_data = dataset["data"].values * factor_values[np.newaxis, :]
    scaled_weight = dataset["weight"].values / factor_values[np.newaxis, :]
    if overall_weight is not None:
        scaled_weight = scaled_weight * overall_weight

    return dataset.assign(
        {
            "data": (("time", "spectral"), scaled_data),
            "weight": (("time", "spectral"), scaled_weight),
            "factor": (("spectral",), factor_values),
        }
    )


_apply_factor_dataset = apply_factor


def irf_dataset_coarsen(
    dataset: xr.Dataset,
    time_start: float | None = None,
    time_end: float | None = None,
    logtimestart: float = 8000,
    number_of_log_time_points: int = 1000,
    shift: bool = True,
    bin_width: float | None = None,
    target_ps: float = 100.0,
) -> xr.Dataset:
    """Shift and coarsen an IRF-like dataset created by the raw IRF loaders.

    This continues from an already loaded dataset such as the output of
    ``ascii_trace_folder_to_dataset_IRF`` or ``csv_to_dataset_IRF``. The data are
    optionally shifted so the per-wavelength 50 % rising-edge point sits at
    ``target_ps`` and then coarsened on the late-time axis using the same logic as
    ``csv_to_dataset_weight_coarsen``. If no ``weight`` variable is present, a
    unit weight array is created so the coarsened output carries block-size weights
    analogous to ``csv_to_dataset_weight_coarsen``.
    """
    ds = dataset.copy(deep=True)
    if "weight" not in ds:
        weight_values = np.ones((ds.sizes["time"], ds.sizes["spectral"]), dtype=float)
        ds = ds.assign({"weight": (("time", "spectral"), weight_values)})
    if shift:
        ds = _shift_to_half_max(ds, bin_width, target_ps)
    if time_start is not None or time_end is not None:
        ds = ds.sel(time=slice(time_start, time_end))
    return _coarsen_dataset_logarithmic(ds, logtimestart, number_of_log_time_points)


def csv_to_dataset_weight_coarsen(
    filepath,
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    time_start: float | None = 7000,
    time_end: float | None = 23000,
    logtimestart: float = 8000,
    number_of_log_time_points: int = 1000,
    overall_weight: float | None = None,
    shift: bool = False,
    bin_width: float | None = None,
    target_ps: float = 100.0,
):
    """
    Load a CSV file with per-wavelength scaling factors and coarsen the time axis
    logarithmically starting from ``logtimestart``.

    Time points before ``logtimestart`` are kept as-is.  Starting from
    ``logtimestart`` the time axis is coarsened by averaging consecutive blocks
    of increasing (odd) size: first groups of 3, then 5, 7, 9, 11, 13.  The
    number of blocks per group size is chosen so that the total number of
    retained time points from ``logtimestart`` is close to
    ``number_of_log_time_points``.  For each block the middle time point is
    used as the representative time coordinate and the data values in the block
    are averaged.

    Parameters
    ----------
    filepath : str
        Path to the CSV file (same format as ``csv_to_dataset_weight``).
    replace_nan_with_zeros : bool
        If True, replace NaN values with zeros.
    silence_warnings : bool
        If True, suppress warnings.
    time_start : float or None
        Lower bound for time selection (ps) applied after loading.
    time_end : float or None
        Upper bound for time selection (ps) applied after loading.
    logtimestart : float
        Time (ps) from which coarsening begins.  Points before this are kept
        at their original resolution.
    number_of_log_time_points : int
        Target number of time points to retain from ``logtimestart`` onward.
        The actual count will be close but may differ slightly depending on
        how many full blocks fit in the available data.
    shift : bool
        If True, shift each spectral column in ``data`` so the 50 % rising-edge
        point lands at ``target_ps`` before coarsening.  Passed through to
        ``csv_to_dataset_weight``.
    bin_width : float | None
        Width of one time bin in ps. If None, infer it from the time axis.
    target_ps : float
        Target time in ps for the 50 % rising-edge point (default 100.0).

    Returns
    -------
    xarray.Dataset
        Dataset with ``data`` and ``weight`` variables on the coarsened time
        axis.
    """
    # ---- load via base function (handles parsing, scaling, weights, time flip) ----
    ds = csv_to_dataset_weight(
        filepath,
        replace_nan_with_zeros=replace_nan_with_zeros,
        silence_warnings=silence_warnings,
        time_start=time_start,
        time_end=time_end,
        overall_weight=overall_weight,
        shift=shift,
        bin_width=bin_width,
        target_ps=target_ps,
    )

    return _coarsen_dataset_logarithmic(ds, logtimestart, number_of_log_time_points)


def csv_to_dataset_weight_coarsen_poisson(
    filepath,
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    time_start: float | None = 7000,
    time_end: float | None = 23000,
    logtimestart: float = 8000,
    number_of_log_time_points: int = 1000,
    minimum_counts: float = 5.0,
    apply_factor: bool = True,
    shift: bool = False,
    bin_width: float | None = None,
    target_ps: float = 100.0,
) -> xr.Dataset:
    """Load count CSV, coarsen first, then apply factors at the end.

    For each raw count value ``cd``, weight is ``1 / sqrt(max(cd, minimum_counts))``.
    For coarsened groups of size ``g``, the block sum ``cdg`` is used so weight is
    ``1 / sqrt(max(cdg, minimum_counts)) / g`` while data is ``cdg / g``.

    If ``apply_factor`` is True (default), factors are applied after coarsening.
    If False, the coarsened count-domain ``data`` and ``weight`` are returned.
    """
    factors, wavelengths, timepoints, data_values = _read_factor_wavelength_data(
        filepath,
        replace_nan_with_zeros=replace_nan_with_zeros,
        silence_warnings=silence_warnings,
    )

    dataset = xr.Dataset(
        data_vars={
            "data": (("time", "spectral"), data_values),
            "factor": (("spectral",), factors),
        },
        coords={"time": timepoints, "spectral": wavelengths},
    )
    dataset = (
        dataset.assign_coords(time=dataset.time[::-1] * 1000).sortby("time").transpose("time", ...)
    )
    dataset.time.attrs.update({"units": "ps"})

    if shift:
        dataset = _shift_to_half_max(dataset, bin_width, target_ps)
    if time_start is not None or time_end is not None:
        dataset = dataset.sel(time=slice(time_start, time_end))

    coarsened = _coarsen_dataset_logarithmic_poisson(
        dataset,
        logtimestart=logtimestart,
        number_of_log_time_points=number_of_log_time_points,
        minimum_counts=minimum_counts,
    )
    if apply_factor:
        return _apply_factor_dataset(coarsened)
    return coarsened


def ascii_folder_to_datasets_weight_coarsen_poisson(
    folderpath: str | Path = (
        "AnnaCalabritto/generated-figures/"
        "20260514col0_nolhcb9_16_kolhcII17_36_opcl_global6/simulated_traces"
    ),
    *,
    file_pattern: str = "*.ascii",
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    time_start: float | None = 7000,
    time_end: float | None = 23000,
    logtimestart: float = 8000,
    number_of_log_time_points: int = 1000,
    minimum_counts: float = 5.0,
    shift: bool = False,
    bin_width: float | None = None,
    target_ps: float = 100.0,
) -> dict[str, dict[str, xr.Dataset]]:
    """Load simulated ASCII traces and build Poisson-weighted dataset dictionaries.

    The returned mapping contains five dictionaries mirroring the notebook
    structure used as

    ``**datasetsnolhcb9, **datasetsnolhcb16, **datasetscol0,``
    ``**datasetskolhcII17, **datasetskolhcII36``.
    """

    folder = Path(folderpath)
    if not folder.is_dir():
        raise ValueError(f"Folder does not exist: {folder.as_posix()!r}")

    files = sorted(folder.glob(file_pattern))
    if not files:
        raise ValueError(
            f"No ASCII files matching {file_pattern!r} found in {folder.as_posix()!r}."
        )

    group_members = {
        "datasetsnolhcb9": {"opennolhcb9", "closenolhcb9"},
        "datasetsnolhcb16": {"opennolhcb16", "closenolhcb16"},
        "datasetscol0": {"opencol0", "closecol0"},
        "datasetskolhcII17": {"openkolhcII17", "closekolhcII17"},
        "datasetskolhcII36": {"openkolhcII36", "closekolhcII36"},
    }
    key_to_group = {
        dataset_key: group_name
        for group_name, dataset_keys in group_members.items()
        for dataset_key in dataset_keys
    }
    grouped_datasets = {group_name: {} for group_name in group_members}

    for filepath in files:
        dataset_key = _strip_simulation_suffix(filepath.stem)
        if dataset_key not in key_to_group:
            continue

        dataset = _ascii_explicit_to_dataset(
            filepath,
            replace_nan_with_zeros=replace_nan_with_zeros,
            silence_warnings=silence_warnings,
        )
        if shift:
            dataset = _shift_to_half_max(dataset, bin_width, target_ps)
        if time_start is not None or time_end is not None:
            dataset = dataset.sel(time=slice(time_start, time_end))

        coarsened = _coarsen_dataset_logarithmic_poisson(
            dataset,
            logtimestart=logtimestart,
            number_of_log_time_points=number_of_log_time_points,
            minimum_counts=minimum_counts,
        )
        grouped_datasets[key_to_group[dataset_key]][dataset_key] = coarsened

    missing_keys: list[str] = []
    for group_name, expected_keys in group_members.items():
        present = set(grouped_datasets[group_name])
        missing_keys.extend(sorted(expected_keys - present))
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(
            "Missing required simulated datasets: "
            f"{missing}. Check filenames in {folder.as_posix()!r}."
        )

    return grouped_datasets


def _ascii_explicit_to_dataset(
    filepath: str | Path,
    *,
    replace_nan_with_zeros: bool,
    silence_warnings: bool,
) -> xr.Dataset:
    path = Path(filepath)
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 6:
        raise ValueError(f"ASCII file {path.name!r} is too short.")

    explicit_format = lines[2].strip().lower()
    explicit_axis = np.fromstring(lines[4], sep="\t")
    if explicit_axis.size == 0:
        explicit_axis = np.fromstring(lines[4], sep=" ")
    if explicit_axis.size == 0:
        raise ValueError(f"Could not parse explicit-axis row in {path.name!r}.")

    matrix_text = "\n".join(lines[5:])
    raw_matrix = np.loadtxt(StringIO(matrix_text), dtype=float, ndmin=2)
    if raw_matrix.shape[1] < 2:
        raise ValueError(f"ASCII file {path.name!r} does not contain data columns.")

    secondary_axis = raw_matrix[:, 0]
    observations = raw_matrix[:, 1:]

    if explicit_format == "time explicit":
        time = explicit_axis.astype(float)
        spectral = secondary_axis.astype(float)
        data = observations.T
    elif explicit_format == "wavelength explicit":
        spectral = explicit_axis.astype(float)
        time = secondary_axis.astype(float)
        data = observations
    else:
        raise ValueError(
            f"Unsupported explicit format {lines[2].strip()!r} in file {path.name!r}."
        )

    if np.isnan(data).any():
        if replace_nan_with_zeros:
            if not silence_warnings:
                warnings.warn(
                    f"NaN values detected in {path.name!r} and replaced with zeros.",
                    stacklevel=2,
                )
            data = np.nan_to_num(data)
        elif not silence_warnings:
            warnings.warn(f"NaN values detected in {path.name!r} but not replaced.", stacklevel=2)

    if data.shape != (time.size, spectral.size):
        raise ValueError(
            f"Parsed shape mismatch in {path.name!r}: data {data.shape}, "
            f"time {time.size}, spectral {spectral.size}."
        )

    dataset = xr.Dataset(
        data_vars={"data": (("time", "spectral"), data)},
        coords={"time": time, "spectral": spectral},
    )
    dataset.time.attrs.update({"units": "ps"})
    return dataset


def _strip_simulation_suffix(name: str) -> str:
    return re.sub(r"sim[0-9eE+\-.]+$", "", name)


def csv_to_dataset_org(
    filepath,
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    index_col: int | None = 0,
    header: int | None = 0,
    ordering: Literal["time_explicit", "wavelength_explicit"] = "time_explicit",
):
    """
    Load a regular formatted CSV file into an xarray dataset.

    Optionally replace NaN values with zeros and handle a missing index column
    by allowing specification or defaulting to the first column.
    Supports 'time_explicit' and 'wavelength_explicit' orderings.

    Parameters:
    - filepath: str, path to the CSV file.
    - replace_nan_with_zeros: bool, if True, replace NaN values with zeros.
    - silence_warnings: bool, if True, do not print warnings.
        - index_col: int or None, column to use as the row labels of the
            DataFrame. If None, defaults to the first column.
    - ordering: str, either 'time_explicit' or 'wavelength_explicit' to specify the CSV format.

    Returns:
    - dataset: xarray.Dataset, dataset constructed from the CSV file.

    Note: only works well for properly formatted and padded comma-separated CSV files.
    """
    # Load the CSV file into a pandas DataFrame
    df = pd.read_csv(
        filepath, index_col=index_col, header=header, delimiter=",", skipinitialspace=True
    )

    # Check for NaN values and replace them if requested
    if df.isnull().values.any():
        if replace_nan_with_zeros:
            if not silence_warnings:
                warnings.warn("NaN values detected and replaced with zeros.", stacklevel=2)
            df.fillna(0, inplace=True)
        else:
            if not silence_warnings:
                warnings.warn("NaN values detected but not replaced.", stacklevel=2)

    df.index = pd.to_numeric(df.index)
    df.columns = pd.to_numeric(df.columns)
    # Process based on the ordering type
    if ordering == "time_explicit":
        df = df.T
    elif ordering == "wavelength_explicit":
        pass
    else:
        raise ValueError(
            "Invalid ordering type. Must be 'time_explicit' or 'wavelength_explicit'."
        )
    timepoints = np.array(df.index.values).astype(float)
    wavelengths = np.array(df.columns.values).astype(float)
    return xr.DataArray(
        df.values,
        dims=["time", "spectral"],
        coords={"time": timepoints, "spectral": wavelengths},
    ).to_dataset(name="data")
