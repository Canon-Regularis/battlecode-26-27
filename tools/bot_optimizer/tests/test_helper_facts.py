import ast
import unittest

from tools.bot_optimizer import optimize_source
from tools.bot_optimizer.model import Options
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''from dataclasses import dataclass
@dataclass(frozen=True)
class Row:
    a: int
    b: int
    c: int
def run(rows,route,matrix):
    legs=[]
    legs.extend(matrix[a][b] for a,b in zip(route,route[1:]))
    a=sum(rows[i].a for i in route)
    b=sum(rows[i].b for i in route)
    c=sum(rows[i].c for i in route)
    return legs,(a,b,c)
'''


class HelperFactTests(unittest.TestCase):
    def test_guard_branches_preserve_noninteger_fallbacks(self):
        for disabled in ((), ('helper-builtin-cache',), ('helper-guard-branches',)):
            result = optimize_source(SOURCE, Options(disabled=frozenset(disabled)))
            self.assertEqual('helper-guard-branches' in [c.pass_name for c in result.changes],
                             'helper-guard-branches' not in disabled)
            for mode in ('custom', 'missing', 'bool', 'float', 'subclass'):
                outcomes = []
                for text in (SOURCE, result.source):
                    ns, events = execute(text), []
                    class Number:
                        def __radd__(self, other):
                            events.append('add')
                            return other + 7
                        def __del__(self):
                            events.append('release')
                    class Integer(int):
                        pass
                    value = {'custom': Number, 'missing': lambda: 1, 'bool': lambda: True,
                             'float': lambda: 1.5, 'subclass': lambda: Integer(5)}[mode]()
                    row = ns['Row'](value, 2, 3)
                    if mode == 'missing':
                        object.__delattr__(row, 'b')
                    try:
                        outcome = ns['run']([row], (0,), [[1]])
                    except Exception as error:
                        outcome = type(error).__name__, str(error)
                    del value, row
                    outcomes.append((outcome, list(events)))
                self.assertEqual(*outcomes, mode)

    def test_static_shape_survives_alias_and_content_mutation(self):
        source = '''def run(factory):
    values=[]
    alias=values
    values.append(factory(values))
    return any(value<0 for value in alias)
'''
        result = optimize_source(source)
        self.assertIn('static-helper-shapes', [c.pass_name for c in result.changes])
        outcomes = []
        for text in (source, result.source):
            events = []
            def factory(values):
                class Value:
                    def __lt__(self, other):
                        events.append('compare')
                        values.append(-1)
                        return False
                return Value()
            outcomes.append((execute(text)['run'](factory), events))
        self.assertEqual(*outcomes)
        self.assertEqual(outcomes[0], (True, ['compare']))

    def test_static_shapes_do_not_trust_annotations_or_rebound_names(self):
        sources = [
            'def run(values: list):\n    return any(value<0 for value in values)\n',
            'def run(replacement):\n    values=[]\n    values=replacement\n    return any(value<0 for value in values)\n',
            'def run(replacement):\n    values=[]\n    if replacement:\n        values=replacement\n    return any(value<0 for value in values)\n',
        ]
        for source in sources:
            result = optimize_source(source)
            self.assertNotIn('static-helper-shapes', [c.pass_name for c in result.changes])

    def test_static_shapes_keep_primitive_checks_and_can_be_disabled(self):
        source = SOURCE.replace('def run(rows,route,matrix):',
            'def run(rows,route,matrix):\n    rows=[row for row in rows]')
        result = optimize_source(source)
        self.assertGreaterEqual([c.pass_name for c in result.changes].count('static-helper-shapes'), 2)
        outcomes = []
        for text in (source, result.source):
            ns = execute(text)
            class Number:
                def __radd__(self, value):return value+17
            outcomes.append(ns['run']([ns['Row'](Number(),2,3)], (0,), [[1]]))
        self.assertEqual(*outcomes)
        disabled = optimize_source(source, Options(disabled=frozenset({'static-helper-shapes'})))
        self.assertNotIn('static-helper-shapes', [c.pass_name for c in disabled.changes])

    def test_region_shares_proof_with_multiple_consumers(self):
        source = SOURCE.replace('    return legs,(a,b,c)',
            '    maximum=max(rows[i].a+rows[i].b for i in route)\n    return legs,(a,b,c),maximum')
        for disabled in ((), ('immutable-helper-regions',)):
            result = optimize_source(source, Options(disabled=frozenset(disabled)))
            passes = [change.pass_name for change in result.changes]
            self.assertEqual(passes.count('immutable-helper-facts'), 2)
            self.assertEqual('immutable-helper-regions' in passes, not disabled)
            run = next(n for n in ast.parse(result.source).body if isinstance(n, ast.FunctionDef) and n.name == 'run')
            self.assertEqual(any(isinstance(n, ast.NamedExpr) for n in ast.walk(run)), bool(disabled))
            for route in ((), (0,), (0, 1), [0, 1]):
                outcomes = []
                for text in (source, result.source):
                    ns = execute(text)
                    rows = [ns['Row'](1, 2, 3), ns['Row'](1, 2, 3)]
                    try:
                        value = ns['run'](rows, route, [[1, 2], [3, 4]])
                    except Exception as error:
                        value = type(error).__name__, str(error)
                    outcomes.append(value)
                self.assertEqual(*outcomes)

    def test_region_does_not_extend_facts_past_rebinding(self):
        source = SOURCE.replace('    return legs,(a,b,c)',
            '    route=[1]\n    maximum=max(rows[i].a+rows[i].b for i in route)\n    return legs,(a,b,c),maximum')
        result = optimize_source(source)
        self.assertEqual([c.pass_name for c in result.changes].count('immutable-helper-facts'), 1)
        outcomes = []
        for text in (source, result.source):
            ns = execute(text)
            outcomes.append(ns['run']([ns['Row'](1, 2, 3), ns['Row'](4, 5, 6)], (0,), [[1, 2], [3, 4]]))
        self.assertEqual(*outcomes)

    def test_allocator_reserves_non_name_bindings_in_all_scopes(self):
        tree = ast.parse('''import package.submodule
