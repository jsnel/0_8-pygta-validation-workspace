"""Helpers for editing glotaran parameter CSV files."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

_RATE_SERIES_SUFFIX_ORDER = ("21", "32", "43", "54", "65", "76", "77")

# Default parameters file used by unfreeze_irf_wavelength_parameters.
_DEFAULT_PARAMS_PATH = (
    Path(__file__).parents[3]
    / "AnnaCalabritto"
    / "models"
    / "20260504col0nolhcb9_16_kolhcII17_36_opcl_target_LHCIfree.csv"
)

_DEFAULT_PARAMS_FREE2_PATH = (
    Path(__file__).parents[3]
    / "AnnaCalabritto"
    / "models"
    / "20260504col0nolhcb9_16_kolhcII17_36_opcl_target_LHCIfree2.csv"
)

_ABSOLUTE_TIME_SUFFIX_RE = re.compile(r"^(center|shift)\d*$")
_TIME_WIDTH_SUFFIX_RE = re.compile(r"^(width|convwidth|disp|lifetime)\d*$")
_RATE_LABEL_RE = re.compile(r"^(rate|kinetic\.)")
_IRF_COMPONENT_LABEL_RE = re.compile(
    r"^(?P<prefix>.+)\.(?P<family>center|scale|width)(?P<suffix>\d+)$"
)
_SHIFT_CONV_WL_LABEL_RE = re.compile(r"^.+\.(?P<kind>shift|convwidth)(?P<wl>\d+)$")
_CONVWIDTH_LABEL_RE = re.compile(r"(^|\.)convwidth\d*$")
_IRF_SHAPE_LABEL_SUBSTRINGS = (
    "close.center",
    "close.scale",
    "close.width",
    "open.center",
    "open.scale",
    "open.width",
    "i.shift",
    "i.convwidth",
)


def parameter_scale_factor_for_shift_binwidth_bug(
    label: str,
    *,
    old_bin_width: float = 4.0,
    new_bin_width: float = 3.2,
) -> float:
    """Return the multiplicative unit-conversion factor for a parameter label.

    This factor is suitable for widths, periods, rate constants, and parameter
    uncertainties. Absolute time-location parameters such as ``center`` and
    ``shift`` need an additional offset handled by
    ``transform_parameter_for_shift_binwidth_bug``.
    """
    if old_bin_width <= 0 or new_bin_width <= 0:
        raise ValueError("Both old_bin_width and new_bin_width must be positive.")

    time_scale = new_bin_width / old_bin_width
    rate_scale = old_bin_width / new_bin_width
    suffix = label.rsplit(".", 1)[-1]

    if _RATE_LABEL_RE.match(label):
        return rate_scale
    if suffix == "backsweep" or _TIME_WIDTH_SUFFIX_RE.match(suffix):
        return time_scale
    if _ABSOLUTE_TIME_SUFFIX_RE.match(suffix):
        return time_scale
    return 1.0


def transform_parameter_for_shift_binwidth_bug(
    label: str,
    value: float,
    *,
    old_bin_width: float = 4.0,
    new_bin_width: float = 3.2,
    target_ps: float = 100.0,
) -> float:
    """Convert one parameter value from the old 4 ps shift grid to the new grid.

    The buggy shift code rebuilt the time axis using ``old_bin_width`` instead
    of the real ``new_bin_width``. On a corrected dataset, time-like widths and
    periods therefore need to shrink by ``new_bin_width / old_bin_width`` while
    rate constants need to grow by the inverse factor. Absolute time-location
    parameters keep ``target_ps`` fixed and are transformed around that anchor.

    Parameters
    ----------
    label:
        Parameter label used to infer whether the value is a rate, absolute
        time location, or time-like width/period.
    value:
        Original parameter value fitted on the wrongly shifted dataset.
    old_bin_width:
        Bin width used by the buggy code. Defaults to ``4.0`` ps.
    new_bin_width:
        Real bin width of the shifted dataset. Defaults to ``3.2`` ps.
    target_ps:
        Time-location anchor used by the shift routine. Defaults to ``100.0``
        ps and stays invariant during conversion.

    Returns
    -------
    float
        Converted parameter value for the corrected dataset.
    """
    scale_factor = parameter_scale_factor_for_shift_binwidth_bug(
        label,
        old_bin_width=old_bin_width,
        new_bin_width=new_bin_width,
    )
    suffix = label.rsplit(".", 1)[-1]

    if _ABSOLUTE_TIME_SUFFIX_RE.match(suffix):
        return target_ps + (value - target_ps) * scale_factor
    return value * scale_factor


def convert_parameter_table_from_shift_binwidth_bug(
    parameters_table: pd.DataFrame | object,
    *,
    old_bin_width: float = 4.0,
    new_bin_width: float = 3.2,
    target_ps: float = 100.0,
) -> pd.DataFrame:
    """Convert an in-memory parameter table from the old shift timing to the new one.

    The function accepts either a pandas ``DataFrame`` or an object exposing a
    ``to_dataframe()`` method such as ``optimized_parameters``. It returns a new
    DataFrame with transformed ``value`` entries. If a ``standard_error`` or
    ``stderr`` column is present, those uncertainties are scaled by the same
    unit-conversion factor as the parameter itself. When both value and
    uncertainty are available, any ``t-value`` / ``T_value`` column is
    recomputed from the transformed values.
    """
    if isinstance(parameters_table, pd.DataFrame):
        converted = parameters_table.copy(deep=True)
    else:
        try:
            converted = parameters_table.to_dataframe().copy(deep=True)
        except AttributeError as exc:
            raise TypeError(
                "parameters_table must be a DataFrame or expose to_dataframe()"
            ) from exc

    normalized_columns = {
        "".join(ch for ch in str(col).lower() if ch.isalnum()): col for col in converted.columns
    }
    value_col = normalized_columns.get("value")
    if value_col is None:
        raise ValueError("parameter table does not contain a value column")

    if "label" in converted.columns:
        labels = converted["label"].astype(str)
    else:
        labels = converted.index.to_series().astype(str)

    values = pd.to_numeric(converted[value_col], errors="coerce")
    transformed_values: list[float | object] = []
    scale_factors: list[float | None] = []
    for label, value in zip(labels, values, strict=False):
        if pd.isna(value):
            transformed_values.append(value)
            scale_factors.append(None)
            continue
        scale_factor = parameter_scale_factor_for_shift_binwidth_bug(
            label,
            old_bin_width=old_bin_width,
            new_bin_width=new_bin_width,
        )
        transformed_values.append(
            transform_parameter_for_shift_binwidth_bug(
                label,
                float(value),
                old_bin_width=old_bin_width,
                new_bin_width=new_bin_width,
                target_ps=target_ps,
            )
        )
        scale_factors.append(scale_factor)
    converted[value_col] = transformed_values

    stderr_col = normalized_columns.get("standarderror") or normalized_columns.get("stderr")
    if stderr_col is not None:
        stderr_values = pd.to_numeric(converted[stderr_col], errors="coerce")
        transformed_stderr: list[float | object] = []
        for scale_factor, stderr in zip(scale_factors, stderr_values, strict=False):
            if scale_factor is None or pd.isna(stderr):
                transformed_stderr.append(stderr)
            else:
                transformed_stderr.append(float(stderr) * abs(scale_factor))
        converted[stderr_col] = transformed_stderr

        t_value_col = normalized_columns.get("tvalue")
        if t_value_col is not None:
            recomputed_t = []
            for value, stderr in zip(converted[value_col], converted[stderr_col], strict=False):
                if pd.isna(value) or pd.isna(stderr) or float(stderr) == 0:
                    recomputed_t.append(float("nan"))
                else:
                    recomputed_t.append(float(value) / float(stderr))
            converted[t_value_col] = recomputed_t

    return converted


def convert_parameters_from_shift_binwidth_bug(
    parameters_filename: str | Path,
    output_filename: str | Path | None = None,
    *,
    old_bin_width: float = 4.0,
    new_bin_width: float = 3.2,
    target_ps: float = 100.0,
) -> dict[str, tuple[float, float]]:
    """Rewrite a glotaran parameter CSV for the corrected shifted-data timing.

    The helper updates the ``value`` column in-place, or writes to
    ``output_filename`` when provided. Labels are interpreted as follows:

    - ``center*`` and ``shift*``: affine correction around ``target_ps``
    - ``width*``, ``convwidth*``, ``disp1``, ``disp2``, ``lifetime*``,
      ``backsweep``: multiply by ``new_bin_width / old_bin_width``
    - labels starting with ``rate`` or ``kinetic.``: multiply by
      ``old_bin_width / new_bin_width``

    Parameters
    ----------
    parameters_filename:
        Input CSV file with at least ``label`` and ``value`` columns.
    output_filename:
        Optional output CSV path. When omitted, the input file is updated
        in-place.
    old_bin_width:
        Bin width used by the buggy shift code. Defaults to ``4.0`` ps.
    new_bin_width:
        Real bin width. Defaults to ``3.2`` ps.
    target_ps:
        Alignment target preserved by the shift routine. Defaults to ``100.0``
        ps.

    Returns
    -------
    dict[str, tuple[float, float]]
        Mapping of changed labels to ``(old_value, new_value)``.
    """
    path = Path(parameters_filename)
    output_path = Path(output_filename) if output_filename is not None else path
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    if not lines:
        return {}

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        value_idx = header.index("value")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'value' column") from exc

    changed: dict[str, tuple[float, float]] = {}
    rewritten: list[str] = [lines[0]]
    for line in lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, value_idx):
            rewritten.append(line)
            continue

        label = cols[label_idx].strip()
        value_str = cols[value_idx].strip()
        try:
            old_value = float(value_str)
        except ValueError:
            rewritten.append(line)
            continue

        new_value = transform_parameter_for_shift_binwidth_bug(
            label,
            old_value,
            old_bin_width=old_bin_width,
            new_bin_width=new_bin_width,
            target_ps=target_ps,
        )
        if math.isclose(old_value, new_value):
            rewritten.append(line)
            continue

        cols[value_idx] = str(new_value)
        eol = line[len(stripped) :]
        rewritten.append(",".join(cols) + eol)
        changed[label] = (old_value, new_value)

    output_path.write_text("".join(rewritten), encoding="utf-8-sig")
    return changed


def fix_negative_convwidth(
    result: object | str | Path,
    path: str | Path | None = None,
) -> list[str]:
    """Normalize ``.convwidth`` parameter values in-place.

    For every row whose label contains ``.convwidth`` the function:

    * negates the value (column index 1) if it is negative, and
    * sets the minimum (column index 5) to ``0``.

    The ``result`` argument is accepted for API consistency with other notebook
    helpers but is not used. The helper also remains backward compatible with
    path-only calls like ``fix_negative_convwidth(csv_path)``.

    Parameters
    ----------
    result:
        Unused result object, or the CSV path when called with a single
        positional argument.
    path:
        Path to the glotaran parameter CSV file to fix.

    Returns
    -------
    list[str]
        Labels of the parameters that were changed.
    """
    resolved_path = Path(result) if path is None else Path(path)
    lines = resolved_path.read_text(encoding="utf-8-sig").splitlines(keepends=True)

    fixed_lines: list[str] = []
    changed: list[str] = []
    flipped: list[str] = []
    minimum_set: list[str] = []
    for line in lines:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        label = cols[0] if cols else ""
        if ".convwidth" in label and len(cols) >= 2:
            try:
                value = float(cols[1])
            except ValueError:
                fixed_lines.append(line)
                continue
            row_changed = False
            if value < 0:
                cols[1] = str(-value)
                flipped.append(label)
                row_changed = True
            while len(cols) <= 5:
                cols.append("")
            if cols[5].strip() != "0":
                cols[5] = "0"
                minimum_set.append(label)
                row_changed = True
            if row_changed:
                eol = line[len(stripped) :]
                fixed_lines.append(",".join(cols) + eol)
                changed.append(label)
                continue
        fixed_lines.append(line)

    resolved_path.write_text("".join(fixed_lines), encoding="utf-8-sig")
    if flipped:
        print("Flipped negative convwidth parameters:")
        for label in flipped:
            print(f"  {label}")
    else:
        print("No negative convwidth parameters found.")
    if minimum_set:
        print("Set minimum=0 for convwidth parameters:")
        for label in minimum_set:
            print(f"  {label}")
    else:
        print("All convwidth parameters already had minimum=0.")
    return changed


def reanchor_conv_multi_multi_gaussian_irf_parameters(
    parameters_filename: str | Path,
    output_filename: str | Path | None = None,
) -> dict[str, int]:
    """Promote the strongest IRF gaussian to anchor position ``1`` in-place.

    This helper rewrites glotaran parameter CSV rows of the form
    ``<irf-prefix>.centerN``, ``<irf-prefix>.scaleN``, and
    ``<irf-prefix>.width`` rows with numeric suffixes.
    It is intended for ``type: conv-multi-multi-gaussian`` parameter tables where
    gaussian ``1`` acts as the anchor, non-anchor centers are stored relative to
    ``center1``, and non-anchor scales are stored relative to ``scale1``.

    For each IRF prefix, the gaussian with the largest stored absolute scale is
    swapped into suffix ``1``. The helper then recomputes every ``center*`` and
    ``scale*`` value relative to that new anchor, swaps the corresponding
    ``width*`` values, and finally normalizes ``scale1`` back to ``1``.

    Parameters
    ----------
    parameters_filename:
        Input parameter CSV file.
    output_filename:
        Optional output path. When omitted, the input file is updated in-place.

    Returns
    -------
    dict[str, int]
        Mapping of IRF prefixes to the original gaussian suffix that was
        promoted to anchor position ``1``.
    """

    path = Path(parameters_filename)
    output_path = Path(output_filename) if output_filename is not None else path
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    if not lines:
        return {}

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        value_idx = header.index("value")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'value' column") from exc
    minimum_idx = header.index("minimum") if "minimum" in header else None

    groups: dict[str, dict[str, dict[int, tuple[int, list[str]]]]] = {}
    for line_idx, line in enumerate(lines[1:], start=1):
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, value_idx):
            continue

        label = cols[label_idx].strip()
        match = _IRF_COMPONENT_LABEL_RE.match(label)
        if match is None:
            continue

        prefix = match.group("prefix")
        family = match.group("family")
        suffix = int(match.group("suffix"))
        groups.setdefault(prefix, {}).setdefault(family, {})[suffix] = (line_idx, cols)

    changed: dict[str, int] = {}
    for prefix, family_rows in groups.items():
        if not {"center", "scale", "width"}.issubset(family_rows):
            continue

        common_suffixes = (
            set(family_rows["center"]) & set(family_rows["scale"]) & set(family_rows["width"])
        )
        if 1 not in common_suffixes:
            continue

        center_values = {
            suffix: float(family_rows["center"][suffix][1][value_idx])
            for suffix in common_suffixes
        }
        scale_values = {
            suffix: float(family_rows["scale"][suffix][1][value_idx]) for suffix in common_suffixes
        }
        width_values = {
            suffix: float(family_rows["width"][suffix][1][value_idx]) for suffix in common_suffixes
        }

        promoted_suffix = 1
        largest_scale = scale_values[1]
        for suffix in sorted(common_suffixes):
            if scale_values[suffix] > largest_scale:
                promoted_suffix = suffix
                largest_scale = scale_values[suffix]

        if promoted_suffix == 1:
            continue
        if math.isclose(largest_scale, 0.0):
            raise ValueError(
                f"Cannot re-anchor IRF group '{prefix}' because the promoted scale is zero."
            )

        absolute_centers = {1: center_values[1]}
        absolute_scales = {1: scale_values[1]}
        for suffix in common_suffixes - {1}:
            absolute_centers[suffix] = center_values[1] + center_values[suffix]
            absolute_scales[suffix] = scale_values[1] * scale_values[suffix]

        anchor_center = absolute_centers[promoted_suffix]
        anchor_scale = absolute_scales[promoted_suffix]

        source_suffix_by_target = {suffix: suffix for suffix in common_suffixes}
        source_suffix_by_target[1] = promoted_suffix
        source_suffix_by_target[promoted_suffix] = 1

        for target_suffix, source_suffix in source_suffix_by_target.items():
            if target_suffix == 1:
                new_center = anchor_center
                new_scale = 1.0
            else:
                new_center = absolute_centers[source_suffix] - anchor_center
                new_scale = absolute_scales[source_suffix] / anchor_scale
            new_width = width_values[source_suffix]

            center_row = family_rows["center"][target_suffix][1]
            center_row[value_idx] = str(new_center)
            if minimum_idx is not None and new_center < 0 and len(center_row) > minimum_idx:
                minimum_str = center_row[minimum_idx].strip()
                if minimum_str:
                    try:
                        minimum_value = float(minimum_str)
                    except ValueError:
                        minimum_value = None
                    if minimum_value is not None and minimum_value >= 0:
                        center_row[minimum_idx] = ""
            family_rows["scale"][target_suffix][1][value_idx] = str(new_scale)
            family_rows["width"][target_suffix][1][value_idx] = str(new_width)

        changed[prefix] = promoted_suffix

    for family_rows in groups.values():
        for rows_by_suffix in family_rows.values():
            for line_idx, cols in rows_by_suffix.values():
                eol = lines[line_idx][len(lines[line_idx].rstrip("\r\n")) :]
                lines[line_idx] = ",".join(cols) + eol

    output_path.write_text("".join(lines), encoding="utf-8-sig")
    return changed


def freeze_parameters_with_low_t_value(
    result: object,
    parameters_filename: str | Path,
    exclude: list[str] | None = None,
) -> list[str]:
    """Set ``vary=False`` when ``abs(T-value) < 2`` based on optimized parameters.

    Parameter labels whose names start with any prefix in ``exclude`` are
    reported when they have low T-values but are not changed.

    Parameters
    ----------
    result:
        Glotaran result object with ``optimized_parameters.to_dataframe()``.
    parameters_filename:
        Path to the parameter CSV file to update in-place.
    exclude:
        Optional list of label prefixes that must not be changed.

    Returns
    -------
    list[str]
        Labels that were changed to ``vary=False``.
    """

    try:
        optimized_df = result.optimized_parameters.to_dataframe()
    except AttributeError as exc:
        raise TypeError("result must expose optimized_parameters.to_dataframe()") from exc

    # Accept common variants such as "t-value", "T_value", or "t value".
    normalized_columns = {
        "".join(ch for ch in str(col).lower() if ch.isalnum()): col for col in optimized_df.columns
    }
    t_value_col = normalized_columns.get("tvalue")

    if "label" in optimized_df.columns:
        label_series = optimized_df["label"].astype(str)
    else:
        label_series = optimized_df.index.to_series().astype(str)

    if t_value_col is not None:
        t_values = pd.to_numeric(optimized_df[t_value_col], errors="coerce")
    else:
        value_col = normalized_columns.get("value")
        stderr_col = normalized_columns.get("standarderror") or normalized_columns.get("stderr")
        if value_col is None or stderr_col is None:
            raise ValueError(
                "optimized parameters table does not contain a T-value column "
                "and lacks value/standard_error columns to derive it"
            )

        values = pd.to_numeric(optimized_df[value_col], errors="coerce")
        stderr = pd.to_numeric(optimized_df[stderr_col], errors="coerce")
        t_values = values / stderr.where(stderr != 0)
    low_t_labels = {
        label
        for label, t_value in zip(label_series, t_values, strict=False)
        if pd.notna(t_value) and math.fabs(float(t_value)) < 2.0
    }

    exclude_prefixes = tuple(exclude or [])
    excluded_low_t_labels = {
        label for label in low_t_labels if exclude_prefixes and label.startswith(exclude_prefixes)
    }
    if excluded_low_t_labels:
        print(
            "Excluded from fixing despite |T-value| < 2: "
            + ", ".join(sorted(excluded_low_t_labels))
        )

    path = Path(parameters_filename)
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    if not lines:
        return []

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        vary_idx = header.index("vary")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'vary' column") from exc

    changed: list[str] = []
    rewritten: list[str] = [lines[0]]
    for line in lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, vary_idx):
            rewritten.append(line)
            continue

        label = cols[label_idx].strip()
        if (
            label in low_t_labels
            and label not in excluded_low_t_labels
            and cols[vary_idx] != "False"
        ):
            cols[vary_idx] = "False"
            eol = line[len(stripped) :]
            rewritten.append(",".join(cols) + eol)
            changed.append(label)
            continue

        rewritten.append(line)

    path.write_text("".join(rewritten), encoding="utf-8-sig")
    return changed


def freeze_all_parameters_with_low_t_value(
    result: object,
    path: str | Path,
    exclude: list[str] | None = None,
) -> list[str]:
    """Set ``vary=False`` for all parameters whose absolute T-value is below 2.

    This is a convenience wrapper around
    :func:`freeze_parameters_with_low_t_value` for notebook workflows which use
    the ``(result, PARAMETER_PATH)`` calling pattern.
    """

    return freeze_parameters_with_low_t_value(result, path, exclude=exclude)


def copy_estimated_parameters_to_file(
    result: object,
    parameters_filename: str | Path,
    exclude: list[str] | None = None,
) -> list[str]:
    """Copy optimized parameter values into the parameter CSV file.

    Parameter labels whose names start with any prefix in ``exclude`` are
    reported but not changed.

    Parameters
    ----------
    result:
        Glotaran result object with ``optimized_parameters.to_dataframe()``.
    parameters_filename:
        Path to the parameter CSV file to update in-place.
    exclude:
        Optional list of label prefixes that must not be changed.

    Returns
    -------
    list[str]
        Labels whose ``value`` entry was updated.
    """

    try:
        optimized_df = result.optimized_parameters.to_dataframe()
    except AttributeError as exc:
        raise TypeError("result must expose optimized_parameters.to_dataframe()") from exc

    normalized_columns = {
        "".join(ch for ch in str(col).lower() if ch.isalnum()): col for col in optimized_df.columns
    }
    value_col = normalized_columns.get("value")
    if value_col is None:
        raise ValueError("optimized parameters table does not contain a value column")

    if "label" in optimized_df.columns:
        label_series = optimized_df["label"].astype(str)
    else:
        label_series = optimized_df.index.to_series().astype(str)

    value_series = pd.to_numeric(optimized_df[value_col], errors="coerce")
    estimated_values = {
        label: float(value)
        for label, value in zip(label_series, value_series, strict=False)
        if pd.notna(value)
    }

    exclude_prefixes = tuple(exclude or [])
    excluded_labels = {
        label
        for label in estimated_values
        if exclude_prefixes and label.startswith(exclude_prefixes)
    }
    if excluded_labels:
        print("Excluded from value copy: " + ", ".join(sorted(excluded_labels)))

    path = Path(parameters_filename)
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    if not lines:
        return []

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        value_idx = header.index("value")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'value' column") from exc

    changed: list[str] = []
    rewritten: list[str] = [lines[0]]
    for line in lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, value_idx):
            rewritten.append(line)
            continue

        label = cols[label_idx].strip()
        if label in estimated_values and label not in excluded_labels:
            new_value = estimated_values[label]
            old_value = cols[value_idx].strip()
            should_update = True
            try:
                should_update = not math.isclose(float(old_value), new_value)
            except ValueError:
                should_update = old_value != str(new_value)

            if should_update:
                cols[value_idx] = str(new_value)
                eol = line[len(stripped) :]
                rewritten.append(",".join(cols) + eol)
                changed.append(label)
                continue

        rewritten.append(line)

    path.write_text("".join(rewritten), encoding="utf-8-sig")
    return changed


def copy_irf_shape_parameters_to_file(
    source_parameters_filename: str | Path,
    target_parameters_filename: str | Path,
    label_substrings: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Copy IRF-shape parameter values from one parameter CSV into another.

    Only labels containing one of the configured ``label_substrings`` are
    considered. When a matching label exists in both files, the helper copies
    the ``value`` from the source file into the target file and sets
    ``vary=False`` on the target row.

    Parameters
    ----------
    source_parameters_filename:
        CSV file providing the authoritative IRF-shape parameter values.
    target_parameters_filename:
        CSV file updated in-place.
    label_substrings:
        Optional list of substrings used to identify IRF-shape labels. When
        omitted, defaults to the workspace IRF-shape label patterns.

    Returns
    -------
    list[str]
        Labels whose value and/or vary flag changed in the target file.
    """

    label_patterns = tuple(label_substrings or _IRF_SHAPE_LABEL_SUBSTRINGS)
    return _copy_matching_parameters_to_file(
        source_parameters_filename,
        target_parameters_filename,
        lambda label: any(pattern in label for pattern in label_patterns),
    )


