import ast
from dataclasses import asdict, is_dataclass
import unittest

from tools.bot_optimizer.program import Program
from tools.bot_optimizer.region_types import RegionSchemas, SnapshotEmitter
from tools.bot_optimizer.numeric_regions import NumericClones, Unsupported, emit_argument_guards
from tools.bot_optimizer.record_returns import InlineRecordReturns
from tools.bot_optimizer.scalar_extrema import ScalarExtrema
from tools.bot_optimizer.model import Options
from tools.bot_optimizer.tests.test_specialization import execute


SOURCE = '''from dataclasses import dataclass
@dataclass(frozen=True)
class Item:
    red: int
    blue: int
    duration: int
    delay: int
@dataclass(frozen=True)
class Weights:
    values: tuple[float,...]
@dataclass(frozen=True)
class Result:
    red: int
    blue: int
    duration: int
    peak: int
    score: float
class Engine:
    def __init__(self,items: list[Item],matrix: list[list[int]],weights: Weights | None):
        self.items=items
        self.matrix=matrix
        self.weights=weights
    def evaluate(self,route: tuple[int,...],selector: int):
        if not route:
            return None
        items=self.items
        red=sum(items[i].red for i in route)
        blue=sum(items[i].blue for i in route)
        duration=sum(items[i].duration for i in route)
        ratio=red/(selector+1)
        peak=max(items[i].delay+items[i].duration for i in route)
        value=self.matrix[selector][route[0]]
        score=self.weighted(route)+ratio+value
        return Result(red,blue,duration,peak,score)
    def weighted(self,route):
        weights=self.weights
        if weights is None:
            return 0.0
        return sum(self.items[i].duration*weights.values[i] for i in route)
'''


def normalized(value):
    if is_dataclass(value):
        return normalized(asdict(value))
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    return value


