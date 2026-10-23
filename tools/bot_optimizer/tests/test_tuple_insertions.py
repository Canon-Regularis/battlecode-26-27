import gc
import inspect
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''def run(route, item):
    for position in range(len(route)+1):
        yield route[:position]+(item,)+route[position:]
'''


class TupleInsertionTests(unittest.TestCase):
    def functions(self, source=SOURCE):
        result = optimize_source(source)
        self.assertIn('tuple-insertion-buffer', [c.pass_name for c in result.changes])
        return execute(source)['run'], execute(result.source)['run']

    def test_values_identity_and_source_signature(self):
        old, new = self.functions()
        self.assertEqual(inspect.signature(old), inspect.signature(new))
        for size in (0, 1, 4, 8, 16, 40):
            route, item = tuple(object() for _ in range(size)), object()
            before, after = tuple(old(route, item)), tuple(new(route, item))
            self.assertEqual(before, after)
            for position, row in enumerate(after):
                self.assertIs(type(row), tuple)
                self.assertIs(row[position], item)
                self.assertIsNot(row, route)

    def test_nested_insertion_loop_and_send(self):
        source = '''def run(route, count):
    for item in range(count):
        if item in route:
            continue
        for position in range(len(route)+1):
            yield route[:position]+(item,)+route[position:]
'''
        old, new = self.functions(source)
        self.assertEqual(list(old((1,3), 5)), list(new((1,3), 5)))
        for function in (old,new):
            gen = function((1,3), 5)
            self.assertEqual(next(gen), (0,1,3))
            self.assertEqual(gen.send(object()), (1,0,3))
            gen.close()

    def test_close_throw_and_exhaustion_lifetimes(self):
        for mode in ('unstarted', 'close', 'throw', 'stop', 'exhaust'):
            outcomes = []
            for function in self.functions():
                events = []
                class Value:
                    def __init__(self, label):
                        self.label = label
                    def __del__(self):
                        events.append(self.label)
                gen = function((Value('a'), Value('b')), Value('item'))
                saved = None
                if mode != 'unstarted':
                    row = next(gen)
                    del row
                if mode in ('throw','stop'):
                    try:
                        gen.throw(ValueError('injected') if mode == 'throw' else StopIteration('injected'))
                    except (ValueError, RuntimeError) as error:
                        saved = error
                        events.append(('caught', type(error).__name__, type(error.__cause__).__name__))
                elif mode == 'exhaust':
                    for row in gen:
                        pass
                    del row
                else:
                    gen.close()
                events.append('after')
                del gen, saved
                gc.collect()
                outcomes.append(events)
            self.assertEqual(*outcomes, mode)

    def test_custom_tuple_protocol_and_list_error_fallback(self):
        outcomes = []
        for function in self.functions():
            events = []
            class Route(tuple):
                def __len__(self):
                    events.append('len')
                    return super().__len__()
                def __getitem__(self, index):
                    events.append(('get', repr(index)))
                    return super().__getitem__(index)
            rows = list(function(Route((1,2)), 3))
            try:
                next(function([1,2], 3))
            except TypeError as error:
                events.append(('error', str(error)))
            outcomes.append((rows,events))
        self.assertEqual(*outcomes)

    def test_buffer_cleanup_precedes_unrelated_local_finalizers(self):
        source = SOURCE.replace('def run(route, item):', 'def run(route, item, make):\n    token = make()')
        outcomes = []
        for function in self.functions(source):
            events = []
            class Value:
                def __init__(self, label):
                    self.label = label
                def __del__(self):
                    events.append(self.label)
            gen = function((Value('a'), Value('b')), Value('item'), lambda: Value('token'))
            next(gen)
            gen.close()
            del gen
            outcomes.append(events)
        self.assertEqual(*outcomes)

    def test_rebinding_shadowing_and_unsupported_patterns(self):
        sources = [
            SOURCE.replace('def run(route, item):', 'def run(route, item, range):'),
            SOURCE.replace('def run(route, item):', 'def run(route, item, len):'),
            SOURCE.replace('    for position', '    route = tuple(route)\n    for position'),
            SOURCE.replace('    for position', '    def mutate():\n        nonlocal route\n        route=()\n    for position'),
            SOURCE.replace('        yield', '        value = yield'),
            SOURCE.replace('route[position:]', 'route[position+1:]'),
            SOURCE.replace('(item,)', '(item(),)'),
        ]
        for source in sources:
            self.assertNotIn('tuple-insertion-buffer', [c.pass_name for c in optimize_source(source).changes])
        result = optimize_source(SOURCE, Options(disabled=frozenset({'tuple-insertion-buffer'})))
        self.assertFalse(result.changes)
