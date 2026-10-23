import unittest

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.tests.test_specialization import execute


class ScalarTests(unittest.TestCase):
    def functions(self, source):
        result = optimize_source(source)
        self.assertIn('scalar-extremum', [c.pass_name for c in result.changes])
        return execute(source)['run'], execute(result.source)['run']

    def test_scalar_ties_nans_and_signed_zero(self):
        for consumer in ('min', 'max'):
            old, new = self.functions(f'def run(a,b):\n    return {consumer}(a,b)')
            for a, b in ((1, 2), (-0., 0.), (0., -0.), (float('nan'), 1.), (1., float('nan'))):
                self.assertIs(old(a, b), new(a, b))

    def test_nested_clamp(self):
        old, new = self.functions('def run(x,y):\n    return min(1.0,max(0.0,x/y))')
        for x in (-3., -0., 0., .5, 1., 3., float('nan'), float('inf')):
            self.assertEqual(old(x, 1.).hex(), new(x, 1.).hex())
        for function in (old, new):
            with self.assertRaises(ZeroDivisionError):
                function(1, 0)

    def test_callback_order_and_saved_error_lifetimes(self):
        source = 'def run(make):\n    return min(1.0,max(0.0,make()))'
        for mode in ('keep', 'replace', 'compare-inner', 'compare-outer', 'bool-inner', 'bool-outer'):
            observations = []
            for function in self.functions(source):
                events = []
                class Truth:
                    def __init__(self, which):
                        self.which = which
                    def __bool__(self):
                        events.append(('bool', self.which))
                        if mode == 'bool-' + self.which:
                            raise ValueError('bool')
                        return self.which == 'inner' or mode == 'replace'
                    def __del__(self):
                        events.append(('truth-del', self.which))
                class Value:
                    def compare(self, which):
                        events.append(('compare', which))
                        if mode == 'compare-' + which:
                            raise ValueError('compare')
                        return Truth(which)
                    def __gt__(self, other):
                        return self.compare('inner')
                    def __lt__(self, other):
                        return self.compare('outer')
                    def __del__(self):
                        events.append('value-del')
                def make():
                    events.append('make')
                    return Value()
                saved = None
                try:
                    value = function(make)
                    events.append(('result', isinstance(value, Value)))
                    del value
                except ValueError as error:
                    saved = error
                    events.append(('error', str(error)))
                events.append('after')
                del saved
                observations.append(events)
            self.assertEqual(*observations, mode)

    def test_unsupported_bindings(self):
        for source in (
            'def run(a,b,min):\n    return min(a,b)',
            'def run(a,b):\n    return min(a(),b())',
            'def run(a,b):\n    def change():\n        nonlocal a\n        a=3\n    return min(a,b)',
            'def run(b):\n    if b:\n        a=1\n    return min(a,b)',
            'def run(a,b):\n    return min(a,b,key=str)',
            'def run(a,b):\n    return min(*a,b)',
        ):
            self.assertNotIn('scalar-extremum', [c.pass_name for c in optimize_source(source).changes])
        result = optimize_source('def run(a,b):\n    return min(a,b)', Options(disabled=frozenset({'scalar-extremum'})))
        self.assertFalse(result.changes)
