"""Exact checks of emitted retained integer-edge blocks and final loop locals."""

import argparse
import ast
import builtins
import hashlib
import json
from pathlib import Path
import random


def blocks(path):
    tree = ast.parse(path.read_text())
    consumer, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('_bcopt_region_consumer_')]
    result = {}
    for wrapper in ast.walk(consumer):
        if not (isinstance(wrapper, ast.For) and isinstance(wrapper.target, ast.Name)
                and wrapper.target.id == '_bcopt_position_once'):
            continue
        route = wrapper.body[0].value
        width = len(route.elts)
        position, = [i for i, n in enumerate(route.elts) if n.id == '_bcopt_fused_camp_index']
        version, = [n for n in ast.walk(wrapper) if isinstance(n, ast.If)
                    and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0']
        region = ast.Module(body=version.body, type_ignores=[])
        fast, = [n for n in ast.walk(region) if isinstance(n, ast.If)
                 and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_algebra_fast']
        result[width, position] = compile(ast.fix_missing_locations(ast.Module(body=fast.body, type_ignores=[])),
                                          '<actual-integer-edge-fast-block>', 'exec')
    assert len(result) == 77
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original, changed = blocks(args.baseline), blocks(args.candidate)
    rng, digest, cases = random.Random(808117), hashlib.sha256(), 0
    outputs = ('_bcopt_algebra_base_total', '_bcopt_algebra_first', '_bcopt_algebra_total',
               '_bcopt_algebra_a', '_bcopt_algebra_z')
    for trial in range(1000):
        n = rng.randrange(1, 9)
        def value():
            return rng.randrange(10**80) if trial % 3 == 0 else rng.randrange(100)
        matrix = tuple(tuple(value() for _ in range(n)) for _ in range(n))
        terminals = tuple(tuple(value() for _ in range(n)) for _ in range(2))
        for width in range(2, 13):
            base = tuple(rng.randrange(-n, n) for _ in range(width-1))
            environment = dict(_bcopt_entry_local_30=terminals, _bcopt_entry_local_34=matrix,
                               _bcopt_fused_route=base, _bcopt_algebra_builtins=builtins,
                               altar_index=trial % 2, _bcopt_algebra_base_total=None,
                               _bcopt_algebra_a=None, _bcopt_algebra_z=None)
            environment.update({f'_bcopt_direct_item_{i}': x for i, x in enumerate(base)})
            left, right = dict(environment), dict(environment)
            for item in (-1, 0, n-1):
                for position in range(width):
                    if trial % 3 == 0 and position % 2 == 0:
                        continue
                    route = base[:position]+(item,)+base[position:]
                    outcomes = []
                    for code, namespace in ((original[width, position], left), (changed[width, position], right)):
                        namespace.update(route=route, _bcopt_fused_camp_index=item)
                        exec(code, namespace)
                        outcomes.append(tuple(namespace[name] for name in outputs))
                    assert outcomes[0] == outcomes[1], (trial, width, position, outcomes)
                    digest.update(repr(outcomes[1]).encode())
                    cases += 1
    report = dict(status='complete', cases=cases, exact_integer_edges_totals_and_final_loop_locals_equal=True,
                  observations_sha256=digest.hexdigest(), baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                  candidate_sha256=hashlib.sha256(args.candidate.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
