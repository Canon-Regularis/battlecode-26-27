import ast
import builtins
import copy
from types import SimpleNamespace
import unittest

from tools.bot_optimizer.derived_tables import DerivedTables


def specialize(source, fields=2, contract=True, tuple_inputs=(), native_projection=False):
    tree = ast.parse(source)
    original = copy.deepcopy(tree)
    function = tree.body[0]
    if contract:
        for node in ast.walk(function):
            if isinstance(node, ast.BinOp):
                node._bcopt_numeric_kind = 'number'
            if isinstance(node, ast.Name) and node.id in tuple_inputs:
                node._bcopt_numeric_kind = 'tuple'
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in tuple_inputs:
                node._bcopt_numeric_kind = 'int'
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'sum':
                node._bcopt_numeric_native = 'sum'
    taken = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    def fresh(stem):
        name = '_test_' + stem
        while name in taken:
            name += '_'
        taken.add(name)
        return name
    builder = SimpleNamespace(fresh=fresh, owner=SimpleNamespace(fields=tuple(range(fields))))
    transformation = DerivedTables(builder, SimpleNamespace(function=function), '_builtins',
                                   native_projection=native_projection)
    helpers, preparations = transformation.apply()
    tree.body[:0] = helpers
    before, after = {}, {'_builtins': builtins}
    exec(compile(original, '<original>', 'exec'), before)
    exec(compile(ast.fix_missing_locations(tree), '<derived>', 'exec'), after)
    def snapshot(data):
        return (*data, *(after[name](data) for name in preparations))
    return before[function.name], after[function.name], snapshot, transformation


