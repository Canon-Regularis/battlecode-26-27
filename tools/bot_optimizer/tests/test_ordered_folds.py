import ast
import struct
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.ordered_folds import OrderedFolds
from tools.bot_optimizer.tests.test_insertion_keys import PRODUCER, CONSUMER
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE
from tools.bot_optimizer.tests.test_regions import CALLER
from tools.bot_optimizer.tests.test_specialization import execute


class OrderedFoldTests(unittest.TestCase):
    def source(self, width=2, expression='self.matrix[begin][end] * weights.values[end]', after=''):
        extra = f'''        weights=self.weights
        if weights is not None:
            score=weights.values[route[0]] * 1.0
            for begin,end in zip(route,route[1:]):
                score += {expression}
{after}'''
        evaluator = SOURCE.replace('score=self.weighted(route)+ratio+value', 'score=0.0')
        evaluator = evaluator.replace('        return Result(red,blue,duration,peak,score)',
            extra+'        return Result(red,blue,duration,peak,score)')
        consumer = CONSUMER.replace('tuple([0, 0])', 'tuple(['+','.join(['0']*width)+'])')
        return PRODUCER+evaluator+consumer+CALLER

    def compare(self, source, matrix, weights=(1.0, 2.0), limit=2, disabled=()):
        compiled = optimize_source(source, Options(disabled=frozenset(disabled)))
        observations = []
        for text in (source, compiled.source):
            ns = execute(text)
            items = [ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)]
            try:
                rows = ns['run'](items, matrix, ns['Weights'](weights), limit)
                observations.append([(row.red, row.blue, struct.pack('>d', row.score)) for row in rows])
            except Exception as error:
                observations.append((type(error).__name__, str(error)))
        self.assertEqual(*observations)
        return compiled

    def test_short_and_long_routes_preserve_bitwise_addition_order(self):
        nan = struct.unpack('>d', bytes.fromhex('7ff8000000000123'))[0]
        for width in (0, 1, 2, 11, 12):
            source = self.source(width)
            for weights in ((1e16, 1.0), (1.0, -1.0), (-0.0, 0.0), (nan, -0.0),
                            (float('inf'), float('-inf')), (5e-324, 1e-323)):
                compiled = self.compare(source, [[1, -1], [1, 0]], weights)
                self.assertTrue(any(c.pass_name == 'numeric-ordered-folds' for c in compiled.changes))

    def test_loop_targets_and_exception_fallbacks(self):
        source = self.source(after='            score += begin + end\n')
        self.compare(source, [[1, 2], [3, 4]])
        for matrix in ([[1], [3, 4]], [[10**400, 2], [3, 4]]):
            self.compare(self.source(), matrix)
        self.compare(self.source(), [[1, 2], [3, 4]], limit=3)
        division = self.source(expression='weights.values[end] / self.matrix[begin][end]')
        self.compare(division, [[1, 2], [3, 0]])  # skipped failure still takes original prepared fallback
        self.compare(division, [[0, 2], [3, 4]])

    def test_missing_contracts_and_disabled_passes(self):
        for disabled in ('numeric-ordered-folds', 'numeric-prepared-versions', 'tuple-adjacent-iterator'):
            compiled = self.compare(self.source(), [[1, 2], [3, 4]], disabled=(disabled,))
            self.assertFalse(any(c.pass_name == 'numeric-ordered-folds' for c in compiled.changes))
        tree = ast.parse(self.source())
        before = ast.dump(tree)
        self.assertEqual(before, ast.dump(OrderedFolds(Options()).apply(tree)))


if __name__ == '__main__':
    unittest.main()
