"""Custom plotting helpers used across local analysis notebooks."""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterable
from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from cycler import Cycler
from cycler import cycler as cycler_func
from pyglotaran_extras import add_subplot_labels
from pyglotaran_extras.io.utils import result_dataset_mapping
from pyglotaran_extras.plotting.plot_concentrations import plot_concentrations
from pyglotaran_extras.plotting.plot_irf_dispersion_center import _plot_irf_dispersion_center
from pyglotaran_extras.plotting.plot_residual import plot_residual
from pyglotaran_extras.plotting.plot_spectra import plot_das
from pyglotaran_extras.plotting.plot_spectra import plot_norm_das
from pyglotaran_extras.plotting.plot_spectra import plot_norm_sas
from pyglotaran_extras.plotting.plot_spectra import plot_sas
from pyglotaran_extras.plotting.plot_svd import plot_lsv_residual
from pyglotaran_extras.plotting.plot_svd import plot_rsv_residual
from pyglotaran_extras.plotting.plot_traces import plot_fitted_traces
from pyglotaran_extras.plotting.style import PlotStyle
from pyglotaran_extras.plotting.utils import MinorSymLogLocator
from pyglotaran_extras.plotting.utils import add_cycler_if_not_none
from pyglotaran_extras.plotting.utils import extract_dataset_scale
from pyglotaran_extras.plotting.utils import extract_irf_location
from pyglotaran_extras.types import ResultLike
from ruamel.yaml import YAML

DEFAULT_FITTED_SPECTRA_CYCLER = PlotStyle().data_cycler_solid_dashed


def _format_lifetime_label(lifetime: float) -> str:
    if not math.isfinite(lifetime):
        return str(lifetime)
    abs_lifetime = abs(lifetime)
    if abs_lifetime < 1e3:
        value = lifetime
        unit = "ps"
    elif abs_lifetime < 1e6:
        value = lifetime / 1000
        unit = "ns"
    elif abs_lifetime < 1e9:
        value = lifetime / 1e6
        unit = "us"
    elif abs_lifetime < 1e13:
        value = lifetime / 1e9
        unit = "ms"
    else:
        value = lifetime / 1e12
        unit = "s"
    return f"{value:.3g} {unit}"


def _main_megacomplex_label(result_dataset) -> str | None:
    plotted_species = set(result_dataset.coords.get("species", []).values.tolist())
    best_label = None
    best_overlap = -1

    for var_name in result_dataset.data_vars:
        if not var_name.startswith("a_matrix_"):
            continue
        label = var_name.removeprefix("a_matrix_")
        species_coord = f"species_{label}"
        lifetime_coord = f"lifetime_{label}"
        if (
            species_coord not in result_dataset.coords
            or lifetime_coord not in result_dataset.coords
        ):
            continue
        species = set(result_dataset.coords[species_coord].values.tolist())
        overlap = len(species & plotted_species)
        if overlap > best_overlap:
            best_label = label
            best_overlap = overlap

    return best_label


def _species_display_labels(result_dataset, show_lifetimes: bool) -> tuple[list[str], list[str]]:
    if "species" not in result_dataset.coords:
        return [], []

    species = [
        str(species_name) for species_name in result_dataset.coords["species"].values.tolist()
    ]
    if not show_lifetimes:
        return species, species

    main_label = _main_megacomplex_label(result_dataset)
    if main_label is None:
        return species, species

    a_matrix = result_dataset[f"a_matrix_{main_label}"]
    component_dim, species_dim = a_matrix.dims
    lifetime_coord = f"lifetime_{main_label}"
    species_coord = f"species_{main_label}"

    lifetimes = a_matrix.coords[lifetime_coord].values.tolist()
    source_species = [
        str(species_name) for species_name in a_matrix.coords[species_coord].values.tolist()
    ]

    if len(source_species) == len(lifetimes):
        species_labels = {
            species_name: _format_lifetime_label(float(lifetime))
            for species_name, lifetime in zip(source_species, lifetimes, strict=False)
        }
        return species, [
            species_labels.get(species_name, species_name) for species_name in species
        ]

    a_matrix_values = a_matrix.transpose(component_dim, species_dim).values

    species_labels: dict[str, str] = {}
    for column_index, species_name in enumerate(source_species):
        weights = [abs(float(value)) for value in a_matrix_values[:, column_index]]
        if not weights:
            continue
        dominant_index = max(range(len(weights)), key=weights.__getitem__)
        species_labels[species_name] = _format_lifetime_label(float(lifetimes[dominant_index]))

    return species, [species_labels.get(species_name, species_name) for species_name in species]


def _relabel_new_lines(
    ax, start_index: int, species_labels: list[str], display_labels: list[str]
) -> None:
    new_lines = ax.lines[start_index:]
    if not new_lines or not species_labels:
        return

    if len(new_lines) % len(species_labels) != 0:
        return

    repeat_count = len(new_lines) // len(species_labels)
    repeated_species = species_labels * repeat_count
    repeated_display = display_labels * repeat_count
    for line, species_name, display_label in zip(
        new_lines, repeated_species, repeated_display, strict=False
    ):
        line.set_gid(species_name)
        line.set_label(display_label)


def _refresh_legend(ax) -> None:
    handles, labels = ax.get_legend_handles_labels()
    visible = [
        (handle, label)
        for handle, label in zip(handles, labels, strict=False)
        if label and not label.startswith("_")
    ]
    if not visible:
        return

    legend = ax.get_legend()
    if legend is not None:
        legend.remove()
    visible_handles, visible_labels = zip(*visible, strict=False)
    ax.legend(visible_handles, visible_labels)


