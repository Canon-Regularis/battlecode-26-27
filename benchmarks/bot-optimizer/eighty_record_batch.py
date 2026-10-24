"""Research-only native ordered dictionary population of numeric result records.

Keep original record allocation and __dict__ access. Native dict.update consumes
zip(key_tuple, value_tuple) in source order using the sequential pair-insertion
path; do not replace the instance dictionary or defer record construction.
"""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.records import used_names
import tools.bot_optimizer.compare as measurement


def transform(folder, mapping=False):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    consumer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_region_consumer_')]
    update, zipper, keys = ('_bcopt_batch80_'+name for name in ('update', 'zip', 'keys'))
    assert not {update, zipper, keys} & used_names(tree)
    changes, inventory = [], []
    def store(node):
        return (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Subscript) and isinstance(node.targets[0].value, ast.Name)
                and isinstance(node.targets[0].slice, ast.Constant) and type(node.targets[0].slice.value) is str
                and isinstance(node.value, ast.Name))
    class Batch(ast.NodeTransformer):
        def generic_visit(self, node):
            node = super().generic_visit(node)
            for _, body in ast.iter_fields(node):
                if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                    continue
                index = 0
                while index < len(body):
                    if not store(body[index]):
                        index += 1
                        continue
                    end, target = index+1, body[index].targets[0].value.id
                    while end < len(body) and store(body[end]) and body[end].targets[0].value.id == target:
                        end += 1
                    if end-index < 4:
                        index = end
                        continue
                    before = body[index-1]
                    assert isinstance(before, ast.Assign) and isinstance(before.value, ast.Attribute) and before.value.attr == '__dict__'
                    names = tuple(part.targets[0].slice.value for part in body[index:end])
                    if inventory:
                        assert names == inventory[0]
                    else:
                        inventory.append(names)
                    values = ', '.join(part.value.id for part in body[index:end])
                    if mapping:
                        assert len(names) <= 16 and len(set(names)) == len(names)
                        literal = ast.Dict(keys=[part.targets[0].slice for part in body[index:end]],
                                           values=[part.value for part in body[index:end]])
                        replacement = [ast.Expr(value=ast.Call(func=ast.Name(id=update, ctx=ast.Load()),
                            args=[ast.Name(id=target, ctx=ast.Load()), literal], keywords=[]))]
                    else:
                        replacement = ast.parse(f'{update}({target}, {zipper}({keys}, ({values},)))').body
                    body[index:end] = replacement
                    changes.append(names)
                    index += len(replacement)
            return node
    Batch().visit(consumer)
    assert len(changes) == 2
    index = 1 if isinstance(tree.body[0], ast.Expr) else 0
    while isinstance(tree.body[index], ast.ImportFrom) and tree.body[index].module == '__future__':
        index += 1
    setup = f'import builtins as _bcopt_batch80_b\n{update} = _bcopt_batch80_b.dict.update\n'
    if not mapping:
        setup += f'{zipper} = _bcopt_batch80_b.zip\n{keys} = {inventory[0]!r}'
    tree.body[index:index] = ast.parse(setup).body
    source = ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source, str(path), 'exec')
    path.write_text(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mapping', action='store_true', help='Research exact-dict merge instead of sequential zip pairs')
    args = parser.parse_args()
    original = measurement.optimize_folder
    def compile_variant(bot, output, options):
        report = original(bot, output, options)
        if not options.disabled:
            transform(output, mapping=args.mapping)
            report['pass_counts']['experiment-record-batch'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform'] = 'ordered native record dictionary population, research only'
    report['mapping_merge'] = args.mapping
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
