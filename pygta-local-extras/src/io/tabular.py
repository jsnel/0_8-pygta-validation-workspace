from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal
from typing import TypeAlias

import pandas as pd
import xarray as xr

DatasetOrdering: TypeAlias = Literal["time_explicit", "wavelength_explicit"]


def load_dataset_from_csv(
    filepath: str | Path,
    *,
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    index_col: int | None = 0,
    header: int | None = 0,
    delimiter: str = ",",
    ordering: DatasetOrdering = "time_explicit",
    variable_name: str = "data",
) -> xr.Dataset:
    """Load a rectangular CSV file into an xarray dataset."""
    df = pd.read_csv(
        filepath,
        index_col=index_col,
        header=header,
        delimiter=delimiter,
        skipinitialspace=True,
    )
    df = _handle_missing_values(
        df,
        replace_nan_with_zeros=replace_nan_with_zeros,
        silence_warnings=silence_warnings,
    )

    if ordering == "time_explicit":
        df = df.T
        if len(df.columns) and _is_padding_value(df.columns[0]):
            df = df.iloc[:, 1:]
            _warn("Padded first row detected and removed.", silence_warnings)
    elif ordering == "wavelength_explicit":
        if len(df.index) and _is_padding_value(df.index[0]):
            df = df.iloc[1:, :]
            _warn("Padded first column detected and removed.", silence_warnings)
    else:
        raise ValueError(
            "Invalid ordering type. Must be 'time_explicit' or 'wavelength_explicit'."
        )

    df.index = pd.to_numeric(df.index, errors="coerce")
    df.columns = pd.to_numeric(df.columns, errors="coerce")
    df = df.loc[df.index.notnull(), df.columns.notnull()]

    return _dataframe_to_dataset(df, variable_name=variable_name)


csv_to_dataset = load_dataset_from_csv


def load_dataset_from_csv_legacy(
    filepath: str | Path,
    *,
    replace_nan_with_zeros: bool = True,
    silence_warnings: bool = False,
    index_col: int | None = 0,
    header: int | None = 0,
    delimiter: str = ",",
    ordering: DatasetOrdering = "time_explicit",
    variable_name: str = "data",
) -> xr.Dataset:
    """Compatibility implementation for the original simpler CSV loader."""
    df = pd.read_csv(
        filepath,
        index_col=index_col,
        header=header,
        delimiter=delimiter,
        skipinitialspace=True,
    )
    df = _handle_missing_values(
        df,
        replace_nan_with_zeros=replace_nan_with_zeros,
        silence_warnings=silence_warnings,
    )

    df.index = pd.to_numeric(df.index)
    df.columns = pd.to_numeric(df.columns)
    if ordering == "time_explicit":
        df = df.T
    elif ordering != "wavelength_explicit":
        raise ValueError(
            "Invalid ordering type. Must be 'time_explicit' or 'wavelength_explicit'."
        )

    return _dataframe_to_dataset(df, variable_name=variable_name)


csv_to_dataset_org = load_dataset_from_csv_legacy


def _handle_missing_values(
    df: pd.DataFrame,
    *,
    replace_nan_with_zeros: bool,
    silence_warnings: bool,
) -> pd.DataFrame:
    if not df.isnull().values.any():
        return df

    if replace_nan_with_zeros:
        _warn("NaN values detected and replaced with zeros.", silence_warnings)
        return df.fillna(0)

    _warn("NaN values detected but not replaced.", silence_warnings)
    return df


def _dataframe_to_dataset(df: pd.DataFrame, *, variable_name: str) -> xr.Dataset:
    return xr.DataArray(
        df.to_numpy(dtype=float),
        dims=["time", "spectral"],
        coords={
            "time": df.index.to_numpy(dtype=float),
            "spectral": df.columns.to_numpy(dtype=float),
        },
    ).to_dataset(name=variable_name)


def _is_padding_value(value: object) -> bool:
    if pd.isna(value):
        return True
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def _warn(message: str, silence_warnings: bool) -> None:
    if not silence_warnings:
        warnings.warn(message, stacklevel=3)
