"""Direct indexed extrema: stable ties, protocols, errors and reference cleanup."""

import gc
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''def run(rows, route):
    return max(rows[i][0] + rows[i][1] for i in route)
'''


class ExtremumLoopTests(unittest.TestCase):
    def functions(self, consumer='max', source=SOURCE):
        source = source.replace('max(', consumer + '(')
        result = optimize_source(source)
        self.assertIn('extremum-loop', [c.pass_name for c in result.changes])
        return execute(source)['run'], execute(result.source)['run']

    def test_numeric_values_and_empty(self):
        for consumer in ('min', 'max'):
            old, new = self.functions(consumer)
            for rows in ([(1, 2), (4, 5)], [(1e30, 0), (1e-30, 0)], [(float('nan'), 0), (1., 0)],
                         [(1., 0), (float('nan'), 0)], [(2**120, 0), (-(2**120), 0)]):
                for constructor in (tuple, list):
                    self.assertEqual(repr(old(rows, constructor((0, 1)))), repr(new(rows, constructor((0, 1)))))
            for function in (old, new):
                with self.assertRaisesRegex(ValueError, 'empty'):
                    function([], ())

    def test_ties_keep_first_object(self):
        source = 'def run(rows, route):\n    return max(rows[i] for i in route)\n'
        class Value:
            def __lt__(self, other):
                return False
            def __gt__(self, other):
                return False
        values = [Value(), Value()]
        for consumer in ('min', 'max'):
            for function in self.functions(consumer, source):
                self.assertIs(function(values, (0, 1)), values[0])

    def lifecycle(self, function, mode):
        events = []
        class Truth:
            def __bool__(self):
                events.append('bool')
                if mode == 'bool-stop':
                    raise StopIteration('bool')
                if mode == 'bool-error':
                    raise ValueError('bool')
                return mode == 'replace'
            def __del__(self):
                events.append('truth-del')
        class Value:
            def __init__(self, index):
                self.index = index
            def compare(self, other, operation):
                events.append((operation, self.index, other.index))
                if mode == 'compare-stop':
                    raise StopIteration('comparison')
                if mode == 'compare-error':
                    raise ValueError('comparison')
                return Truth()
            def __lt__(self, other):
                return self.compare(other, 'lt')
            def __gt__(self, other):
                return self.compare(other, 'gt')
            def __del__(self):
                events.append(('value-del', self.index))
        class Payload:
            def __init__(self, index):
                self.index = index
            def __add__(self, other):
                events.append(('evaluate', self.index))
                if self.index == 1 and mode == 'expr-stop':
                    raise StopIteration('expression')
                if self.index == 1 and mode == 'expr-error':
                    raise ValueError('expression')
                return Value(self.index)
        rows, route = [(Payload(i), 0) for i in range(3)], (0, 1, 2)
        try:
            result = function(rows, route)
            events.append(('result', result.index))
            del result
        except BaseException as error:
            events.append(('error', type(error).__name__, str(error), type(error.__cause__).__name__))
        events.append('caught')
        gc.collect()
        events.append('collected')
        return events

    def test_expression_comparison_boolean_errors_and_finalizers(self):
        for consumer in ('min', 'max'):
            old, new = self.functions(consumer)
            for mode in ('keep', 'replace', 'compare-stop', 'compare-error', 'bool-stop',
                         'bool-error', 'expr-stop', 'expr-error'):
                with self.subTest(consumer=consumer, mode=mode):
                    self.assertEqual(self.lifecycle(old, mode), self.lifecycle(new, mode))

    def test_custom_iterator_and_mutable_rows(self):
        old, new = self.functions()
        observations = []
        for function in (old, new):
            events = []
            class Route:
                def __init__(self):
                    self.index = 0
                def __iter__(self):
                    events.append('iter')
                    return self
                def __next__(self):
                    events.append('next')
                    self.index += 1
                    if self.index > 2:
                        raise StopIteration
                    return self.index - 1
            class Rows(list):
                def __getitem__(self, index):
                    events.append(('read', index))
                    if index == 0:
                        self[1] = (8, 9)
                    return super().__getitem__(index)
            result = function(Rows([(1, 2), (3, 4)]), Route())
            direct = function(Rows([(1, 2), (3, 4)]), (0, 1))
            observations.append((result, direct, events))
        self.assertEqual(*observations)

    def test_unsupported_scopes_and_unbound_capture(self):
        sources = [
            SOURCE.replace('def run(rows, route):', 'def run(rows, route, max):'),
            SOURCE.replace('def run(rows, route):', 'def run(route):\n    if route:\n        rows = []'),
            SOURCE.replace('def run(rows, route):', 'def run(rows, route):\n    def mutate():\n        nonlocal rows\n        rows=[]'),
            SOURCE.replace('for i in route)', 'for i in route if i)'),
            SOURCE.replace('rows[i][0] + rows[i][1]', 'len(rows[i])'),
            'def run(rows, route):\n    return max((rows[i] for i in route), default=0)',
            'class Owner[max]:\n    def run(self, rows, route):\n        return max(rows[i] for i in route)',
        ]
        for source in sources:
            self.assertNotIn('extremum-loop', [c.pass_name for c in optimize_source(source).changes])
        result = optimize_source(SOURCE, Options(disabled=frozenset({'extremum-loop'})))
        self.assertNotIn('extremum-loop', [c.pass_name for c in result.changes])


if __name__ == '__main__':
    unittest.main()