def plot_concentration_and_spectra(
    result_datasets: list,
    cycler=None,
    spectra_cycler=None,
    das_cycler=None,
    labels=None,
    show_DADS=True,
    show_nDADS=False,
    show_nSADS=False,
    axes=None,
    annotate_labels=True,
    linthresh=None,
    show_lifetimes=False,
):
    sads_axis_index = 1
    current_axis_index = 2
    nsads_axis_index = current_axis_index if show_nSADS else None
    if show_nSADS:
        current_axis_index += 1
    dads_axis_index = current_axis_index if show_DADS else None
    if show_DADS:
        current_axis_index += 1
    ndads_axis_index = current_axis_index if show_nDADS else None
    if show_nDADS:
        current_axis_index += 1
    n_axes = current_axis_index
    if axes is None:
        fig, axes = plt.subplots(1, n_axes, figsize=(15, 4))
    else:
        axes = tuple(axes)
        if len(axes) != n_axes:
            raise ValueError(f"Expected {n_axes} axes, got {len(axes)}.")
        fig = axes[0].figure
    cyclers = cycler if isinstance(cycler, list | tuple) else [cycler] * len(result_datasets)
    if spectra_cycler is None:
        spectra_cyclers = cyclers
    elif isinstance(spectra_cycler, list | tuple):
        spectra_cyclers = spectra_cycler
    else:
        spectra_cyclers = [spectra_cycler] * len(result_datasets)
    if annotate_labels and labels is None:
        labels = tuple(chr(ord("A") + idx) for idx in range(n_axes))
    for idx, result_dataset in enumerate(result_datasets):
        cycler = cyclers[idx]
        species_labels, display_labels = _species_display_labels(result_dataset, show_lifetimes)

        line_count = len(axes[0].lines)
        plot_concentrations(
            result_dataset, axes[0], center_λ=0, linlog=True, cycler=cycler, linthresh=linthresh
        )
        _relabel_new_lines(axes[0], line_count, species_labels, display_labels)

        line_count = len(axes[sads_axis_index].lines)
        plot_sas(result_dataset, axes[sads_axis_index], cycler=spectra_cyclers[idx])
        _relabel_new_lines(axes[sads_axis_index], line_count, species_labels, display_labels)
        if show_nSADS:
            line_count = len(axes[nsads_axis_index].lines)
            plot_norm_sas(result_dataset, axes[nsads_axis_index], cycler=spectra_cyclers[idx])
            _relabel_new_lines(axes[nsads_axis_index], line_count, species_labels, display_labels)
        if show_DADS:
            plot_das(result_dataset, axes[dads_axis_index], cycler=das_cycler)
        if show_nDADS:
            plot_norm_das(result_dataset, axes[ndads_axis_index], cycler=das_cycler)
    axes[0].axhline(0, color="k", linewidth=1)
    axes[sads_axis_index].axhline(0, color="k", linewidth=1)
    if annotate_labels:
        axes[0].annotate(labels[0], xy=(-0.05, 1.02), xycoords="axes fraction", fontsize=16)
        for axis_index, label in enumerate(labels[1:], start=1):
            axes[axis_index].annotate(
                label, xy=(-0.05, 1.02), xycoords="axes fraction", fontsize=16
            )

    if show_lifetimes:
        _refresh_legend(axes[0])
        _refresh_legend(axes[sads_axis_index])
        if show_nSADS:
            _refresh_legend(axes[nsads_axis_index])

    return fig, axes


def plot_residual_and_svd(result_datasets: list, indices=None):
    fig, axes = plt.subplots(1, 3, figsize=(10, 2))
    if indices is None:
        indices = [0]
    for result_dataset in result_datasets:
        plot_residual(result_dataset, axes[0])
        plot_lsv_residual(result_dataset, axes[1], indices=indices)
        plot_rsv_residual(result_dataset, axes[2], indices=indices)
    axes[0].get_legend().remove()
    axes[0].set_ylabel("Wavelength (nm)")
    axes[1].get_legend().remove()
    axes[1].set_ylabel("")
    axes[1].set_title("residual 1st LSV")
    axes[2].set_xlabel("Wavelength (nm)")
    axes[0].set_xlabel("Time (ps)")
    axes[1].set_xlabel("Time (ps)")
    axes[2].set_title("residual 1st RSV")
    axes[2].get_legend().remove()
    axes[2].set_ylabel("")

    return fig, axes


def _custom_cyclers_for_svd_residual():
    return (
        cycler_func(color=["tab:grey"]),
        cycler_func(color=["k"]),
        cycler_func(color=["tab:orange"]),
        cycler_func(color=["r"]),
    )


def _prepare_residual_svd_for_plot(result_dataset: ResultLike):
    from glotaran.io.prepare_dataset import add_svd_to_dataset

    residual = result_dataset.get("residual")
    if residual is None or not {"time", "spectral"}.issubset(residual.dims):
        return result_dataset

    plotting_dataset = result_dataset.copy(deep=False)
    svd_variables = [
        name
        for name in plotting_dataset.data_vars
        if name.startswith(("residual_", "weighted_residual_"))
    ]
    if svd_variables:
        plotting_dataset = plotting_dataset.drop_vars(svd_variables)

    for name in ("residual", "weighted_residual"):
        if name not in plotting_dataset:
            continue
        plotting_dataset[name] = plotting_dataset[name].transpose("time", "spectral")
        add_svd_to_dataset(
            plotting_dataset,
            name=name,
            lsv_dim="time",
            rsv_dim="spectral",
        )
    return plotting_dataset


