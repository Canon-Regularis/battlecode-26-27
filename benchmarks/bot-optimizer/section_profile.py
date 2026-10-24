"""Inclusive guest profiles of current economy planner sections, not savings claims.

Section probes include timing/name-construction overhead. The emitted source and
section inventory are archived so boundaries can be audited against each run.
"""

import argparse
import ast
import copy
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


def numeric_sections(folder):
    """Profile the emitted evaluator and count repeated exact argument tuples."""
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    function, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_numeric_')
                 and len(node.body) == 1 and isinstance(node.body[0], ast.Try)]
    retry, = function.body
    if not isinstance(retry, ast.Try):
        raise ValueError('numeric retry layout changed')
    boundaries = [('inputs', None), ('edges', 'legs ='), ('totals', 'gems ='),
                  ('timing', 'tribute_turns ='), ('scoring', 'reward_value ='),
                  ('risk', 'loop_risk ='), ('record', 'risk_multiplier =')]
    alias, start = '_bcopt_sections_profile', '_bcopt_section_start'
    if {alias, start, '_bcopt_profile_arguments'} & used_names(tree):
        raise ValueError('numeric probe name collision')
    groups, pending = [(boundaries[0][0], [])], list(boundaries[1:])
    for statement in retry.body:
        if pending and ast.unparse(statement).startswith(pending[0][1]):
            label, _ = pending.pop(0)
            groups.append((label, []))
        groups[-1][1].append(statement)
    if pending or any(not statements for _, statements in groups):
        raise ValueError('numeric section boundaries changed')
    inventory = {}
    output = ast.parse(f'import _bcopt_fuel_profile as {alias}\n'
                       f'_bcopt_profile_arguments = (route, altar_index)\n'
                       f'if _bcopt_profile_arguments in {alias}.arguments:\n'
                       f'    {alias}.duplicates += 1\n'
                       f'else:\n'
                       f'    {alias}.arguments.add(_bcopt_profile_arguments)\n').body
    for label, statements in groups:
        key = f'numeric/{label}'
        inventory[key] = '\n'.join(ast.unparse(node) for node in statements)
        output.extend(ast.parse(f'{start} = {alias}.cambc.fuel_remaining()').body)
        finish = ast.parse(f'{alias}.record(({key!r}, len(route)), {start})').body
        output.append(ast.Try(body=statements, handlers=[], orelse=[], finalbody=finish))
    retry.body = output
    path.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n')
    return inventory


def inline_section_probes(tree, inventory):
    """Benchmark-only probes inserted before the production entry inliner.

    Straight-line boundaries and early-return probes survive return lowering;
    nested try/finally wrappers would prevent that lowering. Exception paths are
    excluded from these timing intervals and must not occur in this workload.
    """
    entries = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and getattr(node, '_bcopt_index_retry', None) is not None
               and len(node.body) == 1 and isinstance(node.body[0], ast.Try)
               and any(isinstance(part, ast.Name) and part.id == 'legs' for part in ast.walk(node))]
    if not entries:
        return False
    function, = entries
    alias, start = '_bcopt_inline_profile', '_bcopt_inline_start'
    if {alias, start} & used_names(tree):
        raise ValueError('inline probe name collision')
    boundaries = [('inputs', None), ('edges', 'legs ='), ('totals', 'gems ='),
                  ('timing', 'tribute_turns ='), ('scoring', 'reward_value ='),
                  ('risk', 'loop_risk ='), ('record', 'risk_multiplier =')]
    groups, pending = [(boundaries[0][0], [])], list(boundaries[1:])
    for statement in function.body[0].body:
        if pending and ast.unparse(statement).startswith(pending[0][1]):
            label, _ = pending.pop(0)
            groups.append((label, []))
        groups[-1][1].append(statement)
    if pending or any(not body for _, body in groups):
        raise ValueError('inline section boundaries changed')
    output = []
    for index, (label, statements) in enumerate(groups):
        key = f'inline/{label}'
        inventory[key] = '\n'.join(ast.unparse(node) for node in statements)
        finish = ast.parse(f'{alias}.record(({key!r}, len(route)), {start})').body
        class FinishReturn(ast.NodeTransformer):
            def visit_Return(self, node):
                return [*copy.deepcopy(finish), node]
        output.extend(ast.parse(f'{start} = {alias}.cambc.fuel_remaining()').body)
        wrapper = FinishReturn().visit(ast.Module(body=statements, type_ignores=[]))
        output.extend(wrapper.body)
        if index + 1 < len(groups):
            output.extend(copy.deepcopy(finish))
    function.body[0].body = output
    index = 1 if isinstance(tree.body[0], ast.Expr) else 0
    while isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = ast.parse(f'import _bcopt_fuel_profile as {alias}').body
    ast.fix_missing_locations(tree)
    return True


