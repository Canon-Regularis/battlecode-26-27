"""Research-only move short ordered-fold width dispatch outside insertion groups.

Duplicate the fused producer for widths 2..12. Select once per base route, then
retain only its matching ordered-fold branch. Everything else, including fresh
route tuples, callback points, exceptions, fallback and allocation, is unchanged.
"""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer import Options


def transform(folder, producer_name='_bcopt_fused_camp_index'):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    producer, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Name) and node.target.id == producer_name]
    def is_width(node):
        return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id.startswith('_bcopt_ordered_size')
                and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)
                and isinstance(node.test.comparators[0], ast.Constant))
    branch = next(node for node in ast.walk(producer) if is_width(node))
    size_name = branch.test.left.id
    size_assignments = [node for node in ast.walk(producer) if isinstance(node, ast.Assign)
                        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id == size_name]
    size_assignment, = size_assignments
    assert isinstance(size_assignment.value, ast.Name)
    size = size_assignment.value.id
    fallback = [producer]
    for width in reversed(range(2, 13)):
        variant = copy.deepcopy(producer)
        class Specialize(ast.NodeTransformer):
            def visit_If(self, node):
                if is_width(node):
                    body = node.body if node.test.comparators[0].value == width else node.orelse
                    return self.visit(ast.Module(body=body, type_ignores=[])).body
                return self.generic_visit(node)
        variant = Specialize().visit(variant)
        fallback = [ast.If(test=ast.Compare(left=ast.Name(id=size, ctx=ast.Load()), ops=[ast.Eq()],
            comparators=[ast.Constant(width)]), body=[variant], orelse=fallback)]
    class Replace(ast.NodeTransformer):
        def visit_For(self, node):
            return fallback if node is producer else self.generic_visit(node)
    Replace().visit(consumer)
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-width-dispatch'}):
            transform(output)
            report['pass_counts']['experiment-width-dispatch'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-width-dispatch'})))
    report['experimental_post_compile_transform'] = 'ordered-fold width dispatch once per base route, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
