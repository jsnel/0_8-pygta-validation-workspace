"""Run paired fresh-process continuation benchmarks in alternating order."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=['pfid', 'two', 'spectral'], action='append', required=True)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--skip-baseline-warmup', action='store_true')
    parser.add_argument('--initial-snapshot', type=Path)
    parser.add_argument('--perturb', type=float, default=1.0)
    parser.add_argument('--max-nfev', type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cores = {'baseline': root / 'validation/runs/runtime-continuation-20260906/baseline-core',
             'optimized': root / 'temp/pyglotaran-staging-dev/pyglotaran'}
    examples = root / 'temp/pyglotaran-staging-dev/pyglotaran-examples/pyglotaran_examples'
    notebooks = {'pfid': root / 'temp/case-studies/pfid/staging/20260830_20240827target_4pfid_lyco_all-plot-config_ksv_v08.ipynb',
                 'two': examples / 'ex_two_datasets/ex_two_datasets.ipynb',
                 'spectral': examples / 'ex_spectral_guidance/ex_spectral_guidance.ipynb'}
    jobs = []
    for case in args.case:
        for repeat in range(args.repetitions + 1):
            for branch in (['baseline', 'optimized'] if repeat % 2 == 0 else ['optimized', 'baseline']):
                if repeat == 0 and branch == 'baseline' and args.skip_baseline_warmup:
                    continue
                name = f'{case}-{branch}-' + ('warmup' if repeat == 0 else str(repeat))
                command = [sys.executable, str(root / 'validation/benchmark_staging_continuation.py'),
                           '--notebook', str(notebooks[case]), '--core', str(cores[branch]),
                           '--output', str(output / name), '--perturb', str(args.perturb)]
                if repeat == 0:
                    command += ['--save-results']
                if args.initial_snapshot:
                    command += ['--initial-snapshot', str(args.initial_snapshot.resolve())]
                if args.max_nfev:
                    command += ['--max-nfev', str(args.max_nfev)]
                print(f'START {name}', flush=True)
                with (output / f'{name}.log').open('w', encoding='utf-8') as log:
                    result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
                jobs.append(dict(name=name, returncode=result.returncode, command=command))
                (output / 'jobs.json').write_text(json.dumps(jobs, indent=2))
                print(f'END {name}: {result.returncode}', flush=True)
                if result.returncode:
                    return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
