"""Small, dependency-light semantic result model used by validation tooling."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr


@dataclass
class DatasetView:
    """One dataset projected into the common v0.7 semantic vocabulary."""

    label: str
    variables: dict[str, xr.DataArray] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_files: dict[str, str] = field(default_factory=dict)
    transformations: list[str] = field(default_factory=list)
    unmapped_fields: list[str] = field(default_factory=list)
    raw_variables: dict[str, xr.DataArray] = field(default_factory=dict)


@dataclass
class ResultView:
    """A v0.7-compatible semantic projection of one saved result leaf."""

    scenario: str
    root: Path
    format: str
    datasets: dict[str, DatasetView] = field(default_factory=dict)
    parameters: pd.DataFrame | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    transformations: list[str] = field(default_factory=list)
    unmapped_fields: list[str] = field(default_factory=list)
    scheme: dict[str, Any] = field(default_factory=dict)