def copy_shift_conv_parameters_to_file(
    source_parameters_filename: str | Path,
    target_parameters_filename: str | Path,
    *,
    min_wavelength: int = 678,
    max_wavelength: int = 760,
) -> list[str]:
    """Copy wavelength-resolved shift/convwidth parameters into a target CSV.

    The helper copies only labels matching ``.shift{wl}`` or
    ``.convwidth{wl}`` where ``wl`` is an integer between ``min_wavelength``
    and ``max_wavelength`` inclusive. For matching labels present in both
    files, the target ``value`` is updated from the source and ``vary`` is set
    to ``False``.
    """

    return _copy_matching_parameters_to_file(
        source_parameters_filename,
        target_parameters_filename,
        lambda label: _is_shift_conv_wavelength_label(
            label,
            min_wavelength=min_wavelength,
            max_wavelength=max_wavelength,
        ),
    )


def freeze_shift_conv_parameters_to_file(
    parameters_filename: str | Path,
    *,
    min_wavelength: int = 678,
    max_wavelength: int = 760,
) -> list[str]:
    """Set ``vary=False`` for wavelength-resolved shift/convwidth parameters.

    The helper freezes only labels matching ``.shift{wl}`` or
    ``.convwidth{wl}`` where ``wl`` is an integer between ``min_wavelength``
    and ``max_wavelength`` inclusive.
    """

    return _set_vary_matching_parameters_to_file(
        parameters_filename,
        lambda label: _is_shift_conv_wavelength_label(
            label,
            min_wavelength=min_wavelength,
            max_wavelength=max_wavelength,
        ),
        vary_value="False",
    )