class DerivedTableTests(unittest.TestCase):
    def test_native_projection_keeps_compensated_sum_and_index_sequence(self):
        source = '''def f(self, indices):
    value = sum([self[0][i] * self[1][i] for i in indices])
    return value
'''
        before, after, snapshot, pass_ = specialize(source, tuple_inputs=('indices',), native_projection=True)
        self.assertIsNotNone(pass_.getter)
        data = ([1e16, 1.0, -1e16, -0.0], [1.0]*4)
        for indices in ((), (0,), (-1,), (0, 1, 2), (0, 1, 1, 2), (-2, -3, 0), (3, 3)):
            expected, actual = before(data, indices), after(snapshot(data), indices)
            self.assertIs(type(expected), type(actual))
            self.assertEqual(expected.hex() if type(expected) is float else expected,
                             actual.hex() if type(actual) is float else actual)
        self.assertEqual(after(snapshot(data), (0, 1, 2)), 1.0)

    def test_native_projection_failed_preparation_and_exception_order(self):
        before, after, snapshot, pass_ = specialize('''def f(self, indices):
    value = sum([self[0][i] / self[1][i] for i in indices])
    return value
''', tuple_inputs=('indices',), native_projection=True)
        self.assertIsNotNone(pass_.getter)
        for data in (([4.0, 8.0], [2.0, 0.0]), ([4.0, 8.0], [2.0]),
                     ([4.0, 8.0], [2.0, 1.0])):
            for indices in ((), (0,), (0, 0), (1, 8), (8, 1), (-1, 0)):
                outcomes = []
                for fn, values in ((before, data), (after, snapshot(data))):
                    try:
                        outcomes.append(('value', fn(values, indices)))
                    except Exception as error:
                        outcomes.append((type(error).__name__, str(error)))
                self.assertEqual(*outcomes)

    def test_native_projection_requires_numeric_and_tuple_contracts(self):
        source = '''def f(self, indices):
    value = sum([self[0][i] * self[1][i] for i in indices])
    return value
'''
        for contract, tuple_inputs in ((False, ('indices',)), (True, ())):
            _, _, _, pass_ = specialize(source, contract=contract, tuple_inputs=tuple_inputs, native_projection=True)
            self.assertIsNone(pass_.getter)

    def test_negative_indices_and_unequal_domains(self):
        before, after, snapshot, pass_ = specialize('''def f(self, indices):
    result = []
    for i in indices:
        value = self[0][i] + self[1][i]
        result.append(value)
    return result
''')
        self.assertEqual(len(pass_.tables), 1)
        for data in (([1, 2], [4, 8]), ([1, 2], [4, 8, 16])):
            prepared = snapshot(data)
            self.assertEqual(before(data, [-1, 0, 1]), after(prepared, [-1, 0, 1]))
            if len(data[0]) != len(data[1]):
                self.assertIsNone(prepared[-1])

    def test_preparation_failure_preserves_skipped_errors(self):
        before, after, snapshot, _ = specialize('''def f(self, indices):
    result = []
    for i in indices:
        value = self[0][i] / self[1][i]
        result.append(value)
    return result
''')
        data = ([4.0, 8.0], [2.0, 0.0])
        prepared = snapshot(data)
        self.assertIsNone(prepared[-1])
        self.assertEqual(before(data, [0]), after(prepared, [0]))
        for function, values in ((before, data), (after, prepared)):
            with self.assertRaises(ZeroDivisionError):
                function(values, [1])

    def test_aliases_are_invalidated_across_loop_backedges(self):
        before, after, snapshot, _ = specialize('''def f(self, indices):
    row = self[0]
    result = []
    for i in indices:
        value = row[i] + self[0][i]
        result.append(value)
        row = self[1]
    return result
''')
        data = ([1, 2], [10, 20])
        self.assertEqual(before(data, [0, 1]), after(snapshot(data), [0, 1]))

    def test_rebinding_an_index_invalidates_its_projection(self):
        before, after, snapshot, _ = specialize('''def f(self, indices):
    result = []
    for i in indices:
        row = self[0][i]
        i += 1
        value = row[0] + self[1][i]
        result.append(value)
    return result
''')
        data = ([[1], [2]], [10, 20, 30])
        self.assertEqual(before(data, [0, 1]), after(snapshot(data), [0, 1]))

    def test_comprehension_target_shadows_outer_alias(self):
        before, after, snapshot, _ = specialize('''def f(self, indices):
    i = self[0]
    result = [self[0][i] + self[1][i] for i in indices]
    return result
''')
        data = ([1, 2], [10, 20])
        self.assertEqual(before(data, [0, 1]), after(snapshot(data), [0, 1]))

    def test_annotated_rebinding_replaces_projection(self):
        before, after, snapshot, _ = specialize('''def f(self, indices):
    row = self[0]
    row: tuple = self[1]
    result = [row[i] + self[0][i] for i in indices]
    return result
''')
        data = ([1, 2], [10, 20])
        self.assertEqual(before(data, [0, 1]), after(snapshot(data), [0, 1]))

    def test_float_bits_and_bounded_table_size(self):
        before, after, snapshot, _ = specialize('''def f(self, indices):
    result = [self[0][i] * self[1][i] for i in indices]
    return result
''')
        data = ([-0.0, float('nan'), float('inf')], [1.0, 0.0, 0.0])
        self.assertEqual([v.hex() for v in before(data, range(3))],
                         [v.hex() for v in after(snapshot(data), range(3))])
        self.assertIsNone(snapshot(([1]*4097, [2]*4097))[-1])

    def test_owned_list_prefix_survives_append_and_extend(self):
        before, after, snapshot, pass_ = specialize('''def f(self, indices):
    result = []
    for i in indices:
        head = [self[0][i], self[1][i]]
        alias = head
        alias.append(99)
        head.extend([100, 101])
        value = head[0] * alias[1] / 2
        result.append(value)
    return result
''')
        data = ([2, -4], [0.25, 0.75])
        self.assertEqual(len(pass_.tables), 1)
        self.assertEqual(before(data, [-1, 0]), after(snapshot(data), [-1, 0]))

    def test_mutable_prefix_does_not_prove_negative_index(self):
        before, after, snapshot, pass_ = specialize('''def f(self, indices):
    result = []
    for i in indices:
        head = [self[0][i], self[1][i]]
        head.append(99)
        value = head[-1] * self[0][i]
        result.append(value)
    return result
''')
        data = ([2, -4], [0.25, 0.75])
        self.assertFalse(pass_.tables)
        self.assertEqual(before(data, [0, 1]), after(snapshot(data), [0, 1]))

    def test_snapshot_scalar_preserves_skipped_error(self):
        before, after, snapshot, pass_ = specialize('''def f(self, indices):
    value = 1.0
    if indices:
        value = self[0][0] / self[1][0]
    return value
''')
        self.assertEqual(len(pass_.tables), 1)
        data = ([1.0], [0.0])
        self.assertIsNone(snapshot(data)[-1])
        self.assertEqual(before(data, []), after(snapshot(data), []))
        with self.assertRaises(ZeroDivisionError):
            after(snapshot(data), [0])
        data = ([-0.0], [2.0])
        self.assertEqual(before(data, [0]).hex(), after(snapshot(data), [0]).hex())

    def test_equivalent_tuple_projections_share_one_index_domain(self):
        before, after, snapshot, pass_ = specialize('''def f(self, indices):
    first = indices[-1]
    prefix = [self[0][first], self[1][first]]
    again = indices[-1]
    value = prefix[0] * (self[1][again] + self[0][again]) / 2
    return value
''', tuple_inputs=('indices',))
        data = ([2, -4], [0.25, 0.75])
        prepared = snapshot(data)
        self.assertEqual(len(pass_.tables), 1)
        self.assertEqual(len(prepared[-1]), 2)
        self.assertTrue(all(type(value) is float for value in prepared[-1]))
        for indices in ((0,), (1,), (-1,), (1, 0)):
            self.assertEqual(before(data, indices).hex(), after(prepared, indices).hex())

    def test_rebinding_tuple_invalidates_saved_prefix_projection(self):
        before, after, snapshot, _ = specialize('''def f(self, indices):
    first = indices[0]
    prefix = [self[0][first], self[1][first]]
    indices = (1,)
    value = prefix[0] * self[1][indices[0]]
    return value
''', tuple_inputs=('indices',))
        data = ([2, -4], [0.25, 0.75])
        self.assertEqual(before(data, (0,)), after(snapshot(data), (0,)))

    def test_missing_numeric_contract_is_not_optimized(self):
        _, _, _, pass_ = specialize('''def f(self, indices):
    result = [self[0][i] + self[1][i] for i in indices]
    return result
''', contract=False)
        self.assertFalse(pass_.tables)