class NumericRegionTests(unittest.TestCase):
    def generate(self, source=SOURCE, method='evaluate'):
        program = Program({'example': ast.parse(source)})
        schemas = RegionSchemas(program)
        owner = schemas.owner('example.Engine')
        self.assertIsNotNone(owner)
        builder = NumericClones(program, schemas, owner)
        entry = builder.entry(method)
        refs = {f'example.{node.name}': node.name for node in program.modules['example'].tree.body
                if isinstance(node, ast.ClassDef)}
        snapshots = SnapshotEmitter(builder.taken, refs)
        root, fail, validators = snapshots.emit(owner)
        builder.taken.update(snapshots.taken)
        prepare, check, params, guards = emit_argument_guards(builder, entry)
        methods = ast.Module(body=[clone.function for clone in builder.clones.values()], type_ignores=[])
        methods = InlineRecordReturns(program, 'example', Options()).apply(methods)
        methods = ScalarExtrema(program, 'example', Options()).apply(methods)
        tree = ast.fix_missing_locations(ast.Module(body=[*validators.body, *guards.body, *methods.body], type_ignores=[]))
        ns = execute(source+'\n'+ast.unparse(tree))
        original = getattr(ns['Engine'], method)
        def guarded(instance, *args):
            data = ns[root](instance)
            if data is ns[fail]:
                return original(instance, *args)
            bounds = ns[prepare](data)
            if not ns[check](bounds, *args):
                return original(instance, *args)
            return ns[entry.name](data, *args)
        return ns, builder, guarded, (root, fail, prepare, check)

    def instance(self, ns, *, weights=True):
        rows = [ns['Item'](2, 3, 5, 7), ns['Item'](11, 13, 17, 19)]
        return ns['Engine'](rows, [[2, 3], [5, 7]], ns['Weights']((0.1, 0.9)) if weights else None)

    def test_source_derived_clones_fuse_and_resolve_pure_helpers(self):
        ns, builder, guarded, _ = self.generate()
        self.assertEqual(builder.required_methods, {'evaluate', 'weighted'})
        self.assertEqual(builder.fusions, 1)
        for with_weights in (False, True):
            instance = self.instance(ns, weights=with_weights)
            for route in ((), (0,), (0, 1), (1, 0), (-1, 0)):
                self.assertEqual(normalized(instance.evaluate(route, 0)), normalized(guarded(instance, route, 0)))

    def test_bounds_preserve_original_errors_and_custom_index_effects(self):
        ns, _, guarded, (root, fail, prepare, check) = self.generate()
        instance = self.instance(ns)
        data = ns[root](instance)
        self.assertIsNot(data, ns[fail])
        bounds = ns[prepare](data)
        events = []
        class Index:
            def __index__(self):
                events.append('index')
                return 0
        index = Index()
        self.assertFalse(ns[check](bounds, (index,), 0))
        self.assertEqual(events, [])
        for route, selector in (((index,), 0), ((99,), 0), ((0,), 99), ((0,), -1), ((0,), True)):
            values = []
            for run in (instance.evaluate, lambda r, s: guarded(instance, r, s)):
                events.clear()
                try:
                    value = normalized(run(route, selector))
                except Exception as error:
                    value = type(error).__name__, str(error)
                values.append((value, list(events)))
            self.assertEqual(*values)

    def test_empty_maximum_raises_at_original_point_after_gap(self):
        source = SOURCE.replace('        if not route:\n            return None\n', '')
        ns, builder, guarded, _ = self.generate(source)
        self.assertEqual(builder.fusions, 1)
        instance = self.instance(ns)
        for selector in (-1, 0):
            results = []
            for run in (instance.evaluate, lambda route, index: guarded(instance, route, index)):
                try:
                    run((), selector)
                except Exception as error:
                    results.append((type(error).__name__, str(error)))
            self.assertEqual(*results)
            self.assertEqual(results[0][0], 'ZeroDivisionError' if selector == -1 else 'ValueError')

    def test_native_float_sum_and_overflow_order_remain_exact(self):
        ns, _, guarded, _ = self.generate(SOURCE.replace('def weighted(self,route):',
                                                       'def weighted(self,route: tuple[int,...]):'), method='weighted')
        for quantities, weights in (((), ()), ((10**16, 1, -10**16), (1.0, 1.0, 1.0)),
                                    ((10**1000, 1), (1.0, 0.0)),
                                    ((1, 2), (float('inf'), float('-inf')))):
            rows = [ns['Item'](0, 0, quantity, 0) for quantity in quantities]
            instance = ns['Engine'](rows, [], ns['Weights'](weights))
            values = []
            for run in (instance.weighted, lambda route: guarded(instance, route)):
                try:
                    value = normalized(run(tuple(range(len(rows)))))
                except Exception as error:
                    value = type(error).__name__, str(error)
                values.append(value)
            self.assertEqual(*values)

    def test_unknown_calls_mutation_escape_and_unsafe_any_decline(self):
        for body in (
            'return unknown()',
            'self.items=[]\nreturn 1',
            'return self.items',
            'return any(1/(i-i)>0 for i in route)',
            'value=sum(i for i in route)\nif selector:\n    sum=0\nreturn value',
            'table=self.items\nfor i in route:\n    value=table[i].red\n    table=self.items[1:]\nreturn 1',
            'value=selector\nfor i in route:\n    result=value+1\n    value=0.5\nreturn 1',
            'values=[1]\nvalues.extend(len(values) for i in route)\nreturn sum(values)',
            'values=[1]\nalias=(values,)\nvalues.extend(len(alias[0]) for i in route)\nreturn sum(values)',
            'table=self.items\nvalues=(table[i].red for i in route)\ntable=self.items[1:]\nreturn sum(values)',
        ):
            source = SOURCE[:SOURCE.index('    def evaluate')]+ '    def evaluate(self,route: tuple[int,...],selector: int):\n'+ '\n'.join('        '+line for line in body.splitlines())+'\n'
            with self.assertRaises(Unsupported, msg=body):
                self.generate(source)

    def test_private_clones_do_not_repeat_annotation_evaluation(self):
        source = SOURCE.replace('selector: int):', 'selector: int) -> annotation():')
        source = 'events=[]\ndef annotation():\n    events.append(1)\n    return int\n'+source
        ns, _, guarded, _ = self.generate(source)
        self.assertEqual(ns['events'], [1])
        instance = self.instance(ns)
        self.assertEqual(normalized(instance.evaluate((0,), 0)), normalized(guarded(instance, (0,), 0)))

    def test_nested_borrowed_helper_values_cannot_be_mutated(self):
        source = SOURCE[:SOURCE.index('    def evaluate')]+'''
    def evaluate(self,route: tuple[int,...],selector: int):
        values=[1]
        bundle=(values,)
        return self.touch(bundle)
    def touch(self,bundle):
        values,=bundle
        values.append(2)
        return 1
'''
        with self.assertRaises(Unsupported):
            self.generate(source)

    def test_helper_inlining_retains_global_resolution(self):
        source = 'FACTOR=2\n'+SOURCE.replace('        items=self.items', '        FACTOR=selector\n        items=self.items').replace(
            'return sum(self.items[i].duration*weights.values[i] for i in route)',
            'return FACTOR*sum(self.items[i].duration*weights.values[i] for i in route)')
        ns, builder, guarded, _ = self.generate(source)
        self.assertEqual(builder.inlined_helpers, 0)
        instance = self.instance(ns)
        self.assertEqual(normalized(instance.evaluate((0, 1), 0)), normalized(guarded(instance, (0, 1), 0)))

    def test_fusion_expires_when_table_is_rebound(self):
        source = SOURCE.replace('        ratio=red/(selector+1)',
                                '        items=self.items[1:]\n        ratio=red/(selector+1)')
        # The sums may fuse, but the later maximum must retain its own traversal.
        ns, builder, guarded, _ = self.generate(source)
        entry = next(clone for clone in builder.clones.values() if clone.method == 'evaluate')
        self.assertNotIn('_bcopt_region_best_', ast.unparse(entry.function))
        instance = self.instance(ns)
        self.assertEqual(normalized(instance.evaluate((0,), 0)), normalized(guarded(instance, (0,), 0)))
        for run in (instance.evaluate, lambda route, index: guarded(instance, route, index)):
            with self.assertRaisesRegex(IndexError, 'list index out of range'):
                run((1,), 0)


if __name__ == '__main__':
    unittest.main()
