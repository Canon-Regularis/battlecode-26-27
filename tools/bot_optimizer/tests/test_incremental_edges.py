import ast
import unittest

from tools.bot_optimizer import optimize_source, Options
from tools.bot_optimizer.incremental_edges import IncrementalEdges
from tools.bot_optimizer.tests.test_insertion_keys import PRODUCER, CONSUMER
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE, normalized
from tools.bot_optimizer.tests.test_regions import CALLER
from tools.bot_optimizer.tests.test_specialization import execute


EDGES = '''        matrix=self.matrix
        first,last=route[0],route[-1]
        edges=[matrix[selector][first],matrix[selector][last]]
        edges.extend(matrix[a][b] for a,b in zip(route,route[1:]))
        if any(value < 0 for value in edges):
            return None
'''


class IncrementalEdgeTests(unittest.TestCase):
    def source(self, consumer=CONSUMER, edges=EDGES):
        evaluator = SOURCE.replace('        items=self.items', edges+'        items=self.items')
        evaluator = evaluator.replace('score=self.weighted(route)+ratio+value',
                                      'score=self.weighted(route)+ratio+value+sum(edges)')
        return PRODUCER+evaluator+consumer+CALLER

    def compare(self, source, matrix, limit=2):
        compiled = optimize_source(source)
        values = []
        for text in (source, compiled.source):
            ns = execute(text)
            items = [ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)]
            try:
                records = ns['run'](items, matrix, ns['Weights']((0.1, 0.9)), limit)
                values.append([normalized(row) for row in records])
            except Exception as error:
                values.append((type(error).__name__, str(error)))
        self.assertEqual(*values)
        return compiled

    def test_rolling_edges_keep_duplicate_negative_indices_and_error_order(self):
        for matrix in ([[2, 3], [5, 7]], [[2, -3], [5, 7]], [[2, 3], [-5, 7]],
                       [[2], [5, 7]], [], [[10**100, 3], [5, 7]]):
            compiled = self.compare(self.source(), matrix)
            self.assertTrue(any(change.pass_name == 'insertion-incremental-edges' for change in compiled.changes))
        self.compare(self.source(), [[2, 3], [5, 7]], limit=3)

    def test_changing_endpoint_axis_and_skipped_positions_rebuild(self):
        consumer = CONSUMER.replace('value=evaluate(route, 0)', 'selector=index % 2\n            value=evaluate(route, selector)')
        compiled = self.compare(self.source(consumer=consumer), [[2, 3], [11, 17]])
        self.assertTrue(any(change.pass_name == 'insertion-incremental-edges' for change in compiled.changes))
        consumer = CONSUMER.replace('            value=evaluate(route, 0)',
            '            index+=1\n            if index % 3 == 0:\n                continue\n            value=evaluate(route, 0)')
        self.compare(self.source(consumer=consumer), [[2, 3], [11, 17]])

    def test_only_proven_invariants_omit_runtime_context_guards(self):
        def context_guards(compiled):
            return [node for node in ast.walk(ast.parse(compiled.source))
                    if isinstance(node, ast.Compare) and isinstance(node.left, ast.Subscript)
                    and isinstance(node.left.value, ast.Name) and node.left.value.id.startswith('_bcopt_edge_state')
                    and isinstance(node.left.slice, ast.Constant) and node.left.slice.value >= 2]
        consumer = CONSUMER.replace('        prior=None', '        prior=None\n        selection=0')
        consumer = consumer.replace('value=evaluate(route, 0)', 'value=evaluate(route, selection)')
        constant = self.compare(self.source(consumer=consumer), [[2, 3], [11, 17]])
        self.assertFalse(context_guards(constant))
        consumer = CONSUMER.replace('value=evaluate(route, 0)',
                                   'selector=index % 2\n            value=evaluate(route, selector)')
        changing = self.compare(self.source(consumer=consumer), [[2, 3], [11, 17]])
        self.assertTrue(context_guards(changing))

    def test_later_list_mutation_aliases_and_reversed_endpoints_reject(self):
        for edges in (EDGES+'        edges.append(11)\n', EDGES+'        other=edges\n',
                      EDGES.replace('first,last=route[0],route[-1]', 'first,last=route[-1],route[0]')):
            compiled = self.compare(self.source(edges=edges), [[2, 3], [5, 7]])
            self.assertFalse(any(change.pass_name == 'insertion-incremental-edges' for change in compiled.changes))

    def test_missing_contract_does_not_enable_transform(self):
        tree = ast.parse(self.source())
        before = ast.dump(tree)
        pass_ = IncrementalEdges(Options())
        self.assertEqual(before, ast.dump(pass_.apply(tree)))
        self.assertFalse(pass_.changes)


if __name__ == '__main__':
    unittest.main()