def free_shift_conv_parameters_to_file(
    parameters_filename: str | Path,
    *,
    min_wavelength: int = 678,
    max_wavelength: int = 760,
) -> list[str]:
    """Set ``vary=True`` for wavelength-resolved shift/convwidth parameters.

    The helper frees only labels matching ``.shift{wl}`` or
    ``.convwidth{wl}`` where ``wl`` is an integer between ``min_wavelength``
    and ``max_wavelength`` inclusive.
    """

    return _set_vary_matching_parameters_to_file(
        parameters_filename,
        lambda label: _is_shift_conv_wavelength_label(
            label,
            min_wavelength=min_wavelength,
            max_wavelength=max_wavelength,
        ),
        vary_value="True",
    )


def _is_shift_conv_wavelength_label(
    label: str,
    *,
    min_wavelength: int,
    max_wavelength: int,
) -> bool:
    match = _SHIFT_CONV_WL_LABEL_RE.match(label)
    if match is None:
        return False

    wavelength = int(match.group("wl"))
    return min_wavelength <= wavelength <= max_wavelength


def _copy_matching_parameters_to_file(
    source_parameters_filename: str | Path,
    target_parameters_filename: str | Path,
    label_matcher: callable,
) -> list[str]:
    """Copy source values to matching target labels and set ``vary=False``."""

    source_path = Path(source_parameters_filename)
    source_lines = source_path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    if not source_lines:
        return []

    source_header = source_lines[0].rstrip("\r\n").split(",")
    try:
        source_label_idx = source_header.index("label")
    except ValueError as exc:
        raise ValueError("source parameters CSV has no 'label' column") from exc
    try:
        source_value_idx = source_header.index("value")
    except ValueError as exc:
        raise ValueError("source parameters CSV has no 'value' column") from exc

    source_values: dict[str, str] = {}
    for line in source_lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(source_label_idx, source_value_idx):
            continue

        label = cols[source_label_idx].strip()
        if label_matcher(label):
            source_values[label] = cols[source_value_idx].strip()

    if not source_values:
        return []

    target_path = Path(target_parameters_filename)
    target_lines = target_path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    if not target_lines:
        return []

    target_header = target_lines[0].rstrip("\r\n").split(",")
    try:
        target_label_idx = target_header.index("label")
    except ValueError as exc:
        raise ValueError("target parameters CSV has no 'label' column") from exc
    try:
        target_value_idx = target_header.index("value")
    except ValueError as exc:
        raise ValueError("target parameters CSV has no 'value' column") from exc
    try:
        target_vary_idx = target_header.index("vary")
    except ValueError as exc:
        raise ValueError("target parameters CSV has no 'vary' column") from exc

    changed: list[str] = []
    rewritten: list[str] = [target_lines[0]]
    for line in target_lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(target_label_idx, target_value_idx, target_vary_idx):
            rewritten.append(line)
            continue

        label = cols[target_label_idx].strip()
        if label in source_values:
            new_value = source_values[label]
            old_value = cols[target_value_idx].strip()
            value_changed = True
            try:
                value_changed = not math.isclose(float(old_value), float(new_value))
            except ValueError:
                value_changed = old_value != new_value

            vary_changed = cols[target_vary_idx] != "False"
            if value_changed or vary_changed:
                cols[target_value_idx] = new_value
                cols[target_vary_idx] = "False"
                eol = line[len(stripped) :]
                rewritten.append(",".join(cols) + eol)
                changed.append(label)
                continue

        rewritten.append(line)

    target_path.write_text("".join(rewritten), encoding="utf-8-sig")
    return changed


