"""Simulation helpers for fitted pyglotaran datasets."""

from __future__ import annotations

import json
import numbers
import re
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import xarray as xr


def save_dataset(
    dataset: xr.Dataset | xr.DataArray,
    file_name: str | Path,
    format_name: str | None = None,
    *,
    irf_center_location: xr.DataArray | Sequence[float] | None = None,
    allow_overwrite: bool = False,
    update_source_path: bool = True,
    **kwargs: object,
) -> Path:
    """Save a dataset after removing wavelength-dependent IRF dispersion.

    The corrected traces are interpolated onto the original time grid. For each
    wavelength, the trace is shifted by the difference between its IRF center and
    the minimum IRF center, so all IRF maxima align with that minimum.
    """

    corrected_dataset = _correct_dataset_for_irf_dispersion(
        dataset,
        irf_center_location=irf_center_location,
    )
    output_path = _add_filename_suffix(file_name, "nodisp")

    from glotaran.io import save_dataset as glotaran_save_dataset

    glotaran_save_dataset(
        corrected_dataset,
        output_path,
        format_name,
        allow_overwrite=allow_overwrite,
        update_source_path=update_source_path,
        **kwargs,
    )
    return output_path


save_dataset_nodisp = save_dataset


def simulate_from_fitted_data(
    result: object,
    *,
    poisson: bool = True,
    sigma: float = 0.0,
    output_dir: str | Path | None = None,
    rng: np.random.Generator | None = None,
) -> dict[str, xr.Dataset]:
    """Simulate all fitted datasets from a result object and export them as ASCII.

    The function reads ``fitted_data`` from every dataset in ``result.data`` (or
    compatible result-like inputs), simulates new observations, writes one
    ``.ascii`` file per dataset, and returns the simulated datasets.
    """

    if sigma < 0:
        raise ValueError("sigma must be non-negative")

    generator = np.random.default_rng() if rng is None else rng
    target_dir = Path.cwd() if output_dir is None else Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    result_map = _result_dataset_mapping(result)
    suffix = _simulation_suffix(poisson=poisson, sigma=sigma)
    simulated: dict[str, xr.Dataset] = {}

    for dataset_name, result_dataset in result_map.items():
        fitted_data = _fitted_data_array(result_dataset, dataset_name)
        simulated_values = _simulate_values(
            fitted_data.to_numpy(),
            dataset_name=dataset_name,
            poisson=poisson,
            sigma=sigma,
            rng=generator,
        )
        simulated_name = f"{dataset_name}{suffix}"
        simulated_dataset = xr.DataArray(
            simulated_values,
            dims=fitted_data.dims,
            coords=fitted_data.coords,
            attrs=dict(fitted_data.attrs),
            name="data",
        ).to_dataset()
        simulated_dataset.attrs.update(getattr(result_dataset, "attrs", {}))

        file_format = (
            "Wavelength explicit"
            if simulated_dataset.sizes["spectral"] < simulated_dataset.sizes["time"]
            else "Time explicit"
        )
        output_path = target_dir / f"{simulated_name}.ascii"
        _write_explicit_ascii(
            output_path,
            simulated_dataset["data"],
            file_format=file_format,
            comment=simulated_name,
            poisson=poisson,
        )
        simulated_dataset.attrs["source_path"] = str(output_path)
        simulated[simulated_name] = simulated_dataset

    return simulated


def simulate_from_result(
    result: object,
    *,
    dataset_labels: Sequence[str] | None = None,
) -> dict[str, xr.Dataset]:
    """Create clean simulated datasets from the fitted data in a result object.

    The returned mapping preserves the dataset names from ``result.data`` unless
    ``dataset_labels`` selects a subset.
    """

    result_map = _result_dataset_mapping(result)
    selected_labels = _normalize_dataset_labels(dataset_labels, result_map.keys())
    simulated: dict[str, xr.Dataset] = {}

    for dataset_name, result_dataset in result_map.items():
        if selected_labels is not None and dataset_name not in selected_labels:
            continue
        fitted_data = _fitted_data_array(result_dataset, dataset_name)
        simulated[dataset_name] = _dataset_from_values(
            result_dataset=result_dataset,
            fitted_data=fitted_data,
            values=fitted_data.to_numpy(),
            noise_mode="none",
            sigma=0.0,
        )

    return simulated