def _plot_svd_of_residual_on_axes(
    result_datasets: Sequence[ResultLike],
    axes,
    *,
    linlog: bool,
    linthresh: float,
    index: int,
    labels: Sequence[str] | None = None,
    show_titles: bool = True,
    show_bottom_labels: bool = True,
    legend_column: int | None = 1,
):
    custom_cyclers = _custom_cyclers_for_svd_residual()
    lsv_handles = []
    rsv_handles = []

    for idx, result_dataset in enumerate(result_datasets):
        result_dataset = _prepare_residual_svd_for_plot(result_dataset)
        center_λ = min(
            result_dataset.sizes["spectral"], round(result_dataset.sizes["spectral"] / 2)
        )
        irf_location = extract_irf_location(result_dataset, center_λ, 0)
        custom_cycler = custom_cyclers[idx % len(custom_cyclers)]
        label = None if labels is None else labels[idx]

        plot_lsv_residual(
            result_dataset,
            axes[0],
            indices=[index],
            linlog=linlog,
            linthresh=linthresh,
            irf_location=irf_location,
            cycler=custom_cycler,
        )
        lsv_handle = axes[0].lines[-1]
        if label is not None:
            lsv_handle.set_label(label)
        lsv_handles.append(lsv_handle)

        plot_rsv_residual(result_dataset, axes[1], indices=[index], cycler=custom_cycler)
        rsv_handle = axes[1].lines[-1]
        if label is not None:
            rsv_handle.set_label(label)
        rsv_handles.append(rsv_handle)

    axes[0].set_ylabel("")
    axes[1].set_ylabel("")
    axes[0].set_xlabel("Time (ps)" if show_bottom_labels else "")
    axes[1].set_xlabel("Wavelength (nm)" if show_bottom_labels else "")
    axes[0].set_title("residual 1st LSV" if show_titles else "")
    axes[1].set_title("residual 1st RSV" if show_titles else "")

    for axis_index, (axis, handles) in enumerate(
        zip(axes, (lsv_handles, rsv_handles), strict=False)
    ):
        existing_legend = axis.get_legend()
        if existing_legend is not None:
            existing_legend.remove()
        if labels is not None and axis_index == legend_column:
            axis.legend(handles=handles)

    return axes


def plot_svd_of_residual(
    result_datasets: list,
    linlog,
    linthresh,
    index,
):
    fig, axes = plt.subplots(1, 2, figsize=(10, 2))
    _plot_svd_of_residual_on_axes(
        result_datasets,
        axes,
        linlog=linlog,
        linthresh=linthresh,
        index=index,
    )
    return fig, axes


def plot_svd_of_residual_grid(
    dataset_rows: Sequence[Sequence[tuple[str, ResultLike]]],
    *,
    linlog: bool,
    linthresh: float,
    index: int,
    figsize: tuple[float, float] = (10, 7.5),
):
    fig, axes = plt.subplots(len(dataset_rows), 2, figsize=figsize, constrained_layout=True)
    row_axes = [axes] if len(dataset_rows) == 1 else axes

    for row_index, row in enumerate(dataset_rows):
        labels, datasets = zip(*row, strict=False)
        _plot_svd_of_residual_on_axes(
            datasets,
            row_axes[row_index],
            linlog=linlog,
            linthresh=linthresh,
            index=index,
            labels=labels,
            show_titles=row_index == 0,
            show_bottom_labels=row_index == len(dataset_rows) - 1,
            legend_column=1,
        )

    add_subplot_labels(axes, label_format_function="upper_case_letter")

    return fig, axes


def plot_final_and_diff_EADS(result_dataset1, result_dataset2, scale=1.0):
    fig, axes = plt.subplots(1, 2, figsize=(15, 4))
    idx1 = len(result_dataset1.species_associated_spectra.species) - 1
    idx2 = len(result_dataset2.species_associated_spectra.species) - 1
    final1 = result_dataset1.species_associated_spectra[:, idx1]
    final2 = scale * result_dataset2.species_associated_spectra[:, idx2]
    diff = final1 - final2
    final1.plot.line(x="spectral", ax=axes[0], color="k", label="700 exc")
    final2.plot.line(x="spectral", ax=axes[0], color="r", label="670 exc")
    diff.plot.line(x="spectral", ax=axes[1])
    axes[0].set_xlabel("Wavelength (nm)")
    axes[0].set_ylabel("EADS (mOD)")
    axes[0].set_title("final EADS")
    axes[0].axhline(0, color="k", linewidth=1)
    axes[1].set_xlabel("Wavelength (nm)")
    axes[1].set_ylabel("difference (mOD)")
    axes[1].set_title("difference final EADS")
    axes[1].axhline(0, color="k", linewidth=1)
    axes[0].legend()
    axes[0].annotate("A", xy=(-0.05, 1.02), xycoords="axes fraction", fontsize=16)
    axes[1].annotate("B", xy=(-0.05, 1.02), xycoords="axes fraction", fontsize=16)
    return fig, axes


def _paired_data_fit_colors(index: int) -> tuple[str, str]:
    colors = PlotStyle().data_cycler_solid.by_key()["color"]
    data_color = colors[(2 * index) % len(colors)]
    fit_color = colors[(2 * index + 1) % len(colors)]
    return data_color, fit_color