class Owner:
    import nested.module
    try:
        pass
    except Exception as class_error:
        pass
    def method(self, parameter):
        match parameter:
            case {'key': value, **rest}:
                return value, rest
            case [first, *remaining] as whole:
                return first, remaining, whole
''')
        self.assertTrue({'package', 'package.submodule', 'nested', 'nested.module',
                         'Owner', 'class_error', 'method', 'self', 'parameter',
                         'value', 'rest', 'first', 'remaining', 'whole'} <= used_names(tree))

    def test_contract_reuse_and_disabled_modes(self):
        for disabled in ((), ('native-index-guard',), ('wide-helper-limit',),
                         ('helper-builtin-cache',), ('helper-loop-shape',)):
            result = optimize_source(SOURCE, Options(disabled=frozenset(disabled)))
            self.assertIn('immutable-helper-facts', [c.pass_name for c in result.changes])
            tree = ast.parse(result.source)
            trusted, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name.startswith('_bcopt_facts_trusted_')]
            self.assertNotIn('(index) is not', ast.unparse(trusted))
            self.assertIn('(row) is not record', ast.unparse(trusted))
            old, new = execute(SOURCE), execute(result.source)
            for route in ((), (0,), (0, 1, 2), (-1, 0), (0,) * 17):
                values = []
                for ns in (old, new):
                    rows = [ns['Row'](i, i + 1, i + 2) for i in range(3)]
                    values.append(ns['run'](rows, route, [[1] * 3] * 3))
                self.assertEqual(*values)
        result = optimize_source(SOURCE, Options(disabled=frozenset({'immutable-helper-facts'})))
        self.assertNotIn('immutable-helper-facts', [c.pass_name for c in result.changes])

    def test_mutable_records_are_revalidated_after_callbacks(self):
        result = optimize_source(SOURCE)
        outcomes = []
        for text in (SOURCE, result.source):
            ns, events = execute(text), []
            rows = [ns['Row'](1, 2, 3), ns['Row'](4, 5, 6)]
            class Number:
                def __radd__(self, other):
                    events.append('add')
                    ns['Row'].__init__(rows[1], 4, 99, 6)
                    return other + 7
            class Matrix:
                def __getitem__(self, index):
                    events.append(('matrix', index))
                    ns['Row'].__init__(rows[0], Number(), 2, 3)
                    return [1, 1]
            value = ns['run'](rows, (0, 1), Matrix())
            outcomes.append((value, events))
        self.assertEqual(*outcomes)
        self.assertEqual(outcomes[0][0], ([1], (11, 101, 9)))

    def test_rebinding_and_deletion_expire_facts(self):
        for between in ('route=(0,)\n', 'if rows:\n    route=(0,)\n',
                        'del route\nroute=(0,)\n'):
            source = SOURCE.replace('    a=sum', ''.join('    ' + line + '\n'
                                    for line in between.splitlines()) + '    a=sum', 1)
            result = optimize_source(source)
            self.assertNotIn('immutable-helper-facts', [c.pass_name for c in result.changes])

    def test_custom_route_and_index_fallback_effects(self):
        result = optimize_source(SOURCE)
        for mode in ('tuple-subclass', 'custom-index', 'list'):
            outcomes = []
            for text in (SOURCE, result.source):
                ns, events = execute(text), []
                class Route(tuple):
                    def __getitem__(self, key):
                        events.append(('slice', repr(key)))
                        return super().__getitem__(key)
                class Index:
                    def __index__(self):
                        events.append('index')
                        return 0
                route = Route((0, 1)) if mode == 'tuple-subclass' else (
                    (Index(), 1) if mode == 'custom-index' else [0, 1])
                rows = [ns['Row'](1, 2, 3), ns['Row'](4, 5, 6)]
                outcomes.append((ns['run'](rows, route, [[1, 2], [3, 4]]), events))
            self.assertEqual(*outcomes, mode)

    def test_invalid_index_error_preserved(self):
        result = optimize_source(SOURCE)
        for route in ((99,), (0, 99), (10**100,)):
            outcomes = []
            for text in (SOURCE, result.source):
                ns = execute(text)
                try:
                    ns['run']([ns['Row'](1, 2, 3)], route, [[1]])
                except Exception as error:
                    outcomes.append((type(error).__name__, str(error)))
            self.assertEqual(*outcomes)


if __name__ == '__main__':
    unittest.main()