def _set_vary_matching_parameters_to_file(
    parameters_filename: str | Path,
    label_matcher: callable,
    *,
    vary_value: str,
) -> list[str]:
    """Set ``vary`` for all rows whose label matches ``label_matcher``."""

    path = Path(parameters_filename)
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    if not lines:
        return []

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        vary_idx = header.index("vary")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'vary' column") from exc

    changed: list[str] = []
    rewritten: list[str] = [lines[0]]
    for line in lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, vary_idx):
            rewritten.append(line)
            continue

        label = cols[label_idx].strip()
        if label_matcher(label) and cols[vary_idx] != vary_value:
            cols[vary_idx] = vary_value
            eol = line[len(stripped) :]
            rewritten.append(",".join(cols) + eol)
            changed.append(label)
            continue

        rewritten.append(line)

    path.write_text("".join(rewritten), encoding="utf-8-sig")
    return changed


def sort_rate_series_values_descending(
    parameters_filename: str | Path,
) -> list[str]:
    """Sort grouped rate constant values in descending order in-place.

    The helper looks for groups of labels shaped like ``rate*.kopen21`` ..
    ``rate*.kopen77`` or ``rate*.kclose21`` .. ``rate*.kclose77``. For each
    group, the function sorts the current numeric values in descending order and
    writes those sorted values back to the fixed suffix order ``21, 32, 43,
    54, 65, 76, 77`` for the suffixes that are present.

    Parameters
    ----------
    parameters_filename:
        Path to the glotaran parameter CSV file to update in-place.

    Returns
    -------
    list[str]
        Group prefixes whose values were rewritten.
    """

    path = Path(parameters_filename)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        return []

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        value_idx = header.index("value")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'value' column") from exc

    group_rows: dict[str, dict[str, tuple[int, list[str], str, float]]] = {}
    for line_idx, line in enumerate(lines[1:], start=1):
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, value_idx):
            continue

        label = cols[label_idx].strip()
        if not label.startswith("rate"):
            continue

        suffix = next(
            (candidate for candidate in _RATE_SERIES_SUFFIX_ORDER if label.endswith(candidate)),
            None,
        )
        if suffix is None:
            continue

        group_name = label[: -len(suffix)]
        if not group_name.endswith(("kopen", "kclose")):
            continue

        value_str = cols[value_idx].strip()
        try:
            value = float(value_str)
        except ValueError:
            continue

        group_rows.setdefault(group_name, {})[suffix] = (line_idx, cols, value_str, value)

    changed_groups: list[str] = []
    for group_name, suffix_rows in group_rows.items():
        present_suffixes = [
            suffix for suffix in _RATE_SERIES_SUFFIX_ORDER if suffix in suffix_rows
        ]
        if not present_suffixes:
            continue

        sorted_value_strings = [
            value_str
            for _, _, value_str, _ in sorted(
                (suffix_rows[suffix] for suffix in present_suffixes),
                key=lambda item: item[3],
                reverse=True,
            )
        ]

        group_changed = False
        for suffix, new_value_str in zip(
            present_suffixes,
            sorted_value_strings,
            strict=True,
        ):
            line_idx, cols, old_value_str, _ = suffix_rows[suffix]
            if old_value_str == new_value_str:
                continue

            cols[value_idx] = new_value_str
            eol = lines[line_idx][len(lines[line_idx].rstrip("\r\n")) :]
            lines[line_idx] = ",".join(cols) + eol
            group_changed = True

        if group_changed:
            changed_groups.append(group_name)

    path.write_text("".join(lines), encoding="utf-8")
    return changed_groups


