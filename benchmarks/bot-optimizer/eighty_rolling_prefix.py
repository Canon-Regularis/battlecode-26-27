"""Research-only one-scalar ordered-prefix reuse across adjacent insertions.

Interior insertion positions have identical endpoints. Their unchanged ordered
prefix grows by exactly one base edge. Retain that scalar only after the current
fold succeeds; skipped positions and endpoint changes keep the original fold.
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


def transform(folder, producer_name='_bcopt_fused_camp_index'):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    last, prefix, candidate = ('_bcopt_prefix80_'+part for part in ('last', 'value', 'candidate'))
    assert not {last, prefix, candidate} & used_names(tree)
    producer, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Name) and node.target.id == producer_name]
    producer.body.insert(0, ast.parse(f'{last} = -2').body[0])
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
                                                   and isinstance(part.value, ast.Subscript) for part in additions)
            target = additions[0].target.id
            assert all(part.target.id == target for part in additions)
            fallback = [*copy.deepcopy(additions), *ast.parse(f'{last} = -2').body]
            for position in reversed(range(1, width-1)):
                if position == 1:
                    body = [*ast.parse(f'{candidate} = {target}').body, *copy.deepcopy(additions)]
                else:
                    cached = ast.parse(f'if {last} == {position-1}:\n    {target} = {prefix}\nelse:\n    pass').body[0]
                    cached.orelse = copy.deepcopy(additions[:position-2]) or [ast.Pass()]
                    body = [cached, copy.deepcopy(additions[position-2]),
                            *ast.parse(f'{candidate} = {target}').body, *copy.deepcopy(additions[position-1:])]
                body.extend(ast.parse(f'{prefix} = {candidate}\n{last} = {position}').body)
                fallback = [ast.If(test=ast.Compare(left=ast.Name(id='_bcopt_edge_position', ctx=ast.Load()),
                    ops=[ast.Eq()], comparators=[ast.Constant(position)]), body=body, orelse=fallback)]
            node.body = [node.body[0], *fallback, node.body[-1]]
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
            report['pass_counts']['experiment-rolling-prefix'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'single-scalar ordered prefix across adjacent insertion positions, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
