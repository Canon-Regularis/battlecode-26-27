import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.base_prefix_scalars import BasePrefixScalars
from tools.bot_optimizer.tests.test_width_dispatch import SOURCE
from tools.bot_optimizer.tests.test_specialization import execute


PREFIX_SOURCE = SOURCE.replace('score = reward + rounded',
    'score = matrix[0][route[0]] * self.weights[route[0]]\n'
    '        score += matrix[0][route[-1]] * self.weights[route[-1]]')


class BasePrefixScalarTests(unittest.TestCase):
    def test_generic_prefix_boundaries_and_noninvariant_initial(self):
        for length in (1, 2, 11, 12):
            text = PREFIX_SOURCE.replace('[tuple([0, 0]), tuple([0])]', f'[tuple({[0]*length!r})]')
            result = optimize_source(text)
            self.assertEqual(sum(c.pass_name == 'insertion-base-prefix-scalars' for c in result.changes), 55)
            original, optimized = execute(text), execute(result.source)
            for case in original['CASES']:
                self.assertEqual(original[case](), optimized[case](), (length, case))
        for text, disabled in ((SOURCE, ()), (PREFIX_SOURCE, ('insertion-base-prefix-scalars',)),
                               (PREFIX_SOURCE, ('insertion-base-edge-scalars',))):
            result = optimize_source(text, Options(disabled=frozenset(disabled)))
            self.assertFalse(any(c.pass_name == 'insertion-base-prefix-scalars' for c in result.changes))

    def test_modified_lookup_index_and_cached_slot_proofs(self):
        captured = []
        def capture(pass_, tree):
            captured.append(tree)
            return tree
        with patch('tools.bot_optimizer.compiler.BasePrefixScalars.apply', capture):
            optimize_source(PREFIX_SOURCE)
        tree, = captured
        branch = next(n for n in ast.walk(tree) if getattr(n, '_bcopt_width_specialization', None) == 4)
        for mutation in ('lookup', 'item', 'table', 'base-write', 'cached-write', 'guard', 'external-index'):
            clone = copy.deepcopy(branch)
            producer = clone.body[-1]
            version = [n for n in ast.walk(producer) if getattr(n, '_bcopt_base_prefix_site', None)][2]
            route, item, base, fields = version._bcopt_base_prefix_site
            region = ast.Module(body=version.body, type_ignores=[])
            update = next(n for n in ast.walk(region) if getattr(n, '_bcopt_ordered_update', None))
            target = update.target.id
            initial = next(n for n in ast.walk(region) if isinstance(n, ast.Assign) and len(n.targets) == 1
                           and isinstance(n.targets[0], ast.Name) and n.targets[0].id == target)
            slots = clone._bcopt_base_edge_slots
            tables = {n.value.id for n in ast.walk(region) if isinstance(n, ast.Subscript)
                      and isinstance(n.value, ast.Name)}
            if mutation == 'lookup':
                del initial.value._bcopt_prepared_lookup
            elif mutation == 'item':
                initial.value.slice = ast.Name(id=item, ctx=ast.Load())
            elif mutation == 'table':
                tables = set()
            elif mutation == 'base-write':
                producer.body.append(ast.parse(f'{base[0]} = 0').body[0])
            elif mutation == 'external-index':
                initial.value.slice = ast.Name(id='unproven', ctx=ast.Load())
            else:
                guard = next(n for n in ast.walk(region) if getattr(n, '_bcopt_base_edge_guard', None))
                if mutation == 'guard':
                    guard.body[0].value = ast.Constant(0.0)
                else:
                    producer.body.append(ast.parse(f'{guard._bcopt_base_edge_guard[0]} = 0.0').body[0])
            transform = BasePrefixScalars(Options())
            self.assertIsNone(transform.rewrite(version, producer, slots, tables), mutation)


if __name__ == '__main__':
    unittest.main()
