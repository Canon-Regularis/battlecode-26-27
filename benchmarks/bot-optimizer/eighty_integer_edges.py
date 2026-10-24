"""Research-only retain base integer edges already read by lazy base totals."""

import argparse
import ast
import copy
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
    changes = 0
    for branch in list(ast.walk(consumer)):
        if (not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare)
                or not isinstance(branch.test.left, ast.Name) or branch.test.left.id != '_bcopt_fused_size'
                or not isinstance(branch.test.ops[0], ast.Eq)):
            continue
        width = branch.test.comparators[0].value
        base = [n.id for n in branch.body[0].targets[0].elts]
        assert len(base) == width-1
        producer = branch.body[-1]
        for wrapper in [n for n in ast.walk(producer) if isinstance(n, ast.For)
                        and isinstance(n.target, ast.Name) and n.target.id == '_bcopt_position_once']:
            route = wrapper.body[0].value
            position, = [i for i, n in enumerate(route.elts) if n.id == '_bcopt_fused_camp_index']
            version, = [n for n in ast.walk(wrapper) if isinstance(n, ast.If)
                        and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0']
            region = ast.Module(body=version.body, type_ignores=[])
            initialize, = [n for n in ast.walk(region) if isinstance(n, ast.If)
                           and ast.unparse(n.test) == '_bcopt_algebra_base_total is None']
            assignment, loop = initialize.body
            assert isinstance(assignment, ast.Assign) and isinstance(assignment.value, ast.BinOp)
            assert isinstance(assignment.value.op, ast.Add) and isinstance(loop, ast.For)
            first, last = '_bcopt_intedge80_first', '_bcopt_intedge80_last'
            setup = ast.parse(f'{first} = None\n{last} = None\n_bcopt_algebra_base_total = {first} + {last}').body
            setup[0].value, setup[1].value = assignment.value.left, assignment.value.right
            for i in range(len(base)-1):
                setup.extend(ast.parse(f'_bcopt_intedge80_{i} = _bcopt_entry_local_34[{base[i]}][{base[i+1]}]\n'
                                       f'_bcopt_algebra_base_total += _bcopt_intedge80_{i}').body)
            if len(base) > 1:
                setup.extend(ast.parse(f'_bcopt_algebra_a, _bcopt_algebra_z = {base[-2]}, {base[-1]}').body)
            initialize.body = setup
            mappings = {
                '_bcopt_entry_local_30[altar_index][_bcopt_fused_route[0]]': first,
                '_bcopt_entry_local_30[altar_index][_bcopt_fused_route[-1]]': last,
                f'_bcopt_entry_local_30[altar_index][{base[0]}]': first,
            }
            if 0 < position < width-1:
                mappings['_bcopt_entry_local_34[_bcopt_algebra_a][_bcopt_algebra_z]'] = f'_bcopt_intedge80_{position-1}'
            replacements = {ast.dump(ast.parse(expr, mode='eval').body): name for expr, name in mappings.items()}
            class Reuse(ast.NodeTransformer):
                def visit_If(self, node):
                    return node if node is initialize else self.generic_visit(node)

                def visit_Subscript(self, node):
                    key = ast.dump(node)
                    if key in replacements:
                        return ast.Name(id=replacements[key], ctx=ast.Load())
                    return self.generic_visit(node)
            version.body = Reuse().visit(region).body
            changes += 1
    assert changes == 77
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision')
    args = parser.parse_args()
    modules = []
    for name in ('eighty_base_totals', 'eighty_lookup_reuse', 'eighty_dead_slots'):
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    disabled = frozenset({'insertion-base-integer-totals', 'insertion-cancelled-products', 'losing-record-lookup-reuse', 'insertion-retained-integer-edges', 'numeric-dead-primitive-slots'})
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == disabled:
            modules[0].transform(output, wait_term=True)
            modules[1].transform(output)
            modules[2].transform(output)
            transform(output)
            report['pass_counts']['experiment-retained-base-integer-edges'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
        maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ', options=Options(disabled=disabled))
    report['experimental_post_compile_transform'] = 'retain base integer edges plus totals/wait/lookup/dead aliases, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
