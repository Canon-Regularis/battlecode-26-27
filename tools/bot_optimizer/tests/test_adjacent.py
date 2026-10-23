import unittest

from tools.bot_optimizer import optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''def run(route, callback):
    result = []
    for a, b in zip(route, route[1:]):
        result.append(callback(a, b))
    return result
'''


class AdjacentTests(unittest.TestCase):
    def test_break_continue_else_and_unbound_targets(self):
        source = '''def run(route, stop):
    result=[]
    for a,b in zip(route,route[1:]):
        if b==stop:
            break
        if b==2:
            continue
        result.append((a,b))
    else:
        result.append('exhausted')
    try:
        result.append((a,b))
    except UnboundLocalError:
        result.append('unbound')
    return result
'''
        result = optimize_source(source)
        self.assertIn('tuple-adjacent-iterator', [c.pass_name for c in result.changes])
        old, new = execute(source)['run'], execute(result.source)['run']
        for route in ((),(1,),(1,2,3,4),[1,2,3,4]):
            for stop in (0,2,4):
                self.assertEqual(old(route,stop),new(route,stop))

    def test_cleanup_on_return_and_saved_exception(self):
        source = '''def run(route, callback, make):
    token = make()
    for a,b in zip(route,route[1:]):
        callback(a,b)
        return None
'''
        result = optimize_source(source)
        for fails in (False,True):
            outcomes=[]
            for text in (source,result.source):
                events=[]
                class Value:
                    def __init__(self,label):self.label=label
                    def __del__(self):events.append(self.label)
                def callback(a,b):
                    events.append((a.label,b.label))
                    if fails:raise ValueError('callback')
                saved=None
                try:
                    execute(text)['run']((Value('a'),Value('b'),Value('c')), callback, lambda:Value('token'))
                except ValueError as error:
                    saved=error
                events.append('after')
                del saved
                outcomes.append(events)
            self.assertEqual(*outcomes)

    def test_reassigned_targets_keep_original_binding_order(self):
        for source in (SOURCE.replace('    result = []', '    a = callback\n    result = []'),
                       SOURCE.replace('        result.append', '        b = callback\n        result.append')):
            self.assertNotIn('tuple-adjacent-iterator', [c.pass_name for c in optimize_source(source).changes])

    def test_tuple_and_mutating_list_fallback(self):
        result = optimize_source(SOURCE)
        self.assertIn('tuple-adjacent', [c.pass_name for c in result.changes])
        for sequence in ((), (1,), (1, 2, 3, 4), [1, 2, 3, 4]):
            outcomes = []
            for source in (SOURCE, result.source):
                route = list(sequence) if type(sequence) is list else sequence
                def callback(a, b):
                    if type(route) is list and len(route) > 2:
                        route.pop()
                    return a, b
                outcomes.append(execute(source)['run'](route, callback))
            self.assertEqual(*outcomes)

    def test_custom_sequence_protocol(self):
        result = optimize_source(SOURCE)
        outcomes = []
        for source in (SOURCE, result.source):
            events = []
            class Route(tuple):
                def __getitem__(self, key):
                    events.append(('get', repr(key)))
                    return super().__getitem__(key)
                def __iter__(self):
                    events.append('iter')
                    return super().__iter__()
            value = execute(source)['run'](Route((1, 2, 3)), lambda a, b: a + b)
            outcomes.append((value, events))
        self.assertEqual(*outcomes)

    def test_rebinding_and_escaping_pairs_fall_back(self):
        for source in (
            SOURCE.replace('        result.append', '        route = ()\n        result.append'),
            SOURCE.replace('for a, b in', 'for pair in').replace('callback(a, b)', 'callback(*pair)'),
            SOURCE.replace('def run(route, callback):', 'def run(route, callback, zip):'),
            SOURCE.replace('    result = []', '    def mutate():\n        nonlocal route\n        route=()\n    result=[]'),
        ):
            self.assertNotIn('tuple-adjacent', [c.pass_name for c in optimize_source(source).changes])
