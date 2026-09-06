"""Shared adapters for the validated v0.7 notebook workflows on v0.8."""

from pathlib import Path

from glotaran.io import load_dataset


class DataStore:
    """Minimal replacement for v0.7 Project data loading in migrated notebooks."""

    def __init__(self):
        self._datasets = {}

    def import_data(self, data, dataset_name, allow_overwrite=False):
        if dataset_name in self._datasets and not allow_overwrite:
            raise ValueError(f"Dataset {dataset_name!r} already exists")
        self._datasets[dataset_name] = load_dataset(data) if isinstance(data, (str, bytes, Path)) else data

    def load_data(self, dataset_name):
        return self._datasets[dataset_name]


def report_real_fit(native_result, scheme_name):
    success = native_result.optimization_info.success
    status = "PASS" if success else "NON_SUCCESS"
    print(
        f"MIGRATION_VALIDATION scheme={scheme_name} real_fit={status} "
        f"termination={native_result.optimization_info.termination_reason!r}"
    )


def simulate(scheme, dataset_label, parameters, coordinates, **kwargs):
    """Call the v0.8 simulator for a named dataset in a migrated scheme."""
    from glotaran.simulation import simulate as _native_simulate

    if not hasattr(scheme, "experiments"):
        return _native_simulate(scheme, dataset_label, parameters, coordinates, **kwargs)
    data_model = next(
        experiment.datasets[dataset_label]
        for experiment in scheme.experiments.values()
        if dataset_label in experiment.datasets
    )
    return _native_simulate(data_model, scheme.library, parameters, coordinates, **kwargs)