def _compute_fwhm(time: np.ndarray, fitted_data: np.ndarray) -> float:
    finite_mask = np.isfinite(time) & np.isfinite(fitted_data)
    x_vals = time[finite_mask]
    y_vals = fitted_data[finite_mask]
    if x_vals.size < 3:
        return math.nan

    peak_index = int(np.argmax(y_vals))
    peak_value = float(y_vals[peak_index])
    if peak_index == 0 or peak_index == y_vals.size - 1 or peak_value <= 0:
        return math.nan

    half_max = peak_value / 2
    left_candidates = np.where(y_vals[:peak_index] < half_max)[0]
    right_candidates = np.where(y_vals[peak_index + 1 :] < half_max)[0]
    if left_candidates.size == 0 or right_candidates.size == 0:
        return math.nan

    left_index = int(left_candidates[-1])
    right_index = int(peak_index + 1 + right_candidates[0])

    def interpolate_crossing(idx_low: int, idx_high: int) -> float:
        x_low = float(x_vals[idx_low])
        x_high = float(x_vals[idx_high])
        y_low = float(y_vals[idx_low])
        y_high = float(y_vals[idx_high])
        if y_high == y_low:
            return x_low
        return x_low + (half_max - y_low) * (x_high - x_low) / (y_high - y_low)

    left_crossing = interpolate_crossing(left_index, left_index + 1)
    right_crossing = interpolate_crossing(right_index - 1, right_index)
    return float(right_crossing - left_crossing)


def _iter_irf_trace_arrays(
    result_dataset,
    *,
    center_λ: float | None,
    main_irf_nr: int,
    divide_by_scale: bool,
):
    spectral_coords = result_dataset.coords.get("spectral")
    if spectral_coords is None or spectral_coords.to_numpy().size == 0:
        scale = extract_dataset_scale(result_dataset, divide_by_scale)
        irf_location = extract_irf_location(result_dataset, center_λ, main_irf_nr)
        trace_dataset = result_dataset.assign_coords(
            time=result_dataset.coords["time"] - irf_location
        )
        time = np.asarray(trace_dataset.coords["time"].to_numpy(), dtype=float)
        data = np.asarray((trace_dataset.data / scale).squeeze(drop=True).to_numpy(), dtype=float)
        fitted = np.asarray(
            (trace_dataset.fitted_data / scale).squeeze(drop=True).to_numpy(), dtype=float
        )
        yield None, time, data, fitted
        return

    for spectral_value in spectral_coords.to_numpy():
        trace_dataset = result_dataset.sel(spectral=[spectral_value], method="nearest")
        actual_spectral = float(trace_dataset.coords["spectral"].item())
        scale = extract_dataset_scale(result_dataset, divide_by_scale, spectral=actual_spectral)
        irf_location = extract_irf_location(trace_dataset, center_λ, main_irf_nr)
        trace_dataset = trace_dataset.assign_coords(
            time=trace_dataset.coords["time"] - irf_location
        )
        time = np.asarray(trace_dataset.coords["time"].to_numpy(), dtype=float)
        data = np.asarray((trace_dataset.data / scale).squeeze(drop=True).to_numpy(), dtype=float)
        fitted = np.asarray(
            (trace_dataset.fitted_data / scale).squeeze(drop=True).to_numpy(), dtype=float
        )
        yield actual_spectral, time, data, fitted


def _plot_fitted_irf_traces_on_axis(
    result: ResultLike,
    ax,
    *,
    center_λ: float | None,
    main_irf_nr: int,
    linlog: bool,
    linthresh: float,
    divide_by_scale: bool,
    normalize_to_fitted: bool,
    y_label: str,
    show_zero_line: bool,
) -> None:
    result_map = result_dataset_mapping(result)
    plotted_any = False
    trace_index = 0

    for dataset_name, result_dataset in result_map.items():
        if result_dataset.coords["time"].to_numpy().size <= 1:
            continue

        for spectral_value, time, data, fitted in _iter_irf_trace_arrays(
            result_dataset,
            center_λ=center_λ,
            main_irf_nr=main_irf_nr,
            divide_by_scale=divide_by_scale,
        ):
            normalization = 1.0
            if normalize_to_fitted:
                fitted_max = float(np.nanmax(fitted))
                if math.isfinite(fitted_max) and fitted_max != 0:
                    normalization = fitted_max

            data_color, fit_color = _paired_data_fit_colors(trace_index)
            dataset_prefix = f"{dataset_name} " if len(result_map) > 1 else ""
            trace_label = dataset_prefix.rstrip()
            if spectral_value is not None:
                trace_label = f"{dataset_prefix}{float(spectral_value):.6g} nm".strip()
            fwhm = _compute_fwhm(time, fitted)
            label = f"{trace_label} ({fwhm:.3g} ps)" if math.isfinite(fwhm) else trace_label

            ax.plot(time, data / normalization, color=data_color, linewidth=1.25)
            ax.plot(time, fitted / normalization, color=fit_color, linewidth=1.75, label=label)
            plotted_any = True
            trace_index += 1

    if not plotted_any:
        ax.set_visible(False)
        return

    if linlog:
        ax.set_xscale("symlog", linthresh=linthresh)
        ax.xaxis.set_minor_locator(MinorSymLogLocator(linthresh))
    if show_zero_line:
        ax.axhline(0, color="k", linewidth=1)
    ax.set_ylabel(y_label)
    ax.legend()


