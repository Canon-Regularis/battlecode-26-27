import ast
import unittest

from tools.bot_optimizer.program import Program
from tools.bot_optimizer.region_types import RegionSchemas, SnapshotEmitter
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''from dataclasses import dataclass
WEIGHT=0.2
@dataclass(frozen=True)
class Item:
    location: tuple[int,int]
    quantity: int
@dataclass(frozen=True)
class Tuning:
    weight: float = WEIGHT
    def __post_init__(self):
        if not 0<=self.weight<=1:
            raise ValueError('weight')
class Store:
    def __init__(self,items: list[Item],matrix: list[list[int]],tuning: Tuning,weights: tuple[float,...] | None):
        self.items=items
        self.matrix=matrix
        self.tuning=tuning
        self.weights=weights
    def calculate(self):
        return 0
'''


class RegionTypeTests(unittest.TestCase):
    def generated(self, source=SOURCE):
        program = Program({'example': ast.parse(source)})
        schema = RegionSchemas(program).owner('example.Store')
        self.assertIsNotNone(schema)
        root, failure, tree = SnapshotEmitter(set(), {
            'example.Store': 'Store', 'example.Item': 'Item', 'example.Tuning': 'Tuning',
        }).emit(schema)
        ns = execute(source+'\n'+ast.unparse(tree))
        return ns, ns[root], ns[failure]

    def test_guarded_copy_is_primitive_and_does_not_alias_mutable_tables(self):
        ns, snapshot, failure = self.generated()
        rows = [ns['Item']((1, 2), 3)]
        matrix = [[4]]
        value = ns['Store'](rows, matrix, ns['Tuning'](), (0.5,))
        copied = snapshot(value)
        self.assertIsNot(copied, failure)
        self.assertEqual(copied, ((((1, 2), 3),), ((4,),), (0.2,), (0.5,)))
        matrix[0][0] = 99
        ns['Item'].__init__(rows[0], (1, 2), 88)
        self.assertEqual(copied[0][0][1], 3)
        self.assertEqual(copied[1][0][0], 4)
        value.weights = None
        self.assertIsNone(snapshot(value)[3])

    def test_annotations_never_bypass_runtime_type_or_missing_field_checks(self):
        ns, snapshot, failure = self.generated()
        class Integer(int):
            pass
        class Rows(list):
            def __iter__(self):
                raise AssertionError('custom iteration must not run')
        for quantity in (True, 1.5, Integer(3), object()):
            value = ns['Store']([ns['Item']((1, 2), quantity)], [[4]], ns['Tuning'](), (0.5,))
            self.assertIs(snapshot(value), failure)
        value = ns['Store'](Rows(), [], ns['Tuning'](), None)
        self.assertIs(snapshot(value), failure)
        value = ns['Store']([ns['Item']((1, 2), 3)], [[4]], ns['Tuning'](), None)
        object.__delattr__(value.items[0], 'quantity')
        self.assertIs(snapshot(value), failure)
        value = ns['Store']([], [], ns['Tuning'](1), None)
        # A float annotation is a candidate for an exact-float guard, not a
        # promise that mixed int/float native sums cannot raise during conversion.
        self.assertIs(snapshot(value), failure)

    def test_snapshot_retains_no_mutable_source_alias(self):
        ns, snapshot, failure = self.generated()
        events = []
        class Marker:
            def __del__(self):
                events.append('released')
        value = ns['Store']([], [[1]], ns['Tuning'](), None)
        copied = snapshot(value)
        self.assertIsNot(copied, failure)
        value.matrix[0].append(Marker())
        del value.matrix
        self.assertEqual(events, ['released'])
        self.assertEqual(copied[1], ((1,),))

    def test_runtime_descriptor_or_lookup_changes_decline_without_callbacks(self):
        for mode in ('descriptor', 'lookup'):
            ns, snapshot, failure = self.generated()
            value = ns['Store']([ns['Item']((1, 2), 3)], [[4]], ns['Tuning'](), None)
            events = []
            class Descriptor:
                def __get__(self, instance, owner):
                    events.append('descriptor')
                    return 9
                def __set__(self, instance, value):
                    pass
            if mode == 'descriptor':
                ns['Item'].quantity = Descriptor()
            else:
                def lookup(instance, name):
                    events.append('lookup')
                    return object.__getattribute__(instance, name)
                ns['Item'].__getattribute__ = lookup
            self.assertIs(snapshot(value), failure)
            self.assertEqual(events, [])

    def test_custom_layouts_and_ambiguous_defaults_are_not_schema_candidates(self):
        variants = [
            SOURCE.replace('class Item:', 'class Item(object):'),
            SOURCE.replace('    quantity: int', '    quantity: int\n    def __getattribute__(self,name):\n        return object.__getattribute__(self,name)'),
            SOURCE.replace('WEIGHT=0.2', 'WEIGHT=unknown()'),
            SOURCE.replace("            raise ValueError('weight')", "            self.weight=0"),
            SOURCE.replace('    def calculate(self):', '    @property\n    def calculate(self):'),
            SOURCE.replace('        self.items=items', '        self.items=list(items)'),
        ]
        for source in variants:
            schema = RegionSchemas(Program({'example': ast.parse(source)})).owner('example.Store')
            self.assertIsNone(schema, source)

    def test_recursive_and_unknown_annotations_decline(self):
        source = SOURCE.replace('quantity: int', "quantity: 'Item'")
        self.assertIsNone(RegionSchemas(Program({'example': ast.parse(source)})).owner('example.Store'))
        source = SOURCE.replace('quantity: int', 'quantity: Unknown')
        self.assertIsNone(RegionSchemas(Program({'example': ast.parse(source)})).owner('example.Store'))


if __name__ == '__main__':
    unittest.main()
