"""Steady-state spectrum computation from pyglotaran results.

The steady-state spectrum replicates the ``calcsteadystateperexp`` logic from
``timutil.f``:

    c_SS_i = sum_j  A_{ji} * tau_j       (= A.T @ tau, per species i)
    esteady(lambda, i) = c_SS_i * SAS_i(lambda)
    esteady(lambda, total) = sum_i esteady(lambda, i)

where A is the amplitude (A-)matrix, tau_j = 1/kappa_j are the component
lifetimes, and SAS are the Species-Associated Spectra.

The A-matrix already encodes the initial concentrations (it is built from the
eigenvectors and the gamma vector ``solve(V, j0)``), so no separate handling of
``initial_concentration`` is needed beyond what is already embedded in it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from pygta_local_extras.analysis.initial_concentration import _megacomplex_scale_mapping

if TYPE_CHECKING:
    from collections.abc import Mapping


def _steady_state_concentrations_from_dataset(
    dataset: xr.Dataset,
    megacomplex_scales: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Return per-species steady-state concentrations for one result dataset.

    Iterates over every ``a_matrix_<mc_label>`` variable present in *dataset*
    and accumulates:

        c_SS[i] += sum_j  A[j, i] * tau[j]

    for all megacomplex contributions.

    Parameters
    ----------
    dataset:
        A single dataset from ``result.data``.

    Returns
    -------
    dict[str, float]
        Mapping from species name to its steady-state concentration.
        Empty if no A-matrix variables are found.
    """
    c_ss: dict[str, float] = {}

    for var_name in dataset.data_vars:
        if not var_name.startswith("a_matrix_"):
            continue

        mc_label = var_name[len("a_matrix_") :]
        a_mat = dataset[var_name]  # dims: (component_<mc>, species_<mc>)

        lifetime_coord = f"lifetime_{mc_label}"
        species_coord = f"species_{mc_label}"

        if lifetime_coord not in a_mat.coords or species_coord not in a_mat.coords:
            continue  # unexpected shape; skip gracefully

        lifetimes = a_mat.coords[lifetime_coord].values  # (n_components,)
        species = a_mat.coords[species_coord].values  # (n_species,)
        a_values = a_mat.values  # (n_components, n_species)

        # c_SS[i] = sum_j A[j, i] * tau[j]  →  A.T @ tau
        scale = (megacomplex_scales or {}).get(mc_label, 1.0)
        c_ss_mc = scale * (a_values.T @ lifetimes)  # (n_species,)

        for sp, c in zip(species, c_ss_mc, strict=True):
            c_ss[sp] = c_ss.get(sp, 0.0) + float(c)

    return c_ss


def compute_steady_state_spectra(
    result: object,
    exclude_species: list[str] | None = None,
) -> dict[str, xr.Dataset]:
    """Compute per-dataset steady-state spectra from a pyglotaran result.

    For each dataset in *result.data* the function:

    1. Reads the A-matrix (or matrices, for multi-megacomplex datasets) and
       their associated component lifetimes to obtain steady-state
       concentrations ``c_SS``.
    2. Multiplies each species' ``c_SS`` value by its SAS column to get the
       per-species steady-state contribution.
    3. Sums the contributions for the total steady-state spectrum.

    The returned datasets contain:

    * ``steady_state_spectra`` – ``(spectral, species)`` DataArray with the
      per-species steady-state spectra.
    * ``steady_state_spectrum`` – ``(spectral,)`` DataArray with the summed
      total steady-state spectrum.

    Parameters
    ----------
    result:
        A pyglotaran ``Result`` object (or any object whose ``.data``
        attribute is a mapping of dataset labels to ``xr.Dataset``).
    exclude_species:
        Optional list of species names to exclude from the steady-state
        computation.  Useful to omit scatter compartments (e.g.
        ``["oscatnolhcb9", "cscatnolhcb9"]``) that are modelled as
        technical artefacts and should not contribute to the physical
        steady-state spectrum.  Species absent from a dataset are silently
        ignored.

    Returns
    -------
    dict[str, xr.Dataset]
        Mapping from dataset label to a dataset containing the two
        steady-state variables described above.  Datasets without an
        A-matrix (e.g. pure spectral megacomplexes) are silently skipped.

    Examples
    --------
    >>> ss = compute_steady_state_spectra(result)
    >>> ss["dataset1"]["steady_state_spectrum"].plot()

    >>> scatter = ["oscatnolhcb9", "cscatnolhcb9", "oscatnolhcb16", "cscatnolhcb16"]
    >>> ss = compute_steady_state_spectra(result, exclude_species=scatter)
    """
    excluded: frozenset[str] = frozenset(exclude_species or [])
    data: Mapping[str, xr.Dataset] = result.data  # type: ignore[attr-defined]
    scale_map = _megacomplex_scale_mapping(result)
    out: dict[str, xr.Dataset] = {}

    for dataset_name, dataset in data.items():
        dataset_scales = {
            mc_label: scale
            for (scaled_dataset_name, mc_label), scale in scale_map.items()
            if scaled_dataset_name == dataset_name
        }
        c_ss = _steady_state_concentrations_from_dataset(dataset, dataset_scales)
        if not c_ss:
            continue

        if "species_associated_spectra" not in dataset:
            continue

        sas = dataset["species_associated_spectra"]  # (spectral, species)
        spectral_coords = sas.coords["spectral"].values
        all_species_in_sas = sas.coords["species"].values.tolist()

        # Only keep species that appear in both c_SS and the SAS array,
        # and are not explicitly excluded.
        valid_species = [s for s in c_ss if s in all_species_in_sas and s not in excluded]
        if not valid_species:
            continue

        sas_vals = sas.sel(species=valid_species).values  # (n_spectral, n_valid)
        c_ss_vals = np.array([c_ss[s] for s in valid_species])  # (n_valid,)

        per_species_vals = sas_vals * c_ss_vals[np.newaxis, :]  # (n_spectral, n_valid)
        total_vals = per_species_vals.sum(axis=1)  # (n_spectral,)

        per_species_da = xr.DataArray(
            per_species_vals,
            dims=("spectral", "species"),
            coords={"spectral": spectral_coords, "species": valid_species},
        )
        total_da = xr.DataArray(
            total_vals,
            dims=("spectral",),
            coords={"spectral": spectral_coords},
        )

        out[dataset_name] = xr.Dataset(
            {
                "steady_state_spectra": per_species_da,
                "steady_state_spectrum": total_da,
            }
        )

    return out