def plot_fitted_IRF_traces(
    results: Sequence[ResultLike],
    axes_shape: tuple[int, int] = (2, 2),
    center_λ: float | None = None,
    main_irf_nr: int = 0,
    linlog: bool = True,
    linthresh: float = 100,
    divide_by_scale: bool = True,
    normalize_to_fitted: bool = False,
    figsize: tuple[float, float] = (14, 8),
    title: str = "IRF fit overview",
    y_label: str = "a.u.",
    show_zero_line: bool = True,
):
    """Plot IRF trace overlays for multiple result objects on a subplot grid.

    Each subplot corresponds to one result object from ``results``. For every dataset in a result,
    all available spectral traces are overlaid on that subplot with light colors for the data and
    matching dark colors for the fitted traces. The legend only lists the fitted traces, annotated
    with wavelength and full width at half maximum (FWHM) in ps.
    """

    fig, axes = plt.subplots(*axes_shape, figsize=figsize, squeeze=False)
    flat_axes = axes.flatten()
    if len(results) > len(flat_axes):
        msg = (
            f"The number of result objects ({len(results)}) exceeds the available subplot axes "
            f"({len(flat_axes)}). Increase axes_shape to fit all results."
        )
        raise ValueError(msg)

    for result, ax in zip(results, flat_axes, strict=False):
        _plot_fitted_irf_traces_on_axis(
            result,
            ax,
            center_λ=center_λ,
            main_irf_nr=main_irf_nr,
            linlog=linlog,
            linthresh=linthresh,
            divide_by_scale=divide_by_scale,
            normalize_to_fitted=normalize_to_fitted,
            y_label=y_label,
            show_zero_line=show_zero_line,
        )

    for ax in flat_axes[len(results) :]:
        ax.set_visible(False)

    visible_row_indices = [
        row_index
        for row_index, row_axes in enumerate(axes)
        if any(ax.get_visible() for ax in row_axes)
    ]
    bottom_row_index = max(visible_row_indices, default=None)
    for row_index, row_axes in enumerate(axes):
        for ax in row_axes:
            if not ax.get_visible():
                continue
            ax.set_xlabel("Time (ps)" if row_index == bottom_row_index else "")

    fig.suptitle(title, fontsize=28)
    fig.tight_layout()
    return fig, axes


def plot_fitted_traces_iscience(
    result: ResultLike,
    wavelengths: Iterable[float],
    axes_shape: tuple[int, int] = (4, 4),
    center_λ: float | None = None,
    main_irf_nr: int = 0,
    linlog: bool = False,
    linthresh: float = 1,
    divide_by_scale: bool = True,
    per_axis_legend: bool = False,
    figsize: tuple[float, float] = (30, 15),
    title: str = "Fit overview",
    y_label: str = "a.u.",
    cycler: Cycler | None = PlotStyle().data_cycler_solid,  # noqa: B008
    show_zero_line: bool = True,
):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fig, ax_ = plot_fitted_traces(
            result,
            wavelengths,
            linlog=linlog,
            linthresh=linthresh,
            axes_shape=axes_shape,
            figsize=figsize,
            title=title,
            per_axis_legend=per_axis_legend,
            cycler=cycler,
            center_λ=center_λ,
            main_irf_nr=main_irf_nr,
            y_label=y_label,
            show_zero_line=show_zero_line,
            divide_by_scale=divide_by_scale,
        )
        handles, labels = ax_.flatten()[0].get_legend_handles_labels()
        for i in range(len(handles)):
            if i == 1:
                labels[i] = "670 nm excitation"
            elif i == 5:
                labels[i] = "700 nm excitation"
            else:
                labels[i] = "_Hidden"
        for idx, ax in enumerate(ax_.flatten()):
            ax.set_ylabel(ax.title.get_text().replace("spectral = ", ""))
            if idx > 1:
                ax.set_xlabel("Time (ps)")
            else:
                ax.set_xlabel("")
            ax.set_title("")
            if ax.get_legend() is not None:
                ax.get_legend().remove()
            for line in ax.lines:
                line.set_linewidth(0.5)
        fig.legend(
            handles,
            labels,
            bbox_to_anchor=(0.5, -0.05),
            loc="lower center",
            ncol=len(handles),
        )
        fig.tight_layout()
        return fig, ax_


def _plot_data_and_fits_for_timepoint(
    result: ResultLike,
    timepoint: float,
    ax,
    *,
    cycler: Cycler | None,
    divide_by_scale: bool,
    per_axis_legend: bool,
    show_zero_line: bool,
    xmin: float | None,
    xmax: float | None,
) -> None:
    result_map = result_dataset_mapping(result)

    add_cycler_if_not_none(ax, cycler)

    for dataset_name, result_dataset in result_map.items():
        time_coords = np.asarray(result_dataset.coords["time"].to_numpy(), dtype=float)
        if time_coords.size <= 1:
            continue
        if time_coords.min() <= timepoint <= time_coords.max():
            result_data = result_dataset.sel(time=[timepoint], method="nearest")
            actual_time = float(result_data.coords["time"].item())
            scale = extract_dataset_scale(result_dataset, divide_by_scale)
            (result_data.data / scale).plot(
                x="spectral",
                ax=ax,
                label=f"{dataset_name}_data @ {actual_time:.4g} ps",
            )
            (result_data.fitted_data / scale).plot(
                x="spectral",
                ax=ax,
                label=f"{dataset_name}_fit @ {actual_time:.4g} ps",
            )

    if show_zero_line:
        ax.axhline(0, color="k", linewidth=1)
    ax.set_xlim(left=xmin, right=xmax)
    if per_axis_legend:
        ax.legend()


