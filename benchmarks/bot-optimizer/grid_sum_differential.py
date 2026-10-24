"""Check the emitted binary-grid certificate and integer division against sum."""

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import random
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('planner', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    tree = ast.parse(args.planner.read_text())
    helper, = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_bcopt_compensated_certify']
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])), '<emitted-grid-certificate>', 'exec'), namespace)
    certify = namespace[helper.name]
    for rejected in (None, [1], [-1.0], [float('inf')], [float('nan')], [1e300], [1.0]*4097,
                     [float.fromhex('0x1p-1074'), 1.0]):
        assert certify(rejected) is False, rejected
    rng, digest, cases, accepted, declined = random.Random(808080), hashlib.sha256(), 0, 0, 0
    fixtures = [[-0.0, 0.0], [float.fromhex('0x1p-1074'), float.fromhex('0x1p-1022')],
                [1.0, 2.0**-53, 2.0**-54], [float(2**79), float(2**27), 1.0],
                [math.nextafter(1.0, 0.0), 2.0**-53], [0.0]*4]
    for trial in range(20000):
        exponent = rng.randrange(-1074, 28)
        values = [math.ldexp(float(rng.randrange(1 << 53)), exponent+rng.randrange(28))
                  for _ in range(rng.randrange(1, 17))]
        if trial < len(fixtures):
            values = fixtures[trial]
        proof = certify(values)
        if proof is False:
            declined += 1
            continue
        integers, denominator = proof
        accepted += 1
        assert len(integers) == len(values)
        for size in (2, 3, 8, 16):
            route = [rng.randrange(-len(values), len(values)) for _ in range(size)]
            expected = sum(values[index] for index in route)
            actual = sum(integers[index] for index in route) / denominator
            assert struct.pack('d', expected) == struct.pack('d', actual), (trial, values, route, expected.hex(), actual.hex())
            digest.update(struct.pack('d', actual))
            cases += 1
    assert accepted > 10000 and cases > 40000
    report = dict(status='complete', accepted_tables=accepted, declined_tables=declined, bitwise_comparisons=cases,
                  exact_native_compensated_results=True, ordinary_sequential_sums_unchanged=True,
                  observations_sha256=digest.hexdigest(), planner_sha256=hashlib.sha256(args.planner.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
