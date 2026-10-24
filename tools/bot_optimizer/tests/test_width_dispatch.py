import ast
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.width_dispatch import WidthDispatch
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = (Path(__file__).resolve().parents[3]/'benchmarks/bot-optimizer/src/eighty.py').read_text()


class WidthDispatchTests(unittest.TestCase):
    def test_all_guest_shapes_width_limits_and_fallbacks(self):
        for length in (0, 1, 2, 10, 11, 12):
            text = SOURCE.replace('[tuple([0, 0]), tuple([0])]', f'[tuple({[0]*length!r})]')
            compiled = optimize_source(text)
            self.assertTrue(any(c.pass_name == 'insertion-width-dispatch' for c in compiled.changes), length)
            original, optimized = execute(text), execute(compiled.source)
            for case in original['CASES']:
                self.assertEqual(original[case](), optimized[case](), (length, case))
        for disabled in ('insertion-width-dispatch', 'numeric-ordered-folds', 'insertion-producer-fusion'):
            result = optimize_source(SOURCE, Options(disabled=frozenset({disabled})))
            self.assertFalse(any(c.pass_name == 'insertion-width-dispatch' for c in result.changes))

    def test_perturbed_proofs_and_code_growth_budget(self):
        captured = []
        def capture(pass_, tree):
            captured.append(copy.deepcopy(tree))
            return tree
        with patch('tools.bot_optimizer.compiler.WidthDispatch.apply', capture):
            optimize_source(SOURCE)
        original, = captured
        for mutation in ('dispatch', 'producer', 'binding', 'comparison', 'size-write', 'growth'):
            tree = copy.deepcopy(original)
            producer = next(n for n in ast.walk(tree) if getattr(n, '_bcopt_fused_insertion', None))
            dispatch = next(n for n in ast.walk(producer) if getattr(n, '_bcopt_ordered_width_dispatch', None))
            width, route, maximum = dispatch._bcopt_ordered_width_dispatch
            if mutation == 'dispatch':
                del dispatch._bcopt_ordered_width_dispatch
            elif mutation == 'producer':
                del producer._bcopt_fused_insertion
            elif mutation == 'binding':
                binding = next(n for n in ast.walk(producer) if isinstance(n, ast.Assign)
                               and isinstance(n.targets[0], ast.Name) and n.targets[0].id == width)
                binding.value = ast.Constant(3)
            elif mutation == 'comparison':
                dispatch.test.ops[0] = ast.GtE()
            elif mutation == 'size-write':
                producer.body.append(ast.parse(f'{producer._bcopt_fused_insertion["size"]} = 3').body[0])
            else:
                producer.body.extend(ast.Pass() for _ in range(10000))
            transform = WidthDispatch(Options())
            transform.apply(tree)
            self.assertFalse(transform.changes, mutation)
        plain = ast.parse(ast.unparse(original))
        transform = WidthDispatch(Options())
        transform.apply(plain)
        self.assertFalse(transform.changes)


if __name__ == '__main__':
    unittest.main()
