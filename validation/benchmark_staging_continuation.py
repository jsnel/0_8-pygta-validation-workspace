"""Fresh-process staging probes; timing excludes notebook work and snapshot serialization.

Invoke once per warmup/repetition with an unused output directory. --core selects
an isolated source snapshot without changing the editable installation. Production
cells run unchanged through the final optimizer cell; later plotting is excluded.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import inspect
import json
import os
import pickle
import platform
import sys
import threading
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notebook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--perturb', type=float, default=1.0)
    parser.add_argument('--initial-snapshot', type=Path)
    parser.add_argument('--max-nfev', type=int)
    parser.add_argument('--save-results', action='store_true')
    args = parser.parse_args()
    source, output, core = (p.resolve() for p in (args.notebook, args.output, args.core))
    initial_snapshot = args.initial_snapshot.resolve() if args.initial_snapshot else None
    output.mkdir(parents=True, exist_ok=False)
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMBA_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ['MPLBACKEND'] = 'Agg'
    home = output / 'home'
    home.mkdir()
    os.environ.update(HOME=str(home), USERPROFILE=str(home),
                      HOMEDRIVE=home.drive, HOMEPATH=str(home)[len(home.drive):])
    sys.path.insert(0, str(core))
    import numpy as np
    import scipy
    import numba
    import psutil
    from IPython.core.interactiveshell import InteractiveShell
    from glotaran.project.scheme import Scheme
    from glotaran.optimization.objective import OptimizationObjective
    from glotaran.optimization.optimization import Optimization
    import glotaran.optimization.optimization as optimization_module

    report = dict(notebook=str(source), notebook_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  core=str(core), python=sys.version, executable=sys.executable,
                  packages=dict(numpy=np.__version__, scipy=scipy.__version__, numba=numba.__version__),
                  cpu=platform.processor(), threads=1, perturb=args.perturb, calls=[],
                  source_hashes={str(p.relative_to(core)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted((core / 'glotaran').rglob('*.py'))})
    active = None
    least_squares = optimization_module.least_squares
    @functools.wraps(least_squares)
    def record_solver(*a, **kw):
        result = least_squares(*a, **kw)
        active['scipy_success'] = bool(result.success)
        active['scipy_status'] = int(result.status)
        return result
    optimization_module.least_squares = record_solver
    for cls, method, field in ((OptimizationObjective, 'get_result', 'reconstruction_s'),
                               (OptimizationObjective, 'calculate', 'objective_s'),
                               (Optimization, '__init__', 'initialization_s')):
        original = getattr(cls, method)
        def wrap(original=original, field=field):
            @functools.wraps(original)
            def timed(*a, **kw):
                start = time.perf_counter()
                try:
                    return original(*a, **kw)
                finally:
                    if active is not None:
                        active[field] = active.get(field, 0) + time.perf_counter() - start
                        if field == 'objective_s':
                            active['objective_calls'] = active.get('objective_calls', 0) + 1
            return timed
        setattr(cls, method, wrap())

    original_optimize = Scheme.optimize
    signature = inspect.signature(original_optimize)
    @functools.wraps(original_optimize)
    def optimize(*a, **kw):
        nonlocal active
        bound = signature.bind(*a, **kw)
        bound.apply_defaults()
        parameters = bound.arguments['parameters']
        if not bound.arguments['dry_run'] and initial_snapshot is not None:
            from glotaran.parameter import Parameters
            from compare_staging_snapshots import read_snapshot
            parameters = Parameters.from_dataframe(read_snapshot(initial_snapshot)['parameters'])
            bound.arguments['parameters'] = parameters
        if not bound.arguments['dry_run'] and args.max_nfev is not None:
            bound.arguments['maximum_number_function_evaluations'] = args.max_nfev
        if not bound.arguments['dry_run'] and args.perturb != 1:
            parameters = parameters.copy()
            for p in parameters.all():
                if p.vary and p.expression is None:
                    p.value *= args.perturb
            bound.arguments['parameters'] = parameters
        active = dict(invocation=len(report['calls']) + 1, dry_run=bound.arguments['dry_run'],
                      budget=bound.arguments['maximum_number_function_evaluations'],
                      method=bound.arguments['optimization_method'],
                      tolerances={k: bound.arguments[k] for k in ('ftol', 'gtol', 'xtol')},
                      initial_parameters=[(p.label, p.value, p.vary, p.expression) for p in parameters.all()])
        done = threading.Event()
        process = psutil.Process()
        peak = [process.memory_info().rss]
        def sample():
            while not done.wait(.02):
                peak[0] = max(peak[0], process.memory_info().rss)
        thread = threading.Thread(target=sample, daemon=True)
        thread.start()
        start = time.perf_counter()
        try:
            result = original_optimize(*bound.args, **bound.kwargs)
        finally:
            duration = time.perf_counter() - start
            done.set()
            thread.join()
        active.update(total_s=duration, peak_rss_bytes=peak[0])
        info = result.optimization_info
        history = info.optimization_history.data
        active['accepted_iterations'] = int(history.index.max()) if len(history) else None
        active['nonzero_accepted_steps'] = int(((history.step_norm > 0) &
                                              (history.cost_reduction > 0)).sum()) if len(history) else None
        for k in ('success', 'termination_reason', 'number_of_function_evaluations',
                  'number_of_jacobian_evaluations', 'number_of_parameters', 'free_parameter_labels'):
            active[k] = getattr(info, k, None)
        active['datasets'] = {k: dict(shape=list(v.input_data.shape), dtype=str(v.input_data.dtype),
                                    dims=list(v.input_data.dims)) for k,v in result.optimization_results.items()}
        report['calls'].append(active)
        active = None
        (output / 'measurements.json').write_text(json.dumps(report, indent=2, default=str))
        if args.save_results:
            with (output / f'result-{len(report["calls"])}.pkl').open('wb') as stream:
                pickle.dump(dict(results={k: v.model_dump() for k, v in result.optimization_results.items()},
                                 parameters=result.optimized_parameters.to_dataframe(),
                                 info=info.model_dump()), stream, protocol=5)
        return result
    Scheme.optimize = optimize
    notebook = json.loads(source.read_text(encoding='utf-8'))
    cells = notebook['cells']
    last = max(i for i,c in enumerate(cells) if c['cell_type']=='code' and '.optimize(' in ''.join(c['source']))
    os.chdir(source.parent)
    shell = InteractiveShell.instance()
    for i,c in enumerate(cells[:last+1]):
        if c['cell_type'] == 'code':
            print(f'Executing cell {i}', flush=True)
            execution = shell.run_cell(''.join(c['source']), store_history=False)
            execution.raise_error()
    report['completed'] = True
    (output / 'measurements.json').write_text(json.dumps(report, indent=2, default=str))


if __name__ == '__main__':
    main()
