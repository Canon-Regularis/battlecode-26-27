"""Archive completed fuel reports and their generated-source fingerprints.

Usage: uv run python benchmarks/bot-optimizer/collect.py --output <new.json>
       label=path/to/results.json [label=path/to/results.json ...]
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def collect(inputs):
    runs = {}
    for argument in inputs:
        label, separator, filename = argument.partition('=')
        if not separator or not label or label in runs:
            raise ValueError('Reports require unique label=path arguments')
        path = Path(filename)
        report = json.loads(path.read_text())
        if 'datasets' in report:
            datasets = report['datasets']
            if {d['map'] for d in datasets} != {'collision', 'corners'} or len(datasets) != 2:
                raise ValueError(f'Incomplete maps: {path}')
            inventory = None
            for dataset in datasets:
                if len(dataset['metadata']) != 2 or not dataset['pairs']:
                    raise ValueError(f'Incomplete teams: {path}')
                if inventory is not None and set(dataset['pairs']) != inventory:
                    raise ValueError(f'Inconsistent cases: {path}')
                inventory = set(dataset['pairs'])
                for records in dataset['pairs'].values():
                    if len(records) != 2 or any(
                        r['baseline'] <= 0 or r['optimized'] <= 0
                        or len(r['baseline_samples']) != 5 or len(r['optimized_samples']) != 5
                        for r in records
                    ):
                        raise ValueError(f'Incomplete measurements: {path}')
            # Older benchmark driver has no status field; completeness above is
            # checked explicitly rather than merely trusting a report exists.
            if report.get('status', 'complete') != 'complete':
                raise ValueError(f'Unfinished report: {path}')
        elif report.get('status') != 'complete':
            raise ValueError(f'Unfinished comparison: {path}')
        if 'target' in report and 'comparisons' in report:
            maps = list(dict.fromkeys(row['map'] for row in report['comparisons']))
            checks = []
            for run in range(report['repeats']):
                for index, game_map in enumerate(maps):
                    files = [list((path.parent / f'run-{run}-map-{index}-{variant}').glob('*.repl26a'))
                             for variant in ('baseline', 'optimized')]
                    if any(len(paths) != 1 for paths in files):
                        checks.append({'run': run, 'map': game_map, 'status': 'replay not available'})
                        continue
                    with ZipFile(files[0][0]) as before, ZipFile(files[1][0]) as after:
                        a, b = before.read('replay.repl26a'), after.read('replay.repl26a')
                        stdout_equal = []
                        for side in ('a', 'b'):
                            def plain(archive):
                                return [line for line in archive.read(f'team-{side}.stdout').decode().splitlines()
                                        if line.strip() and not line.startswith('BCOPT_MEASURE ')]
                            stdout_equal.append(plain(before) == plain(after))
                        checks.append({'run': run, 'map': game_map, 'engine_replay_equal': a == b,
                            'baseline_replay_sha256': hashlib.sha256(a).hexdigest(),
                            'optimized_replay_sha256': hashlib.sha256(b).hexdigest(),
                            'all_nonmeasurement_stdout_equal': all(stdout_equal)})
            report['trajectory_checks'] = checks
        if 'compiler' in report:
            report['pass_counts'] = dict(Counter(c['pass_name'] for c in report['compiler']['changes']))
            del report['compiler']  # Full before/after AST remains in raw report.
        generated = {}
        for folder in ('bot/src', 'baseline/src', 'optimized/src'):
            for source in sorted((path.parent / folder).rglob('*.py')):
                generated[str(source.relative_to(path.parent))] = hashlib.sha256(source.read_bytes()).hexdigest()
        runs[label] = {'raw_report': str(path), 'raw_report_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'generated_source_sha256': generated, 'report': report}
    root = Path(__file__).resolve().parents[2]
    return {'status': 'complete', 'cambc': '3.0.4', 'runs': runs,
            'archive_time_optimizer_source_sha256': {
                str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted((root/'tools/bot_optimizer').glob('*.py'))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('reports', nargs='+')
    args = parser.parse_args()
    result = collect(args.reports)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
