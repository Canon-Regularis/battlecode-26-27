"""Domain-rich planner checks for guarded score pruning and stable selection."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

from planner_differential import normalized


def scenarios(folder):
    sys.path.insert(0, str(folder.resolve()/'src'))
    from planner import CampGroupInfo, LoopPlanner, RiskProfile
    from settings import SearchConfig
    results = []
    for seed in range(96):
        rng = random.Random(807582+seed)
        n, altars = (2, 4, 8, 12)[seed % 4], 1+seed % 3
        camps = [CampGroupInfo((i, i), rng.randrange(1, 40), rng.randrange(100),
                               rng.randrange(1, 20), rng.randrange(1, 100)) for i in range(n)]
        matrix = [[0 if a == b else rng.randrange(1, 80) for b in range(n)] for a in range(n)]
        terminal = [[rng.randrange(1, 80) for _ in range(n)] for _ in range(altars)]
        home = [rng.randrange(1, 80) for _ in range(n)]
        risks = tuple(rng.uniform(0.2, 0.9) for _ in range(n))
        altar_risks = tuple(rng.uniform(0.2, 0.9) for _ in range(altars))
        if seed % 7 == 0:
            risks, altar_risks = (0.5,)*n, (0.5,)*altars
        if seed % 11 == 0:
            risks, altar_risks = (0.0,)*n, (0.0,)*altars
        config = SearchConfig(beam_width=2+seed % 4, max_camps=2+seed % 5,
            max_expansions=(128, 256, 512, 1024)[seed % 4], gold_weight=rng.random(),
            opening_weight=rng.random(), risk_tolerance=(0.0, 0.2, 0.5, 0.8, 1.0)[seed % 5])
        owner = LoopPlanner(camps, matrix, terminal, home, config=config,
                            risk=RiskProfile(risks, altar_risks))
        before = normalized((camps, matrix, terminal, home, config, owner.risk))
        calls = 0
        action = ('continue', 'stop', 'throw', 'mutate-stop')[seed % 4]
        def stop():
            nonlocal calls
            calls += 1
            if calls != 13 or action == 'continue':
                return False
            if action == 'throw':
                raise RuntimeError('stop witness')
            if action == 'mutate-stop':
                owner.distances[0][0] += 1
            return True
        try:
            rows = owner.find_loops(should_stop=stop, limit=1+seed % 9)
            outcome = normalized(rows)
        except Exception as error:
            outcome = [type(error).__name__, str(error)]
        after = normalized((camps, matrix, terminal, home, config, owner.risk))
        if action != 'mutate-stop':
            assert before == after
        results.append(dict(seed=seed, outcome=outcome, stop_calls=calls, inputs=after))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('optimized', type=Path, nargs='?')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(scenarios(args.original), sort_keys=True))
        return
    assert args.optimized and args.output and not args.output.exists()
    args.output.mkdir(parents=True)
    observations = []
    for name, folder in (('original', args.original), ('optimized', args.optimized)):
        payload = subprocess.check_output([sys.executable, __file__, str(folder), '--worker'])
        (args.output/(name+'.json')).write_bytes(payload)
        observations.append(payload)
    assert observations[0] == observations[1], 'domain-rich planner mismatch; inspect archived observations'
    report = dict(status='complete', scenarios=96, exact_records_stable_ties_callbacks_errors_and_mutation_equal=True,
                  observations_sha256=hashlib.sha256(observations[0]).hexdigest())
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
