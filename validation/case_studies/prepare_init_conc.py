"""Prepare the authorized, portable TestCaseInitConc analysis copies.

Run with ``python -m validation.case_studies.prepare_init_conc --output PATH``.
Original notebooks remain untouched. This adapter intentionally selects the first
target analysis and replaces optional development-only presentation cells.
"""

from __future__ import annotations

import argparse
import copy
import json
import io
import subprocess
import zipfile
from pathlib import Path

import nbformat
import yaml

from validation.case_studies.migrate import convert_model, migrate_notebook, sha256


PLOTS = '''from pathlib import Path
import matplotlib.pyplot as plt
from cycler import cycler
from pyglotaran_extras.plotting.plot_concentrations import plot_concentrations
from pyglotaran_extras.plotting.plot_spectra import plot_sas, plot_das, plot_norm_das

plot_root = Path("plots")
plot_root.mkdir(exist_ok=True)
colors = cycler(color=["#999999", "black", "#ff8800", "red", "cyan", "blue", "lime", "magenta", "#008800"])
for state in (1, 2):
    fig, axes = plt.subplots(4, 4, figsize=(24, 16), sharex="col", constrained_layout=True)
    for row in range(4):
        label = f"dataSt{state}_{row + 1}"
        dataset = result.data[label]
        plot_concentrations(dataset, axes[row, 0], center_λ=700, linlog=True,
                            linthresh=100, cycler=colors)
        plot_sas(dataset, axes[row, 1], cycler=colors)
        plot_das(dataset, axes[row, 2], cycler=colors)
        plot_norm_das(dataset, axes[row, 3], cycler=colors)
        axes[row, 0].set_title(label, loc="left", fontweight="bold")
        for column, ax in enumerate(axes[row]):
            ax.set_ylabel("")
            ax.tick_params(axis="y", labelleft=False)
            ax.set_xlabel("Time (ps)" if column == 0 else "Wavelength (nm)")
            if row < 3:
                ax.set_xlabel("")
            if row > 0 and column > 0:
                ax.set_title("")
            ax.text(-0.05, 1.05, chr(65 + row * 4 + column), transform=ax.transAxes)
    fig.savefig(plot_root / f"state{state}-concentrations-sas-das.png", dpi=120)
    fig.savefig(plot_root / f"state{state}-concentrations-sas-das.svg")
    plt.show()
'''