def apply_noise_to_simulated_datasets(
    simulated_datasets: Mapping[str, xr.Dataset],
    *,
    noise: str | None = "poisson",
    sigma: float = 0.0,
    rng: np.random.Generator | None = None,
) -> dict[str, xr.Dataset]:
    """Return noisy copies of simulated datasets.

    Parameters
    ----------
    simulated_datasets:
        Mapping of dataset names to xarray datasets containing a ``data`` variable.
    noise:
        ``"poisson"`` for Poisson sampling, ``"additive"`` for Gaussian noise,
        or ``None`` to keep the data unchanged.
    sigma:
        Standard deviation for additive noise.
    rng:
        Optional random number generator.
    """

    if sigma < 0:
        raise ValueError("sigma must be non-negative")

    if noise not in {None, "poisson", "additive"}:
        raise ValueError("noise must be None, 'poisson', or 'additive'")

    generator = np.random.default_rng() if rng is None else rng
    noisy_datasets: dict[str, xr.Dataset] = {}

    for dataset_name, simulated_dataset in simulated_datasets.items():
        data_array = _dataset_data_array(simulated_dataset, dataset_name)
        noisy_values = _apply_noise(
            data_array.to_numpy(),
            dataset_name=dataset_name,
            noise=noise,
            sigma=sigma,
            rng=generator,
        )
        noisy_datasets[dataset_name] = _dataset_from_values(
            result_dataset=simulated_dataset,
            fitted_data=data_array,
            values=noisy_values,
            noise_mode="none" if noise is None else noise,
            sigma=sigma,
        )

    return noisy_datasets


def _estimate_effective_group_size(
    time_ps: np.ndarray,
    logtimestart: float = 8000.0,
) -> np.ndarray:
    """Estimate effective coarsening group size from a coarsened time grid."""

    t = np.asarray(time_ps, dtype=float)
    if t.ndim != 1 or t.size < 2:
        return np.ones_like(t, dtype=float)

    diffs = np.diff(t)
    positive_diffs = diffs[diffs > 0]
    if positive_diffs.size == 0:
        return np.ones_like(t, dtype=float)

    early_mask = t < logtimestart
    early_diffs = np.diff(t[early_mask]) if np.count_nonzero(early_mask) >= 2 else np.array([])
    early_diffs = early_diffs[early_diffs > 0]
    base_dt = float(np.median(early_diffs)) if early_diffs.size else float(np.min(positive_diffs))

    span = np.empty_like(t)
    span[0] = t[1] - t[0]
    span[-1] = t[-1] - t[-2]
    span[1:-1] = 0.5 * (t[2:] - t[:-2])

    g = np.maximum(1, np.rint(span / max(base_dt, 1e-12)).astype(int))
    g[early_mask] = 1

    late_mask = ~early_mask
    g[late_mask] = np.where(g[late_mask] % 2 == 0, g[late_mask] + 1, g[late_mask])

    return g.astype(float)


