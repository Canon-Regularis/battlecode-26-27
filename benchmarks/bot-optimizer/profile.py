"""Aggregate guest-fuel profiling of selected source-defined functions.

Stages separate original/generated copies. Nested timings are inclusive and add
instrumentation overhead; use this to rank opportunities, not to claim savings.
"""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import Options, optimize_folder
from tools.bot_optimizer.model import PASS_DESCRIPTIONS
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.runtime import executable, run_command, replay_logs, check_logs


def instrument(folder, targets, root_target):
    helper = '_bcopt_fuel_profile'
    source = folder / 'src' if (folder / 'src/main.py').exists() else folder
    if (source / f'{helper}.py').exists():
        raise ValueError('profiling helper name already exists')
    (source / f'{helper}.py').write_text('''import cambc
totals = {}
def record(name, start):
    end = cambc.fuel_remaining()
    if end >= start:
        raise ValueError('profiling interval crossed a fuel boundary')
    calls, fuel = totals.get(name, (0, 0))
    totals[name] = calls + 1, fuel + start - end
def publish():
    print('BCOPT_PROFILE ' + repr(totals), flush=True)
''')
    modules = {}
    for target in dict.fromkeys([*targets, root_target]):
        module, _, qualified = target.partition(':')
        if not all(p.isidentifier() for p in [*module.split('.'), *qualified.split('.')]):
            raise ValueError(f'Invalid target: {target}')
        path = source.joinpath(*module.split('.')).with_suffix('.py')
        tree = modules.setdefault(path, ast.parse(path.read_text()))
        node = tree
        for name in qualified.split('.'):
            node, = [child for child in node.body if isinstance(child, (ast.FunctionDef, ast.ClassDef))
                     and child.name == name]
        if not isinstance(node, ast.FunctionDef) or any(isinstance(p, (ast.Yield, ast.YieldFrom, ast.Await))
                                                      for p in ast.walk(node)):
            raise ValueError('Cannot profile suspending functions')
        taken = used_names(tree)
        suffix = 0
        while f'_bcopt_profile_{suffix}' in taken or f'_bcopt_start_{suffix}' in taken:
            suffix += 1
        alias, start = f'_bcopt_profile_{suffix}', f'_bcopt_start_{suffix}'
        prefix = ast.parse(f'import {helper} as {alias}\n{start} = {alias}.cambc.fuel_remaining()').body
        finish = ast.parse(f'{alias}.record({target!r}, {start})').body
        if target == root_target:
            finish += ast.parse(f'{alias}.publish()').body
        doc = []
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            doc, body = body[:1], body[1:]
        node.body = [*doc, *prefix, ast.Try(body=body, handlers=[], orelse=[], finalbody=finish)]
    for path, tree in modules.items():
        text = ast.unparse(ast.fix_missing_locations(tree)) + '\n'
        compile(text, str(path), 'exec')
        path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', action='append', default=[])
    parser.add_argument('--root-target', required=True)
    parser.add_argument('--maps', default='collision,corners')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('output must be new')
    cli = executable()
    report = {'status': 'running', 'inclusive': True, 'instrumentation_overhead_included': True, 'runs': []}
    for variant in ('baseline', 'optimized'):
        folder = output / variant
        options = Options(disabled=frozenset(PASS_DESCRIPTIONS)) if variant == 'baseline' else Options()
        compiled = optimize_folder(args.bot, folder, options)
        instrument(folder, args.target, args.root_target)
        for game_map in args.maps.split(','):
            dest = output / f'{variant}-{game_map}'
            run_command([cli, 'run', str(folder), str(folder), '--release', '--rounds', '1',
                         '--fuel', '1000000000', '--map', game_map, '--out-dir', str(dest)], timeout=300)
            replay, = dest.glob('*.repl26a')
            logs = replay_logs(replay)
            check_logs(logs)
            for side in ('a', 'b'):
                samples = [ast.literal_eval(line.removeprefix('BCOPT_PROFILE '))
                           for line in logs[f'team-{side}.stdout'].splitlines()
                           if line.startswith('BCOPT_PROFILE ')]
                if len(samples) != 1:
                    raise ValueError('Expected one completed profile per team')
                row = {'variant': variant, 'map': game_map, 'side': side,
                       'input_sha256': compiled['input_sha256'], 'totals': samples[0]}
                report['runs'].append(row)
                print(row, flush=True)
            (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
