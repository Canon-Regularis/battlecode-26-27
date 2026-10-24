"""Research-only direct fresh tuple construction for width-specialized insertions.

Unpack the primitive base once, then use a balanced position dispatch to build
each route directly. This removes the private list insert/copy/delete roundtrip.
Keep the original fallback and original callback, evaluation and exception order.
"""

import argparse
import ast
import copy
import json
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer import Options
from tools.bot_optimizer.records import used_names


def transform(folder, unroll=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    assert not any(name.startswith('_bcopt_route80_') for name in used_names(tree))
    size_binding, = [node for node in ast.walk(consumer) if isinstance(node, ast.Assign)
                     and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                     and node.targets[0].id == '_bcopt_fused_size']
    base = size_binding.value.left.args[0].id
    changed = []
    for branch in ast.walk(consumer):
        if (not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare)
                or not isinstance(branch.test.left, ast.Name) or branch.test.left.id != '_bcopt_fused_size'
                or not isinstance(branch.test.ops[0], ast.Eq) or not isinstance(branch.test.comparators[0], ast.Constant)):
            continue
        width = branch.test.comparators[0].value
        producer, = branch.body
        assert isinstance(producer, ast.For) and isinstance(producer.target, ast.Name)
        item = producer.target.id
        loops = [node for node in ast.walk(producer) if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Name) and node.target.id == '_bcopt_edge_position']
        loop, = loops
        insertion, protected = loop.body
        assert isinstance(insertion, ast.Expr) and insertion.value.func.attr == 'insert'
        assert isinstance(protected, ast.Try) and not protected.handlers and not protected.orelse
        assert len(protected.finalbody) == 1 and isinstance(protected.finalbody[0], ast.Delete)
        route = protected.body[0]
        assert isinstance(route, ast.Assign) and route.targets[0].id == 'route'
        assert isinstance(route.value, ast.Call) and len(route.value.args) == 1
        work = route.value.args[0].id
        assert insertion.value.func.value.id == work and protected.finalbody[0].targets[0].value.id == work
        assert sum(isinstance(n, ast.Name) and n.id == work for n in ast.walk(loop)) == 3
        values = [f'_bcopt_route80_{index}' for index in range(width-1)]
        unpack = ast.Assign(targets=[ast.Tuple(elts=[ast.Name(id=value, ctx=ast.Store()) for value in values], ctx=ast.Store())],
                            value=ast.Name(id=base, ctx=ast.Load()))
        def dispatch(low, high):
            if low == high:
                members = values[:low]+[item]+values[low:]
                return [ast.Assign(targets=copy.deepcopy(route.targets), value=ast.Tuple(
                    elts=[ast.Name(id=value, ctx=ast.Load()) for value in members], ctx=ast.Load()))]
            mid = (low+high)//2
            return [ast.If(test=ast.Compare(left=ast.Name(id='_bcopt_edge_position', ctx=ast.Load()),
                ops=[ast.LtE()], comparators=[ast.Constant(mid)]), body=dispatch(low,mid), orelse=dispatch(mid+1,high))]
        loop.body = [*dispatch(0,width-1), *protected.body[1:]]
        if unroll:
            once = '_bcopt_route80_once'
            expanded = []
            class Constants(ast.NodeTransformer):
                def visit_Name(self, node):
                    if isinstance(node.ctx, ast.Load) and node.id in {'_bcopt_edge_position', '_bcopt_fused_size'}:
                        return ast.copy_location(ast.Constant(position if node.id == '_bcopt_edge_position' else width), node)
                    return node
                def visit_BinOp(self, node):
                    self.generic_visit(node)
                    if (isinstance(node.left, ast.Constant) and type(node.left.value) is int
                            and isinstance(node.right, ast.Constant) and type(node.right.value) is int):
                        if isinstance(node.op, ast.Add):
                            return ast.Constant(node.left.value+node.right.value)
                        if isinstance(node.op, ast.Sub):
                            return ast.Constant(node.left.value-node.right.value)
                    return node
                def visit_Compare(self, node):
                    self.generic_visit(node)
                    if (len(node.ops) == 1 and isinstance(node.left, ast.Constant) and type(node.left.value) is int
                            and isinstance(node.comparators[0], ast.Constant) and type(node.comparators[0].value) is int):
                        a,b = node.left.value,node.comparators[0].value
                        operations = {ast.Eq:a==b,ast.NotEq:a!=b,ast.Lt:a<b,ast.LtE:a<=b,ast.Gt:a>b,ast.GtE:a>=b}
                        if type(node.ops[0]) in operations:
                            return ast.Constant(operations[type(node.ops[0])])
                    return node
                def visit_If(self, node):
                    self.generic_visit(node)
                    if isinstance(node.test, ast.Constant) and type(node.test.value) is bool:
                        return node.body if node.test.value else node.orelse
                    return node
            for position in range(width):
                body = Constants().visit(ast.Module(body=copy.deepcopy(loop.body), type_ignores=[])).body
                expanded.extend(ast.parse(f'_bcopt_edge_position = {position}').body)
                expanded.append(ast.For(target=ast.Name(id=once,ctx=ast.Store()),
                    iter=ast.Tuple(elts=[ast.Constant(None)],ctx=ast.Load()),body=body,orelse=[]))
                expanded.extend(ast.parse('if _bcopt_fused_halted:\n    break').body)
            class Expand(ast.NodeTransformer):
                def visit_For(self, node):
                    return expanded if node is loop else self.generic_visit(node)
            Expand().visit(producer)
        branch.body.insert(0, unpack)
        changed.append(width)
    assert sorted(changed) == list(range(2,13)), changed
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision')
    parser.add_argument('--unroll', action='store_true')
    parser.add_argument('--normal', action='store_true')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options=None):
        enabled = options is None or not options.disabled or options.disabled == frozenset({'insertion-direct-routes'})
        if enabled:
            options = Options(disabled=frozenset({'insertion-direct-routes'}))
        report = original(bot, output, options)
        if enabled:
            transform(output, unroll=args.unroll)
            report['pass_counts']['experiment-direct-routes'] = 1
        return report
    if args.normal:
        spec = importlib.util.spec_from_file_location('normal', Path(__file__).with_name('normal_budget.py'))
        normal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(normal)
        normal.optimize_folder = compile_variant
        sys.argv = [str(Path(__file__).with_name('normal_budget.py')),str(args.bot),'--output',str(args.output),
                    '--maps',args.maps,'--rounds','1','--observe-local','planner:LoopPlanner.find_loops:expansion_count']
        normal.main()
        report = json.loads((args.output/'results.json').read_text())
    else:
        measurement.optimize_folder = compile_variant
        report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                     maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
        for row in report['comparisons']:
            print(row['map'], row['side'], row['reduction_percent'])
    report['experimental_post_compile_transform'] = 'direct fresh insertion tuples with balanced position dispatch, research only'
    report['unroll'] = args.unroll
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