def transform_simulated_from_result_poisson_noise(
    simulated_dict: Mapping[str, xr.Dataset],
    *,
    count_scale: float = 20000.0,
    minimum_counts: float = 5.0,
    logtimestart: float = 8000.0,
    dataset_labels: Sequence[str] | None = None,
    seed: int = 123,
    use_expected_for_weight: bool = True,
) -> tuple[dict[str, xr.Dataset], float, float]:
    """Create Poisson-noisy simulations and matching coarsening-aware weights."""

    labels = list(dataset_labels) if dataset_labels is not None else list(simulated_dict.keys())
    if not labels:
        raise ValueError("No dataset labels provided for simulated transformation.")

    global_max = 0.0
    for label in labels:
        ds = simulated_dict[label]
        data_values = np.asarray(ds["data"].values, dtype=float)
        if data_values.size:
            global_max = max(global_max, float(np.nanmax(data_values)))

    if global_max <= 0:
        raise ValueError("Simulated data maximum is non-positive; cannot derive count factor.")

    factor = float(count_scale) / global_max
    rng = np.random.default_rng(seed)
    transformed: dict[str, xr.Dataset] = {}

    for label in labels:
        ds = simulated_dict[label]
        data_arr = np.asarray(ds["data"].values, dtype=float)
        dims = ds["data"].dims
        time_vals = np.asarray(ds.time.values, dtype=float)

        g = _estimate_effective_group_size(time_vals, logtimestart=logtimestart)
        g2d = g[:, np.newaxis]

        expected_counts = np.clip(data_arr * factor, a_min=0.0, a_max=None) * g2d
        sampled_counts = rng.poisson(expected_counts)

        noisy_intensity = sampled_counts / (factor * g2d)

        counts_for_sigma = expected_counts if use_expected_for_weight else sampled_counts
        sigma_intensity = np.sqrt(np.maximum(counts_for_sigma, minimum_counts)) / (factor * g2d)
        poisson_weight = 1.0 / sigma_intensity

        ds_out = ds.copy(deep=True)
        ds_out["data"] = (dims, noisy_intensity)
        ds_out["weight"] = (dims, poisson_weight)
        ds_out.attrs["poisson_factor"] = factor
        ds_out.attrs["poisson_count_scale"] = float(count_scale)
        ds_out.attrs["poisson_minimum_counts"] = float(minimum_counts)
        ds_out.attrs["poisson_weight_source"] = (
            "expected" if use_expected_for_weight else "sampled"
        )
        transformed[label] = ds_out

    return transformed, factor, global_max


def simulate_from_result_with_noise(
    result: object,
    *,
    dataset_labels: Sequence[str] | None = None,
    noise: str | None = "poisson",
    sigma: float = 0.0,
    rng: np.random.Generator | None = None,
) -> dict[str, xr.Dataset]:
    """Convenience wrapper that simulates fitted data and immediately adds noise."""

    simulated = simulate_from_result(result, dataset_labels=dataset_labels)
    return apply_noise_to_simulated_datasets(
        simulated,
        noise=noise,
        sigma=sigma,
        rng=rng,
    )


def save_dataset_dict_to_nc(
    datasets: Mapping[str, xr.Dataset],
    output_dir: str | Path,
    *,
    allow_overwrite: bool = False,
    compression: bool = True,
) -> Path:
    """Save a mapping of datasets as individual NetCDF files plus an index file."""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    index: dict[str, str] = {}
    encoding = {"data": {"zlib": True, "complevel": 1}} if compression else None

    for dataset_name, dataset in datasets.items():
        file_path = target_dir / f"{dataset_name}.nc"
        if file_path.exists() and not allow_overwrite:
            raise FileExistsError(file_path)
        safe_dataset = _dataset_for_netcdf(dataset)
        safe_dataset.to_netcdf(file_path, mode="w", encoding=encoding)
        index[dataset_name] = file_path.name

    index_path = target_dir / "index.json"
    if index_path.exists() and not allow_overwrite:
        raise FileExistsError(index_path)
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return target_dir


def load_dataset_dict_from_nc(
    input_dir: str | Path,
) -> dict[str, xr.Dataset]:
    """Load a dataset mapping previously written by save_dataset_dict_to_nc."""

    source_dir = Path(input_dir)
    index_path = source_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))

    loaded: dict[str, xr.Dataset] = {}
    for dataset_name, file_name in index.items():
        loaded[dataset_name] = xr.load_dataset(source_dir / file_name)

    return loaded


