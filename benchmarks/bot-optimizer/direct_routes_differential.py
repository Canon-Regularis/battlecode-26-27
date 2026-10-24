"""Check actual emitted direct-route factories, including fresh tuple identity."""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import random


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('planner', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    tree = ast.parse(args.planner.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    factories = {}
    for branch in ast.walk(consumer):
        if (not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare)
                or not isinstance(branch.test.left, ast.Name) or branch.test.left.id != '_bcopt_fused_size'
                or not isinstance(branch.test.ops[0], ast.Eq)):
            continue
        width = branch.test.comparators[0].value
        unpack, producer = branch.body
        loop, = [node for node in ast.walk(producer) if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Name) and node.target.id == '_bcopt_edge_position']
        block = copy.deepcopy([unpack, loop.body[0]])
        namespace = {}
        wrapper = ast.parse(f'def factory({unpack.value.id}, {producer.target.id}, {loop.target.id}):\n    return route').body[0]
        wrapper.body[:0] = block
        exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])), '<emitted-direct-routes>', 'exec'), namespace)
        factories[width] = namespace['factory']
    assert sorted(factories) == list(range(2,13))
    rng, digest, cases = random.Random(807770), hashlib.sha256(), 0
    for case in range(1000):
        for width, factory in factories.items():
            base = tuple(rng.randrange(-4,5) if case % 2 else rng.randrange(-10**100,10**100) for _ in range(width-1))
            item = rng.randrange(-4,5)
            for position in range(width):
                first, second = factory(base,item,position), factory(base,item,position)
                expected = base[:position]+(item,)+base[position:]
                assert first == second == expected and first is not second and first is not base
                assert all(a is b for a,b in zip(first,expected))
                digest.update(repr(first).encode())
                cases += 1
    report = dict(status='complete',evaluations=cases,exact_routes_fresh_tuples_and_element_identities_equal=True,
                  observations_sha256=digest.hexdigest(),planner_sha256=hashlib.sha256(args.planner.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