def unfreeze_irf_wavelength_parameters(
    path: str | Path | None = None,
    allow: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[str]:
    """Set ``vary=True`` for per-wavelength IRF parameters.

    For every parameter whose label matches ``<prefix>.<suffix><wl>`` where

        * ``<suffix>`` is one of the substrings in *allow* (default:
            ``[".shift"]``),
    * ``<wl>`` is an integer in the range 678–760, and
    * the ``<prefix>`` (everything before the first dot) does **not** contain
      any substring from *exclude* (default: ``["x"]``),

    the ``vary`` column is set to ``True`` in-place.

    Parameters
    ----------
    path:
        Path to the glotaran parameter CSV file.  Defaults to
        ``AnnaCalabritto/models/20260504col0nolhcb9_16_kolhcII17_36_opcl_target_LHCIfree.csv``
        relative to the workspace root.
    allow:
        Substrings that must appear in the label suffix.  Defaults to
        ``[".shift"]``. Pass e.g. ``[".shift", ".convwidth"]`` to also
        unfreeze convwidth parameters.
    exclude:
        Substrings whose presence in the prefix disqualifies a parameter.
        Defaults to ``["x"]``.

    Returns
    -------
    list[str]
        Labels of the parameters whose ``vary`` column was changed to ``True``.
    """
    resolved_path = Path(path) if path is not None else _DEFAULT_PARAMS_PATH
    allow_suffixes = allow if allow is not None else [".shift"]
    exclude_substrings = exclude if exclude is not None else ["x"]

    lines = resolved_path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        return []

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        vary_idx = header.index("vary")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'vary' column") from exc

    changed: list[str] = []
    rewritten: list[str] = [lines[0]]
    for line in lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, vary_idx):
            rewritten.append(line)
            continue

        label = cols[label_idx].strip()

        # Split into prefix (before first dot) and the rest.
        dot_pos = label.find(".")
        if dot_pos == -1:
            rewritten.append(line)
            continue
        prefix = label[:dot_pos]
        suffix_wl = label[dot_pos:]  # e.g. ".convwidth682"

        # Exclude if any exclude substring appears in the prefix.
        if any(ex in prefix for ex in exclude_substrings):
            rewritten.append(line)
            continue

        # Check whether suffix matches <allowed_suffix><wl> with wl in 678-760.
        matched = False
        for allowed in allow_suffixes:
            if suffix_wl.startswith(allowed):
                wl_str = suffix_wl[len(allowed) :]
                try:
                    wl = int(wl_str)
                except ValueError:
                    continue
                if 678 <= wl <= 760:
                    matched = True
                    break

        if not matched:
            rewritten.append(line)
            continue

        if cols[vary_idx].strip() != "True":
            cols[vary_idx] = "True"
            eol = line[len(stripped) :]
            rewritten.append(",".join(cols) + eol)
            changed.append(label)
        else:
            rewritten.append(line)

    resolved_path.write_text("".join(rewritten), encoding="utf-8")
    if changed:
        print(f"Set vary=True for {len(changed)} parameters:")
        for label in changed:
            print(f"  {label}")
    else:
        print("No parameters matched (or all already had vary=True).")
    return changed


def unfreeze_irf_component_parameters(
    path: str | Path | None = None,
    allow: list[str] | None = None,
    indices: list[int] | None = None,
) -> list[str]:
    """Set ``vary=True`` for IRF ``.center/.scale/.width`` component parameters.

    A parameter is changed when its label ends with one of:

    * ``.center{x}``
    * ``.scale{x}``
    * ``.width{x}``

    where ``x`` is one of the values in *indices* (default: ``[2, 3, 4, 8]``).

    Parameters
    ----------
    path:
        Path to the glotaran parameter CSV file. Defaults to
        ``AnnaCalabritto/models/20260504col0nolhcb9_16_kolhcII17_36_opcl_target_LHCIfree2.csv``
        relative to the workspace root.
    allow:
        Suffix families to match. Defaults to
        ``[".center", ".scale", ".width"]``.
    indices:
        Numeric suffixes to match. Defaults to ``[2, 3, 4, 8]``.

    Returns
    -------
    list[str]
        Labels of the parameters whose ``vary`` column was changed to ``True``.
    """
    resolved_path = Path(path) if path is not None else _DEFAULT_PARAMS_FREE2_PATH
    allow_suffixes = allow if allow is not None else [".center", ".scale", ".width"]
    allowed_indices = set(indices if indices is not None else [2, 3, 4, 8])

    lines = resolved_path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        return []

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        vary_idx = header.index("vary")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'vary' column") from exc

    changed: list[str] = []
    rewritten: list[str] = [lines[0]]
    for line in lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, vary_idx):
            rewritten.append(line)
            continue

        label = cols[label_idx].strip()

        matched = False
        for suffix in allow_suffixes:
            if label.startswith("$"):
                continue
            if suffix in label:
                pos = label.rfind(suffix)
                if pos == -1:
                    continue
                idx_str = label[pos + len(suffix) :]
                try:
                    idx = int(idx_str)
                except ValueError:
                    continue
                if idx in allowed_indices:
                    matched = True
                    break

        if not matched:
            rewritten.append(line)
            continue

        if cols[vary_idx].strip() != "True":
            cols[vary_idx] = "True"
            eol = line[len(stripped) :]
            rewritten.append(",".join(cols) + eol)
            changed.append(label)
        else:
            rewritten.append(line)

    resolved_path.write_text("".join(rewritten), encoding="utf-8")
    if changed:
        print(f"Set vary=True for {len(changed)} parameters:")
        for label in changed:
            print(f"  {label}")
    else:
        print("No parameters matched (or all already had vary=True).")
    return changed