def _dataset_for_netcdf(dataset: xr.Dataset) -> xr.Dataset:
    safe_dataset = dataset.copy(deep=True)
    safe_dataset.attrs.clear()
    safe_dataset.attrs.update(_sanitize_attrs(dict(dataset.attrs)))

    for variable_name in safe_dataset.variables:
        variable = safe_dataset[variable_name]
        variable.attrs.clear()
        variable.attrs.update(_sanitize_attrs(dict(dataset[variable_name].attrs)))

    return safe_dataset


def _sanitize_attrs(attrs: Mapping[str, object]) -> dict[str, object]:
    return {str(key): _sanitize_attr_value(value) for key, value in attrs.items()}


def _sanitize_attr_value(value: object) -> object:
    if value is None:
        return "None"
    if isinstance(value, (bool, np.bool_)):
        return int(value)
    if isinstance(value, (str, bytes, numbers.Number, np.number)):
        return value
    if isinstance(value, list):
        return [_sanitize_attr_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_attr_value(item) for item in value)
    if isinstance(value, np.ndarray):
        if value.dtype == object:
            return np.array([_sanitize_attr_value(item) for item in value], dtype=object)
        return value
    return str(value)


def _simulate_values(
    fitted_data: np.ndarray,
    *,
    dataset_name: str,
    poisson: bool,
    sigma: float,
    rng: np.random.Generator,
) -> np.ndarray:
    if not np.isfinite(fitted_data).all():
        raise ValueError(f"dataset {dataset_name!r} contains non-finite fitted_data values")

    if poisson:
        if np.any(fitted_data < 0):
            raise ValueError(
                f"dataset {dataset_name!r} contains negative fitted_data values, "
                "which cannot be used as Poisson intensities"
            )
        return rng.poisson(fitted_data)

    noise = rng.normal(loc=0.0, scale=sigma, size=fitted_data.shape)
    return fitted_data.astype(np.float64, copy=False) + noise


def _apply_noise(
    values: np.ndarray,
    *,
    dataset_name: str,
    noise: str | None,
    sigma: float,
    rng: np.random.Generator,
) -> np.ndarray:
    if not np.isfinite(values).all():
        raise ValueError(f"dataset {dataset_name!r} contains non-finite values")

    if noise is None:
        return values.astype(np.float64, copy=False)

    if noise == "poisson":
        if np.any(values < 0):
            raise ValueError(
                f"dataset {dataset_name!r} contains negative values, "
                "which cannot be used as Poisson intensities"
            )
        return rng.poisson(values)

    noise_values = rng.normal(loc=0.0, scale=sigma, size=values.shape)
    return values.astype(np.float64, copy=False) + noise_values


def _fitted_data_array(result_dataset: xr.Dataset, dataset_name: str) -> xr.DataArray:
    if "fitted_data" not in result_dataset:
        raise TypeError(f"dataset {dataset_name!r} does not contain a fitted_data variable")

    fitted_data = result_dataset["fitted_data"]
    if fitted_data.dims != ("time", "spectral"):
        try:
            fitted_data = fitted_data.transpose("time", "spectral")
        except ValueError as exc:
            raise TypeError(
                f"dataset {dataset_name!r} fitted_data must have time and spectral dimensions"
            ) from exc
    return fitted_data


def _correct_dataset_for_irf_dispersion(
    dataset: xr.Dataset | xr.DataArray,
    *,
    irf_center_location: xr.DataArray | Sequence[float] | None,
) -> xr.Dataset | xr.DataArray:
    if irf_center_location is None:
        return dataset.copy(deep=True)

    if isinstance(dataset, xr.Dataset):
        if "data" not in dataset:
            raise TypeError("dataset must contain a 'data' variable")
        corrected = dataset.copy(deep=True)
        corrected["data"] = _correct_data_array_for_irf_dispersion(
            corrected["data"],
            irf_center_location=irf_center_location,
        )
        return corrected

    return _correct_data_array_for_irf_dispersion(
        dataset,
        irf_center_location=irf_center_location,
    )


