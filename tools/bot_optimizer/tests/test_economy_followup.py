"""Regression risks for generic passes discovered using the recovered planner."""

import textwrap
import unittest
from pathlib import Path
import tempfile
import sys
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source, optimize_folder
from tools.bot_optimizer.tests.test_specialization import execute


class SmallRecordTests(unittest.TestCase):
    def test_large_factories_require_cached_allocator_and_measured_width(self):
        for width in (4, 8, 12, 20, 21):
            fields = [f'f{i}' for i in range(width)]
            source = ('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Row:\n'
                      + ''.join(f'    {name}: object\n' for name in fields)
                      + 'def run():\n    events=[]\n'
                      + '    def value(n):\n        events.append(n)\n        return n\n'
                      + '    row=Row(' + ', '.join(f'{name}=value({i})' for i, name in reversed(list(enumerate(fields))))
                      + ')\n    return row, events\n')
            result = optimize_source(source)
            self.assertEqual('record-call' in [c.pass_name for c in result.changes], width <= 20)
            old, new = execute(source)['run'](), execute(result.source)['run']()
            self.assertEqual((old[0].__dict__, old[1]), (new[0].__dict__, new[1]))
            for disabled in ('record-call', 'record-allocator-cache'):
                result = optimize_source(source, Options(disabled=frozenset({disabled})))
                self.assertNotIn('record-call', [c.pass_name for c in result.changes])

    def test_call_order_identity_freezing_and_finalizers(self):
        source = textwrap.dedent('''
            from dataclasses import dataclass, FrozenInstanceError
            @dataclass(frozen=True)
            class Pair:
                left: object
                right: object
            def run():
                events = []
                class Item:
                    def __init__(self, label):
                        self.label = label
                        events.append(label)
                    def __del__(self):
                        events.append('del-' + self.label)
                row = Pair(right=Item('right'), left=Item('left'))
                identity = type(row) is Pair
                try:
                    row.left = 3
                except FrozenInstanceError:
                    events.append('frozen')
                labels = row.left.label, row.right.label
                del row
                return identity, labels, events
        ''')
        result = optimize_source(source)
        self.assertIn('small-record-call', [c.pass_name for c in result.changes])
        self.assertEqual(execute(source)['run'](), execute(result.source)['run']())

    def test_public_constructor_and_subclass_descriptor_remain_original(self):
        source = textwrap.dedent('''
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Pair:
                a: object
                b: object
            def make(a, b):
                return Pair(a, b)
            class Child(Pair):
                @property
                def a(self):
                    return 7
        ''')
        result = optimize_source(source)
        old, new = execute(source), execute(result.source)
        for namespace in (old, new):
            row = namespace['make'](1, 2)
            self.assertIs(type(row), namespace['Pair'])
            namespace['Pair'].__init__(row, 3, 4)
            self.assertEqual((row.a, row.b), (3, 4))
            with self.assertRaises(AttributeError):
                namespace['Child'](1, 2)

    def test_unknown_and_unsupported_constructors_are_retained(self):
        for decorator, body in (
            ('dataclass(frozen=True)', 'a: int = 1\n    b: int = 2'),
            ('dataclass(frozen=True, slots=True)', 'a: int\n    b: int'),
            ('dataclass', 'a: int\n    b: int'),
            ('dataclass(frozen=True)', 'a: int\n    b: int\n    def __post_init__(self):\n        print(self.a)'),
        ):
            source = f'from dataclasses import dataclass\n@{decorator}\nclass Pair:\n    {body}\ndef run():\n    return Pair(1,2)'
            self.assertNotIn('small-record-call', [c.pass_name for c in optimize_source(source).changes])
        source = 'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Pair:\n    a: int\n    b: int\n'
        for call in ('Pair(1)', 'Pair(1,2,3)', 'Pair(*values)', 'Pair(1,a=2)', 'Pair(1,2,extra=3)'):
            self.assertNotIn('small-record-call', [c.pass_name for c in optimize_source(
                source + f'def run(values):\n    return {call}').changes])
        self.assertNotIn('small-record-call', [c.pass_name for c in optimize_source(
            source + 'def run(Pair):\n    return Pair(1,2)').changes])

    def test_disable_keeps_original_and_source_is_deterministic(self):
        source = 'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Pair:\n    a: int\n    b: int\ndef run():\n    return Pair(1,2)'
        self.assertEqual(optimize_source(source).source, optimize_source(source).source)
        result = optimize_source(source, Options(disabled=frozenset({'small-record-call'})))
        self.assertFalse(result.changes)
        cached = optimize_source(source)
        uncached = optimize_source(source, Options(disabled=frozenset({'record-allocator-cache'})))
        self.assertIn('_bcopt_new_', cached.source)
        self.assertNotIn('_bcopt_new_', uncached.source)
        self.assertEqual(execute(cached.source)['run']().__dict__, execute(uncached.source)['run']().__dict__)

    def test_cross_module_field_names_cannot_collide_with_factory_locals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bot = root/'bot'
            bot.mkdir()
            (bot/'types_local.py').write_text('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Row:\n    _bcopt_class_0: int\n    _bcopt_dict_0: int\n')
            (bot/'main.py').write_text('from types_local import Row\ndef run():\n    row=Row(3,4)\n    result=row._bcopt_class_0 + row._bcopt_dict_0\n    return result\n')
            report = optimize_folder(bot, root/'out')
            self.assertEqual(report['pass_counts']['small-record-call'], 1)
            namespace = execute((root/'out/types_local.py').read_text())
            from types import ModuleType
            module = ModuleType('types_local')
            module.__dict__.update(namespace)
            with patch.dict(sys.modules, {'types_local': module}):
                self.assertEqual(execute((root/'out/main.py').read_text())['run'](), 7)


