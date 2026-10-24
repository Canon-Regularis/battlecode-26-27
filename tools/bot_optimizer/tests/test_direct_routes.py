import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.direct_routes import DirectRoutes
from tools.bot_optimizer.tests.test_width_dispatch import SOURCE
from tools.bot_optimizer.tests.test_specialization import execute


class DirectRouteTests(unittest.TestCase):
    def test_source_variants_errors_and_disable_dependencies(self):
        for length in (0, 1, 2, 11, 12):
            text = SOURCE.replace('[tuple([0, 0]), tuple([0])]', f'[tuple({[0]*length!r})]')
            compiled = optimize_source(text)
            self.assertEqual(sum(c.pass_name == 'insertion-direct-routes' for c in compiled.changes), 11)
            original, optimized = execute(text), execute(compiled.source)
            for case in original['CASES']:
                self.assertEqual(original[case](), optimized[case](), (length, case))
        for disabled in ('insertion-direct-routes', 'insertion-width-dispatch', 'tuple-insertion-buffer'):
            compiled = optimize_source(SOURCE, Options(disabled=frozenset({disabled})))
            self.assertFalse(any(c.pass_name == 'insertion-direct-routes' for c in compiled.changes))

    def test_private_buffer_native_calls_and_cleanup_proofs(self):
        captured = []
        def capture(pass_, tree):
            captured.append(copy.deepcopy(tree))
            return tree
        with patch('tools.bot_optimizer.compiler.DirectRoutes.apply', capture):
            optimize_source(SOURCE)
        original, = captured
        for mutation in ('proof', 'width', 'tuple', 'range', 'len', 'insert', 'cleanup', 'escape'):
            tree = copy.deepcopy(original)
            branches = [n for n in ast.walk(tree) if getattr(n, '_bcopt_width_specialization', None)]
            for branch in branches:
                producer = branch.body[0]
                loop = next(n for n in ast.walk(producer) if getattr(n, '_bcopt_tuple_buffer_loop', None))
                insertion, protected = loop.body
                if mutation == 'proof':
                    del loop._bcopt_tuple_buffer_loop
                elif mutation == 'width':
                    branch.test.comparators[0] = ast.Constant(99)
                elif mutation == 'tuple':
                    protected.body[0].value.func = ast.Name(id='custom',ctx=ast.Load())
                elif mutation == 'range':
                    loop.iter.func = ast.Name(id='custom',ctx=ast.Load())
                elif mutation == 'len':
                    loop.iter.args[0].left.func = ast.Name(id='custom',ctx=ast.Load())
                elif mutation == 'insert':
                    insertion.value.args.reverse()
                elif mutation == 'cleanup':
                    protected.finalbody[0].targets[0].slice = ast.Constant(0)
                else:
                    protected.body.append(ast.parse(f'observed={insertion.value.func.value.id}').body[0])
            transform = DirectRoutes(Options())
            transform.apply(tree)
            self.assertFalse(transform.changes, mutation)
        plain = ast.parse(ast.unparse(original))
        transform = DirectRoutes(Options())
        transform.apply(plain)
        self.assertFalse(transform.changes)


if __name__ == '__main__':
    unittest.main()
