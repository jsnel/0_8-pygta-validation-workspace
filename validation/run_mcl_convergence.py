"""Capture an isolated MCL first fit with an explicitly selected Python environment."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--branch', choices=['reference', 'staging'], required=True)
    parser.add_argument('--max-nfev', type=int, default=200)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    work = output / 'worktree'
    work.mkdir()
    for name in ['models', 'data']:
        shutil.copytree(source / name, work / name)
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:
        os.environ[key] = '1'
    import glotaran
    import numpy
    import scipy
    from glotaran.io import load_parameters, save_result, SAVING_OPTIONS_DEFAULT
    def hashes(root):
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}
    core = Path(glotaran.__file__).resolve().parents[1]
    def git(*cmd):
        return subprocess.run(['git','-C',str(core),*cmd],capture_output=True,text=True).stdout.strip()
    manifest = {'started_at': datetime.now(timezone.utc).isoformat(), 'command':sys.argv,
                'python':sys.executable,'glotaran':glotaran.__file__,'core_revision':git('rev-parse','HEAD'),
                'core_status':git('status','--short'),'numpy':numpy.__version__,'scipy':scipy.__version__,
                'source':str(source),'max_nfev':args.max_nfev,'input_hashes':hashes(work)}
    os.chdir(work)
    with (output/'optimizer.log').open('w',encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        if args.branch == 'reference':
            from glotaran.project import Scheme
            from glotaran.optimization.optimize import optimize
            scheme = Scheme(model='models/20241110streak_target_77K_supercomplex.yml',
                parameters='models/20241120streak_target_77K_supercomplex_first_fit.csv',
                maximum_number_function_evaluations=args.max_nfev,clp_link_tolerance=0.1,
                data={'super1ns':'data/supercomplex_targeta.ascii','super2ns':'data/supercomplex_targetb.ascii'})
            result = optimize(scheme)
        else:
            from glotaran.io import load_scheme
            scheme=load_scheme('models/20241110streak_target_77K_supercomplex_v08.yml')
            result=scheme.optimize(parameters=load_parameters('models/20241120streak_target_77K_supercomplex.csv'),
                datasets={'super1ns':'data/supercomplex_targeta.ascii','super2ns':'data/supercomplex_targetb.ascii'},
                maximum_number_function_evaluations=args.max_nfev,raise_exception=True)
        if isinstance(SAVING_OPTIONS_DEFAULT,dict):
            options=dict(SAVING_OPTIONS_DEFAULT);options['data_filter']=set()
        else:
            from glotaran.io.interface import SavingOptions
            options=SavingOptions(data_filter=None,report=False)
        save_result(result=result,result_path=str(output/'result'/'result.yaml'),saving_options=options)
    manifest.update(finished_at=datetime.now(timezone.utc).isoformat(),result_hashes=hashes(output/'result'),status='PASSED')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(args.branch,output,'PASSED')

if __name__ == '__main__':
    main()