def consumer_sections(folder):
    """Measure generator resumption separately from its consumer's work."""
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
             and (isinstance(node.target, ast.Name) and node.target.id == 'route'
                  or isinstance(node.target, ast.Tuple) and isinstance(node.target.elts[0], ast.Name)
                  and node.target.elts[0].id == 'route')]
    alias, start, generation = '_bcopt_consumer_profile', '_bcopt_consumer_start', '_bcopt_generation_start'
    if {alias, start, generation} & used_names(tree):
        raise ValueError('consumer probe name collision')
    groups, pending = [('checks', [])], [('numeric-dispatch', 'if _bcopt_region_live_'),
                                       ('candidate', 'if evaluation is None:')]
    for statement in loop.body:
        if pending and ast.unparse(statement).startswith(pending[0][1]):
            label, _ = pending.pop(0)
            groups.append((label, []))
        groups[-1][1].append(statement)
    if pending or any(not body for _, body in groups):
        raise ValueError('consumer section boundaries changed')
    inventory, output = {}, []
    for label, statements in groups:
        key = f'consumer/{label}'
        inventory[key] = '\n'.join(ast.unparse(node) for node in statements)
        output.extend(ast.parse(f'{start} = {alias}.cambc.fuel_remaining()').body)
        finish = ast.parse(f'{alias}.record(({key!r}, len(route)), {start})').body
        output.append(ast.Try(body=statements, handlers=[], orelse=[], finalbody=finish))
    loop.body = [*ast.parse(f"{alias}.record(('consumer/generation', len(route)), {generation})").body,
                 ast.Try(body=output, handlers=[], orelse=[],
                         finalbody=ast.parse(f'{generation} = {alias}.cambc.fuel_remaining()').body)]
    class StartGenerator(ast.NodeTransformer):
        def visit_For(self, node):
            if node is loop:
                return [*ast.parse(f'{generation} = {alias}.cambc.fuel_remaining()').body, node]
            return self.generic_visit(node)
    StartGenerator().visit(consumer)
    consumer.body[:0] = ast.parse(f'import _bcopt_fuel_profile as {alias}').body
    path.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n')
    return inventory, consumer.name


