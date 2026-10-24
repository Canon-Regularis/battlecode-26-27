import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.base_edge_scalars import BaseEdgeScalars
from tools.bot_optimizer.tests.test_width_dispatch import SOURCE
from tools.bot_optimizer.tests.test_specialization import execute


class BaseEdgeScalarTests(unittest.TestCase):
    def test_boundaries_errors_and_disabled_dependencies(self):
        for length in (0, 1, 2, 11, 12):
            text = SOURCE.replace('[tuple([0, 0]), tuple([0])]', f'[tuple({[0]*length!r})]')
            compiled = optimize_source(text)
            self.assertEqual(sum(c.pass_name == 'insertion-base-edge-scalars' for c in compiled.changes), 11)
            original, optimized = execute(text), execute(compiled.source)
            for case in original['CASES']:
                self.assertEqual(original[case](), optimized[case](), (length, case))
        for disabled in ('insertion-base-edge-scalars', 'insertion-unroll-positions', 'numeric-ordered-folds'):
            compiled = optimize_source(SOURCE, Options(disabled=frozenset({disabled})))
            self.assertFalse(any(c.pass_name == 'insertion-base-edge-scalars' for c in compiled.changes))

    def test_perturbed_emitter_contracts_and_rebindings(self):
        captured = []
        def capture(pass_, tree):
            captured.append(copy.deepcopy(tree))
            return tree
        with patch('tools.bot_optimizer.compiler.BaseEdgeScalars.apply', capture):
            optimize_source(SOURCE)
        original, = captured
        for mutation in ('base', 'tuple', 'position', 'unpack', 'update', 'table', 'route-write', 'base-write', 'alias-use'):
            tree = copy.deepcopy(original)
            for branch in [n for n in ast.walk(tree) if getattr(n, '_bcopt_width_specialization', None)]:
                unpack, producer = branch.body
                if mutation == 'base':
                    del unpack._bcopt_direct_base
                if mutation == 'base-write':
                    producer.body.append(ast.parse(f'{unpack.targets[0].elts[0].id} = 0').body[0])
                for wrapper in [n for n in ast.walk(producer) if getattr(n, '_bcopt_unrolled_position', None)]:
                    if mutation == 'tuple':
                        wrapper.body[0].value.elts.reverse()
                    if mutation == 'position':
                        del wrapper._bcopt_unrolled_position
                    if mutation == 'route-write':
                        wrapper.body.append(ast.parse(f'{wrapper.body[0].targets[0].id} = ()').body[0])
                    for node in ast.walk(wrapper):
                        if getattr(node, '_bcopt_ordered_unpack', None):
                            if mutation == 'unpack':
                                del node._bcopt_ordered_unpack
                            if mutation == 'alias-use':
                                wrapper.body.insert(1, ast.Expr(value=ast.Name(id=node.targets[0].elts[0].id, ctx=ast.Load())))
                        if mutation == 'update' and getattr(node, '_bcopt_ordered_update', None):
                            node.op = ast.Sub()
            if mutation == 'table':
                for node in ast.walk(tree):
                    if getattr(node, '_bcopt_prepared_table', False):
                        del node._bcopt_prepared_table
            transform = BaseEdgeScalars(Options())
            transform.apply(tree)
            self.assertFalse(transform.changes, mutation)


if __name__ == '__main__':
    unittest.main()
