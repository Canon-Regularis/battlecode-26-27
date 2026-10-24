"""Research-only omission of unobservable field stores on losing result records.

Keep object allocation, original __dict__ materialization, and object lifetimes.
An existing winning record of the same type has already populated every field;
the experiment tests whether later losing records can omit redundant stores
without changing shared-key history. Generic escape/lifetime/key proofs pending.
"""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer import Options
from tools.bot_optimizer.records import used_names


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    assert not any(name.startswith('_bcopt_store80_') for name in used_names(tree))
    route, = [node for node in ast.walk(consumer) if isinstance(node, ast.Assign)
              and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'route']
    class Initialize(ast.NodeTransformer):
        def visit_Assign(self, node):
            return [node, *ast.parse('_bcopt_store80_fast = False').body] if node is route else self.generic_visit(node)
    Initialize().visit(consumer)
    version, = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                and isinstance(node.test, ast.Name) and node.test.id == '_bcopt_entry_prepared_ready_0']
    blocks = []
    for node in ast.walk(version):
        for _, body in ast.iter_fields(node):
            if not isinstance(body, list):
                continue
            stores = [part for part in body if isinstance(part, ast.Assign) and len(part.targets) == 1
                      and isinstance(part.targets[0], ast.Subscript) and isinstance(part.targets[0].value, ast.Name)
                      and part.targets[0].value.id == '_bcopt_entry_local_26']
            if stores:
                blocks.append((body, stores))
    # Restrict this experiment to the prepared branch; the fallback remains full.
    body, stores = blocks[0]
    assert len(blocks) == 2 and len(stores) == 12
    index = body.index(stores[0])
    assert body[index:index+12] == stores
    assert isinstance(body[index-1], ast.Assign) and isinstance(body[index-1].value, ast.Attribute)
    assert body[index-1].value.attr == '__dict__'
    setup = ast.parse('''
_bcopt_store80_previous = candidates_by_altar[altar_index].get(_bcopt_insertion_key_set)
_bcopt_store80_keep = _bcopt_store80_previous is None or _bcopt_entry_local_28 > _bcopt_store80_previous.evaluation.score
del _bcopt_store80_previous
_bcopt_store80_fast = True
if _bcopt_store80_keep:
    pass
''').body
    setup[-1].body = stores
    body[index:index+12] = setup
    comparison, = [node for node in ast.walk(consumer) if isinstance(node, ast.If)
                   and isinstance(node.test, ast.BoolOp) and any(isinstance(part, ast.Attribute)
                       and part.attr == 'score' and isinstance(part.value, ast.Name) and part.value.id == 'evaluation'
                       for part in ast.walk(node.test))]
    comparison.test = ast.IfExp(test=ast.Name(id='_bcopt_store80_fast', ctx=ast.Load()),
        body=ast.Name(id='_bcopt_store80_keep', ctx=ast.Load()), orelse=comparison.test)
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
        if options.disabled == frozenset({'losing-record-stores'}):
            transform(output)
            report['pass_counts']['experiment-losing-stores'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=tuple(args.maps.split(',')), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'losing-record-stores'})))
    report['experimental_post_compile_transform'] = 'losing-record field-store omission with preserved allocation, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
