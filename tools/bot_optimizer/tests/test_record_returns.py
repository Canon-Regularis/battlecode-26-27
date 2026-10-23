"""Allocation timing, argument effects and shared-key history at inline returns."""

import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    a: object
    b: object
    c: object
    d: object
def make(a, b, c, d):
    return Row(a, b, c, d)
'''


class InlineReturnTests(unittest.TestCase):
    def namespaces(self, source=SOURCE):
        result = optimize_source(source)
        self.assertIn('record-inline-return', [c.pass_name for c in result.changes])
        return execute(source), execute(result.source)

    def test_exact_type_aliases_and_shared_key_finalizers(self):
        for order in ('abcd', 'dbac'):
            observations = []
            for ns in self.namespaces():
                seed = object.__new__(ns['Row'])
                for name in order:
                    object.__setattr__(seed, name, 0)
                del seed
                events = []
                class Item:
                    def __init__(self, label):
                        self.label = label
                    def __del__(self):
                        events.append(self.label)
                row = ns['make'](*(Item(name) for name in 'abcd'))
                self.assertIs(type(row), ns['Row'])
                self.assertEqual(tuple(row.__dict__), tuple('abcd'))
                del row
                observations.append(events)
            self.assertEqual(*observations)

    def test_single_effectful_argument_precedes_allocation(self):
        source = SOURCE.replace('return Row(a, b, c, d)', 'return Row(a, b * 2, c, d)')
        observations = []
        for ns in self.namespaces(source):
            events = []
            class Item:
                def __init__(self, label):
                    self.label = label
                def __del__(self):
                    events.append(self.label)
            class Product:
                def __mul__(self, other):
                    events.append(('multiply', other))
                    seed = object.__new__(ns['Row'])
                    for name in 'dbac':
                        object.__setattr__(seed, name, 0)
                    return Item('b')
            row = ns['make'](Item('a'), Product(), Item('c'), Item('d'))
            del row
            observations.append(events)
        self.assertEqual(*observations)
        self.assertEqual(observations[0], [('multiply', 2), 'd', 'b', 'a', 'c'])

    def test_rejected_first_record_still_initializes_shared_keys(self):
        observations = []
        for ns in self.namespaces():
            ns['make'](1, 2, 3, 4)
            seed = object.__new__(ns['Row'])
            for name in 'dbac':
                object.__setattr__(seed, name, 0)
            del seed
            events = []
            class Item:
                def __init__(self, label):
                    self.label = label
                def __del__(self):
                    events.append(self.label)
            row = ns['make'](*(Item(name) for name in 'abcd'))
            del row
            observations.append(events)
        self.assertEqual(observations, [list('abcd'), list('abcd')])

    def test_unsupported_lifetimes_and_bindings_fall_back(self):
        sources = [
            SOURCE.replace('Row(a, b, c, d)', 'Row(a(), b(), c, d)'),
            SOURCE.replace('def make(a, b, c, d):', 'def make(b, c, d):\n    if b:\n        a = 1'),
            SOURCE.replace('def make(a, b, c, d):', 'def make(a, b, c, d):\n    try:\n        raise ValueError()\n    except ValueError as a:\n        pass'),
            SOURCE.replace('def make(a, b, c, d):', 'def make(a, b, c, d, Row):'),
            SOURCE.replace('def make(a, b, c, d):', 'def make(a, b, c, d):\n    def mutate():\n        nonlocal a\n        a=3'),
            SOURCE.replace('Row(a, b, c, d)', 'Row(a, b, c, extra=d)'),
        ]
        for source in sources:
            self.assertNotIn('record-inline-return', [c.pass_name for c in optimize_source(source).changes])
        for disabled in ('record-inline-return', 'record-allocator-cache', 'record-call'):
            result = optimize_source(SOURCE, Options(disabled=frozenset({disabled})))
            self.assertNotIn('record-inline-return', [c.pass_name for c in result.changes])


if __name__ == '__main__':
    unittest.main()