class ReturnShapeTests(unittest.TestCase):
    def test_later_record_fields_do_not_shadow_shared_factory_object(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bot = root / 'bot'
            bot.mkdir()
            (bot / 'rows.py').write_text('from dataclasses import dataclass\n'
                '@dataclass(frozen=True)\nclass First:\n    a: int\n    b: int\n'
                '@dataclass(frozen=True)\nclass Second:\n    _bcopt_object_0: int\n    c: int\n    _bcopt_new_0: int\n')
            (bot / 'main.py').write_text('from rows import First, Second\ndef run():\n'
                '    first = First(1, 2)\n    second = Second(3, 4, 5)\n'
                '    result = first.a + second.c\n    return result\n')
            report = optimize_folder(bot, root / 'out')
            self.assertEqual(report['pass_counts']['small-record-call'], 2)
            from types import ModuleType
            rows = ModuleType('rows')
            rows.__dict__.update(execute((root / 'out/rows.py').read_text()))
            with patch.dict(sys.modules, {'rows': rows}):
                self.assertEqual(execute((root / 'out/main.py').read_text())['run'](), 5)

    def test_effectful_wrapper_is_still_called_once_at_original_position(self):
        source = textwrap.dedent('''
            events = []
            def values():
                events.append('called')
                return (-3, -2, -1, 0, 1, 2, 3)
            def run():
                events.append('before')
                result = sum(x*x for x in values() if x > 0)
                events.append('after')
                return result, events
        ''')
        result = optimize_source(source)
        self.assertIn('bounded-reduction', [c.pass_name for c in result.changes])
        self.assertEqual(execute(source)['run'](), execute(result.source)['run']())
        disabled = optimize_source(source, Options(disabled=frozenset({'return-shape'})))
        self.assertNotIn('bounded-reduction', [c.pass_name for c in disabled.changes])

    def test_annotations_mutable_contents_branches_and_shadowed_builtins_are_not_proofs(self):
        for function in (
            'def values(arg) -> tuple[int, ...]:\n    return arg',
            'def values(arg):\n    return tuple(arg)',
            'def values(arg):\n    return [1, 2, 3]',
            'def values(arg):\n    if arg:\n        return (1, 2)\n    return arg',
            'def values(range):\n    return range(3)',
        ):
            source = function + '\ndef run(arg):\n    return sum(x*x for x in values(arg))\n'
            self.assertNotIn('bounded-reduction', [c.pass_name for c in optimize_source(source).changes])

    def test_cross_module_return_propagation_and_reexports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bot = root/'bot'
            bot.mkdir()
            (bot/'data.py').write_text('def values():\n    return (1, 2, 3)\n')
            (bot/'middle.py').write_text('from data import values\ndef wrapped():\n    return values()\n')
            (bot/'main.py').write_text('from middle import wrapped\ndef run():\n    return sum(x*x for x in wrapped())\n')
            report = optimize_folder(bot, root/'out')
            self.assertEqual(report['pass_counts']['bounded-reduction'], 1)
            self.assertGreaterEqual(report['analysis']['inferred_returns'], 2)
            # An import cycle invalidates the same lookup assumptions.
            (bot/'data.py').write_text('import main\ndef values():\n    return (1, 2, 3)\n')
            report = optimize_folder(bot, root/'cyclic')
            self.assertNotIn('bounded-reduction', report['pass_counts'])


class IntegerLoopTests(unittest.TestCase):
    def test_signed_and_large_values_match_modulo(self):
        source = textwrap.dedent('''
            PERIOD = 8
            def run():
                result = []
                for value in (-100000000000000000001, -9, -8, -1, 0, 1, 8, 9, 100000000000000000001):
                    result.append(value % PERIOD)
                return result
        ''')
        result = optimize_source(source)
        self.assertIn('integer-mod-mask', [c.pass_name for c in result.changes])
        self.assertEqual(execute(source)['run'](), execute(result.source)['run']())

    def test_nested_counter_recurrence_keeps_type_but_not_initial_value(self):
        source = textwrap.dedent('''
            PERIOD = 8
            def run(n):
                count = 0
                hits = []
                for x in range(n):
                    for y in range(4):
                        count += 1
                        if count % PERIOD == 0:
                            hits.append(count)
                return count, hits
        ''')
        result = optimize_source(source)
        self.assertIn('integer-mod-mask', [c.pass_name for c in result.changes])
        old, new = execute(source)['run'], execute(result.source)['run']
        for n in (0, 1, 2, 13):
            self.assertEqual(old(n), new(n))
        for option in ('constant-facts', 'loop-integer-facts', 'integer-mod-mask'):
            self.assertNotIn('integer-mod-mask', [c.pass_name for c in optimize_source(
                source, Options(disabled=frozenset({option}))).changes])

    def test_unknown_writes_and_deletions_invalidate_recurrence(self):
        for mutation in ('count = value', 'count /= 2', 'count += value', 'del count',
                         'count, other = value', 'for count in value:\n            pass'):
            source = f'def run(value):\n    count=0\n    for x in range(4):\n        {mutation}\n        print(count % 8)\n'
            self.assertNotIn('integer-mod-mask', [c.pass_name for c in optimize_source(source).changes])

    def test_effectful_constant_return_call_is_not_elided(self):
        source = textwrap.dedent('''
            events=[]
            def divisor():
                events.append('called')
                return 8
            def run():
                x=9
                return x % divisor(), events
        ''')
        result = optimize_source(source)
        self.assertNotIn('integer-mod-mask', [c.pass_name for c in result.changes])
        self.assertEqual(execute(source)['run'](), execute(result.source)['run']())

    def test_mutable_global_and_shadowed_constant_not_folded(self):
        for source in (
            'PERIOD=8\ndef set_period():\n    global PERIOD\n    PERIOD=3\ndef run():\n    x=9\n    return x%PERIOD',
            'PERIOD=8\ndef run(PERIOD):\n    x=9\n    return x%PERIOD',
            'def run():\n    count=0\n    def change():\n        nonlocal count\n        count=1.5\n    for x in range(4):\n        change()\n        print(count%8)',
        ):
            self.assertNotIn('integer-mod-mask', [c.pass_name for c in optimize_source(source).changes])

    def test_imported_constant_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            bot=root/'bot'
            bot.mkdir()
            (bot/'constants.py').write_text('PERIOD = 8\n')
            (bot/'main.py').write_text('from constants import PERIOD\ndef run():\n    x=9\n    return x % PERIOD\n')
            report=optimize_folder(bot,root/'out')
            self.assertEqual(report['pass_counts']['integer-mod-mask'],1)
            # Removing the read during circular/partial initialization is unsafe.
            (bot/'constants.py').write_text('import main\nPERIOD=8\n')
            report=optimize_folder(bot,root/'cyclic')
            self.assertNotIn('integer-mod-mask',report['pass_counts'])


if __name__ == '__main__':
    unittest.main()
