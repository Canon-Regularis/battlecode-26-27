"""Exercise the manual region fast path, invalidation, and original fallbacks."""

import argparse
from dataclasses import asdict, is_dataclass
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
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be fresh')
    sys.path.insert(0, str(args.bot.resolve()/'src'))
    import planner as p
    from settings import SearchConfig

    count = 0
    for seed in range(240):
        rng = random.Random(seed)
        n, a = (0, 1, 2, 4, 8)[seed % 5], seed % 4
        camps = [p.CampGroupInfo((i, i+1), rng.randrange(40), rng.randrange(100),
                               rng.randrange(1, 20), rng.randrange(1, 100)) for i in range(n)]
        matrix = [[0 if i == j else rng.randrange(-1, 20) for j in range(n)] for i in range(n)]
        altars = [[rng.randrange(-1, 20) for _ in range(n)] for _ in range(a)]
        spawn = [rng.randrange(-1, 20) for _ in range(n)]
        risk = p.RiskProfile(tuple(rng.random() for _ in range(n)),
                             tuple(rng.random() for _ in range(a))) if seed % 3 else None
        config = SearchConfig(beam_width=1+seed % 5, max_camps=1+seed % 4,
                              max_expansions=(0, 1, 7, 8, 9, 32, 128, 256)[seed % 8],
                              gold_weight=rng.random(), opening_weight=rng.random(),
                              risk_tolerance=(0, 0.2, 1)[seed % 3])
        instance = p.LoopPlanner(camps, matrix, altars, spawn, config=config, risk=risk)
        data = p._region_context(instance, camps, config, {i: [()] for i in range(a)}, instance.evaluate_loop)
        assert data is not None, seed
        for altar in range(a):
            for length in range(min(n, 4)+1):
                route = tuple(range(length))
                assert normalized(instance.evaluate_loop(route, altar)) == normalized(
                    p._region_evaluate(data, route, altar)), (seed, route, altar)
                count += 1
        outcomes = []
        for fast in (False, True):
            calls = [0]
            def stop():
                calls[0] += 1
                return calls[0] > (0, 1, 2, 10000)[seed % 4]
            value = (p._region_find_loops(instance, should_stop=stop, limit=seed % 7, _callback_safe=True)
                     if fast else instance.find_loops(should_stop=stop, limit=seed % 7))
            outcomes.append((normalized(value), calls[0]))
        assert outcomes[0] == outcomes[1], seed

    modes = ('unknown-callback', 'custom-truth', 'numeric-fallback', 'risk-override',
             'level-mutation', 'custom-beam', 'missing-field')
    for mode in modes:
        outcomes = []
        for fast in (False, True):
            events = []
            camps = [p.CampGroupInfo((i, 0), i+1, 2, 3, 4) for i in range(3)]
            matrix = [[0 if i == j else 2 for j in range(3)] for i in range(3)]
            config = SearchConfig(max_camps=3, max_expansions=100, beam_width=2)
            instance = p.LoopPlanner(camps, matrix, [[2, 3, 4]], [1, 2, 3], config=config,
                                     risk=p.RiskProfile((0.1, 0.2, 0.3), (0.4,)))
            safe = mode not in ('unknown-callback', 'custom-truth')
            def mutate():
                events.append('mutate')
                p.CampGroupInfo.__init__(camps[0], (0, 0), 17, 2, 3, 4)
                matrix[0][1] = 19
            class Truth:
                def __bool__(self):
                    mutate()
                    return False
            def stop():
                events.append('stop')
                if mode == 'unknown-callback':
                    mutate()
                if mode == 'custom-truth':
                    return Truth()
                return False
            if mode == 'numeric-fallback':
                class Number:
                    def __radd__(self, other):
                        events.append('add')
                        return other+7
                p.CampGroupInfo.__init__(camps[0], (0, 0), Number(), 2, 3, 4)
            if mode == 'missing-field':
                object.__delattr__(camps[0], 'gold')
            if mode == 'risk-override':
                def risk(*args):
                    events.append('risk')
                    return 0.25
                instance._calculate_loop_risk = risk
            if mode in ('level-mutation', 'custom-beam'):
                original = instance._select_next_beams
                class Beam(list):
                    def __getitem__(self, index):
                        mutate()
                        return super().__getitem__(index)
                def select(*args):
                    result = original(*args)
                    events.append('select')
                    if mode == 'level-mutation':
                        mutate()
                    else:
                        result = {key: Beam(value) for key, value in result.items()}
                    return result
                instance._select_next_beams = select
            try:
                value = (p._region_find_loops(instance, should_stop=stop, limit=3, _callback_safe=safe)
                         if fast else instance.find_loops(should_stop=stop, limit=3))
                value = normalized(value)
            except Exception as error:
                value = type(error).__name__, str(error)
            outcomes.append((value, list(events)))
        assert outcomes[0] == outcomes[1], (mode, outcomes)

    # The snapshot must not keep the source mutable tables alive after a dirty
    # terminating callback or a later region boundary.
    events = []
    class Marker:
        def __del__(self):
            events.append('released')
    camps = [p.CampGroupInfo((0, 0), 1, 2, 3, 4)]
    config = SearchConfig()
    instance = p.LoopPlanner(camps, [[0]], [[1]], [1], config=config)
    data = p._region_context(instance, camps, config, {0: [()]}, instance.evaluate_loop)
    assert data is not None
    instance.distances[0].append(Marker())
    del instance.distances
    assert events == ['released'], events

    report = {'status': 'complete', 'scenarios': 240, 'fast_contexts': 240,
              'direct_evaluations': count, 'exact_records_and_stop_counts_equal': True,
              'effect_cases': list(modes), 'mutable_alias_retention': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
