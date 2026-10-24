"""Research-only exact integer-grid evaluation of certified compensated sums.

Only the existing <=16-term, nonnegative binary-grid certificate qualifies.
Ordinary sequential additions remain untouched. Invalid indices and uncertified
tables retain native sums. This candidate needs separate rounding proofs before
production integration.
"""

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
    helper, = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_bcopt_compensated_certify']
    maximum = next(n for n in helper.body if isinstance(n, ast.Assign) and n.targets[0].id == 'maximum')
    source = maximum.value.args[0]
    assert isinstance(source, ast.GeneratorExp)
    integers = ast.parse('integers = _b.tuple(())').body[0]
    integers.value.args[0] = source
    helper.body.insert(helper.body.index(maximum), integers)
    maximum.value.args[0] = ast.Name(id='integers', ctx=ast.Load())
    check = helper.body[-1]
    assert isinstance(check, ast.Return)
    helper.body[-1:] = [ast.If(test=check.value, body=ast.parse('return integers, denominator').body,
                               orelse=ast.parse('return False').body)]
    consumer, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('_bcopt_region_consumer_')]
    count = 0
    for branch in list(ast.walk(consumer)):
        if (not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare)
                or not isinstance(branch.test.left, ast.Name) or branch.test.left.id != '_bcopt_fused_size'
                or not isinstance(branch.test.ops[0], ast.Eq)):
            continue
        producer = branch.body[-1]
        assert isinstance(producer, ast.For)
        branch.body[-1:-1] = ast.parse('_bcopt_grid80_base = None\n_bcopt_grid80_valid = None').body
        versions = [n for n in ast.walk(producer) if isinstance(n, ast.If)
                    and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0']
        for version in versions:
            misses = [n for statement in version.body for n in ast.walk(statement)
                      if isinstance(n, ast.If) and ast.unparse(n.test) == '_bcopt_compensated_value is None']
            miss, = misses
            original, publish = miss.body
            assert isinstance(original, ast.Assign) and isinstance(original.value, ast.Call)
            replacement = ast.parse('''
if _bcopt_grid80_valid is None:
    _bcopt_grid80_values, _bcopt_grid80_denominator = _bcopt_compensated_ready
    _bcopt_grid80_n = len(_bcopt_grid80_values)
    _bcopt_grid80_valid = all(-_bcopt_grid80_n <= _bcopt_grid80_index < _bcopt_grid80_n for _bcopt_grid80_index in _bcopt_fused_route)
if _bcopt_grid80_valid and -_bcopt_grid80_n <= _bcopt_fused_camp_index < _bcopt_grid80_n:
    if _bcopt_grid80_base is None:
        _bcopt_grid80_base = sum(_bcopt_grid80_values[_bcopt_grid80_index] for _bcopt_grid80_index in _bcopt_fused_route)
    _bcopt_compensated_value = (_bcopt_grid80_base + _bcopt_grid80_values[_bcopt_fused_camp_index]) / _bcopt_grid80_denominator
else:
    pass
''').body
            replacement[-1].orelse = [copy.deepcopy(original)]
            miss.body = [*replacement, publish]
            count += 1
    assert count == 77, count
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
            report['pass_counts']['experiment-grid-compensated-sums'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
        maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ', options=Options(disabled=disabled))
    report['experimental_post_compile_transform'] = 'certified exact integer-grid compensated sums plus totals/wait/lookup/dead aliases, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
