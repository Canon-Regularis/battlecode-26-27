import ast
import unittest

from tools.bot_optimizer.compiler import optimize_source
from tools.bot_optimizer.tests.test_consumer_regions import CONSUMER
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE, normalized
from tools.bot_optimizer.tests.test_specialization import execute


CALLER = '''
REMAINING=1
def mutate():
    pass
def stop():
    if REMAINING > 0:
        return False
    mutate()
    return True
def run(items,matrix,weights,limit):
    engine=Engine(items,matrix,weights)
    return engine.search(stop=stop,limit=limit)
'''


def normalized_result(value):
    return [normalized(item) for item in value]


class RegionIntegrationTests(unittest.TestCase):
    def compile(self, consumer=CONSUMER, evaluator=SOURCE):
        source = evaluator+consumer+CALLER
        result = optimize_source(source)
        changes = [change for change in result.changes if change.pass_name == 'numeric-consumer-regions']
        self.assertEqual(len(changes), 2)
        return execute(source), execute(result.source), result.source

    def inputs(self, ns):
        return [ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)], [[2, 3], [5, 7]], ns['Weights']((0.1, 0.9))

    def test_pipeline_derives_and_executes_guarded_consumer(self):
        original, optimized, emitted = self.compile()
        self.assertIn('_bcopt_region_consumer_', emitted)
        values = [normalized_result(ns['run'](*self.inputs(ns), 2)) for ns in (original, optimized)]
        self.assertEqual(*values)
        tree = ast.parse(emitted)
        fast = [node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith('_bcopt_region_numeric_')]
        events = []
        for name in fast:
            original_fast = optimized[name]
            def observed(*args, _function=original_fast, **kwargs):
                events.append(_function.__name__)
                return _function(*args, **kwargs)
            optimized[name] = observed
        optimized['run'](*self.inputs(optimized), 2)
        self.assertGreaterEqual(len(events), 2)

    def test_dirty_true_exit_invalidates_before_later_evaluation(self):
        original, optimized, _ = self.compile(CONSUMER.replace('                break', '                pass'))
        values = []
        for ns in (original, optimized):
            args = self.inputs(ns)
            ns['REMAINING'] = 0
            calls = []
            def mutate():
                calls.append('mutate')
                args[0][0] = ns['Item'](101, 3, 5, 7)
            ns['mutate'] = mutate
            values.append((normalized_result(ns['run'](*args, 2)), calls))
        self.assertEqual(*values)

    def test_subclass_and_method_overrides_use_original_consumer(self):
        original, optimized, _ = self.compile()
        values = []
        for ns in (original, optimized):
            base = ns['Engine']
            class Custom(base):
                def search(self, **kwargs):
                    return ['custom', kwargs['limit']]
            ns['Engine'] = Custom
            values.append(ns['run'](*self.inputs(ns), 2))
        self.assertEqual(*values)

    def test_invalid_bounds_keep_original_exception(self):
        original, optimized, _ = self.compile()
        values = []
        for ns in (original, optimized):
            try:
                ns['run'](*self.inputs(ns), 3)
            except Exception as error:
                values.append((type(error).__name__, str(error)))
        self.assertEqual(values, [('IndexError', 'list index out of range')]*2)

    def test_integer_reduction_cache_preserves_multisets_and_epochs(self):
        _, optimized, emitted = self.compile()
        tree = ast.parse(emitted)
        enter, = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name.startswith('_bcopt_region_enter_')]
        numeric, = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name.startswith('_bcopt_region_numeric_') and len(node.body) == 1
                    and isinstance(node.body[0], ast.Try)]
        inputs = self.inputs(optimized)
        owner = optimized['Engine'](*inputs)
        state = optimized[enter](owner.search)
        data, _ = state
        cache, = [value for value in data if type(value) is dict]
        fast = optimized[numeric]
        for route in ((0, 1), (1, 0), (0, 0), (-1, 0), (0, -1)):
            self.assertEqual(normalized(owner.evaluate(route, 0)), normalized(fast(data, route, 0)))
        self.assertEqual(set(cache), {(0, 1), (0, 0), (-1, 0)})
        self.assertNotEqual(cache[(0, 1)], cache[(0, 0)])
        inputs[0][0] = optimized['Item'](101, 3, 5, 7)
        next_data, _ = optimized[enter](owner.search)
        next_cache, = [value for value in next_data if type(value) is dict]
        self.assertEqual(next_cache, {})
        self.assertIsNot(cache, next_cache)
        self.assertEqual(normalized(owner.evaluate((0, 1), 0)), normalized(fast(next_data, (0, 1), 0)))
        self.assertNotEqual(cache[(0, 1)], next_cache[(0, 1)])

    def test_unknown_callback_and_custom_truth_keep_effect_order(self):
        original, optimized, _ = self.compile()
        values = []
        for ns in (original, optimized):
            args, events = self.inputs(ns), []
            class Truth:
                def __bool__(self):
                    events.append('truth')
                    args[0][0] = ns['Item'](103, 3, 5, 7)
                    return False
            def stop():
                events.append('stop')
                return Truth()
            ns['stop'] = stop
            values.append((normalized_result(ns['run'](*args, 2)), events))
        self.assertEqual(*values)

    def test_native_index_retry_restores_skipped_short_circuit_access(self):
        evaluator = SOURCE.replace('        items=self.items',
            '        if any(self.matrix[selector][i] < 0 for i in route):\n            return None\n        items=self.items')
        consumer = CONSUMER.replace('route=(index,)', 'route=tuple(range(2))')
        original, optimized, emitted = self.compile(consumer, evaluator)
        self.assertIn('except _bcopt_region_index_error_', emitted)
        values = []
        for ns in (original, optimized):
            items, _, weights = self.inputs(ns)
            values.append(ns['run'](items, [[-1]], weights, 1))
        self.assertEqual(values, [[], []])

    def test_derived_edge_table_and_inline_retry_keep_error_order(self):
        evaluator = SOURCE.replace('value=self.matrix[selector][route[0]]', 'value=1').replace(
            'score=self.weighted(route)+ratio+value', 'weighted=self.weighted(route)\n        score=weighted+ratio+value').replace(
            'return sum(self.items[i].duration*weights.values[i] for i in route)',
            'total=0.0\n        for i in route:\n'
            '            pair=weights.values[i]+weights.values[i]\n'
            '            total+=self.matrix[i][i]*pair/2\n        return total')
        original, optimized, emitted = self.compile(evaluator=evaluator)
        helpers = [node for node in ast.parse(emitted).body if isinstance(node, ast.FunctionDef)
                   and node.name.startswith('_bcopt_region_derive_')]
        self.assertTrue(any(isinstance(node, ast.Div) for helper in helpers for node in ast.walk(helper)))
        values = [normalized_result(ns['run'](*self.inputs(ns), 2)) for ns in (original, optimized)]
        self.assertEqual(*values)
        errors = []
        for ns in (original, optimized):
            items, _, _ = self.inputs(ns)
            try:
                ns['run'](items, [], ns['Weights'](()), 1)
            except Exception as error:
                errors.append((type(error).__name__, str(error)))
        self.assertEqual(errors, [('IndexError', 'tuple index out of range')]*2)

    def test_later_record_definition_does_not_move_lookup_earlier(self):
        tree = ast.parse(SOURCE+CONSUMER+CALLER)
        result = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Result')
        tree.body.remove(result)
        tree.body.append(result)
        source = 'from __future__ import annotations\n'+ast.unparse(tree)
        compiled = optimize_source(source)
        self.assertFalse(any(change.pass_name == 'numeric-consumer-regions' for change in compiled.changes))
        original, optimized = execute(source), execute(compiled.source)
        values = [normalized_result(ns['run'](*self.inputs(ns), 2)) for ns in (original, optimized)]
        self.assertEqual(*values)

    def test_callsite_does_not_retain_new_arbitrary_argument_temporaries(self):
        source = SOURCE+CONSUMER+CALLER.replace('stop=stop,limit=limit)', 'stop=stop,limit=make_limit())')
        source += '\ndef make_limit():\n    return 2\n'
        compiled = optimize_source(source)
        self.assertFalse(any(change.pass_name == 'numeric-consumer-regions' for change in compiled.changes))
        original, optimized = execute(source), execute(compiled.source)
        values = [normalized_result(ns['run'](*self.inputs(ns), 2)) for ns in (original, optimized)]
        self.assertEqual(*values)


if __name__ == '__main__':
    unittest.main()