def freeze_irf_component_parameters_with_low_t_value(
    result: object,
    path: str | Path | None = None,
    allow: list[str] | None = None,
    indices: list[int] | None = None,
    t_threshold: float = 2.0,
) -> list[str]:
    """Set ``vary=False`` for selected IRF components when ``abs(T-value) < t_threshold``.

    The target labels are parameters ending with one of:

    * ``.center{x}``
    * ``.scale{x}``
    * ``.width{x}``

    where ``x`` is in *indices* (default: ``[2, 3, 4, 8]``).

    T-values are taken from ``result.optimized_parameters.to_dataframe()``.
    If no explicit T-value column is present, they are derived as
    ``value / standard_error``.

    Parameters
    ----------
    result:
        Glotaran result object with ``optimized_parameters.to_dataframe()``.
    path:
        Path to the glotaran parameter CSV file. Defaults to
        ``AnnaCalabritto/models/20260504col0nolhcb9_16_kolhcII17_36_opcl_target_LHCIfree2.csv``
        relative to the workspace root.
    allow:
        Suffix families to match. Defaults to
        ``[".center", ".scale", ".width"]``.
    indices:
        Numeric suffixes to match. Defaults to ``[2, 3, 4, 8]``.
    t_threshold:
        Absolute T-value threshold used for freezing. Defaults to ``2.0``.

    Returns
    -------
    list[str]
        Labels whose ``vary`` column was changed to ``False``.
    """
    try:
        optimized_df = result.optimized_parameters.to_dataframe()
    except AttributeError as exc:
        raise TypeError("result must expose optimized_parameters.to_dataframe()") from exc

    normalized_columns = {
        "".join(ch for ch in str(col).lower() if ch.isalnum()): col for col in optimized_df.columns
    }
    t_value_col = normalized_columns.get("tvalue")

    if "label" in optimized_df.columns:
        label_series = optimized_df["label"].astype(str)
    else:
        label_series = optimized_df.index.to_series().astype(str)

    if t_value_col is not None:
        t_values = pd.to_numeric(optimized_df[t_value_col], errors="coerce")
    else:
        value_col = normalized_columns.get("value")
        stderr_col = normalized_columns.get("standarderror") or normalized_columns.get("stderr")
        if value_col is None or stderr_col is None:
            raise ValueError(
                "optimized parameters table does not contain a T-value column "
                "and lacks value/standard_error columns to derive it"
            )

        values = pd.to_numeric(optimized_df[value_col], errors="coerce")
        stderr = pd.to_numeric(optimized_df[stderr_col], errors="coerce")
        t_values = values / stderr.where(stderr != 0)

    low_t_labels = {
        label
        for label, t_value in zip(label_series, t_values, strict=False)
        if pd.notna(t_value) and math.fabs(float(t_value)) < t_threshold
    }

    resolved_path = Path(path) if path is not None else _DEFAULT_PARAMS_FREE2_PATH
    allow_suffixes = allow if allow is not None else [".center", ".scale", ".width"]
    allowed_indices = set(indices if indices is not None else [2, 3, 4, 8])

    lines = resolved_path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        return []

    header = lines[0].rstrip("\r\n").split(",")
    try:
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'label' column") from exc
    try:
        vary_idx = header.index("vary")
    except ValueError as exc:
        raise ValueError("parameters CSV has no 'vary' column") from exc

    changed: list[str] = []
    rewritten: list[str] = [lines[0]]
    for line in lines[1:]:
        stripped = line.rstrip("\r\n")
        cols = stripped.split(",")
        if len(cols) <= max(label_idx, vary_idx):
            rewritten.append(line)
            continue

        label = cols[label_idx].strip()

        matched = False
        for suffix in allow_suffixes:
            pos = label.rfind(suffix)
            if pos == -1:
                continue
            idx_str = label[pos + len(suffix) :]
            try:
                idx = int(idx_str)
            except ValueError:
                continue
            if idx in allowed_indices:
                matched = True
                break

        if not matched or label not in low_t_labels:
            rewritten.append(line)
            continue

        if cols[vary_idx].strip() != "False":
            cols[vary_idx] = "False"
            eol = line[len(stripped) :]
            rewritten.append(",".join(cols) + eol)
            changed.append(label)
        else:
            rewritten.append(line)

    resolved_path.write_text("".join(rewritten), encoding="utf-8")
    if changed:
        print(f"Set vary=False for {len(changed)} parameters with abs(T-value) < {t_threshold}:")
        for label in changed:
            print(f"  {label}")
    else:
        print("No parameters matched the suffix/index filter and T-value criterion.")
    return changed


def transform_width_parameters(
    model_or_scheme: str | Path | object,
    parameters_path: str | Path | None = None,
    *,
    mass: float,
    dataset_labels: list[str] | None = None,
    apply_stability_guard: bool = False,
    max_mass_to_minconvwidth_ratio: float | None = 1.0,
    output_path: str | Path | None = None,
) -> tuple[object, dict[str, float]]:
    """Transform width parameters in conv-multi-multi-gaussian IRFs by shifting mass to convwidth.

    Shifts `mass` amount from individual width parameters to the common convwidth parameter,
    preserving the effective broadened width in quadrature:
        cwidth_effective = sqrt(convwidth^2 + width^2)

    Works with both `type: conv-multi-multi-gaussian` and `type: norm-conv-multi-multi-gaussian` IRFs.
    For these IRF types, each width is broadened in quadrature with convwidth.
    This function shifts the mass from the widths to convwidth, reducing each width and
    increasing convwidth by the same amount in the effective (broadened) width space.

    Parameters
    ----------
    model_or_scheme : str | Path | Scheme | Model
        Either a Scheme object (which provides model and parameters),
        a Model object, or a path to the YAML model file.
    parameters_path : str | Path | None
        Path to the CSV parameters file. Required if model_or_scheme is not a Scheme.
    mass : float
        Amount to shift from width parameters to convwidth (can be positive or negative).
        Represents the change in convwidth: new_convwidth = convwidth + mass.
    dataset_labels : list[str] | None
        Optional list of IRF dataset labels to transform. Labels must match IRF keys
        in the model (for example ``"irfocol0open"``). If omitted, all compatible
        conv-multi-multi-gaussian IRF datasets are transformed.
    apply_stability_guard : bool
        Whether to apply a stability guard that skips IRFs with small convwidth values
        when the requested mass is large relative to convwidth. Defaults to ``False``
        (no exclusion). When ``True``, uses ``max_mass_to_minconvwidth_ratio`` as the threshold.
    max_mass_to_minconvwidth_ratio : float | None
        Stability guard threshold (only used if ``apply_stability_guard=True``).
        If ``abs(mass) / min(abs(convwidth))`` for an IRF exceeds this threshold,
        that IRF is skipped and a warning is emitted. Set to ``None`` to disable.
        Defaults to ``1.0``.
    output_path : str | Path | None
        If provided, writes the transformed parameters to this CSV file.

    Returns
    -------
    tuple[ParameterGroup, dict[str, float]]
        - Transformed ParameterGroup
        - Mapping of parameter names to their transformed values for inspection

    Raises
    ------
    ValueError
        If the mass transformation would result in negative width values or if the model
        does not contain a conv-multi-multi-gaussian IRF.
    TypeError
        If the model or parameters cannot be loaded.

    Notes
    -----
    The transformation preserves effective broadened width:
        cwidth_eff_original = sqrt(convwidth_old^2 + width_old^2)
        cwidth_eff_original = sqrt(convwidth_new^2 + width_new^2)

    Where:
        convwidth_new = convwidth_old + mass
        width_new = sqrt(cwidth_eff_original^2 - convwidth_new^2)

    Example
    -------
    Shift 1 unit of broadening from width parameters to convwidth:

    >>> from glotaran.project.scheme import Scheme
    >>> scheme = Scheme.from_yaml("model.yml", "parameters.csv")
    >>> params_new, transformed = transform_width_parameters(
    ...     scheme,
    ...     mass=1.0,
    ...     output_path="parameters_transformed.csv"
    ... )
    """

    from glotaran.io import load_model
    from glotaran.io import load_parameters
    from glotaran.model import Model

    try:
        from glotaran.project.scheme import Scheme
    except ImportError:
        Scheme = None

    scheme_instance = None
    if Scheme is not None:
        try:
            scheme_instance = isinstance(model_or_scheme, Scheme)
        except TypeError:
            scheme_instance = False

    if scheme_instance:
        model = model_or_scheme.model
        if parameters_path is None:
            parameters_path = model_or_scheme.parameters
    else:
        model = (
            model_or_scheme
            if isinstance(model_or_scheme, Model)
            else load_model(str(model_or_scheme), format_name="yaml")
        )

    if parameters_path is None:
        raise ValueError("parameters_path is required if model_or_scheme is not a Scheme object")

    parameters = load_parameters(str(parameters_path), format_name="csv")

    irf_config = _find_conv_multi_multi_gaussian_irfs(model)
    if not irf_config:
        raise ValueError(
            "No conv-multi-multi-gaussian or norm-conv-multi-multi-gaussian IRF found in the model. "
            "This function only works with models using these IRF types."
        )

    # Apply stability guard only if requested
    effective_ratio = max_mass_to_minconvwidth_ratio if apply_stability_guard else None

    transformed_values = _transform_width_values(
        irf_config,
        parameters,
        mass=mass,
        dataset_labels=dataset_labels,
        max_mass_to_minconvwidth_ratio=effective_ratio,
    )

    # Materialize transformed values in the returned parameter object.
    # The previous implementation returned the original loaded parameters and a
    # separate dict of transformed values, which made downstream use of
    # ``parameters=transformed_obj`` silently keep pre-transform values.
    parameters = _apply_transformed_values(parameters, transformed_values)

    if output_path is not None:
        _write_transformed_parameters(
            parameters, transformed_values, Path(output_path), parameters_path=parameters_path
        )

    return parameters, transformed_values


