"""Explicitly exercise emitted generic numeric/consumer paths on planner inputs.

This harness discovers private helper names in compiler output. Its callbacks are
test-controlled and mutate only counters; production callback identity/effect
dispatch is covered separately by compiler integration tests and actual Wasm.
"""

import argparse
import ast
from dataclasses import asdict, is_dataclass
import hashlib
import inspect
import json
from pathlib import Path
import random
import sys


def normalized(value):
    if is_dataclass(value):
        return normalized(asdict(value))
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inlined-entry', action='store_true', help='Instrument an experimental inlined numeric entry in memory')
    parser.add_argument('--entry-copies', type=int, default=1, help='Expected number of research loop-specialized entry copies')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be fresh')
    path = args.bot.resolve()/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    consumer, = consumers
    enter, = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)
              and node.name.startswith('_bcopt_region_enter_')]
    call_targets = {node.body.func.id for node in ast.walk(consumer)
                    if isinstance(node, ast.IfExp) and isinstance(node.body, ast.Call)
                    and isinstance(node.body.func, ast.Name) and node.body.func.id.startswith('_bcopt_region_numeric_')}
    inlined_entry = args.inlined_entry or not call_targets
    if inlined_entry:
        numeric, = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name.startswith('_bcopt_region_numeric_') and len(node.body) == 1
                    and isinstance(node.body[0], ast.Try)]
    else:
        numeric, = call_targets
    check, = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)
              and node.name.startswith('_bcopt_region_arguments_')}
    sys.path.insert(0, str(args.bot.resolve()/'src'))
    import planner as p
    from settings import SearchConfig
    counts = {'contexts': 0, 'direct_evaluations': 0, 'direct_fast_evaluations': 0, 'consumer_numeric_calls': 0}
    if inlined_entry:
        def observed_entry():
            counts['consumer_numeric_calls'] += 1
        marker = '_profile_inlined_numeric_entry'
        assert not hasattr(p, marker)
        setattr(p, marker, observed_entry)
        entries = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                   and isinstance(node.test, ast.Name) and node.test.id.startswith('_bcopt_region_live_')
                   and any(isinstance(part, ast.Name) and part.id.startswith(('_bcopt_inline80_', '_bcopt_entry_'))
                           for statement in node.body for part in ast.walk(statement))]
        assert len(entries) == args.entry_copies
        for entry in entries:
            entry.body.insert(0, ast.Expr(value=ast.Call(func=ast.Name(id=marker, ctx=ast.Load()), args=[], keywords=[])))
        if any(name.startswith(('_bcopt_sum80_certify', '_bcopt_compensated_certify')) for name in vars(p)):
            counts['compensated_cache_eligible'] = counts['compensated_cache_hits'] = 0
            def observe_sum(hit):
                counts['compensated_cache_eligible'] += 1
                counts['compensated_cache_hits'] += hit
            sum_marker = '_profile_compensated_cache'
            assert not hasattr(p, sum_marker)
            setattr(p, sum_marker, observe_sum)
            caches = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                      and isinstance(node.test, ast.BoolOp)
                      and any(isinstance(part, ast.Name) and part.id.startswith(('_bcopt_sum80_ready', '_bcopt_compensated_ready'))
                              for part in ast.walk(node.test))]
            assert caches
            for cache in caches:
                read = cache.body[0].value
                assert (isinstance(read, ast.Subscript) and isinstance(read.value, ast.Name)
                        or isinstance(read, ast.Name) and read.id.startswith(('_bcopt_slot80_', '_bcopt_cache_slot_')))
                cache.body[:0] = ast.parse(f'{sum_marker}({ast.unparse(read)} is not None)').body
        scalar_reads = [node for node in ast.walk(consumer) if isinstance(node, ast.Assign)
                        and isinstance(node.targets[0], ast.Name) and node.targets[0].id.startswith('_bcopt_group_scalar_state')]
        if scalar_reads:
            counts['scalar_group_calls'] = counts['scalar_group_hits'] = 0
            def observe_scalars(value):
                counts['scalar_group_calls'] += 1
                counts['scalar_group_hits'] += value is not None
                return value
            scalar_marker = '_profile_scalar_group'
            assert not hasattr(p, scalar_marker)
            setattr(p, scalar_marker, observe_scalars)
            for node in scalar_reads:
                assert (isinstance(node.value, ast.Subscript)
                        or isinstance(node.value, ast.Name) and node.value.id.startswith(('_bcopt_slot80_', '_bcopt_cache_slot_')))
                node.value = ast.Call(func=ast.Name(id=scalar_marker, ctx=ast.Load()), args=[node.value], keywords=[])
        exec(compile(ast.fix_missing_locations(ast.Module(body=[consumer], type_ignores=[])), '<inline-observation>', 'exec'), vars(p))
    fast, context = getattr(p, consumer.name), getattr(p, enter)
    state_parameter, = [name for name in inspect.signature(fast).parameters if name.startswith('_bcopt_region_state_')]
    numeric_function = getattr(p, numeric)
    def observed(*values):
        counts['consumer_numeric_calls'] += 1
        return numeric_function(*values)
    setattr(p, numeric, observed)
    observations = []
    for seed in range(240):
        rng = random.Random(seed)
        n, a = (0, 1, 2, 4, 8)[seed % 5], seed % 4
        camps = [p.CampGroupInfo((i, i+1), rng.randrange(40), rng.randrange(100),
                                rng.randrange(1, 20), rng.randrange(1, 100)) for i in range(n)]
        matrix = [[0 if i == j else rng.randrange(-1, 20) for j in range(n)] for i in range(n)]
        altars = [[rng.randrange(-1, 20) for _ in range(n)] for _ in range(a)]
        spawn = [rng.randrange(-1, 20) for _ in range(n)]
        risk = p.RiskProfile(tuple(rng.random() for _ in range(n)), tuple(rng.random() for _ in range(a))) if seed % 3 else None
        config = SearchConfig(beam_width=1+seed % 5, max_camps=1+seed % 4,
                              max_expansions=(0, 1, 7, 8, 9, 32, 128, 256)[seed % 8],
                              gold_weight=rng.random(), opening_weight=rng.random(),
                              risk_tolerance=(0.0, 0.2, 1.0)[seed % 3])
        instance = p.LoopPlanner(camps, matrix, altars, spawn, config=config, risk=risk)
        state = context(instance.find_loops)
        assert state is not None, seed
        counts['contexts'] += 1
        data, bounds = state
        inputs = normalized((camps, matrix, altars, spawn, config, risk))
        for altar in range(a):
            for length in range(min(n, 4)+1):
                route = tuple(range(length))
                valid = getattr(p, check)(bounds, route, altar)
                expected = instance.evaluate_loop(route, altar)
                actual = numeric_function(data, route, altar) if valid else instance.evaluate_loop(route, altar)
                assert normalized(expected) == normalized(actual), (seed, route, altar)
                counts['direct_evaluations'] += 1
                counts['direct_fast_evaluations'] += valid
        outcomes = []
        for use_fast in (False, True):
            calls = [0]
            def stop():
                calls[0] += 1
                return calls[0] > (0, 1, 2, 10000)[seed % 4]
            result = (fast(instance, should_stop=stop, limit=seed % 7, **{state_parameter: state})
                      if use_fast else instance.find_loops(should_stop=stop, limit=seed % 7))
            outcomes.append((normalized(result), calls[0]))
        assert outcomes[0] == outcomes[1], seed
        assert inputs == normalized((camps, matrix, altars, spawn, config, risk)), seed
        observations.append(outcomes[0])
    assert counts['direct_fast_evaluations'] and counts['consumer_numeric_calls']
    # The retained context must not retain source lists or records.
    events = []
    class Marker:
        def __del__(self):
            events.append('released')
    instance.distances.append([Marker()])
    del matrix
    del instance.distances
    assert events == ['released'], events
    report = {'status': 'complete', 'scenarios': 240, **counts, 'exact_records_and_stop_counts_equal': True,
              'mutable_alias_retention': False, 'observations_sha256': hashlib.sha256(
                  json.dumps(observations, sort_keys=True).encode()).hexdigest(),
               'planner_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if inlined_entry:
        report['inlined_entry_instrumentation'] = 'host-only in-memory entry counter; source files unchanged'
    args.output.mkdir(parents=True)
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
