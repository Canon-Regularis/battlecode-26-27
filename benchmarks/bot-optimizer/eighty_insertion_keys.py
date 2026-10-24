"""Research-only producer reuse of insertion-invariant multiset/set keys.

The certified primitive consumer gets a private generator clone. Every position
inserting the same value into the same tuple shares its canonical keys, while
route tuples, evaluations and result records remain fresh at their old points.
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
    producer, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'camp_insertions']
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    names = {key: '_bcopt_insert80_'+key for key in ('producer', 'joined', 'key', 'members')}
    assert not set(names.values()) & used_names(tree)
    clone = copy.deepcopy(producer)
    clone.name = names['producer']
    loop, = [node for node in ast.walk(clone) if isinstance(node, ast.For)
             and isinstance(node.target, ast.Name) and node.target.id == 'camp_index']
    assert isinstance(loop.body[0], ast.If) and isinstance(loop.body[0].body[0], ast.Continue)
    loop.body[1:1] = ast.parse(f'''{names['joined']} = (*route, camp_index)
{names['key']} = tuple(sorted({names['joined']}))
{names['members']} = frozenset({names['joined']})
del {names['joined']}
''').body
    for node in ast.walk(clone):
        if isinstance(node, ast.Yield):
            node.value = ast.Tuple(elts=[node.value, ast.Name(id=names['key'], ctx=ast.Load()),
                                       ast.Name(id=names['members'], ctx=ast.Load())], ctx=ast.Load())
    route_loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                   and isinstance(node.target, ast.Name) and node.target.id == 'route']
    assert isinstance(route_loop.iter, ast.Call) and route_loop.iter.func.id == producer.name
    route_loop.iter.func.id = clone.name
    route_loop.target = ast.Tuple(elts=[route_loop.target, ast.Name(id=names['key'], ctx=ast.Store()),
                                      ast.Name(id=names['members'], ctx=ast.Store())], ctx=ast.Store())
    changes = {'key': 0, 'members': 0}
    class Keys(ast.NodeTransformer):
        def visit_Call(self, node):
            if (isinstance(node.func, ast.Attribute) and node.func.attr == 'tuple'
                    and len(node.args) == 1 and isinstance(node.args[0], ast.Call)
                    and isinstance(node.args[0].func, ast.Attribute) and node.args[0].func.attr == 'sorted'
                    and len(node.args[0].args) == 1 and isinstance(node.args[0].args[0], ast.Name)
                    and node.args[0].args[0].id == 'route'):
                changes['key'] += 1
                return ast.Name(id=names['key'], ctx=ast.Load())
            if (isinstance(node.func, ast.Name) and node.func.id == 'frozenset' and len(node.args) == 1
                    and isinstance(node.args[0], ast.Name) and node.args[0].id == 'route'):
                changes['members'] += 1
                return ast.Name(id=names['members'], ctx=ast.Load())
            return self.generic_visit(node)
    Keys().visit(consumer)
    assert changes == {'key': 2, 'members': 1}, changes
    tree.body.insert(tree.body.index(consumer), clone)
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
        if options.disabled == frozenset({'insertion-invariant-keys'}):
            transform(output)
            report['pass_counts']['experiment-insertion-keys'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-invariant-keys'})))
    report['experimental_post_compile_transform'] = 'insertion-invariant key reuse, not production integrated'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