def _apply_transformed_values(parameters: object, transformed_values: dict[str, float]) -> object:
    """Apply transformed values to a parameters object, returning the transformed object.

    The function first tries in-place updates via ``parameters[label].value``. If
    those are not available, it attempts a dataframe roundtrip via
    ``type(parameters).from_dataframe(df)``.
    """

    if not transformed_values:
        return parameters

    updated_labels: set[str] = set()

    # Preferred path: mutate parameter values in-place.
    for label, new_value in transformed_values.items():
        try:
            param = parameters[label]
        except Exception:
            continue

        if hasattr(param, "value"):
            try:
                param.value = float(new_value)
                if _is_convwidth_parameter_label(label) and hasattr(param, "vary"):
                    param.vary = True
                updated_labels.add(label)
                continue
            except Exception:
                pass

    if len(updated_labels) == len(transformed_values):
        return parameters

    # Fallback path: dataframe roundtrip for parameter containers that expose it.
    if not hasattr(parameters, "to_dataframe"):
        return parameters

    try:
        df = parameters.to_dataframe().copy(deep=True)
    except Exception:
        return parameters

    if "value" not in df.columns:
        return parameters

    remaining = {
        label: value for label, value in transformed_values.items() if label not in updated_labels
    }
    if not remaining:
        return parameters

    if "label" in df.columns:
        for label, new_value in remaining.items():
            mask = df["label"].astype(str) == label
            if mask.any():
                df.loc[mask, "value"] = float(new_value)
                if "vary" in df.columns and _is_convwidth_parameter_label(label):
                    df.loc[mask, "vary"] = True
                updated_labels.add(label)
    else:
        index_labels = df.index.astype(str)
        for label, new_value in remaining.items():
            mask = index_labels == label
            if mask.any():
                df.loc[mask, "value"] = float(new_value)
                if "vary" in df.columns and _is_convwidth_parameter_label(label):
                    df.loc[mask, "vary"] = True
                updated_labels.add(label)

    if len(updated_labels) == len(transformed_values):
        from_dataframe = getattr(type(parameters), "from_dataframe", None)
        if callable(from_dataframe):
            try:
                return from_dataframe(df)
            except Exception:
                return parameters

    return parameters


def _find_conv_multi_multi_gaussian_irfs(model: object) -> dict[str, dict]:
    """Extract conv-multi-multi-gaussian IRF configuration from the model.

    Returns a dict mapping IRF label -> {"convwidth": [...], "width": [[...], [...]], ...}
    Accepts both conv-multi-multi-gaussian and norm-conv-multi-multi-gaussian types.
    """
    irf_config = {}

    irf_dict = getattr(model, "irf", {})
    for irf_label, irf in irf_dict.items():
        irf_type = getattr(irf, "type", None)
        if irf_type in ("conv-multi-multi-gaussian", "norm-conv-multi-multi-gaussian"):
            irf_config[irf_label] = {
                "convwidth": irf.convwidth,
                "width": irf.width,
            }

    return irf_config


def _is_convwidth_parameter_label(label: str) -> bool:
    """Return whether a parameter label represents a convwidth parameter."""

    return _CONVWIDTH_LABEL_RE.search(label) is not None


def _flatten_nested_params(param_list: list) -> list[str]:
    """Flatten a nested parameter list (from YAML) to a flat list of parameter names."""
    result = []

    def _recurse(item):
        if isinstance(item, list):
            for sub in item:
                _recurse(sub)
        elif isinstance(item, str):
            result.append(item)
        else:
            result.append(str(item))

    _recurse(param_list)
    return result


