import ast
import unittest

from tools.bot_optimizer.consumer_regions import ConsumerProof
from tools.bot_optimizer.numeric_regions import NumericClones, Unsupported
from tools.bot_optimizer.program import Program
from tools.bot_optimizer.region_types import RegionSchemas
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE


CONSUMER = '''
    def search(self, *, stop, limit: int):
        evaluate=self.evaluate
        results={}
        for index in range(limit):
            if index > 100 or (index % 2 == 0 and stop()):
                break
            route=(index,)
            value=evaluate(route, 0)
            if value is None:
                continue
            previous=results.get(index)
            if previous is None or value.score > previous.score:
                results[index]=value
        return self.rank(results)
    def rank(self,results):
        return sorted(results.values(),key=lambda value:value.score,reverse=True)
'''


class ConsumerRegionTests(unittest.TestCase):
    def prove(self, consumer=CONSUMER):
        program = Program({'example': ast.parse(SOURCE+consumer)})
        schemas = RegionSchemas(program)
        builder = NumericClones(program, schemas, schemas.owner('example.Engine'))
        entry = builder.entry('evaluate')
        return ConsumerProof(builder, entry).consumer('search', 'stop')

    def test_owned_dictionary_aliases_and_helpers_are_closed(self):
        proof = self.prove()
        self.assertEqual(proof.methods, {'search', 'rank', 'evaluate', 'weighted'})
        self.assertEqual(len(proof.numeric_calls), 1)
        self.assertEqual(len(proof.callback_tests), 1)
        self.assertIn('example.Result', proof.records)

    def test_unknown_effects_and_borrowed_mutation_decline(self):
        for statement in ('unknown()', 'self.items=[]', 'self.items[0]=value',
                          'self.items.append(value)', 'stop()'):
            with self.subTest(statement=statement), self.assertRaises(Unsupported):
                self.prove(CONSUMER.replace('        return self.rank(results)',
                                            f'        {statement}\n        return self.rank(results)'))

    def test_callback_must_imply_true_branch(self):
        for condition in ('not stop()', 'stop() and index > 0', 'stop() == False'):
            with self.subTest(condition=condition), self.assertRaises(Unsupported):
                self.prove(CONSUMER.replace('index > 100 or (index % 2 == 0 and stop())', condition))

    def test_numeric_arguments_cannot_use_annotation_as_proof(self):
        with self.assertRaises(Unsupported):
            self.prove(CONSUMER.replace('route=(index,)', 'route=(1.0,)'))
        with self.assertRaises(Unsupported):
            self.prove(CONSUMER.replace('route=(index,)', 'route=self.empty()')+
                       '\n    def empty(self):\n        pass\n')

    def test_unknown_helper_and_mutating_alias_decline(self):
        with self.assertRaises(Unsupported):
            self.prove(CONSUMER.replace('return sorted(results.values(),key=lambda value:value.score,reverse=True)',
                                        'return mystery(results)'))
        with self.assertRaises(Unsupported):
            self.prove(CONSUMER.replace('        results={}', '        results=self.items'))
        with self.assertRaises(Unsupported):
            self.prove(CONSUMER.replace('def rank(self,results):', 'def rank(self,results,shared=[]):'))

    def test_continue_backedge_must_not_lose_rebound_type(self):
        source = CONSUMER.replace('        results={}', '        results={}\n        bound=limit').replace(
            '            value=evaluate(route, 0)',
            '            size=bound+1\n            if index:\n                bound=self.items\n                continue\n            bound=limit\n            value=evaluate(route, 0)')
        with self.assertRaises(Unsupported):
            self.prove(source)


if __name__ == '__main__':
    unittest.main()
