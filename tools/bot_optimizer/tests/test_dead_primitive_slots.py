import ast
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.dead_primitive_slots import DeadPrimitiveSlots, definitely_bound
from tools.bot_optimizer.tests.test_width_dispatch import SOURCE
from tools.bot_optimizer.tests.test_specialization import execute


class DeadPrimitiveSlotTests(unittest.TestCase):
    def test_generic_fixture_and_disabled_pass(self):
        result = optimize_source(SOURCE)
        self.assertTrue(any(c.pass_name == 'numeric-dead-primitive-slots' for c in result.changes))
        original, optimized = execute(SOURCE), execute(result.source)
        for case in original['CASES']:
            self.assertEqual(original[case](), optimized[case](), case)
        disabled = optimize_source(SOURCE, Options(disabled=frozenset({'numeric-dead-primitive-slots'})))
        self.assertFalse(any(c.pass_name == 'numeric-dead-primitive-slots' for c in disabled.changes))

    def test_binding_paths_and_target_index_reads(self):
        for text, valid in (
            ('x = 1\nuse(x)', True),
            ('if flag:\n x = 1\nuse(x)', False),
            ('if flag:\n x = 1\nelse:\n x = 2\nuse(x)', True),
            ('for x in values:\n use(x)', True),
            ('for x in values:\n pass\nuse(x)', False),
            ('table[x] = 1', False),
            ('try:\n x = 1\nexcept Error:\n use(x)', False),
            ('try:\n x = 1\nfinally:\n use(x)', False),
        ):
            self.assertEqual(definitely_bound(ast.parse(text).body, 'x')[0], valid, text)

    def test_contract_type_escape_and_cross_arm_use_reject(self):
        source = '''def consumer(base, item, ready):
    for once in (None,):
        route = (base, item)
        if ready:
            x = base
        else:
            x = item
            use(x)
'''
        for mutation in ('none', 'kind', 'private', 'escape', 'cross-arm', 'shape', 'disabled'):
            tree = ast.parse(source)
            consumer = tree.body[0]
            consumer._bcopt_fused_consumer = True
            wrapper = consumer.body[0]
            wrapper._bcopt_unrolled_position = (2, 0, 'size')
            wrapper.body[0]._bcopt_direct_tuple = ('route', 'item', ('base', 'item'))
            version = wrapper.body[1]
            version._bcopt_prepared_dispatch = True
            version._bcopt_private_numeric_locals = ('x',)
            for n in ast.walk(version):
                if isinstance(n, ast.Name) and n.id == 'x' and isinstance(n.ctx, ast.Store):
                    n._bcopt_bound_kind = 'int'
            if mutation == 'kind':
                version.orelse[0].targets[0]._bcopt_bound_kind = 'float'
            elif mutation == 'private':
                del version._bcopt_private_numeric_locals
            elif mutation == 'escape':
                consumer.body.append(ast.parse('use(x)').body[0])
            elif mutation == 'cross-arm':
                version.orelse.pop(0)
            elif mutation == 'shape':
                version.body[0].value = ast.Tuple(elts=[ast.Name(id='base', ctx=ast.Load())], ctx=ast.Load())
            options = Options(disabled=frozenset({'numeric-dead-primitive-slots'})) if mutation == 'disabled' else Options()
            transform = DeadPrimitiveSlots(options)
            transform.apply(tree)
            self.assertEqual(bool(transform.changes), mutation == 'none', mutation)


if __name__ == '__main__':
    unittest.main()
