"""Archive actual guest numeric snapshots for host analysis; not fuel claims."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import optimize_folder
from tools.bot_optimizer.runtime import check_logs, executable, replay_logs, run_command


def grid(values):
    values = list(values)
    if not values:
        return dict(count=0)
    import math
    if any(type(value) not in (float, int) or not math.isfinite(value) or value < 0 for value in values):
        return dict(count=len(values), finite_nonnegative=False)
    ratios = [value.as_integer_ratio() for value in values]
    scale = max(denominator.bit_length()-1 for _, denominator in ratios)
    maximum = max(numerator << (scale-(denominator.bit_length()-1)) for numerator, denominator in ratios)
    return dict(count=len(values), finite_nonnegative=True, denominator_bits=scale,
                max_scaled_bits=maximum.bit_length(), exact_16_term_bound=16*maximum < 2**53,
                distinct_values=len(set(values)), minimum=min(values), maximum=max(values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision,corners,lanes')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be fresh')
    folder = args.output/'optimized'
    report = optimize_folder(args.bot, folder)
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    binding = consumer.body[0]
    assert isinstance(binding, ast.Assign) and isinstance(binding.targets[0], ast.Tuple)
    data = binding.targets[0].elts[0].id
    consumer.body[1:1] = ast.parse(f"print('BCOPT_SNAPSHOT ' + repr({data}), flush=True)").body
    path.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n')
    results = dict(status='running', fuel_measurement=False, input_sha256=report['input_sha256'],
                   snapshots=[], compiler_pass_counts=report['pass_counts'])
    for index, game_map in enumerate(args.maps.split(',')):
        output = args.output/f'run-{index}-{game_map}'
        run_command([executable(), 'run', str(folder.resolve()), str(folder.resolve()), '--release',
                     '--rounds', '1', '--map', game_map, '--fuel', '6000000000', '--out-dir', str(output.resolve())], timeout=300)
        replay, = output.glob('*.repl26a')
        logs = replay_logs(replay)
        check_logs(logs)
        for side in ('a', 'b'):
            rows = [line.removeprefix('BCOPT_SNAPSHOT ') for line in logs[f'team-{side}.stdout'].splitlines()
                    if line.startswith('BCOPT_SNAPSHOT ')]
            assert rows
            for ordinal, row in enumerate(rows):
                snapshot = ast.literal_eval(row)
                filename = f'{game_map}-{side}-{ordinal}.txt'
                (args.output/filename).write_text(row+'\n')
                pair = snapshot[9]
                stats = dict(map=game_map, side=side, file=filename,
                    sha256=hashlib.sha256(row.encode()).hexdigest(), camps=len(snapshot[0]), altars=len(snapshot[2]),
                    risk_pairs=grid(value for values in pair for value in values) if pair is not None else None,
                    camp_risk=grid(snapshot[10]) if snapshot[10] is not None else None,
                    raw_risk=grid(snapshot[5][0]) if snapshot[5] is not None else None)
                results['snapshots'].append(stats)
                print(json.dumps(stats), flush=True)
        (args.output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    results['status'] = 'complete'
    (args.output/'results.json').write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    main()
