import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.retained_integer_edges import RetainedIntegerEdges
from tools.bot_optimizer.tests.test_width_dispatch import SOURCE
from tools.bot_optimizer.tests.test_specialization import execute


class RetainedIntegerEdgeTests(unittest.TestCase):
    def test_widths_and_original_fallbacks(self):
        for length in (1, 2, 11, 12):
            text = SOURCE.replace('[tuple([0, 0]), tuple([0])]', f'[tuple({[0]*length!r})]')
            result = optimize_source(text)
            self.assertEqual(sum(c.pass_name == 'insertion-retained-integer-edges' for c in result.changes), 11)
            original, optimized = execute(text), execute(result.source)
            for case in original['CASES']:
                self.assertEqual(original[case](), optimized[case](), (length, case))
        for disabled in ('insertion-retained-integer-edges', 'insertion-base-edge-scalars', 'insertion-edge-algebra'):
            result = optimize_source(SOURCE, Options(disabled=frozenset({disabled})))
            self.assertFalse(any(c.pass_name == 'insertion-retained-integer-edges' for c in result.changes))

    def test_changed_contract_guard_and_immutable_root_reject(self):
        captured = []
        def capture(pass_, tree):
            captured.append(tree)
            return tree
        with patch('tools.bot_optimizer.compiler.RetainedIntegerEdges.apply', capture):
            optimize_source(SOURCE)
        original, = captured
        for mutation in ('contract', 'initial', 'guard', 'snapshot', 'base', 'total-write'):
            tree = copy.deepcopy(original)
            for node in list(ast.walk(tree)):
                if mutation == 'snapshot' and getattr(node, '_bcopt_snapshot_hoisted', False):
                    del node._bcopt_snapshot_hoisted
                if mutation == 'base' and getattr(node, '_bcopt_direct_base', None):
                    del node._bcopt_direct_base
                if getattr(node, '_bcopt_integer_edge_fast', None):
                    if mutation == 'contract':
                        del node._bcopt_integer_edge_fast
                    elif mutation == 'initial':
                        node.body[0].body[0].value = ast.Constant(0)
                    elif mutation == 'guard':
                        node.test = ast.Constant(True)
                    elif mutation == 'total-write':
                        node.body.append(ast.parse(f'{node._bcopt_integer_edge_fast["base_total"]} = 0').body[0])
            transform = RetainedIntegerEdges(Options())
            transform.apply(tree)
            self.assertFalse(transform.changes, mutation)


if __name__ == '__main__':
    unittest.main()
