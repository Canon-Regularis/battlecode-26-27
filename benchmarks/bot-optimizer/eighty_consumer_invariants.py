"""Research-only closed-consumer load hoisting and nonempty-route specialization.

The private insertion producer always yields a nonempty integer tuple. The
validated false-continuation callback leaves the owner snapshot unchanged, and
the per-altar candidate dictionary is fixed during one generator consumption.
"""

import argparse
import ast
import copy
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
    bound, bucket = '_bcopt_consumer80_bound', '_bcopt_consumer80_bucket'
    assert not {bound, bucket} & used_names(tree)
    route_loop, = [node for node in ast.walk(consumer) if isinstance(node, ast.For)
                   and isinstance(node.target, ast.Tuple) and node.target.elts[0].id == 'route']
    loads = [node for node in ast.walk(route_loop) if isinstance(node, ast.Attribute)
             and node.attr == 'max_expansions' and isinstance(node.value, ast.Name) and node.value.id == 'config']
    candidate, = [node for node in route_loop.body if isinstance(node, ast.Assign)
                  and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'candidates']
    assert isinstance(candidate.value, ast.Subscript) and isinstance(candidate.value.value, ast.Name)
    assert candidate.value.value.id == 'candidates_by_altar' and candidate.value.slice.id == 'altar_index'
    candidate_value = copy.deepcopy(candidate.value)
    candidate.value = ast.Name(id=bucket, ctx=ast.Load())
    count = []
    class Simplify(ast.NodeTransformer):
        def visit_Attribute(self, node):
            if node in loads:
                return ast.Name(id=bound, ctx=ast.Load())
            return self.generic_visit(node)
        def visit_If(self, node):
            if (isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
                    and isinstance(node.test.operand, ast.Name) and node.test.operand.id == 'route'):
                assert len(node.body) == 1 and isinstance(node.body[0], ast.Assign)
                assert node.body[0].targets[0].id == 'evaluation' and node.body[0].value.value is None
                count.append(node)
                return [self.visit(part) for part in node.orelse]
            return self.generic_visit(node)
        def visit_For(self, node):
            node = self.generic_visit(node)
            if node is route_loop:
                return [ast.Assign(targets=[ast.Name(id=bucket, ctx=ast.Store())], value=candidate_value), node]
            return node
    Simplify().visit(consumer)
    assert len(count) == 2 and len(loads) == 1, (len(count), len(loads))
    outer = next(i for i, node in enumerate(consumer.body) if isinstance(node, ast.For))
    consumer.body[outer:outer] = ast.parse(f'{bound} = config.max_expansions').body
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
            report['pass_counts']['experiment-consumer-invariants'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'consumer invariant loads and nonempty insertion routes, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
