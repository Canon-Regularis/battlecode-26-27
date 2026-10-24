import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.base_integer_totals import BaseIntegerTotals
from tools.bot_optimizer.tests.test_width_dispatch import SOURCE
from tools.bot_optimizer.tests.test_specialization import execute


class BaseIntegerTotalTests(unittest.TestCase):
    def test_exact_sums_extrema_widths_errors_and_fallbacks(self):
        for length, operation in ((0, 'max'), (2, 'max'), (11, 'min'), (12, 'max')):
            text = SOURCE.replace('[tuple([0, 0]), tuple([0])]', f'[tuple({[0]*length!r})]')
            text = text.replace('peak = max(', f'peak = {operation}(')
            result = optimize_source(text)
            self.assertEqual(sum(c.pass_name == 'insertion-base-integer-totals' for c in result.changes), 11)
            self.assertEqual(sum(c.pass_name == 'insertion-sink-integer-initializers' for c in result.changes), 77)
            original, optimized = execute(text), execute(result.source)
            for case in original['CASES']:
                self.assertEqual(original[case](), optimized[case](), (length, operation, case))
        for disabled in ('insertion-base-integer-totals', 'insertion-direct-routes', 'insertion-width-dispatch'):
            result = optimize_source(SOURCE, Options(disabled=frozenset({disabled})))
            self.assertFalse(any(c.pass_name == 'insertion-base-integer-totals' for c in result.changes))
        result = optimize_source(SOURCE, Options(disabled=frozenset({'insertion-sink-integer-initializers'})))
        self.assertTrue(any(c.pass_name == 'insertion-base-integer-totals' for c in result.changes))
        self.assertFalse(any(c.pass_name == 'insertion-sink-integer-initializers' for c in result.changes))

    def test_changed_fields_types_shapes_and_initializers_reject(self):
        captured = []
        def capture(pass_, tree):
            captured.append(tree)
            return tree
        with patch('tools.bot_optimizer.compiler.BaseIntegerTotals.apply', capture):
            optimize_source(SOURCE)
        tree, = captured
        for mutation in ('fields', 'extremum', 'lookup', 'snapshot', 'width', 'base', 'initial', 'extra-write'):
            clone = copy.deepcopy(tree)
            for node in ast.walk(clone):
                if mutation == 'snapshot' and getattr(node, '_bcopt_snapshot_hoisted', False):
                    del node._bcopt_snapshot_hoisted
                if mutation == 'width' and getattr(node, '_bcopt_width_specialization', None):
                    node.test.comparators[0] = ast.Constant(0)
                if mutation == 'base' and getattr(node, '_bcopt_direct_base', None):
                    del node._bcopt_direct_base
                if mutation == 'initial' and getattr(node, '_bcopt_group_init', False):
                    node.value = ast.Constant(1)
                if getattr(node, '_bcopt_integer_fields', None):
                    if mutation == 'fields':
                        node._bcopt_integer_fields = tuple(99 for _ in node._bcopt_integer_fields)
                    elif mutation == 'extremum':
                        node._bcopt_integer_extremum = 'custom'
                    elif mutation == 'extra-write':
                        target = node.body[1].target.id
                        node.body.append(ast.parse(f'{target} = 0').body[0])
                if mutation == 'lookup' and getattr(node, '_bcopt_prepared_lookup', None):
                    del node._bcopt_prepared_lookup
            transform = BaseIntegerTotals(Options())
            transform.apply(clone)
            self.assertFalse(transform.changes, mutation)


if __name__ == '__main__':
    unittest.main()
