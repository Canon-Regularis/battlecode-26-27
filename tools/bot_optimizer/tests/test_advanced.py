"""Risk-focused differential checks for the fuel-measured extensions."""

import dis
import textwrap
import unittest
from types import ModuleType
from unittest.mock import patch
import sys

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


class AdvancedTests(unittest.TestCase):
    def compare(self, source, inputs=((),), options=None):
        source = textwrap.dedent(source)
        result = optimize_source(source, options)
        before, after = execute(source), execute(result.source)
        for args in inputs:
            self.assertEqual(before['run'](*args), after['run'](*args))
        return result

    def test_compound_item_keys_access_order_ties_and_errors(self):
        for index in (1, 99):
            result = self.compare(f'''
                def run():
                    seen=[]
                    class Row:
                        def __init__(self, tag):
                            self.tag=tag
                        def __getitem__(self, key):
                            seen.append((self.tag,key))
                            if key==99:
                                raise ValueError('bad index')
                            return 0
                    rows=[Row(i) for i in range(3)]
                    try:
                        result=sorted(rows,key=lambda r:(r[0],r[{index}]))
                        tags=[r.tag for r in result]
                    except ValueError as error:
                        tags=str(error)
                    return tags,seen
            ''')
            self.assertIn('native-itemgetter', [c.pass_name for c in result.changes])

    def test_compound_attribute_keys_repeated_descriptor_and_nested_paths(self):
        result = self.compare('''
            def run():
                seen=[]
                class Row:
                    @property
                    def child(self):
                        seen.append('child')
                        return self
                    @property
                    def score(self):
                        seen.append('score')
                        return 0
                rows=[Row(),Row()]
                return len(sorted(rows,key=lambda r:(r.child.score,r.child.score))),seen
        ''')
        self.assertIn('native-attrgetter', [c.pass_name for c in result.changes])

    def test_unsupported_key_shapes_preserved(self):
        for body in ('(r[0],)', '()', '(r.x,r[0])', '(r.x, f())', '(r.__hidden,r.x)', '(r[0],*r)'):
            source = f'def run(rows,f):\n    return sorted(rows,key=lambda r:{body})\n'
            self.assertFalse(optimize_source(source).changes, body)

    def test_filtered_reductions_predicates_short_circuit_and_empty_defaults(self):
        result = self.compare('''
            def run():
                values=(-3,-2,-1,0,1,2,3)
                return (sum(x*x for x in values if x > 0 if x & 1),
                        min((x*x for x in values if x > 5),default=None),
                        max(x*x for x in values if x < 0 or (x > 0 and not x == 2)))
        ''')
        self.assertEqual(sum(c.pass_name == 'bounded-reduction' for c in result.changes), 3)

    def test_effectful_float_mutable_and_raising_filters_preserved(self):
        for expression in ('sum(x*x for x in range(8) if f(x))',
                           'sum(x*x for x in (1.0,2.0) if x)',
                           'sum(x*x for x in [1,2] if x)',
                           'sum(x*x for x in range(8) if 1//x)',
                           'any(x*x for x in range(8) if x)'):
            self.assertFalse(optimize_source(f'def run(f):\n    return {expression}').changes)

    def test_native_map_consumers_and_empty_inputs(self):
        for consumer in ('list', 'tuple', 'sum', 'any', 'all', 'min', 'max'):
            suffix = ', default=None' if consumer in {'min','max'} else ''
            result = self.compare(f'''
                def run(n):
                    return {consumer}((abs(x) for x in range(-n,0)){suffix})
            ''', [(0,), (1,), (8,), (128,)])
            self.assertIn('native-map', [c.pass_name for c in result.changes])

    def test_native_map_unknown_values_keep_pep479_stopiteration(self):
        source = '''
            class Value:
                def __abs__(self):
                    raise StopIteration('not end of input')
            def run():
                values=(Value(),)
                try:
                    return tuple(abs(x) for x in values)
                except RuntimeError:
                    return 'PEP479'
        '''
        result = self.compare(source)
        self.assertNotIn('native-map', [c.pass_name for c in result.changes])
        for expression in ('tuple(abs(x) for x in values)', 'tuple(abs(abs) for abs in range(4))'):
            self.assertNotIn('native-map', [c.pass_name for c in optimize_source(
                f'def run(values):\n    return {expression}').changes])

    def test_integer_membership_hash_semantics_guards_and_constant_folding(self):
        result = self.compare('''
            def run(n):
                matches=[]
                for x in range(n):
                    if x in (-3,0,2,2,4,100000000000000000000):
                        matches.append(x)
                return matches
        ''', [(0,), (8,)])
        self.assertIn('integer-membership', [c.pass_name for c in result.changes])
        code = execute(result.source)['run'].__code__
        self.assertTrue(any(type(value) is frozenset for value in code.co_consts))
        self.assertNotIn('BUILD_SET', [i.opname for i in dis.get_instructions(code)])
        for source in ('def run(x):\n    return x in (1,2,3,4)',
                       'def run():\n    x=1.0\n    return x in (1,2,3,4)',
                       'def run():\n    x=1\n    return x in (1,2,3,f())',
                       'def run():\n    x=1\n    return x in (1,2,3,True)'):
            self.assertNotIn('integer-membership', [c.pass_name for c in optimize_source(source).changes])

    def test_record_reinitialization_preserves_dict_alias_and_extra_keys(self):
        source = textwrap.dedent('''
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Row:
                a:object
                b:object
                c:object
                d:object
        ''')
        result = optimize_source(source)
        self.assertIn('record-bulk-init', [c.pass_name for c in result.changes])
        observations = []
        for version in (source, result.source):
            cls = execute(version)['Row']
            row = cls(1,2,3,4)
            dictionary = row.__dict__
            object.__setattr__(row, 'extra', 9)
            cls.__init__(row, 5,6,7,8)
            self.assertIs(dictionary, row.__dict__)
            observations.append(dictionary.copy())
        self.assertEqual(*observations)

    def test_record_reinitialization_finalizer_observes_field_order(self):
        source = 'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Row:\n    a:object\n    b:object\n    c:object\n    d:object\n'
        results = []
        for version in (source, optimize_source(source).source):
            seen = []
            cls = execute(version)['Row']
            class Old:
                def __del__(self):
                    seen.append((row.b, row.c, row.d))
            row = cls(Old(),2,3,4)
            cls.__init__(row,1,20,30,40)
            results.append(seen)
        self.assertEqual(results, [[(2,3,4)], [(2,3,4)]])

    def test_record_reinitialization_finalizer_can_replace_instance_dictionary(self):
        source = 'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Row:\n    a:object\n    b:object\n    c:object\n    d:object\n'
        results = []
        for version in (source, optimize_source(source).source):
            cls = execute(version)['Row']
            class Old:
                def __del__(self):
                    object.__setattr__(row, '__dict__', {'extra': 9})
            row = cls(Old(),2,3,4)
            original_dict = row.__dict__
            cls.__init__(row,1,20,30,40)
            results.append((row.__dict__.copy(), original_dict['b']))
        self.assertEqual(results, [({'extra':9,'b':20,'c':30,'d':40},2)]*2)

    def test_record_initialization_does_not_call_dictionary_subclass_overrides(self):
        source = 'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Row:\n    a:object\n    b:object\n    c:object\n    d:object\n'
        class Dictionary(dict):
            def __bool__(self):
                raise AssertionError('must not consult custom truth value')
            def __setitem__(self, key, value):
                raise AssertionError('object setters bypass dictionary overrides')
        for version in (source, optimize_source(source).source):
            cls = execute(version)['Row']
            row = object.__new__(cls)
            dictionary = Dictionary()
            object.__setattr__(row, '__dict__', dictionary)
            cls.__init__(row,1,2,3,4)
            self.assertIs(row.__dict__, dictionary)
            self.assertEqual(dict(dictionary), dict(a=1,b=2,c=3,d=4))

    def test_record_fallback_does_not_retain_replaced_dictionary_or_delay_finalizers(self):
        source = 'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Row:\n    a:object\n    b:object\n    c:object\n    d:object\n'
        observations = []
        for version in (source, optimize_source(source).source):
            seen = []
            cls = execute(version)['Row']
            class Swap:
                def __del__(self):
                    object.__setattr__(row, '__dict__', {})
                    seen.append('swap')
            class Watch:
                def __del__(self):
                    seen.append(tuple(sorted(row.__dict__)))
            row = cls(Swap(),Watch(),3,4)
            cls.__init__(row,1,20,30,40)
            observations.append(seen)
        self.assertEqual(*observations)
        self.assertEqual(observations[0], [(), 'swap'])

    def test_new_membership_disable_and_materialization_bound(self):
        source = 'def run():\n    x=1\n    return x not in (1,2,3,4)'
        for options in (Options(disabled=frozenset({'integer-membership'})), Options(max_materialize=3)):
            self.assertFalse(optimize_source(source, options).changes)

    def test_state_expression_short_circuit_and_definition_dominance(self):
        sdk = ModuleType('cambc')
        flags = type('ChampionState', (int,), dict(CAN_MOVE=1, CAN_ATTACK=2, CAN_CAST=4, RECALLING=8))
        sdk.ChampionState = flags
        class State(int):
            def __contains__(self, flag):
                return self & flag == flag
            def intersects(self, flags):
                return bool(self & flags)
        class Champion:
            bits = 0
            reads = 0
            alive = True
            def state(self):
                self.reads += 1
                return State(self.bits)
            def is_alive(self):
                return self.alive
            def can_move(self):
                return flags.CAN_MOVE in self.state()
            def can_attack(self):
                return flags.CAN_ATTACK in self.state()
            def can_cast(self):
                return flags.CAN_CAST in self.state()
        champion = Champion()
        sdk.me = lambda: champion
        for expression in (
            'me.can_move() and me.can_attack()',
            'not me.is_alive() or me.can_move() or (me.can_attack() and me.can_cast())',
            '(False and me.can_move()) or (me.can_attack() and me.can_cast())',
            '(True or me.can_move()) and (me.can_attack() or me.can_cast())',
            'not me.can_move() or not me.can_attack()',
            'not me.can_move() and not me.can_attack()',
        ):
            source = f'import cambc\ndef run():\n    me=cambc.me()\n    return {expression}\n'
            result = optimize_source(source)
            self.assertIn('sdk-state-expression', [c.pass_name for c in result.changes])
            with patch.dict(sys.modules, {'cambc': sdk}):
                old, new = execute(source)['run'], execute(result.source)['run']
            for alive in (False, True):
                champion.alive = alive
                for bits in range(8):
                    champion.bits = bits
                    champion.reads = 0
                    before = old()
                    old_reads = champion.reads
                    champion.reads = 0
                    self.assertEqual(before, new(), (expression, alive, bits))
                    self.assertLessEqual(champion.reads, old_reads)

    def test_state_sharing_never_crosses_callbacks_actions_or_receivers(self):
        for expression in (
            'me.can_move() and action() and me.can_attack()',
            'me.can_move() and other.can_attack()',
            '(False and me.can_move()) or me.can_attack()',
        ):
            source = f'import cambc\ndef run(action,other):\n    me=cambc.me()\n    return {expression}\n'
            self.assertNotIn('sdk-state-expression', [c.pass_name for c in optimize_source(source).changes])
        source = 'import cambc\ndef run():\n    me=cambc.me()\n    return me.can_move() and me.can_attack()'
        self.assertFalse(optimize_source(source, Options(disabled=frozenset({'sdk-state-expression'}))).changes)


if __name__ == '__main__':
    unittest.main()
