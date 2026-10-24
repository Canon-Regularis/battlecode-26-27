"""Bitwise host checks of the actual emitted experimental prefix-fold block."""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import random
import struct


def extract(path):
    tree = ast.parse(path.read_text())
    blocks = []
    for parent in ast.walk(tree):
        for _, body in ast.iter_fields(parent):
            if not isinstance(body, list):
                continue
            for index, node in enumerate(body):
                if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id == '_bcopt_fold80_initial'):
                    end = next(i for i in range(index, len(body)) if isinstance(body[i], ast.Delete)
                               and any(isinstance(part, ast.Name) and part.id == '_bcopt_fold80_iterator'
                                       for part in ast.walk(body[i])))
                    blocks.append(copy.deepcopy(body[index:end+1]))
    body, = blocks
    target = body[0].value.id
    scope = ast.Module(body=body, type_ignores=[])
    position, = {part.id for part in ast.walk(scope) if isinstance(part, ast.Name)
                 and part.id.startswith('_bcopt_edge_position')}
    table, = {part.value.value.id for part in ast.walk(scope) if isinstance(part, ast.Subscript)
              and isinstance(part.value, ast.Subscript) and isinstance(part.value.value, ast.Name)}
    mapping = {target: 'result', position: 'position', table: 'table'}
    class Rename(ast.NodeTransformer):
        def visit_Name(self, node):
            node.id = mapping.get(node.id, node.id)
            return node
    scope = Rename().visit(scope)
    wrapper = ast.parse('def folded(table, route, position, initial, _bcopt_fold80_group):\n    result = initial\n    return result').body[0]
    wrapper.body[1:1] = scope.body
    namespace = {'_bcopt_fold80_iter': iter, '_bcopt_fold80_next': next}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])), '<emitted-prefix-fold>', 'exec'), namespace)
    return namespace['folded']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('planner', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    folded = extract(args.planner)
    rng = random.Random(8047)
    samples = [0.0, -0.0, 1.0, -1.0, 1e16, -1e16, 1e308, -1e308,
               1e-300, -1e-300, float('inf'), float('-inf')]
    samples += [struct.unpack('<d', struct.pack('<Q', bits))[0]
                for bits in (0x7ff8000000000123, 0xfff8000000000123, 0x7ff0000000000123)]
    digest, evaluations = hashlib.sha256(), 0
    for case in range(4000):
        width = rng.randrange(2, 13)
        base = tuple(rng.randrange(-width, width) for _ in range(rng.randrange(0, 13)))
        added = rng.randrange(-width, width)
        table = [[rng.choice(samples) if case % 2 else rng.uniform(-100, 100)
                  for _ in range(width)] for _ in range(width)]
        group = [None]
        initial = rng.choice(samples) if case % 2 else rng.uniform(1, 100)
        for position in range(len(base)+1):
            if case % 3 == 0 and rng.randrange(4) == 0:
                continue  # Require fallback after skipped positions.
            if case % 5 == 0:
                initial = rng.choice(samples)
            route = base[:position]+(added,)+base[position:]
            expected = initial
            for origin, destination in zip(route, route[1:]):
                expected += table[destination][origin]
            actual = folded(table, route, position, initial, group)
            a, b = struct.pack('>d', expected), struct.pack('>d', actual)
            if a != b:
                raise AssertionError((case, route, position, initial, a.hex(), b.hex()))
            digest.update(a)
            evaluations += 1
    report = {'status': 'complete', 'cases': 4000, 'evaluations': evaluations,
              'bitwise_float_results_equal': True, 'includes_nan_payloads_and_signed_zero': True,
              'observations_sha256': digest.hexdigest(),
              'planner_sha256': hashlib.sha256(args.planner.read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
