from __future__ import annotations

import sys
import types

sys.modules.setdefault("matplotlib", types.ModuleType("matplotlib"))
sys.modules.setdefault("matplotlib.pyplot", types.ModuleType("matplotlib.pyplot"))

cycler_module = types.ModuleType("cycler")


class _Cycler:
    pass


cycler_module.Cycler = _Cycler
cycler_module.cycler = lambda *args, **kwargs: None
sys.modules.setdefault("cycler", cycler_module)

pyglotaran_extras = types.ModuleType("pyglotaran_extras")
pyglotaran_extras.add_subplot_labels = lambda *args, **kwargs: None
sys.modules.setdefault("pyglotaran_extras", pyglotaran_extras)

io_utils_module = types.ModuleType("pyglotaran_extras.io.utils")
io_utils_module.result_dataset_mapping = lambda result: result
sys.modules.setdefault("pyglotaran_extras.io", types.ModuleType("pyglotaran_extras.io"))
sys.modules.setdefault("pyglotaran_extras.io.utils", io_utils_module)

plotting_package = types.ModuleType("pyglotaran_extras.plotting")
sys.modules.setdefault("pyglotaran_extras.plotting", plotting_package)


def _noop(*args, **kwargs):
    return None


for module_name, attribute_names in {
    "pyglotaran_extras.plotting.plot_concentrations": ["plot_concentrations"],
    "pyglotaran_extras.plotting.plot_residual": ["plot_residual"],
    "pyglotaran_extras.plotting.plot_spectra": ["plot_das", "plot_norm_sas", "plot_sas"],
    "pyglotaran_extras.plotting.plot_svd": ["plot_lsv_residual", "plot_rsv_residual"],
    "pyglotaran_extras.plotting.plot_traces": ["plot_fitted_traces"],
    "pyglotaran_extras.plotting.utils": [
        "MinorSymLogLocator",
        "extract_dataset_scale",
        "extract_irf_location",
    ],
}.items():
    module = types.ModuleType(module_name)
    for attribute_name in attribute_names:
        if attribute_name == "MinorSymLogLocator":
            module.MinorSymLogLocator = type("MinorSymLogLocator", (), {})
        else:
            setattr(module, attribute_name, _noop)
    sys.modules.setdefault(module_name, module)

style_module = types.ModuleType("pyglotaran_extras.plotting.style")


class _DummyCycler:
    def by_key(self):
        return {"color": ["black"]}


class _PlotStyle:
    def __init__(self):
        self.data_cycler_solid = _DummyCycler()


style_module.PlotStyle = _PlotStyle
sys.modules.setdefault("pyglotaran_extras.plotting.style", style_module)

types_module = types.ModuleType("pyglotaran_extras.types")
types_module.ResultLike = object
sys.modules.setdefault("pyglotaran_extras.types", types_module)

from pygta_local_extras.analysis import plot_residuals  # noqa: E402


def test_plot_residuals_is_exported_from_analysis() -> None:
    assert callable(plot_residuals)
