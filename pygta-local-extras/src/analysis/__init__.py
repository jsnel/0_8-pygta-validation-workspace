"""Analysis helpers for pyglotaran results."""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "add_svd",
    "apply_noise_to_simulated_datasets",
    "collect_irf_datasets",
    "compute_steady_state_spectra",
    "concatenate_result_datasets",
    "drop_scatter",
    "drop_svd",
    "initial_concentration_table",
    "load_dataset_dict_from_nc",
    "plot_concentration_and_spectra",
    "plot_data_fit_residual_rows",
    "plot_final_and_diff_EADS",
    "plot_fitted_IRF_traces",
    "plot_fitted_spectra",
    "plot_fitted_traces_iscience",
    "plot_residual_and_svd",
    "plot_residuals",
    "plot_svd_of_residual",
    "plot_svd_of_residual_grid",
    "save_dataset",
    "save_dataset_dict_to_nc",
    "save_dataset_nodisp",
    "selected_initial_concentration_table",
    "simulate_from_fitted_data",
    "simulate_from_result",
    "simulate_from_result_with_noise",
    "transform_simulated_from_result_poisson_noise",
]

_MODULE_BY_NAME = {
    "add_svd": "pygta_local_extras.analysis.pygta_result_processing",
    "concatenate_result_datasets": "pygta_local_extras.analysis.pygta_result_processing",
    "collect_irf_datasets": "pygta_local_extras.analysis.pygta_result_processing",
    "compute_steady_state_spectra": "pygta_local_extras.analysis.steady_state",
    "drop_scatter": "pygta_local_extras.analysis.pygta_result_processing",
    "drop_svd": "pygta_local_extras.analysis.pygta_result_processing",
    "initial_concentration_table": "pygta_local_extras.analysis.initial_concentration",
    "plot_concentration_and_spectra": "pygta_local_extras.analysis.custom_plotting",
    "plot_data_fit_residual_rows": "pygta_local_extras.analysis.custom_plotting",
    "plot_final_and_diff_EADS": "pygta_local_extras.analysis.custom_plotting",
    "plot_fitted_IRF_traces": "pygta_local_extras.analysis.custom_plotting",
    "plot_fitted_spectra": "pygta_local_extras.analysis.custom_plotting",
    "plot_fitted_traces_iscience": "pygta_local_extras.analysis.custom_plotting",
    "plot_residuals": "pygta_local_extras.analysis.custom_plotting",
    "plot_residual_and_svd": "pygta_local_extras.analysis.custom_plotting",
    "simulate_from_fitted_data": "pygta_local_extras.analysis.simulation",
    "simulate_from_result": "pygta_local_extras.analysis.simulation",
    "simulate_from_result_with_noise": "pygta_local_extras.analysis.simulation",
    "transform_simulated_from_result_poisson_noise": "pygta_local_extras.analysis.simulation",
    "apply_noise_to_simulated_datasets": "pygta_local_extras.analysis.simulation",
    "save_dataset": "pygta_local_extras.analysis.simulation",
    "save_dataset_dict_to_nc": "pygta_local_extras.analysis.simulation",
    "save_dataset_nodisp": "pygta_local_extras.analysis.simulation",
    "load_dataset_dict_from_nc": "pygta_local_extras.analysis.simulation",
    "plot_svd_of_residual": "pygta_local_extras.analysis.custom_plotting",
    "plot_svd_of_residual_grid": "pygta_local_extras.analysis.custom_plotting",
    "selected_initial_concentration_table": "pygta_local_extras.analysis.initial_concentration",
}


def __getattr__(name: str):
    try:
        module_name = _MODULE_BY_NAME[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    return getattr(import_module(module_name), name)
