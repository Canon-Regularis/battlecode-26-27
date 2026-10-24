"""Research-only native traversal of prepared pairwise numeric tables.

Native reduce(add, ..., initial) preserves sequential floating additions; using
sum here would change their rounding. Only the certified emitted consumer is
rewritten, with its original short-route/preparation-failure path retained.
"""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.records import used_names
import tools.bot_optimizer.compare as measurement


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    names = used_names(tree)
    aliases = {}
    for name in ('reduce', 'add', 'getitem', 'itemgetter', 'len', 'map'):
        alias = '_bcopt_edges80_' + name
        assert alias not in names
        aliases[name] = alias
    changes = []
    class Edges(ast.NodeTransformer):
        def visit_If(self, node):
            test = node.test
            if (not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Call)
                    or not isinstance(test.left.func, ast.Name)
                    or not test.left.func.id.startswith('_bcopt_adj_type_')):
                return self.generic_visit(node)
            route, = test.left.args
            assert isinstance(route, ast.Name)
            updates = [part for part in ast.walk(node) if isinstance(part, ast.AugAssign)]
            assert len(updates) == 2
            update = updates[0]
            assert isinstance(update.op, ast.Add) and isinstance(update.target, ast.Name)
            choice = update.value
            assert isinstance(choice, ast.IfExp)
            lookup = choice.orelse
            assert isinstance(lookup, ast.Subscript) and isinstance(lookup.value, ast.Subscript)
            table = lookup.value.value
            assert isinstance(table, ast.Name)
            loop, = [part for part in ast.walk(node.body[3]) if isinstance(part, ast.For)]
            assert isinstance(loop.target, ast.Name) and lookup.value.slice.id == loop.target.id
            assert ast.dump(updates[1].value) == ast.dump(choice)
            target = update.target.id
            a = aliases
            code = f'''if {table.id} is not None and {a['len']}({route.id}) > 2:
    {target} = {a['reduce']}({a['add']}, {a['map']}({a['getitem']}, {a['itemgetter']}(*{route.id}[1:])({table.id}), {route.id}), {target})
else:
    pass
'''
            result = ast.parse(code).body[0]
            result.orelse = [node]
            changes.append(node.lineno)
            return result
    Edges().visit(consumer)
    assert len(changes) == 1, changes
    imports = []
    for module, members in (('_functools', ('reduce',)), ('_operator', ('add', 'getitem', 'itemgetter')),
                            ('builtins', ('len', 'map'))):
        imports.append(ast.ImportFrom(module=module,
            names=[ast.alias(name=name, asname=aliases[name]) for name in members], level=0))
    index = 1 if isinstance(tree.body[0], ast.Expr) else 0
    while isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = imports
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
        if not options.disabled:
            transform(output)
            report['pass_counts']['experiment-native-edges'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'native pairwise prepared reduction, not production integrated'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
