import ast
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.group_scalars import GroupScalars
from tools.bot_optimizer.tests.test_insertion_keys import PRODUCER, CONSUMER
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE, normalized
from tools.bot_optimizer.tests.test_regions import CALLER
from tools.bot_optimizer.tests.test_specialization import execute


class GroupScalarTests(unittest.TestCase):
    def source(self, consumer=CONSUMER, reward='red + self.matrix[0][0] * blue'):
        evaluator = SOURCE.replace('        ratio=red/(selector+1)',
            '        rounded=ceil(red/10)\n        ratio=red/(selector+1)')
        evaluator = evaluator.replace('        score=self.weighted(route)+ratio+value',
            f'        reward={reward}\n        score=self.weighted(route)+ratio+value+reward+rounded')
        return 'from math import ceil\n'+PRODUCER+evaluator+consumer+CALLER

    def compare(self, source, *, limit=2, red=2, matrix=None, disabled=()):
        compiled = optimize_source(source, Options(disabled=frozenset(disabled)))
        values = []
        for text in (source, compiled.source):
            ns = execute(text)
            items = [ns['Item'](red, 3, 5, 7), ns['Item'](11, 13, 17, 19)]
            try:
                rows = ns['run'](items, [[2, 3], [5, 7]] if matrix is None else matrix,
                                 ns['Weights']((0.1, 0.9)), limit)
                values.append([normalized(row) for row in rows])
            except Exception as error:
                values.append((type(error).__name__, str(error)))
        self.assertEqual(*values)
        return compiled

    def test_generic_scalar_dependence_and_changing_call_arguments(self):
        consumer = CONSUMER.replace('value=evaluate(route, 0)', 'selection=index % 2\n            value=evaluate(route, selection)')
        compiled = self.compare(self.source(consumer))
        self.assertTrue(any(c.pass_name == 'insertion-group-scalars' for c in compiled.changes))
        self.compare(self.source(), limit=3)
        self.compare(self.source(), red=-13)
        self.compare(self.source(), red=10**400)
        self.compare(self.source(), matrix=[[2], [5, 7]])
        self.compare(self.source(reward='red * 0.1'))
        self.compare(self.source(reward='(red * 1e309) - (blue * 1e309)'))

    def test_original_exception_points_and_failed_cache_publication(self):
        # Variant division must run before the later invariant division error.
        consumer = CONSUMER.replace('value=evaluate(route, 0)', 'selection=-1\n            value=evaluate(route, selection)')
        compiled = self.compare(self.source(consumer, reward='1.0 / (red-red)'))
        self.assertTrue(any(c.pass_name == 'insertion-group-scalars' for c in compiled.changes))
        self.compare(self.source(reward='1.0 / (red-red)'))
        # A later varying error still occurs after a successful group cache fill.
        consumer = CONSUMER.replace('value=evaluate(route, 0)', 'selection=-(index % 2)\n            value=evaluate(route, selection)')
        self.compare(self.source(consumer))

    def test_actual_group_hits_and_missing_contracts(self):
        compiled = optimize_source(self.source())
        tree = ast.parse(compiled.source)
        caches = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id.startswith('_bcopt_group_scalar_state')):
                self.assertTrue(isinstance(node.value, ast.Subscript)
                                or isinstance(node.value, ast.Name) and node.value.id.startswith('_bcopt_cache_slot_'))
                caches.append(node)
                node.value = ast.Call(func=ast.Name(id='_observe_group', ctx=ast.Load()), args=[node.value], keywords=[])
        self.assertTrue(caches)
        ns = execute(ast.unparse(ast.fix_missing_locations(tree)))
        calls = []
        def observe(value):
            calls.append(value is not None)
            return value
        ns['_observe_group'] = observe
        items = [ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)]
        ns['run'](items, [[2, 3], [5, 7]], ns['Weights']((0.1, 0.9)), 2)
        self.assertEqual((len(calls), sum(calls)), (9, 6))
        for disabled in ('insertion-group-scalars', 'numeric-reduction-memo', 'insertion-invariant-keys'):
            compiled = self.compare(self.source(), disabled=(disabled,))
            self.assertFalse(any(c.pass_name == 'insertion-group-scalars' for c in compiled.changes))
        tree = ast.parse(self.source())
        before = ast.dump(tree)
        self.assertEqual(before, ast.dump(GroupScalars(Options()).apply(tree)))


if __name__ == '__main__':
    unittest.main()
