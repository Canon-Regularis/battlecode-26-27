"""Research-only specialization of a numeric consumer for prepared tables."""

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


def transform(folder, *, zip_edges=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    dispatch, = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                 and isinstance(node.test, ast.Name) and node.test.id.startswith('_bcopt_region_live_')
                 and len(node.body) == 1 and isinstance(node.body[0], ast.Try)]
    hoisted = {node.targets[0].id for node in consumer.body if isinstance(node, ast.Assign)
               and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
               and isinstance(node.value, ast.Subscript) and isinstance(node.value.value, ast.Name)
               and node.value.value.id.startswith('_bcopt_region_data_')}
    def table_test(node):
        return (isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                and node.left.id in hoisted and len(node.ops) == 1 and isinstance(node.ops[0], ast.Is)
                and len(node.comparators) == 1 and isinstance(node.comparators[0], ast.Constant)
                and node.comparators[0].value is None)
    tables = sorted({node.test.left.id for node in ast.walk(dispatch) if isinstance(node, ast.IfExp)
                     and table_test(node.test)})
    assert len(tables) == 6, tables
    ready = '_bcopt_ready80_tables'
    assert ready not in used_names(tree)
    class Prepared(ast.NodeTransformer):
        def visit_IfExp(self, node):
            if table_test(node.test):
                return self.visit(node.orelse)
            return self.generic_visit(node)
        def visit_If(self, node):
            if (zip_edges and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Call)
                    and isinstance(node.test.left.func, ast.Name)
                    and node.test.left.func.id.startswith('_bcopt_adj_type_')):
                return [self.visit(part) for part in node.orelse]
            return self.generic_visit(node)
    specialized = Prepared().visit(copy.deepcopy(dispatch.body[0]))
    dispatch.body = [ast.If(test=ast.Name(id=ready, ctx=ast.Load()), body=[specialized], orelse=dispatch.body)]
    index = next(i for i, node in enumerate(consumer.body) if isinstance(node, ast.Expr)
                 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
    consumer.body[index:index] = ast.parse(f'{ready} = '+ ' and '.join(f'{name} is not None' for name in tables)).body
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--zip-edges', action='store_true')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'numeric-prepared-versions'}):
            transform(output, zip_edges=args.zip_edges)
            report['pass_counts']['experiment-prepared-table-version'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'numeric-prepared-versions'})))
    report['experimental_post_compile_transform'] = 'prepared-table specialization, not production integrated'
    report['zip_edges'] = args.zip_edges
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
