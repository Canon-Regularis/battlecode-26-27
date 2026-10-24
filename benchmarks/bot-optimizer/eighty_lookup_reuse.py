"""Research-only reuse of a proven unchanged bucket lookup across record stores.

Keep the previous-record alias only while its bucket still owns it. Transfer to
the original previous binding at its original point, then release the temporary
in finally before publication. The finally also releases it on errors/continues.
"""

import argparse
import ast
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
    count = 0
    for parent in list(ast.walk(consumer)):
        for _, body in ast.iter_fields(parent):
            if not isinstance(body, list):
                continue
            lookups = [n for n in body if isinstance(n, ast.Assign)
                       and ast.unparse(n) == 'previous = candidates.get(camp_set)']
            if not lookups:
                continue
            lookup, = lookups
            start, = [i for i, n in enumerate(body) if isinstance(n, ast.Assign)
                      and ast.unparse(n) == '_bcopt_losing_fast = False']
            end = body.index(lookup)
            block = body[start:end]
            releases = [n for statement in block for n in ast.walk(statement) if isinstance(n, ast.Delete)
                        and ast.unparse(n) == 'del _bcopt_losing_previous']
            release, = releases
            class Release(ast.NodeTransformer):
                def visit_Delete(self, node):
                    return None if node is release else node
            block = Release().visit(ast.Module(body=block, type_ignores=[])).body
            selection = ast.parse('if _bcopt_losing_fast:\n    previous = _bcopt_losing_previous\nelse:\n    pass').body[0]
            selection.orelse = [lookup]
            protected = ast.Try(body=[*block, selection], handlers=[], orelse=[],
                                finalbody=ast.parse('del _bcopt_losing_previous').body)
            body[start:end+1] = [*ast.parse('_bcopt_losing_previous = None').body, protected]
            count += 1
    assert count == 78, count
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('totals', Path(__file__).with_name('eighty_base_totals.py'))
    totals = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(totals)
    disabled = frozenset({'insertion-base-integer-totals', 'insertion-cancelled-products', 'losing-record-lookup-reuse', 'insertion-retained-integer-edges', 'numeric-dead-primitive-slots'})
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if options.disabled == disabled:
            totals.transform(output, wait_term=True)
            transform(output)
            report['pass_counts']['experiment-lookup-reuse-with-totals-wait'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
        maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ', options=Options(disabled=disabled))
    report['experimental_post_compile_transform'] = 'lookup reuse with finally-bounded alias, plus base totals and no-wait term, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
