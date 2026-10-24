"""Deterministic held-out pure-planner scenarios; host semantics, not fuel claims.

Runs original/generated modules in separate processes. Compares complete returned
records (floats as exact hex strings), stop callback counts, and input mutation.
"""

import argparse
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys


def normalized(value):
    if is_dataclass(value):
        return normalized(asdict(value))
    if isinstance(value, float):
        return {'float_hex': value.hex()}
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    return value


def scenarios(bot):
    sys.path.insert(0, str(bot.resolve() / 'src'))
    from planner import CampGroupInfo, LoopPlanner, RiskProfile
    from settings import SearchConfig

    results = []
    for seed in range(240):
        rng = random.Random(seed)
        n = (0, 1, 2, 4, 8)[seed % 5]
        altars = seed % 4
        camps = [CampGroupInfo((i, i + 1), rng.randrange(40), rng.randrange(100),
                               rng.randrange(1, 20), rng.randrange(1, 100)) for i in range(n)]
        distances = [[0 if i == j else rng.randrange(-1, 20) for j in range(n)] for i in range(n)]
        altar_distances = [[rng.randrange(-1, 20) for _ in range(n)] for _ in range(altars)]
        spawn = [rng.randrange(-1, 20) for _ in range(n)]
        risk = (RiskProfile(tuple(rng.random() for _ in range(n)),
                            tuple(rng.random() for _ in range(altars))) if seed % 3 else None)
        config = SearchConfig(beam_width=1 + seed % 5, max_camps=1 + seed % 4,
                              max_expansions=(0, 1, 7, 8, 9, 32, 128, 256)[seed % 8],
                              gold_weight=rng.random(), opening_weight=rng.random(),
                              risk_tolerance=(0, 0.2, 1)[seed % 3])
        planner = LoopPlanner(camps, distances, altar_distances, spawn, config=config, risk=risk)
        inputs = normalized((camps, distances, altar_distances, spawn, config, risk))
        evaluations = [planner.evaluate_loop(tuple(range(length)), altar)
                       for altar in range(altars) for length in range(min(n, 4) + 1)]
        calls = 0
        stop_after = (0, 1, 2, 10000)[seed % 4]

        def should_stop():
            nonlocal calls
            calls += 1
            return calls > stop_after

        loops = planner.find_loops(should_stop=should_stop, limit=seed % 7)
        if inputs != normalized((camps, distances, altar_distances, spawn, config, risk)):
            raise AssertionError(f'Input mutation in scenario {seed}')
        results.append(normalized({'seed': seed, 'evaluations': evaluations,
                                   'loops': loops, 'stop_calls': calls}))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(scenarios(args.bot), sort_keys=True))
        return
    if args.output is None or args.output.exists():
        parser.error('a fresh --output directory is required')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.bot_optimizer import optimize_folder
    report = optimize_folder(args.bot, args.output / 'optimized')
    payloads = []
    for variant, folder in (('original', args.bot), ('optimized', args.output / 'optimized')):
        data = subprocess.check_output([sys.executable, __file__, str(folder), '--worker'])
        (args.output / f'{variant}.json').write_bytes(data)
        payloads.append(data)
    if payloads[0] != payloads[1]:
        raise AssertionError('Differential scenarios disagree; inspect saved complete observations')
    result = {'status': 'complete', 'scenario_count': 240, 'exact_observations_equal': True,
              'float_comparison': 'hex strings', 'input_mutation': False,
              'fuel_measurement': False, 'input_sha256': report['input_sha256'],
              'pass_counts': report['pass_counts'],
              'observations_sha256': hashlib.sha256(payloads[0]).hexdigest()}
    (args.output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
