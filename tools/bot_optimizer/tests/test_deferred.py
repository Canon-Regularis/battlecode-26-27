"""Regression witnesses that prevent accepting the deferred-record prototype."""

import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
    d: int
@dataclass(frozen=True)
class Kept:
    index: object
    value: object
class Engine:
    def __init__(self, output):
        self.output = output
    def make(self, values):
        if values is None:
            return None
        a, b, c, d = values
        return Row(a, b, c, d)
    def choose(self, data, threshold):
        produce = self.make
        kept = self.output
        for index, values in enumerate(data):
            row = produce(values)
            if row is None:
                continue
            if row.a > threshold:
                kept[index] = Kept(index, row)
        return kept
'''


class DeferredTests(unittest.TestCase):
    def namespaces(self, source=SOURCE):
        result = optimize_source(source)
        self.assertNotIn('deferred-record', [c.pass_name for c in result.changes])
        return execute(source), execute(result.source)

    def test_exact_records_public_producer_and_none_path(self):
        for ns in self.namespaces():
            engine = ns['Engine']({})
            self.assertIs(type(engine.make((1, 2, 3, 4))), ns['Row'])
            result = engine.choose([None, (2, 3, 4, 5), (-1, 2, 3, 4)], 0)
            self.assertEqual(list(result), [1])
            self.assertIs(type(result[1]), ns['Kept'])
            self.assertIs(type(result[1].value), ns['Row'])
            self.assertEqual(result[1].value.b, 3)

    def test_overridden_and_instance_supplied_callables_use_fallback(self):
        for ns in self.namespaces():
            Row, Base = ns['Row'], ns['Engine']
            class Child(Base):
                def make(self, values):
                    return Row(values[0] + 10, *values[1:])
            result = Child({}).choose([(1, 2, 3, 4)], 5)
            self.assertEqual(result[0].value.a, 11)
            engine = Base({})
            engine.make = lambda values: Row(20, *values[1:])
            self.assertEqual(engine.choose([(1, 2, 3, 4)], 5)[0].value.a, 20)
            events = []
            class Property(Base):
                @property
                def make(self):
                    events.append('lookup')
                    return lambda values: Row(30, *values[1:])
            self.assertEqual(Property({}).choose([(1, 2, 3, 4)], 5)[0].value.a, 30)
            self.assertEqual(events, ['lookup'])

    def lifecycle(self, ns, *, retain, mutate=False, fail=False):
        events = []
        class Item:
            def __init__(self, label):
                self.label = label
            def __gt__(self, other):
                events.append(('compare', self.label))
                if fail and self.label == '1a':
                    raise ValueError('comparison failed')
                return retain
            def __del__(self):
                events.append(('del', self.label))
        class Output(dict):
            def __setitem__(self, key, value):
                events.append(('store', key))
                if mutate:
                    object.__setattr__(value.value, 'b', Item(f'{key}replacement'))
                super().__setitem__(key, value)
        def data():
            for i in range(3):
                yield tuple(Item(f'{i}{field}') for field in 'abcd')
        output = Output()
        engine = ns['Engine'](output)
        try:
            engine.choose(data(), 0)
        except ValueError:
            events.append('caught')
        del engine
        output.clear()
        return events

    def test_field_finalizers_rejection_retention_mutation_and_exception(self):
        old, new = self.namespaces()
        for retain, mutate, fail in ((False, False, False), (True, False, False),
                                     (True, True, False), (False, False, True)):
            with self.subTest(retain=retain, mutate=mutate, fail=fail):
                self.assertEqual(self.lifecycle(old, retain=retain, mutate=mutate, fail=fail),
                                 self.lifecycle(new, retain=retain, mutate=mutate, fail=fail))

    def test_shared_key_order_and_custom_metaclass_payload_fall_back(self):
        old, new = self.namespaces()
        for ns in (old, new):
            seed = object.__new__(ns['Row'])
            for field in ('d', 'b', 'a', 'c'):
                object.__setattr__(seed, field, 0)
            del seed
        self.assertEqual(self.lifecycle(old, retain=False), self.lifecycle(new, retain=False))
        for ns in (old, new):
            events = []
            class Meta(type):
                def __eq__(cls, other):
                    events.append('type comparison')
                    return False
                def __hash__(cls):
                    events.append('type hashing')
                    return 1
            class Value(metaclass=Meta):
                def __gt__(self, other):
                    return False
            ns['Engine']({}).choose([(Value(), 2, 3, 4)], 0)
            self.assertEqual(events, [])

    def test_primitive_rejections_preserve_future_shared_key_history(self):
        observations = []
        for ns in self.namespaces():
            events = []
            class Item:
                def __init__(self, name):
                    self.name = name
                def __del__(self):
                    events.append(self.name)
            class Output(dict):
                def __setitem__(self, key, value):
                    for name in 'abcd':
                        object.__setattr__(value.value, name, Item(name))
                    super().__setitem__(key, value)
            def data():
                yield (-1, 2, 3, 4)
                seed = object.__new__(ns['Row'])
                for name in 'dbac':
                    object.__setattr__(seed, name, 0)
                del seed
                yield (1, 2, 3, 4)
            output = Output()
            engine = ns['Engine'](output)
            engine.choose(data(), 0)
            output.clear()
            observations.append(events)
        self.assertEqual(observations, [list('abcd'), list('abcd')])

    def test_one_effectful_argument_is_evaluated_once(self):
        source = SOURCE.replace('return Row(a, b, c, d)', 'return Row(a, b * 2, c, d)')
        for ns in self.namespaces(source):
            events = []
            class Product:
                def __mul__(self, value):
                    events.append(value)
                    return 17
            engine = ns['Engine']({})
            row = engine.choose([(1, Product(), 3, 4)], 0)[0].value
            self.assertEqual((row.b, events), (17, [2]))

    def test_unsupported_escapes_and_producers_remain_original(self):
        sources = [
            SOURCE.replace('a: int', 'a: object'),
            SOURCE.replace('def make(self, values):', 'def make(self, values, *, __unused):'),
            SOURCE.replace('return kept', 'return row'),
            SOURCE.replace('kept[index] = Kept(index, row)', 'kept[index] = Kept(index, row)\n                print(row.a)'),
            SOURCE.replace('return Row(a, b, c, d)', 'return Row(a + 1, b + 2, c, d)'),
            SOURCE.replace('return Row(a, b, c, d)', 'return Row(super().get(), b, c, d)'),
            SOURCE.replace('return Row(a, b, c, d)', 'return Row(a, b, c, d)\n    make = lambda self, values: None'),
            SOURCE.replace('if row.a > threshold:', 'if any(row.a > threshold for row in data):'),
            SOURCE.replace('a, b, c, d = values', 'try:\n            a, b, c, d = values\n        except ValueError as a:\n            pass'),
        ]
        for source in sources:
            self.assertNotIn('deferred-record', [c.pass_name for c in optimize_source(source).changes])
        self.assertNotIn('deferred-record', [c.pass_name for c in optimize_source(
            SOURCE, Options(disabled=frozenset({'deferred-record'}))).changes])


if __name__ == '__main__':
    unittest.main()