def plot_fitted_spectra(
    result: ResultLike,
    timepoints: Iterable[float],
    axes_shape: tuple[int, int] = (4, 4),
    divide_by_scale: bool = True,
    per_axis_legend: bool = False,
    figsize: tuple[float, float] = (30, 15),
    title: str | None = "Spectrum fit overview",
    y_label: str = "a.u.",
    x_label: str = "Wavelength (nm)",
    show_zero_line: bool = True,
    xmin: float | None = None,
    xmax: float | None = None,
    cycler: Cycler | None = DEFAULT_FITTED_SPECTRA_CYCLER,
):
    """Plot data and fit spectra for selected ``timepoints`` on a subplot grid."""

    fig, axes = plt.subplots(*axes_shape, figsize=figsize, squeeze=False)
    flat_axes = axes.flatten()
    timepoint_values = [float(timepoint) for timepoint in timepoints]
    tick_label_size = plt.rcParams.get("xtick.labelsize", 10)

    for timepoint, axis in zip(timepoint_values, flat_axes, strict=False):
        _plot_data_and_fits_for_timepoint(
            result,
            timepoint,
            axis,
            cycler=cycler,
            divide_by_scale=divide_by_scale,
            per_axis_legend=per_axis_legend,
            show_zero_line=show_zero_line,
            xmin=xmin,
            xmax=xmax,
        )
        axis.text(
            0.97,
            0.03,
            f"{timepoint:.4g} ps",
            transform=axis.transAxes,
            fontsize=tick_label_size,
            va="bottom",
            ha="right",
            bbox={"facecolor": "white", "alpha": 0.6, "edgecolor": "none", "pad": 1.0},
        )

    for axis in flat_axes[len(timepoint_values) :]:
        axis.set_visible(False)

    visible_row_indices = [
        row_index
        for row_index, row_axes in enumerate(axes)
        if any(axis.get_visible() for axis in row_axes)
    ]
    bottom_row_index = max(visible_row_indices, default=None)

    for row_index, row_axes in enumerate(axes):
        for axis in row_axes:
            if not axis.get_visible():
                continue
            axis.set_title("")
            axis.set_ylabel("")
            axis.set_xlabel(x_label if row_index == bottom_row_index else "")

    if title is not None and title != "":
        fig.suptitle(title, fontsize=28)
        # Reserve space at the top so the figure title never overlaps panels.
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    else:
        fig.tight_layout()
    return fig, axes


def _residual_plot_mode_label(*, weighted_residual: bool, plot_weights: bool) -> str:
    if plot_weights:
        return "weight"
    if weighted_residual:
        return "weighted residual"
    return "residual"


def _residual_trace_for_wavelength(
    result_dataset,
    wavelength: float,
    *,
    center_λ: float | None,
    main_irf_nr: int,
    weighted_residual: bool,
    plot_weights: bool,
    divide_by_scale: bool,
):
    trace_dataset = result_dataset.sel(spectral=[wavelength], method="nearest")
    actual_spectral = float(trace_dataset.coords["spectral"].item())
    scale = (
        1.0
        if plot_weights
        else extract_dataset_scale(result_dataset, divide_by_scale, spectral=actual_spectral)
    )
    irf_location = extract_irf_location(trace_dataset, center_λ, main_irf_nr)
    trace_dataset = trace_dataset.assign_coords(time=trace_dataset.coords["time"] - irf_location)
    time = np.asarray(trace_dataset.coords["time"].to_numpy(), dtype=float)

    if plot_weights:
        if "weight" not in trace_dataset:
            return None
        values = np.asarray(
            (trace_dataset.weight / scale).squeeze(drop=True).to_numpy(), dtype=float
        )
    elif weighted_residual:
        if "weighted_residual" in trace_dataset:
            values = np.asarray(
                (trace_dataset.weighted_residual / scale).squeeze(drop=True).to_numpy(),
                dtype=float,
            )
        else:
            if "residual" not in trace_dataset or "weight" not in trace_dataset:
                return None
            residual = np.asarray(
                (trace_dataset.residual / scale).squeeze(drop=True).to_numpy(), dtype=float
            )
            weight = np.asarray(
                (trace_dataset.weight / scale).squeeze(drop=True).to_numpy(), dtype=float
            )
            values = residual * weight
    else:
        if "residual" not in trace_dataset:
            return None
        values = np.asarray(
            (trace_dataset.residual / scale).squeeze(drop=True).to_numpy(), dtype=float
        )

    return actual_spectral, time, values


def _tight_residual_y_limits(
    axis,
    values: np.ndarray,
    *,
    weighted_residual: bool,
    plot_weights: bool,
) -> None:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return

    if weighted_residual:
        # Keep full range visible without forcing symmetry around zero.
        lower = float(np.min(finite))
        upper = float(np.max(finite))
        if not np.isfinite(lower) or not np.isfinite(upper):
            return
        if upper <= lower:
            span = abs(upper) if upper != 0 else 1.0
            axis.set_ylim(lower - 0.1 * span, upper + 0.1 * span)
            return
        pad = 0.08 * (upper - lower)
        axis.set_ylim(lower - pad, upper + pad)
        return

    if plot_weights:
        # Keep full range visible (0th to 100th percentile).
        lower = float(np.min(finite))
        upper = float(np.max(finite))
        if not np.isfinite(lower) or not np.isfinite(upper):
            return
        if upper <= lower:
            span = abs(upper) if upper != 0 else 1.0
            axis.set_ylim(lower - 0.1 * span, upper + 0.1 * span)
            return
        pad = 0.08 * (upper - lower)
        # Weights are expected to be non-negative for most datasets.
        axis.set_ylim(max(0.0, lower - pad), upper + pad)
        return


