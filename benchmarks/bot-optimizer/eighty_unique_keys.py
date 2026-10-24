"""Research-only set-backed reduction keys for certified unique index tuples.

Reuse the already-private frozenset as a reduction key only when its cardinality
equals the complete insertion multiset's size. Duplicates retain sorted tuples;
negative indices remain distinct values. Public generator output is unchanged.
"""

import argparse
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement
from tools.bot_optimizer.model import Options


def transform(folder):
    path = folder/'src/planner.py'
    tree = ast.parse(path.read_text())
    producer, = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name.startswith('_bcopt_insertion_key_producer')]
    changes = []
    class Keys(ast.NodeTransformer):
        def generic_visit(self, node):
            node = super().generic_visit(node)
            for _, body in ast.iter_fields(node):
                if not isinstance(body, list):
                    continue
                for index in range(len(body)-1):
                    key, members = body[index:index+2]
                    if (not isinstance(key, ast.Assign) or not isinstance(key.value, ast.Call)
                            or not isinstance(key.value.func, ast.Attribute) or key.value.func.attr != 'tuple'
                            or len(key.value.args) != 1 or not isinstance(key.value.args[0], ast.Call)
                            or not isinstance(key.value.args[0].func, ast.Attribute) or key.value.args[0].func.attr != 'sorted'):
                        continue
                    joined, = key.value.args[0].args
                    assert isinstance(joined, ast.Name)
                    assert isinstance(members, ast.Assign) and isinstance(members.value, ast.Call)
                    assert isinstance(members.value.func, ast.Attribute) and members.value.func.attr == 'frozenset'
                    assert ast.dump(members.value.args[0]) == ast.dump(joined)
                    assert isinstance(members.targets[0], ast.Name)
                    builtins = key.value.func.value.id
                    private_set = members.targets[0].id
                    condition = ast.parse(f'{builtins}.len({private_set}) == {builtins}.len({joined.id})', mode='eval').body
                    key.value = ast.IfExp(test=condition, body=ast.Name(id=private_set, ctx=ast.Load()),
                                         orelse=copy.deepcopy(key.value))
                    body[index:index+2] = [members, key]
                    changes.append(index)
                    break
            return node
    Keys().visit(producer)
    assert len(changes) == 1, changes
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
        if options.disabled == frozenset({'insertion-unique-keys'}):
            transform(output)
            report['pass_counts']['experiment-unique-keys'] = 1
        return report
    measurement.optimize_folder = compile_variant
    report = measurement.compare(args.bot, args.output, target='draft_planner:DraftPlanner.build',
                                 maps=('collision',), repeats=1, output_prefix='SQUAD_LOOPS_DATA ',
                                 options=Options(disabled=frozenset({'insertion-unique-keys'})))
    report['experimental_post_compile_transform'] = 'unique-multiset frozenset reduction keys, research only'
    (args.output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'], row['side'], row['reduction_percent'])


if __name__ == '__main__':
    main()