def _correct_data_array_for_irf_dispersion(
    data_array: xr.DataArray,
    *,
    irf_center_location: xr.DataArray | Sequence[float],
) -> xr.DataArray:
    if {"time", "spectral"} - set(data_array.dims):
        raise ValueError("dataset must have 'time' and 'spectral' dimensions")

    data_array = data_array.transpose("time", "spectral")
    time_values = np.asarray(data_array.coords["time"].values, dtype=float)
    if time_values.ndim != 1 or time_values.size < 2 or np.any(np.diff(time_values) <= 0):
        raise ValueError("time coordinate must contain at least two strictly increasing values")

    center_values = _irf_center_values(
        irf_center_location,
        spectral_values=np.asarray(data_array.coords["spectral"].values),
    )
    shifts = center_values - np.min(center_values)
    values = np.asarray(data_array.values)
    corrected_values = np.empty_like(values, dtype=np.result_type(values, np.float64))
    for spectral_index, shift in enumerate(shifts):
        corrected_values[:, spectral_index] = np.interp(
            time_values + shift,
            time_values,
            values[:, spectral_index],
            # By default, it clamps values outside but NaN is undesirable
            # left=np.nan,
            # right=np.nan,
        )

    return xr.DataArray(
        corrected_values,
        dims=data_array.dims,
        coords=data_array.coords,
        attrs=dict(data_array.attrs),
        name=data_array.name,
    )


def _irf_center_values(
    irf_center_location: xr.DataArray | Sequence[float],
    *,
    spectral_values: np.ndarray,
) -> np.ndarray:
    if isinstance(irf_center_location, xr.DataArray):
        centers = irf_center_location
        if "spectral" not in centers.dims:
            raise ValueError("irf_center_location must have a 'spectral' dimension")
        for dimension in centers.dims:
            if dimension != "spectral":
                if centers.sizes[dimension] != 1:
                    raise ValueError(
                        "irf_center_location must contain one IRF center per spectral value"
                    )
                centers = centers.isel({dimension: 0}, drop=True)
        if centers.sizes["spectral"] != spectral_values.size:
            centers = centers.interp(spectral=spectral_values)
        values = np.asarray(centers.values, dtype=float)
    else:
        values = np.asarray(irf_center_location, dtype=float)

    if values.ndim != 1 or values.size != spectral_values.size:
        raise ValueError("irf_center_location must have one value per spectral value")
    if not np.isfinite(values).all():
        raise ValueError("irf_center_location must contain only finite values")
    return values


def _add_filename_suffix(file_name: str | Path, suffix: str) -> Path:
    output_path = Path(file_name)
    if output_path.stem.endswith(f"_{suffix}"):
        return output_path
    return output_path.with_name(f"{output_path.stem}_{suffix}{output_path.suffix}")


def _dataset_data_array(dataset: xr.Dataset, dataset_name: str) -> xr.DataArray:
    if "data" not in dataset:
        raise TypeError(f"dataset {dataset_name!r} does not contain a data variable")

    data_array = dataset["data"]
    if data_array.dims != ("time", "spectral"):
        try:
            data_array = data_array.transpose("time", "spectral")
        except ValueError as exc:
            raise TypeError(
                f"dataset {dataset_name!r} data must have time and spectral dimensions"
            ) from exc
    return data_array


def _dataset_from_values(
    *,
    result_dataset: xr.Dataset,
    fitted_data: xr.DataArray,
    values: np.ndarray,
    noise_mode: str,
    sigma: float,
) -> xr.Dataset:
    simulated_dataset = xr.DataArray(
        values,
        dims=fitted_data.dims,
        coords=fitted_data.coords,
        attrs=dict(fitted_data.attrs),
        name="data",
    ).to_dataset()
    simulated_dataset.attrs.update(getattr(result_dataset, "attrs", {}))
    simulated_dataset.attrs["noise_mode"] = noise_mode
    simulated_dataset.attrs["noise_sigma"] = float(sigma)
    return simulated_dataset


