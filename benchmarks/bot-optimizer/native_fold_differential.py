"""Bitwise witnesses for actual emitted native ordered-fold branches."""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import random
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('planner', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    tree = ast.parse(args.planner.read_text())
    helpers = [node for node in tree.body if isinstance(node, ast.ImportFrom)
               and all(alias.asname and alias.asname.startswith('_bcopt_fold80_') for alias in node.names)
               or isinstance(node, ast.ClassDef) and node.name.startswith('_bcopt_fold80_')]
    namespace = {}
    exec(compile(ast.Module(body=helpers, type_ignores=[]), '<native-fold-helpers>', 'exec'), namespace)
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    folds = {}
    for branch in ast.walk(consumer):
        if (not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare)
                or not isinstance(branch.test.left, ast.Name) or not branch.test.left.id.startswith('_bcopt_ordered_size')
                or not isinstance(branch.test.ops[0], ast.Eq)):
            continue
        width = branch.test.comparators[0].value
        scope = ast.Module(body=copy.deepcopy(branch.body), type_ignores=[])
        target = scope.body[1].target.id if isinstance(scope.body[1], ast.AugAssign) else scope.body[1].targets[0].id
        table, = {node.value.value.id for node in ast.walk(scope) if isinstance(node, ast.Subscript)
                  and isinstance(node.value, ast.Subscript) and isinstance(node.value.value, ast.Name)}
        route = scope.body[0].value.id
        mapping = {target: 'result', table: 'table', route: 'route'}
        class Rename(ast.NodeTransformer):
            def visit_Name(self, node):
                node.id = mapping.get(node.id, node.id)
                return node
        Rename().visit(scope)
        wrapper = ast.parse('def folded(table, route, initial):\n    result = initial\n    return result').body[0]
        wrapper.body[1:1] = scope.body
        exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])), '<native-fold>', 'exec'), namespace)
        folds[width] = namespace['folded']
    assert sorted(folds) == list(range(2, 13))
    samples = [0.0, -0.0, 1.0, -1.0, 1e16, -1e16, 1e308, -1e308, 1e-300, -1e-300,
               float('inf'), float('-inf')]
    samples += [struct.unpack('<d', struct.pack('<Q', bits))[0]
                for bits in (0x7ff8000000000123, 0xfff8000000000123, 0x7ff0000000000123)]
    rng, digest = random.Random(80582), hashlib.sha256()
    for case in range(20000):
        n, width = rng.randrange(1, 13), rng.randrange(2, 13)
        table = [[rng.choice(samples) if case % 2 else rng.uniform(-100, 100) for _ in range(n)] for _ in range(n)]
        route = tuple(rng.randrange(-n, n) for _ in range(width))
        initial = rng.choice(samples) if case % 2 else rng.uniform(-100, 100)
        expected = initial
        for a, z in zip(route, route[1:]):
            expected += table[z][a]
        actual = folds[width](table, route, initial)
        a, b = struct.pack('>d', expected), struct.pack('>d', actual)
        assert a == b and type(actual) is float, (case, a.hex(), b.hex(), type(actual))
        digest.update(a)
    report = dict(status='complete', cases=20000, bitwise_results_and_exact_float_type_equal=True,
                  observations_sha256=digest.hexdigest(), planner_sha256=hashlib.sha256(args.planner.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
