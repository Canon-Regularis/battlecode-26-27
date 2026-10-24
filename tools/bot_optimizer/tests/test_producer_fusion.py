import ast
import inspect
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.producer_fusion import ProducerFusion
from tools.bot_optimizer.tests.test_insertion_keys import PRODUCER, CONSUMER
from tools.bot_optimizer.tests.test_numeric_regions import SOURCE, normalized
from tools.bot_optimizer.tests.test_regions import CALLER
from tools.bot_optimizer.tests.test_specialization import execute


class ProducerFusionTests(unittest.TestCase):
    def source(self, consumer=CONSUMER, producer=PRODUCER):
        return producer+SOURCE+consumer+CALLER

    def compare(self, source, *, limit=2, after=1000, action='stop', disabled=(), active=True):
        compiled = optimize_source(source, Options(disabled=frozenset(disabled)))
        self.assertEqual(any(c.pass_name == 'insertion-producer-fusion' for c in compiled.changes), active)
        outcomes = []
        for text, fast in ((source, False), (compiled.source, True)):
            ns = execute(text)
            owner = ns['Engine']([ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)],
                                 [[2, 3], [5, 7]], ns['Weights']((0.1, 0.9)))
            calls = []
            def stop():
                index = len(calls)
                calls.append(index)
                if index != after:
                    return False
                if action == 'throw':
                    raise RuntimeError('stop callback')
                if action == 'mutate':
                    owner.matrix[0][0] += 10
                return True
            kwargs = dict(stop=stop, limit=limit)
            if fast:
                enter, = [value for name, value in ns.items() if name.startswith('_bcopt_region_enter_')]
                consumer, = [value for name, value in ns.items() if name.startswith('_bcopt_region_consumer_')]
                state = enter(owner.search)
                self.assertIsNotNone(state)
                param, = [name for name in inspect.signature(consumer).parameters if name.startswith('_bcopt_region_state_')]
                kwargs[param] = state
            try:
                rows = consumer(owner, **kwargs) if fast else owner.search(**kwargs)
                result = [normalized(row) for row in rows]
            except Exception as error:
                result = (type(error).__name__, str(error))
            outcomes.append((result, calls, owner.matrix))
        self.assertEqual(*outcomes)
        return compiled

    def test_nonempty_duplicates_negative_indices_and_buffer_fallbacks(self):
        for base in ('[]', '[0]', '[0,0]', '[-1,0]'):
            source = self.source(CONSUMER.replace('[0, 0]', base))
            for limit in (-2, 0, 2, 3):
                self.compare(source, limit=limit)
        for disabled in ('tuple-insertion-buffer', 'tuple-insertion-hoist'):
            self.compare(self.source(), disabled=(disabled,))

    def test_nested_control_early_return_and_callback_effects(self):
        nested = CONSUMER.replace('            index+=1',
            '            for turn in range(2):\n                if turn:\n                    break\n                continue\n            index+=1')
        self.compare(self.source(nested))
        early = CONSUMER.replace('            index+=1',
            '            index+=1\n            if index == 4:\n                return self.rank(results)')
        self.compare(self.source(early))
        # Reenter another base after a true callback so the dirty fallback runs.
        outer = CONSUMER.replace('        for route in variations(tuple([0, 0]), limit):',
                                '        for base in [tuple([0,0]),tuple([0])]:\n            for route in variations(base, limit):')
        start = outer.index('            if index % 2')
        end = outer.index('        return self.rank(results)')
        outer = outer[:start] + '\n'.join('    '+line for line in outer[start:end].splitlines())+'\n'+outer[end:]
        for action in ('stop', 'throw', 'mutate'):
            for after in (0, 1, 3):
                self.compare(self.source(outer), after=after, action=action)

    def test_fresh_route_aliases_and_proof_rejections(self):
        consumer = CONSUMER.replace('        prior=None', '        prior=None\n        routes={}').replace(
            '            value=evaluate(route, 0)', '            routes[index]=route\n            value=evaluate(route, 0)').replace(
            '        return self.rank(results)', '        return list(routes.values())')
        compiled = self.compare(self.source(consumer))
        ns = execute(compiled.source)
        rows = ns['run']([ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)],
                         [[2, 3], [5, 7]], ns['Weights']((0.1, 0.9)), 2)
        self.assertEqual(len({id(row) for row in rows}), len(rows))
        self.compare(self.source(), disabled=('insertion-producer-fusion',), active=False)
        # A producer's global builtin must not become a consumer local capture.
        consumer = CONSUMER.replace('        prior=None', '        prior=None\n        range=7')
        self.compare(self.source(consumer), active=False)
        # Even unused parameters can have observable lifetimes; no fusion proof.
        producer = PRODUCER.replace('def variations(base, count):', 'def variations(base, count, extra=0):')
        self.compare(self.source(producer=producer), active=False)
        tree = ast.parse(self.source())
        before = ast.dump(tree)
        self.assertEqual(before, ast.dump(ProducerFusion(Options()).apply(tree)))


if __name__ == '__main__':
    unittest.main()
