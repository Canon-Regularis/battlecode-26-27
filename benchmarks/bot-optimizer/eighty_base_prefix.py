"""Research-only ordered risk prefixes shared across all insertions of one base.

Interior routes retain their endpoints. Cache sequential base-edge prefixes once,
then evaluate only the inserted edges and remaining suffix in original order.
Endpoint routes and failed speculative primitive reads retain the original fold.
"""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer.records import used_names


def transform(folder, producer_name='_bcopt_fused_camp_index', base='_bcopt_fused_route'):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    stem = '_bcopt_baseprefix80_'
    assert not any(name.startswith(stem) for name in used_names(tree))
    cache, key, work, running, a, z = (stem+part for part in ('cache', 'key', 'work', 'running', 'a', 'z'))
    producer, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Name) and node.target.id == producer_name]
    class Initialize(ast.NodeTransformer):
        def visit_For(self, node):
            if node is producer:
                return [*ast.parse(f'{cache} = None\n{key} = None').body, node]
            return self.generic_visit(node)
    Initialize().visit(consumer)
    changes = []
    class Prefix(ast.NodeTransformer):
        def visit_If(self, node):
            self.generic_visit(node)
            if (not isinstance(node.test, ast.Compare) or not isinstance(node.test.left, ast.Name)
                    or not node.test.left.id.startswith('_bcopt_ordered_size') or len(node.test.ops) != 1
                    or not isinstance(node.test.ops[0], ast.Eq) or not isinstance(node.test.comparators[0], ast.Constant)):
                return node
            width = node.test.comparators[0].value
            assert 2 <= width <= 12 and isinstance(node.body[0], ast.Assign) and isinstance(node.body[0].targets[0], ast.Tuple)
            additions = node.body[1:-1]
            assert len(additions) == width-1 and all(isinstance(part, ast.AugAssign) and isinstance(part.op, ast.Add)
                and isinstance(part.value, ast.Subscript) and isinstance(part.value.value, ast.Subscript) for part in additions)
            target = additions[0].target.id
            table = additions[0].value.value.value.id
            assert all(part.target.id == target and part.value.value.value.id == table for part in additions)
            if width == 2:
                changes.append(width)
                return node
            def dispatch(low, high):
                if low == high:
                    return [*ast.parse(f'{target} = {cache}[{low-1}]').body, *copy.deepcopy(additions[low-1:])]
                mid = (low+high)//2
                return [ast.If(test=ast.parse(f'_bcopt_edge_position <= {mid}', mode='eval').body,
                               body=dispatch(low, mid), orelse=dispatch(mid+1, high))]
            block = ast.parse(f'''
if 0 < _bcopt_edge_position < {width-1}:
    if {cache} is None or {key} != {target} or ({target} == 0.0 and {key}.hex() != {target}.hex()):
        {key} = {target}
        {work} = [{target}]
        {running} = {target}
        try:
            for {a}, {z} in zip({base}, {base}[1:]):
                {running} += {table}[{z}][{a}]
                {work}.append({running})
        except IndexError:
            {cache} = False
        else:
            {cache} = {work}
        del {work}
    if {cache} is not False:
        pass
    else:
        pass
else:
    pass
''').body[0]
            block.body[-1].body = dispatch(1, width-2)
            block.body[-1].orelse = copy.deepcopy(additions)
            block.orelse = copy.deepcopy(additions)
            node.body = [node.body[0], block, node.body[-1]]
            changes.append(width)
            return node
    Prefix().visit(consumer)
    assert sorted(changes) == list(range(2, 13)), changes
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
            report['pass_counts']['experiment-base-prefix'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'base-route ordered risk prefix cache, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
