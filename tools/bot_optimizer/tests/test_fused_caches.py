import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.fused_caches import FusedCaches
from tools.bot_optimizer.tests import test_group_scalars as group_cases
from tools.bot_optimizer.tests import test_incremental_edges as edge_cases


class FusedCacheTests(unittest.TestCase):
    def test_integrated_outputs_fallbacks_and_disabled_contracts(self):
        cases = group_cases.GroupScalarTests()
        compiled = cases.compare(cases.source())
        names = {change.pass_name for change in compiled.changes}
        self.assertTrue({'insertion-fused-cache-slots', 'insertion-resident-scalars'} <= names)
        cases.compare(cases.source(), red=10**400)
        cases.compare(cases.source(), limit=3)
        cases.compare(cases.source(), matrix=[[2], [5, 7]])
        cases.compare(cases.source(reward='1.0 / (red-red)'))
        cases.compare(cases.source(reward='red * 0.1'))
        for disabled in ('insertion-fused-cache-slots', 'insertion-producer-fusion'):
            result = cases.compare(cases.source(), disabled=(disabled,))
            self.assertFalse(any(change.pass_name == 'insertion-resident-scalars' for change in result.changes))
        result = cases.compare(cases.source(), disabled=('insertion-resident-scalars',))
        self.assertTrue(any(change.pass_name == 'insertion-fused-cache-slots' for change in result.changes))
        self.assertFalse(any(change.pass_name == 'insertion-resident-scalars' for change in result.changes))

    def before_caches(self, source=None):
        captured = []
        def capture(pass_, tree):
            captured.append(copy.deepcopy(tree))
            return tree
        with patch('tools.bot_optimizer.compiler.FusedCaches.apply', capture):
            optimize_source(source or group_cases.GroupScalarTests().source())
        self.assertEqual(len(captured), 1)
        return captured[0]

    def test_resident_proof_rejects_changed_selector_writes_and_flag_observation(self):
        source = self.before_caches()
        for change in ('selector', 'output', 'observe'):
            tree = copy.deepcopy(source)
            consumer, = [node for node in tree.body if getattr(node, '_bcopt_fused_consumer', False)]
            version, = [node for node in ast.walk(consumer) if getattr(node, '_bcopt_prepared_dispatch', False)]
            read = next(node for node in ast.walk(version) if getattr(node, '_bcopt_group_scalar_read', False))
            miss = next(node for node in ast.walk(version) if getattr(node, '_bcopt_group_scalar_miss', False) and node.orelse)
            if change == 'selector':
                statement = ast.parse(f'{version.test.id} = False').body[0]
            elif change == 'output':
                statement = ast.parse(f'{miss.orelse[0].targets[0].elts[0].id} = 0').body[0]
            else:
                statement = ast.Expr(value=ast.Name(id=read.targets[0].id, ctx=ast.Load()))
            version.body.append(statement)
            pass_ = FusedCaches(Options())
            pass_.apply(tree)
            self.assertTrue(any(c.pass_name == 'insertion-fused-cache-slots' for c in pass_.changes))
            self.assertFalse(any(c.pass_name == 'insertion-resident-scalars' for c in pass_.changes), change)

    def test_slot_proof_rejects_aliases_dynamic_indices_and_source_spelling(self):
        source = self.before_caches()
        for change in ('alias', 'index'):
            tree = copy.deepcopy(source)
            consumer, = [node for node in tree.body if getattr(node, '_bcopt_fused_consumer', False)]
            read = next(node for node in ast.walk(consumer) if getattr(node, '_bcopt_group_scalar_read', False))
            slot = read.value.value.id
            if change == 'alias':
                consumer.body.append(ast.parse(f'escape = {slot}').body[0])
            else:
                read.value.slice = ast.Name(id='index', ctx=ast.Load())
            pass_ = FusedCaches(Options())
            pass_.apply(tree)
            self.assertFalse(any(c.pass_name == 'insertion-resident-scalars' for c in pass_.changes))
            self.assertTrue(any(isinstance(node, ast.Name) and node.id == slot for node in ast.walk(consumer)))
        tree = ast.parse(ast.unparse(source))
        before = ast.dump(tree)
        self.assertEqual(before, ast.dump(FusedCaches(Options()).apply(tree)))

    def test_resident_edges_skip_rebuild_errors_and_changing_axis(self):
        cases = edge_cases.IncrementalEdgeTests()
        consumer = edge_cases.CONSUMER.replace('        prior=None', '        prior=None\n        selection=0').replace(
            'value=evaluate(route, 0)', 'value=evaluate(route, selection)')
        for matrix in ([[2, 3], [5, 7]], [[2, -3], [5, 7]], [[2], [5, 7]], [], [[10**100, 3], [5, 7]]):
            compiled = cases.compare(cases.source(consumer=consumer), matrix)
            self.assertTrue(any(c.pass_name == 'insertion-resident-edges' for c in compiled.changes))
        cases.compare(cases.source(consumer=consumer), [[2, 3], [5, 7]], limit=3)
        skipped = consumer.replace('            value=evaluate(route, selection)',
            '            index+=1\n            if index % 3 == 0:\n                continue\n            value=evaluate(route, selection)')
        compiled = cases.compare(cases.source(consumer=skipped), [[2, 3], [11, 17]])
        self.assertTrue(any(c.pass_name == 'insertion-resident-edges' for c in compiled.changes))
        varying = consumer.replace('            value=evaluate(route, selection)',
            '            selection=index % 2\n            value=evaluate(route, selection)')
        compiled = cases.compare(cases.source(consumer=varying), [[2, 3], [11, 17]])
        self.assertFalse(any(c.pass_name == 'insertion-resident-edges' for c in compiled.changes))
        compiled = optimize_source(cases.source(consumer=consumer), Options(disabled=frozenset({'insertion-resident-edges'})))
        self.assertFalse(any(c.pass_name == 'insertion-resident-edges' for c in compiled.changes))
        tree = self.before_caches(cases.source(consumer=consumer))
        function, = [node for node in tree.body if getattr(node, '_bcopt_fused_consumer', False)]
        version, = [node for node in ast.walk(function) if getattr(node, '_bcopt_prepared_dispatch', False)]
        update = next(node for node in ast.walk(function) if getattr(node, '_bcopt_edge_cache_update', False))
        edges = update.body[-1].value.elts[1].id
        version.body.append(ast.parse(f'{edges} = []').body[0])
        pass_ = FusedCaches(Options())
        pass_.apply(tree)
        self.assertFalse(any(c.pass_name == 'insertion-resident-edges' for c in pass_.changes))


if __name__ == '__main__':
    unittest.main()
