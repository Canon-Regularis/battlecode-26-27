"""Research-only bounded multiset reuse of native compensated float sums.

The first result still comes from native sum. Reuse requires exact, nonnegative,
finite floats, a bounded common binary grid, at most 16 terms, and CPython 3.13.
On that grid Neumaier's low accumulator is exact, so the final native rounding is
independent of permutation. Uncertified tables/routes retain their original sum.
"""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.records import used_names
from tools.bot_optimizer.model import Options
import tools.bot_optimizer.compare as measurement


CERTIFICATE = '''def _bcopt_sum80_certify(values):
    import sys as _sys
    import builtins as _b
    if _sys.implementation.name != 'cpython' or _sys.version_info[:2] != (3, 13) or values is None or _b.len(values) > 4096:
        return False
    ratios = []
    denominator = 1
    for value in values:
        if _b.type(value) is not _b.float or not 0.0 <= value < _b.float('inf'):
            return False
        numerator, divisor = value.as_integer_ratio()
        ratios.append((numerator, divisor))
        denominator = _b.max(denominator, divisor)
    maximum = _b.max((numerator * (denominator // divisor) for numerator, divisor in ratios), default=0)
    # With <=16 terms, high remains below 32*K grid units. Each exact
    # FastTwoSum correction is below 64*K/2**52 units, and the sum of all
    # correction magnitudes is below 2**38 when K < 2**80. Thus low never
    # rounds on this grid; native high+low rounds the exact rational total.
    return maximum.bit_length() <= 80 and (maximum * 32).bit_length() - (denominator.bit_length() - 1) <= 1023
'''


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    producer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_insertion_key_producer')]
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    slot, ready, value, length = (f'_bcopt_sum80_{name}' for name in ('slot', 'ready', 'value', 'len'))
    assert not {slot, ready, value, length, '_bcopt_sum80_certify'} & used_names(tree)
    outer, = [node for node in ast.walk(producer) if isinstance(node, ast.For)
              and isinstance(node.target, ast.Name) and node.target.id == 'camp_index']
    outer.body.insert(0, ast.parse(f'{slot} = [None]').body[0])
    for node in ast.walk(producer):
        if isinstance(node, ast.Yield):
            node.value.elts.append(ast.Name(id=slot, ctx=ast.Load()))
    route_loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                   and isinstance(node.target, ast.Tuple) and node.target.elts[0].id == 'route']
    route_loop.target.elts.append(ast.Name(id=slot, ctx=ast.Store()))
    tables = []
    class Memo(ast.NodeTransformer):
        def visit_AugAssign(self, node):
            call = node.value
            if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != 'sum'
                    or len(call.args) != 1 or not isinstance(call.args[0], ast.IfExp)):
                return self.generic_visit(node)
            choice = call.args[0]
            if (not isinstance(choice.test, ast.Compare) or not isinstance(choice.test.left, ast.Call)
                    or not isinstance(choice.test.ops[0], ast.Gt) or not isinstance(choice.body, ast.Call)
                    or not isinstance(choice.body.func, ast.Call) or len(choice.body.args) != 1
                    or not isinstance(choice.body.args[0], ast.Name)):
                return node
            table = choice.body.args[0].id
            tables.append(table)
            result = ast.parse(f'''if {ready} and {length}(route) <= 16:
    {value} = {slot}[0]
    if {value} is None:
        pass
else:
    pass
''').body[0]
            assignment = ast.Assign(targets=[ast.Name(id=value, ctx=ast.Store())], value=copy.deepcopy(call))
            result.body[1].body = [assignment, *ast.parse(f'{slot}[0] = {value}').body]
            result.orelse = [copy.deepcopy(assignment)]
            node.value = ast.Name(id=value, ctx=ast.Load())
            return [result, node]
    Memo().visit(consumer)
    table, = tables
    index = next(i for i, node in enumerate(consumer.body) if isinstance(node, ast.Expr)
                 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
    consumer.body[index:index] = ast.parse(f'{ready} = _bcopt_sum80_certify({table})').body
    index = 1 if isinstance(tree.body[0], ast.Expr) else 0
    while isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = [*ast.parse(f'from builtins import len as {length}').body, *ast.parse(CERTIFICATE).body]
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-compensated-sums'}):
            transform(output)
            report['pass_counts']['experiment-compensated-cache'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-compensated-sums'})))
    report['experimental_post_compile_transform'] = 'bounded native compensated-sum multiset reuse, not production integrated'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
