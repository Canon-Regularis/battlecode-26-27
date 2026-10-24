import ast
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.insertion_keys import InsertionKeys
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE, normalized
from tools.bot_optimizer.tests.test_regions import CALLER
from tools.bot_optimizer.tests.test_specialization import execute


PRODUCER = '''
def variations(base, count):
    for added in range(-1, count):
        for slot in range(len(base)+1):
            yield base[:slot]+(added,)+base[slot:]
'''
CONSUMER = '''
    def search(self, *, stop, limit: int):
        evaluate=self.evaluate
        results={}
        index=0
        prior=None
        for route in variations(tuple([0, 0]), limit):
            if index % 2 == 0 and stop():
                break
            value=evaluate(route, 0)
            index+=1
            if value is None:
                continue
            key=frozenset(route)
            previous=results.get(key)
            if previous is None or value.score > previous.score:
                results[key]=value
        return self.rank(results)
    def rank(self, results):
        return sorted(results.values(),key=lambda value:value.score,reverse=True)
'''


class InsertionKeyTests(unittest.TestCase):
    def compile(self, consumer=CONSUMER, producer=PRODUCER, disabled=()):
        # Define the producer before the owner; its identity is guarded at entry.
        source = producer+SOURCE+consumer+CALLER
        compiled = optimize_source(source, Options(disabled=frozenset(disabled)))
        return source, compiled

    def compare(self, source, compiled, limit=2, stopped=False):
        outcomes = []
        for text in (source, compiled.source):
            ns = execute(text)
            if stopped:
                ns['REMAINING'] = 0
            try:
                items = [ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)]
                records = ns['run'](items, [[2, 3], [5, 7]], ns['Weights']((0.1, 0.9)), limit)
                outcomes.append([normalized(value) for value in records])
            except Exception as error:
                outcomes.append((type(error).__name__, str(error)))
        self.assertEqual(*outcomes)

    def test_generic_names_duplicate_negative_indices_and_public_generator(self):
        source, compiled = self.compile()
        self.assertTrue(any(change.pass_name == 'insertion-invariant-keys' for change in compiled.changes))
        self.compare(source, compiled)
        self.compare(source, compiled, limit=3)  # Native index retry preserves the source error.
        self.compare(source, compiled, stopped=True)
        ns = execute(compiled.source)
        producer, = [node.name for node in ast.parse(compiled.source).body
                     if isinstance(node, ast.FunctionDef) and node.name.startswith('_bcopt_insertion_key_producer')]
        actual = list(ns[producer]((0, 0), 2))
        expected = list(ns['variations']((0, 0), 2))
        self.assertEqual([row[0] for row in actual], expected)
        for route, key, members, *private_state in actual:
            self.assertEqual(key, tuple(sorted(route)))
            self.assertEqual(members, frozenset(route))
        self.assertIs(actual[0][1], actual[1][1])
        self.assertIs(actual[0][2], actual[1][2])
        self.assertIsNot(actual[0][0], actual[1][0])
        self.assertEqual(actual[0][1], (-1, 0, 0))
        # Public generator continues to yield only the original tuples, even for
        # payloads that do not satisfy the private consumer's integer proof.
        marker = object()
        self.assertIs(next(ns['variations']((marker,), 0))[1], marker)

    def test_observed_identity_iteration_and_escape_disable_set_sharing(self):
        variants = [
            CONSUMER.replace('            previous=results.get(key)',
                '            if prior is key:\n                break\n            prior=key\n            previous=results.get(key)'),
            CONSUMER.replace('            previous=results.get(key)',
                '            for member in key:\n                index+=member\n            previous=results.get(key)'),
            CONSUMER.replace('        prior=None', '        prior=None\n        key=frozenset(())')
                    .replace('        return self.rank(results)', '        return [key]'),
        ]
        for consumer in variants:
            source, compiled = self.compile(consumer=consumer)
            self.assertTrue(any(change.pass_name == 'insertion-invariant-keys' for change in compiled.changes))
            self.compare(source, compiled)
            ns = execute(compiled.source)
            producer, = [node.name for node in ast.parse(compiled.source).body
                         if isinstance(node, ast.FunctionDef) and node.name.startswith('_bcopt_insertion_key_producer')]
            row = next(ns[producer]((0,), 2))
            self.assertIs(type(row[1]), tuple)
            self.assertFalse(any(type(value) is frozenset for value in row[2:]))

    def test_fallback_without_buffer_optimization_and_generator_cleanup(self):
        source, compiled = self.compile(disabled=('tuple-insertion-buffer',))
        self.compare(source, compiled)
        ns = execute(compiled.source)
        producer, = [node.name for node in ast.parse(compiled.source).body
                     if isinstance(node, ast.FunctionDef) and node.name.startswith('_bcopt_insertion_key_producer')]
        generator = ns[producer]((0, 0), 2)
        next(generator)
        generator.close()
        self.assertIsNone(generator.gi_frame)
        generator = ns[producer]((0, 0), 2)
        next(generator)
        with self.assertRaisesRegex(RuntimeError, 'stop'):
            generator.throw(RuntimeError('stop'))
        self.assertIsNone(generator.gi_frame)

    def test_position_dependent_item_and_missing_contract_are_rejected(self):
        source, compiled = self.compile(producer=PRODUCER.replace('(added,)', '(slot,)'))
        self.assertFalse(any(change.pass_name == 'insertion-invariant-keys' for change in compiled.changes))
        tree = ast.parse(source)
        pass_ = InsertionKeys(Options())
        before = ast.dump(tree)
        self.assertEqual(before, ast.dump(pass_.apply(tree)))
        self.assertFalse(pass_.changes)

    def test_unique_key_guard_preserves_multiplicity_and_negative_indices(self):
        source, compiled = self.compile()
        self.assertTrue(any(change.pass_name == 'insertion-unique-keys' for change in compiled.changes))
        ns = execute(compiled.source)
        producer, = [node.name for node in ast.parse(compiled.source).body
                     if isinstance(node, ast.FunctionDef) and node.name.startswith('_bcopt_insertion_key_producer')]
        kinds = set()
        for base in ((), (0,), (0, 0), (-1, 0), (-1, -1, 0)):
            for row in ns[producer](base, 2):
                route, key, members, *private = row
                unique = len(set(route)) == len(route)
                self.assertIs(type(key), frozenset if unique else tuple)
                self.assertEqual(key, frozenset(route) if unique else tuple(sorted(route)))
                if unique:
                    self.assertIs(key, members)
                kinds.add(type(key))
        self.assertEqual(kinds, {tuple, frozenset})
        source, disabled = self.compile(disabled=('insertion-unique-keys',))
        self.assertFalse(any(change.pass_name == 'insertion-unique-keys' for change in disabled.changes))
        self.compare(source, disabled)


if __name__ == '__main__':
    unittest.main()
