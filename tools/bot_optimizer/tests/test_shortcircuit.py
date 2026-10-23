"""Guarded short-circuit loops: protocols, PEP 479, cleanup and mutation."""

import gc
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


class ShortCircuitTests(unittest.TestCase):
    def functions(self, consumer='any', predicate='item < 0'):
        source = f'def run(items):\n    return {consumer}({predicate} for item in items)\n'
        result = optimize_source(source)
        self.assertIn('short-circuit-loop', [c.pass_name for c in result.changes])
        return execute(source)['run'], execute(result.source)['run']

    def test_values_and_operators(self):
        for consumer in ('any', 'all'):
            for predicate in ('item < 0', 'item <= -1', 'item == 0', 'item != 0', 'item > 2', 'item >= 3'):
                old, new = self.functions(consumer, predicate)
                for values in ([], [1], [-1], [0, 1, -1], [0.0, float('nan'), -0.1]):
                    for constructor in (list, tuple):
                        self.assertEqual(old(constructor(values)), new(constructor(values)))

    def test_custom_iterator_calls_and_errors_are_preserved(self):
        for consumer in ('any', 'all'):
            old, new = self.functions(consumer)
            for failure in (None, 'first-iter', 'later-iter', 'next'):
                observations = []
                for function in (old, new):
                    events = []
                    class Items:
                        def __init__(self):
                            self.lookups = self.index = 0
                        def __iter__(self):
                            self.lookups += 1
                            events.append('iter')
                            if failure == 'first-iter' or failure == 'later-iter' and self.lookups > 1:
                                raise StopIteration('iter')
                            return self
                        def __next__(self):
                            events.append('next')
                            self.index += 1
                            if failure == 'next':
                                raise ValueError('next')
                            if self.index > 2:
                                raise StopIteration
                            return 1
                    try:
                        events.append(function(Items()))
                    except BaseException as error:
                        events.append((type(error).__name__, str(error), type(error.__cause__).__name__))
                    observations.append(events)
                self.assertEqual(*observations)

    def observe_lifetime(self, function, mode):
        events, items = [], []
        class Value:
            def __bool__(self):
                events.append('bool')
                if mode == 'bool-stop':
                    raise StopIteration('bool')
                if mode == 'bool-error':
                    raise ValueError('bool')
                return mode == 'true'
            def __del__(self):
                events.append('value-del')
        class Item:
            def __init__(self, index):
                self.index = index
            def __lt__(self, other):
                events.append(('compare', self.index))
                items.clear()
                if mode == 'compare-stop':
                    raise StopIteration('compare')
                if mode == 'compare-error':
                    raise ValueError('compare')
                return Value()
            def __del__(self):
                events.append(('item-del', self.index))
        items.extend(Item(i) for i in range(3))
        try:
            events.append(('result', function(items)))
        except BaseException as error:
            events.append(('error', type(error).__name__, str(error), type(error.__cause__).__name__))
        events.append('caught')
        gc.collect()
        events.append('collected')
        return events

    def test_result_and_item_cleanup_on_mutation_and_exceptions(self):
        for consumer in ('any', 'all'):
            old, new = self.functions(consumer)
            for mode in ('true', 'false', 'bool-stop', 'bool-error', 'compare-stop', 'compare-error'):
                with self.subTest(consumer=consumer, mode=mode):
                    self.assertEqual(self.observe_lifetime(old, mode), self.observe_lifetime(new, mode))

    def test_unsupported_scope_and_predicates(self):
        sources = [
            'def run(items, any):\n    return any(item < 0 for item in items)',
            'def run(items):\n    return any(item < 0 for item in items if item)',
            'def run(items, limit):\n    return any(item < limit for item in items)',
            'def run(items):\n    return any(item < 0 for item in iter(items))',
            'def run(items):\n    return any(item < 0 for item in GLOBAL)',
            'def run(items, calls):\n    return [any(item < 0 for item in items) for any in calls]',
            'items = []\ndef run(items, result=any(item < 0 for item in items)):\n    return result',
            'def run(items):\n    def mutate():\n        nonlocal items\n        items=[]\n    return any(item < 0 for item in items)',
            'class Owner[any]:\n    def run(self, items):\n        return any(item < 0 for item in items)',
        ]
        for source in sources:
            self.assertNotIn('short-circuit-loop', [c.pass_name for c in optimize_source(source).changes])
        result = optimize_source('def run(items):\n    return any(item < 0 for item in items)',
                                 Options(disabled=frozenset({'short-circuit-loop'})))
        self.assertNotIn('short-circuit-loop', [c.pass_name for c in result.changes])


if __name__ == '__main__':
    unittest.main()
