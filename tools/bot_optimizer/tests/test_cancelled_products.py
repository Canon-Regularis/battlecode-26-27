import ast
import copy
import struct
import unittest

from tools.bot_optimizer import Options
from tools.bot_optimizer.cancelled_products import CancelledProducts


SOURCE = '''
def consumer(data, values, amounts, ready=True):
    snapshot = data[0]
    axis = 0
    results = []
    for item in range(len(values)):
        cache = None
        for position in range(len(amounts)):
            if ready:
                state = cache
                if state is None:
                    a = values[item]
                    cache = True
                b = amounts[position]
                c = b if position % 2 else b + 1
                d = snapshot[axis]
                result = 0.0
                result += (a + b - c) * d
                results.append(result)
    return results
'''


def fixture():
    tree = ast.parse(SOURCE)
    consumer = tree.body[0]
    consumer._bcopt_fused_consumer = True
    consumer.body[0]._bcopt_snapshot_hoisted = True
    producer = next(n for n in ast.walk(consumer) if isinstance(n, ast.For))
    producer._bcopt_fused_insertion = {'item': 'item'}
    producer.body[0]._bcopt_scalar_cache_init = True
    version = next(n for n in ast.walk(producer) if isinstance(n, ast.If))
    version._bcopt_prepared_dispatch = True
    version.body[0]._bcopt_resident_scalar_outputs = ('a',)
    version.body[1]._bcopt_group_scalar_miss = True
    update = next(n for n in ast.walk(version) if isinstance(n, ast.AugAssign))
    update.value._bcopt_integer_cancel_product = True
    return tree


class CancelledProductTests(unittest.TestCase):
    def test_certified_first_use_exact_cancellation_and_multiplication(self):
        tree = fixture()
        transform = CancelledProducts(Options())
        result = transform.apply(tree)
        self.assertEqual(len(transform.changes), 1)
        left, right = {}, {}
        exec(SOURCE, left)
        exec(compile(result, '<cancelled-products>', 'exec'), right)
        for factor in (0.0, -0.0, 0.1, float('inf'), float('-inf'), float('nan')):
            for values in ([0, 1, -3, 40], [10**400]):
                for ready in (True, False):
                    outcomes = []
                    for namespace in (left, right):
                        try:
                            rows = namespace['consumer'](((factor,),), values, [0, 1, 2**100, -2**100], ready)
                            outcome = [struct.pack('d', row).hex() for row in rows]
                        except OverflowError as error:
                            outcome = type(error).__name__, str(error)
                        outcomes.append(outcome)
                    self.assertEqual(*outcomes)

    def test_missing_integer_resident_snapshot_or_invariance_proofs(self):
        for mutation in ('integer', 'resident', 'snapshot', 'reset', 'axis', 'factor', 'scalar-write', 'disabled', 'plain'):
            tree = fixture()
            consumer = tree.body[0]
            producer = next(n for n in ast.walk(consumer) if isinstance(n, ast.For))
            version = next(n for n in ast.walk(producer) if isinstance(n, ast.If))
            if mutation == 'integer':
                next(n for n in ast.walk(version) if isinstance(n, ast.AugAssign)).value._bcopt_integer_cancel_product = False
            elif mutation == 'resident':
                del version.body[0]._bcopt_resident_scalar_outputs
            elif mutation == 'snapshot':
                del consumer.body[0]._bcopt_snapshot_hoisted
            elif mutation == 'reset':
                del producer.body[0]._bcopt_scalar_cache_init
            elif mutation == 'axis':
                version.body.insert(0, ast.parse('axis = position').body[0])
            elif mutation == 'factor':
                version.body.insert(-1, ast.parse('d = 2.0').body[0])
            elif mutation == 'scalar-write':
                version.body.insert(-1, ast.parse('a = 0').body[0])
            elif mutation == 'plain':
                tree = ast.parse(SOURCE)
            options = Options(disabled=frozenset({'insertion-cancelled-products'})) if mutation == 'disabled' else Options()
            transform = CancelledProducts(options)
            transform.apply(copy.deepcopy(tree))
            self.assertFalse(transform.changes, mutation)


if __name__ == '__main__':
    unittest.main()
