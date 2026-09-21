"""Utility functions for post-processing pyglotaran optimization results.

Handles SVD recomputation, scatter-compartment removal, and IRF dataset
concatenation for open/close target-analysis notebooks.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence

import numpy as np
import xarray as xr
from glotaran.io.prepare_dataset import add_svd_to_dataset


def drop_svd(ds: xr.Dataset) -> xr.Dataset:
    """Drop all SVD-related variables and dimensions from *ds* before concatenation.

    Removes only variables and dimensions tied to singular-value decomposition so
    that xr.concat does not trip on mismatched SVD coordinates across datasets
    while preserving decay metadata such as DAS and A-matrices.
    """
    drop_names = [
        name
        for name, var in ds.variables.items()
        if "singular" in name or any("singular" in dim for dim in var.dims)
    ]
    cleaned = ds.drop_vars(drop_names, errors="ignore")
    drop_dims = [dim for dim in cleaned.dims if "singular" in dim]
    if drop_dims:
        cleaned = cleaned.drop_dims(drop_dims, errors="ignore")
    return cleaned


def _svd_on(ds: xr.Dataset, name: str, label: str) -> bool:
    """Attempt to compute SVD for variable *name* in *ds*.

    Prints diagnostics and shows plots when the data contains non-finite values.

    Returns
    -------
    bool
        True when SVD was successfully added, False when data was bad.
    """
    if name not in ds:
        return False
    da = ds[name]
    bad = ~np.isfinite(da.values)
    if not bad.any():
        add_svd_to_dataset(ds, name=name, lsv_dim="time", rsv_dim="spectral")
        return True

    dims = da.dims
    time_axis = dims.index("time")
    spectral_axis = dims.index("spectral")
    bad_spectral_idx = np.where(bad.any(axis=time_axis))[0]
    bad_time_idx = np.where(bad.any(axis=spectral_axis))[0]

    print(f"\n{'=' * 60}")
    print(f"[{label}] '{name}' dims={dims}, shape={da.shape}")
    print(f"  {bad.sum()} non-finite / {bad.size} total ({100 * bad.mean():.1f}%)")
    print(
        f"  Bad spectral ({len(bad_spectral_idx)}/{da.sizes['spectral']}): "
        f"{bad_spectral_idx.tolist()}"
    )
    print(f"  Bad spectral coords: {ds.spectral.values[bad_spectral_idx].tolist()}")
    print(
        f"  Bad time indices: {bad_time_idx[:20].tolist()}"
        f"{'...' if len(bad_time_idx) > 20 else ''}"
    )
    n_plot = min(len(bad_spectral_idx), 6)
    if n_plot > 0:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, n_plot, figsize=(4 * n_plot, 4), squeeze=False)
        fig.suptitle(f"[{label}] Non-finite values in '{name}'", fontsize=11)
        time_vals = ds.time.values
        for i, si in enumerate(bad_spectral_idx[:n_plot]):
            ax = axes[0, i]
            col = da.isel(spectral=si).values
            finite_mask = np.isfinite(col)
            ax.plot(time_vals[finite_mask], col[finite_mask], "b.", ms=2)
            ax.axvline(0, color="k", lw=0.5)
            ax.set_title(
                f"{ds.spectral.values[si]:.2f} nm\n{(~finite_mask).sum()} bad",
                fontsize=9,
            )
            ax.set_xlabel("time")
        plt.tight_layout()
        plt.show()
    print(f"{'=' * 60}\n")
    return False


def add_svd(ds: xr.Dataset, label: str = "dataset") -> xr.Dataset:
    """Add residual SVD variables to *ds*, handling mixed-weight concat artefacts.

    Strategy:
    - ``weighted_residual`` fully finite  -> SVD on ``weighted_residual``.
    - ``weighted_residual`` has any NaN   -> drop it (and ``weight``) from the
      dataset so downstream tools (``plot_overview`` etc.) never see them, then
      compute SVD on plain ``residual``.
    - Only ``residual`` present           -> SVD on ``residual``.

    Parameters
    ----------
    ds:
        The concatenated result dataset.
    label:
        Human-readable name shown in diagnostic messages.

    Returns
    -------
    xr.Dataset
        The (possibly modified) dataset with SVD variables added.
    """
    if "weighted_residual" in ds:
        if np.isfinite(ds["weighted_residual"].values).all():
            add_svd_to_dataset(ds, name="weighted_residual", lsv_dim="time", rsv_dim="spectral")
            return ds
        # NaN in weighted_residual: mixed-weights concat artefact.
        # Drop it so plot_overview cannot accidentally SVD the NaN array.
        bad = ~np.isfinite(ds["weighted_residual"].values)
        dims = ds["weighted_residual"].dims
        bad_spectral_idx = np.where(bad.any(axis=dims.index("time")))[0]
        print(
            f"[{label}] weighted_residual has {bad.sum()} NaN/Inf "
            f"({len(bad_spectral_idx)}/{ds['weighted_residual'].sizes['spectral']} "
            f"spectral columns) - dropping it and computing SVD on residual instead."
        )
        drop_vars = [v for v in ("weighted_residual", "weight") if v in ds]
        ds = ds.drop_vars(drop_vars)

    _svd_on(ds, "residual", label)
    return ds


def drop_scatter(ds: xr.Dataset, scatter_labels: list[str]) -> xr.Dataset:
    """Remove scatter compartments from the dataset.

    Uses ``ds.sel(species=keep)`` so that **all** variables sharing the
    ``species`` coordinate (``species_concentration``,
    ``species_associated_spectra``, ``initial_concentration``, ...) are
    filtered together in one consistent step.

    ``clp`` uses the separate ``clp_label`` coordinate, so scatter entries
    there are zeroed rather than dropped.

    Parameters
    ----------
    ds:
        Result dataset (after SVD has been added).
    scatter_labels:
        List of compartment names to remove / zero out.

    Returns
    -------
    xr.Dataset
        Dataset without scatter compartments in species-indexed variables.
    """
    if "species" in ds.coords:
        keep = [s for s in ds.coords["species"].values if s not in scatter_labels]
        ds = ds.sel(species=keep)

    removed_decay_suffixes: set[str] = set()

    for coord_name in list(ds.coords):
        if not coord_name.startswith(("species_", "to_species_", "from_species_")):
            continue
        coord_values = ds.coords[coord_name].values.tolist()
        drop_values = [value for value in coord_values if value in scatter_labels]
        if drop_values:
            ds = ds.drop_sel({coord_name: drop_values})

    decay_metadata_prefixes = (
        "decay_associated_spectra_",
        "a_matrix_",
        "k_matrix_",
        "k_matrix_reduced_",
    )
    empty_decay_suffixes = {
        coord_name.removeprefix(prefix)
        for coord_name in ds.coords
        for prefix in ("species_", "to_species_", "from_species_")
        if coord_name.startswith(prefix) and ds.sizes[coord_name] == 0
    }
    removed_decay_suffixes.update(empty_decay_suffixes)
    empty_decay_vars = [
        var_name
        for var_name in ds.data_vars
        if var_name.startswith(decay_metadata_prefixes)
        and (
            any(ds.sizes[dim] == 0 for dim in ds[var_name].dims)
            or any(
                var_name == f"{prefix}{suffix}"
                for prefix in decay_metadata_prefixes
                for suffix in empty_decay_suffixes
            )
        )
    ]
    if empty_decay_vars:
        ds = ds.drop_vars(empty_decay_vars)

    for var_name in list(ds.data_vars):
        if not var_name.startswith("a_matrix_"):
            continue

        suffix = var_name.removeprefix("a_matrix_")
        das_name = f"decay_associated_spectra_{suffix}"
        if das_name not in ds or "species_associated_spectra" not in ds:
            continue

        a_matrix = ds[var_name]
        species_dims = [dim for dim in a_matrix.dims if dim.startswith("species_")]
        component_dims = [dim for dim in a_matrix.dims if dim.startswith("component_")]
        if len(species_dims) != 1 or len(component_dims) != 1:
            continue

        species_dim = species_dims[0]
        component_dim = component_dims[0]
        keep_species = [s for s in a_matrix.coords[species_dim].values if s not in scatter_labels]
        if not keep_species:
            removed_decay_suffixes.add(suffix)
            related_var_names = [
                name
                for name in (
                    var_name,
                    das_name,
                    f"k_matrix_{suffix}",
                    f"k_matrix_reduced_{suffix}",
                )
                if name in ds
            ]
            if related_var_names:
                ds = ds.drop_vars(related_var_names)
            continue

        filtered_a_matrix = a_matrix.sel({species_dim: keep_species})
        ds[var_name] = filtered_a_matrix

        species_spectra = ds["species_associated_spectra"].sel(species=keep_species)
        rebuilt_das = xr.dot(
            species_spectra.rename({"species": species_dim}),
            filtered_a_matrix,
            dims=species_dim,
        )
        transpose_dims = tuple(
            dim for dim in ("spectral", component_dim) if dim in rebuilt_das.dims
        )
        ds[das_name] = rebuilt_das.transpose(*transpose_dims)

    decay_coord_prefixes = (
        "component_",
        "rate_",
        "lifetime_",
        "species_",
        "to_species_",
        "from_species_",
    )
    decay_coord_names = [
        f"{prefix}{suffix}"
        for suffix in removed_decay_suffixes
        for prefix in decay_coord_prefixes
        if f"{prefix}{suffix}" in ds.coords
    ]
    decay_dim_names = [name for name in decay_coord_names if name in ds.dims]
    if decay_dim_names:
        ds = ds.drop_dims(decay_dim_names, errors="ignore")
    remaining_decay_coords = [name for name in decay_coord_names if name in ds.coords]
    if remaining_decay_coords:
        ds = ds.drop_vars(remaining_decay_coords, errors="ignore")

    if "clp" in ds:
        ds = ds.assign(clp=ds["clp"].where(~ds["clp"].clp_label.isin(scatter_labels), 0))
    return ds


def concatenate_result_datasets(
    result: object,
    dataset_keys: Sequence[str],
    scatter_labels: Sequence[str] = (),
) -> xr.Dataset:
    """Concatenate selected result datasets and recompute their SVD.

    The selected datasets have SVD variables removed before concatenation,
    ``dataset_scale_list`` metadata merged when it remains aligned, and
    scatter compartments removed after SVD recomputation.

    Parameters
    ----------
    result:
        Optimization result exposing the datasets through ``result.data``.
    dataset_keys:
        Keys in ``result.data`` to concatenate in the given order.
    scatter_labels:
        Compartment names to remove after concatenation.

    Returns
    -------
    xr.Dataset
        The concatenated and post-processed result dataset.
    """
    result_data = getattr(result, "data", None)
    if not isinstance(result_data, Mapping):
        raise TypeError("result must expose result.data as a mapping of datasets")

    dataset_keys = list(dataset_keys)
    concatenated = xr.concat(
        [drop_svd(result_data[key]) for key in dataset_keys],
        "spectral",
        coords="minimal",
        join="outer",
    )

    merged_scale_list = []
    for key in dataset_keys:
        scale_list = result_data[key].attrs.get("dataset_scale_list")
        if scale_list is not None:
            merged_scale_list.extend(scale_list)

    if merged_scale_list:
        if len(merged_scale_list) == concatenated.sizes["spectral"]:
            concatenated.attrs["dataset_scale_list"] = merged_scale_list
        else:
            concatenated.attrs.pop("dataset_scale_list", None)

    concatenated = add_svd(concatenated, label="concatenated")
    if scatter_labels:
        concatenated = drop_scatter(concatenated, list(scatter_labels))
    return concatenated


def collect_irf_datasets(
    result_data: dict,
    irf_prefix: str,
    spectral_coords,
) -> xr.Dataset:
    """Concatenate IRF result datasets along the spectral dimension.

    Datasets are sorted by key, SVD variables are stripped before
    concatenation, and spectral coordinates are reassigned from
    *spectral_coords* (typically taken from the matching kinetic dataset).

    Parameters
    ----------
    result_data:
        ``result.data`` dictionary from an ``optimize()`` call.
    irf_prefix:
        Key prefix identifying the IRF datasets (e.g. ``"IRFonolhcb9"``).
    spectral_coords:
        1-D array of spectral coordinate values to assign, one per dataset.

    Returns
    -------
    xr.Dataset
        Concatenated IRF dataset with spectral coordinates aligned to the
        kinetic data.
    """
    irf_pairs = sorted(
        [(key, val) for key, val in result_data.items() if key.startswith(irf_prefix)]
    )
    return xr.concat(
        [
            drop_svd(val).isel(spectral=0, drop=False).assign_coords({"spectral": [sc]})
            for (_, val), sc in zip(irf_pairs, spectral_coords)
        ],
        "spectral",
        join="outer",
        coords="minimal",
    )
