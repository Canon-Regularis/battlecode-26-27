import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.edge_algebra import EdgeAlgebra
from tools.bot_optimizer.tests import test_incremental_edges as cases
from tools.bot_optimizer.tests.test_specialization import execute


class EdgeAlgebraTests(unittest.TestCase):
    def source(self, consumer=None):
        consumer = consumer or cases.CONSUMER.replace('        prior=None', '        prior=None\n        selection=0').replace(
            'value=evaluate(route, 0)', 'value=evaluate(route, selection)')
        return cases.IncrementalEdgeTests().source(consumer=consumer)

    def test_exact_totals_duplicate_negative_indices_skips_and_errors(self):
        helper = cases.IncrementalEdgeTests()
        for base in ('[]', '[0]', '[0, 0]', '[-1, 0]', '[0, 1]'):
            source = self.source().replace('tuple([0, 0])', f'tuple({base})')
            for matrix in ([[2, 3], [11, 17]], [[0, 0], [0, 0]], [[-1, 3], [11, 17]],
                           [[2], [11, 17]], [[10**100, 3], [11, 17]], []):
                compiled = helper.compare(source, matrix)
                self.assertTrue(any(c.pass_name == 'insertion-edge-algebra' for c in compiled.changes))
        helper.compare(self.source(), [[2, 3], [11, 17]], limit=3)
        source = self.source().replace('            value=evaluate(route, selection)',
            '            index+=1\n            if index % 3 == 0:\n                continue\n            value=evaluate(route, selection)')
        helper.compare(source, [[2, 3], [11, 17]])

    def test_certificate_bounds_and_disabled_or_changing_context(self):
        compiled = optimize_source(self.source())
        self.assertTrue(any(c.pass_name == 'insertion-edge-native-certificate' for c in compiled.changes))
        ns = execute(compiled.source)
        certify, = [value for key, value in ns.items() if key.startswith('_bcopt_algebra_certify')]
        self.assertTrue(certify(((0, 10**100), (1, 2)), ((2, 3),)))
        for matrix, terminals in [(((0, 10**100), (1, 2)), ((2, 3),)),
                                  (((0, -1), (1, 2)), ((2, 3),)), (((0, 1), (1, 2)), ((2,),))]:
            self.assertEqual(certify(matrix, terminals), certify(matrix, terminals, True))
        for matrix, terminals in [(((0, -1), (1, 2)), ((2, 3),)),
                                  (((0, 1), (1, 2)), ((2,),)),
                                  (((True,),), ((1,),)), (((1.0,),), ((1,),)),
                                  (([1],), ((1,),)), ((), ()),
                                  (tuple((1,)*64 for _ in range(64)), ((1,)*64,))]:
            self.assertFalse(certify(matrix, terminals))
        for disabled in ('insertion-edge-algebra', 'insertion-producer-fusion', 'insertion-incremental-edges'):
            result = optimize_source(self.source(), Options(disabled=frozenset({disabled})))
            self.assertFalse(any(c.pass_name == 'insertion-edge-algebra' for c in result.changes))
        result = optimize_source(self.source(), Options(disabled=frozenset({'insertion-edge-native-certificate'})))
        self.assertTrue(any(c.pass_name == 'insertion-edge-algebra' for c in result.changes))
        self.assertFalse(any(c.pass_name == 'insertion-edge-native-certificate' for c in result.changes))
        varying = self.source().replace('            value=evaluate(route, selection)',
            '            selection=index % 2\n            value=evaluate(route, selection)')
        compiled = cases.IncrementalEdgeTests().compare(varying, [[2, 3], [11, 17]])
        self.assertFalse(any(c.pass_name == 'insertion-edge-algebra' for c in compiled.changes))

    def test_rejects_observable_list_reads_changed_proofs_and_table_rebinding(self):
        captured = []
        def capture(pass_, tree):
            captured.append(copy.deepcopy(tree))
            return tree
        with patch('tools.bot_optimizer.compiler.EdgeAlgebra.apply', capture):
            optimize_source(self.source())
        source, = captured
        unproven = copy.deepcopy(source)
        for node in ast.walk(unproven):
            if getattr(node, '_bcopt_edge_integer_tables', False):
                del node._bcopt_edge_integer_tables
        pass_ = EdgeAlgebra(Options())
        pass_.apply(unproven)
        self.assertTrue(any(c.pass_name == 'insertion-edge-algebra' for c in pass_.changes))
        self.assertFalse(any(c.pass_name == 'insertion-edge-native-certificate' for c in pass_.changes))
        for mutation in ('escape', 'index', 'snapshot', 'axis', 'contract', 'producer'):
            tree = copy.deepcopy(source)
            consumer, = [node for node in tree.body if getattr(node, '_bcopt_fused_consumer', False)]
            version, = [node for node in ast.walk(consumer) if getattr(node, '_bcopt_prepared_dispatch', False)]
            update = next(node for statement in version.body for node in ast.walk(statement)
                          if getattr(node, '_bcopt_edge_algebra', None))
            fact = update._bcopt_edge_algebra
            if mutation == 'escape':
                version.body[0].body.append(ast.parse(f'observed = {fact["legs"]}').body[0])
            elif mutation == 'index':
                version.body[0].body.append(ast.parse(f'observed = {fact["legs"]}[1]').body[0])
            elif mutation == 'snapshot':
                version.body[0].body.append(ast.parse(f'{fact["matrix"]} = ()').body[0])
            elif mutation == 'axis':
                version.body[0].body.append(ast.parse(f'{fact["axis"]} = 1').body[0])
            elif mutation == 'contract':
                del update._bcopt_edge_algebra
            else:
                producer = next(node for node in ast.walk(consumer) if getattr(node, '_bcopt_fused_insertion', None))
                del producer._bcopt_fused_insertion
            pass_ = EdgeAlgebra(Options())
            pass_.apply(tree)
            self.assertFalse(pass_.changes, mutation)
        tree = ast.parse(ast.unparse(source))
        before = ast.dump(tree)
        self.assertEqual(before, ast.dump(EdgeAlgebra(Options()).apply(tree)))


if __name__ == '__main__':
    unittest.main()
