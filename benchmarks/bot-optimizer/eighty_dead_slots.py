"""Research-only removal of dead primitive aliases after direct-route forwarding."""

import argparse
import ast
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import Options
import tools.bot_optimizer.compare as measurement


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('_bcopt_region_consumer_')]
    removed = 0
    for wrapper in ast.walk(consumer):
        if (not isinstance(wrapper, ast.For) or not isinstance(wrapper.target, ast.Name)
                or wrapper.target.id != '_bcopt_position_once'):
            continue
        route = wrapper.body[0]
        assert isinstance(route, ast.Assign) and isinstance(route.value, ast.Tuple)
        scalars = {n.id for n in route.value.elts}
        versions = [n for n in ast.walk(wrapper) if isinstance(n, ast.If)
                    and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0']
        version, = versions
        region = ast.Module(body=version.body, type_ignores=[])
        loads = Counter(n.id for n in ast.walk(region) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load))
        def pure(node):
            return ((isinstance(node, ast.Name) and node.id in scalars)
                    or isinstance(node, ast.Constant) and type(node.value) in {int, float, bool, type(None)}
                    or isinstance(node, ast.Tuple) and all(pure(n) for n in node.elts))
        class Remove(ast.NodeTransformer):
            def visit_Assign(self, node):
                nonlocal removed
                if len(node.targets) != 1:
                    return node
                target = node.targets[0]
                targets = target.elts if isinstance(target, ast.Tuple) else [target]
                if (all(isinstance(n, ast.Name) and n.id.startswith(('_bcopt_entry_local_', '_bcopt_ordered_size'))
                        and not loads[n.id] for n in targets) and pure(node.value)):
                    removed += 1
                    return None
                return node
        version.body = Remove().visit(region).body
    assert removed > 0
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)
    return removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision')
    args = parser.parse_args()
    modules = []
    for name in ('eighty_base_totals', 'eighty_lookup_reuse'):
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    disabled = frozenset({'insertion-base-integer-totals', 'insertion-cancelled-products', 'losing-record-lookup-reuse', 'insertion-retained-integer-edges', 'numeric-dead-primitive-slots'})
    original = measurement.optimize_folder
    counts = []
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == disabled:
            modules[0].transform(output, wait_term=True)
            modules[1].transform(output)
            counts.append(transform(output))
            report['pass_counts']['experiment-dead-primitive-slots'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
        maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ', options=Options(disabled=disabled))
    report['experimental_post_compile_transform'] = dict(dead_aliases=counts, includes='base totals, no-wait term, lookup reuse')
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
