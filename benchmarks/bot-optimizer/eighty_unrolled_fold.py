"""Research-only short-tuple specialization of ordered numeric pair folds.

Tuple unpacking provides primitive locals; additions retain their source order.
Long tuples keep the original loop. Only the already-prepared consumer branch is
rewritten, leaving failed preparation and native-index retry unchanged.
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


def transform(folder, maximum=12):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    length, size = '_bcopt_unroll80_len', '_bcopt_unroll80_size'
    locals_ = [f'_bcopt_unroll80_item_{i}' for i in range(maximum)]
    assert not {length, size, *locals_} & used_names(tree)
    changes = []
    class Fold(ast.NodeTransformer):
        def visit_If(self, node):
            test = node.test
            if (not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Call)
                    or not isinstance(test.left.func, ast.Name) or not test.left.func.id.startswith('_bcopt_adj_type_')):
                return self.generic_visit(node)
            updates = [part for part in ast.walk(node) if isinstance(part, ast.AugAssign)]
            if len(updates) != 2 or not isinstance(updates[0].value, ast.Subscript):
                return node
            update = updates[0]
            assert isinstance(update.op, ast.Add) and isinstance(update.target, ast.Name)
            assert ast.dump(update.value) == ast.dump(updates[1].value)
            source, = node.orelse
            assert isinstance(source, ast.For) and isinstance(source.target, ast.Tuple)
            origin, destination = [part.id for part in source.target.elts]
            lookup = update.value
            assert isinstance(lookup.value, ast.Subscript) and lookup.value.slice.id == destination
            assert lookup.slice.id == origin and isinstance(lookup.value.value, ast.Name)
            table, target = lookup.value.value.id, update.target.id
            fallback = [node]
            for count in reversed(range(2, maximum+1)):
                text = ', '.join(locals_[:count]) + ' = route\n'
                text += '\n'.join(f'{target} += {table}[{b}][{a}]' for a, b in zip(locals_, locals_[1:count]))
                # Preserve the original loop targets for any downstream uses.
                text += f'\n{origin}, {destination} = {locals_[count-2]}, {locals_[count-1]}\n'
                fallback = [ast.If(test=ast.Compare(left=ast.Name(id=size, ctx=ast.Load()),
                    ops=[ast.Eq()], comparators=[ast.Constant(count)]), body=ast.parse(text).body, orelse=fallback)]
            changes.append(node.lineno)
            return [*ast.parse(f'{size} = {length}(route)').body, *fallback]
    Fold().visit(consumer)
    assert len(changes) == 1, changes
    index = 1 if isinstance(tree.body[0], ast.Expr) else 0
    while isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = ast.parse(f'from builtins import len as {length}').body
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maximum', type=int, default=12)
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'numeric-ordered-folds'}):
            transform(output, args.maximum)
            report['pass_counts']['experiment-unrolled-fold'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'numeric-ordered-folds'})))
    report['experimental_post_compile_transform'] = 'short-tuple ordered pair fold specialization, research only'
    report['maximum'] = args.maximum
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
