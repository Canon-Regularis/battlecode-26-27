import gc
import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''def run(target, rows, route):
    target.extend(rows[a][b] for a,b in zip(route,route[1:]))
    return target
'''


class ExtensionTests(unittest.TestCase):
    def functions(self, source=SOURCE):
        result = optimize_source(source)
        self.assertIn('adjacent-extend', [c.pass_name for c in result.changes])
        return execute(source)['run'], execute(result.source)['run']

    def test_empty_short_long_and_subclasses(self):
        class Tuple(tuple):
            pass
        class List(list):
            pass
        old, new = self.functions()
        rows = [list(range(20)) for _ in range(20)]
        for length in (0, 1, 4, 8, 9, 16):
            for route in (tuple(range(length)), list(range(length)), Tuple(range(length))):
                for target_type in (list, List):
                    self.assertEqual(old(target_type([99]), rows, route), new(target_type([99]), rows, route))

    def test_mutation_and_partial_extension(self):
        for mode in ('normal', 'mutate', 'error', 'stop'):
            outcomes = []
            for function in self.functions():
                events, target = [], []
                class Value:
                    def __init__(self, label):
                        self.label = label
                    def __del__(self):
                        events.append(('del', self.label))
                class Row:
                    def __init__(self, label):
                        self.label = label
                    def __getitem__(self, index):
                        events.append(('get', self.label, index, len(target)))
                        if self.label == 1:
                            if mode == 'stop':
                                raise StopIteration('index')
                            if mode == 'error':
                                raise ValueError('index')
                            if mode == 'mutate':
                                target.clear()
                        return Value(self.label)
                saved = None
                try:
                    function(target, [Row(i) for i in range(4)], (0, 1, 2, 3))
                except BaseException as error:
                    saved = error
                    events.append(('error', type(error).__name__, str(error), type(error.__cause__).__name__))
                events.append(('length', len(target)))
                target.clear()
                events.append('cleared')
                del saved
                gc.collect()
                outcomes.append(events)
            self.assertEqual(*outcomes, mode)

    def test_saved_traceback_owner_and_index_finalizers(self):
        source = SOURCE.replace('def run(target, rows, route):', 'def run(rows, route):\n    target = []')
        for primitive in (True, False):
            outcomes = []
            for function in self.functions(source):
                events = []
                class Index:
                    def __init__(self, number):
                        self.number = number
                    def __del__(self):
                        events.append(('index-del', self.number))
                class Rows:
                    def __getitem__(self, index):
                        number = index if type(index) is int else index.number
                        if number == 1:
                            raise ValueError('index')
                        return self
                    def __del__(self):
                        events.append('rows-del')
                saved = None
                try:
                    function(Rows(), tuple(range(4)) if primitive else tuple(Index(i) for i in range(4)))
                except ValueError as error:
                    saved = error
                events.append('caught')
                del saved
                gc.collect()
                outcomes.append(events)
            self.assertEqual(*outcomes)

    def test_original_receiver_lookup_and_iteration_fallback(self):
        outcomes = []
        for function in self.functions():
            events = []
            class Target:
                @property
                def extend(self):
                    events.append('extend-lookup')
                    return lambda values: events.append(tuple(values))
            class Route(tuple):
                def __getitem__(self, key):
                    events.append(('slice', repr(key)))
                    return super().__getitem__(key)
                def __iter__(self):
                    events.append('iter')
                    return super().__iter__()
            function(Target(), [[1, 2], [3, 4]], Route((0, 1)))
            outcomes.append(events)
        self.assertEqual(*outcomes)

    def test_unsupported_bindings_and_disable(self):
        for source in (
            SOURCE.replace('def run(target, rows, route):', 'def run(target, rows, route, zip):'),
            SOURCE.replace('def run(target, rows, route):', 'def run(target, route):\n    if route:\n        rows=[]'),
            SOURCE.replace('    target.extend', '    def mutate():\n        nonlocal rows\n        rows=[]\n    target.extend'),
            SOURCE.replace('rows[a][b]', 'rows(a,b)'),
        ):
            self.assertNotIn('adjacent-extend', [c.pass_name for c in optimize_source(source).changes])
        result = optimize_source(SOURCE, Options(disabled=frozenset({'adjacent-extend'})))
        self.assertNotIn('adjacent-extend', [c.pass_name for c in result.changes])
