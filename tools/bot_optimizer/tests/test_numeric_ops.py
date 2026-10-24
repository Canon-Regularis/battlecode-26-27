import ast
import copy
import unittest

from tools.bot_optimizer.model import Options
from tools.bot_optimizer.numeric_ops import NumericOperations


def transform(expression, *, integer=True, contract=True):
    tree = ast.parse(f'def f(values,x):\n    return {expression}\n')
    original = copy.deepcopy(tree)
    tree.body[0]._bcopt_numeric_clone = contract
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            node._bcopt_numeric_native = node.func.id
            node._bcopt_numeric_kind = 'float' if node.func.id in {'min', 'max'} else 'bool'
        if isinstance(node, ast.Name):
            node._bcopt_numeric_kind = 'list' if node.id == 'values' else 'int' if integer else 'float'
    specializer = NumericOperations(Options())
    emitted = specializer.apply(tree)
    before, after = {}, {}
    exec(compile(original, '<before>', 'exec'), before)
    exec(compile(emitted, '<after>', 'exec'), after)
    return before['f'], after['f'], specializer.changes, ast.unparse(emitted)


class NumericOperationTests(unittest.TestCase):
    def test_native_integer_predicates_preserve_empty_and_inequalities(self):
        for reduction in ('any', 'all'):
            for operation in ('<', '<=', '>', '>='):
                expression = f'{reduction}([v {operation} 0 for v in values])'
                before, after, changes, _ = transform(expression)
                self.assertEqual(len(changes), 1)
                for values in ([], [0], [-1], [1], [2, -1, 0], [10**1000, -10**1000]):
                    self.assertIs(before(values, 0), after(values, 0))

    def test_scalar_extrema_preserve_nan_stable_ties_and_signed_zero(self):
        for expression in ('min(1.0,max(0.0,x))', 'min(x,-0.0)', 'max(x,0.0)'):
            before, after, changes, _ = transform(expression)
            self.assertTrue(changes)
            for value in (float('nan'), float('inf'), float('-inf'), -0.0, 0.0, -1.0, 0.5, 2.0):
                self.assertEqual(before([], value).hex(), after([], value).hex())

    def test_float_predicates_and_untrusted_source_do_not_specialize(self):
        for options in ({'integer': False}, {'contract': False}):
            before, after, changes, _ = transform('any([v < 0 for v in values])', **options)
            self.assertFalse(changes)
            self.assertIs(before([float('nan'), -1.0], 0), after([float('nan'), -1.0], 0))

    def test_effectful_first_operand_keeps_exception_order(self):
        before, after, changes, _ = transform('min(1.0/0.0,values[0])')
        self.assertFalse(changes)
        for function in (before, after):
            with self.assertRaises(ZeroDivisionError):
                function([], 0)


if __name__ == '__main__':
    unittest.main()
