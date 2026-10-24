"""Uninstrumented baseline/generated smoke comparisons at normal engine fuel.

This records complete engine-replay equality, not just printed witnesses. A
different trajectory under normal fuel is reported, not called a semantic bug:
fuel-aware bots may intentionally do more work after optimization.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import Options, optimize_folder
from tools.bot_optimizer.model import PASS_DESCRIPTIONS
from tools.bot_optimizer.runtime import check_logs, executable, replay_logs, run_command


def observe_local(folder, specification):
    """Report an existing work counter at function exit, with no per-loop probe."""
    module, qualified, local = specification.split(':')
    if not all(part.isidentifier() for part in [*module.split('.'), *qualified.split('.'), local]):
        raise ValueError('local observation must be module:Function.or.method:local')
    source = folder / 'src' if (folder / 'src/main.py').exists() else folder
    path = source.joinpath(*module.split('.')).with_suffix('.py')
    tree = ast.parse(path.read_text())
    node = tree
    for name in qualified.split('.'):
        node, = [child for child in node.body if isinstance(child, (ast.FunctionDef, ast.ClassDef))
                 and child.name == name]
    if not isinstance(node, ast.FunctionDef):
        raise ValueError('local observation target must be a function')
    targets = [node]
    manifest = folder/'optimizer-report.json'
    if manifest.exists():
        report = json.loads(manifest.read_text())
        for info in report['files'].values():
            for change in info['changes']:
                if change['pass_name'] != 'numeric-consumer-regions' or not change['before'].startswith(f'{module}.{qualified}:'):
                    continue
                names = [word for word in change['after'].split() if word.startswith('_bcopt_region_consumer_')]
                for name in names:
                    clone, = [child for child in tree.body if isinstance(child, ast.FunctionDef) and child.name == name]
                    targets.append(clone)
    for target in targets:
        body, doc = target.body, []
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            doc, body = body[:1], body[1:]
        finish = ast.parse(f"print('BCOPT_WORK ' + repr(({specification!r}, {local})), flush=True)").body
        target.body = [*doc, ast.Try(body=body, handlers=[], orelse=[], finalbody=finish)]
    text = ast.unparse(ast.fix_missing_locations(tree)) + '\n'
    compile(text, str(path), 'exec')
    path.write_text(text)
    return [target.name for target in targets]


def work_counts(replay):
    logs = replay_logs(replay)
    return {side: [ast.literal_eval(line.removeprefix('BCOPT_WORK '))
                   for line in logs[f'team-{side}.stdout'].splitlines()
                   if line.startswith('BCOPT_WORK ')] for side in ('a', 'b')}


def trajectory(old, new):
    with ZipFile(old) as before, ZipFile(new) as after:
        a, b = before.read('replay.repl26a'), after.read('replay.repl26a')
        return {'engine_replay_equal': a == b,
                'baseline_replay_sha256': hashlib.sha256(a).hexdigest(),
                'optimized_replay_sha256': hashlib.sha256(b).hexdigest(),
                'full_stdout_equal': all(before.read(f'team-{s}.stdout') == after.read(f'team-{s}.stdout')
                                         for s in ('a', 'b'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision,corners,lanes')
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--fuel', type=int, help='Omit for normal engine default')
    parser.add_argument('--observe-local', help='module:Function.or.method:counter (exit-only instrumentation)')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('output must be a new directory')
    maps = [name.strip() for name in args.maps.split(',') if name.strip()]
    if not maps or args.rounds < 1 or args.fuel is not None and args.fuel < 1:
        parser.error('positive rounds and at least one map required')
    cli = executable()
    baseline, optimized = output/'baseline', output/'optimized'
    old = optimize_folder(args.bot, baseline, Options(disabled=frozenset(PASS_DESCRIPTIONS)))
    new = optimize_folder(args.bot, optimized)
    if old['input_sha256'] != new['input_sha256']:
        raise ValueError('input changed between variants')
    observation_targets = {}
    if args.observe_local:
        for folder in (baseline, optimized):
            observation_targets[folder.name] = observe_local(folder, args.observe_local)
    report = {'status': 'running', 'instrumented': bool(args.observe_local),
              'fuel': args.fuel or 'normal engine default', 'observe_local': args.observe_local,
              'input_sha256': old['input_sha256'], 'pass_counts': new['pass_counts'],
              'rounds': args.rounds, 'comparisons': [], 'observation_targets': observation_targets}
    for index, game_map in enumerate(maps):
        paths = []
        for name, bot in (('baseline', baseline), ('optimized', optimized)):
            dest = output/f'run-0-map-{index}-{name}'
            run_command([cli, 'run', str(bot), str(bot), '--release', '--rounds', str(args.rounds),
                         '--map', game_map, '--out-dir', str(dest),
                         *(['--fuel', str(args.fuel)] if args.fuel else [])], timeout=300)
            replay, = dest.glob('*.repl26a')
            check_logs(replay_logs(replay))
            paths.append(replay)
        result = {'map': game_map, **trajectory(*paths)}
        if args.observe_local:
            counts = [work_counts(path) for path in paths]
            if any(not counts[v][s] for v in (0, 1) for s in ('a', 'b')):
                raise ValueError('Missing work-count observations')
            result.update(baseline_work=counts[0], optimized_work=counts[1], work_counts_equal=counts[0] == counts[1])
        report['comparisons'].append(result)
        print(game_map, result)
        (output/'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (output/'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
