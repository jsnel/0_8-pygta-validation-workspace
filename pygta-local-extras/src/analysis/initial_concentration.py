"""Helpers for inspecting initial concentrations from result a-matrixes."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import xarray as xr


def initial_concentration_table(
    result: object,
    *,
    normalize_initial_concentration: bool = False,
    omit: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Create a dataset-by-species table of initial concentrations.

    The table contains one row per dataset and one column per species found in
    any ``a_matrix_*`` variable. If the same species occurs in multiple
    a-matrix blocks for one dataset, the values are summed.
    """

    result_map = _result_dataset_mapping(result)
    scale_map = _megacomplex_scale_mapping(result)
    omitted_species = {str(species_name) for species_name in (omit or [])}
    species_order: list[str] = []
    rows: list[dict[str, float | str]] = []

    for dataset_name, result_dataset in result_map.items():
        row: dict[str, float | str] = {"dataset": dataset_name}

        for var_name in result_dataset.data_vars:
            if not var_name.startswith("a_matrix_"):
                continue

            mc_suffix = var_name.removeprefix("a_matrix_")
            species_coord = f"species_{mc_suffix}"
            initial_coord = f"initial_concentration_{mc_suffix}"
            if species_coord not in result_dataset[var_name].coords:
                continue
            if initial_coord not in result_dataset[var_name].coords:
                continue

            species = [
                str(species_name)
                for species_name in result_dataset[var_name].coords[species_coord].values.tolist()
            ]
            initial_values = result_dataset[var_name].coords[initial_coord].values.tolist()

            for species_name, initial_value in zip(species, initial_values, strict=False):
                if species_name in omitted_species:
                    continue
                value = float(initial_value) * scale_map.get((dataset_name, mc_suffix), 1.0)
                row[species_name] = float(row.get(species_name, 0.0)) + value
                if species_name not in species_order:
                    species_order.append(species_name)

        numeric_species = [species_name for species_name in species_order if species_name in row]
        if normalize_initial_concentration and numeric_species:
            total = sum(float(row[species_name]) for species_name in numeric_species)
            if total != 0:
                for species_name in numeric_species:
                    row[species_name] = float(row[species_name]) / total

        rows.append(row)

    if not rows:
        return pd.DataFrame(index=pd.Index([], name="dataset"))

    table = pd.DataFrame.from_records(rows).set_index("dataset")
    if species_order:
        table = table.reindex(columns=species_order, fill_value=0.0)
    return table.fillna(0.0)


def selected_initial_concentration_table(
    result: object,
    species: Sequence[str],
    *,
    multipliers: Mapping[str, float] | Sequence[float] | float | None = None,
    normalize_initial_concentration: bool = False,
    omit: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Create a selected initial-concentration table, optionally scaled.

    Parameters
    ----------
    result:
        Result-like object accepted by ``result_dataset_mapping``.
    species:
        Species labels to keep as columns in the returned table.
    multipliers:
        Optional per-species scaling applied after selection. This may be a
        mapping keyed by species label, a sequence aligned with ``species``, or
        one scalar applied to every selected species.
    normalize_initial_concentration:
        Whether to normalize per-dataset totals before selection.
    """

    selected_species = [str(species_name) for species_name in species]
    table = initial_concentration_table(
        result,
        normalize_initial_concentration=normalize_initial_concentration,
        omit=omit,
    )
    if table.empty:
        return table.reindex(columns=selected_species, fill_value=0.0)

    selected_table = table.reindex(columns=selected_species, fill_value=0.0).copy()
    multiplier_map = _multiplier_mapping(selected_species, multipliers)
    for species_name, multiplier in multiplier_map.items():
        selected_table[species_name] = selected_table[species_name] * multiplier
    return selected_table


def _multiplier_mapping(
    species: Sequence[str],
    multipliers: Mapping[str, float] | Sequence[float] | float | None,
) -> dict[str, float]:
    if multipliers is None:
        return dict.fromkeys(species, 1.0)

    if isinstance(multipliers, Mapping):
        return {
            species_name: float(multipliers.get(species_name, 1.0)) for species_name in species
        }

    if isinstance(multipliers, int | float):
        return {species_name: float(multipliers) for species_name in species}

    if len(multipliers) != len(species):
        raise ValueError("multipliers must match the length of species")

    return {
        species_name: float(multiplier)
        for species_name, multiplier in zip(species, multipliers, strict=False)
    }


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
    raise TypeError("initial concentration helpers require xarray.Dataset inputs")


def _megacomplex_scale_mapping(result: object) -> dict[tuple[str, str], float]:
    """Resolve per-dataset, per-megacomplex scales from a result-like object.

    The mapping key is ``(dataset_name, megacomplex_label)`` and values default
    to ``1.0`` if no scale information is available.
    """

    model = getattr(result, "model", None)
    if model is None:
        scheme = getattr(result, "scheme", None)
        model = getattr(scheme, "model", None)
    if model is None:
        return {}

    dataset_models = getattr(model, "dataset", None)
    if not isinstance(dataset_models, Mapping):
        return {}

    parameters = _result_parameters(result)
    scale_map: dict[tuple[str, str], float] = {}

    for dataset_name, dataset_model in dataset_models.items():
        megacomplexes = getattr(dataset_model, "megacomplex", None)
        if not isinstance(megacomplexes, Sequence) or isinstance(megacomplexes, str | bytes):
            continue

        megacomplex_scales = getattr(dataset_model, "megacomplex_scale", None)
        for index, megacomplex in enumerate(megacomplexes):
            mc_label = _label_from_model_item(megacomplex)
            if mc_label is None:
                continue

            scale_value = 1.0
            if (
                isinstance(megacomplex_scales, Sequence)
                and not isinstance(megacomplex_scales, str | bytes)
                and index < len(megacomplex_scales)
            ):
                scale_value = _resolve_parameter_like_value(megacomplex_scales[index], parameters)

            scale_map[(str(dataset_name), mc_label)] = scale_value

    return scale_map


def _result_parameters(result: object) -> object | None:
    optimized_parameters = getattr(result, "optimized_parameters", None)
    if optimized_parameters is not None:
        return optimized_parameters

    scheme = getattr(result, "scheme", None)
    return getattr(scheme, "parameters", None)


def _label_from_model_item(item: object) -> str | None:
    if isinstance(item, str):
        return item

    label = getattr(item, "label", None)
    return str(label) if label is not None else None


def _resolve_parameter_like_value(value: object, parameters: object | None) -> float:
    # Parameter-like values from glotaran typically expose ``.value``.
    if hasattr(value, "value"):
        return float(value.value)  # type:ignore[attr-defined]

    if isinstance(value, str):
        if parameters is not None and hasattr(parameters, "get"):
            try:
                parameter_value = parameters.get(value)
            except (AttributeError, KeyError, TypeError, ValueError):
                return 1.0
            if hasattr(parameter_value, "value"):
                return float(parameter_value.value)  # type:ignore[attr-defined]
            return float(parameter_value)
        return 1.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0
