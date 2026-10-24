import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.losing_stores import LosingStores
from tools.bot_optimizer.tests.test_insertion_keys import PRODUCER, CONSUMER, InsertionKeyTests
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE
from tools.bot_optimizer.tests.test_regions import CALLER
from tools.bot_optimizer.tests.test_specialization import execute


def source():
    base = SOURCE.replace('class Engine:', '''@dataclass(frozen=True)
class Candidate:
    route: tuple[int,...]
    evaluation: Result
class Engine:''')
    consumer = CONSUMER.replace('results={}', 'results={0:{}}\n        selection=0')
    consumer = consumer.replace('            value=evaluate(route, 0)\n            index+=1',
                                '            index+=1\n            value=evaluate(route, 0)')
    consumer = consumer.replace('            previous=results.get(key)',
                                '            bucket=results[selection]\n            previous=bucket.get(key)')
    consumer = consumer.replace('previous.score', 'previous.evaluation.score')
    consumer = consumer.replace('results[key]=value', 'bucket[key]=Candidate(route,value)')
    consumer = consumer.replace('sorted(results.values(),key=lambda value:value.score',
                                'sorted(results[0].values(),key=lambda value:value.evaluation.score')
    return PRODUCER+base+consumer+CALLER


class LosingStoreTests(unittest.TestCase):
    def test_generic_selection_ties_nans_and_actual_omitted_stores(self):
        text = source()
        compiled = optimize_source(text)
        self.assertTrue(any(c.pass_name == 'losing-record-stores' for c in compiled.changes))
        self.assertTrue(any(c.pass_name == 'losing-record-lookup-reuse' for c in compiled.changes))
        helper = InsertionKeyTests()
        helper.compare(text, compiled)
        helper.compare(text, compiled, limit=3)
        helper.compare(text, compiled, stopped=True)
        for expression in ('0.0', '-0.0', '1e309 - 1e309', '1e309'):
            changed = text.replace('self.weighted(route)+ratio+value', expression+'+self.weighted(route)*0.0')
            result = optimize_source(changed)
            helper.compare(changed, result)
        tree = ast.parse(compiled.source)
        probes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id.startswith('_bcopt_losing_keep'):
                node.value = ast.Call(func=ast.Name(id='_observe', ctx=ast.Load()), args=[node.value], keywords=[])
                probes.append(node)
        self.assertEqual(len(probes), 1)
        ns = execute(ast.unparse(ast.fix_missing_locations(tree)))
        decisions = []
        ns['_observe'] = lambda value: (decisions.append(value), value)[1]
        items = [ns['Item'](2,3,5,7), ns['Item'](11,13,17,19)]
        ns['run'](items, [[2,3],[5,7]], ns['Weights']((0.1,0.9)), 2)
        self.assertIn(False, decisions)
        self.assertIn(True, decisions)

    def test_observed_result_changed_comparison_and_disabled_proofs(self):
        for text in (source().replace('            key=frozenset(route)', '            prior=value\n            key=frozenset(route)'),
                     source().replace('value.score > previous.evaluation.score', 'value.score >= previous.evaluation.score'),
                     source().replace('results={0:{}}', 'results={0:{frozenset(()):Candidate((),Result(0,0,0,0,0.0))}}'),
                     source().replace('            previous=bucket.get(key)', '            alias=bucket\n            previous=bucket.get(key)')):
            compiled = optimize_source(text)
            self.assertFalse(any(c.pass_name == 'losing-record-stores' for c in compiled.changes))
            self.assertFalse(any(c.pass_name == 'losing-record-lookup-reuse' for c in compiled.changes))
            InsertionKeyTests().compare(text, compiled)
        for disabled in ('losing-record-stores', 'numeric-entry-inline', 'numeric-prepared-versions',
                         'record-inline-return', 'insertion-invariant-keys', 'insertion-producer-fusion'):
            compiled = optimize_source(source(), Options(disabled=frozenset({disabled})))
            self.assertFalse(any(c.pass_name == 'losing-record-stores' for c in compiled.changes), disabled)
            InsertionKeyTests().compare(source(), compiled)

    def test_lookup_reuse_disabled_and_finally_release(self):
        text = source()
        compiled = optimize_source(text, Options(disabled=frozenset({'losing-record-lookup-reuse'})))
        self.assertTrue(any(c.pass_name == 'losing-record-stores' for c in compiled.changes))
        self.assertFalse(any(c.pass_name == 'losing-record-lookup-reuse' for c in compiled.changes))
        InsertionKeyTests().compare(text, compiled)
        enabled = optimize_source(text)
        tree = ast.parse(enabled.source)
        cleanup = [n for n in ast.walk(tree) if isinstance(n, ast.Try) and n.finalbody
                   and any(isinstance(x, ast.Delete) and any(isinstance(t, ast.Name)
                           and t.id.startswith('_bcopt_losing_previous') for t in x.targets) for x in n.finalbody)]
        self.assertEqual(len(cleanup), 1)

    def test_missing_and_perturbed_emitter_proofs_reject(self):
        captured = []
        def capture(pass_, tree):
            captured.append(copy.deepcopy(tree))
            return tree
        with patch('tools.bot_optimizer.compiler.LosingStores.apply', capture):
            optimize_source(source())
        original, = captured
        for change in ('entry', 'record', 'store', 'lookup', 'comparison', 'escape'):
            tree = copy.deepcopy(original)
            entry = next(n for n in ast.walk(tree) if getattr(n, '_bcopt_losing_entry', None) and isinstance(n, ast.If))
            version = next(n for n in ast.walk(entry) if getattr(n, '_bcopt_prepared_dispatch', False))
            alloc = next(n for statement in version.body for n in ast.walk(statement) if getattr(n, '_bcopt_complete_record', None))
            if change == 'entry':
                del entry._bcopt_losing_entry
            elif change == 'record':
                del alloc._bcopt_complete_record
            elif change in {'store', 'escape'}:
                parent = next(n for statement in version.body for n in ast.walk(statement) if alloc in getattr(n, 'body', []))
                index = parent.body.index(alloc)
                if change == 'store':
                    parent.body[index+2].targets[0].slice = ast.Constant('wrong')
                else:
                    parent.body.append(ast.parse(f'observed={alloc.targets[0].id}').body[0])
            else:
                role = 'lookup' if change == 'lookup' else 'select'
                node = next(n for n in ast.walk(tree) if getattr(n, '_bcopt_losing_role', (None,None))[1] == role)
                if change == 'lookup':
                    node.value.args.append(ast.Constant(0))
                else:
                    node.test.values[1].ops[0] = ast.GtE()
            transform = LosingStores(Options())
            transform.apply(tree)
            self.assertFalse(transform.changes, change)
        plain = ast.parse(ast.unparse(original))
        transform = LosingStores(Options())
        transform.apply(plain)
        self.assertFalse(transform.changes)


if __name__ == '__main__':
    unittest.main()
