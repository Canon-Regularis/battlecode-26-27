"""Inclusive guest profiles of current economy planner sections, not savings claims.

Section probes include timing/name-construction overhead. The emitted source and
section inventory are archived so boundaries can be audited against each run.
"""

import argparse
import ast
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import optimize_folder
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.runtime import executable, run_command, replay_logs, check_logs


SECTIONS = {
    'evaluate_loop': [
        ('inputs', None), ('edges', 'if not _bcopt_extend_pairs_'),
        ('totals', '_bcopt_reduce_totals_0 ='), ('timing', 'tribute_turns ='),
        ('scoring', 'reward_value ='), ('risk', 'loop_risk ='),
        ('record', '_bcopt_return_record_0 ='),
    ],
    '_calculate_loop_risk': [
        ('setup', None), ('altar-exposure', 'exposure ='),
        ('inter-camp', ('for origin, destination', 'if _bcopt_adj_type_')), ('service', 'exposure += sum'),
        ('waiting-clamp', 'exposure += (tribute_turns'),
    ],
}


def sections(folder):
    path = folder / 'src/planner.py'
    tree = ast.parse(path.read_text())
    owner, = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LoopPlanner']
    taken, inventory = used_names(tree), {}
    alias, start = '_bcopt_sections_profile', '_bcopt_section_start'
    if {alias, start} & taken:
        raise ValueError('section probe name collision')
    for name, boundaries in SECTIONS.items():
        function, = [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name]
        body = function.body[:]
        doc = []
        if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            doc, body = body[:1], body[1:]
        groups = [(boundaries[0][0], [])]
        pending = list(boundaries[1:])
        for statement in body:
            text = ast.unparse(statement)
            if pending and text.startswith(pending[0][1]):
                label, _ = pending.pop(0)
                groups.append((label, []))
            groups[-1][1].append(statement)
        if pending or any(not statements for _, statements in groups):
            raise ValueError(f'section boundaries no longer match {name}: {pending}')
        result = [*doc, *ast.parse(f'import _bcopt_fuel_profile as {alias}').body]
        for label, statements in groups:
            key = f'{name}/{label}'
            inventory[key] = '\n'.join(ast.unparse(n) for n in statements)
            result.extend(ast.parse(f'{start} = {alias}.cambc.fuel_remaining()').body)
            finish = ast.parse(f'{alias}.record(({key!r}, len(route)), {start})').body
            result.append(ast.Try(body=statements, handlers=[], orelse=[], finalbody=finish))
        function.body = result
    text = ast.unparse(ast.fix_missing_locations(tree)) + '\n'
    compile(text, str(path), 'exec')
    path.write_text(text)
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision,corners')
    parser.add_argument('--functions-only', action='store_true',
                        help='Profile generated helpers and planner methods without relying on section layout')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new')
    folder = args.output.resolve() / 'optimized'
    compiled = optimize_folder(args.bot, folder)
    if args.functions_only:
        tree = ast.parse((folder / 'src/planner.py').read_text())
        helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name.startswith('_bcopt_')]
        inventory = {node.name: ast.unparse(node) for node in helpers}
        targets = [*(f'planner:{node.name}' for node in helpers),
                   'planner:LoopPlanner.evaluate_loop', 'planner:LoopPlanner._calculate_loop_risk',
                   'planner:LoopPlanner.find_loops']
    else:
        inventory = sections(folder)
        targets = ['planner:LoopPlanner.find_loops']
    spec = importlib.util.spec_from_file_location('fuel_profile', Path(__file__).with_name('profile.py'))
    profiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profiler)
    profiler.instrument(folder, targets, 'draft_planner:DraftPlanner.build')
    report = {'status': 'running', 'inclusive': True, 'instrumentation_overhead_included': True,
              'input_sha256': compiled['input_sha256'], 'sections': inventory, 'runs': [],
              'functions_only': args.functions_only, 'targets': targets}
    for game_map in args.maps.split(','):
        dest = args.output.resolve() / game_map
        run_command([executable(), 'run', str(folder), str(folder), '--release', '--rounds', '1',
                     '--fuel', '1000000000', '--map', game_map, '--out-dir', str(dest)], timeout=300)
        replay, = dest.glob('*.repl26a')
        logs = replay_logs(replay)
        check_logs(logs)
        for side in ('a', 'b'):
            samples = [ast.literal_eval(line.removeprefix('BCOPT_PROFILE '))
                       for line in logs[f'team-{side}.stdout'].splitlines() if line.startswith('BCOPT_PROFILE ')]
            if len(samples) != 1:
                raise ValueError('expected one completed profile')
            totals, by_length = {}, {}
            for key, (count, fuel) in samples[0].items():
                label = key[0] if isinstance(key, tuple) else key
                row = totals.setdefault(label, {'calls': 0, 'fuel': 0})
                row['calls'] += count
                row['fuel'] += fuel
                if isinstance(key, tuple):
                    by_length.setdefault(label, {})[str(key[1])] = {'calls': count, 'fuel': fuel}
            report['runs'].append({'map': game_map, 'side': side, 'totals': totals, 'by_route_length': by_length})
            print(game_map, side, json.dumps(totals), flush=True)
        (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