def fused_sections(folder):
    """Post-optimization probes: do not disturb emitter metadata or late passes."""
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    alias, start = '_bcopt_fused_profile', '_bcopt_fused_profile_start'
    assert not {alias, start} & used_names(tree)
    inventory = {}
    def wrap(label, statements):
        key = 'fused/'+label
        inventory.setdefault(key, []).append('\n'.join(ast.unparse(node) for node in statements))
        return [*ast.parse(f'{start} = {alias}.cambc.fuel_remaining()').body,
                ast.Try(body=statements, handlers=[], orelse=[],
                        finalbody=ast.parse(f'{alias}.record(({key!r}, len(route)), {start})').body)]
    sites = 0
    for protected in list(ast.walk(consumer)):
        if not isinstance(protected, ast.Try) or not protected.handlers:
            continue
        branches = [node for node in protected.body if isinstance(node, ast.If)
                    and any(isinstance(part, ast.Attribute) and part.attr == '__dict__'
                            for statement in node.orelse for part in ast.walk(statement))]
        if len(branches) != 1:
            continue
        branch, = branches
        fields = {node.targets[0].slice.value: node.value.id for node in branch.orelse
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript)
                  and isinstance(node.targets[0].slice, ast.Constant) and isinstance(node.value, ast.Name)}
        assert {'travel_turns', 'risk', 'risk_multiplier'} <= fields.keys()
        boundaries = [('timing', fields['travel_turns']), ('risk', fields['risk']), ('record', fields['risk_multiplier'])]
        groups, pending = [('totals', [])], list(boundaries)
        for statement in branch.orelse:
            if (pending and isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id == pending[0][1]):
                label, _ = pending.pop(0)
                groups.append((label, []))
            groups[-1][1].append(statement)
        assert not pending and all(body for _, body in groups)
        index = protected.body.index(branch)
        assert index > 0
        protected.body[:index] = wrap('edges', protected.body[:index])
        branch.orelse = [part for label, body in groups for part in wrap(label, body)]
        sites += 1
    assert sites == 2, sites
    consumer.body[:0] = ast.parse(f'import _bcopt_fuel_profile as {alias}').body
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)
    return inventory, consumer.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision,corners')
    parser.add_argument('--functions-only', action='store_true',
                        help='Profile generated helpers and planner methods without relying on section layout')
    parser.add_argument('--numeric-sections', action='store_true',
                        help='Profile emitted numeric sections and exact-argument duplication')
    parser.add_argument('--inline-sections', action='store_true',
                        help='Profile the actual inlined numeric consumer using pre-inlining probes')
    parser.add_argument('--consumer-sections', action='store_true',
                        help='Profile generator resumes, consumer checks, dispatch, candidate handling and beam selection')
    parser.add_argument('--fused-sections', action='store_true',
                        help='Profile final fused numeric code after all production optimizations')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new')
    folder = args.output.resolve() / 'optimized'
    inventory = {}
    if args.inline_sections:
        from tools.bot_optimizer.entry_inlining import InlineNumericEntries
        original_apply = InlineNumericEntries.apply
        def profiled_apply(pass_, tree):
            instrumented = inline_section_probes(tree, inventory)
            result = original_apply(pass_, tree)
            if instrumented and not pass_.changes:
                raise ValueError('probes prevented entry inlining')
            return result
        InlineNumericEntries.apply = profiled_apply
        try:
            compiled = optimize_folder(args.bot, folder)
        finally:
            InlineNumericEntries.apply = original_apply
        if not inventory:
            raise ValueError('no inline sections instrumented')
    else:
        compiled = optimize_folder(args.bot, folder)
    if args.fused_sections:
        inventory, consumer = fused_sections(folder)
        targets = [f'planner:{consumer}', 'planner:LoopPlanner._select_next_beams']
    elif args.consumer_sections:
        inventory, consumer = consumer_sections(folder)
        targets = [f'planner:{consumer}', 'planner:LoopPlanner._select_next_beams']
    elif args.inline_sections:
        tree = ast.parse((folder/'src/planner.py').read_text())
        consumer, = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name.startswith('_bcopt_region_consumer_')]
        targets = [f'planner:{consumer}', 'planner:LoopPlanner.find_loops']
    elif args.numeric_sections:
        inventory = numeric_sections(folder)
        targets = ['planner:LoopPlanner.find_loops']
    elif args.functions_only:
        tree = ast.parse((folder / 'src/planner.py').read_text())
        helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name.startswith('_bcopt_')
                   and not any(isinstance(part, (ast.Yield, ast.YieldFrom, ast.Await)) for part in ast.walk(node))]
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
    if args.numeric_sections:
        helper = folder/'src/_bcopt_fuel_profile.py'
        helper.write_text(helper.read_text()+'\narguments = set()\nduplicates = 0\n')
        path = folder/'src/draft_planner.py'
        tree = ast.parse(path.read_text())
        owner, = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'DraftPlanner']
        build, = [node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == 'build']
        wrapper = next(node for node in build.body if isinstance(node, ast.Try))
        wrapper.finalbody.extend(ast.parse('import _bcopt_fuel_profile as _profile80\n'
            "print('BCOPT_DUPLICATES ' + repr((len(_profile80.arguments), _profile80.duplicates)), flush=True)\n").body)
        path.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n')
    report = {'status': 'running', 'inclusive': True, 'instrumentation_overhead_included': True,
              'input_sha256': compiled['input_sha256'], 'sections': inventory, 'runs': [],
              'functions_only': args.functions_only, 'numeric_sections': args.numeric_sections,
              'inline_sections': args.inline_sections, 'consumer_sections': args.consumer_sections,
              'fused_sections': args.fused_sections, 'targets': targets}
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
            if args.numeric_sections:
                duplicates, = [ast.literal_eval(line.removeprefix('BCOPT_DUPLICATES '))
                               for line in logs[f'team-{side}.stdout'].splitlines() if line.startswith('BCOPT_DUPLICATES ')]
                report['runs'][-1]['distinct_arguments'], report['runs'][-1]['repeated_arguments'] = duplicates
            print(game_map, side, json.dumps(totals), flush=True)
        (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    report['status'] = 'complete'
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
