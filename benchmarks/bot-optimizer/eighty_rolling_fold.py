"""Research-only rolling prepared contributions with unchanged float fold order."""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.records import used_names
import tools.bot_optimizer.compare as measurement


def transform(folder, *, prefix_fold=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    producer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_insertion_key_producer')]
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    names = {key: '_bcopt_fold80_'+key for key in ('group', 'state', 'values', 'value', 'left', 'right', 'a', 'b', 'zip', 'len',
              'initial', 'prefix', 'index', 'iterator', 'previous', 'current', 'iter', 'next')}
    assert not set(names.values()) & used_names(tree)
    outer, = [node for node in ast.walk(producer) if isinstance(node, ast.For)
              and isinstance(node.target, ast.Name) and node.target.id == 'camp_index']
    outer.body.insert(0, ast.parse(f"{names['group']} = [None]").body[0])
    for node in ast.walk(producer):
        if isinstance(node, ast.Yield):
            node.value.elts.append(ast.Name(id=names['group'], ctx=ast.Load()))
    route_loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                   and isinstance(node.target, ast.Tuple) and node.target.elts[0].id == 'route']
    position, = [part.id for part in route_loop.target.elts if isinstance(part, ast.Name)
                 and part.id.startswith('_bcopt_edge_position')]
    route_loop.target.elts.append(ast.Name(id=names['group'], ctx=ast.Store()))
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
            n = names
            code = f'''{n['state']} = {n['group']}[0]
if {n['state']} is None or {position} != {n['state']}[0] + 1:
    {n['values']} = [{table}[{n['b']}][{n['a']}] for {n['a']}, {n['b']} in {n['zip']}(route, route[1:])]
    {n['group']}[0] = [{position}, {n['values']}]
else:
    {n['values']} = {n['state']}[1]
    {n['left']}, {n['right']} = route[{position}-1], route[{position}]
    if {position} > 1:
        {n['values']}[{position}-2] = {table}[{n['left']}][route[{position}-2]]
    {n['values']}[{position}-1] = {table}[{n['right']}][{n['left']}]
    if {position} < {n['len']}(route)-1:
        {n['values']}[{position}] = {table}[route[{position}+1]][{n['right']}]
    {n['state']}[0] = {position}
for {n['value']} in {n['values']}:
    {target} += {n['value']}
'''
            if prefix_fold:
                # Equal nonzero exact floats have identical bits. Zero and NaN
                # always take the full fold, preserving their sign/payload rules.
                code = f'''{n['initial']} = {target}
{n['prefix']} = {target}
{n['state']} = {n['group']}[0]
if {n['state']} is not None and {position} > 1 and {position} == {n['state']}[0] + 1 and {target} != 0.0 and {target} == {n['state']}[1]:
    {target} = {n['state']}[2] + {table}[route[{position}-1]][route[{position}-2]]
    {n['prefix']} = {target}
    {n['iterator']} = {n['iter']}(route[{position}-1:])
    {n['previous']} = {n['next']}({n['iterator']}, None)
    for {n['current']} in {n['iterator']}:
        {target} += {table}[{n['current']}][{n['previous']}]
        {n['previous']} = {n['current']}
else:
    {n['index']} = 0
    {n['iterator']} = {n['iter']}(route)
    {n['previous']} = {n['next']}({n['iterator']}, None)
    for {n['current']} in {n['iterator']}:
        {target} += {table}[{n['current']}][{n['previous']}]
        if {n['index']} == {position} - 2:
            {n['prefix']} = {target}
        {n['index']} += 1
        {n['previous']} = {n['current']}
{n['group']}[0] = [{position}, {n['initial']}, {n['prefix']}]
del {n['iterator']}, {n['previous']}
'''
            changes.append(node.lineno)
            return ast.parse(code).body
    Fold().visit(consumer)
    assert len(changes) == 1, changes
    index = 1 if isinstance(tree.body[0], ast.Expr) else 0
    while isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    tree.body[index:index] = ast.parse(f"from builtins import zip as {names['zip']}, len as {names['len']}, iter as {names['iter']}, next as {names['next']}").body
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prefix-fold', action='store_true')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if not options.disabled:
            transform(output, prefix_fold=args.prefix_fold)
            report['pass_counts']['experiment-rolling-fold'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'rolling prepared contributions with sequential fold, not production integrated'
    report['prefix_fold'] = args.prefix_fold
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
