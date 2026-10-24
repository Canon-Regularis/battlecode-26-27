"""Research-only sink overwritten integer initializers into reduction fallback.

The guarded base-total path and multiset-cache hit assign all outputs directly.
Original zero/None initializers remain immediately before the original fallback
loop, including partial-error paths. This is measured separately before generic
cache-provenance and definite-assignment integration.
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


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('_bcopt_region_consumer_')]
    count = 0
    for wrapper in ast.walk(consumer):
        if not (isinstance(wrapper, ast.For) and isinstance(wrapper.target, ast.Name)
                and wrapper.target.id == '_bcopt_position_once'):
            continue
        version, = [n for n in ast.walk(wrapper) if isinstance(n, ast.If)
                    and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0']
        region = ast.Module(body=version.body, type_ignores=[])
        guards = [n for n in ast.walk(region) if isinstance(n, ast.If)
                  and isinstance(n.test, ast.BoolOp) and isinstance(n.test.values[0], ast.Name)
                  and n.test.values[0].id.startswith('_bcopt_base_total_valid')]
        guard, = guards
        parent, = [n for n in ast.walk(region) if isinstance(n, ast.If)
                   and len(n.body) > 4 and [ast.unparse(x) for x in n.body[:4]] == [
                       '_bcopt_entry_local_37 = 0', '_bcopt_entry_local_38 = 0',
                       '_bcopt_entry_local_46 = 0', '_bcopt_entry_local_4 = None']]
        assert guard in set(ast.walk(parent))
        assert len(guard.orelse) == 1 and isinstance(guard.orelse[0], ast.For)
        guard.orelse[:0] = copy.deepcopy(parent.body[:4])
        del parent.body[:4]
        count += 1
    assert count == 77, count
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision,corners,lanes')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == frozenset({'insertion-sink-integer-initializers'}):
            transform(output)
            report['pass_counts']['experiment-sunk-integer-initializers'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
        maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
        options=Options(disabled=frozenset({'insertion-sink-integer-initializers'})))
    report['experimental_post_compile_transform'] = 'sink overwritten integer reduction initializers into original fallback loop'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
