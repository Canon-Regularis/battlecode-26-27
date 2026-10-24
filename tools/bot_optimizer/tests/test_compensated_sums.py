import ast
from fractions import Fraction
import itertools
import math
import random
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.compensated_sums import CERTIFICATE, CompensatedSums
from tools.bot_optimizer.tests.test_insertion_keys import PRODUCER, CONSUMER
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE, normalized
from tools.bot_optimizer.tests.test_regions import CALLER
from tools.bot_optimizer.tests.test_specialization import execute


def certificate():
    namespace = {}
    exec(CERTIFICATE, namespace)
    return namespace['certify']


class CompensatedSumTests(unittest.TestCase):
    def test_certificate_boundaries_and_runtime_version(self):
        certify = certificate()
        for values in ([], [0.0, -0.0], [math.ulp(0.0), 2*math.ulp(0.0)],
                       [1.0, 2.0**-79], [0.0]*4096):
            self.assertTrue(certify(values), values[:3])
        for values in (None, [1.0, 2.0**-80], [1.0, 1e-300], [1e308], [float('inf')],
                       [float('nan')], [-1.0], [1], [True], [0.0]*4097):
            self.assertFalse(certify(values))
        with patch.object(sys, 'version_info', (3, 12, 9)):
            self.assertFalse(certify([1.0]))
        with patch.object(sys, 'implementation', SimpleNamespace(name='other')):
            self.assertFalse(certify([1.0]))

    def test_certified_permutations_round_exactly_with_native_correction(self):
        certify = certificate()
        tables = [[1e16, 1.0, 1.0], [0.0, -0.0], [math.ulp(0.0), 2*math.ulp(0.0)],
                  [1.0, 2**-79, 2**-79]]
        rng = random.Random(1368)
        for _ in range(100):
            exponent = rng.randrange(-1050, 0)
            tables.append([math.ldexp(rng.random(), exponent+rng.randrange(25)) for _ in range(5)])
        for table in tables:
            self.assertTrue(certify(table))
            expected = struct.pack('>d', float(sum(map(Fraction.from_float, table), Fraction())))
            for values in itertools.permutations(table):
                self.assertEqual(expected, struct.pack('>d', sum(values)))
        self.assertEqual(sum(tables[0]), 1e16+2.0)

    def source(self, consumer=CONSUMER):
        extra = '''        weights=self.weights
        if weights is not None:
            score += sum(weights.values[i] / self.items[i].duration for i in route)
'''
        return PRODUCER+SOURCE.replace('        return Result(red,blue,duration,peak,score)',
            extra+'        return Result(red,blue,duration,peak,score)')+consumer+CALLER

    def compare(self, source, weights, durations=(1, 1), limit=2, disabled=()):
        compiled = optimize_source(source, Options(disabled=frozenset(disabled)))
        values = []
        for text in (source, compiled.source):
            ns = execute(text)
            items = [ns['Item'](2, 3, durations[0], 7), ns['Item'](11, 13, durations[1], 19)]
            try:
                rows = ns['run'](items, [[2, 3], [5, 7]], ns['Weights'](weights), limit)
                values.append([normalized(row) for row in rows])
            except Exception as error:
                values.append((type(error).__name__, str(error)))
        self.assertEqual(*values)
        return compiled

    def test_native_sum_fallbacks_duplicates_and_negative_indices(self):
        for weights in ((1e16, 1.0), (0.0, -0.0), (1.0, -1.0), (float('inf'), 1.0),
                        (math.ulp(0.0), 2*math.ulp(0.0)), (1.0, 2**-80)):
            compiled = self.compare(self.source(), weights)
            self.assertTrue(any(c.pass_name == 'insertion-compensated-sums' for c in compiled.changes))
        self.compare(self.source(), (1.0, 2.0), limit=3)
        self.compare(self.source(), (1.0, 2.0), durations=(1, 0))
        self.compare(self.source(), (1.0,), limit=2)
        # Original error/failure path must survive failed table preparation.
        source = self.source().replace('range(-1, count)', 'range(count)')
        self.compare(source, (1.0, 2.0), durations=(1, 0), limit=1)

    def test_long_routes_and_missing_contracts(self):
        consumer = CONSUMER.replace('tuple([0, 0])', 'tuple(['+','.join(['0']*16)+'])')
        compiled = self.compare(self.source(consumer), (1.0, 2.0))
        self.assertTrue(any(c.pass_name == 'insertion-compensated-sums' for c in compiled.changes))
        for disabled in ('insertion-compensated-sums', 'numeric-prepared-versions',
                         'numeric-native-projection', 'insertion-invariant-keys'):
            compiled = self.compare(self.source(), (1.0, 2.0), disabled=(disabled,))
            self.assertFalse(any(c.pass_name == 'insertion-compensated-sums' for c in compiled.changes))
        tree = ast.parse(self.source())
        before = ast.dump(tree)
        self.assertEqual(before, ast.dump(CompensatedSums(Options()).apply(tree)))

    def test_actual_cache_hits_and_length_fallback(self):
        for width, weights, expected in ((2, (1e16, 1.0), 3), (2, (1.0, -1.0), 9),
                                         (16, (1.0, 2.0), 51)):
            consumer = CONSUMER.replace('tuple([0, 0])', 'tuple(['+','.join(['0']*width)+'])')
            compiled = optimize_source(self.source(consumer))
            tree = ast.parse(compiled.source)
            sites = 0
            for node in ast.walk(tree):
                if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id.startswith('_bcopt_compensated_value')
                        and isinstance(node.value, ast.Call)):
                    node.value.func = ast.Name(id='_observe_native_sum', ctx=ast.Load())
                    sites += 1
            self.assertEqual(sites, 2)
            ns = execute(ast.unparse(ast.fix_missing_locations(tree)))
            calls = []
            def observe(values):
                calls.append(1)
                return sum(values)
            ns['_observe_native_sum'] = observe
            items = [ns['Item'](2, 3, 1, 7), ns['Item'](11, 13, 1, 19)]
            ns['run'](items, [[2, 3], [5, 7]], ns['Weights'](weights), 2)
            self.assertEqual(len(calls), expected)


if __name__ == '__main__':
    unittest.main()