def _transform_width_values(
    irf_config: dict[str, dict],
    parameters: object,
    *,
    mass: float,
    dataset_labels: list[str] | None = None,
    max_mass_to_minconvwidth_ratio: float | None = 1.0,
) -> dict[str, float]:
    """Compute transformed parameter values for width parameters.

    **Dataset-level algorithm (per IRF):**

    Each IRF is a separate dataset. The 5 width parameters are shared across
    all wavelengths within that IRF, while convwidth parameters vary per wavelength.

    For each IRF:
        1. Find minconvwidth among all convwidth parameters
        2. Shift minconvwidth by +mass
        3. Compute required width change to preserve quadrature invariant:
           Δw² = -(2 * minconvwidth * mass + mass²)
        4. Apply same Δw² to all 5 shared width components
        5. Recompute all other convwidth parameters to maintain quadrature:
           new_convwidth_i = sqrt(convwidth_i² - Δw²)

    This preserves sqrt(convwidth_i² + width_j²) = constant for every (i,j) pair
    within each IRF independently.

    If mass would make any width negative for an IRF, the entire IRF's dataset
    is skipped and a UserWarning is issued.

    A stability guard also skips IRFs when ``mass`` is too large relative to the
    smallest convwidth magnitude in that IRF. This prevents extreme updates for
    datasets with near-zero convwidth values.
    """

    if max_mass_to_minconvwidth_ratio is not None and max_mass_to_minconvwidth_ratio < 0:
        raise ValueError("max_mass_to_minconvwidth_ratio must be non-negative or None")

    selected_labels = set(dataset_labels) if dataset_labels is not None else None
    if selected_labels is not None:
        unknown_labels = sorted(selected_labels - set(irf_config))
        if unknown_labels:
            available_labels = ", ".join(sorted(irf_config))
            unknown_str = ", ".join(unknown_labels)
            raise ValueError(
                "Unknown dataset_labels for width transform: "
                f"{unknown_str}. Available IRF labels: {available_labels}"
            )

    # Helper to get parameter value by label
    def get_param_value(label: str) -> float:
        """Get a parameter value by label, handling different parameter object types."""
        # Try direct bracket access first (works with test mocks and some glotaran versions)
        try:
            param = parameters[label]
            if hasattr(param, "value"):
                return float(param.value)
            return float(param)
        except (TypeError, KeyError):
            pass

        # Try accessing via attribute
        if hasattr(parameters, label):
            param = getattr(parameters, label)
            if hasattr(param, "value"):
                return float(param.value)
            return float(param)

        # Try dataframe conversion
        if hasattr(parameters, "to_dataframe"):
            df = parameters.to_dataframe()
            if label in df.index:
                row = df.loc[label]
                return float(row.get("value", 0.0))
            # Try by index/label column
            if "label" in df.columns:
                mask = df["label"] == label
                if mask.any():
                    return float(df[mask]["value"].iloc[0])

        raise ValueError(f"Cannot access parameter {label}")

    transformed: dict[str, float] = {}
    skipped_irfs: dict[str, dict] = {}

    # Process each IRF independently
    for irf_label, irf_params in irf_config.items():
        if selected_labels is not None and irf_label not in selected_labels:
            continue

        convwidth_params = _flatten_nested_params(irf_params["convwidth"])
        width_params = _flatten_nested_params(irf_params["width"])

        if not convwidth_params:
            raise ValueError(f"No convwidth parameters found for {irf_label}")

        # Get all convwidth and width values for this IRF
        convwidth_values = {p: get_param_value(p) for p in convwidth_params}
        width_values = {p: get_param_value(p) for p in width_params}

        # Find minimum convwidth within this IRF
        minconvwidth = min(convwidth_values.values())
        minconvwidth_abs = min(abs(value) for value in convwidth_values.values())

        # Stability guard: skip IRFs where requested mass dwarfs convwidth scale.
        if max_mass_to_minconvwidth_ratio is not None and abs(mass) > 0:
            mass_to_conv_ratio = abs(mass) / max(minconvwidth_abs, 1e-12)
            if mass_to_conv_ratio > max_mass_to_minconvwidth_ratio:
                skipped_irfs[irf_label] = {
                    "reason": "stability",
                    "minconvwidth_abs": minconvwidth_abs,
                    "mass_requested": mass,
                    "mass_to_conv_ratio": mass_to_conv_ratio,
                    "ratio_limit": max_mass_to_minconvwidth_ratio,
                }
                continue

        # Compute delta_w_sq for this IRF
        # delta_w_sq is negative: widths shrink
        delta_w_sq = -(2 * minconvwidth * mass + mass**2)

        # Validity check: every width_j^2 + delta_w_sq must remain >= 0
        min_width_sq = min(wv**2 for wv in width_values.values())
        if min_width_sq + delta_w_sq < 0:
            min_width = np.sqrt(min_width_sq)
            max_allowed_mass = np.sqrt(minconvwidth**2 + min_width_sq) - abs(minconvwidth)
            skipped_irfs[irf_label] = {
                "reason": "negative-width",
                "width_params": width_params,
                "minconvwidth": minconvwidth,
                "min_width": min_width,
                "mass_requested": mass,
                "max_allowed_mass": max_allowed_mass,
            }
            continue

        # New width values (same delta_w_sq for all Gaussian components)
        for wp, wv in width_values.items():
            transformed[wp] = np.sqrt(max(0.0, wv**2 + delta_w_sq))

        # New convwidth values for this IRF
        for cwp, cwv in convwidth_values.items():
            transformed[cwp] = np.sqrt(max(0.0, cwv**2 - delta_w_sq))

    # Warn about skipped IRFs
    if skipped_irfs:
        import warnings

        skip_msg = "The following IRF datasets could not be transformed (mass too large):\n"
        for irf_label, info in skipped_irfs.items():
            if info.get("reason") == "stability":
                skip_msg += (
                    f"  - {irf_label}: "
                    f"abs(mass)/min(|convwidth|)={info['mass_to_conv_ratio']:.4f} "
                    f"exceeds limit {info['ratio_limit']:.4f} "
                    f"(requested mass {info['mass_requested']}, "
                    f"min|convwidth|={info['minconvwidth_abs']:.4f})\n"
                )
            else:
                skip_msg += (
                    f"  - {irf_label}: "
                    f"minconvwidth={info['minconvwidth']:.4f}, "
                    f"min_width={info['min_width']:.4f}, "
                    f"max allowed mass={info['max_allowed_mass']:.4f} "
                    f"(requested {info['mass_requested']})\n"
                )
        warnings.warn(skip_msg, UserWarning)

    return transformed


def _write_transformed_parameters(
    parameters: object,
    transformed_values: dict[str, float],
    output_path: Path,
    parameters_path: Path | str | None = None,
) -> None:
    """Write transformed parameters to a CSV file, preserving format of original.

    Parameters
    ----------
    parameters : object
        The parameters object (ParameterGroup or similar)
    transformed_values : dict[str, float]
        Dictionary of parameter labels -> new transformed values
    output_path : Path
        Output CSV file path
    parameters_path : Path | str | None
        Path to the original CSV file to use as template for formatting
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Try to read original CSV file to preserve its format
    if parameters_path is not None:
        try:
            # Read the original CSV preserving all columns, including empty ones
            with open(str(parameters_path), "r") as f:
                original_header = f.readline().rstrip("\n")

            df = pd.read_csv(str(parameters_path), keep_default_na=False, na_values=[])

            # Update values in the dataframe for transformed parameters
            if "label" in df.columns and "value" in df.columns:
                for idx, row in df.iterrows():
                    label = row["label"]
                    if label in transformed_values:
                        df.at[idx, "value"] = transformed_values[label]
                        if "vary" in df.columns and _is_convwidth_parameter_label(str(label)):
                            df.at[idx, "vary"] = "True"

                # Write back, then fix the header to match original
                df.to_csv(output_path, index=False, sep=",", float_format="%.17g", na_rep="None")

                # Fix header: replace "Unnamed: X" columns with empty strings to match original
                with open(str(output_path), "r") as f:
                    lines = f.readlines()

                if lines:
                    # Replace the header line with the original header
                    lines[0] = original_header + "\n"

                    with open(str(output_path), "w") as f:
                        f.writelines(lines)

                return
        except Exception as e:
            # If reading original fails, fall through to create from scratch
            pass

    # Fallback: create from parameters object
    # Convert parameters to a dataframe if possible
    if hasattr(parameters, "to_dataframe"):
        try:
            df = parameters.to_dataframe()

            # Update transformed values
            if "label" in df.columns and "value" in df.columns:
                for label, new_value in transformed_values.items():
                    mask = df["label"].astype(str) == label
                    if mask.any():
                        df.loc[mask, "value"] = new_value
                        if "vary" in df.columns and _is_convwidth_parameter_label(label):
                            df.loc[mask, "vary"] = "True"

                df.to_csv(output_path, index=False, sep=",", float_format="%.17g", na_rep="None")
                return
        except Exception:
            pass

    # Last resort: create minimal output with just labels and values
    df_data = []
    labels = getattr(parameters, "labels", list(transformed_values.keys()))

    for label in labels:
        if label in transformed_values:
            value = transformed_values[label]
        else:
            value = None

        df_data.append(
            {
                "label": label,
                "value": value,
                "vary": "True" if _is_convwidth_parameter_label(str(label)) else None,
            }
        )

    df = pd.DataFrame(df_data)
    df.to_csv(output_path, index=False, sep=",", float_format="%.17g", na_rep="None")
