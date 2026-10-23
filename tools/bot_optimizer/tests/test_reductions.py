"""Semantic fallbacks and callback order for short reduction fusion."""

import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
def run(rows, route):
    a = sum(rows[i].a for i in route)
    b = sum(rows[i].b for i in route)
    c = sum(rows[i].c for i in route)
    return a, b, c
'''


class ShortReductionTests(unittest.TestCase):
    def namespaces(self, source=SOURCE):
        result = optimize_source(source)
        self.assertIn('short-int-reductions', [c.pass_name for c in result.changes])
        return execute(source), execute(result.source)

    def test_exact_values_bounds_sizes_and_float_fallback(self):
        old, new = self.namespaces()
        for size in (0, 1, 4, 5, 8, 9, 32):
            for values in ((1, 2, 3), (2**100, -2**120, 9), (1e30, -1e30, 0.1), (True, False, 4)):
                for container in (list, tuple):
                    observations = []
                    for ns in (old, new):
                        rows = container(ns['Row'](*values) for _ in range(size))
                        observations.append(ns['run'](rows, tuple(range(size))))
                    self.assertEqual(observations[0], observations[1])
        for ns in (old, new):
            rows = [ns['Row'](1, 2, 3), ns['Row'](4, 5, 6)]
            self.assertEqual(ns['run'](rows, (-1, -2)), (5, 7, 9))
            for route in ((2,), (-3,)):
                with self.assertRaises(IndexError):
                    ns['run'](rows, route)
            object.__delattr__(rows[0], 'b')
            with self.assertRaises(AttributeError):
                ns['run'](rows, (0,))

    def test_unsupported_callbacks_keep_original_order(self):
        observations = []
        for ns in self.namespaces():
            events = []
            class Row(ns['Row']):
                def __getattribute__(self, key):
                    events.append(('attribute', key))
                    return super().__getattribute__(key)
            class Rows(list):
                def __getitem__(self, index):
                    events.append(('index', index))
                    return super().__getitem__(index)
            class Index:
                def __index__(self):
                    events.append('convert')
                    return 0
            rows = Rows([Row(1, 2, 3), Row(4, 5, 6)])
            values = ns['run'](rows, (1, 0))
            indexed = ns['run']([ns['Row'](7, 8, 9)], (Index(),))
            iterated = ns['run'](rows, iter((0, 1)))
            observations.append((values, indexed, iterated, events))
        self.assertEqual(*observations)

    def test_failed_later_guard_releases_references_before_fallback(self):
        observations = []
        for ns in self.namespaces():
            events = []
            rows = [ns['Row'](1, 2, 3)]
            class Value:
                def __radd__(self, other):
                    events.append('add')
                    rows.clear()
                    return other + 7
                def __del__(self):
                    events.append('del')
            rows.append(ns['Row'](Value(), 8, 9))
            try:
                ns['run'](rows, (0, 1))
            except IndexError:
                events.append('caught')
            observations.append(events)
        self.assertEqual(*observations)

    def test_fresh_locals_and_unsupported_patterns(self):
        sources = [
            SOURCE.replace('def run(rows, route):', 'def run[sum](rows, route):'),
            SOURCE.replace('def run(rows, route):', 'def run(rows, route, a=0):'),
            SOURCE.replace('    a = sum', '    a = 0\n    a = sum'),
            SOURCE.replace('def run(rows, route):', 'def run(rows, route, sum=sum):'),
            SOURCE.replace('for i in route)', 'for i in route if i)'),
            SOURCE.replace('    a = sum', '    object.__setattr__(rows[0], "a", 3)\n    a = sum'),
            SOURCE.replace('    a = sum', '    def capture():\n        return a\n    a = sum'),
            SOURCE.replace('for i in route)', 'for rows in route)'),
            SOURCE.replace('    a = sum', '    try:\n        raise ValueError()\n    except ValueError as rows:\n        pass\n    a = sum'),
        ]
        for source in sources:
            self.assertNotIn('short-int-reductions', [c.pass_name for c in optimize_source(source).changes])
        result = optimize_source(SOURCE, Options(disabled=frozenset({'short-int-reductions'})))
        self.assertNotIn('short-int-reductions', [c.pass_name for c in result.changes])


if __name__ == '__main__':
    unittest.main()
