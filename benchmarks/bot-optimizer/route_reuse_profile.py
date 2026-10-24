"""Count exact-route reuse on archived guest snapshots; host work, not fuel."""

import argparse
import ast
from collections import Counter
import inspect
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('snapshots', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timing', action='store_true', help='Also count repeated timing inputs within insertion groups')
    args = parser.parse_args()
    assert not args.output.exists()
    sys.path.insert(0, str(args.bot.resolve()/'src'))
    import planner as p
    from settings import SearchConfig
    tree = ast.parse((args.bot/'src/planner.py').read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    entries = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
               and isinstance(node.test, ast.Name) and node.test.id.startswith('_bcopt_region_live_')]
    assert entries
    for entry in entries:
        entry.body[:0] = ast.parse('_observe_route_reuse(route, altar_index)').body
    if args.timing:
        class Timing(ast.NodeTransformer):
            def visit_Assign(self, node):
                if any(isinstance(target, ast.Name) and target.id == '_bcopt_entry_local_29' for target in node.targets):
                    return [*ast.parse('_observe_timing(_bcopt_entry_local_48, route[0])').body, node]
                return node
        for node in ast.walk(consumer):
            if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == '_bcopt_entry_prepared_ready_0':
                node.body = Timing().visit(ast.Module(body=node.body, type_ignores=[])).body
        class Reset(ast.NodeTransformer):
            def visit_Assign(self, node):
                if (isinstance(node.value, ast.Constant) and node.value.value is None
                        and any(isinstance(target, ast.Name) and target.id == '_bcopt_cache_slot_3' for target in node.targets)):
                    return [node, *ast.parse('_timing_reset()').body]
                return node
        Reset().visit(consumer)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[consumer], type_ignores=[])), '<route-reuse>', 'exec'), vars(p))
    fast = getattr(p, consumer.name)
    enter, = [getattr(p, node.name) for node in tree.body if isinstance(node, ast.FunctionDef)
              and node.name.startswith('_bcopt_region_enter_')]
    parameter, = [name for name in inspect.signature(fast).parameters if name.startswith('_bcopt_region_state_')]
    reports = []
    for path in sorted(args.snapshots.glob('*-a-0.txt')):
        snapshot = ast.literal_eval(path.read_text())
        owner = p.LoopPlanner([p.CampGroupInfo(*row) for row in snapshot[0]],
            [list(row) for row in snapshot[1]], [list(row) for row in snapshot[2]], list(snapshot[3]),
            config=SearchConfig(*snapshot[4]), risk=p.RiskProfile(*snapshot[5]) if snapshot[5] else None)
        seen, bounded, counts = set(), {}, Counter()
        timing_seen, previous = set(), [None]
        def reset_timing():
            timing_seen.clear()
            previous[0] = None
            counts['timing_groups'] += 1
        def observe_timing(total, first):
            key = total, first
            counts['timing_evaluations'] += 1
            counts['adjacent_timing_hits'] += key == previous[0]
            counts['all_prior_timing_hits'] += key in timing_seen
            previous[0] = key
            timing_seen.add(key)
        p._timing_reset, p._observe_timing = reset_timing, observe_timing
        def observe(route, axis):
            key = axis, route
            counts['evaluations'] += 1
            counts['duplicate_routes'] += key in seen
            counts['bounded_hits'] += key in bounded
            seen.add(key)
            if len(bounded) < 4096:
                bounded[key] = True
        p._observe_route_reuse = observe
        rows = fast(owner, should_stop=lambda:False, limit=5, **{parameter:enter(owner.find_loops)})
        report = dict(snapshot=path.name, **counts, unique_routes=len(seen), cache_size=len(bounded), results=len(rows))
        reports.append(report)
        print(json.dumps(report))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(status='complete', fuel_measurement=False, reports=reports), indent=2)+'\n')


if __name__ == '__main__':
    main()