def convert_result(native_result, scheme):
    """Project native v0.8 results for legacy plotting while retaining native results."""
    import numpy as np
    import xarray as xr

    if not hasattr(native_result, "optimization_results"):
        return native_result
    from pyglotaran_extras.compat import convert

    compat_result = convert(native_result)
    for dataset_label, dataset in compat_result.data.items():
        if "irf_center" in dataset.coords:
            irf_center = dataset.coords["irf_center"]
            if irf_center.ndim and np.allclose(irf_center, irf_center.values.flat[0]):
                dataset = dataset.drop_vars("irf_center").assign_coords(
                    irf_center=float(irf_center.values.flat[0])
                )
            dataset = dataset.reset_coords("irf_center")
            compat_result.data[dataset_label] = dataset
        optimization_result = native_result.optimization_results[dataset_label]
        global_dimension = optimization_result.meta.global_dimension
        model_dimension = optimization_result.meta.model_dimension
        input_data = optimization_result.input_data
        residual = optimization_result.residuals
        if isinstance(input_data, xr.Dataset):
            input_data = input_data["data"]
        if isinstance(residual, xr.Dataset):
            residual = residual["residual"]
        fitted_data = input_data - residual
        if {"time", "spectral"}.issubset(fitted_data.dims):
            fitted_data = fitted_data.transpose("time", "spectral")
        dataset["fitted_data"] = fitted_data
        data_model = next(
            experiment.datasets[dataset_label]
            for experiment in scheme.experiments.values()
            if dataset_label in experiment.datasets
        )
        weight = xr.ones_like(residual)
        for weight_item in data_model.weights:
            selected = xr.ones_like(residual, dtype=bool)
            if weight_item.global_interval is not None:
                lower, upper = weight_item.global_interval
                selected = selected & (
                    (residual.coords[global_dimension] >= lower)
                    & (residual.coords[global_dimension] <= upper)
                )
            if weight_item.model_interval is not None:
                lower, upper = weight_item.model_interval
                selected = selected & (
                    (residual.coords[model_dimension] >= lower)
                    & (residual.coords[model_dimension] <= upper)
                )
            weight = weight * xr.where(selected, float(weight_item.value), 1.0)
        dataset["weight"] = weight
        dataset["weighted_residual"] = residual * weight
        dataset["clp"] = optimization_result.fit_decomposition.clp.rename(
            amplitude_label="clp_label"
        )
        dataset["matrix"] = optimization_result.fit_decomposition.matrix.rename(
            amplitude_label="clp_label"
        )
        kinetic_elements = [
            element
            for element in optimization_result.elements.values()
            if "compartment" in element.coords
        ]
        for element_label, element in optimization_result.elements.items():
            if "kinetic" not in element.coords:
                continue
            component_dimension = f"component_{element_label}"
            dataset.coords[f"rate_{element_label}"] = element.coords["rate"].rename(
                kinetic=component_dimension
            )
            dataset.coords[f"lifetime_{element_label}"] = element.coords["lifetime"].rename(
                kinetic=component_dimension
            )
        if kinetic_elements:
            legacy_species_order = list(
                dict.fromkeys(
                    compartment
                    for activation in data_model.activations.values()
                    for compartment in activation.compartments
                )
            )
            species_concentration = xr.concat(
                [
                    element["concentrations"].rename(compartment="species")
                    for element in kinetic_elements
                ],
                dim="species",
            )
            species_concentration = species_concentration.isel(
                species=~species_concentration.get_index("species").duplicated()
            )
            species_concentration = species_concentration.sel(
                species=[
                    species
                    for species in legacy_species_order
                    if species in species_concentration.coords["species"].values
                ]
            )
            concentration_order = [
                dimension
                for dimension in (global_dimension, model_dimension, "species")
                if dimension in species_concentration.dims
            ]
            concentration_order.extend(
                dimension
                for dimension in species_concentration.dims
                if dimension not in concentration_order
            )
            dataset["species_concentration"] = species_concentration.transpose(
                *concentration_order
            )
            species_associated_spectra = xr.concat(
                [element["amplitudes"].rename(compartment="species") for element in kinetic_elements],
                dim="species",
            )
            species_associated_spectra = species_associated_spectra.isel(
                species=~species_associated_spectra.get_index("species").duplicated()
            )
            species_associated_spectra = species_associated_spectra.sel(
                species=[
                    species
                    for species in legacy_species_order
                    if species in species_associated_spectra.coords["species"].values
                ]
            )
            spectra_order = [
                dimension
                for dimension in (global_dimension, model_dimension, "species")
                if dimension in species_associated_spectra.dims
            ]
            spectra_order.extend(
                dimension
                for dimension in species_associated_spectra.dims
                if dimension not in spectra_order
            )
            dataset["species_associated_spectra"] = species_associated_spectra.transpose(
                *spectra_order
            )
            initial_concentration = xr.concat(
                [
                    element["initial_concentrations"]
                    .isel(activation=0, drop=True)
                    .rename(compartment="species")
                    for element in kinetic_elements
                ],
                dim="species",
            )
            dataset["initial_concentration"] = initial_concentration.isel(
                species=~initial_concentration.get_index("species").duplicated()
            ).sel(
                species=[
                    species
                    for species in legacy_species_order
                    if species in initial_concentration.coords["species"].values
                ]
            )
            kinetic_compatibility_variables = [
                variable
                for element_label in optimization_result.elements
                for variable in (
                    f"species_concentration_{element_label}",
                    f"species_associated_spectra_{element_label}",
                )
                if variable in dataset
            ]
            dataset = dataset.drop_vars(kinetic_compatibility_variables)
        spectral_elements = [
            element
            for element in optimization_result.elements.values()
            if "shape" in element.coords
        ]
        if spectral_elements:
            species_spectra = xr.concat(
                [
                    element["concentrations"].rename(shape="species").squeeze(
                        [
                            dimension
                            for dimension in element["concentrations"].dims
                            if dimension != "shape"
                            and element["concentrations"].sizes[dimension] == 1
                        ],
                        drop=True,
                    )
                    for element in spectral_elements
                ],
                dim="species",
            )
            spectral_order = [
                dimension
                for dimension in (global_dimension, model_dimension, "species")
                if dimension in species_spectra.dims
            ]
            spectral_order.extend(
                dimension for dimension in species_spectra.dims if dimension not in spectral_order
            )
            dataset["species_spectra"] = species_spectra.transpose(*spectral_order)
        pfid_elements = [
            (element_label, element)
            for element_label, element in optimization_result.elements.items()
            if "oscillation" in element.coords
            and {"amplitudes", "phase", "sin_concentrations", "cos_concentrations"}
            .issubset(element.data_vars)
        ]
        for element_label, element in pfid_elements:
            prefix = "pfid" if len(pfid_elements) == 1 else f"{element_label}_pfid"
            renames = {
                "oscillation": prefix,
                "oscillation_frequency": f"{prefix}_frequency",
                "oscillation_rate": f"{prefix}_rate",
            }
            renames = {
                old: new
                for old, new in renames.items()
                if old in element.coords or old in element.dims
            }
            converted_pfid = element.rename(renames)
            dataset[f"{prefix}_associated_spectra"] = converted_pfid["amplitudes"]
            dataset[f"{prefix}_phase"] = converted_pfid["phase"]
            dataset[f"{prefix}_sin"] = converted_pfid["sin_concentrations"]
            dataset[f"{prefix}_cos"] = converted_pfid["cos_concentrations"]
        if "activation" in dataset.coords and "activation" not in dataset.dims:
            dataset = dataset.reset_coords("activation")
        dataset.attrs["dataset_scale"] = optimization_result.meta.scale
        dataset.attrs["scale"] = optimization_result.meta.scale
        compat_result.data[dataset_label] = dataset
    return compat_result


def matrix_markdown(scheme, element_label, compartments=None):
    """Render a symbolic v0.8 kinetic rate map for legacy notebook display cells."""
    import pandas as pd

    element = scheme.library[element_label]
    compartments = list(compartments or element.compartments)
    table = [["" for _ in compartments] for _ in compartments]
    for (to_compartment, from_compartment), rate in element.rates.items():
        if to_compartment in compartments and from_compartment in compartments:
            table[compartments.index(to_compartment)][compartments.index(from_compartment)] = str(rate)
    return pd.DataFrame(table, index=compartments, columns=compartments).to_markdown()
