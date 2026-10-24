"""Research native minimum scans for already-validated integer snapshot rows."""

import argparse
import ast
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer import Options


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    helper, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name.startswith('_bcopt_algebra_certify')]
    calls = [node for node in ast.walk(helper) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == 'all']
    call, = calls
    alias = call.func.value.id
    class Native(ast.NodeTransformer):
        def visit_Call(self, node):
            if node is call:
                return ast.parse(f'{alias}.min(row) >= 0', mode='eval').body
            return self.generic_visit(node)
    Native().visit(helper)
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--normal', action='store_true')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options=None):
        enabled = options is None or not options.disabled
        if enabled:
            options = Options(disabled=frozenset({'insertion-edge-native-certificate'}))
        report = original(bot, output, options)
        if enabled:
            transform(output)
            report['pass_counts']['experiment-native-edge-certificate'] = 1
        return report
    if args.normal:
        spec = importlib.util.spec_from_file_location('normal', Path(__file__).with_name('normal_budget.py'))
        normal = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(normal)
        normal.optimize_folder = compile_variant
        sys.argv = [str(Path(__file__).with_name('normal_budget.py')), str(args.bot), '--output', str(args.output),
                    '--maps', 'collision', '--rounds', '1', '--observe-local', 'planner:LoopPlanner.find_loops:expansion_count']
        normal.main()
        report = json.loads((args.output/'results.json').read_text())
    else:
        measurement.optimize_folder = compile_variant
        report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                     maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
        for row in report['comparisons']:
            print(row['map'], row['side'], row['reduction_percent'])
    report['experimental_post_compile_transform'] = 'native minima on validated integer edge snapshots, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
