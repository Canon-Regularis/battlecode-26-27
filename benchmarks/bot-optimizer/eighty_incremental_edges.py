"""Research-only rolling edge lists for certified adjacent insertion positions.

Only private primitive lists are reused. The first position follows the original
construction, and native min/sum still operate on the full updated list. No float
accumulation is changed, and all edge access remains after the callback check.
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
    producer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_insertion_key_producer')]
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    names = {key: '_bcopt_edge80_'+key for key in ('group', 'position', 'left', 'right', 'state')}
    assert not set(names.values()) & used_names(tree)
    outer, = [node for node in ast.walk(producer) if isinstance(node, ast.For)
              and isinstance(node.target, ast.Name) and node.target.id == 'camp_index']
    outer.body.insert(0, ast.parse(f"{names['group']} = [None]").body[0])
    for node in ast.walk(producer):
        if isinstance(node, ast.Yield):
            assert isinstance(node.value, ast.Tuple)
            node.value.elts.extend([ast.Name(id=names['group'], ctx=ast.Load()), ast.Name(id='position', ctx=ast.Load())])
    route_loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                   and isinstance(node.target, ast.Tuple) and isinstance(node.target.elts[0], ast.Name)
                   and node.target.elts[0].id == 'route']
    route_loop.target.elts.extend([ast.Name(id=names['group'], ctx=ast.Store()),
                                  ast.Name(id=names['position'], ctx=ast.Store())])
    changes = []
    class Edges(ast.NodeTransformer):
        def generic_visit(self, node):
            node = super().generic_visit(node)
            for field, body in ast.iter_fields(node):
                if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                    continue
                for index in range(len(body)-1):
                    assignment, extension = body[index:index+2]
                    if (not isinstance(assignment, ast.Assign) or len(assignment.targets) != 1
                            or not isinstance(assignment.targets[0], ast.Name) or not isinstance(assignment.value, ast.List)
                            or len(assignment.value.elts) != 2 or not isinstance(extension, ast.Expr)
                            or not isinstance(extension.value, ast.Call) or not isinstance(extension.value.func, ast.Attribute)
                            or extension.value.func.attr != 'extend' or not isinstance(extension.value.func.value, ast.Name)
                            or extension.value.func.value.id != assignment.targets[0].id):
                        continue
                    first, last = assignment.value.elts
                    comp, = extension.value.args
                    assert isinstance(comp, ast.ListComp) and isinstance(comp.elt, ast.Subscript)
                    assert isinstance(comp.elt.value, ast.Subscript) and isinstance(comp.elt.value.value, ast.Name)
                    assert isinstance(first, ast.Subscript) and isinstance(last, ast.Subscript)
                    assert isinstance(first.value, ast.Subscript) and isinstance(last.value, ast.Subscript)
                    assert ast.dump(first.value) == ast.dump(last.value)
                    matrix = comp.elt.value.value.id
                    legs = assignment.targets[0].id
                    group, position, left, right, state = (names[key] for key in ('group', 'position', 'left', 'right', 'state'))
                    text = f'''{state} = {group}[0]
if {state} is None or {position} != {state}[0] + 1:
    pass
else:
    {legs} = {state}[1]
    {left}, {right} = route[{position} - 1], route[{position}]
    if {position} == 1:
        {legs}[0] = {ast.unparse(first)}
    else:
        {legs}[{position}] = {matrix}[route[{position} - 2]][{left}]
    {legs}[{position} + 1] = {matrix}[{left}][{right}]
    if {position} == len(route) - 1:
        {legs}[1] = {ast.unparse(last)}
    else:
        {legs}[{position} + 2] = {matrix}[{right}][route[{position} + 1]]
    {state}[0] = {position}
'''
                    replacement = ast.parse(text).body
                    replacement[1].body = [copy.deepcopy(assignment), copy.deepcopy(extension),
                        *ast.parse(f'{group}[0] = [{position}, {legs}]').body]
                    body[index:index+2] = replacement
                    changes.append(assignment.lineno)
                    break
            return node
    Edges().visit(consumer)
    assert len(changes) == 2, changes
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
        if options.disabled == frozenset({'insertion-incremental-edges'}):
            transform(output)
            report['pass_counts']['experiment-incremental-edges'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-incremental-edges'})))
    report['experimental_post_compile_transform'] = 'incremental private edge list, not production integrated'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
