"""Host witnesses for research producer fusion, including nested stop/throw paths."""

import argparse
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--production', action='store_true')
    parser.add_argument('--cache-slots', choices=('scalar', 'resident'))
    parser.add_argument('--resident-edges', action='store_true')
    parser.add_argument('--rolling-prefix', action='store_true')
    parser.add_argument('--base-prefix', action='store_true')
    parser.add_argument('--direct-routes', action='store_true')
    parser.add_argument('--unroll-routes', action='store_true')
    args = parser.parse_args()
    if args.cache_slots:
        assert args.production, 'cache-slot research requires production producer fusion'
    if args.resident_edges:
        assert args.production and not args.cache_slots
    if args.rolling_prefix:
        assert args.production and not args.cache_slots and not args.resident_edges
    if args.base_prefix:
        assert args.production and not args.cache_slots and not args.resident_edges and not args.rolling_prefix
    if args.direct_routes:
        assert args.production and not args.cache_slots and not args.resident_edges and not args.rolling_prefix and not args.base_prefix
    assert not args.unroll_routes or args.direct_routes
    path = Path(__file__).with_name('eighty_inline_producer.py')
    spec = importlib.util.spec_from_file_location('fusion', path)
    fusion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fusion)
    source = Path(__file__).with_name('src').joinpath('eighty.py').read_text()
    if args.resident_edges and 'result = evaluate(route, 0)' in source:
        # Expose a loop-invariant selector rather than a per-call temporary so
        # this research witness exercises the two-field rolling-state path.
        source = source.replace('        results = {}', '        results = {}\n        selection = 0').replace(
            'result = evaluate(route, 0)', 'result = evaluate(route, selection)')
    disabled = set() if args.production else {'insertion-producer-fusion'}
    if args.cache_slots:
        disabled.update({'insertion-fused-cache-slots', 'insertion-resident-scalars'})
    if args.resident_edges:
        disabled.add('insertion-resident-edges')
    compiled = optimize_source(source, Options(disabled=frozenset(disabled)))
    if args.production:
        assert any(change.pass_name == 'insertion-producer-fusion' for change in compiled.changes)
    observations, contexts = [], 0
    for invariants in ((True,) if args.production else (False, True)):
        folder = args.output/('invariants' if invariants else 'plain')
        (folder/'src').mkdir(parents=True, exist_ok=True)
        target = folder/'src/planner.py'
        target.write_text(compiled.source)
        if not args.production:
            fusion.transform(folder, invariants=invariants)
        if args.cache_slots:
            slots_path = path.with_name('eighty_fused_slots.py')
            slots_spec = importlib.util.spec_from_file_location('slots', slots_path)
            slots = importlib.util.module_from_spec(slots_spec)
            slots_spec.loader.exec_module(slots)
            slots.transform(folder, resident_scalars=args.cache_slots == 'resident')
        if args.resident_edges:
            edge_path = path.with_name('eighty_resident_edges.py')
            edge_spec = importlib.util.spec_from_file_location('edges', edge_path)
            edges = importlib.util.module_from_spec(edge_spec)
            edge_spec.loader.exec_module(edges)
            edges.transform(folder)
        if args.rolling_prefix:
            prefix_spec = importlib.util.spec_from_file_location('prefix', path.with_name('eighty_rolling_prefix.py'))
            prefix = importlib.util.module_from_spec(prefix_spec)
            prefix_spec.loader.exec_module(prefix)
            prefix.transform(folder, producer_name='_bcopt_fused_value')
        if args.base_prefix:
            prefix_spec = importlib.util.spec_from_file_location('prefix', path.with_name('eighty_base_prefix.py'))
            prefix = importlib.util.module_from_spec(prefix_spec)
            prefix_spec.loader.exec_module(prefix)
            prefix.transform(folder, producer_name='_bcopt_fused_value', base='_bcopt_fused_base')
        if args.direct_routes:
            route_spec = importlib.util.spec_from_file_location('routes', path.with_name('eighty_direct_routes.py'))
            routes = importlib.util.module_from_spec(route_spec)
            route_spec.loader.exec_module(routes)
            routes.transform(folder, unroll=args.unroll_routes)
        original, optimized = execute(source), execute(target.read_text())
        for name in original['CASES']:
            expected, actual = original[name](), optimized[name]()
            assert expected == actual, (invariants, name, expected, actual)
            observations.append((invariants, name, actual))
        enter, = [value for name, value in optimized.items() if name.startswith('_bcopt_region_enter_')]
        fast, = [value for name, value in optimized.items() if name.startswith('_bcopt_region_consumer_')]
        parameter, = [name for name in inspect.signature(fast).parameters if name.startswith('_bcopt_region_state_')]
        for action in ('stop', 'throw', 'mutate-stop'):
            for after in (0, 1, 2, 5, 17, 100):
                outcomes = []
                for namespace, use_fast in ((original, False), (optimized, True)):
                    owner = namespace['Engine']([namespace['Item'](2, 3), namespace['Item'](5, 7)],
                                                (0.1, 0.9), (2.0, 2.0), [[2, 3], [5, 7]])
                    calls = []
                    def stop():
                        index = len(calls)
                        calls.append(index)
                        if index != after:
                            return False
                        if action == 'throw':
                            raise RuntimeError('callback exception')
                        if action == 'mutate-stop':
                            owner.matrix[0][0] += 10
                        return True
                    kwargs = dict(stop=stop, limit=2)
                    if use_fast:
                        state = enter(owner.search)
                        assert state is not None
                        contexts += 1
                        kwargs[parameter] = state
                    try:
                        rows = fast(owner, **kwargs) if use_fast else owner.search(**kwargs)
                        result = [(row.amount, row.duration, row.peak, row.score.hex()) for row in rows]
                    except Exception as error:
                        result = (type(error).__name__, str(error))
                    outcomes.append((result, calls, owner.matrix))
                assert outcomes[0] == outcomes[1], (invariants, action, after, outcomes)
                observations.append((invariants, action, after, outcomes[1]))
    report = dict(status='complete', fixture_observations=10 if args.production else 20, explicit_fast_contexts=contexts,
                  production=args.production,
                  cache_slots=args.cache_slots,
                  resident_edges=args.resident_edges,
                  rolling_prefix=args.rolling_prefix,
                  base_prefix=args.base_prefix,
                  direct_routes=args.direct_routes,
                  unroll_routes=args.unroll_routes,
                  callback_stops_throws_and_mutation_equal=True,
                  observations_sha256=hashlib.sha256(json.dumps(observations).encode()).hexdigest())
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
