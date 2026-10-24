"""Bitwise checks of actual emitted rolling-prefix branches, including skips."""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import random
import struct


def extract(path, base_prefix=False):
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    branches = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                and node.test.left.id.startswith('_bcopt_ordered_size') and isinstance(node.test.ops[0], ast.Eq)]
    result = {}
    for branch in branches:
        width = branch.test.comparators[0].value
        scope = ast.Module(body=copy.deepcopy(branch.body), type_ignores=[])
        target, = {part.target.id for part in ast.walk(scope) if isinstance(part, ast.AugAssign)
                   and not part.target.id.startswith('_bcopt_baseprefix80_')}
        table, = {part.value.value.id for part in ast.walk(scope) if isinstance(part, ast.Subscript)
                  and isinstance(part.value, ast.Subscript) and isinstance(part.value.value, ast.Name)}
        route = scope.body[0].value.id
        mapping = {target: 'result', table: 'table', route: 'route', '_bcopt_edge_position': 'position'}
        class Rename(ast.NodeTransformer):
            def visit_Name(self, node):
                node.id = mapping.get(node.id, node.id)
                return node
        Rename().visit(scope)
        wrapper = ast.parse('def folded(table, route, position, initial, state):\n'
                            '    _bcopt_prefix80_last, _bcopt_prefix80_value = state\n'
                            '    result = initial\n'
                            '    return result, (_bcopt_prefix80_last, _bcopt_prefix80_value)').body[0]
        wrapper.body[2:2] = scope.body
        if base_prefix:
            wrapper = ast.parse('def folded(table, route, position, initial, state):\n'
                                '    _bcopt_baseprefix80_cache, _bcopt_baseprefix80_key = state\n'
                                '    _bcopt_fused_route = route[:position] + route[position+1:]\n'
                                '    result = initial\n'
                                '    return result, (_bcopt_baseprefix80_cache, _bcopt_baseprefix80_key)').body[0]
            wrapper.body[3:3] = scope.body
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
                     '<emitted-rolling-prefix>', 'exec'), namespace)
        result[width] = namespace['folded']
    assert sorted(result) == list(range(2, 13))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('planner', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-prefix', action='store_true')
    args = parser.parse_args()
    folds = extract(args.planner, base_prefix=args.base_prefix)
    rng = random.Random(8073)
    samples = [0.0, -0.0, 1.0, -1.0, 1e16, -1e16, 1e308, -1e308,
               1e-300, -1e-300, float('inf'), float('-inf')]
    samples += [struct.unpack('<d', struct.pack('<Q', bits))[0]
                for bits in (0x7ff8000000000123, 0xfff8000000000123, 0x7ff0000000000123)]
    digest, evaluations, hits = hashlib.sha256(), 0, 0
    for case in range(6000):
        size = rng.randrange(2, 13)
        width = rng.randrange(2, 13)
        base = tuple(rng.randrange(-size, size) for _ in range(width-1))
        added = rng.randrange(-size, size)
        table = [[rng.choice(samples) if case % 2 else rng.uniform(-100, 100)
                  for _ in range(size)] for _ in range(size)]
        # Initial value may depend on endpoints, but is invariant inside a group.
        endpoints = [rng.choice(samples) if case % 2 else rng.uniform(-100, 100) for _ in range(size)]
        state = (None, None) if args.base_prefix else (-2, None)
        for position in list(range(width)) * (3 if args.base_prefix else 1):
            if position == 0 and args.base_prefix:
                added = rng.randrange(-size, size)
            if case % 3 == 0 and rng.randrange(4) == 0:
                continue
            route = base[:position]+(added,)+base[position:]
            initial = endpoints[route[0]] + endpoints[route[-1]]
            if args.base_prefix and case % 5 == 0:
                initial = rng.choice(samples)
            expected = initial
            for origin, destination in zip(route, route[1:]):
                expected += table[destination][origin]
            hits += ((0 < position < width-1 and state[0] is not None and state[0] is not False
                      and state[1] == initial and (initial != 0.0 or state[1].hex() == initial.hex())) if args.base_prefix
                     else (1 < position < width-1 and state[0] == position-1))
            actual, state = folds[width](table, route, position, initial, state)
            a, b = struct.pack('>d', expected), struct.pack('>d', actual)
            assert a == b, (case, route, position, a.hex(), b.hex())
            digest.update(a)
            evaluations += 1
    report = dict(status='complete', cases=6000, evaluations=evaluations, prefix_hits=hits,
                  base_prefix=args.base_prefix,
                  bitwise_float_results_equal=True, includes_nan_payloads_signed_zero_skips_and_endpoints=True,
                  observations_sha256=digest.hexdigest(), planner_sha256=hashlib.sha256(args.planner.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
