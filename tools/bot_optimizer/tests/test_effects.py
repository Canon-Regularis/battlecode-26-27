import ast
import unittest

from tools.bot_optimizer.effects import CallbackEffects
from tools.bot_optimizer.program import Program


class CallbackEffectTests(unittest.TestCase):
    def analyze(self, source, extra=None):
        modules = {'budget': ast.parse(source), 'settings': ast.parse('LIMIT=4000000\n')}
        modules.update({name: ast.parse(text) for name, text in (extra or {}).items()})
        return CallbackEffects(Program(modules)).false_continuation('budget.stop')

    def test_dirty_terminating_path_does_not_poison_readonly_false_path(self):
        contract = self.analyze('''import cambc
import settings
def stop():
    if cambc.fuel_remaining() >= settings.LIMIT:
        return False
    print('stop', flush=True)
    return True
''')
        self.assertIsNotNone(contract)
        self.assertEqual(contract.constants, ('settings.LIMIT',))
        self.assertEqual(contract.sdk_calls, ('cambc.fuel_remaining',))

    def test_unknown_effect_before_false_exit_rejects_contract(self):
        for body in (
            "print('side effect')\nreturn False",
            'return unknown()',
            'if unknown():\n    return True\nreturn False',
            "if True:\n    print('side effect')\nreturn False",
            "print('side effect')",  # An implicit None also continues the loop.
        ):
            self.assertIsNone(self.analyze('def stop():\n' + '\n'.join('    '+line for line in body.splitlines())))

    def test_annotations_and_custom_comparison_cannot_prove_purity(self):
        self.assertIsNone(self.analyze('''threshold: int = object()
def stop():
    return threshold > 0
'''))
        self.assertIsNone(self.analyze('''def stop(value: int = 1):
    return value > 0
'''))
        self.assertIsNone(self.analyze('''import cambc
threshold = unknown()
def stop():
    if cambc.fuel_remaining() > threshold:
        return False
    return True
'''))

    def test_native_aliases_and_local_primitive_dataflow(self):
        contract = self.analyze('''from cambc import fuel_remaining as remaining
from settings import LIMIT as limit
def stop():
    fuel=remaining()
    reserve=limit+1
    if fuel-reserve < 0:
        print('stop')
        return True
    return False
''')
        self.assertIsNotNone(contract)
        self.assertEqual(contract.sdk_calls, ('cambc.fuel_remaining',))

    def test_shadowed_sdk_rebound_constants_and_dynamic_modules_reject(self):
        source = '''import cambc
import settings
def stop():
    return cambc.fuel_remaining() < settings.LIMIT
'''
        self.assertIsNone(self.analyze(source, {'cambc': 'def fuel_remaining():\n    return 1\n'}))
        self.assertIsNone(self.analyze(source, {'settings': '''LIMIT=1
def change():
    global LIMIT
    LIMIT=object()
'''}))
        self.assertIsNone(self.analyze(source, {'settings': '''LIMIT=1
def __getattr__(name):
    return 1
'''}))
        self.assertIsNone(self.analyze('''import cambc
def stop():
    cambc=unknown()
    return cambc.fuel_remaining() < 1
'''))

    def test_raising_path_has_no_ordinary_continuation(self):
        contract = self.analyze('''import cambc
def stop():
    if cambc.fuel_remaining() < 0:
        raise RuntimeError('invalid')
    return False
''')
        self.assertIsNotNone(contract)


if __name__ == '__main__':
    unittest.main()
