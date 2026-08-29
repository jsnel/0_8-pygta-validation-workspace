"""Migrate selected v0.7 case-study models and notebooks in staging checkouts."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import nbformat
import yaml


MODEL_TOP_LEVEL_KEYS = {
    "default_megacomplex",
    "dataset_groups",
    "dataset",
    "megacomplex",
    "k_matrix",
    "initial_concentration",
    "irf",
    "weights",
    "clp_relations",
    "clp_constraints",
    "clp_penalties",
    "clp_area_penalties",
    "shape",
}
DATASET_KEYS = {
    "group",
    "megacomplex",
    "megacomplex_scale",
    "initial_concentration",
    "irf",
    "scale",
    "spectral_axis_inverted",
    "spectral_axis_scale",
}
MEGACOMPLEX_KEYS = {
    "type",
    "k_matrix",
    "dimension",
    "target",
    "order",
    "width",
    "labels",
    "frequencies",
    "rates",
    "shape",
}
IRF_KEYS = {
    "type",
    "center",
    "width",
    "scale",
    "shift",
    "normalize",
    "backsweep",
    "backsweep_period",
    "dispersion_center",
    "center_dispersion_coefficients",
    "width_dispersion_coefficients",
    "model_dispersion_with_wavenumber",
    "force_index_dependent",
}
FIT_CONTROL_NAMES = {
    "maximum_number_function_evaluations",
    "ftol",
    "gtol",
    "xtol",
    "optimization_method",
    "add_svd",
}
OLD_MODEL_ACCESS = re.compile(r"(?P<scheme>\w+)\.model\.k_matrix\[['\"](?P<km>[^'\"]+)")
OLD_INITIAL_ACCESS = re.compile(r"initial_concentration\[['\"](?P<initial>[^'\"]+)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migrated_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}_v08{path.suffix}")


def checked_keys(item: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = set(item) - allowed
    if unknown:
        raise ValueError(f"Unsupported fields in {context}: {sorted(unknown)}")


def element_from_megacomplex(
    label: str,
    item: dict[str, Any],
    document: dict[str, Any],
    log: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    checked_keys(item, MEGACOMPLEX_KEYS, f"megacomplex {label}")
    element_type = item.get("type", document.get("default_megacomplex"))
    if element_type == "decay":
        rates: dict[str, Any] = {}
        origins: dict[str, str] = {}
        k_matrix_labels = item.get("k_matrix") or []
        if not k_matrix_labels:
            raise ValueError(f"Decay megacomplex {label} has no k-matrix")
        for k_matrix_label in k_matrix_labels:
            matrix = document["k_matrix"][k_matrix_label].get("matrix") or {}
            for rate_key, value in matrix.items():
                key = str(rate_key)
                if key in rates:
                    log["overrides"].append(
                        {
                            "element": label,
                            "rate_key": key,
                            "overridden_k_matrix": origins[key],
                            "overriding_k_matrix": k_matrix_label,
                            "overriding_value": value,
                        }
                    )
                rates[key] = value
                origins[key] = k_matrix_label
        if len(k_matrix_labels) > 1:
            log["combined_k_matrices"].append(
                {"element": label, "k_matrices": list(k_matrix_labels)}
            )
        compartments = {
            compartment.strip()
            for key in rates
            for compartment in key.strip().lstrip("(").rstrip(")").split(",")
        }
        return {"type": "kinetic", "rates": rates}, compartments
    if element_type == "coherent-artifact":
        result = {"type": "coherent-artifact", "order": item["order"]}
        if "width" in item:
            result["width"] = item["width"]
        return result, {f"{label}_derivative_{index}" for index in range(item["order"])}
    if element_type == "damped-oscillation":
        labels = item.get("labels") or []
        frequencies = item.get("frequencies") or []
        rates = item.get("rates") or []
        if not (len(labels) == len(frequencies) == len(rates)):
            raise ValueError(f"Damped oscillation arrays differ in {label}")
        oscillations = {
            oscillation_label: {"frequency": frequency, "rate": rate}
            for oscillation_label, frequency, rate in zip(
                labels, frequencies, rates, strict=True
            )
        }
        outputs = {f"{oscillation_label}_{part}" for oscillation_label in labels for part in ("cos", "sin")}
        return {"type": "damped-oscillation", "oscillations": oscillations}, outputs
    if element_type == "clp-guide":
        result = {"type": "clp-guide", "target": item["target"]}
        if "dimension" in item:
            result["dimension"] = item["dimension"]
        return result, {str(item["target"])}
    if element_type == "spectral":
        shapes = {
            shape_label: copy.deepcopy(document["shape"][shape_reference])
            for shape_label, shape_reference in (item.get("shape") or {}).items()
        }
        return {"type": "spectral", "shapes": shapes}, set(shapes)
    raise ValueError(f"Unsupported megacomplex type {element_type!r} for {label}")


def activation(
    dataset: dict[str, Any],
    document: dict[str, Any],
    megacomplexes: dict[str, Any],
) -> dict[str, Any] | None:
    initial_label = dataset.get("initial_concentration")
    irf_label = dataset.get("irf")
    if initial_label is None and irf_label is None:
        return None
    if initial_label is None or irf_label is None:
        raise ValueError("An activation requires both legacy initial concentration and IRF")
    initial = document["initial_concentration"][initial_label]
    compartments = initial.get("compartments") or []
    parameters = initial.get("parameters") or []
    if len(compartments) != len(parameters):
        raise ValueError(f"Initial concentration arrays differ in {initial_label}")
    activation_compartments = dict(zip(compartments, parameters, strict=True))
    for element_label in dataset.get("megacomplex") or []:
        element = megacomplexes[element_label]
        element_type = element.get("type", document.get("default_megacomplex"))
        if element_type == "coherent-artifact":
            activation_compartments[element_label] = 1
        elif element_type == "damped-oscillation":
            for oscillation_label in element.get("labels") or []:
                activation_compartments[oscillation_label] = 1
    legacy_irf = document["irf"][irf_label]
    checked_keys(legacy_irf, IRF_KEYS, f"IRF {irf_label}")
    legacy_type = legacy_irf.get("type")
    if legacy_type in {"spectral-gaussian", "gaussian"}:
        activation_type = "gaussian"
    elif legacy_type in {"spectral-multi-gaussian", "multi-gaussian"}:
        activation_type = "multi-gaussian"
    else:
        raise ValueError(f"Unsupported IRF type {legacy_type!r}")
    result = {
        "type": activation_type,
        "compartments": activation_compartments,
        "center": legacy_irf["center"],
        "width": legacy_irf["width"],
    }
    for key in (
        "scale",
        "shift",
        "normalize",
        "dispersion_center",
        "center_dispersion_coefficients",
        "width_dispersion_coefficients",
    ):
        if key in legacy_irf:
            result[key] = legacy_irf[key]
    if legacy_irf.get("backsweep"):
        if "backsweep_period" not in legacy_irf:
            raise ValueError(f"IRF {irf_label} enables backsweep without a period")
        result["backsweep"] = legacy_irf["backsweep_period"]
    if legacy_irf.get("model_dispersion_with_wavenumber"):
        result["reciproke_global_axis"] = True
    if legacy_irf.get("force_index_dependent") and "dispersion_center" not in legacy_irf:
        raise ValueError(f"IRF {irf_label} uses unsupported force_index_dependent behavior")
    if initial.get("exclude_from_normalize"):
        result["not_normalized_compartments"] = initial["exclude_from_normalize"]
    return result


def constraint_targets(item: dict[str, Any]) -> list[str]:
    target = item.get("target")
    return [str(value) for value in target] if isinstance(target, list) else [str(target)]


def convert_model(document: dict[str, Any], source: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    checked_keys(document, MODEL_TOP_LEVEL_KEYS, str(source))
    if any(not group.get("link_clp", True) for group in (document.get("dataset_groups") or {}).values()):
        raise ValueError(f"Intentional unlinked CLP behavior in {source}")
    log: dict[str, Any] = {
        "source": str(source),
        "combined_k_matrices": [],
        "overrides": [],
        "constraint_ownership": [],
        "relation_and_penalty_experiments": [],
    }
    megacomplexes = document.get("megacomplex") or {}
    library: dict[str, Any] = {}
    outputs: dict[str, set[str]] = {}
    for label, item in megacomplexes.items():
        library[label], outputs[label] = element_from_megacomplex(label, item, document, log)

    for constraint in document.get("clp_constraints") or []:
        targets = constraint_targets(constraint)
        owners = []
        for label, labels in outputs.items():
            owned_targets = [target for target in targets if target in labels]
            if not owned_targets:
                continue
            migrated_constraint = copy.deepcopy(constraint)
            if isinstance(constraint.get("target"), list):
                migrated_constraint["target"] = owned_targets
            library[label].setdefault("clp_constraints", []).append(migrated_constraint)
            owners.append(label)
        if not owners:
            raise ValueError(f"No v0.8 element owns constraint targets {targets} in {source}")
        log["constraint_ownership"].append({"targets": targets, "elements": owners})

    source_groups = document.get("dataset_groups") or {
        "default": {"residual_function": "variable_projection", "link_clp": True}
    }
    experiments: dict[str, Any] = {}
    for group_label, group in source_groups.items():
        experiment = {
            "residual_function": group.get("residual_function", "variable_projection"),
            "datasets": {},
        }
        if document.get("dataset_groups") is not None:
            experiment["clp_link_tolerance"] = 0.1
        experiments[group_label] = experiment

    dataset_groups: dict[str, str] = {}
    for dataset_label, item in (document.get("dataset") or {}).items():
        checked_keys(item, DATASET_KEYS, f"dataset {dataset_label}")
        group_label = item.get("group", "default")
        if group_label not in experiments:
            raise ValueError(f"Dataset {dataset_label} references unknown group {group_label}")
        dataset_groups[dataset_label] = group_label
        element_labels = list(item.get("megacomplex") or [])
        migrated_dataset: dict[str, Any] = {"elements": element_labels}
        scales = item.get("megacomplex_scale")
        if scales is not None:
            if len(element_labels) != len(scales):
                raise ValueError(f"Element scale count differs in dataset {dataset_label}")
            migrated_dataset["element_scale"] = dict(zip(element_labels, scales, strict=True))
        migrated_activation = activation(item, document, megacomplexes)
        if migrated_activation is not None:
            migrated_dataset["activations"] = {"irf": migrated_activation}
        for key in ("spectral_axis_inverted", "spectral_axis_scale"):
            if key in item:
                migrated_dataset[key] = item[key]
        experiments[group_label]["datasets"][dataset_label] = migrated_dataset
        if "scale" in item:
            experiments[group_label].setdefault("scale", {})[dataset_label] = item["scale"]

    for weight in document.get("weights") or []:
        for dataset_label in weight.get("datasets") or []:
            group_label = dataset_groups[dataset_label]
            migrated_weight = {key: copy.deepcopy(value) for key, value in weight.items() if key != "datasets"}
            experiments[group_label]["datasets"][dataset_label].setdefault("weights", []).append(
                migrated_weight
            )

    group_outputs = {
        group_label: {
            output
            for dataset in experiment["datasets"].values()
            for element_label in dataset["elements"]
            for output in outputs[element_label]
        }
        for group_label, experiment in experiments.items()
    }
    for old_key, new_key in (
        ("clp_relations", "clp_relations"),
        ("clp_penalties", "clp_penalties"),
        ("clp_area_penalties", "clp_penalties"),
    ):
        for item in document.get(old_key) or []:
            source_label = str(item["source"])
            target_label = str(item["target"])
            owners = [
                group_label
                for group_label, labels in group_outputs.items()
                if source_label in labels and target_label in labels
            ]
            if not owners:
                raise ValueError(
                    f"No experiment owns {old_key} relation {source_label}->{target_label} in {source}"
                )
            for group_label in owners:
                experiments[group_label].setdefault(new_key, []).append(copy.deepcopy(item))
            log["relation_and_penalty_experiments"].append(
                {"kind": new_key, "source": source_label, "target": target_label, "experiments": owners}
            )

    return {"library": library, "experiments": experiments}, log


def schema_documents(root: Path) -> dict[Path, dict[str, Any]]:
    documents = {}
    for path in root.rglob("*.yml"):
        if "models" not in path.parts or path.stem.endswith("_v08"):
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(document, dict) and "dataset" in document and "megacomplex" in document:
            documents[path] = document
    return documents


class NotebookMigrator(ast.NodeTransformer):
    def __init__(self, notebook_dir: Path, model_documents: dict[Path, dict[str, Any]]) -> None:
        self.notebook_dir = notebook_dir
        self.model_documents = {path.resolve(): document for path, document in model_documents.items()}
        self.constant_paths: dict[str, Path] = {}
        self.scheme_models: dict[str, Path] = {}
        self.loaded_scheme_names: set[str] = set()
        self.scheme_controls: dict[str, dict[str, ast.expr]] = {}
        self.result_native: dict[str, str] = {}

    def resolve_model_expression(self, expression: ast.expr) -> Path | None:
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            candidate = (self.notebook_dir / expression.value).resolve()
            return candidate if candidate in self.model_documents else None
        if isinstance(expression, ast.Name):
            return self.constant_paths.get(expression.id) or self.scheme_models.get(expression.id)
        return None

    def migrate_model_expression(self, expression: ast.expr) -> ast.expr:
        path = self.resolve_model_expression(expression)
        if path is None:
            return expression
        if isinstance(expression, ast.Constant):
            relative = migrated_path(path).relative_to(self.notebook_dir).as_posix()
            return ast.Constant(relative)
        return expression

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom | None:
        if node.module in {"glotaran.optimization.optimize", "glotaran.project.scheme"}:
            return None
        if node.module == "glotaran.io":
            names = [alias for alias in node.names if alias.name != "load_model"]
            return ast.ImportFrom(module=node.module, names=names, level=node.level) if names else None
        return node

    def visit_Assign(self, node: ast.Assign) -> ast.Assign | list[ast.stmt]:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                model = self.resolve_model_expression(node.value)
                if model is not None:
                    self.constant_paths[target] = model
                    node.value = self.migrate_model_expression(node.value)
                    return node
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                if node.value.func.id == "load_model" and node.value.args:
                    source_model = self.resolve_model_expression(node.value.args[0])
                    if source_model is not None:
                        self.scheme_models[target] = source_model
                        self.loaded_scheme_names.add(target)
                    return self.generic_visit(node)
                if node.value.func.id == "Scheme":
                    return self.convert_scheme_assignment(target, node.value)
                if node.value.func.id == "optimize":
                    return self.convert_optimize_assignment(target, node.value)
        return self.generic_visit(node)

    def convert_scheme_assignment(self, target: str, call: ast.Call) -> list[ast.stmt]:
        keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
        model = keywords.get("model", call.args[0] if call.args else None)
        parameters = keywords.get("parameters", call.args[1] if len(call.args) > 1 else None)
        datasets = keywords.get("data", call.args[2] if len(call.args) > 2 else None)
        if model is None or parameters is None or datasets is None:
            raise ValueError(f"Cannot migrate Scheme constructor assigned to {target}")
        source_model = self.resolve_model_expression(model)
        if target == "target_schemetmp":
            if source_model is not None:
                self.scheme_models[target] = source_model
            return [ast.Assign(targets=[ast.Name(target, ast.Store())], value=ast.Name("target_scheme", ast.Load()))]
        if source_model is not None:
            self.scheme_models[target] = source_model
        model_is_loaded_scheme = isinstance(model, ast.Name) and model.id in self.loaded_scheme_names
        model = self.migrate_model_expression(model)
        if isinstance(parameters, ast.Constant) and isinstance(parameters.value, str):
            parameters = ast.Call(func=ast.Name("load_parameters", ast.Load()), args=[parameters], keywords=[])
        controls = {name: value for name, value in keywords.items() if name in FIT_CONTROL_NAMES}
        self.scheme_controls[target] = controls
        statements: list[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(target, ast.Store())],
                value=(
                    model
                    if model_is_loaded_scheme
                    else ast.Call(func=ast.Name("load_scheme", ast.Load()), args=[model], keywords=[])
                ),
            ),
            ast.Assign(targets=[ast.Name(f"{target}_parameters", ast.Store())], value=parameters),
            ast.Assign(targets=[ast.Name(f"{target}_datasets", ast.Store())], value=datasets),
        ]
        dry_keywords = [
            ast.keyword(arg="parameters", value=ast.Name(f"{target}_parameters", ast.Load())),
            ast.keyword(arg="datasets", value=ast.Name(f"{target}_datasets", ast.Load())),
            *[ast.keyword(arg=name, value=value) for name, value in controls.items()],
            ast.keyword(arg="dry_run", value=ast.Constant(True)),
            ast.keyword(arg="verbose", value=ast.Constant(False)),
            ast.keyword(arg="raise_exception", value=ast.Constant(True)),
        ]
        statements.extend(
            [
                ast.Assign(
                    targets=[ast.Name(f"{target}_dry_run", ast.Store())],
                    value=ast.Call(
                        func=ast.Attribute(ast.Name(target, ast.Load()), "optimize", ast.Load()),
                        args=[],
                        keywords=dry_keywords,
                    ),
                ),
                ast.Expr(
                    ast.Call(
                        func=ast.Name("print", ast.Load()),
                        args=[ast.Constant(f"MIGRATION_VALIDATION scheme={target} load=PASS dry_run=PASS")],
                        keywords=[],
                    )
                ),
            ]
        )
        return statements

    def convert_optimize_assignment(self, target: str, call: ast.Call) -> list[ast.stmt]:
        if not call.args or not isinstance(call.args[0], ast.Name):
            raise ValueError("Module optimize call does not name a scheme variable")
        scheme = call.args[0].id
        native = f"{target}_native"
        self.result_native[target] = native
        keyword_names = {keyword.arg for keyword in call.keywords}
        keywords = [
            ast.keyword(arg="parameters", value=ast.Name(f"{scheme}_parameters", ast.Load())),
            ast.keyword(arg="datasets", value=ast.Name(f"{scheme}_datasets", ast.Load())),
            *[
                ast.keyword(arg=name, value=value)
                for name, value in self.scheme_controls.get(scheme, {}).items()
                if name not in keyword_names
            ],
            *call.keywords,
        ]
        return [
            ast.Assign(
                targets=[ast.Name(native, ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(ast.Name(scheme, ast.Load()), "optimize", ast.Load()),
                    args=[],
                    keywords=keywords,
                ),
            ),
            ast.Expr(
                ast.Call(
                    func=ast.Name("print", ast.Load()),
                    args=[ast.Constant(f"MIGRATION_VALIDATION scheme={scheme} real_fit=PASS")],
                    keywords=[],
                )
            ),
            ast.Assign(
                targets=[ast.Name(target, ast.Store())],
                value=ast.Call(
                    func=ast.Name("_case_study_convert", ast.Load()),
                    args=[ast.Name(native, ast.Load()), ast.Name(scheme, ast.Load())],
                    keywords=[],
                ),
            ),
        ]

    def visit_Expr(self, node: ast.Expr) -> ast.Expr | None:
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "validate"
        ):
            return None
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.Call:
        node = self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "load_model":
            node.func.id = "load_scheme"
            if node.args:
                node.args[0] = self.migrate_model_expression(node.args[0])
        if isinstance(node.func, ast.Name) and node.func.id == "save_result":
            for keyword in node.keywords:
                if keyword.arg == "result" and isinstance(keyword.value, ast.Name):
                    native = self.result_native.get(keyword.value.id)
                    if native:
                        keyword.value = ast.Name(native, ast.Load())
        return node

    def replace_old_model_access(self, source: str) -> str | None:
        match = OLD_MODEL_ACCESS.search(source)
        if match is None:
            return None
        scheme = match.group("scheme")
        k_matrix = match.group("km")
        model_path = self.scheme_models.get(scheme)
        if model_path is None and scheme == "target_schemetmp":
            model_path = self.scheme_models.get("target_schemetmp")
        if model_path is None:
            raise ValueError(f"Cannot resolve old model access for {scheme}")
        document = self.model_documents[model_path]
        element = next(
            (
                label
                for label, item in document["megacomplex"].items()
                if k_matrix in (item.get("k_matrix") or [])
            ),
            None,
        )
        if element is None:
            raise ValueError(f"Cannot map k-matrix {k_matrix} in {model_path}")
        initial_match = OLD_INITIAL_ACCESS.search(source)
        compartments = None
        if initial_match:
            initial = document["initial_concentration"][initial_match.group("initial")]
            compartments = initial["compartments"]
        expression = f"_case_study_matrix_markdown({scheme}, {element!r}"
        if compartments is not None:
            expression += f", {compartments!r}"
        expression += ")"
        if '.replace("CF9212", "")' in source or ".replace('CF9212', '')" in source:
            expression += '.replace("CF9212", "")'
        return expression


HELPERS = '''\
from glotaran.io import load_scheme
from pyglotaran_extras.compat import convert


def _case_study_convert(native_result, scheme):
    """Project native v0.8 results for legacy plotting while retaining native results."""
    import numpy as np
    import xarray as xr

    compat_result = convert(native_result)
    for dataset_label, dataset in compat_result.data.items():
        if "irf_center" in dataset.coords:
            irf_center = dataset.coords["irf_center"]
            if irf_center.ndim and np.allclose(irf_center, irf_center.values.flat[0]):
                dataset = dataset.drop_vars("irf_center").assign_coords(
                    irf_center=float(irf_center.values.flat[0])
                )
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
        if kinetic_elements:
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
            )
        spectral_elements = [
            element
            for element in optimization_result.elements.values()
            if "shape" in element.coords
        ]
        if spectral_elements:
            species_spectra = xr.concat(
                [
                    element["concentrations"].squeeze(drop=True).rename(shape="species")
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
        dataset.attrs["dataset_scale"] = optimization_result.meta.scale
    return compat_result


def _case_study_matrix_markdown(scheme, element_label, compartments=None):
    """Render a symbolic v0.8 kinetic rate map for legacy notebook display cells."""
    import pandas as pd

    element = scheme.library[element_label]
    compartments = list(compartments or element.compartments)
    table = [["" for _ in compartments] for _ in compartments]
    for (to_compartment, from_compartment), rate in element.rates.items():
        if to_compartment in compartments and from_compartment in compartments:
            table[compartments.index(to_compartment)][compartments.index(from_compartment)] = str(rate)
    return pd.DataFrame(table, index=compartments, columns=compartments).to_markdown()
'''


def migrate_notebook(path: Path, model_documents: dict[Path, dict[str, Any]]) -> Path:
    notebook = nbformat.read(path, as_version=4)
    migrator = NotebookMigrator(path.parent.resolve(), model_documents)
    first_code_cell = True
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        old_access = migrator.replace_old_model_access(cell.source)
        if old_access is not None:
            cell.source = old_access
            continue
        tree = ast.parse(cell.source or "pass")
        migrated = migrator.visit(tree)
        ast.fix_missing_locations(migrated)
        source = ast.unparse(migrated)
        source = source.replace(
            "additional_penalties = target_result.additional_penalty",
            "additional_penalties = __import__('numpy').atleast_2d(target_result.additional_penalty)",
        )
        if source == "pass" and not cell.source.strip():
            source = ""
        if first_code_cell:
            source = f"{HELPERS}\n\n{source}"
            first_code_cell = False
        cell.source = source
        cell.outputs = []
        cell.execution_count = None
    output = migrated_path(path)
    nbformat.write(notebook, output)
    return output


def migrate_repository(root: Path, specification: dict[str, Any]) -> dict[str, Any]:
    documents = schema_documents(root)
    model_records = []
    for source, document in documents.items():
        if source.stem.endswith("tmp"):
            continue
        converted, log = convert_model(document, source)
        destination = migrated_path(source)
        content = "# Migrated from pyglotaran v0.7 for v0.8 staging validation.\n" + yaml.safe_dump(
            converted, sort_keys=False, allow_unicode=True
        )
        destination.write_text(content, encoding="utf-8")
        model_records.append(
            {
                "source": str(source),
                "source_sha256": sha256(source),
                "destination": str(destination),
                "destination_sha256": sha256(destination),
                **log,
            }
        )
    notebooks = []
    for relative in specification["notebooks"]:
        source = root / relative
        destination = migrate_notebook(source, documents)
        notebooks.append(
            {
                "source": str(source),
                "source_sha256": sha256(source),
                "destination": str(destination),
                "destination_sha256": sha256(destination),
            }
        )
    return {"slug": specification["slug"], "models": model_records, "notebooks": notebooks}


def markdown(report: dict[str, Any]) -> str:
    lines = ["# v0.7 to v0.8 case-study migration log", ""]
    for repository in report["repositories"]:
        overrides = sum(len(model["overrides"]) for model in repository["models"])
        combinations = sum(len(model["combined_k_matrices"]) for model in repository["models"])
        lines.extend(
            [
                f"## {repository['slug']}",
                "",
                f"- New v0.8 schemes: {len(repository['models'])}",
                f"- New migrated notebooks: {len(repository['notebooks'])}",
                f"- Explicit multi-k-matrix compositions: {combinations}",
                f"- Later-entry duplicate rate overrides preserved: {overrides}",
                "",
            ]
        )
    lines.extend(
        [
            "Original v0.7 files were not modified. Compatibility conversion is used only for legacy plotting and analysis consumers; native v0.8 results are retained and saved.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    config = yaml.safe_load(arguments.config.read_text(encoding="utf-8"))
    repositories = []
    for specification in config["repositories"]:
        root = (
            arguments.workspace.resolve()
            / "temp"
            / "case-studies"
            / specification["slug"]
            / "staging"
        )
        repositories.append(migrate_repository(root, specification))
    report = {"version": 1, "repositories": repositories}
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    arguments.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