def prepare(output: Path) -> None:
    root = Path("temp/case-studies/TestCaseInitConc").resolve()
    reference, staging = root / "reference", root / "staging"
    original = reference / "20260905target_State1_2guide_8comp4test.ipynb"
    name = original.stem + "_validation.ipynb"
    source = nbformat.read(original, as_version=4)
    # Retain data setup, model/parameter loading, first fit, guide fits and traces.
    selected = [i for i in range(22) if i not in (12, 16)]
    notebook = nbformat.v4.new_notebook(cells=[copy.deepcopy(source.cells[i]) for i in selected])
    for cell in notebook.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
            cell.source = cell.source.replace(",x_scale='jac'", "")
            cell.source = cell.source.replace("from glotaran.project import Scheme", "from glotaran.project.scheme import Scheme")
    notebook.cells.insert(0, nbformat.v4.new_markdown_cell(
        "# Portable TestCaseInitConc target analysis\n\n"
        "Derived from the supplied notebook with user authorization. Uses the supported "
        "optimizer defaults (development-only x_scale removed), unchanged initialization "
        "and three-evaluation budget. Retains guide and trace plots; reconstructs the "
        "concentration/SAS/DAS/normalized-DAS rows using public extras functions, selecting "
        "700 nm for dispersed concentrations. Optional private helpers, kinetic diagrams "
        "and the trailing older analysis are omitted. Native results are captured by the "
        "validation runner. This short fit is not a convergence claim."
    ))
    notebook.cells.append(nbformat.v4.new_code_cell(PLOTS))
    nbformat.write(notebook, reference / name)
    nbformat.write(notebook, staging / name)
    # The user's visualizer checkout uses Python 3.12 f-string syntax; reference
    # Python is 3.10. Vendor a pinned, unmodified plotting-only dependency copy.
    extras_revision = "dcbe4baad5949768b65bf602d58018b5fe309f0a"
    archive = subprocess.check_output([
        "git", "-C", "temp/pyglotaran-main-dev/pyglotaran-extras", "archive",
        "--format=zip", extras_revision, "pyglotaran_extras",
    ])
    dependency_root = reference / "_plotting_dependencies"
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        bundle.extractall(dependency_root)
    reference_notebook = nbformat.read(reference / name, as_version=4)
    reference_notebook.cells.insert(1, nbformat.v4.new_code_cell(
        "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path('_plotting_dependencies').resolve()))"
    ))
    nbformat.write(reference_notebook, reference / name)
    model = next((reference / "models").glob("*.yml"))
    parameters = next((reference / "models").glob("*.csv"))
    # Use explicit matching copies, preserving every original staging input.
    parameter_copy = parameters.with_name(parameters.stem + "_validation.csv")
    for side in (reference, staging):
        (side / "models" / parameter_copy.name).write_bytes(parameters.read_bytes())
        path = side / name
        current = nbformat.read(path, as_version=4)
        for cell in current.cells:
            cell.source = cell.source.replace(parameters.name, parameter_copy.name)
        nbformat.write(current, path)
    document = yaml.safe_load(model.read_text())
    staging_model = staging / "models" / (model.stem + "_validation.yml")
    staging_model.write_bytes(model.read_bytes())
    staged_notebook = nbformat.read(staging / name, as_version=4)
    for cell in staged_notebook.cells:
        cell.source = cell.source.replace(model.name, staging_model.name)
    nbformat.write(staged_notebook, staging / name)
    converted, mapping = convert_model(document, staging_model, clp_link_tolerance=0.5)
    empty_groups = [key for key, value in converted["experiments"].items() if not value["datasets"]]
    converted["experiments"] = {key: value for key, value in converted["experiments"].items() if value["datasets"]}
    scheme = staging_model.with_name(staging_model.stem + "_v08.yml")
    scheme.write_text(yaml.safe_dump(converted, sort_keys=False), encoding="utf-8")
    migrated = migrate_notebook(staging / name, {staging_model: document})
    # Schema discovery follows the loaded scheme name; retain explicit linkage.
    current = nbformat.read(migrated, as_version=4)
    for cell in current.cells:
        if cell.cell_type == "code":
            cell.source = cell.source.replace("scheme_parameters = parameters", "model_parameters = parameters\nscheme_parameters = parameters")
            cell.source = cell.source.replace("print(model.validate(parameters=parameters))", "print('Scheme loaded; parameter validation follows in the dry run.')")
    nbformat.write(current, migrated)
    record = {"slug": "TestCaseInitConc", "source": str(original), "source_sha256": sha256(original),
              "selected_source_cells": selected, "omitted_source_cells": [i for i in range(len(source.cells)) if i not in selected],
              "models": [{"source": str(model), "destination": str(scheme), "destination_sha256": sha256(scheme), **mapping}],
              "notebooks": [{"source": str(reference / name), "destination": str(migrated), "destination_sha256": sha256(migrated)}],
              "parameter_sha256": sha256(parameter_copy), "clp_link_tolerance": 0.5,
              "omitted_empty_groups": empty_groups, "reference_plotting_extras_revision": extras_revision,
              "adjustments": ["Removed unsupported x_scale='jac'; both branches use public optimizer defaults.",
                              "Copied user-corrected reference parameters without altering values or expressions.",
                              "Replaced private plotting with public extras panels; omitted optional diagrams and trailing analysis."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"version": 1, "repositories": [record]}, indent=2), encoding="utf-8")
    output.with_suffix(".md").write_text("# TestCaseInitConc migration\n\n" + "\n".join("- " + line for line in record["adjustments"]) + "\n\nCLP link tolerance 0.5 and three-evaluation budget preserved. Full model mapping and hashes are in migration-log.json.\n", encoding="utf-8")
    print(migrated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    prepare(parser.parse_args().output)
