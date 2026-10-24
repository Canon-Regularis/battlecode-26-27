"""Research-only native collection of prepared numeric projections.

Retains native compensated sum and its empty-input behavior. This experiment
only rewrites the already certified emitted consumer, never original bot code.
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


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    names = used_names(tree)
    def fresh(stem):
        name = '_bcopt_projection80_' + stem
        while name in names:
            name += '_'
        names.add(name)
        return name
    getter, length = fresh('getter'), fresh('len')
    changes = []
    class Projection(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if (not isinstance(node.func, ast.Name) or node.func.id != 'sum' or node.keywords
                    or len(node.args) != 1 or not isinstance(node.args[0], ast.ListComp)):
                return node
            comp = node.args[0]
            if len(comp.generators) != 1 or not isinstance(comp.elt, ast.IfExp):
                return node
            gen, choice = comp.generators[0], comp.elt
            if (gen.is_async or gen.ifs or not isinstance(gen.target, ast.Name)
                    or not isinstance(gen.iter, ast.Name) or not isinstance(choice.orelse, ast.Subscript)
                    or not isinstance(choice.orelse.value, ast.Name)
                    or not isinstance(choice.orelse.slice, ast.Name) or choice.orelse.slice.id != gen.target.id):
                return node
            test, table = choice.test, choice.orelse.value
            if (not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Name)
                    or test.left.id != table.id or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Is)
                    or not isinstance(test.comparators[0], ast.Constant) or test.comparators[0].value is not None):
                return node
            original, short = copy.deepcopy(comp), copy.deepcopy(comp)
            original.elt, short.elt = copy.deepcopy(choice.body), copy.deepcopy(choice.orelse)
            native = ast.Call(func=ast.Call(func=ast.Name(id=getter, ctx=ast.Load()),
                args=[ast.Starred(value=copy.deepcopy(gen.iter), ctx=ast.Load())], keywords=[]),
                args=[copy.deepcopy(table)], keywords=[])
            native_or_short = ast.IfExp(test=ast.Compare(left=ast.Call(func=ast.Name(id=length, ctx=ast.Load()),
                args=[copy.deepcopy(gen.iter)], keywords=[]), ops=[ast.Gt()], comparators=[ast.Constant(1)]),
                body=native, orelse=short)
            node.args = [ast.IfExp(test=copy.deepcopy(test), body=original, orelse=native_or_short)]
            changes.append(node.lineno)
            return node
    Projection().visit(consumer)
    assert len(changes) == 1, changes
    index = 0
    if isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        index = 1
    while isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = ast.parse(f'from _operator import itemgetter as {getter}\nfrom builtins import len as {length}\n').body
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
        if options.disabled == frozenset({'numeric-native-projection'}):
            transform(output)
            report['pass_counts']['experiment-native-projection'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'numeric-native-projection'})))
    report['experimental_post_compile_transform'] = 'native prepared projection collection, not production integrated'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
