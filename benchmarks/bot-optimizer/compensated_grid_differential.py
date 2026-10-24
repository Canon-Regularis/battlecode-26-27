"""Check the experimental grid certificate against exact rational reference sums."""

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--production', action='store_true')
    parser.add_argument('--native-certificate', action='store_true')
    args = parser.parse_args()
    path = Path(__file__).with_name('eighty_compensated_cache.py')
    spec = importlib.util.spec_from_file_location('compensated_experiment', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    namespace = {}
    exec(module.CERTIFICATE, namespace)
    certify = namespace['_bcopt_sum80_certify']
    if args.production:
        from tools.bot_optimizer.compensated_sums import CERTIFICATE
        exec(CERTIFICATE, namespace)
        certify = namespace['certify']
    if args.native_certificate:
        native_path = path.with_name('eighty_native_certificate.py')
        native_spec = importlib.util.spec_from_file_location('native_certificate', native_path)
        native = importlib.util.module_from_spec(native_spec)
        native_spec.loader.exec_module(native)
        exec(native.CERTIFICATE, namespace)
        certify = namespace['certify']
    rng, digest = random.Random(8013), hashlib.sha256()
    accepted = rejected = evaluations = 0
    for _ in range(12000):
        exponent = rng.randrange(-1074, 960)
        table = [math.ldexp(rng.random(), exponent+rng.randrange(0, 26)) for _ in range(rng.randrange(1, 33))]
        table.extend([0.0, -0.0])
        if not certify(table):
            rejected += 1
            continue
        accepted += 1
        values = [rng.choice(table) for _ in range(rng.randrange(1, 17))]
        expected = float(sum((Fraction.from_float(value) for value in values), Fraction()))
        expected_bits = struct.pack('>d', expected)
        for _ in range(6):
            rng.shuffle(values)
            actual_bits = struct.pack('>d', sum(values))
            if actual_bits != expected_bits:
                raise AssertionError((values, expected_bits.hex(), actual_bits.hex()))
            digest.update(actual_bits)
            evaluations += 1
    for table in ([float('nan')], [float('inf')], [-1.0], [1], [1e308], [1.0, 1e-300], [0.0]*4097):
        if certify(table):
            raise AssertionError(('unexpected certificate', table[:3]))
    assert accepted and evaluations
    report = {'status': 'complete', 'accepted_tables': accepted, 'rejected_random_tables': rejected,
              'production_certificate': args.production,
              'native_certificate': args.native_certificate,
              'permutations': evaluations, 'native_sum_equals_exact_rational_rounding': True,
              'signed_zero_subnormal_and_overflow_boundaries_included': True,
              'observations_sha256': digest.hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
