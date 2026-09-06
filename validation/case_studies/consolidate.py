"""Replace embedded compatibility helpers without remigrating notebook analyses.

Run with ``python -m validation.case_studies.consolidate temp/case-studies``.
Historical validation/runs evidence is deliberately outside the default scope.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from validation.case_studies.migrate import HELPERS


HELPER_NAMES = {
    "_CaseStudyDataStore", "_case_study_report_real_fit", "_case_study_simulate",
    "_case_study_convert", "_case_study_matrix_markdown",
}


def consolidate(path: Path) -> bool:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        definitions = [
            node for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in HELPER_NAMES
        ]
        if not definitions:
            continue
        lines = source.splitlines(keepends=True)
        for node in reversed(definitions):
            del lines[node.lineno - 1:node.end_lineno]
        cell["source"] = (HELPERS + "\n" + "".join(lines)).splitlines(keepends=True)
        changed = True
    if changed:
        # Outputs are historical evidence, not evidence of executing the new source.
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                cell["outputs"] = []
                cell["execution_count"] = None
        path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    for path in sorted(args.root.rglob("*_v08.ipynb")):
        if consolidate(path):
            print(path)


if __name__ == "__main__":
    main()
