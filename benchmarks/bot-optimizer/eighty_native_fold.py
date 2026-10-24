"""Research-only native ordered addition of prepared short-route contributions.

functools.reduce(operator.add, values, initial) keeps sequential additions. Only
prepared immutable primitive table reads in the already-unrolled path qualify;
long-route and failed-preparation code stays as emitted.
"""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer.records import used_names


def transform(folder, accumulate=False, generic_sum=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    reduce, add, listing = '_bcopt_fold80_reduce', '_bcopt_fold80_add', '_bcopt_fold80_list'
    assert not {reduce, add, listing} & used_names(tree)
    changed = []
    class Fold(ast.NodeTransformer):
        def generic_visit(self, node):
            node = super().generic_visit(node)
            for _, body in ast.iter_fields(node):
                if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                    continue
                index = 0
                def eligible(part):
                    return (isinstance(part, ast.AugAssign) and isinstance(part.op, ast.Add)
                            and isinstance(part.target, ast.Name) and isinstance(part.value, ast.Subscript)
                            and isinstance(part.value.value, ast.Subscript)
                            and isinstance(part.value.slice, ast.Name) and part.value.slice.id.startswith('_bcopt_ordered_item_')
                            and isinstance(part.value.value.slice, ast.Name) and part.value.value.slice.id.startswith('_bcopt_ordered_item_'))
                while index < len(body):
                    if not eligible(body[index]):
                        index += 1
                        continue
                    target, end = body[index].target.id, index+1
                    while end < len(body) and eligible(body[end]) and body[end].target.id == target:
                        end += 1
                    if end-index < 2:
                        index = end
                        continue
                    call = ast.Call(func=ast.Name(id=reduce, ctx=ast.Load()), args=[
                        ast.Name(id=add, ctx=ast.Load()), ast.Tuple(elts=[part.value for part in body[index:end]], ctx=ast.Load()),
                        ast.Name(id=target, ctx=ast.Load())], keywords=[])
                    if accumulate:
                        call = ast.Subscript(value=ast.Call(func=ast.Name(id=listing, ctx=ast.Load()), args=[
                            ast.Call(func=ast.Name(id=reduce, ctx=ast.Load()), args=[call.args[1]],
                                     keywords=[ast.keyword(arg='initial', value=call.args[2])])], keywords=[]),
                            slice=ast.UnaryOp(op=ast.USub(), operand=ast.Constant(1)), ctx=ast.Load())
                    elif generic_sum:
                        call.args = [call.args[1], ast.Call(func=ast.Name(id=add, ctx=ast.Load()),
                                                          args=[call.args[2]], keywords=[])]
                    body[index:end] = [ast.Assign(targets=[ast.Name(id=target, ctx=ast.Store())], value=call)]
                    changed.append(end-index)
                    index += 1
            return node
    Fold().visit(consumer)
    assert sorted(changed) == list(range(2, 12)), changed
    index = 1 if isinstance(tree.body[0], ast.Expr) else 0
    while isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    imports = (f'from itertools import accumulate as {reduce}\nfrom builtins import list as {listing}' if accumulate
               else f'from functools import reduce as {reduce}\nfrom operator import add as {add}')
    if generic_sum:
        imports = (f'from builtins import sum as {reduce}, float as {listing}\n'
                   f'class {add}({listing}):\n    __slots__ = ()')
    tree.body[index:index] = ast.parse(imports).body
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--accumulate', action='store_true')
    parser.add_argument('--generic-sum', action='store_true')
    args = parser.parse_args()
    assert not (args.accumulate and args.generic_sum)
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if not options.disabled:
            transform(output, accumulate=args.accumulate, generic_sum=args.generic_sum)
            report['pass_counts']['experiment-native-fold'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'native ordered primitive fold, research only'
    report['accumulate'] = args.accumulate
    report['generic_sum'] = args.generic_sum
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
