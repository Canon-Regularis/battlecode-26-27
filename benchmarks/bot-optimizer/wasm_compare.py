"""Compare immutable prebuilt Wasm modules with existing target instrumentation.

The engine and its fuel accounting are unchanged. Module optimization is a
separate experiment from source transforms; matching reports alone do not prove
semantic equivalence or equal expansion counts.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.compare import observations
from tools.bot_optimizer.runtime import executable, run_command


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision,corners,lanes')
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args()
    if args.output.exists() or args.repeats < 1:
        parser.error('output must be new and repeats must be positive')
    modules = {'baseline': args.baseline.resolve(), 'candidate': args.candidate.resolve()}
    hashes = {name: fingerprint(path) for name, path in modules.items()}
    cli = executable()
    args.output.mkdir(parents=True)
    report = {'status': 'running', 'modules': {name: str(path) for name, path in modules.items()},
              'sha256': hashes, 'fuel_quantum_argument': 1_000_000_000,
              'rounds': 1, 'repeats': args.repeats, 'comparisons': [],
              'note': 'Prebuilt modules; unchanged engine. Requires separate work-count and semantic audits.'}
    for repeat in range(args.repeats):
        for game_map in args.maps.split(','):
            data = {}
            order = list(modules)
            if repeat % 2:
                order.reverse()
            for name in order:
                module = modules[name]
                assert fingerprint(module) == hashes[name]
                dest = args.output.resolve() / f'run-{repeat}-{game_map}-{name}'
                result = run_command([cli, 'run', str(module), str(module), '--release', '--rounds', '1',
                                      '--fuel', '1000000000', '--map', game_map, '--out-dir', str(dest)], timeout=300)
                (dest / 'cli.stdout').write_text(result.stdout)
                (dest / 'cli.stderr').write_text(result.stderr)
                replay, = dest.glob('*.repl26a')
                try:
                    if any(marker in result.stdout + result.stderr for marker in ('Guest trapped:', 'draft bot crashed:')):
                        raise ValueError('Engine reported a guest crash; see archived CLI logs')
                    data[name] = observations(replay, 'SQUAD_LOOPS_DATA ')
                except ValueError as error:
                    report.update(status='failed', error=str(error), failed_module=name, failed_map=game_map)
                    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
                    raise
                assert fingerprint(module) == hashes[name]
            for side in ('a', 'b'):
                old, new = data['baseline'][side], data['candidate'][side]
                assert old['outputs'] == new['outputs'], (game_map, side, 'reports differ')
                assert len(old['samples']) == len(new['samples'])
                savings = 100 * (1 - sum(new['samples']) / sum(old['samples']))
                report['comparisons'].append({'run': repeat, 'map': game_map, 'side': side,
                    'baseline_fuel': old['samples'], 'candidate_fuel': new['samples'],
                    'reduction_percent': savings, 'printed_outputs_equal': True})
                print(repeat, game_map, side, f'{savings:.4f}% lower fuel', flush=True)
            (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
