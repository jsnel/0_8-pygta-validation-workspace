"""Standalone diagnostic for this scenario, not a production optimizer.

Run separately with each checkout's Python. Optional runtime imports and
monkeypatches affect this process only. Output must be a fresh directory.
The two dataset shapes and linked residual ordering are scenario-specific.
See issues/spectral-guidance-current-tree.md for experiments and limitations.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import hashlib
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--branch', choices=['main', 'staging'], required=True)
parser.add_argument('--numeric-site', type=Path)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--diff-step', type=float)
parser.add_argument('--canonical-compartments', action='store_true')
parser.add_argument('--nnls-v14', action='store_true')
parser.add_argument('--pinned-vary', action='store_true')
parser.add_argument('--max-nfev', type=int, default=100)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
(out / 'probe.py').write_bytes(Path(__file__).read_bytes())
if args.numeric_site:
    sys.path.insert(0, str(args.numeric_site.resolve()))
import numpy as np
import scipy
from scipy.optimize import least_squares
from scipy.optimize._numdiff import approx_derivative
import numba
if args.numeric_site:
    sys.path.pop(0)

import scipy.optimize
native_nnls = scipy.optimize.nnls
if args.nnls_v14:
    import importlib.util
    spec = importlib.util.spec_from_file_location('probe_nnls14', root/'temp/pyglotaran-staging-dev/.venv/Lib/site-packages/scipy/optimize/_nnls.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    native_nnls = module.nnls
first_matrix = None
def capture_nnls(matrix, data, *a, **kw):
    global first_matrix
    if first_matrix is None:
        first_matrix = matrix.copy()
    return native_nnls(matrix, data, *a, **kw)
scipy.optimize.nnls = capture_nnls

from glotaran.io import load_dataset, load_parameters
os.chdir(root / f'temp/pyglotaran-{args.branch}-dev/pyglotaran-examples/pyglotaran_examples/ex_spectral_guidance')
data = {label: load_dataset('data/' + file) for label, file in [
    ('dataset1', 'Npq2_220219_800target3fasea.ascii'),
    ('dataset2', 'trNpq2_220219_800target3fase10SAS5.ascii'),
]}
p = load_parameters('models/parameters_guidance.yml')
if args.pinned_vary:
    for label in ('rates.k5', 'rates.k6', 'scale.2'):
        p.get(label).vary = True
if args.branch == 'main':
    from glotaran.io import load_model
    from glotaran.project.scheme import Scheme
    from glotaran.optimization.optimizer import Optimizer
    engine = Optimizer(Scheme(load_model('models/model_guidance.yml'), p, data), verbose=False)
    labels, x, lower, upper = engine._parameters.get_label_value_and_bounds_arrays(exclude_non_vary=True)
    engine._free_parameter_labels = labels
else:
    from glotaran.io import load_scheme
    from glotaran.optimization.optimization import Optimization
    if args.canonical_compartments:
        from glotaran.builtin.elements.kinetic.kinetic import Kinetic
        original_compartments = Kinetic.compartments.fget
        Kinetic.compartments = property(lambda self: sorted(original_compartments(self)))
    scheme = load_scheme('models/scheme_guidance.yml')
    scheme._load_data(data)
    engine = Optimization(models=list(scheme.experiments.values()), parameters=p, library=scheme.library, verbose=False)
    labels, x, lower, upper = engine._parameters.get_label_value_and_bounds_arrays(exclude_non_vary=True)

calls = []
def objective(values):
    global first_matrix
    first_matrix = None
    result = engine.objective_function(values)
    calls.append((values.copy(), result.copy(), first_matrix))
    return result

initial = objective(x)
jac = approx_derivative(objective, x, method='2-point', rel_step=args.diff_step)
fit = least_squares(objective, x, bounds=(lower, upper), max_nfev=args.max_nfev,
                    diff_step=args.diff_step, ftol=1e-8, xtol=1e-8, gtol=1e-8)
# Mirror native result construction: v0.7 restores the accepted vector;
# current v0.8 retains the parameter state of the last objective evaluation.
if args.branch == 'main':
    packaged_residual = objective(fit.x)
else:
    packaged_residual = np.concatenate([o.calculate() for o in engine._objectives])
_, packaged_x, _, _ = engine._parameters.get_label_value_and_bounds_arrays(exclude_non_vary=True)
observations = np.concatenate([
    (d.data if hasattr(d, 'data_vars') else d).values.T for d in data.values()
], axis=1)
packaged_fits = observations - packaged_residual[:-1].reshape(observations.shape)
np.savez(out/'arrays.npz', initial=initial, jac=jac, x=fit.x, residual=fit.fun,
         packaged_residual=packaged_residual, packaged_x=packaged_x,
         fitted_dataset1=packaged_fits[:, :31].T, fitted_dataset2=packaged_fits[:, 31:].T,
         call_x=np.array([c[0] for c in calls]), call_residual=np.array([c[1] for c in calls]))
np.save(out/'call_matrix.npy', np.array([c[2] for c in calls]))
report = dict(branch=args.branch, numpy=np.__version__, scipy=scipy.__version__,
              numba=numba.__version__,
              canonical_compartments=args.canonical_compartments, nnls_v14=args.nnls_v14,
              pinned_vary=args.pinned_vary, max_nfev=args.max_nfev,
              numpy_path=np.__file__, scipy_path=scipy.__file__, labels=labels,
              initial=x.tolist(), final=fit.x.tolist(), nfev=fit.nfev, cost=fit.cost,
              optimality=fit.optimality, termination=fit.message, diff_step=args.diff_step)
report['packaged_x'] = packaged_x.tolist()
report['source_revisions'] = {
    name: subprocess.check_output(['git', '-C', str(root/f'temp/pyglotaran-{args.branch}-dev'/name), 'rev-parse', 'HEAD'], text=True).strip()
    for name in ('pyglotaran', 'pyglotaran-examples')
}
report['hashes'] = {
    str(path): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in [Path(__file__).resolve(), Path('models/parameters_guidance.yml'),
                 Path('models/model_guidance.yml' if args.branch == 'main' else 'models/scheme_guidance.yml'),
                 *Path('data').glob('*.ascii')]
}
(out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
