import ast
import copy
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.entry_inlining import InlineNumericEntries
from tools.bot_optimizer.tests.test_regions import SOURCE, CONSUMER, CALLER, normalized_result
from tools.bot_optimizer.tests.test_specialization import execute


class EntryInliningTests(unittest.TestCase):
    def test_prepared_versions_keep_partial_preparation_and_skipped_errors(self):
        evaluator = SOURCE.replace('self.items[i].duration*weights.values[i]',
                                   'self.items[i].duration/weights.values[i]')
        for route in ('(0,)', '(1,)', '()'):
            source = evaluator+CONSUMER.replace('route=(index,)', f'route={route}')+CALLER
            compiled = optimize_source(source)
            self.assertTrue(any(change.pass_name == 'numeric-prepared-versions' for change in compiled.changes))
            for weights in (None, (0.0, 2.0), (1.0, 2.0)):
                outcomes = []
                for text in (source, compiled.source):
                    ns = execute(text)
                    items = [ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)]
                    weight = ns['Weights'](weights) if weights is not None else None
                    try:
                        outcomes.append(normalized_result(ns['run'](items, [[2, 3], [5, 7]], weight, 2)))
                    except Exception as error:
                        outcomes.append((type(error).__name__, str(error)))
                self.assertEqual(*outcomes)

    def test_prepared_version_needs_both_emitter_contracts(self):
        protected = ast.parse('try:\n    value = 1 / 0 if table is None else table[0]\nexcept IndexError:\n    value = None').body[0]
        load = ast.parse('table = data[0]').body[0]
        pass_ = InlineNumericEntries(Options())
        self.assertIsNone(pass_.prepared_version(protected, [load]))
        protected.body[0].value.test._bcopt_prepared_test = True
        self.assertIsNone(pass_.prepared_version(protected, [load]))
        load._bcopt_prepared_table = True
        self.assertIsNotNone(pass_.prepared_version(protected, [load]))
        disabled = InlineNumericEntries(Options(disabled=frozenset({'numeric-prepared-versions'})))
        self.assertIsNone(disabled.prepared_version(protected, [load]))

    def compare(self, source, weights=True):
        compiled = optimize_source(source)
        original, optimized = execute(source), execute(compiled.source)
        values = []
        for ns in (original, optimized):
            items = [ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)]
            weight = ns['Weights']((0.1, 0.9)) if weights else None
            values.append(normalized_result(ns['run'](items, [[2, 3], [5, 7]], weight, 2)))
        self.assertEqual(*values)
        return compiled

    def test_parameter_rebinding_does_not_rebind_consumer_local(self):
        source = SOURCE.replace('        items=self.items', '        selector=selector+1\n        items=self.items')
        source = source.replace('value=self.matrix[selector][route[0]]', 'value=self.matrix[0][route[0]]')
        consumer = CONSUMER.replace('evaluate(route, 0)', 'evaluate(route, index)')
        compiled = self.compare(source+consumer+CALLER)
        self.assertTrue(any(change.pass_name == 'numeric-entry-inline' for change in compiled.changes))

    def test_global_name_cannot_be_captured_by_consumer_local(self):
        source = 'ADJUST=1\n'+SOURCE.replace('selector+1', 'selector+ADJUST')
        consumer = CONSUMER.replace('        evaluate=self.evaluate', '        ADJUST=9\n        evaluate=self.evaluate')
        compiled = self.compare(source+consumer+CALLER)
        self.assertFalse(any(change.pass_name == 'numeric-entry-inline' for change in compiled.changes))

    def test_optional_snapshot_field_is_not_dereferenced_early(self):
        source = SOURCE.replace('score=self.weighted(route)+ratio+value',
                                'weighted=self.weighted(route)\n        score=weighted+ratio+value')
        compiled = self.compare(source+CONSUMER+CALLER, weights=False)
        self.assertTrue(any(change.pass_name == 'numeric-entry-inline' for change in compiled.changes))

    def test_repeated_inputs_still_return_distinct_records(self):
        source = SOURCE+CONSUMER.replace('route=(index,)', 'route=(0,)')+CALLER
        compiled = self.compare(source)
        ns = execute(compiled.source)
        records = ns['run']([ns['Item'](2, 3, 5, 7)], [[2]], None, 2)
        self.assertEqual(len(records), 2)
        self.assertIsNot(records[0], records[1])
        self.assertEqual(records[0], records[1])
        object.__setattr__(records[0], 'red', 99)
        self.assertEqual(records[1].red, 2)

    def test_missing_emitter_contract_and_unproven_root_index(self):
        source = '''failed=object()
def worker(data, flag):
    try:
        if flag:
            return 7
        row=data[1]
        return row[0]
    except IndexError:
        return failed
def consumer(state, flag):
    data=state
    live=True
    result=worker(data, flag) if live else worker(data, flag)
    return result
'''
        tree = ast.parse(source)
        unchanged = InlineNumericEntries(Options())
        self.assertEqual(ast.dump(tree), ast.dump(unchanged.apply(copy.deepcopy(tree))))
        self.assertFalse(unchanged.changes)
        worker, consumer = tree.body[1:]
        worker._bcopt_numeric_clone = True
        worker._bcopt_index_retry = ('IndexError', 'failed')
        consumer._bcopt_numeric_consumer = ('data', 1)
        consumer.body[1]._bcopt_consumer_ready = True
        consumer.body[2]._bcopt_numeric_assignment = True
        pass_ = InlineNumericEntries(Options())
        emitted = pass_.apply(tree)
        self.assertEqual(len(pass_.changes), 1)
        ns = {}
        exec(compile(emitted, '<emitted>', 'exec'), ns)
        self.assertEqual(ns['consumer'](((),), True), 7)
        self.assertIs(ns['consumer'](((),), False), ns['failed'])


if __name__ == '__main__':
    unittest.main()
