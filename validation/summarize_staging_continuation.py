"""Summarize timed (non-warmup) samples from continuation probe directories."""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    groups = defaultdict(list)
    for file in args.root.rglob('measurements.json'):
        parts = file.parent.name.rsplit('-', 2)
        if len(parts) != 3 or not parts[2].isdigit():
            continue
        case, branch, repeat = parts
        if branch not in ('baseline', 'optimized'):
            continue
        data = json.loads(file.read_text())
        assert data.get('completed'), str(file)
        for call in data['calls']:
            groups[(str(file.parent.parent.relative_to(args.root)), case, branch, call['invocation'])].append(call)
    report = []
    for key, calls in sorted(groups.items()):
        row = dict(group=key, samples=len(calls), dry_run=calls[0]['dry_run'])
        for field in ('total_s', 'reconstruction_s', 'objective_s', 'initialization_s', 'peak_rss_bytes'):
            values = [c.get(field, 0) for c in calls]
            row[field] = dict(mean=statistics.mean(values), median=statistics.median(values),
                              stdev=statistics.stdev(values) if len(values)>1 else None,
                              min=min(values), max=max(values))
        for field in ('number_of_function_evaluations', 'number_of_jacobian_evaluations',
                      'number_of_parameters', 'free_parameter_labels', 'termination_reason', 'scipy_success',
                      'nonzero_accepted_steps'):
            row[field] = [c.get(field) for c in calls]
        report.append(row)
    args.output.write_text(json.dumps(report, indent=2))
    for r in report:
        print('/'.join(map(str,r['group'])), r['samples'],
              f"mean={r['total_s']['mean']:.3f}s median={r['total_s']['median']:.3f}s",
              'nfev=',r['number_of_function_evaluations'])


if __name__ == '__main__':
    main()