def _axis_plotted_y_values(axis) -> np.ndarray:
    y_segments: list[np.ndarray] = []
    for line in axis.lines:
        y = np.atleast_1d(np.asarray(line.get_ydata(), dtype=float)).ravel()
        if y.size:
            y_segments.append(y)
    if not y_segments:
        return np.array([], dtype=float)
    return np.concatenate(y_segments)


def _plot_residuals_on_axes(
    result: ResultLike,
    axes,
    wavelengths: Iterable[float],
    *,
    center_λ: float | None,
    main_irf_nr: int,
    weighted_residual: bool,
    plot_weights: bool,
    linlog: bool,
    linthresh: float,
    divide_by_scale: bool,
    show_zero_line: bool,
) -> None:
    result_map = result_dataset_mapping(result)
    flat_axes = np.atleast_1d(axes).flatten()

    color_cycle = PlotStyle().data_cycler_solid.by_key()["color"]

    for axis, wavelength in zip(flat_axes, wavelengths, strict=False):
        plotted_any = False
        title_wavelength = float(wavelength)
        for dataset_index, (dataset_name, result_dataset) in enumerate(result_map.items()):
            trace = _residual_trace_for_wavelength(
                result_dataset,
                wavelength,
                center_λ=center_λ,
                main_irf_nr=main_irf_nr,
                weighted_residual=weighted_residual,
                plot_weights=plot_weights,
                divide_by_scale=divide_by_scale,
            )
            if trace is None:
                continue
            actual_spectral, time, values = trace
            title_wavelength = actual_spectral
            color = color_cycle[dataset_index % len(color_cycle)]
            label = dataset_name if len(result_map) > 1 else None
            axis.plot(time, values, color=color, linewidth=1.25, label=label)
            plotted_any = True

        if not plotted_any:
            axis.set_visible(False)
            continue
        if linlog:
            axis.set_xscale("symlog", linthresh=linthresh)
            axis.xaxis.set_minor_locator(MinorSymLogLocator(linthresh))
        if show_zero_line and not plot_weights:
            axis.axhline(0, color="k", linewidth=1)
        axis.set_title(f"{title_wavelength:.6g} nm")
        axis.set_ylabel(
            _residual_plot_mode_label(
                weighted_residual=weighted_residual, plot_weights=plot_weights
            )
        )
        if weighted_residual or plot_weights:
            # Match default matplotlib behavior while keeping a tiny margin.
            axis.relim()
            axis.autoscale_view(scalex=False, scaley=True)
            axis.margins(y=0.02)
        if axis.get_legend() is not None:
            axis.get_legend().remove()

    if len(result_map) > 1:
        axes_array = np.atleast_2d(axes)
        legend_axis = None
        for row_axes in axes_array:
            visible_axes = [axis for axis in row_axes if axis.get_visible()]
            if visible_axes:
                legend_axis = visible_axes[-1]
                break
        if legend_axis is not None:
            handles, labels = legend_axis.get_legend_handles_labels()
            if handles:
                legend_axis.legend(handles, labels, loc="upper right")


def plot_residuals(
    result: ResultLike,
    wavelengths: Iterable[float],
    axes_shape: tuple[int, int] = (4, 4),
    center_λ: float | None = None,
    main_irf_nr: int = 0,
    weighted_residual: bool = False,
    plot_weights: bool = False,
    linlog: bool = False,
    linthresh: float = 1,
    divide_by_scale: bool = True,
    figsize: tuple[float, float] = (30, 15),
    title: str = "Residual overview",
    show_zero_line: bool = True,
):
    """Plot residual overlays in separate wavelength panels.

    The default mode plots plain residuals. Set ``weighted_residual=True`` to
    plot weighted residuals, or ``plot_weights=True`` to plot the weights
    instead of residuals.
    """
    wavelengths = tuple(wavelengths)
    fig, ax_ = plt.subplots(*axes_shape, figsize=figsize, squeeze=False)
    flat_axes = ax_.flatten()
    if len(wavelengths) > len(flat_axes):
        msg = (
            f"The number of wavelengths ({len(wavelengths)}) exceeds the available subplot axes "
            f"({len(flat_axes)}). Increase axes_shape to fit all wavelengths."
        )
        raise ValueError(msg)

    _plot_residuals_on_axes(
        result,
        ax_,
        wavelengths,
        center_λ=center_λ,
        main_irf_nr=main_irf_nr,
        weighted_residual=weighted_residual,
        plot_weights=plot_weights,
        linlog=linlog,
        linthresh=linthresh,
        divide_by_scale=divide_by_scale,
        show_zero_line=show_zero_line,
    )

    for ax in flat_axes[len(wavelengths) :]:
        ax.set_visible(False)

    visible_row_indices = [
        row_index
        for row_index, row_axes in enumerate(ax_)
        if any(axis.get_visible() for axis in row_axes)
    ]
    bottom_row_index = max(visible_row_indices, default=None)
    for row_index, row_axes in enumerate(ax_):
        for axis in row_axes:
            if not axis.get_visible():
                continue
            axis.set_xlabel("Time (ps)" if row_index == bottom_row_index else "")

    fig.suptitle(title, fontsize=28)
    fig.tight_layout()
    return fig, ax_


