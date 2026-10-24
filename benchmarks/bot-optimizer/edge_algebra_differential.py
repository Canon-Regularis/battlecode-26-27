"""Exercise the emitted edge-algebra block against original list construction."""

import argparse
import ast
import builtins
import copy
import hashlib
import json
from pathlib import Path
import random


def extract(path):
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    setup = [copy.deepcopy(node) for node in consumer.body if isinstance(node, ast.Assign)
             and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {'_bcopt_algebra80_n', '_bcopt_algebra80_cert'}]
    version, = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                and isinstance(node.test, ast.Name) and node.test.id == '_bcopt_entry_prepared_ready_0']
    protected, = version.body
    block = copy.deepcopy(protected.body[:-1])
    ending = ast.parse('''
_observed = None
if _bcopt_algebra80_fast:
    _observed = (_bcopt_algebra80_total, _bcopt_algebra80_first)
elif min(_bcopt_entry_local_40) >= 0 and _bcopt_entry_local_47[_bcopt_entry_local_35] >= 0:
    _observed = (sum(_bcopt_entry_local_40), _bcopt_entry_local_40[0])
''').body
    assert len(setup) == 2
    def compiled(nodes):
        return compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<emitted-edge-algebra>', 'exec')
    return compiled(setup), compiled([*block, *ending])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('planner', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    setup, code = extract(args.planner)
    rng = random.Random(80317)
    digest, evaluations, fast = hashlib.sha256(), 0, 0
    for case in range(4000):
        n = rng.randrange(1, 12)
        value = lambda: rng.choice([0, 1, 2, 10**100]) if case % 7 == 0 else rng.randrange(20)
        matrix = [[value() for _ in range(n)] for _ in range(n)]
        altars = [[value() for _ in range(n)] for _ in range(2)]
        home = [value() for _ in range(n)]
        if case % 5 == 0:
            matrix[0][0] = -1
        if case % 11 == 0:
            matrix[-1].pop()
        if case % 13 == 0:
            altars[0].pop()
        if case % 17 == 0:
            home[-1] = -1
        base = tuple(rng.randrange(-n, n) for _ in range(rng.randrange(13)))
        if base and case % 19 == 0:
            base = (n+1, *base[1:])
        namespace = {'_bcopt_algebra80_b': builtins, '_bcopt_entry_local_34': matrix,
                     '_bcopt_entry_local_30': altars, '_bcopt_entry_local_47': home,
                     '_bcopt_fused_route': base, '_bcopt_fused_size': len(base)+1,
                     '_bcopt_algebra80_valid': None, '_bcopt_algebra80_base_total': None,
                     'altar_index': case % 2}
        exec(setup, namespace)
        for added in (rng.randrange(-n, n), rng.randrange(-n, n), n if case % 23 == 0 else 0):
            namespace['_bcopt_cache_slot_0'] = None
            namespace['_bcopt_fused_camp_index'] = added
            for position in range(len(base)+1):
                if case % 3 == 0 and rng.randrange(4) == 0:
                    continue
                route = base[:position]+(added,)+base[position:]
                namespace.update(route=route, _bcopt_edge_position=position)
                try:
                    edges = [altars[case % 2][route[0]], altars[case % 2][route[-1]]]
                    edges.extend(matrix[a][b] for a, b in zip(route, route[1:]))
                    expected = None if min(edges) < 0 or home[route[0]] < 0 else (sum(edges), edges[0])
                except Exception as error:
                    expected = (type(error).__name__, str(error))
                try:
                    exec(code, namespace)
                    actual = namespace['_observed']
                    fast += bool(namespace['_bcopt_algebra80_fast'])
                except Exception as error:
                    actual = (type(error).__name__, str(error))
                assert actual == expected, (case, base, added, position, expected, actual)
                evaluations += 1
                digest.update(repr(actual).encode())
    report = dict(status='complete', cases=4000, evaluations=evaluations, algebra_evaluations=fast,
                  exact_totals_first_edges_rejections_and_errors_equal=True,
                  observations_sha256=digest.hexdigest(), planner_sha256=hashlib.sha256(args.planner.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