def _normalize_dataset_labels(
    dataset_labels: Sequence[str] | None,
    available_labels: Sequence[str],
) -> set[str] | None:
    if dataset_labels is None:
        return None

    selected = {str(label) for label in dataset_labels}
    available = {str(label) for label in available_labels}
    unknown = sorted(selected - available)
    if unknown:
        raise ValueError(
            "Unknown dataset labels: " + ", ".join(unknown) + ". "
            f"Available labels are: {', '.join(sorted(available))}"
        )
    return selected


def _write_explicit_ascii(
    file_path: Path,
    data_array: xr.DataArray,
    *,
    file_format: str,
    comment: str,
    poisson: bool,
) -> None:
    observations = np.asarray(data_array.to_numpy()).T
    time_axis = np.asarray(data_array.coords["time"].to_numpy(), dtype=float)
    spectral_axis = np.asarray(data_array.coords["spectral"].to_numpy(), dtype=float)
    comments = f"# Filename: {file_path}\n{comment}\n"

    if file_format == "Wavelength explicit":
        explicit_axis = "\t".join(_format_float(value) for value in spectral_axis)
        header = f"{comments}Wavelength explicit\nIntervalnr {len(spectral_axis)}\n{explicit_axis}"
        raw_data = np.vstack((time_axis.T, observations)).T
    elif file_format == "Time explicit":
        explicit_axis = "\t".join(_format_float(value) for value in time_axis)
        header = f"{comments}Time explicit\nIntervalnr {len(time_axis)}\n{explicit_axis}"
        raw_data = np.vstack((spectral_axis.T, observations.T)).T
    else:
        raise ValueError(f"Unsupported file format {file_format!r}")

    data_column_count = raw_data.shape[1] - 1
    number_format: str | list[str]
    if poisson:
        number_format = ["%.17g", *(["%d"] * data_column_count)]
    else:
        number_format = ["%.17g", *(["%.17g"] * data_column_count)]

    np.savetxt(
        file_path,
        raw_data,
        fmt=number_format,
        delimiter="\t",
        newline="\n",
        header=header,
        comments="",
    )


def _simulation_suffix(*, poisson: bool, sigma: float) -> str:
    return "sim0" if poisson else f"sim{_format_sigma(sigma)}"


def _format_sigma(sigma: float) -> str:
    if sigma == 0:
        return "0"

    text = format(sigma, ".15g")
    if "e" not in text and "E" not in text:
        text = format(sigma, ".0e")
    text = text.lower()
    text = re.sub(r"e\+", "e", text)
    return re.sub(r"e(-?)0+(\d+)", r"e\1\2", text)


def _format_float(value: float) -> str:
    return format(float(value), ".17g")


def _result_dataset_mapping(result: object) -> Mapping[str, xr.Dataset]:
    if isinstance(result, xr.Dataset):
        return {"dataset": result}

    if isinstance(result, Mapping):
        return {str(key): _as_dataset(value) for key, value in result.items()}

    if isinstance(result, Sequence) and not isinstance(result, str | bytes | Path):
        return {f"dataset{index}": _as_dataset(value) for index, value in enumerate(result)}

    data_mapping = getattr(result, "data", None)
    if isinstance(data_mapping, Mapping):
        return {str(key): _as_dataset(value) for key, value in data_mapping.items()}

    raise TypeError("result must be a dataset, mapping, sequence, or expose a .data mapping")


def _as_dataset(value: object) -> xr.Dataset:
    if isinstance(value, xr.Dataset):
        return value
    raise TypeError("simulate_from_fitted_data requires xarray.Dataset inputs")