def _discover_pygta_config(start_dir: Path | None = None) -> Path | None:
    """Find pygta_config.yml by walking from ``start_dir`` towards filesystem root."""
    search_root = (start_dir or Path.cwd()).resolve()
    for candidate_dir in (search_root, *search_root.parents):
        candidate = candidate_dir / "pygta_config.yml"
        if candidate.is_file():
            return candidate
    return None


def _axis_labels_from_pygta_config(config_path: Path | None = None) -> tuple[str, str]:
    """Resolve time and spectral axis labels from pygta_config.yml with safe defaults."""
    default_time = "Time (ps)"
    default_spectral = "Wavelength (nm)"

    resolved_path = config_path or _discover_pygta_config()
    if resolved_path is None:
        return default_time, default_spectral

    yaml = YAML(typ="safe")
    loaded = yaml.load(resolved_path.read_text(encoding="utf8"))
    if not isinstance(loaded, dict):
        return default_time, default_spectral

    plotting = loaded.get("plotting")
    if not isinstance(plotting, dict):
        return default_time, default_spectral
    general = plotting.get("general")
    if not isinstance(general, dict):
        return default_time, default_spectral
    axis_overrides = general.get("axis_label_override")
    if not isinstance(axis_overrides, dict):
        return default_time, default_spectral

    time_label = axis_overrides.get("time", default_time)
    spectral_label = axis_overrides.get("spectral", default_spectral)
    return str(time_label), str(spectral_label)


def plot_data_fit_residual_rows(
    result: ResultLike,
    *,
    maximum: float = 0.3,
    linthresh: float = 1.0,
    xmin: float | None = None,
    xmax: float | None = None,
    figsize: tuple[float, float] | None = None,
    figsize_per_row: tuple[float, float] = (8.0, 4.0),
    config_path: str | Path | None = None,
    add_irf_dispersion_center: bool = True,
    add_panel_labels: bool = True,
):
    """Plot data, fitted data and residual in rows for all datasets of a result.

    One row per dataset, with columns ``Data``, ``Fit`` and ``Residual`` using
    the ``seismic`` colormap and symmetric ``vmin/vmax`` based on ``maximum``.
    Axis labels are derived from ``pygta_config.yml``.

    Parameters
    ----------
    xmin : float | None
        Left x-limit applied to each subplot if provided.
    xmax : float | None
        Right x-limit applied to each subplot if provided.
    figsize : tuple[float, float] | None
        Absolute figure size passed to ``matplotlib``. If ``None``, a size is
        derived from ``figsize_per_row``.
    """

    result_map = result_dataset_mapping(result)
    dataset_items = list(result_map.items())
    if not dataset_items:
        raise ValueError("No datasets available in result.")

    row_count = len(dataset_items)
    if figsize is None:
        fig_width = figsize_per_row[0] * 3
        fig_height = figsize_per_row[1] * row_count
        figsize = (fig_width, fig_height)
    fig, axes = plt.subplots(row_count, 3, figsize=figsize, squeeze=False)

    time_label, spectral_label = _axis_labels_from_pygta_config(
        None if config_path is None else Path(config_path)
    )

    custom_cycler = cycler_func(color=["tab:grey"])

    for row_index, (dataset_name, result_dataset) in enumerate(dataset_items):
        data_axis = axes[row_index, 0]
        fit_axis = axes[row_index, 1]
        residual_axis = axes[row_index, 2]

        if add_irf_dispersion_center:
            _plot_irf_dispersion_center(
                result_dataset,
                ax=data_axis,
                spectral_axis="y",
                cycler=custom_cycler,
            )
        result_dataset.data.plot(
            x="time",
            y="spectral",
            center=False,
            cmap="seismic",
            vmin=-maximum,
            vmax=maximum,
            ax=data_axis,
            add_colorbar=False,
        )

        if add_irf_dispersion_center:
            _plot_irf_dispersion_center(
                result_dataset,
                ax=fit_axis,
                spectral_axis="y",
                cycler=custom_cycler,
            )
        result_dataset.fitted_data.plot(
            x="time",
            y="spectral",
            center=False,
            cmap="seismic",
            vmin=-maximum,
            vmax=maximum,
            ax=fit_axis,
            add_colorbar=False,
        )

        if add_irf_dispersion_center:
            _plot_irf_dispersion_center(
                result_dataset,
                ax=residual_axis,
                spectral_axis="y",
                cycler=custom_cycler,
            )
        result_dataset.residual.plot(
            x="time",
            y="spectral",
            center=False,
            cmap="seismic",
            vmin=-maximum,
            vmax=maximum,
            ax=residual_axis,
        )

        row_title_prefix = dataset_name.replace("_", " ")
        data_axis.set_title(f"{row_title_prefix} Data")
        fit_axis.set_title(f"{row_title_prefix} Fit")
        residual_axis.set_title(f"{row_title_prefix} Residual")

        for column_index, axis in enumerate((data_axis, fit_axis, residual_axis)):
            axis.set_xscale("symlog", linthresh=linthresh)
            axis.xaxis.set_minor_locator(MinorSymLogLocator(linthresh))
            axis.set_xlim(left=xmin, right=xmax)
            axis.set_xlabel(time_label if row_index == row_count - 1 else "")
            axis.set_ylabel(spectral_label if column_index == 0 else "")

    if add_panel_labels:
        add_subplot_labels(axes, label_format_function="upper_case_letter")

    fig.tight_layout()
    return fig, axes
